---
name: format-unify
description: 统一代码与文档格式，让风格保持一致。当用户说「格式化」「整理一下格式」「统一风格」「排版乱了」「format」时使用。对应 Prettier 的能力。
---

# 格式统一

## 分层规则：哪些能格式化，哪些绝对不能

| 范围 | 能否格式化 | 工具 |
| --- | --- | --- |
| `readme.md`、`factory/README.md` | 是 | Prettier（`--prose-wrap preserve`） |
| `.vscode/*.json` | 是 | Prettier |
| `factory/*.py` | 谨慎 | 见下 |
| `*.conf` | **否** | 生成产物，改模板 |
| `factory/resultant/*.list` | **否** | 抓取产物 |
| `factory/manual_*.txt` | 仅排序去重 | 见下 |

## Markdown

```bash
npx --yes prettier --prose-wrap preserve --write readme.md factory/README.md
```

`--prose-wrap preserve` 是必需的：readme 里有大量中文段落和表格，重排会把行搞乱。
格式化后 `git diff --stat` 确认改动只是空白和表格对齐。

## Python

本仓库现有风格是紧凑的顺序脚本。**不要**默认跑 black——那会重排整个文件，
制造和内容无关的大 diff，淹没真正的规则改动。只在用户明确要求时执行，并单独一个提交：

```bash
python3 -m black factory/ --line-length 100
```

## 人工规则清单

`manual_*.txt` 的「格式统一」是指排序去重，不是重排：

```bash
for f in factory/manual_direct.txt factory/manual_proxy.txt factory/manual_reject.txt; do
  sort -u "$f" -o "$f"
done
git diff --stat
```

注意：如果文件里有分组注释（`# xxx`），`sort -u` 会把注释打散。先确认：

```bash
grep -c '^#' factory/manual_*.txt
```

有注释就不要整体排序，只在对应分组内手工去重。

## 收尾

格式化和功能改动永远分开提交，提交信息写明「仅格式调整，无逻辑变更」。
