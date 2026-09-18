---
name: code-lint
description: 检查代码与规则文件的语法和规范问题——Python 脚本的静态检查，以及 .conf/.list 规则文件的格式合法性。当用户说「检查一下代码」「有没有语法问题」「lint」「规范检查」「规则写对了吗」时使用。对应 ESLint 的能力。
---

# 代码与规则规范检查

本仓库是 Python + 规则文本，没有 JS，所以 ESLint 本身用不上；等价的检查分两块做。

## 1. Python 脚本（factory/*.py）

按可用性依次尝试，不要为此安装全局工具：

```bash
python3 -m py_compile factory/*.py          # 最低保障：语法必须过
python3 -m pyflakes factory/*.py 2>/dev/null || true   # 未用变量、未定义名
python3 -m ruff check factory/ 2>/dev/null || true
```

本仓库已知的风格特点（不要当成 bug 去改）：模块级顺序脚本、无 `if __name__` 守卫、
`file = open(...)` 不关闭。只在用户明确要求重构时才动这些。

## 2. 规则文件格式

`.conf` 由 `factory/build_confs.py` 生成，`[Rule]` 段每行必须是
`TYPE,VALUE,POLICY`，TYPE 取 `DOMAIN-SUFFIX` / `DOMAIN-KEYWORD` / `IP-CIDR` / `GEOIP` / `FINAL`。

```bash
# 找出 [Rule] 段里不合法的行
awk '/^\[Rule\]/{r=1;next} /^\[/{r=0} r && $0 !~ /^#/ && NF && $0 !~ /^(DOMAIN-SUFFIX|DOMAIN-KEYWORD|DOMAIN|IP-CIDR|GEOIP|USER-AGENT|URL-REGEX|FINAL),/ {print FILENAME":"FNR": "$0}' *.conf

# IP-CIDR 必须带掩码
grep -n '^IP-CIDR,[0-9.]*,' *.conf | grep -v '/' 
```

## 3. 源清单（factory/resultant/*.list、manual_*.txt）

每行应是裸域名或 IP，不带协议、路径、通配前缀：

```bash
grep -nE '^(https?://|\*|\|)|/|\s' factory/manual_*.txt factory/resultant/*.list
```

## 汇报

按 `文件:行号` 列出问题，区分「必须修」（语法错误、规则类型非法）和「可选」（风格）。
不要主动改生成产物 `*.conf`——问题在模板或脚本里，改源头再重新生成。
