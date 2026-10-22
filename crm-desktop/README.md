# 客户关系管理系统（桌面版）

基于 Python + Tkinter + SQLite 的轻量级桌面 CRM，**无需安装任何第三方依赖**，数据保存在本地文件中。

## 功能

- **仪表盘**：客户总数、本月新增、跟进记录数、进行中 / 已赢单商机金额，客户状态分布和销售漏斗图
- **客户管理**：新增 / 编辑 / 删除客户；按关键字（姓名、公司、电话、邮箱、负责人）搜索；按状态、等级筛选；点击表头排序
- **客户详情**：查看客户资料，记录跟进（电话、微信、拜访等，可设置下次跟进日期），管理该客户的商机
- **商机管理**：按阶段（初步接触 → 需求确认 → 方案报价 → 谈判 → 赢单 / 输单）查看全部商机及合计金额
- **待办提醒**：列出 7 天内需要跟进的客户，已逾期的标红
- **导入 / 导出**：客户列表导出为 CSV（Excel 可直接打开），也可从 CSV 批量导入

## 运行

需要 Python 3.8+（Windows / macOS 官方安装包自带 Tkinter；Linux 需安装 `python3-tk`）。

```bash
cd crm-desktop
python main.py            # 正常启动，数据保存在 ~/.crm-desktop/crm.db
python main.py --demo     # 写入一批演示数据后启动，方便体验
python main.py --db 路径  # 使用指定的数据文件
```

## Windows 可执行文件（EXE）

无需安装 Python：直接下载 `CRM.exe` 双击运行即可。每次修改 `crm-desktop/` 后，GitHub Actions 中的
「Build CRM exe」工作流会在 Windows 上自动构建，在该次运行页面底部的 Artifacts 中下载 `CRM-windows`。

首次运行时数据库为空，可通过菜单「文件 → 载入演示数据」体验功能。程序未做代码签名，
Windows 可能提示「Windows 已保护你的电脑」，点击「更多信息 → 仍要运行」即可。

自行打包：

```bash
pip install pyinstaller
pyinstaller -F -w -n CRM main.py   # 生成 dist/CRM.exe（Windows）或 dist/CRM（macOS/Linux）
```

## CSV 导入格式

第一行为表头，支持以下列（中文或英文列名均可，只有「姓名」必填）：

`姓名, 公司, 电话, 邮箱, 地址, 来源, 状态, 等级, 负责人, 备注`

## 目录结构

```
crm-desktop/
├── main.py          # 启动入口
├── crm/
│   ├── db.py        # 数据层（SQLite）
│   ├── app.py       # 界面（Tkinter）
│   └── demo.py      # 演示数据
└── tests/test_db.py # 数据层单元测试：python -m unittest discover -s tests
```
