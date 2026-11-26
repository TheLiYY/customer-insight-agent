# API 字段说明

Base URL：`http://127.0.0.1:8000`
交互式文档：`/docs`（Swagger UI，可直接点「Try it out」调试）

所有接口返回 JSON，异常统一为 `{ "detail": "错误信息" }`（HTTP 4xx/5xx）。

---

## GET /api/health

```json
{
  "status": "ok",
  "app": "Customer Insight Agent",
  "version": "1.0.0",
  "llm_enabled": false,
  "customers": 930,
  "segments": 8,
  "clusters": 4,
  "rules": 20,
  "uptime_seconds": 31.8
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `llm_enabled` | bool | 是否配置了大模型（决定 Agent 走在线还是离线模式） |
| `customers` | int | 清洗后客户数 |
| `segments` | int | RFM 分层数（固定 8） |
| `clusters` | int | 聚类客群数 |
| `rules` | int | 关联规则条数 |
| `uptime_seconds` | float | 服务已运行秒数 |

---

## GET /api/dataset

```json
{
  "source": "https://raw.githubusercontent.com/.../ifood_df.csv",
  "excel": "backend/data/raw/Customer_Personality_Analysis.xlsx",
  "rows": 930,
  "columns": 26,
  "fields": [{ "name": "income", "label": "年收入", "type": "number", "desc": "..." }],
  "missing_cells": 0,
  "duplicate_rows": 0
}
```

---

## GET /api/overview

```json
{
  "kpis": {
    "customers": 930, "response_rate": 0.1355, "response_count": 126,
    "avg_income": 51859.26, "avg_spend": 565.91, "avg_freq": 12.58,
    "avg_recency": 48.96, "total_revenue": 526293.0,
    "dormant_rate": 0.2355, "dormant_count": 219,
    "complain_rate": 0.0075, "discount_dependence": 0.1801
  },
  "age": [{ "name": "41-50", "value": 245, "ratio": 0.263 }],
  "education": [], "marital": [], "income": [],
  "category": [{ "name": "葡萄酒", "value": 305.2 }],
  "channel": [{ "name": "线上商城", "value": 4.2 }],
  "response_by_age": [{ "name": "41-50", "value": 0.164, "count": 40 }],
  "response_by_education": [],
  "spend_hist": [{ "name": "0-200", "value": 300, "label": "0-200" }],
  "recency_hist": [],
  "correlation": { "x": ["income", "..."], "y": ["..."], "values": [[1.0]] }
}
```

| 字段 | 说明 |
| --- | --- |
| `kpis.response_rate` | 最近一次活动响应率（0–1） |
| `kpis.avg_spend` | 人均历史消费金额（货币单位） |
| `kpis.dormant_rate` | 最近购买间隔 > 60 天的客户占比 |
| `kpis.discount_dependence` | 折扣购买次数占总购买次数的比例 |
| `category[].value` | 该品类人均消费金额 |
| `channel[].value` | 该渠道人均购买次数 |
| `response_by_*.value` | 该分组内的响应率 |
| `correlation` | 数值特征相关系数矩阵（用于说明特征选择合理性） |

---

## GET /api/segments

```json
{
  "segments": [{
    "name": "重要价值客户", "priority": 1,
    "desc": "最近买过、买得又多又贵，是企业的现金牛。",
    "action": "VIP 专属权益 + 新品优先购；不要用大额折扣，重点维护关系。",
    "count": 334, "ratio": 0.3591, "revenue": 308112.0, "revenue_ratio": 0.5854,
    "avg_r": 4.62, "avg_f": 4.35, "avg_m": 4.4,
    "avg_recency": 25.1, "avg_freq": 19.2, "avg_spend": 922.5,
    "avg_income": 62031.5, "avg_age": 50.8,
    "response_rate": 0.2066, "complain_rate": 0.006
  }],
  "matrix": { "rows": ["F5", "..."], "cols": ["M1", "..."], "values": [[12]] },
  "treemap": [{ "name": "重要价值客户", "value": 334, "revenue": 308112.0 }],
  "score_distribution": { "R": { "1": 0.2 }, "F": {}, "M": {} }
}
```

| 字段 | 说明 |
| --- | --- |
| `priority` | 1 最高，用于排运营优先级 |
| `ratio` | 人数占比；`revenue_ratio` 为营收占比 |
| `avg_r/avg_f/avg_m` | 该层客户的平均 R/F/M 打分（1–5） |
| `matrix` | F（行）× M（列）人数矩阵，用热力图展示价值分布 |
| `treemap` | 营收矩形树图数据（面积=营收） |

---

## GET /api/personas

```json
{
  "k": 4, "silhouette": 0.2232, "inertia": 3197.75,
  "features": ["income", "total_spend", "..."],
  "clusters": [{ "cluster": 0, "name": "核心高价值客群", "size": 305 }],
  "personas": [{
    "cluster": 0, "name": "核心高价值客群", "status": "活跃", "rank": 1,
    "size": 305, "ratio": 0.328, "revenue": 363650.0, "revenue_ratio": 0.6906,
    "headline": "高收入 · 高价值 · 高频复购",
    "tags": ["高收入", "高价值", "高频复购", "葡萄酒重度用户", "活动敏感型"],
    "summary": "…",
    "demographics": { "avg_age": 52.1, "age_group": [], "education": [], "marital": [], "children_rate": 0.71 },
    "value": { "avg_income": 71385.2, "avg_spend": 1192.3, "avg_freq": 21.4,
               "avg_order_value": 61.9, "avg_recency": 22.4, "avg_tenure_days": 2512 },
    "categories": [{ "name": "葡萄酒", "value": 603.06, "ratio": 0.4771 }],
    "channels": [{ "name": "线下门店", "value": 8.4, "count": 2563 }],
    "behavior": { "discount_dependence": 0.14, "web_visits_month": 3.1,
                  "accepted_rate": 0.29, "response_rate": 0.223, "complain_rate": 0.003 }
  }]
}
```

| 字段 | 说明 |
| --- | --- |
| `silhouette` | 轮廓系数，聚类质量（-1~1，越大越好） |
| `status` | `活跃` / `沉默预警`，按平均最近购买间隔判定 |
| `tags` | 规则生成的画像标签，可直接用于运营打标 |
| `value.avg_order_value` | 客单价 = 总消费 ÷ 购买频次 |
| `categories[].ratio` | 该品类消费占客群总消费的比例 |

---

## GET /api/clusters/elbow?k_max=6

```json
{ "points": [{ "k": 2, "inertia": 4220.82, "silhouette": 0.3214 }] }
```

用肘部法 + 轮廓系数共同选择 k，前端双轴图展示。

---

## GET /api/propensity

```json
{
  "metrics": { "threshold": 0.58, "accuracy": 0.8674, "precision": 0.4828,
               "recall": 0.8, "f1": 0.6022,
               "confusion": { "tp": 28, "fp": 30, "fn": 7, "tn": 214 },
               "auc": 0.8871 },
  "full_metrics": {},
  "coefs": [{ "feature": "历史活动接受数", "key": "accepted_total", "coef": 0.9551, "direction": "正向" }],
  "lift": [{ "group": "第1组", "customers": 93, "avg_score": 0.9095,
             "response_rate": 0.6667, "lift": 4.9206, "captured": 0.4921 }],
  "base_rate": 0.1355,
  "threshold": 0.58,
  "score_hist": [{ "name": "0.0-0.1", "value": 620 }],
  "top_customers": [{ "customer_id": "C00021", "cluster_name": "核心高价值客群",
                      "rfm_segment": "重要价值客户", "prob": 0.93,
                      "total_spend": 1520.0, "purchase_freq": 24, "recency": 8 }]
}
```

| 字段 | 说明 |
| --- | --- |
| `metrics` | 测试集指标（阈值在验证集上搜索得到） |
| `full_metrics` | 全量重训后的指标 |
| `coefs[].coef` | 标准化后的逻辑回归系数，绝对值越大影响越强 |
| `lift[].lift` | 该分位响应率 ÷ 整体响应率 |
| `lift[].captured` | 该分位捕获了多少比例的响应客户 |

> 前端 `metrics` 用的是 `train_metrics`（测试集），后端同时返回 `full_metrics`（全量重训）供对照。

---

## GET /api/association

```json
{
  "rules": [{ "antecedent": "水果", "consequent": "甜食",
              "support": 0.7247, "confidence": 0.8927, "lift": 1.0924, "count": 674 }],
  "penetration": [{ "name": "葡萄酒", "buyers": 890, "penetration": 0.957,
                    "avg_spend": 305.2, "buyer_avg_spend": 318.9,
                    "revenue": 283612.0, "revenue_ratio": 0.5389 }],
  "basket_size": { "avg": 4.6, "distribution": [] }
}
```

| 字段 | 说明 |
| --- | --- |
| `support` | 同时购买 A 和 B 的客户占比 |
| `confidence` | 买了 A 的客户中同时买 B 的比例 |
| `lift` | 置信度 ÷ B 的整体渗透率；>1 表示正相关 |
| `penetration` | 品类渗透率（买过该品类的客户占比） |

---

## GET /api/customers?page=1&size=20&sort=total_spend&order=desc

```json
{
  "total": 930, "page": 1, "size": 20,
  "rows": [{
    "customer_id": "C00021", "age": 41.0, "age_group": "41-50",
    "education": "Graduation", "marital": "Married", "income": 58138.0,
    "total_spend": 1617.0, "purchase_freq": 24, "recency": 8,
    "rfm_segment": "重要价值客户", "cluster_name": "核心高价值客群", "prob": 0.93
  }]
}
```

支持参数：`page`、`size`、`sort`（字段名）、`order`（`asc`/`desc`）、`cluster`（客群名）、`segment`（RFM 层名）、`search`（按客户 ID 模糊匹配）。

---

## GET /api/customers/{customer_id}

返回单个客户的完整明细 + RFM 分层 + 聚类客群 + 响应概率 + 标签。`customer_id` 不存在时返回 404。

---

## GET /api/campaign/options

```json
{
  "clusters": [{ "name": "核心高价值客群", "size": 305, "headline": "高收入 · 高价值 · 高频复购" }],
  "rfm": [{ "name": "重要价值客户", "size": 334 }]
}
```

---

## POST /api/campaign/plan

请求：

```json
{ "segment": "核心高价值客群", "by": "cluster", "budget": 2000, "cost_per_contact": 8, "discount": 0.1 }
```

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `segment` | string | 必填 | 客群名（来自 `/api/campaign/options`） |
| `by` | string | `cluster` | `cluster` 按聚类客群 / `rfm` 按 RFM 分层 |
| `budget` | float | 20000 | 活动总预算 |
| `cost_per_contact` | float | 4 | 单客触达成本 |
| `discount` | float | 0.12 | 折扣力度（0–1） |

响应：

```json
{
  "ok": true, "segment": "核心高价值客群", "segment_size": 305,
  "selected": 250, "coverage": 0.8197,
  "goal": "拉升客单价", "timing": "本周三 19:00-21:00 推送",
  "offer": "组合套装立减 10%", "channel": "线下门店",
  "channel_mix": [{ "name": "线下门店", "ratio": 0.52 }],
  "products": [{ "name": "葡萄酒", "avg_spend": 603.06, "ratio": 0.4771 }],
  "upsell": [{ "from": "鱼类", "to": "甜食", "lift": 1.0849 }],
  "copy": "…", "budget": 2000, "cost_per_contact": 8, "cost": 2000,
  "expected_responses": 107.3, "expected_conv_rate": 0.4293, "avg_order_value": 61.92,
  "expected_revenue": 6644.0, "roi": 3.32, "priority": "P0 立即执行",
  "audience_preview": [{ "customer_id": "C00021", "prob": 0.93,
                         "total_spend": 1520.0, "purchase_freq": 24, "recency": 8 }],
  "kpi": {}
}
```

| 字段 | 说明 |
| --- | --- |
| `selected` | 实际圈选人数 = min(预算 ÷ 单客成本, 客群规模) |
| `coverage` | 圈选人数占客群比例 |
| `expected_responses` | 圈选人数 × 平均响应概率 |
| `avg_order_value` | 客群客单价（总消费 ÷ 购买频次） |
| `expected_revenue` | 预计响应人数 × 客单价 |
| `roi` | `expected_revenue ÷ cost` |
| `audience_preview` | 前 10 位高潜客户，可直接拿去触达 |

---

## POST /api/agent/chat

请求：

```json
{ "message": "给核心高价值客群生成一个营销方案，预算 2000 元", "history": [] }
```

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `message` | string | 用户问题 |
| `history` | array | 可选，历史消息 `[{role, content}]`，最多取最近 8 条 |

响应：

```json
{
  "reply": "已按核心高价值客群生成方案…",
  "intent": "campaign_plan",
  "args": { "segment": "核心高价值客群", "budget": 2000 },
  "mode": "rules",
  "blocks": [
    { "type": "text", "content": "…" },
    { "type": "kpi", "items": [{ "label": "圈选人数", "value": "250", "suffix": "人" }] },
    { "type": "chart", "title": "推荐品类", "option": { "series": [] }, "note": "…" },
    { "type": "table", "title": "名单", "columns": [{ "key": "customer_id", "title": "客户" }], "rows": [] }
  ]
}
```

| 字段 | 说明 |
| --- | --- |
| `intent` | 命中的意图（对应一个工具名） |
| `mode` | `llm`（在线大模型）/ `rules`（离线规则引擎） |
| `blocks` | 渲染块数组，前端按 `type` 分发渲染 |

四种渲染块：

| type | 字段 |
| --- | --- |
| `text` | `content` |
| `kpi` | `items[{label, value, suffix?}]` |
| `chart` | `title`, `option`（ECharts option）, `note?` |
| `table` | `title`, `columns[{key,title}]`, `rows[]` |

---

## GET /api/agent/suggestions

```json
{ "suggestions": [{ "label": "整体数据怎么样？", "message": "先看看整体数据情况" }] }
```

前端「快捷问题」按钮的数据来源。

