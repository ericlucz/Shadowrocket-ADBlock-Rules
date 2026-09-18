---
name: api-test
description: 批量健康检查上游数据源，一次性验证全部依赖是否可用并给出汇总结论。当用户说「上游都还好吗」「批量测一遍」「体检」「健康检查」「生成前先确认依赖」时使用。对应 Thunder Client 的能力。
---

# 上游批量健康检查

和 `rest-client`（单条请求调试）的分工：这里做**全量体检**，跑一遍给结论，
用于「重新生成规则之前先确认能不能跑」。

## 一键体检

```bash
cd /home/user/Shadowrocket-ADBlock-Rules
python3 - <<'PY'
import urllib.request, time, sys

CHECKS = [
    ("EasyList CN+Global", "https://easylist-downloads.adblockplus.org/easylistchina+easylist.txt", b"[Adblock"),
    ("Cheng Feng ABP-FX",  "https://raw.githubusercontent.com/xinggsf/Adblock-Plus-Rule/master/ABP-FX.txt", b"!"),
    ("Alexa chinaz",       "http://alexa.chinaz.com/Global/index.html", b"<table"),
]

fails = 0
for name, url, marker in CHECKS:
    t0 = time.time()
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            body = r.read()
        ok = r.status == 200 and marker in body[:200000]
        print(f"{'PASS' if ok else 'FAIL'}  {name:22} {r.status}  {len(body):>9}B  {time.time()-t0:.1f}s")
        if not ok:
            print(f"      未命中特征 {marker!r}，上游内容可能已变更")
            fails += 1
    except Exception as e:
        print(f"FAIL  {name:22} {type(e).__name__}: {e}")
        fails += 1

print(f"\n{len(CHECKS)-fails}/{len(CHECKS)} 通过")
sys.exit(1 if fails else 0)
PY
```

特征串（`marker`）的作用是区分「返回 200 但内容是错误页/改版了」和「真的正常」——
只看状态码会漏掉 `top500.py` 最常见的静默失败。

## 生成产物自检

上游通过后，跑完生成再确认产物没退化：

```bash
wc -l *.conf factory/resultant/*.list
git diff --stat -- '*.conf'
```

行数**大幅减少**是危险信号，通常意味着上游只返回了部分内容。基线参考：

```bash
git show HEAD:sr_top500_banlist_ad.conf | wc -l
```

新生成的行数若比上一版少 10% 以上，先查上游，不要直接提交。

## 汇报

给出逐项 PASS/FAIL 表格 + 一句总结论（「可以生成」/「上游 X 故障，暂缓」）。
上游故障属于外部问题——如实报告并停下，不要改解析逻辑绕过去。

## 受限网络下的误判

在网络受限的环境（如 Claude Code on the web 的部分网络策略、公司代理）里，
上面的检查可能全部 FAIL，但上游其实是好的。先分辨是谁挡的：

```bash
curl -sS -o /dev/null -w '%{http_code}\n' -L --max-time 20 https://example.com   # 基线
env | grep -i proxy
```

- `Tunnel connection failed: 403` / 状态码 `000` → 代理或网络策略拦截，**不是上游故障**
- 基线也失败 → 整个环境没有出网能力，此时不要得出任何关于上游的结论

判定为环境限制时，如实说明「本环境无法访问上游，无法完成体检」，
不要因此去改 `factory/*.py` 的 URL 或重试逻辑。
