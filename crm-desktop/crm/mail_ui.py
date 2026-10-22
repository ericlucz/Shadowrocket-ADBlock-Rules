"""邮件界面：邮件标签页、写邮件窗口、邮箱设置窗口。"""
import queue
import threading
import tkinter as tk
from email.utils import getaddresses
from tkinter import messagebox, ttk

from . import mail
from .db import now as mail_now

AUTO_CHECK_MS = 5 * 60 * 1000  # 自动收信间隔


def run_in_background(widget, func, on_done, on_error):
    """在后台线程执行 func（网络操作），完成后回到界面线程调用回调，避免界面卡住。"""
    result = queue.Queue()

    def worker():
        try:
            result.put((True, func()))
        except Exception as e:  # noqa: BLE001 - 所有错误都要回传给界面显示
            result.put((False, e))

    def poll():
        try:
            ok, value = result.get_nowait()
        except queue.Empty:
            widget.after(100, poll)
            return
        (on_done if ok else on_error)(value)

    threading.Thread(target=worker, daemon=True).start()
    widget.after(100, poll)


def display_sender(e):
    if e["sender"] and e["sender"] != e["sender_addr"]:
        return f"{e['sender']} <{e['sender_addr']}>"
    return e["sender_addr"]


def error_text(e):
    return str(e) if isinstance(e, mail.MailError) else f"{type(e).__name__}: {e}"


class MailSettingsDialog(tk.Toplevel):
    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.title("邮箱设置")
        self.transient(parent)
        self.resizable(False, False)
        self.saved = False
        cfg = db.get_settings(mail.CONFIG_KEYS)

        body = ttk.Frame(self, padding=14)
        body.pack(fill="both", expand=True)
        self.vars = {k: tk.StringVar(value=cfg[k]) for k in mail.CONFIG_KEYS}
        self.vars["imap_ssl"].set(cfg["imap_ssl"] or "1")
        self.vars["smtp_ssl"].set(cfg["smtp_ssl"] or "1")

        row = 0
        ttk.Label(body, text="邮箱类型").grid(row=row, column=0, sticky="e", padx=(0, 8), pady=4)
        self.preset = ttk.Combobox(body, values=list(mail.PRESETS) + ["其他（手动填写）"],
                                   state="readonly", width=30)
        self.preset.grid(row=row, column=1, columnspan=3, sticky="w", pady=4)
        self.preset.bind("<<ComboboxSelected>>", lambda e: self.apply_preset())

        fields = [("mail_address", "邮箱地址"), ("mail_password", "授权码 / 密码"),
                  ("mail_name", "发件人名称")]
        for key, label in fields:
            row += 1
            ttk.Label(body, text=label).grid(row=row, column=0, sticky="e", padx=(0, 8), pady=4)
            entry = ttk.Entry(body, textvariable=self.vars[key], width=34,
                              show="*" if key == "mail_password" else "")
            entry.grid(row=row, column=1, columnspan=3, sticky="w", pady=4)
            if key == "mail_address":
                entry.bind("<FocusOut>", lambda e: self.auto_preset())
        row += 1
        ttk.Label(body, text="QQ、163 等邮箱需在网页版「设置 → 账户」中开启 IMAP/SMTP 服务，\n"
                             "并使用生成的「授权码」代替登录密码。",
                  foreground="#888888").grid(row=row, column=1, columnspan=3, sticky="w")

        for proto in ("imap", "smtp"):
            row += 1
            ttk.Label(body, text="收信服务器 (IMAP)" if proto == "imap" else "发信服务器 (SMTP)").grid(
                row=row, column=0, sticky="e", padx=(0, 8), pady=4)
            ttk.Entry(body, textvariable=self.vars[f"{proto}_host"], width=22).grid(
                row=row, column=1, sticky="w", pady=4)
            ttk.Entry(body, textvariable=self.vars[f"{proto}_port"], width=6).grid(
                row=row, column=2, sticky="w", padx=4)
            ttk.Checkbutton(body, text="SSL", variable=self.vars[f"{proto}_ssl"],
                            onvalue="1", offvalue="0").grid(row=row, column=3, sticky="w")

        row += 1
        buttons = ttk.Frame(body)
        buttons.grid(row=row, column=0, columnspan=4, sticky="e", pady=(12, 0))
        self.status = ttk.Label(buttons, foreground="#666666")
        self.status.pack(side="left", padx=(0, 12))
        self.test_btn = ttk.Button(buttons, text="测试连接", command=self.test)
        self.test_btn.pack(side="left", padx=4)
        ttk.Button(buttons, text="保存", command=self.save).pack(side="left", padx=4)
        ttk.Button(buttons, text="取消", command=self.destroy).pack(side="left")

        self.preset.set(next((n for n, p in mail.PRESETS.items() if p[0] == cfg["imap_host"]),
                             "其他（手动填写）" if cfg["imap_host"] else "QQ 邮箱"))
        if not cfg["imap_host"]:
            self.apply_preset()
        self.wait_visibility()
        self.grab_set()
        self.wait_window(self)

    def apply_preset(self):
        preset = mail.PRESETS.get(self.preset.get())
        if preset:
            for key, value in zip(("imap_host", "imap_port", "smtp_host", "smtp_port"), preset):
                self.vars[key].set(str(value))
            self.vars["imap_ssl"].set("1")
            self.vars["smtp_ssl"].set("1")

    def auto_preset(self):
        name = mail.guess_preset(self.vars["mail_address"].get().strip())
        if name and self.preset.get() != name:
            self.preset.set(name)
            self.apply_preset()

    def config(self):
        return {k: v.get().strip() for k, v in self.vars.items()}

    def validate(self, cfg):
        for key, label in [("mail_address", "邮箱地址"), ("mail_password", "授权码"),
                           ("imap_host", "收信服务器"), ("smtp_host", "发信服务器")]:
            if not cfg[key]:
                messagebox.showerror("错误", f"请填写{label}", parent=self)
                return False
        return True

    def test(self):
        cfg = self.config()
        if not self.validate(cfg):
            return
        self.status.configure(text="正在连接…")
        self.test_btn.state(["disabled"])

        def done(_):
            self.status.configure(text="")
            self.test_btn.state(["!disabled"])
            messagebox.showinfo("测试成功", "收信和发信服务器均连接成功！", parent=self)

        def fail(e):
            self.status.configure(text="")
            self.test_btn.state(["!disabled"])
            messagebox.showerror("测试失败", error_text(e), parent=self)

        run_in_background(self, lambda: mail.test_connection(cfg), done, fail)

    def save(self):
        cfg = self.config()
        if not self.validate(cfg):
            return
        old = self.db.get_settings(["mail_address", "imap_host"])
        if (old["mail_address"], old["imap_host"]) != (cfg["mail_address"], cfg["imap_host"]):
            cfg.update(imap_last_uid="0", imap_uidvalidity="")  # 换了邮箱，重新收取
        self.db.save_settings(cfg)
        self.saved = True
        self.destroy()


class ComposeDialog(tk.Toplevel):
    """写邮件窗口。发送成功后保存到「已发送」，并给对应客户记一条「邮件」跟进。"""

    def __init__(self, mail_tab, to="", subject="", body=""):
        super().__init__(mail_tab.app.root)
        self.mail_tab = mail_tab
        self.db = mail_tab.db
        self.title("写邮件")
        self.geometry("640x520")
        self.transient(mail_tab.app.root)

        form = ttk.Frame(self, padding=10)
        form.pack(fill="both", expand=True)
        form.columnconfigure(1, weight=1)
        self.entries = {}
        for row, (key, label, value) in enumerate(
                [("to", "收件人", to), ("cc", "抄送", ""), ("subject", "主题", subject)]):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="e", padx=(0, 8), pady=3)
            entry = ttk.Entry(form)
            entry.insert(0, value)
            entry.grid(row=row, column=1, sticky="we", pady=3)
            self.entries[key] = entry
        self.body = tk.Text(form, wrap="word", undo=True)
        self.body.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(6, 0))
        self.body.insert("1.0", body)
        form.rowconfigure(3, weight=1)

        bar = ttk.Frame(form)
        bar.grid(row=4, column=0, columnspan=2, sticky="we", pady=(8, 0))
        self.log_var = tk.IntVar(value=1)
        ttk.Checkbutton(bar, text="发送后记录到客户跟进", variable=self.log_var).pack(side="left")
        self.status = ttk.Label(bar, foreground="#666666")
        self.status.pack(side="left", padx=12)
        ttk.Button(bar, text="取消", command=self.destroy).pack(side="right")
        self.send_btn = ttk.Button(bar, text="发送", command=self.send)
        self.send_btn.pack(side="right", padx=4)

        (self.entries["to"] if not to else self.entries["subject"] if not subject else self.body).focus_set()

    def send(self):
        cfg = self.mail_tab.config()
        if not cfg:
            return
        to = self.entries["to"].get().strip()
        cc = self.entries["cc"].get().strip()
        subject = self.entries["subject"].get().strip()
        body = self.body.get("1.0", "end").rstrip()
        if not subject and not messagebox.askyesno("提示", "邮件没有主题，确定发送吗？", parent=self):
            return
        self.send_btn.state(["disabled"])
        self.status.configure(text="正在发送…")

        def done(msg):
            recipients = [a.lower() for _, a in getaddresses([to, cc]) if a]
            self.db.save_email("SENT", {
                "message_id": msg["Message-ID"], "sender": cfg.get("mail_name") or cfg["mail_address"],
                "sender_addr": cfg["mail_address"], "recipients": ", ".join(recipients),
                "subject": subject, "date": mail_now(), "body": body}, is_read=1)
            if self.log_var.get():
                for addr in recipients:
                    customer = self.db.find_customer_by_email(addr)
                    if customer:
                        self.db.add_followup(customer["id"], "邮件", f"发送邮件：{subject or '（无主题）'}")
            self.mail_tab.app.refresh_all()
            self.destroy()
            messagebox.showinfo("发送成功", "邮件已发送")

        def fail(e):
            self.send_btn.state(["!disabled"])
            self.status.configure(text="")
            messagebox.showerror("发送失败", error_text(e), parent=self)

        run_in_background(self, lambda: mail.send_mail(cfg, to, subject, body, cc), done, fail)


class MailTab:
    def __init__(self, app, notebook):
        self.app = app
        self.db = app.db
        self.notebook = notebook
        self.fetching = False
        self.tab = ttk.Frame(notebook, padding=8)
        notebook.add(self.tab, text="  邮件  ")

        bar = ttk.Frame(self.tab)
        bar.pack(fill="x", pady=(0, 8))
        self.fetch_btn = ttk.Button(bar, text="收信", command=self.fetch)
        self.fetch_btn.pack(side="left")
        for text, cmd in [("写邮件", lambda: self.compose()), ("回复", self.reply),
                          ("转发", self.forward), ("删除", self.delete), ("邮箱设置", self.settings)]:
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=(4, 0))
        self.status = ttk.Label(bar, foreground="#666666")
        self.status.pack(side="left", padx=12)

        bar2 = ttk.Frame(self.tab)
        bar2.pack(fill="x", pady=(0, 8))
        self.folder = tk.StringVar(value="INBOX")
        for text, value in [("收件箱", "INBOX"), ("已发送", "SENT")]:
            ttk.Radiobutton(bar2, text=text, value=value, variable=self.folder,
                            command=self.refresh).pack(side="left", padx=(0, 8))
        self.only_customers = tk.IntVar(value=0)
        ttk.Checkbutton(bar2, text="只看客户邮件", variable=self.only_customers,
                        command=self.refresh).pack(side="left", padx=8)
        ttk.Label(bar2, text="搜索：").pack(side="left", padx=(16, 0))
        self.search_var = tk.StringVar()
        entry = ttk.Entry(bar2, textvariable=self.search_var, width=24)
        entry.pack(side="left")
        entry.bind("<Return>", lambda e: self.refresh())

        paned = ttk.PanedWindow(self.tab, orient="vertical")
        paned.pack(fill="both", expand=True)
        top = ttk.Frame(paned)
        self.tree = ttk.Treeview(top, columns=("who", "subject", "date", "customer"),
                                 show="headings", selectmode="browse", height=10)
        for key, title, width in [("who", "发件人", 200), ("subject", "主题", 460),
                                  ("date", "时间", 130), ("customer", "关联客户", 120)]:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor="w")
        self.tree.tag_configure("unread", font=("", 9, "bold"))
        scroll = ttk.Scrollbar(top, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.show_selected())
        self.tree.bind("<Double-1>", lambda e: self.reply())
        self.tree.bind("<Delete>", lambda e: self.delete())
        paned.add(top, weight=1)

        bottom = ttk.Frame(paned)
        head = ttk.Frame(bottom)
        head.pack(fill="x", pady=(6, 4))
        self.header = ttk.Label(head, justify="left")
        self.header.pack(side="left", fill="x", expand=True)
        self.customer_btn = ttk.Button(head, command=self.customer_action)
        self.preview = tk.Text(bottom, wrap="word", height=12, state="disabled",
                               background="#ffffff", relief="solid", borderwidth=1)
        self.preview.pack(fill="both", expand=True)
        paned.add(bottom, weight=1)

        self.current = None
        self.refresh()
        self.tab.after(2000, self.auto_check)

    # ---------- 配置 ----------
    def config(self, ask=True):
        cfg = self.db.get_settings(mail.CONFIG_KEYS)
        if cfg["mail_address"] and cfg["mail_password"] and cfg["imap_host"]:
            return cfg
        if ask and messagebox.askyesno("尚未设置邮箱", "还没有设置邮箱账户，现在设置吗？"):
            if MailSettingsDialog(self.app.root, self.db).saved:
                return self.db.get_settings(mail.CONFIG_KEYS)
        return None

    def settings(self):
        if MailSettingsDialog(self.app.root, self.db).saved:
            self.fetch()

    # ---------- 列表 ----------
    def customer_names(self):
        return {c["email"].strip().lower(): c["name"] for c in self.db.list_customers() if c["email"].strip()}

    def refresh(self):
        folder = self.folder.get()
        names = self.customer_names()
        self.tree.heading("who", text="发件人" if folder == "INBOX" else "收件人")
        self.tree.delete(*self.tree.get_children())
        for e in self.db.list_emails(folder, self.search_var.get().strip()):
            addrs = [e["sender_addr"]] if folder == "INBOX" else e["recipients"].split(", ")
            customer = "、".join(names[a] for a in addrs if a in names)
            if self.only_customers.get() and not customer:
                continue
            who = display_sender(e) if folder == "INBOX" else e["recipients"]
            self.tree.insert("", "end", iid=e["id"], values=(
                who, e["subject"] or "（无主题）", e["date"], customer),
                tags=("unread",) if not e["is_read"] else ())
        self.show_email(None)
        unread = self.db.unread_count()
        self.notebook.tab(self.tab, text=f"  邮件 ({unread})  " if unread else "  邮件  ")
        cfg = self.db.get_settings(["mail_address"])
        if not self.fetching:
            self.status.configure(text=f"账户：{cfg['mail_address']}" if cfg["mail_address"]
                                  else "尚未设置邮箱，请点击「邮箱设置」")

    def show_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        e = self.db.get_email(int(sel[0]))
        if e and not e["is_read"]:
            self.db.mark_email_read(e["id"])
            self.tree.item(sel[0], tags=())
            unread = self.db.unread_count()
            self.notebook.tab(self.tab, text=f"  邮件 ({unread})  " if unread else "  邮件  ")
        self.show_email(e)

    def show_email(self, e):
        self.current = e
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.customer_btn.pack_forget()
        if e is None:
            self.header.configure(text="")
        else:
            lines = [f"主题：{e['subject'] or '（无主题）'}",
                     f"发件人：{display_sender(e)}",
                     f"收件人：{e['recipients']}", f"时间：{e['date']}"]
            if e["attachments"]:
                lines.append(f"附件：{e['attachments']}（请在邮箱中查看）")
            self.header.configure(text="\n".join(lines))
            self.preview.insert("1.0", e["body"])
            addr = self.counterpart(e)
            if addr:
                self.customer_btn.configure(
                    text="打开客户" if self.db.find_customer_by_email(addr) else "添加为客户")
                self.customer_btn.pack(side="right")
        self.preview.configure(state="disabled")

    def counterpart(self, e):
        """邮件对方的地址：收件箱取发件人，已发送取第一个收件人；自己的地址不算。"""
        me = self.db.get_settings(["mail_address"])["mail_address"].lower()
        if e["folder"] == "INBOX" and e["sender_addr"] != me:
            return e["sender_addr"]
        return next((a for a in e["recipients"].split(", ") if a and a != me), "")

    def customer_action(self):
        e = self.current
        addr = self.counterpart(e) if e else ""
        if not addr:
            return
        customer = self.db.find_customer_by_email(addr)
        if customer:
            self.app.open_detail(customer["id"])
            return
        name = e["sender"] if e["folder"] == "INBOX" and e["sender"] != addr else addr.split("@")[0]
        self.app.add_customer({"name": name, "email": addr, "source": "邮件"})
        self.show_email(e)

    # ---------- 操作 ----------
    def fetch(self, quiet=False):
        if self.fetching:
            return
        cfg = self.config(ask=not quiet)
        if not cfg:
            return
        state = self.db.get_settings(["imap_last_uid", "imap_uidvalidity"])
        since = int(state["imap_last_uid"] or 0)
        self.fetching = True
        self.fetch_btn.state(["disabled"])
        self.status.configure(text="正在收信…")

        def task():
            validity, items = mail.fetch_inbox(cfg, since)
            if state["imap_uidvalidity"] and validity != state["imap_uidvalidity"]:
                validity, items = mail.fetch_inbox(cfg, 0)  # 服务器重建了邮箱，重新收取
            return validity, items

        def done(result):
            validity, items = result
            new = sum(self.db.save_email("INBOX", item) for item in items)
            last = max([i["uid"] for i in items] + [since if validity == state["imap_uidvalidity"] else 0])
            self.db.save_settings({"imap_last_uid": last, "imap_uidvalidity": validity})
            self.fetching = False
            self.fetch_btn.state(["!disabled"])
            self.refresh()
            self.status.configure(text=f"收信完成，新邮件 {new} 封    {mail_now()}")

        def fail(e):
            self.fetching = False
            self.fetch_btn.state(["!disabled"])
            self.status.configure(text="收信失败")
            if not quiet:
                messagebox.showerror("收信失败", error_text(e))

        run_in_background(self.tab, task, done, fail)

    def auto_check(self):
        self.fetch(quiet=True)
        self.tab.after(AUTO_CHECK_MS, self.auto_check)

    def compose(self, to="", subject="", body=""):
        if self.config():
            ComposeDialog(self, to, subject, body)

    def quoted(self, e):
        quote = "\n".join("> " + line for line in e["body"].splitlines())
        return f"\n\n\n------ 原始邮件 ------\n发件人：{display_sender(e)}\n" \
               f"时间：{e['date']}\n主题：{e['subject']}\n\n{quote}"

    def reply(self):
        e = self.current
        if not e:
            return
        subject = e["subject"] if e["subject"].lower().startswith(("re:", "回复")) else f"Re: {e['subject']}"
        self.compose(self.counterpart(e), subject, self.quoted(e))

    def forward(self):
        e = self.current
        if e:
            self.compose("", f"Fwd: {e['subject']}", self.quoted(e))

    def delete(self):
        e = self.current
        if e and messagebox.askyesno("确认", "从本程序中删除这封邮件？\n（不会删除邮箱服务器上的邮件）"):
            self.db.delete_email(e["id"])
            self.refresh()
