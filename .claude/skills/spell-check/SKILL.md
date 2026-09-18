---
name: spell-check
description: 检查注释、文档和变量名的拼写错误，提升代码与文档的专业度。当用户说「查拼写」「有没有错别字」「typo」「文档校对」时使用。对应 Code Spell Checker 的能力。
---

# 拼写检查

## 关键前提：不要检查规则数据

`*.conf`、`factory/resultant/*.list`、`factory/manual_*.txt` 里全是域名，
对拼写检查器来说每一行都是「错词」。**必须排除**，否则结果全是噪音。

检查范围只有三类：`factory/*.py` 的注释与标识符、`readme.md`、`factory/README.md`。

## 执行

有 cspell 就用它（配置已写在 `.vscode/settings.json` 的 `cSpell.words`）：

```bash
npx --yes cspell lint "factory/*.py" "readme.md" "factory/README.md" --no-progress
```

没有则人工扫描英文标识符和注释：

```bash
grep -nE '#.*[a-zA-Z]{4,}' factory/*.py          # 英文注释
grep -noE '\b[a-z]+[A-Z][a-zA-Z]*\b' factory/*.py | sort -u -t: -k3   # 驼峰标识符
```

## 本仓库已知的既有拼写问题

`factory/top500.py` 里有 `class UrlScaner`（应为 `Scanner`）和 `praseHTML`（应为 `parseHTML`）。
这些是**公开标识符**，改名会波及所有调用处。除非用户明确要求，只报告不修改；
真要改就全局改干净并单独提交：

```bash
grep -rn 'UrlScaner\|praseHTML' factory/
```

## 专有名词

以下不是拼写错误，已加入白名单，遇到不要报：
Shadowrocket、adblock、EasyList、easylistchina、chinaz、cnip、banlist、banad、CIDR、GEOIP、lxml、Moshel、xinggsf。
新增专有名词时同步更新 `.vscode/settings.json` 的 `cSpell.words`。

## 中文文档

readme 以中文为主，cspell 不检查中文。人工留意：术语前后是否一致
（如「黑名单」不要有的地方写「黑名單」）、代理/直连/去广告三个词的用法是否统一。

## 汇报

按 `文件:行号  错词 → 建议` 列出，并标明是注释（可直接改）还是标识符（改名有波及范围）。
