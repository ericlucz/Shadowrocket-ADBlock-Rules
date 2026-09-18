---
name: project-map
description: 快速理解本仓库的结构、数据流和各文件职责，定位「要改的东西在哪」。当用户问「这项目怎么组织的」「我该改哪个文件」「XX 在哪」「介绍下结构」，或新接手这个仓库时使用。对应 Project Manager 的能力。
---

# 项目地图

## 一句话

Python 脚本抓取上游广告规则和 Alexa top500 站点 → 分流成域名清单 → 套模板生成
8 份 Shadowrocket `.conf` 规则文件。仓库根目录的 `.conf` 全是**生成产物**。

## 数据流

```
上游
 ├ EasyList China + EasyList ─┐
 └ 乘风 ABP-FX ──────────────┤→ factory/ad.py ──→ factory/resultant/ad.list
                              │
   alexa.chinaz.com ──────────┴→ factory/top500.py ─→ resultant/top500_direct.list
                                                    └→ resultant/top500_proxy.list

factory/manual_{direct,proxy,reject}.txt  ─┐
factory/resultant/*.list                   ├→ factory/build_confs.py ─→ ../*.conf
factory/template/*.txt                     ┘
```

## 该改哪个文件

| 想做的事 | 改这里 |
| --- | --- |
| 某网站该走代理 / 直连 | `factory/manual_proxy.txt` / `manual_direct.txt` |
| 屏蔽某个广告域名 | `factory/manual_reject.txt` |
| 增删上游规则源 | `factory/ad.py` 的 `rules_url` |
| 改 `[General]` 段、DNS、绕过网段 | `factory/template/sr_head.txt` |
| 改规则文件末尾内容 | `factory/template/sr_foot.txt` |
| 改某一份规则的组合方式 | `factory/template/sr_<名字>.txt` |
| 新增一份规则文件 | 加 `template/sr_xxx.txt` **并**登记到 `build_confs.py` 的 `confs_names` |
| 改上游解析逻辑 | `factory/ad.py` / `factory/top500.py` |
| 用户看的说明、下载链接 | `readme.md` |

**绝不直接改仓库根的 `*.conf`**——下次生成就被覆盖。改源头再重新生成。

## 八份规则的区别

| 文件 | 去广告 | 代理范围 |
| --- | --- | --- |
| `sr_top500_banlist_ad` | 是 | top500 中不可直连的 |
| `sr_top500_whitelist_ad` | 是 | 白名单外全部 |
| `sr_top500_banlist` / `sr_top500_whitelist` | 否 | 同上 |
| `sr_cnip_ad` / `sr_cnip` | 是 / 否 | 国外全部 |
| `sr_direct_banad` | 是 | 全直连 |
| `sr_proxy_banad` | 是 | 全代理 |

前两个是大多数人的选择（见 readme）。

## 重新生成

```bash
cd factory
python3 -m pip install -r ../requirements.txt
bash index.sh.bat        # = python ad.py && python build_confs.py
```

`top500.py` 需单独运行（耗时长、依赖页面结构），不在 `index.sh.bat` 里。
生成后必须 `git diff --stat -- '*.conf'` 确认改动量合理再提交。
