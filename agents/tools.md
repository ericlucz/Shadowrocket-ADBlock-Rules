# 工具契约

设计原则：**凡是能算准的，都不要让模型算。** 模型负责选工具和填参数，数值全部由工具返回。
每个工具调用有唯一 `call_id`，写入日志，fact 的 `source` 可以指向它。

---

## 1. 体积重与计费重（物流 Agent 核心）

### 公式

```
体积重(kg) = 长(cm) × 宽(cm) × 高(cm) ÷ 抛比系数
计费重(kg) = max(实际毛重, 体积重)
```

抛比系数按渠道取值，**必须配置化，不得写死在提示词里**（各承运商会调整）：

| 渠道 | 常用系数 | 说明 |
| --- | --- | --- |
| 国际快递（DHL/UPS/FedEx） | 5000 | 行业通用 |
| 空运普货 | 6000 | 部分代理用 5000，以合同为准 |
| 专线小包 | 6000 或 8000 | 渠道差异大 |
| 海运拼箱 | 按 CBM 计费 | `CBM = 长×宽×高 ÷ 1,000,000`，另有最低 1 CBM 起 |

### 进位规则（最容易出错的地方）

1. **先按箱计算，再汇总**，不要把总体积除以系数（多箱时结果不同）
2. 每箱计费重按渠道规则进位：快递多为 **0.5kg 向上取整**，小包多为 **0.1kg**，空运为 **0.5kg**
3. 进位在**每箱**做，不是在总重上做
4. 尺寸先四舍五入到整数厘米（多数承运商规则），再相乘

> 举例：3 箱，每箱 40×30×25cm、实重 4.2kg，走快递（系数 5000，0.5kg 进位）
> 单箱体积重 = 40×30×25÷5000 = 6.0kg → 计费重 = max(4.2, 6.0) = 6.0kg
> 总计费重 = 6.0 × 3 = **18.0kg**（而非用总体积 90000÷5000 = 18kg 巧合相等；一旦尺寸不规整两者就会分叉）

### 接口

```jsonc
// calc_billable_weight
{
  "channel": "express_dhl",
  "packages": [ { "length_cm": 40, "width_cm": 30, "height_cm": 25, "gross_kg": 4.2, "count": 3 } ]
}
// →
{
  "call_id": "tool_8a1",
  "divisor": 5000, "rounding": "0.5_up",
  "per_package": [ { "volumetric_kg": 6.0, "billable_kg": 6.0 } ],
  "total_billable_kg": 18.0,
  "total_cbm": 0.09,
  "warnings": []          // 如 "单箱超 30kg 需分拆" "超长边 120cm 触发超尺寸附加费"
}
```

---

## 2. 运费报价

```jsonc
// quote_shipping
{
  "origin": "CN-SZX", "destination_country": "DE", "destination_zip": "10115",
  "billable_kg": 18.0, "cbm": 0.09,
  "goods": { "category": "power_supply", "has_battery": false, "declared_value_usd": 3200 },
  "service_level": ["express", "air"]
}
// →
{
  "call_id": "tool_8a2",
  "options": [
    { "channel": "express_dhl", "amount_range": [1180, 1320], "currency": "CNY",
      "eta_days": [4, 6],
      "surcharges": ["fuel_28%", "remote_area:no"],
      "includes_duty": false, "valid_until": "2026-09-22" }
  ],
  "blocked": [ { "channel": "air_economy", "reason": "目的国该品类需 CE 文件" } ]
}
```

**契约约束**

- 永远返回**区间**，不返回单一数字（汇率、燃油、旺季附加费会浮动）
- `includes_duty` 必须显式返回，物流 Agent 必须把它写进 `assumptions`
- 报价带 `valid_until`，过期后 `SessionState.shipping_quote` 作废，需重新取数
- 货代 API 不可用时返回本地运价表结果，并置 `degraded: true`，对客文案必须带"最终以下单时为准"

---

## 3. 商品规格查询（技术 Agent）

**精确字段走结构化查询，禁止走向量检索**：

```jsonc
// get_product_spec
{ "sku": "PS-200-B", "fields": ["input_voltage", "output_power", "certifications", "net_weight_kg", "package_dims_cm"] }
// →
{ "call_id": "tool_8a3", "sku": "PS-200-B",
  "fields": { "input_voltage": "100-240VAC", "output_power_w": 200,
              "certifications": ["CE", "FCC"], "net_weight_kg": 2.4,
              "package_dims_cm": [40, 30, 15] },
  "missing_fields": ["mtbf_hours"],     // 库里没有就明说，不许留空让模型脑补
  "source": "product_db:PS-200-B@rev7", "updated_at": "2026-08-30" }
```

> `package_dims_cm` / `net_weight_kg` 正是串行移交（§4.2 A）里技术 Agent 交给物流 Agent 的那两个字段。

```jsonc
// check_compatibility —— 查兼容矩阵，不是让模型推理
{ "sku_a": "PS-200-B", "sku_b": "CTRL-X9" }
// →
{ "call_id": "tool_8a4", "verdict": "conditional",
  "conditions": ["需 CN-02 转接线", "CTRL-X9 固件 ≥ v2.3"],
  "source": "compat_matrix:2026Q3", "tested": true }
```

**`verdict` 只能来自矩阵，不能由模型推断**。矩阵里没有这对组合时返回 `unknown`，技术 Agent 据此回 `need_info` 并建议人工确认 —— 这条规则是防止"看起来应该兼容"的幻觉的关键。

```jsonc
// search_spec_docs —— 仅用于开放性问题（注意事项、安装说明、已知问题）
{ "query": "PS-200-B 高温环境降额", "top_k": 5 }
// → { "chunks": [ { "text": "...", "doc_id": "PS-200-B_v3.pdf", "page": 12, "score": 0.83 } ] }
```

---

## 4. 价格与政策（销售 Agent）

```jsonc
// get_price_policy
{ "sku": "PS-200-B", "qty": 50, "customer_tier": "vip", "country": "DE" }
// →
{ "call_id": "tool_8a5",
  "list_price": 158.00, "currency": "CNY",
  "tier_price": 128.00,
  "max_discount_pct": 12,            // 销售 Agent 的自主权上限
  "ladder": [ { "min_qty": 100, "unit_price": 119.00 } ],
  "requires_approval_above_pct": 12,
  "valid_until": "2026-09-30" }
```

超过 `max_discount_pct` 的请求 → 协调者拦截 → `escalation.required = true`。
这个阈值由**工具返回**而非提示词写死，便于运营随时调整且无需改提示词。

---

## 5. 其它

| 工具 | 归属 | 用途 |
| --- | --- | --- |
| `get_customer_profile` | 销售 | CRM 档案、历史订单、等级 |
| `check_stock` | 销售/技术 | 可用库存与预计到货（只读 ERP，不锁库存） |
| `check_restricted_goods` | 物流 | 禁限运、危品、目的国准入 |
| `create_quote_draft` | 协调者 | 生成**待确认**报价单，不下单、不扣库存 |
| `escalate_to_human` | 协调者 | 转人工，携带完整 SessionState 摘要 |

---

## 6. 工具调用的统一约束

1. **幂等**：同参数重复调用返回同结果（报价类带 `valid_until` 而非每次重算漂移）
2. **超时 3s**，重试 1 次，仍失败则返回 `degraded` 结果或明确的错误，**不许静默降级为模型自答**
3. **参数缺失即失败**：不要给默认值。缺目的国就报错，不要默认发美国
4. **全量落日志**：`call_id`、入参、出参、耗时、是否 degraded
5. **返回结构固定**：任何工具都不返回自由文本段落给模型"自行理解"，除 `search_spec_docs` 的 chunks 外
