---
name: error-lens
description: 快速定位并解释报错——把异常、堆栈、构建失败精确定位到文件和行号，直接给出原因和修法。当用户贴出报错、说「跑不起来」「报错了」「哪里出问题」「build 失败」时使用。对应 Error Lens 的能力。
---

# 报错定位

目标：把报错压缩成 `文件:行号 → 原因 → 修法` 三行，而不是复述堆栈。

## 1. 复现

```bash
cd factory
python3 ad.py           # 抓取并解析广告规则
python3 top500.py       # 抓取 Alexa top500 并分流
python3 build_confs.py  # 用 resultant/ + template/ 生成 ../*.conf
```

`index.sh.bat` 是 `ad.py` → `build_confs.py` 的顺序封装。`build_confs.py` 依赖
`resultant/` 下已存在的 `.list`，所以单独跑它不需要联网。

## 2. 本仓库最常见的四类报错

**网络类** — `requests.exceptions.ConnectionError` / `sys.exit('error in request ...')`
出现在 `ad.py` 的重试循环（5 次）之后。先确认是上游挂了还是本地网络：

```bash
curl -sS -o /dev/null -w '%{http_code}\n' https://easylist-downloads.adblockplus.org/easylistchina+easylist.txt
curl -sS -o /dev/null -w '%{http_code}\n' https://raw.githubusercontent.com/xinggsf/Adblock-Plus-Rule/master/ABP-FX.txt
```

上游 4xx/5xx 是外部问题，不要改解析逻辑去绕过——报告并停。

**解析类** — `top500.py` 依赖 `alexa.chinaz.com` 的 HTML 结构，页面改版会让
BeautifulSoup 选择器返回空，表现为「抓到 0 条」而不是抛异常。先打印中间结果再判断。

**依赖类** — `ModuleNotFoundError`：

```bash
python3 -m pip install -r requirements.txt
```

**文件类** — `FileNotFoundError`：`build_confs.py` 用的是相对路径，必须在 `factory/` 目录下运行。

## 3. 汇报格式

```
factory/ad.py:38  sys.exit('error in request ...')
原因：上游 easylistchina+easylist.txt 连续 5 次返回 503，上游服务不可用
修法：非本仓库问题，稍后重试；若需容错可在 rules_url 里加备用镜像
```

区分「代码 bug」和「外部依赖故障」——后者不要靠改代码掩盖。
