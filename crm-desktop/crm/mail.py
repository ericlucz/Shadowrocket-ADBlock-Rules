"""邮件收发：IMAP 收信、SMTP 发信，以及邮件解析。"""
import email
import imaplib
import re
import smtplib
import ssl
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import formataddr, getaddresses, parseaddr, parsedate_to_datetime
from html import unescape

# 常见邮箱的服务器设置：(IMAP 服务器, IMAP 端口, SMTP 服务器, SMTP 端口)，均为 SSL
PRESETS = {
    "QQ 邮箱": ("imap.qq.com", 993, "smtp.qq.com", 465),
    "腾讯企业邮": ("imap.exmail.qq.com", 993, "smtp.exmail.qq.com", 465),
    "163 邮箱": ("imap.163.com", 993, "smtp.163.com", 465),
    "126 邮箱": ("imap.126.com", 993, "smtp.126.com", 465),
    "阿里企业邮": ("imap.qiye.aliyun.com", 993, "smtp.qiye.aliyun.com", 465),
    "新浪邮箱": ("imap.sina.com", 993, "smtp.sina.com", 465),
    "Gmail": ("imap.gmail.com", 993, "smtp.gmail.com", 465),
    "Outlook / Hotmail": ("outlook.office365.com", 993, "smtp.office365.com", 587),
}

CONFIG_KEYS = ["mail_address", "mail_password", "mail_name", "imap_host", "imap_port",
               "imap_ssl", "smtp_host", "smtp_port", "smtp_ssl"]

# 163/126 等网易邮箱要求客户端登录后发送 ID 命令，否则拒绝访问（Unsafe Login）
imaplib.Commands.setdefault("ID", ("AUTH",))


class MailError(Exception):
    pass


def guess_preset(address):
    domain = address.rsplit("@", 1)[-1].lower()
    return {"qq.com": "QQ 邮箱", "foxmail.com": "QQ 邮箱", "163.com": "163 邮箱",
            "126.com": "126 邮箱", "sina.com": "新浪邮箱", "gmail.com": "Gmail",
            "outlook.com": "Outlook / Hotmail", "hotmail.com": "Outlook / Hotmail"}.get(domain)


def decode_str(value):
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except (UnicodeDecodeError, LookupError, ValueError):
        return value


def html_to_text(html):
    html = re.sub(r"(?is)<(script|style).*?</\1>", "", html)
    html = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</h\d>", "\n", html)
    text = unescape(re.sub(r"<[^>]+>", "", html))
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def get_body(msg):
    """取邮件正文：优先纯文本，没有则把 HTML 转成文本。"""
    plain, html = None, None
    for part in msg.walk() if msg.is_multipart() else [msg]:
        if part.get_content_maintype() == "multipart" or part.get_filename():
            continue
        ctype = part.get_content_type()
        if ctype not in ("text/plain", "text/html"):
            continue
        payload = part.get_payload(decode=True) or b""
        charset = part.get_content_charset() or "utf-8"
        if charset.lower() in ("gb2312", "gbk"):
            charset = "gb18030"
        try:
            text = payload.decode(charset, errors="replace")
        except LookupError:
            text = payload.decode("utf-8", errors="replace")
        if ctype == "text/plain" and plain is None:
            plain = text
        elif ctype == "text/html" and html is None:
            html = text
    text = plain if plain is not None else html_to_text(html) if html else ""
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def attachment_names(msg):
    return [decode_str(p.get_filename()) for p in msg.walk() if p.get_filename()]


def parse_message(raw):
    msg = email.message_from_bytes(raw)
    sender_name, sender_addr = parseaddr(decode_str(msg.get("From", "")))
    recipients = [addr for _, addr in getaddresses(
        [decode_str(msg.get(h, "")) for h in ("To", "Cc")]) if addr]
    try:
        date = parsedate_to_datetime(msg.get("Date")).astimezone().strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        date = ""
    return {
        "message_id": (msg.get("Message-ID") or "").strip(),
        "sender": sender_name or sender_addr,
        "sender_addr": sender_addr.lower(),
        "recipients": ", ".join(r.lower() for r in recipients),
        "subject": decode_str(msg.get("Subject", "")).strip(),
        "date": date,
        "body": get_body(msg),
        "attachments": ", ".join(attachment_names(msg)),
    }


def _imap_connect(cfg):
    host, port = cfg["imap_host"], int(cfg["imap_port"] or 993)
    try:
        if cfg.get("imap_ssl", "1") == "1":
            conn = imaplib.IMAP4_SSL(host, port, ssl_context=ssl.create_default_context(), timeout=30)
        else:
            conn = imaplib.IMAP4(host, port, timeout=30)
        conn.login(cfg["mail_address"], cfg["mail_password"])
    except imaplib.IMAP4.error as e:
        raise MailError(f"收信服务器登录失败：{e}\n请检查邮箱地址和授权码，并确认已在邮箱设置中开启 IMAP 服务。")
    except (OSError, ssl.SSLError) as e:
        raise MailError(f"无法连接收信服务器 {host}:{port}：{e}")
    try:
        conn._simple_command("ID", '("name" "CRM-Desktop" "version" "1.0")')
    except imaplib.IMAP4.error:
        pass  # 不支持 ID 命令的服务器直接忽略
    return conn


def fetch_inbox(cfg, since_uid=0, limit=50):
    """拉取收件箱中 UID 大于 since_uid 的邮件，最多 limit 封（取最新的）。
    返回 (uidvalidity, 邮件列表)，每封邮件为 parse_message 的结果并附带 uid。"""
    conn = _imap_connect(cfg)
    try:
        typ, _ = conn.select("INBOX", readonly=True)
        if typ != "OK":
            raise MailError("无法打开收件箱")
        validity = (conn.response("UIDVALIDITY")[1] or [b"0"])[0]
        validity = validity.decode() if isinstance(validity, bytes) else str(validity)
        typ, data = conn.uid("search", None, f"UID {since_uid + 1}:*" if since_uid else "ALL")
        uids = [int(u) for u in (data[0] or b"").split() if int(u) > since_uid]
        result = []
        for uid in sorted(uids)[-limit:]:
            typ, parts = conn.uid("fetch", str(uid), "(BODY.PEEK[])")
            raw = next((p[1] for p in parts if isinstance(p, tuple)), None)
            if typ == "OK" and raw:
                item = parse_message(raw)
                item["uid"] = uid
                result.append(item)
        return validity, result
    finally:
        try:
            conn.logout()
        except (imaplib.IMAP4.error, OSError):
            pass


def build_message(cfg, to, subject, body, cc=""):
    msg = EmailMessage()
    msg["From"] = formataddr((cfg.get("mail_name") or "", cfg["mail_address"]))
    msg["To"] = to
    if cc:
        msg["Cc"] = cc
    msg["Subject"] = subject
    msg["Message-ID"] = email.utils.make_msgid(domain=cfg["mail_address"].rsplit("@", 1)[-1])
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg.set_content(body)
    return msg


def _smtp_connect(cfg):
    """连接并登录 SMTP 服务器。587 端口使用 STARTTLS，其余端口直接 SSL。"""
    host, port = cfg["smtp_host"], int(cfg["smtp_port"] or 465)
    use_ssl = cfg.get("smtp_ssl", "1") == "1"
    try:
        if use_ssl and port != 587:
            smtp = smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=30)
        else:
            smtp = smtplib.SMTP(host, port, timeout=30)
            if use_ssl:
                smtp.starttls(context=ssl.create_default_context())
        smtp.login(cfg["mail_address"], cfg["mail_password"])
        return smtp
    except smtplib.SMTPAuthenticationError:
        raise MailError("发信服务器登录失败：请检查邮箱地址和授权码，并确认已在邮箱设置中开启 SMTP 服务。")
    except (smtplib.SMTPException, OSError, ssl.SSLError) as e:
        raise MailError(f"无法连接发信服务器 {host}:{port}：{e}")


def send_mail(cfg, to, subject, body, cc=""):
    """发送纯文本邮件，返回已发送的 EmailMessage。"""
    if not [a for _, a in getaddresses([to]) if "@" in a]:
        raise MailError("请填写正确的收件人邮箱")
    msg = build_message(cfg, to, subject, body, cc)
    with _smtp_connect(cfg) as smtp:
        try:
            smtp.send_message(msg)
        except (smtplib.SMTPException, OSError) as e:
            raise MailError(f"发送失败：{e}")
    return msg


def test_connection(cfg):
    """依次测试 IMAP 与 SMTP 登录。"""
    _imap_connect(cfg).logout()
    _smtp_connect(cfg).quit()
