"""演示数据。"""
from datetime import date, timedelta


def load_demo_data(db):
    d = lambda days: (date.today() + timedelta(days=days)).isoformat()
    customers = [
        ({"name": "张伟", "company": "华星科技有限公司", "phone": "13800138001",
          "email": "zhangwei@huaxing.cn", "source": "展会", "status": "成交客户",
          "level": "A", "owner": "李娜"},
         [("拜访", "现场演示产品，客户对报表模块很感兴趣", d(-2))],
         [("年度软件采购", 120000, "赢单", d(-10)), ("二期扩容", 60000, "方案报价", d(30))]),
        ({"name": "王芳", "company": "明远贸易", "phone": "13900139002",
          "email": "wangfang@mingyuan.com", "source": "官网咨询", "status": "意向客户",
          "level": "B", "owner": "李娜"},
         [("电话", "初次沟通，确认需求为 20 个账号", d(3))],
         [("销售管理系统", 45000, "需求确认", d(45))]),
        ({"name": "刘强", "company": "东方物流集团", "phone": "13700137003",
          "email": "liuqiang@dfwl.com", "source": "老客户推荐", "status": "意向客户",
          "level": "A", "owner": "陈杰"},
         [("会议", "与 IT 部门开会讨论集成方案", d(1))],
         [("仓储系统对接", 200000, "谈判", d(20))]),
        ({"name": "赵敏", "company": "青禾餐饮", "phone": "13600136004",
          "source": "地推", "status": "潜在客户", "level": "C", "owner": "陈杰"},
         [("微信", "发送了产品资料，等待回复", d(6))], []),
        ({"name": "孙磊", "company": "启航教育", "phone": "13500135005",
          "source": "广告", "status": "流失客户", "level": "C", "owner": "李娜"},
         [], [("培训管理平台", 30000, "输单", d(-30))]),
    ]
    for info, followups, deals in customers:
        cid = db.add_customer(info)
        for method, content, next_date in followups:
            db.add_followup(cid, method, content, next_date)
        for title, amount, stage, expected in deals:
            db.add_deal(cid, title, amount, stage, expected)
