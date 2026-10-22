import os
import tempfile
import unittest
from datetime import date, timedelta

from crm.db import Database
from crm.demo import load_demo_data


class DatabaseTest(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")

    def tearDown(self):
        self.db.close()

    def test_customer_crud_and_search(self):
        cid = self.db.add_customer({"name": "张三", "company": "测试公司", "status": "意向客户", "level": "A"})
        self.db.add_customer({"name": "李四", "company": "别家"})
        self.assertEqual(len(self.db.list_customers()), 2)
        self.assertEqual([c["name"] for c in self.db.list_customers("测试")], ["张三"])
        self.assertEqual(len(self.db.list_customers(status="意向客户", level="A")), 1)
        self.db.update_customer(cid, {"name": "张三丰", "level": "B"})
        self.assertEqual(self.db.get_customer(cid)["name"], "张三丰")
        with self.assertRaises(ValueError):
            self.db.add_customer({"name": "  "})

    def test_delete_cascades(self):
        cid = self.db.add_customer({"name": "王五"})
        self.db.add_followup(cid, "电话", "沟通")
        self.db.add_deal(cid, "项目", 100, "初步接触")
        self.db.delete_customer(cid)
        self.assertEqual(self.db.list_followups(cid), [])
        self.assertEqual(self.db.list_deals(), [])

    def test_upcoming_uses_latest_followup(self):
        cid = self.db.add_customer({"name": "赵六"})
        soon = (date.today() + timedelta(days=2)).isoformat()
        far = (date.today() + timedelta(days=30)).isoformat()
        self.db.add_followup(cid, "电话", "第一次", soon)
        self.assertEqual(len(self.db.upcoming_followups()), 1)
        self.db.add_followup(cid, "拜访", "第二次", far)
        self.assertEqual(len(self.db.upcoming_followups()), 0)

    def test_stats(self):
        load_demo_data(self.db)
        s = self.db.stats()
        self.assertEqual(s["customers"], 5)
        self.assertEqual(s["new_this_month"], 5)
        self.assertEqual(s["won_amount"], 120000)
        self.assertEqual(s["open_amount"], 60000 + 45000 + 200000)

    def test_csv_roundtrip(self):
        load_demo_data(self.db)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "c.csv")
            self.assertEqual(self.db.export_customers_csv(path), 5)
            other = Database(":memory:")
            self.assertEqual(other.import_customers_csv(path), 5)
            self.assertEqual(other.list_customers("华星")[0]["phone"], "13800138001")
            other.close()


if __name__ == "__main__":
    unittest.main()
