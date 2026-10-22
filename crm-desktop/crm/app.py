"""界面层：基于 Tkinter 的桌面客户关系管理程序。"""
import os
import sys
import tkinter as tk
from tkinter import filedialog, font, messagebox, ttk

from .db import (CUSTOMER_LEVELS, CUSTOMER_STATUSES, DEAL_STAGES,
                 FOLLOWUP_METHODS, Database, today)
from .demo import load_demo_data
from .mail_ui import MailTab, display_sender

APP_TITLE = "客户关系管理系统 CRM"


def default_db_path():
    folder = os.path.join(os.path.expanduser("~"), ".crm-desktop")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "crm.db")


def money(value):
    return f"¥{value:,.2f}"


def make_tree(parent, columns, widths, height=15):
    """创建带滚动条的表格，columns 为 (key, 标题) 列表。"""
    frame = ttk.Frame(parent)
    tree = ttk.Treeview(frame, columns=[c[0] for c in columns],
                        show="headings", height=height, selectmode="browse")
    for (key, title), width in zip(columns, widths):
        tree.heading(key, text=title,
                     command=lambda k=key: sort_tree(tree, k, False))
        tree.column(key, width=width, anchor="w")
    scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    return frame, tree


def sort_tree(tree, col, reverse):
    def key(item):
        value = tree.set(item, col).replace("¥", "").replace(",", "")
        try:
            return (0, float(value), "")
        except ValueError:
            return (1, 0, value)
    items = sorted(tree.get_children(""), key=key, reverse=reverse)
    for index, item in enumerate(items):
        tree.move(item, "", index)
    tree.heading(col, command=lambda: sort_tree(tree, col, not reverse))


def selected_id(tree):
    sel = tree.selection()
    return int(sel[0]) if sel else None


class FormDialog(tk.Toplevel):
    """通用表单对话框。fields: (key, 标签, 类型, 选项)，类型为 entry/combo/text。"""

    def __init__(self, parent, title, fields, initial=None):
        super().__init__(parent)
        self.title(title)
        self.transient(parent)
        self.resizable(False, False)
        self.result = None
        self.widgets = {}
        initial = initial or {}

        body = ttk.Frame(self, padding=12)
        body.pack(fill="both", expand=True)
        for row, (key, label, kind, options) in enumerate(fields):
            ttk.Label(body, text=label).grid(row=row, column=0, sticky="ne", padx=(0, 8), pady=4)
            value = initial.get(key, "")
            value = "" if value is None else str(value)
            if kind == "combo":
                widget = ttk.Combobox(body, values=options, width=32, state="readonly")
                widget.set(value or options[0])
            elif kind == "text":
                widget = tk.Text(body, width=34, height=5, wrap="word")
                widget.insert("1.0", value)
            else:
                widget = ttk.Entry(body, width=34)
                widget.insert(0, value)
            widget.grid(row=row, column=1, sticky="we", pady=4)
            self.widgets[key] = widget

        buttons = ttk.Frame(body)
        buttons.grid(row=len(fields), column=0, columnspan=2, pady=(10, 0), sticky="e")
        ttk.Button(buttons, text="保存", command=self.on_ok).pack(side="left", padx=4)
        ttk.Button(buttons, text="取消", command=self.destroy).pack(side="left")
        self.bind("<Escape>", lambda e: self.destroy())

        first = next(iter(self.widgets.values()))
        first.focus_set()
        self.wait_visibility()
        self.grab_set()
        self.wait_window(self)

    def on_ok(self):
        data = {}
        for key, widget in self.widgets.items():
            if isinstance(widget, tk.Text):
                data[key] = widget.get("1.0", "end").strip()
            else:
                data[key] = widget.get().strip()
        self.result = data
        self.destroy()


CUSTOMER_FORM = [
    ("name", "姓名 *", "entry", None),
    ("company", "公司", "entry", None),
    ("phone", "电话", "entry", None),
    ("email", "邮箱", "entry", None),
    ("address", "地址", "entry", None),
    ("source", "客户来源", "entry", None),
    ("status", "状态", "combo", CUSTOMER_STATUSES),
    ("level", "等级", "combo", CUSTOMER_LEVELS),
    ("owner", "负责人", "entry", None),
    ("notes", "备注", "text", None),
]

DEAL_FORM = [
    ("title", "商机名称 *", "entry", None),
    ("amount", "金额（元）", "entry", None),
    ("stage", "阶段", "combo", DEAL_STAGES),
    ("expected_date", "预计成交日期", "entry", None),
]

FOLLOWUP_FORM = [
    ("method", "跟进方式", "combo", FOLLOWUP_METHODS),
    ("content", "跟进内容 *", "text", None),
    ("next_date", "下次跟进日期", "entry", None),
]


def parse_amount(text):
    try:
        return float(text or 0)
    except ValueError:
        raise ValueError("金额必须是数字")


class CustomerDetail(tk.Toplevel):
    """客户详情窗口：基本信息、跟进记录、商机。"""

    def __init__(self, app, customer_id):
        super().__init__(app.root)
        self.app = app
        self.db = app.db
        self.customer_id = customer_id
        self.geometry("820x560")

        self.info = ttk.Label(self, padding=10, justify="left", font=("", 10))
        self.info.pack(fill="x")

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # 跟进记录
        tab = ttk.Frame(notebook, padding=6)
        notebook.add(tab, text="跟进记录")
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Button(bar, text="新增跟进", command=self.add_followup).pack(side="left")
        ttk.Button(bar, text="删除跟进", command=self.delete_followup).pack(side="left", padx=4)
        frame, self.followup_tree = make_tree(
            tab, [("time", "时间"), ("method", "方式"), ("content", "内容"), ("next", "下次跟进")],
            [130, 60, 420, 100])
        frame.pack(fill="both", expand=True)

        # 商机
        tab = ttk.Frame(notebook, padding=6)
        notebook.add(tab, text="商机")
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Button(bar, text="新增商机", command=self.add_deal).pack(side="left")
        ttk.Button(bar, text="编辑商机", command=self.edit_deal).pack(side="left", padx=4)
        ttk.Button(bar, text="删除商机", command=self.delete_deal).pack(side="left")
        frame, self.deal_tree = make_tree(
            tab, [("title", "商机名称"), ("amount", "金额"), ("stage", "阶段"), ("expected", "预计成交")],
            [320, 120, 100, 120])
        frame.pack(fill="both", expand=True)
        self.deal_tree.bind("<Double-1>", lambda e: self.edit_deal())

        # 往来邮件
        tab = ttk.Frame(notebook, padding=6)
        notebook.add(tab, text="往来邮件")
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Button(bar, text="写邮件", command=self.write_email).pack(side="left")
        ttk.Label(bar, text="双击查看邮件内容", foreground="#888888").pack(side="left", padx=8)
        frame, self.email_tree = make_tree(
            tab, [("dir", "方向"), ("subject", "主题"), ("date", "时间")], [60, 520, 130])
        frame.pack(fill="both", expand=True)
        self.email_tree.bind("<Double-1>", lambda e: self.view_email())

        self.refresh()

    def refresh(self):
        c = self.db.get_customer(self.customer_id)
        if c is None:
            self.destroy()
            return
        self.title(f"客户详情 - {c['name']}")
        self.info.configure(text=(
            f"姓名：{c['name']}    公司：{c['company']}    状态：{c['status']}    等级：{c['level']}\n"
            f"电话：{c['phone']}    邮箱：{c['email']}    负责人：{c['owner']}    来源：{c['source']}\n"
            f"地址：{c['address']}\n备注：{c['notes']}"))
        self.followup_tree.delete(*self.followup_tree.get_children())
        for f in self.db.list_followups(self.customer_id):
            self.followup_tree.insert("", "end", iid=f["id"], values=(
                f["created_at"], f["method"], f["content"].replace("\n", " "), f["next_date"]))
        self.deal_tree.delete(*self.deal_tree.get_children())
        for d in self.db.list_deals(self.customer_id):
            self.deal_tree.insert("", "end", iid=d["id"], values=(
                d["title"], money(d["amount"]), d["stage"], d["expected_date"]))
        self.email_tree.delete(*self.email_tree.get_children())
        for e in self.db.emails_for_customer(self.customer_id):
            self.email_tree.insert("", "end", iid=e["id"], values=(
                "收到" if e["folder"] == "INBOX" else "发出", e["subject"] or "（无主题）", e["date"]))

    def changed(self):
        self.refresh()
        self.app.refresh_all()

    def add_followup(self):
        dlg = FormDialog(self, "新增跟进记录", FOLLOWUP_FORM)
        if dlg.result:
            try:
                self.db.add_followup(self.customer_id, **dlg.result)
            except ValueError as e:
                messagebox.showerror("错误", str(e), parent=self)
                return
            self.changed()

    def delete_followup(self):
        fid = selected_id(self.followup_tree)
        if fid and messagebox.askyesno("确认", "确定删除该跟进记录？", parent=self):
            self.db.delete_followup(fid)
            self.changed()

    def add_deal(self):
        self.app.open_deal_dialog(self, customer_id=self.customer_id)
        self.refresh()

    def edit_deal(self):
        did = selected_id(self.deal_tree)
        if did:
            self.app.open_deal_dialog(self, deal_id=did)
            self.refresh()

    def delete_deal(self):
        did = selected_id(self.deal_tree)
        if did and messagebox.askyesno("确认", "确定删除该商机？", parent=self):
            self.db.delete_deal(did)
            self.changed()

    def write_email(self):
        address = self.db.get_customer(self.customer_id)["email"].strip()
        if not address:
            messagebox.showinfo("提示", "该客户没有填写邮箱，请先编辑客户资料", parent=self)
            return
        self.app.mail.compose(to=address)

    def view_email(self):
        eid = selected_id(self.email_tree)
        if not eid:
            return
        e = self.db.get_email(eid)
        win = tk.Toplevel(self)
        win.title(e["subject"] or "（无主题）")
        win.geometry("640x480")
        text = tk.Text(win, wrap="word", padx=10, pady=10)
        text.pack(fill="both", expand=True)
        text.insert("1.0", f"主题：{e['subject']}\n发件人：{display_sender(e)}\n"
                           f"收件人：{e['recipients']}\n时间：{e['date']}\n\n{e['body']}")
        text.configure(state="disabled")


class CRMApp:
    def __init__(self, root, db):
        self.root = root
        self.db = db
        root.title(APP_TITLE)
        root.geometry("1100x680")
        root.minsize(900, 560)

        if sys.platform == "win32":
            for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
                font.nametofont(name).configure(family="Microsoft YaHei UI", size=9)
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Treeview", rowheight=26)
        style.configure("Card.TFrame", background="#ffffff", relief="solid", borderwidth=1)
        style.configure("CardTitle.TLabel", background="#ffffff", foreground="#666666")
        style.configure("CardValue.TLabel", background="#ffffff", font=("", 18, "bold"))

        self.build_menu()
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=8)
        self.build_dashboard()
        self.build_customers()
        self.build_deals()
        self.build_reminders()
        self.mail = MailTab(self, self.notebook)

        self.status = ttk.Label(root, anchor="w", padding=(8, 2))
        self.status.pack(fill="x", side="bottom")
        self.refresh_all()

    # ---------- 菜单 ----------
    def build_menu(self):
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="导入客户（CSV）...", command=self.import_csv)
        file_menu.add_command(label="导出客户（CSV）...", command=self.export_csv)
        file_menu.add_command(label="邮箱设置...", command=lambda: self.mail.settings())
        file_menu.add_command(label="载入演示数据", command=self.load_demo)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.destroy)
        menubar.add_cascade(label="文件", menu=file_menu)
        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label="关于", command=lambda: messagebox.showinfo(
            "关于", f"{APP_TITLE}\n\n数据文件：{self.db_path_text()}"))
        menubar.add_cascade(label="帮助", menu=help_menu)
        self.root.config(menu=menubar)

    def db_path_text(self):
        return self.db.conn.execute("PRAGMA database_list").fetchone()[2] or "内存"

    # ---------- 仪表盘 ----------
    def build_dashboard(self):
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="  仪表盘  ")
        cards = ttk.Frame(tab)
        cards.pack(fill="x")
        self.card_vars = {}
        for i, (key, title) in enumerate([
                ("customers", "客户总数"), ("new_this_month", "本月新增客户"),
                ("followups", "跟进记录数"), ("open_amount", "进行中商机金额"),
                ("won_amount", "已赢单金额")]):
            card = ttk.Frame(cards, style="Card.TFrame", padding=14)
            card.grid(row=0, column=i, sticky="nsew", padx=6)
            cards.columnconfigure(i, weight=1)
            ttk.Label(card, text=title, style="CardTitle.TLabel").pack(anchor="w")
            var = tk.StringVar(value="0")
            ttk.Label(card, textvariable=var, style="CardValue.TLabel").pack(anchor="w", pady=(6, 0))
            self.card_vars[key] = var

        lower = ttk.Frame(tab)
        lower.pack(fill="both", expand=True, pady=(16, 0))
        lower.columnconfigure(0, weight=1)
        lower.columnconfigure(1, weight=1)
        lower.rowconfigure(1, weight=1)
        ttk.Label(lower, text="客户状态分布", font=("", 11, "bold")).grid(row=0, column=0, sticky="w", padx=6)
        ttk.Label(lower, text="销售漏斗（商机阶段）", font=("", 11, "bold")).grid(row=0, column=1, sticky="w", padx=6)
        self.status_canvas = tk.Canvas(lower, background="#ffffff", highlightthickness=1,
                                       highlightbackground="#cccccc")
        self.status_canvas.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)
        self.stage_canvas = tk.Canvas(lower, background="#ffffff", highlightthickness=1,
                                      highlightbackground="#cccccc")
        self.stage_canvas.grid(row=1, column=1, sticky="nsew", padx=6, pady=6)
        self.status_canvas.bind("<Configure>", lambda e: self.refresh_dashboard())
        self.stage_canvas.bind("<Configure>", lambda e: self.refresh_dashboard())

    def draw_bars(self, canvas, rows, color):
        """rows: (标签, 数值, 显示文本) 列表，绘制横向条形图。"""
        canvas.delete("all")
        width = max(canvas.winfo_width(), 200)
        label_w, pad, bar_h = 90, 16, 26
        max_value = max([r[1] for r in rows] + [1])
        for i, (label, value, text) in enumerate(rows):
            y = pad + i * (bar_h + 14)
            canvas.create_text(pad, y + bar_h / 2, text=label, anchor="w", font=("", 10))
            bar_w = (width - label_w - pad * 2 - 130) * value / max_value
            canvas.create_rectangle(label_w, y, label_w + max(bar_w, 2), y + bar_h,
                                    fill=color, outline="")
            canvas.create_text(label_w + max(bar_w, 2) + 8, y + bar_h / 2, text=text,
                               anchor="w", font=("", 10), fill="#333333")

    def refresh_dashboard(self):
        s = self.db.stats()
        for key in ("customers", "new_this_month", "followups"):
            self.card_vars[key].set(str(s[key]))
        self.card_vars["open_amount"].set(money(s["open_amount"]))
        self.card_vars["won_amount"].set(money(s["won_amount"]))
        self.draw_bars(self.status_canvas,
                       [(k, v, f"{v} 位") for k, v in s["by_status"].items()], "#4a90d9")
        self.draw_bars(self.stage_canvas,
                       [(k, amt, f"{n} 个 / {money(amt)}") for k, (n, amt) in s["by_stage"].items()],
                       "#50b37a")

    # ---------- 客户 ----------
    def build_customers(self):
        tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(tab, text="  客户管理  ")
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 8))
        ttk.Label(bar, text="搜索：").pack(side="left")
        self.search_var = tk.StringVar()
        entry = ttk.Entry(bar, textvariable=self.search_var, width=24)
        entry.pack(side="left")
        entry.bind("<Return>", lambda e: self.refresh_customers())
        ttk.Label(bar, text="  状态：").pack(side="left")
        self.status_filter = ttk.Combobox(bar, values=["全部"] + CUSTOMER_STATUSES,
                                          width=10, state="readonly")
        self.status_filter.set("全部")
        self.status_filter.pack(side="left")
        ttk.Label(bar, text="  等级：").pack(side="left")
        self.level_filter = ttk.Combobox(bar, values=["全部"] + CUSTOMER_LEVELS,
                                         width=6, state="readonly")
        self.level_filter.set("全部")
        self.level_filter.pack(side="left")
        for combo in (self.status_filter, self.level_filter):
            combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_customers())
        ttk.Button(bar, text="查询", command=self.refresh_customers).pack(side="left", padx=6)

        actions = ttk.Frame(tab)
        actions.pack(fill="x", pady=(0, 8), before=bar)
        for text, cmd in [("新增客户", self.add_customer), ("编辑", self.edit_customer),
                          ("详情 / 跟进", self.open_detail), ("发邮件", self.email_customer),
                          ("删除", self.delete_customer)]:
            ttk.Button(actions, text=text, command=cmd).pack(side="left", padx=(0, 4))

        frame, self.customer_tree = make_tree(
            tab, [("name", "姓名"), ("company", "公司"), ("phone", "电话"), ("email", "邮箱"),
                  ("status", "状态"), ("level", "等级"), ("owner", "负责人"), ("updated", "最近更新")],
            [100, 200, 120, 180, 80, 50, 80, 130], height=20)
        frame.pack(fill="both", expand=True)
        self.customer_tree.bind("<Double-1>", lambda e: self.open_detail())
        self.customer_tree.bind("<Delete>", lambda e: self.delete_customer())

    def refresh_customers(self):
        status = self.status_filter.get()
        level = self.level_filter.get()
        rows = self.db.list_customers(self.search_var.get().strip(),
                                      "" if status == "全部" else status,
                                      "" if level == "全部" else level)
        tree = self.customer_tree
        tree.delete(*tree.get_children())
        for c in rows:
            tree.insert("", "end", iid=c["id"], values=(
                c["name"], c["company"], c["phone"], c["email"],
                c["status"], c["level"], c["owner"], c["updated_at"]))
        self.status.configure(text=f"共 {len(rows)} 位客户    数据文件：{self.db_path_text()}")

    def add_customer(self, initial=None):
        dlg = FormDialog(self.root, "新增客户", CUSTOMER_FORM, initial)
        if dlg.result:
            try:
                self.db.add_customer(dlg.result)
            except ValueError as e:
                messagebox.showerror("错误", str(e))
                return
            self.refresh_all()

    def edit_customer(self):
        cid = selected_id(self.customer_tree)
        if not cid:
            messagebox.showinfo("提示", "请先选择一个客户")
            return
        dlg = FormDialog(self.root, "编辑客户", CUSTOMER_FORM, dict(self.db.get_customer(cid)))
        if dlg.result:
            try:
                self.db.update_customer(cid, dlg.result)
            except ValueError as e:
                messagebox.showerror("错误", str(e))
                return
            self.refresh_all()

    def delete_customer(self):
        cid = selected_id(self.customer_tree)
        if not cid:
            return
        name = self.db.get_customer(cid)["name"]
        if messagebox.askyesno("确认删除", f"确定删除客户「{name}」？\n其跟进记录和商机将一并删除。"):
            self.db.delete_customer(cid)
            self.refresh_all()

    def email_customer(self):
        cid = selected_id(self.customer_tree)
        if not cid:
            messagebox.showinfo("提示", "请先选择一个客户")
            return
        address = self.db.get_customer(cid)["email"].strip()
        if not address:
            messagebox.showinfo("提示", "该客户没有填写邮箱，请先编辑客户资料")
            return
        self.mail.compose(to=address)

    def open_detail(self, cid=None):
        cid = cid or selected_id(self.customer_tree)
        if not cid:
            messagebox.showinfo("提示", "请先选择一个客户")
            return
        CustomerDetail(self, cid)

    # ---------- 商机 ----------
    def build_deals(self):
        tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(tab, text="  商机管理  ")
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 8))
        ttk.Label(bar, text="阶段：").pack(side="left")
        self.stage_filter = ttk.Combobox(bar, values=["全部"] + DEAL_STAGES, width=10, state="readonly")
        self.stage_filter.set("全部")
        self.stage_filter.pack(side="left")
        self.stage_filter.bind("<<ComboboxSelected>>", lambda e: self.refresh_deals())
        self.deal_summary = ttk.Label(bar)
        self.deal_summary.pack(side="left", padx=16)
        ttk.Button(bar, text="删除", command=self.delete_deal).pack(side="right", padx=2)
        ttk.Button(bar, text="编辑", command=self.edit_deal).pack(side="right", padx=2)

        frame, self.deal_tree = make_tree(
            tab, [("title", "商机名称"), ("customer", "客户"), ("amount", "金额"),
                  ("stage", "阶段"), ("expected", "预计成交"), ("updated", "最近更新")],
            [280, 140, 130, 100, 110, 130], height=20)
        frame.pack(fill="both", expand=True)
        self.deal_tree.bind("<Double-1>", lambda e: self.edit_deal())
        ttk.Label(tab, text="提示：在「客户管理」中打开客户详情即可为该客户新增商机。",
                  foreground="#888888").pack(anchor="w", pady=(6, 0))

    def refresh_deals(self):
        stage = self.stage_filter.get()
        rows = self.db.list_deals(stage="" if stage == "全部" else stage)
        tree = self.deal_tree
        tree.delete(*tree.get_children())
        for d in rows:
            tree.insert("", "end", iid=d["id"], values=(
                d["title"], d["customer_name"], money(d["amount"]), d["stage"],
                d["expected_date"], d["updated_at"]))
        total = sum(d["amount"] for d in rows)
        self.deal_summary.configure(text=f"共 {len(rows)} 个商机，合计 {money(total)}")

    def open_deal_dialog(self, parent, customer_id=None, deal_id=None):
        initial = dict(self.db.get_deal(deal_id)) if deal_id else {"expected_date": today()}
        dlg = FormDialog(parent, "编辑商机" if deal_id else "新增商机", DEAL_FORM, initial)
        if not dlg.result:
            return
        data = dlg.result
        try:
            amount = parse_amount(data["amount"])
            if deal_id:
                self.db.update_deal(deal_id, data["title"], amount, data["stage"], data["expected_date"])
            else:
                self.db.add_deal(customer_id, data["title"], amount, data["stage"], data["expected_date"])
        except ValueError as e:
            messagebox.showerror("错误", str(e), parent=parent)
            return
        self.refresh_all()

    def edit_deal(self):
        did = selected_id(self.deal_tree)
        if did:
            self.open_deal_dialog(self.root, deal_id=did)

    def delete_deal(self):
        did = selected_id(self.deal_tree)
        if did and messagebox.askyesno("确认", "确定删除该商机？"):
            self.db.delete_deal(did)
            self.refresh_all()

    # ---------- 待办提醒 ----------
    def build_reminders(self):
        tab = ttk.Frame(self.notebook, padding=8)
        self.reminder_tab = tab
        self.notebook.add(tab, text="  待办提醒  ")
        ttk.Label(tab, text="以下客户需要在 7 天内跟进（红色为已逾期），双击打开客户详情：").pack(anchor="w", pady=(0, 8))
        frame, self.reminder_tree = make_tree(
            tab, [("date", "计划跟进日期"), ("customer", "客户"), ("company", "公司"),
                  ("last", "上次跟进内容")],
            [120, 120, 200, 480], height=20)
        frame.pack(fill="both", expand=True)
        self.reminder_tree.tag_configure("overdue", foreground="#d0021b")
        self.reminder_tree.bind("<Double-1>", self.open_reminder)
        self.reminder_customer = {}

    def refresh_reminders(self):
        tree = self.reminder_tree
        tree.delete(*tree.get_children())
        self.reminder_customer.clear()
        rows = self.db.upcoming_followups()
        for f in rows:
            tags = ("overdue",) if f["next_date"] < today() else ()
            tree.insert("", "end", iid=f["id"], tags=tags, values=(
                f["next_date"], f["customer_name"], f["company"], f["content"].replace("\n", " ")))
            self.reminder_customer[f["id"]] = f["customer_id"]
        self.notebook.tab(self.reminder_tab, text=f"  待办提醒 ({len(rows)})  ")

    def open_reminder(self, _event=None):
        fid = selected_id(self.reminder_tree)
        if fid:
            self.open_detail(self.reminder_customer[fid])

    # ---------- 导入导出 ----------
    def export_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="客户列表.csv",
                                            filetypes=[("CSV 文件", "*.csv")])
        if path:
            n = self.db.export_customers_csv(path)
            messagebox.showinfo("导出完成", f"已导出 {n} 位客户到：\n{path}")

    def import_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV 文件", "*.csv")])
        if not path:
            return
        try:
            n = self.db.import_customers_csv(path)
        except (OSError, UnicodeDecodeError, ValueError) as e:
            messagebox.showerror("导入失败", str(e))
            return
        self.refresh_all()
        messagebox.showinfo("导入完成", f"成功导入 {n} 位客户")

    def load_demo(self):
        if messagebox.askyesno("载入演示数据", "将向当前数据库添加 5 位演示客户及其跟进记录和商机，是否继续？"):
            load_demo_data(self.db)
            self.refresh_all()

    def refresh_all(self):
        self.refresh_dashboard()
        self.refresh_customers()
        self.refresh_deals()
        self.refresh_reminders()
        self.mail.refresh()


def main(db_path=None):
    db = Database(db_path or default_db_path())
    root = tk.Tk()
    CRMApp(root, db)
    try:
        root.mainloop()
    finally:
        db.close()
