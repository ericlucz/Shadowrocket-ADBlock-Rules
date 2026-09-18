---
name: path-check
description: 校验代码与文档里引用的文件路径是否真实存在，避免路径写错或文件改名后引用失效。当用户说「路径对吗」「文件找不到」「引用失效」「检查链接」「改名后有没有漏改」时使用。对应 Path Intellisense 的能力。
---

# 路径引用校验

本仓库的路径引用有三处容易断：脚本里的相对路径、模板名清单、readme 里的下载链接。

## 1. 脚本里的相对路径

`factory/*.py` 全部使用相对当前工作目录的路径，且假定在 `factory/` 下运行。

```bash
grep -nE "open\(|'\.\./|\"\.\./|/template/|/resultant/" factory/*.py
```

逐条确认目标存在：

```bash
cd factory
python3 - <<'PY'
import re, os, glob
for f in glob.glob('*.py'):
    for i, line in enumerate(open(f, encoding='utf-8'), 1):
        for m in re.finditer(r"""['"]((?:\.\./|template/|resultant/)[^'"]*|manual_[a-z]+\.txt)['"]""", line):
            p = m.group(1)
            if '%s' in p or '%d' in p:      # 格式化模板，跳过
                continue
            print(('OK   ' if os.path.exists(p) else 'MISS ') + f'{f}:{i}  {p}')
PY
```

## 2. 模板名清单必须和实际文件一一对应

`build_confs.py` 里的 `confs_names` 是硬编码列表，加了模板却忘记登记是最常见的坑：

```bash
cd factory
python3 - <<'PY'
import re, os
src = open('build_confs.py', encoding='utf-8').read()
names = re.findall(r"'(sr_[a-z0-9_]+)'", src.split('confs_names')[1].split(']')[0])
tpl = {f[:-4] for f in os.listdir('template') if f.endswith('.txt')} - {'sr_head', 'sr_foot'}
print('清单有但模板缺失:', sorted(set(names) - tpl) or '无')
print('模板有但清单漏登记:', sorted(tpl - set(names)) or '无')
PY
```

两边都应为「无」。`sr_head` / `sr_foot` 是公共头尾，故意不在清单里。

## 3. readme 里的规则下载链接

readme 给用户的链接指向仓库里的 `.conf`，改名或删文件会留下死链：

```bash
grep -oE '\[[^]]+\]\(([^)]*sr_[a-z0-9_]+\.conf)\)' readme.md | grep -oE 'sr_[a-z0-9_]+\.conf' | sort -u | while read -r f; do
  [ -f "$f" ] && echo "OK   $f" || echo "MISS $f"
done
```

## 汇报

只报 `MISS`，给出引用位置 `文件:行号` 和缺失的目标路径，并说明是路径写错还是文件确实没了。
