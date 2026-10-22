import unittest
from email.message import EmailMessage

from crm import mail
from crm.db import Database
from crm.demo import load_demo_data


def make_raw(**kw):
    m = EmailMessage()
    m["From"] = kw.get("sender", "张伟 <ZhangWei@huaxing.cn>")
    m["To"] = kw.get("to", "me@test.local")
    m["Subject"] = kw.get("subject", "关于二期扩容的报价")
    m["Message-ID"] = kw.get("message_id", "<abc@huaxing.cn>")
    m["Date"] = "Thu, 22 Oct 2026 10:00:00 +0800"
    m.set_content(kw.get("body", "<p>您好：</p><p>请发<b>报价单</b>。</p>"),
                  subtype=kw.get("subtype", "html"), charset=kw.get("charset", "gbk"))
    if kw.get("attachment"):
        m.add_attachment(b"x", maintype="application", subtype="pdf", filename=kw["attachment"])
    return m.as_bytes()


class ParseTest(unittest.TestCase):
    def test_parse_gbk_html_with_attachment(self):
        item = mail.parse_message(make_raw(attachment="需求说明.pdf"))
        self.assertEqual(item["sender"], "张伟")
        self.assertEqual(item["sender_addr"], "zhangwei@huaxing.cn")
        self.assertEqual(item["subject"], "关于二期扩容的报价")
        self.assertEqual(item["body"], "您好：\n请发报价单。")
        self.assertEqual(item["attachments"], "需求说明.pdf")

    def test_crlf_normalized(self):
        raw = make_raw(body="第一行\r\n第二行\r\n", subtype="plain", charset="utf-8")
        self.assertEqual(mail.parse_message(raw)["body"], "第一行\n第二行")

    def test_plain_text_preferred(self):
        m = EmailMessage()
        m["From"] = "a@b.com"
        m.set_content("纯文本正文")
        m.add_alternative("<p>HTML 正文</p>", subtype="html")
        self.assertEqual(mail.parse_message(m.as_bytes())["body"], "纯文本正文")

    def test_guess_preset(self):
        self.assertEqual(mail.guess_preset("x@QQ.com"), "QQ 邮箱")
        self.assertEqual(mail.guess_preset("x@163.com"), "163 邮箱")
        self.assertIsNone(mail.guess_preset("x@unknown.cn"))

    def test_send_requires_recipient(self):
        with self.assertRaises(mail.MailError):
            mail.send_mail({"mail_address": "me@a.com"}, "not-an-address", "s", "b")


class EmailStoreTest(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")
        load_demo_data(self.db)  # 张伟 的邮箱是 zhangwei@huaxing.cn

    def test_save_dedupe_and_customer_link(self):
        item = mail.parse_message(make_raw())
        self.assertTrue(self.db.save_email("INBOX", item))
        self.assertFalse(self.db.save_email("INBOX", item))
        self.db.save_email("SENT", {"message_id": "<s1@x>", "sender_addr": "me@test.local",
                                    "recipients": "other@x.com, zhangwei@huaxing.cn",
                                    "subject": "回复"}, is_read=1)
        self.db.save_email("SENT", {"message_id": "<s2@x>", "recipients": "xzhangwei@huaxing.cn",
                                    "subject": "不相关"})
        subjects = sorted(e["subject"] for e in self.db.emails_for_customer(1))
        self.assertEqual(subjects, ["关于二期扩容的报价", "回复"])
        self.assertEqual(self.db.find_customer_by_email(" ZhangWei@Huaxing.cn")["name"], "张伟")
        self.assertEqual(self.db.unread_count(), 1)
        self.db.mark_email_read(self.db.list_emails("INBOX")[0]["id"])
        self.assertEqual(self.db.unread_count(), 0)

    def test_search(self):
        self.db.save_email("INBOX", mail.parse_message(make_raw()))
        self.assertEqual(len(self.db.list_emails("INBOX", "报价")), 1)
        self.assertEqual(len(self.db.list_emails("INBOX", "不存在")), 0)

    def test_settings(self):
        self.db.save_settings({"mail_address": "me@qq.com", "imap_port": 993})
        self.db.save_settings({"mail_address": "new@qq.com"})
        self.assertEqual(self.db.get_settings(["mail_address", "imap_port", "smtp_host"]),
                         {"mail_address": "new@qq.com", "imap_port": "993", "smtp_host": ""})


if __name__ == "__main__":
    unittest.main()
