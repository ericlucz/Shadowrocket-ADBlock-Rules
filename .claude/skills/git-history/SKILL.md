---
name: git-history
description: 追溯某条规则、某个域名或某个文件的改动来源——谁在什么时候为什么加的。当用户问「这条规则哪来的」「这个域名是谁加的」「这段什么时候改的」「回溯改动」「blame」「git 历史」时使用。对应 GitLens 的能力。
---

# 规则改动考古

本仓库的 `.conf` 是生成产物，`factory/` 才是源头。追溯时要分清这两层。

## 1. 先判断域名属于哪一层

```bash
DOMAIN="example.com"
grep -rn "$DOMAIN" factory/manual_*.txt      # 人工维护 → 有明确提交可查
grep -rn "$DOMAIN" factory/resultant/*.list  # 自动抓取 → 提交只是批量刷新
grep -rln "$DOMAIN" *.conf                   # 最终产物 → 不要在这层追溯
```

人工维护的（`manual_direct.txt` / `manual_proxy.txt` / `manual_reject.txt`）才值得逐行 blame；
`resultant/` 里的来自 EasyList、乘风规则、Alexa top500 的自动抓取，提交信息只会是一次批量更新。

## 2. 定位引入该行的提交

```bash
# 该行最后一次改动
git blame -L "$(grep -n "^$DOMAIN$" factory/manual_proxy.txt | cut -d: -f1)",+1 -- factory/manual_proxy.txt

# 首次引入（跨重命名追踪，最可靠）
git log --follow --oneline -S "$DOMAIN" -- factory/
git show <commit> --stat
```

`-S` 按「该字符串出现/消失次数变化」筛选，比 `-G` 更准，能直接抓到引入和删除的那两个提交。

## 3. 看一个文件的演进

```bash
git log --oneline --follow -- factory/ad.py
git log -p --follow -- factory/template/sr_head.txt   # 模板改动通常影响所有 conf
```

## 汇报格式

给出：引入提交的 short hash、日期、提交信息、作者，以及它属于人工规则还是自动抓取。
如果是自动抓取的，明确说明「来自上游 <源名>，不是本仓库手工添加」，并指向 `factory/ad.py` 里对应的 `rules_url`。
