---
name: rest-client
description: 在本地直接发 HTTP 请求来调试接口和上游数据源，查看响应状态与内容。当用户说「测一下这个接口」「请求看看」「上游还活着吗」「curl 一下」「调接口」时使用。对应 REST Client 的能力。
---

# HTTP 请求调试

本仓库的「接口」就是三个上游数据源。规则生成失败时，第一步永远是确认上游是否还正常。

## 上游清单

| 源 | 地址 | 被谁使用 |
| --- | --- | --- |
| EasyList China + EasyList | `https://easylist-downloads.adblockplus.org/easylistchina+easylist.txt` | `factory/ad.py` |
| 乘风广告过滤规则 | `https://raw.githubusercontent.com/xinggsf/Adblock-Plus-Rule/master/ABP-FX.txt` | `factory/ad.py` |
| Alexa 全球排名（HTML 抓取） | `http://alexa.chinaz.com/Global/index.html` | `factory/top500.py` |

清单以代码为准，改动前先核对：

```bash
grep -nE "https?://" factory/ad.py factory/top500.py
```

## 单次探测

```bash
URL='https://easylist-downloads.adblockplus.org/easylistchina+easylist.txt'
curl -sS -o /dev/null -w 'status=%{http_code}  size=%{size_download}B  time=%{time_total}s\n' -L "$URL"
```

看内容前几行（确认拿到的是规则而不是错误页）：

```bash
curl -sSL "$URL" | head -20
```

EasyList 正常响应应以 `[Adblock Plus 2.0]` 开头，并包含 `! Version:` 和 `! Last modified:`。

## 可复用的请求文件

把请求存成 `.http` 文件，配合 REST Client 扩展可在编辑器里逐条点击执行：

```bash
mkdir -p .vscode/http
cat > .vscode/http/upstream.http <<'HTTP'
### EasyList China + EasyList
GET https://easylist-downloads.adblockplus.org/easylistchina+easylist.txt

### 乘风广告过滤规则
GET https://raw.githubusercontent.com/xinggsf/Adblock-Plus-Rule/master/ABP-FX.txt

### Alexa 全球排名第一页
GET http://alexa.chinaz.com/Global/index.html
HTTP
```

## 注意

- 探测用 `curl`，不要为了测试去改 `ad.py` 的重试逻辑。
- 只发 GET。这些是公开只读源，不需要任何凭据——不要在请求里带 token 或个人信息。
- alexa.chinaz.com 是 HTTP 明文且依赖页面结构，返回 200 不代表解析能成功，还要看 HTML 里有没有目标表格。
