---
name: todo-tree
description: 聚合并整理代码里的 TODO / FIXME / NOTE / HACK 待办事项，方便快速查看待办清单。当用户说「还有哪些待办」「TODO 清一下」「有什么没做完」「列一下遗留问题」时使用。对应 Todo Tree 的能力。
---

# 待办聚合

## 扫描

**必须排除 `*.conf` 和 `factory/resultant/`**——规则文件里有上千行 `#` 注释，
不排除的话结果会被完全淹没。

```bash
grep -rnE '(^|[^a-zA-Z])(TODO|FIXME|NOTE|HACK|XXX|BUG)[[:space:]:：]' \
  --include='*.py' --include='*.md' --include='*.sh' --include='*.bat' \
  --include='*.json' --include='*.txt' \
  --exclude-dir=.git --exclude-dir=.claude --exclude-dir=.vscode \
  . \
  | grep -v '/resultant/' \
  | grep -v 'manual_'
```

按标记分组统计：

```bash
for tag in TODO FIXME HACK BUG NOTE XXX; do
  n=$(grep -rnE "(^|[^a-zA-Z])$tag[[:space:]:：]" --include='*.py' --include='*.md' . 2>/dev/null | grep -vc '/resultant/')
  echo "$tag: $n"
done
```

## 被注释掉的规则源

本仓库还有一类「隐性待办」：`factory/ad.py` 的 `rules_url` 里有被注释掉的上游源
（如单独的 `easylistchina.txt`）。这类注释是刻意保留的备选项，不是遗留待办，
报告时单独归为「备用源」，不要建议删除。

```bash
grep -n "^\s*#.*https\?://" factory/*.py
```

## 汇报格式

按优先级排序输出，不要按文件顺序：

```
FIXME (1)
  factory/top500.py:65  praseHTML 拼写错误，属于公开方法名

TODO (0)

备用源 (1)
  factory/ad.py:15  easylistchina.txt 被注释，当前使用合并版
```

每条给出 `文件:行号` 和一句话说明。若某类为 0 也显式写出，让用户知道确实查过。
