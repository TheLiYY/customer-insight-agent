# API 字段说明

Base URL：`http://127.0.0.1:8000`
交互式文档：`/docs`（Swagger UI，可直接「Try it out」调试）、`/redoc`（ReDoc）、`/openapi.json`（原始 OpenAPI 3.1）

所有接口返回 JSON，异常统一为 `{ "detail": "错误信息" }`（HTTP 4xx/5xx）。

## 用 Apifox / Postman 管理接口

```bash
python scripts/export_openapi.py
```

会生成两个文件，任选其一导入：

| 文件 | 导入方式 |
| --- | --- |
| `docs/openapi.json` | Apifox → 项目设置 → 导入数据 → OpenAPI/Swagger |
| `docs/API.postman.json` | Apifox → 导入数据 → Postman（自带分组 + 示例请求体） |

导入后可在 Apifox 里做调试、Mock、自动化测试，也可以直接分享给前端联调。

> 下文所有示例值均来自仓库现有数据的真实响应（1867 位客户），可对照 `/docs` 自行复核。

---

## GET /api/health

```json
{
  "status": "ok",
  "app": "Customer Insight Agent",
  "version": "1.0.0",
  "llm_enabled": false,
  "customers": 1867,
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
  "source": "https://cdn.jsdelivr.net/gh/nailson/ifood-data-business-analyst-test@master/ifood_df.csv",
  "excel": "backend/data/raw/Customer_Personality_Analysis.xlsx",
  "rows": 1867,
  "columns": 26,
  "fields": [{ "name": "income", "label": "年收入", "type": "number", "desc": "..." }],
  "missing_cells": 0,
  "duplicate_rows": 0
}
```

> `rows` 是**清洗后**行数（原始 2205 行 → 去重 184 → 剔除收入缺失 154）。原始行数与处理过程见「数据说明」页。

---

## GET /api/overview

```json
{
  "kpis": {
    "customers": 1867, "response_rate": 0.1548, "response_count": 289,
    "avg_income": 51678.09, "avg_spend": 564.83, "avg_freq": 12.6,
    "avg_recency": 49.04, "total_revenue": 1054533.0,
    "dormant_rate": 0.2373, "dormant_count": 443,
    "complain_rate": 0.0102, "discount_dependence": 0.1851
  },
  "age": [{ "name": "41-50", "value": 496, "ratio": 0.2656 }],
  "education": [], "marital": [], "income": [],
  "category": [{ "name": "葡萄酒", "value": 296.4 }],
  "channel": [{ "name": "线上商城", "value": 3.9 }],
  "response_by_age": [{ "name": "41-50", "value": 0.164, "count": 81 }],
  "response_by_education": [],
  "spend_hist": [{ "name": "5~220", "value": 800, "label": "5~220" }],
  "recency_hist": [],
  "correlation": { "x": ["income", "..."], "y": ["..."], "values": [[1.0]] }
}
```

| 字段 | 说明 |
| --- | --- |
| `kpis.response_rate` | 最近一次活动响应率（0–1） |
| `kpis.avg_spend` | 人均历史消费金额（货币单位） |
| `kpis.dormant_rate` | 最近购买间隔 > 75 天的客户占比 |
| `kpis.discount_dependence` | 折扣购买次数占总购买次数的比例 |
| `category[].value` | 该品类人均消费金额 |
| `channel[].value` | 该渠道人均购买次数 |
| `response_by_*.value` | 该分组内的响应率 |
| `correlation` | 数值特征相关系数矩阵（用于说明特征选择合理性，前端图下有读图说明） |

---

## GET /api/insights?severity=risk&category=risk

自动结论接口（本次新增）。**分析跑完自动产出**，每条结论带证据链与建议动作。

```json
{
  "headline": "1867 位客户里，前 20% 贡献了 53.5% 的营收；按响应概率筛选后的头部名单，转化率是平均水平的 4.32 倍。",
  "counts": { "total": 10, "opportunity": 2, "risk": 4, "insight": 4, "filtered": 10 },
  "insights": [{
    "id": "value_concentration",
    "category": "insight",
    "severity": "insight",
    "severity_label": "结构洞察",
    "title": "重要价值客户是营收主力",
    "conclusion": "664 位重要价值客户只占 35.6%，却贡献了 56.9% 的营收。",
    "evidence": ["人均消费 902.6 元，是全量均值的 1.6 倍", "…"],
    "action": "对这群人做 VIP 维护，不要用大额折扣换短期成交。"
  }],
  "actions": [{ "priority": "P0", "action": "对 443 位超 75 天未购客户启动召回", "from": "沉默风险" }],
  "stats": {
    "customers": 1867, "response_rate": 0.1548, "top20_revenue_share": 0.5347,
    "auc": 0.8565, "head_lift": 4.32, "dormant_rate": 0.2373
  }
}
```

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `severity` | string | 可选，`opportunity` / `risk` / `insight` |
| `category` | string | 可选，按业务类别过滤（价值结构、流失风险、投放效率…） |

| 字段 | 说明 |
| --- | --- |
| `headline` | 一句话总结（前端首页展示） |
| `counts` | 各类结论数量；`filtered` 为过滤后条数 |
| `insights[].evidence` | 支撑该结论的具体数字，可逐条报给听众 |
| `insights[].action` | 下一步动作建议 |
| `actions` | 汇总后的执行清单（按 `priority` 排序） |

---

## GET /api/segments

```json
{
  "segments": [{
    "name": "重要价值客户", "priority": 1,
    "desc": "最近买过、买得又多又贵，是企业的现金牛。",
    "action": "VIP 专属权益 + 新品优先购；不要用大额折扣，重点维护关系。",
    "count": 664, "ratio": 0.3557, "revenue": 599606.0, "revenue_ratio": 0.5686,
    "avg_r": 4.6, "avg_f": 4.3, "avg_m": 4.4,
    "avg_recency": 26.3, "avg_freq": 19.1, "avg_spend": 902.6,
    "avg_income": 61920.4, "avg_age": 50.9,
    "response_rate": 0.244, "complain_rate": 0.006
  }],
  "matrix": { "rows": ["F5", "..."], "cols": ["M1", "..."], "values": [[12]] },
  "treemap": [{ "name": "重要价值客户", "value": 664, "revenue": 599606.0 }],
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

> 部分分层只有 1–8 人属正常现象：R/F/M 在这份数据里强正相关，交叉组合天然稀少。

---

## GET /api/personas

```json
{
  "k": 4, "silhouette": 0.2167, "inertia": 6536.72,
  "features": ["income", "total_spend", "..."],
  "clusters": [{ "cluster": 0, "name": "核心高价值客群", "size": 629 }],
  "personas": [{
    "cluster": 0, "name": "核心高价值客群", "status": "活跃", "rank": 1,
    "size": 629, "ratio": 0.3369, "revenue": 746686.0, "revenue_ratio": 0.7082,
    "headline": "高收入 · 高价值 · 高频复购",
    "tags": ["高收入", "高价值", "高频复购", "葡萄酒重度用户", "活动敏感型"],
    "summary": "…",
    "demographics": { "avg_age": 52.1, "age_group": [], "education": [], "marital": [], "children_rate": 0.71 },
    "value": { "avg_income": 71385.2, "avg_spend": 1186.9, "avg_freq": 21.4,
               "avg_order_value": 61.9, "avg_recency": 22.4, "avg_tenure_days": 2512 },
    "categories": [{ "name": "葡萄酒", "value": 602.21, "ratio": 0.4789 }],
    "channels": [{ "name": "线下门店", "value": 0.4424, "count": 5384 }],
    "behavior": { "discount_dependence": 0.14, "web_visits_month": 3.1,
                  "accepted_rate": 0.29, "response_rate": 0.223, "complain_rate": 0.003 }
  }]
}
```

| 字段 | 说明 |
| --- | --- |
| `silhouette` | 轮廓系数，聚类质量（-1~1，越大越好；消费类数据 0.2 左右属正常） |
| `status` | `活跃` / `沉默预警`，按平均最近购买间隔判定 |
| `tags` | 规则生成的画像标签，可直接用于运营打标 |
| `value.avg_order_value` | 客单价 = 总消费 ÷ 购买频次 |
| `categories[].ratio` | 该品类消费占客群总消费的比例 |
| `channels[].value` | 该渠道购买次数占比（`count` 为次数合计） |

---

## GET /api/clusters/elbow?k_max=6

```json
{ "points": [{ "k": 2, "inertia": 9421.7, "silhouette": 0.3214 }] }
```

用肘部法 + 轮廓系数共同选择 k，前端双轴图展示。

---

## GET /api/propensity

```json
{
  "metrics": { "threshold": 0.59, "accuracy": 0.8503, "precision": 0.5126,
               "recall": 0.7011, "f1": 0.5922,
               "confusion": { "tp": 61, "fp": 58, "fn": 26, "tn": 416 },
               "auc": 0.8565 },
  "full_metrics": { "threshold": 0.59, "accuracy": 0.8495, "auc": 0.8701 },
  "coefs": [{ "feature": "历史活动接受数", "key": "accepted_total", "coef": 0.836, "direction": "正向" }],
  "lift": [{ "group": "第1组", "customers": 187, "avg_score": 0.9183,
             "response_rate": 0.6684, "lift": 4.3183, "captured": 0.4325 }],
  "base_rate": 0.1548,
  "threshold": 0.59,
  "score_hist": [{ "name": "0.0-0.1", "value": 620 }],
  "top_customers": [{ "customer_id": "C00533", "cluster_name": "核心高价值客群",
                      "rfm_segment": "重要价值客户", "prob": 0.9979,
                      "total_spend": 1924.0, "purchase_freq": 19, "recency": 61 }]
}
```

| 字段 | 说明 |
| --- | --- |
| `metrics` | 测试集（30%）指标；阈值由验证集 PR 曲线按 F1 最优选出 |
| `full_metrics` | 全量重训后的指标（用于对照是否过拟合） |
| `coefs[].coef` | 标准化后的逻辑回归系数，绝对值越大影响越强 |
| `lift[].lift` | 该分位响应率 ÷ 整体响应率 |
| `lift[].captured` | 该分位捕获了多少比例的响应客户 |

> 兼容说明：早期字段名 `train_metrics` 仍保留，含义与 `metrics` 相同（测试集评估结果）。

---

## GET /api/association

```json
{
  "rules": [{ "antecedent": "甜食", "consequent": "鱼类",
              "support": 0.7333, "confidence": 0.8995, "lift": 1.0919, "count": 1369 }],
  "penetration": [{ "name": "葡萄酒", "buyers": 1789, "penetration": 0.958,
                    "avg_spend": 296.4, "buyer_avg_spend": 305.6,
                    "revenue": 553709.0, "revenue_ratio": 0.5251 }],
  "basket_size": { "avg": 4.6, "distribution": [] }
}
```

| 字段 | 说明 |
| --- | --- |
| `support` | 同时购买 A 和 B 的客户占比 |
| `confidence` | 买了 A 的客户中同时买 B 的比例 |
| `lift` | 置信度 ÷ B 的整体渗透率；>1 表示正相关 |
| `penetration` | 品类渗透率（买过该品类的客户占比） |

> 该数据各品类渗透率都在 90% 以上，因此 lift 普遍接近 1.09——关联强度有限，自动结论里据此给出「做组合套餐而非主打推荐」的建议。

---

## GET /api/customers?page=1&size=20&sort=total_spend&order=desc

```json
{
  "total": 1867, "page": 1, "size": 20,
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
  "clusters": [{ "name": "核心高价值客群", "size": 629, "headline": "高收入 · 高价值 · 高频复购" }],
  "rfm": [{ "name": "重要价值客户", "size": 664 }]
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
  "ok": true, "segment": "核心高价值客群", "segment_size": 629,
  "selected": 250, "coverage": 0.3975,
  "goal": "拉升客单价", "timing": "本周三 19:00-21:00 推送",
  "offer": "组合套装立减 10%", "channel": "线下门店",
  "channel_mix": [{ "name": "线下门店", "ratio": 0.4424 }],
  "products": [{ "name": "葡萄酒", "avg_spend": 758.78, "ratio": 0.4972 }],
  "upsell": [{ "from": "甜食", "to": "鱼类", "lift": 1.0919 }],
  "copy": "…", "budget": 2000, "cost_per_contact": 8, "cost": 2000,
  "expected_responses": 200.08, "expected_conv_rate": 0.8003, "avg_order_value": 74.66,
  "expected_revenue": 15386.34, "roi": 6.6932, "priority": "P0 立即执行",
  "audience_preview": [{ "customer_id": "C00533", "prob": 0.9979,
                         "total_spend": 1924.0, "purchase_freq": 19, "recency": 61 }],
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
| `roi` | `expected_revenue ÷ cost`（理想口径，未含物流/退货/毛利） |
| `audience_preview` | 前 10 位高潜客户，可直接拿去触达 |

> 若 `segment` 名字对不上，返回 `{ "ok": false, "message": "没有找到客群「…」的数据" }`，前端会提示重新选择。

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
| `intent` | 命中的意图（对应一个工具名），共 8 个：`overview_report` / `insights_report` / `segment_report` / `persona_report` / `propensity_report` / `campaign_plan` / `category_report` / `customer_profile` |
| `mode` | `llm`（在线大模型 Function Calling）/ `rules`（离线规则引擎） |
| `fallback_reason` | 仅在线模式失败降级到规则引擎时出现 |
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
{ "suggestions": [
  { "label": "自动分析结论", "message": "分析完之后有什么结论和建议？" },
  { "label": "整体数据怎么样？", "message": "先看看整体数据情况" }
] }
```

前端「快捷问题」按钮的数据来源。
