"""数据层：基于 SQLite 的客户、跟进记录、商机存储。"""
import csv
import sqlite3
from datetime import datetime

CUSTOMER_STATUSES = ["潜在客户", "意向客户", "成交客户", "流失客户"]
CUSTOMER_LEVELS = ["A", "B", "C"]
DEAL_STAGES = ["初步接触", "需求确认", "方案报价", "谈判", "赢单", "输单"]
FOLLOWUP_METHODS = ["电话", "微信", "邮件", "拜访", "会议", "其他"]

CUSTOMER_FIELDS = ["name", "company", "phone", "email", "address",
                   "source", "status", "level", "owner", "notes"]
CSV_HEADERS = ["姓名", "公司", "电话", "邮箱", "地址",
               "来源", "状态", "等级", "负责人", "备注"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    company     TEXT DEFAULT '',
    phone       TEXT DEFAULT '',
    email       TEXT DEFAULT '',
    address     TEXT DEFAULT '',
    source      TEXT DEFAULT '',
    status      TEXT DEFAULT '潜在客户',
    level       TEXT DEFAULT 'C',
    owner       TEXT DEFAULT '',
    notes       TEXT DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS followups (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id  INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    method       TEXT DEFAULT '电话',
    content      TEXT NOT NULL,
    next_date    TEXT DEFAULT '',
    created_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS deals (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id  INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    title        TEXT NOT NULL,
    amount       REAL DEFAULT 0,
    stage        TEXT DEFAULT '初步接触',
    expected_date TEXT DEFAULT '',
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_followups_customer ON followups(customer_id);
CREATE INDEX IF NOT EXISTS idx_deals_customer ON deals(customer_id);
"""


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def today():
    return datetime.now().strftime("%Y-%m-%d")


class Database:
    def __init__(self, path):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self):
        self.conn.close()

    # ---------- 客户 ----------
    def add_customer(self, data):
        values = {f: (data.get(f) or "").strip() for f in CUSTOMER_FIELDS}
        if not values["name"]:
            raise ValueError("客户姓名不能为空")
        values["status"] = values["status"] or CUSTOMER_STATUSES[0]
        values["level"] = values["level"] or "C"
        ts = now()
        cur = self.conn.execute(
            f"INSERT INTO customers ({', '.join(CUSTOMER_FIELDS)}, created_at, updated_at) "
            f"VALUES ({', '.join('?' * len(CUSTOMER_FIELDS))}, ?, ?)",
            [values[f] for f in CUSTOMER_FIELDS] + [ts, ts])
        self.conn.commit()
        return cur.lastrowid

    def update_customer(self, customer_id, data):
        values = {f: (data.get(f) or "").strip() for f in CUSTOMER_FIELDS}
        if not values["name"]:
            raise ValueError("客户姓名不能为空")
        self.conn.execute(
            f"UPDATE customers SET {', '.join(f + ' = ?' for f in CUSTOMER_FIELDS)}, "
            f"updated_at = ? WHERE id = ?",
            [values[f] for f in CUSTOMER_FIELDS] + [now(), customer_id])
        self.conn.commit()

    def delete_customer(self, customer_id):
        self.conn.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
        self.conn.commit()

    def get_customer(self, customer_id):
        return self.conn.execute(
            "SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()

    def list_customers(self, keyword="", status="", level=""):
        sql = "SELECT * FROM customers WHERE 1=1"
        args = []
        if keyword:
            sql += (" AND (name LIKE ? OR company LIKE ? OR phone LIKE ?"
                    " OR email LIKE ? OR owner LIKE ?)")
            args += [f"%{keyword}%"] * 5
        if status:
            sql += " AND status = ?"
            args.append(status)
        if level:
            sql += " AND level = ?"
            args.append(level)
        sql += " ORDER BY updated_at DESC, id DESC"
        return self.conn.execute(sql, args).fetchall()

    # ---------- 跟进记录 ----------
    def add_followup(self, customer_id, method, content, next_date=""):
        content = (content or "").strip()
        if not content:
            raise ValueError("跟进内容不能为空")
        cur = self.conn.execute(
            "INSERT INTO followups (customer_id, method, content, next_date, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (customer_id, method, content, (next_date or "").strip(), now()))
        self.conn.execute("UPDATE customers SET updated_at = ? WHERE id = ?",
                          (now(), customer_id))
        self.conn.commit()
        return cur.lastrowid

    def delete_followup(self, followup_id):
        self.conn.execute("DELETE FROM followups WHERE id = ?", (followup_id,))
        self.conn.commit()

    def list_followups(self, customer_id):
        return self.conn.execute(
            "SELECT * FROM followups WHERE customer_id = ? ORDER BY created_at DESC, id DESC",
            (customer_id,)).fetchall()

    def upcoming_followups(self, days=7):
        """待办提醒：下次跟进日期在今天之前（逾期）或 days 天之内的记录。"""
        return self.conn.execute(
            "SELECT f.*, c.name AS customer_name, c.company AS company "
            "FROM followups f JOIN customers c ON c.id = f.customer_id "
            "WHERE f.next_date != '' AND f.next_date <= date('now', 'localtime', ?) "
            "AND f.id IN (SELECT MAX(id) FROM followups GROUP BY customer_id) "
            "ORDER BY f.next_date",
            (f"+{days} day",)).fetchall()

    # ---------- 商机 ----------
    def add_deal(self, customer_id, title, amount, stage, expected_date=""):
        title = (title or "").strip()
        if not title:
            raise ValueError("商机名称不能为空")
        ts = now()
        cur = self.conn.execute(
            "INSERT INTO deals (customer_id, title, amount, stage, expected_date, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (customer_id, title, float(amount or 0), stage, (expected_date or "").strip(), ts, ts))
        self.conn.commit()
        return cur.lastrowid

    def update_deal(self, deal_id, title, amount, stage, expected_date=""):
        title = (title or "").strip()
        if not title:
            raise ValueError("商机名称不能为空")
        self.conn.execute(
            "UPDATE deals SET title = ?, amount = ?, stage = ?, expected_date = ?, "
            "updated_at = ? WHERE id = ?",
            (title, float(amount or 0), stage, (expected_date or "").strip(), now(), deal_id))
        self.conn.commit()

    def delete_deal(self, deal_id):
        self.conn.execute("DELETE FROM deals WHERE id = ?", (deal_id,))
        self.conn.commit()

    def get_deal(self, deal_id):
        return self.conn.execute("SELECT * FROM deals WHERE id = ?", (deal_id,)).fetchone()

    def list_deals(self, customer_id=None, stage=""):
        sql = ("SELECT d.*, c.name AS customer_name FROM deals d "
               "JOIN customers c ON c.id = d.customer_id WHERE 1=1")
        args = []
        if customer_id is not None:
            sql += " AND d.customer_id = ?"
            args.append(customer_id)
        if stage:
            sql += " AND d.stage = ?"
            args.append(stage)
        sql += " ORDER BY d.updated_at DESC, d.id DESC"
        return self.conn.execute(sql, args).fetchall()

    # ---------- 统计 ----------
    def stats(self):
        q = lambda sql: self.conn.execute(sql).fetchone()[0]
        by_status = {s: 0 for s in CUSTOMER_STATUSES}
        for row in self.conn.execute(
                "SELECT status, COUNT(*) FROM customers GROUP BY status"):
            by_status[row[0]] = row[1]
        by_stage = {s: (0, 0.0) for s in DEAL_STAGES}
        for row in self.conn.execute(
                "SELECT stage, COUNT(*), COALESCE(SUM(amount), 0) FROM deals GROUP BY stage"):
            by_stage[row[0]] = (row[1], row[2])
        return {
            "customers": q("SELECT COUNT(*) FROM customers"),
            "new_this_month": q("SELECT COUNT(*) FROM customers WHERE "
                                "substr(created_at, 1, 7) = strftime('%Y-%m', 'now', 'localtime')"),
            "followups": q("SELECT COUNT(*) FROM followups"),
            "open_amount": q("SELECT COALESCE(SUM(amount), 0) FROM deals "
                             "WHERE stage NOT IN ('赢单', '输单')"),
            "won_amount": q("SELECT COALESCE(SUM(amount), 0) FROM deals WHERE stage = '赢单'"),
            "by_status": by_status,
            "by_stage": by_stage,
        }

    # ---------- 导入导出 ----------
    def export_customers_csv(self, path):
        rows = self.list_customers()
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADERS + ["创建时间"])
            for r in rows:
                writer.writerow([r[f] for f in CUSTOMER_FIELDS] + [r["created_at"]])
        return len(rows)

    def import_customers_csv(self, path):
        header_map = dict(zip(CSV_HEADERS, CUSTOMER_FIELDS))
        header_map.update({f: f for f in CUSTOMER_FIELDS})
        count = 0
        with open(path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                data = {header_map[k.strip()]: v for k, v in row.items()
                        if k and k.strip() in header_map}
                if (data.get("name") or "").strip():
                    self.add_customer(data)
                    count += 1
        return count
