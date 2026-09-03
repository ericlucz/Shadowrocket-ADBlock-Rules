# 外贸客户管理 · Foreign Trade CRM

一个**单文件、离线、中英双语**的外贸客户管理工具。下载 `index.html` 后双击用浏览器打开即可使用，
无需安装、无需服务器、无需联网，数据只保存在你自己的电脑里。

A single-file, offline, bilingual (中文 / English) CRM for export sales.
Download `index.html`, double-click to open it in a browser — no install, no server, no network.

![](https://img.shields.io/badge/dependencies-none-brightgreen) ![](https://img.shields.io/badge/offline-yes-blue)

---

## 快速开始 · Quick start

1. 下载 `foreign-trade-crm/index.html`（右键「另存为」或直接从仓库下载）。
2. 双击文件，用 Chrome / Edge / Safari 打开。
3. 进入 **设置 → 载入示例数据** 先试用，熟悉后 **清空全部数据** 再录入真实客户。
4. 建议把文件放在固定位置（如「文档」文件夹），并加到浏览器书签——数据与文件路径绑定。

> **数据存在哪里？** 浏览器的 localStorage（按文件所在来源隔离）。换浏览器、换电脑、清理浏览器数据都会
> 读不到旧数据，请定期用 **设置 → 导出 JSON 备份**。
>
> **Where is my data?** In this browser's localStorage, tied to where the file is opened from.
> Use **Settings → Export JSON backup** regularly.

---

## 功能 · Features

### 客户档案
- 公司、联系人、职位、邮箱、电话、WhatsApp、微信、网站、地址
- 国家/地区（70+ 主要外贸市场，带国旗与区号）
- **客户当地时间**——列表和详情里直接显示对方几点，避免半夜发邮件、上班时间打电话打扰
- 意向产品、意向金额（10 种币种）、客户等级 A/B/C、标签、备注

### 销售阶段
潜在客户 → 询盘中 → 已报价 → 寄样中 → 谈判中 → 已成交 / 沉睡 / 已流失，一键「标记成交」。

### 跟进管理
- 每个客户一条时间线，记录日期 + 方式（邮件 / 电话 / WhatsApp / 微信 / 当面拜访 / 视频会议 / 寄样 / 报价）+ 内容
- 每条跟进可同时设定**下次跟进日期**
- 「跟进」页按 **已逾期 / 今天到期 / 7 天内 / 未设置** 分组，侧栏红点提示待跟进数量

### 看板
客户总数、本月新增、待跟进、已逾期、已成交、在谈意向金额合计；
阶段分布、国家 TOP、客户来源三张分布图；最近跟进动态流。点卡片可直接跳转到对应筛选结果。

### 检索与筛选
全局搜索（公司 / 联系人 / 邮箱 / 电话 / 产品 / 标签 / 备注），
按国家、阶段、等级、来源、跟进状态筛选，四种排序方式。

### 数据进出
- **导出 JSON**：完整备份，含全部跟进记录，可再导入还原
- **导出 CSV**：带 BOM，Excel 直接双击打开不乱码
- **导入 JSON / CSV**：支持中文表头（公司、联系人、邮箱、国家、阶段…），
  公司名 + 邮箱相同的记录会自动合并而不是重复建档
- CSV 模板见 [`customers-template.csv`](customers-template.csv)

### 界面
中英一键切换（记忆选择）、浅色 / 深色 / 跟随系统主题、手机浏览器可用。

---

## 快捷键 · Shortcuts

| 按键 | 作用 |
| --- | --- |
| `/` | 聚焦搜索框 |
| `N` | 新建客户 |
| `Ctrl` / `⌘` + `S` | 保存当前客户 |
| `Esc` | 关闭客户面板（自动保存已填内容） |

---

## CSV 导入格式 · CSV import

表头可用英文字段名，也可用中文（公司、联系人、职位、邮箱、电话、微信、国家、地址、来源、
意向产品、金额、币种、等级、阶段、标签、备注、下次跟进、建档）。

- `country`：填 ISO 代码（`US`）、中文（`美国`）或英文（`United States`）都能识别
- `status`：`lead` / `inquiry` / `quoted` / `sample` / `negotiating` / `won` / `dormant` / `lost`，
  或对应中英文名称
- `source`：`exhibition` / `alibaba` / `madeinchina` / `website` / `google` / `linkedin` / `referral` / `coldmail` / `other`
- `tags`：用 `;` 或 `,` 分隔
- `nextFollowUp`：`YYYY-MM-DD`

---

## 多人使用 / 团队共享

本工具按设计是单机的。若团队要共用，可选：

- 每人一份文件各自录入，定期各自导出 CSV/JSON 汇总；
- 把 `index.html` 放到公司内网静态服务器（同一 URL 打开的人共享同一份浏览器存储的**本地**副本，
  数据仍在各自电脑上，不会互通）；
- 需要真正的多人实时共享，则要加后端数据库——当前版本不含服务端。

---

## 隐私 · Privacy

无任何网络请求、无外部依赖、无统计埋点。客户资料不会离开你的电脑。
