"""Agent 的「工具箱」。

每个工具做一件事：读数据 → 算指标 → 输出一组前端能直接渲染的积木块（blocks）。
积木块只有四种：text / kpi / chart / table，前端实现最简单，也方便大模型挑选用哪个。
"""
from __future__ import annotations

from typing import Any, Callable

from ..core.dataset import categories as categories_of
from ..core.store import store
from ..core.utils import clean


# ------------------------------------------------------------------ 渲染块构造
def text(content: str) -> dict:
    return {"type": "text", "content": content}


def kpi(items: list[dict]) -> dict:
    return {"type": "kpi", "items": items}


def chart(title: str, option: dict, note: str = "") -> dict:
    return {"type": "chart", "title": title, "option": option, "note": note}


def table(title: str, columns: list[dict], rows: list[dict]) -> dict:
    return {"type": "table", "title": title, "columns": columns, "rows": rows}


def pie_option(data: list[dict], name: str = "数量") -> dict:
    return {
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
        "legend": {"bottom": 0, "type": "scroll"},
        "series": [
            {
                "name": name,
                "type": "pie",
                "radius": ["42%", "66%"],
                "center": ["50%", "44%"],
                "avoidLabelOverlap": True,
                "itemStyle": {"borderRadius": 6, "borderWidth": 2},
                "label": {"show": True, "formatter": "{b}\n{d}%"},
                "data": [{"name": d["name"], "value": d["value"]} for d in data],
            }
        ],
    }


def bar_option(categories: list[str], values: list[float], name: str = "数值", horizontal: bool = False) -> dict:
    cat_axis = {"type": "category", "data": categories, "axisLabel": {"interval": 0, "rotate": 0 if horizontal else 25}}
    val_axis = {"type": "value"}
    return {
        "tooltip": {"trigger": "axis"},
        "grid": {"left": 60, "right": 24, "top": 24, "bottom": 60},
        "xAxis": val_axis if horizontal else cat_axis,
        "yAxis": cat_axis if horizontal else val_axis,
        "series": [{"name": name, "type": "bar", "barMaxWidth": 36, "data": values, "itemStyle": {"borderRadius": 4}}],
    }


def line_option(categories: list[str], values: list[float], name: str = "数值") -> dict:
    return {
        "tooltip": {"trigger": "axis"},
        "grid": {"left": 60, "right": 24, "top": 24, "bottom": 50},
        "xAxis": {"type": "category", "data": categories},
        "yAxis": {"type": "value"},
        "series": [
            {"name": name, "type": "line", "smooth": True, "data": values, "areaStyle": {"opacity": 0.15}}
        ],
    }


# ------------------------------------------------------------------ 工具实现
def overview_report(args: dict) -> list[dict]:
    data = store.overview
    k = data["kpis"]
    items = [{"label": "客户总数", "value": k["customers"], "suffix": "人"}]
    if k.get("response_rate") is not None:
        items.append({"label": "活动响应率", "value": round(k["response_rate"] * 100, 1), "suffix": "%"})
    items.append({"label": "人均消费", "value": k["avg_spend"], "suffix": "元"})
    items.append({"label": "人均购买频次", "value": k["avg_freq"], "suffix": "次"})
    if k.get("dormant_rate") is not None:
        items.append({"label": "沉睡客户占比", "value": round(k["dormant_rate"] * 100, 1), "suffix": "%"})
    blocks = [kpi(items)]
    if data["age"]:
        blocks.append(chart("年龄段分布", pie_option(data["age"])))
    if data["category"]:
        blocks.append(chart("各品类消费总额（元）", bar_option([d["name"] for d in data["category"]], [d["value"] for d in data["category"]], "消费额")))
    if data["response_by_age"]:
        blocks.append(chart("不同年龄段的响应率", bar_option([d["name"] for d in data["response_by_age"]], [round((d["value"] or 0) * 100, 1) for d in data["response_by_age"]], "响应率%")))
    top_age = data["response_by_age"][0] if data["response_by_age"] else None
    concl = (
        f"样本共 {k['customers']} 位客户，"
        + (f"最近一次营销活动的响应率为 {k['response_rate'] * 100:.1f}%，" if k.get("response_rate") is not None else "这份数据没有营销响应标签，")
        + f"人均消费 {k['avg_spend']:.0f} 元、人均下单 {k['avg_freq']:.1f} 次。"
    )
    if k.get("dormant_count") is not None:
        concl += f"有 {k['dormant_count']} 位客户（{k['dormant_rate'] * 100:.1f}%）超过 75 天没有购买，属于需要优先唤醒的人群。"
    if top_age:
        concl += f" 响应率最高的是{top_age['name']}客群（{top_age['value'] * 100:.1f}%），说明该年龄段对活动更敏感。"
    blocks.append(text(concl))
    return blocks


def segment_report(args: dict) -> list[dict]:
    segs = store.segment_summary
    cols = [
        {"key": "name", "label": "客群"},
        {"key": "count", "label": "人数"},
        {"key": "ratio", "label": "占比", "format": "percent"},
        {"key": "avg_spend", "label": "人均消费"},
        {"key": "avg_freq", "label": "人均频次"},
        {"key": "response_rate", "label": "响应率", "format": "percent"},
        {"key": "action", "label": "运营策略"},
    ]
    rows = [
        {
            "name": s["name"],
            "count": s["count"],
            "ratio": s["ratio"],
            "avg_spend": s["avg_spend"],
            "avg_freq": s["avg_freq"],
            "response_rate": s["response_rate"],
            "action": s["action"],
        }
        for s in segs
    ]
    blocks = [
        text("按 RFM（最近购买 R、购买频次 F、消费金额 M）把客户分成 8 个经典客群，优先级从高到低排列："),
        table("RFM 客群分层", cols, rows),
        chart("各客群人数", bar_option([s["name"] for s in segs], [s["count"] for s in segs], "人数")),
        chart("各客群消费贡献（元）", pie_option([{"name": s["name"], "value": s["revenue"]} for s in segs], "消费额")),
    ]
    top = segs[0] if segs else None
    if top:
        blocks.append(
            text(
                f"最高优先级是「{top['name']}」：{top['count']} 人（占 {top['ratio'] * 100:.1f}%），"
                f"贡献了 {top['revenue_ratio'] * 100:.1f}% 的消费额。建议动作：{top['action']}"
            )
        )
    return blocks


def persona_report(args: dict) -> list[dict]:
    name = args.get("name")
    personas = store.personas
    if name:
        target = [p for p in personas if p["name"] == name or str(p["cluster"]) == str(name)]
        if not target:
            return [text(f"没有找到客群「{name}」，当前的客群有：" + "、".join(p["name"] for p in personas))]
        p = target[0]
        return [
            {"type": "persona", "persona": p},
            chart(
                f"{p['name']} 的品类偏好（人均消费元）",
                pie_option(p["categories"], "人均消费"),
            ),
            text(
                f"{p['name']}：{p['summary']} 建议动作——"
                f"目标是{p['name']}的核心诉求，优先在{p['channels'][0]['name']}触达。"
            ),
        ]
    return [
        text(f"用 KMeans（k={store.cluster['k']}，轮廓系数 {store.cluster['silhouette']}）把客户聚成 {len(personas)} 个画像清晰的客群："),
        {"type": "persona_list", "personas": personas},
        chart("各客群规模", bar_option([p["name"] for p in personas], [p["size"] for p in personas], "人数", horizontal=True)),
    ]


def propensity_report(args: dict) -> list[dict]:
    prop = store.propensity
    if not prop.get("available", True):
        return [
            text(prop.get("reason") or "这份数据暂时不支持响应预测。"),
            text("响应预测需要「是否响应过活动」这样的标签列。补充后重新跑 prepare_data.py 即可启用。"),
        ]
    metrics = prop["train_metrics"]
    top = (
        store.enriched.sort_values("prob", ascending=False)
        .head(10)[["customer_id", "cluster_name", "prob", "total_spend", "recency"]]
        .to_dict(orient="records")
    )
    coefs = prop["coefs"][:8]
    blocks = [
        kpi(
            [
                {"label": "测试集 AUC", "value": metrics.get("auc"), "suffix": ""},
                {"label": "准确率", "value": round((metrics.get("accuracy") or 0) * 100, 1), "suffix": "%"},
                {"label": "精准率", "value": round((metrics.get("precision") or 0) * 100, 1), "suffix": "%"},
                {"label": "召回率", "value": round((metrics.get("recall") or 0) * 100, 1), "suffix": "%"},
                {"label": "大盘响应率", "value": round((prop.get("base_rate") or 0) * 100, 1), "suffix": "%"},
            ]
        ),
        text(
            "用逻辑回归预测「这位客户会不会响应下一次活动」。AUC 越接近 1 说明排序能力越强，"
            "0.5 相当于瞎猜。下面是每个因素对转化概率的影响（正数=更可能买单）："
        ),
        chart("特征影响力（系数）", bar_option([c["feature"] for c in coefs], [c["coef"] for c in coefs], "系数", horizontal=True)),
        chart("十分位提升曲线", line_option([r["group"] for r in prop["lift"]], [r["lift"] for r in prop["lift"]], "提升倍数")),
        table(
            "预测最可能响应的 10 位客户",
            [
                {"key": "customer_id", "label": "客户ID"},
                {"key": "cluster_name", "label": "所属客群"},
                {"key": "prob", "label": "转化概率", "format": "percent"},
                {"key": "total_spend", "label": "累计消费"},
                {"key": "recency", "label": "最近购买(天前)"},
            ],
            [{**r, "prob": clean(r["prob"])} for r in top],
        ),
    ]
    best = max(prop["coefs"], key=lambda c: c["coef"] or 0)
    worst = min(prop["coefs"], key=lambda c: c["coef"] or 0)
    blocks.append(
        text(
            f"结论：最能把客户推向成交的因素是「{best['feature']}」，最拖后腿的是「{worst['feature']}」。"
            f"把预算集中投给预测概率前 20% 的客户，能覆盖约 {sum(r['captured'] for r in prop['lift'][:2]) * 100:.0f}% 的实际响应客户。"
        )
    )
    return blocks


def campaign_plan(args: dict) -> list[dict]:
    segment = args.get("segment") or (store.personas[0]["name"] if store.personas else "")
    budget = float(args.get("budget") or 20000)
    plan = store.plan(segment, budget, float(args.get("cost_per_contact") or 4), float(args.get("discount") or 0.12))
    if not plan.get("ok"):
        return [text(plan.get("message", "生成失败"))]
    plans = [
        kpi(
            [
                {"label": "触达人数", "value": plan["selected"], "suffix": "人"},
                {"label": "预期响应率", "value": round(plan["expected_conv_rate"] * 100, 1), "suffix": "%"},
                {"label": "预期 GMV", "value": plan["expected_revenue"], "suffix": "元"},
                {"label": "预算消耗", "value": plan["cost"], "suffix": "元"},
                {"label": "ROI", "value": plan["roi"], "suffix": "倍"},
            ]
        ),
        text(f"目标客群：{plan['segment']}（共 {plan['segment_size']} 人，本次覆盖 {plan['coverage'] * 100:.1f}%）"),
        text(f"活动目标：{plan['goal']}　|　触达时点：{plan['timing']}　|　主投渠道：{plan['channel']}"),
        text(f"主推权益：{plan['offer']}"),
        text(f"主推商品：{ '、'.join(p['name'] for p in plan['products']) }"),
        chart(
            "受众品类偏好（人均消费元）",
            pie_option([{"name": p["name"], "value": p["avg_spend"]} for p in plan["products"]], "人均消费"),
        ),
        {"type": "copy", "title": "推荐话术", "content": plan["copy"]},
        table(
            "优先触达名单（前 10 位）",
            [
                {"key": "customer_id", "label": "客户ID"},
                {"key": "prob", "label": "转化概率", "format": "percent"},
                {"key": "total_spend", "label": "累计消费"},
                {"key": "purchase_freq", "label": "频次"},
                {"key": "recency", "label": "最近购买"},
            ],
            plan["audience_preview"],
        ),
        text(f"执行优先级：{plan['priority']}。预期投入 {plan['cost']:.0f} 元，带来约 {plan['expected_revenue']:.0f} 元 GMV，ROI 约 {plan['roi']:.1f} 倍。"),
    ]
    return plans


def category_report(args: dict) -> list[dict]:
    rules = store.rules
    rows = [
        {
            "antecedent": r["antecedent"],
            "consequent": r["consequent"],
            "support": r["support"],
            "confidence": r["confidence"],
            "lift": r["lift"],
        }
        for r in rules[:8]
    ]
    blocks = [
        chart("品类渗透率", pie_option([{"name": p["name"], "value": p["buyers"]} for p in store.penetration], "购买人数")),
        chart("各品类消费额（元）", bar_option([p["name"] for p in store.penetration], [p["revenue"] for p in store.penetration], "消费额")),
        table(
            "品类关联规则（买了 A 之后买 B 的概率）",
            [
                {"key": "antecedent", "label": "先买"},
                {"key": "consequent", "label": "再买"},
                {"key": "support", "label": "支持度", "format": "percent"},
                {"key": "confidence", "label": "置信度", "format": "percent"},
                {"key": "lift", "label": "提升度"},
            ],
            rows,
        ),
    ]
    if rows:
        best = rows[0]
        blocks.append(
            text(
                f"最强关联是「{best['antecedent']} → {best['consequent']}」：置信度 {best['confidence'] * 100:.1f}%，"
                f"提升度 {best['lift']}（大于 1 表示两者确实互相带动）。可以把它做成加购推荐或组合套装。"
            )
        )
    return blocks


def customer_profile(args: dict) -> list[dict]:
    cid = str(args.get("customer_id", "")).strip()
    table_df = store.enriched
    ids = table_df["customer_id"].astype(str)
    hit = table_df.loc[ids == cid] if cid else table_df.head(0)
    if hit.empty:
        samples = "、".join(ids.head(3).tolist())
        prefix = f"没找到客户「{cid}」。" if cid else "记得带上客户编号，"
        return [text(f"{prefix}可以试试 {samples} 这样的编号。")]
    row = hit.iloc[0]
    cat_fields = [(f, label) for f, label in categories_of().items() if f in hit.columns]
    cats = [{"name": label, "value": clean(row[f])} for f, label in cat_fields]
    blocks = [
        kpi(
            [
                {"label": "客户ID", "value": cid},
                {"label": "客群", "value": row["cluster_name"]},
                {"label": "RFM分层", "value": row["rfm_segment"]},
                {"label": "转化概率", "value": round(float(row["prob"]) * 100, 1), "suffix": "%"},
            ]
        ),
        kpi(
            [
                {"label": "年龄", "value": clean(row.get("age")), "suffix": "岁"},
                {"label": "年收入", "value": clean(row.get("income")), "suffix": "元"},
                {"label": "累计消费", "value": clean(row.get("total_spend")), "suffix": "元"},
                {"label": "购买频次", "value": clean(row.get("purchase_freq")), "suffix": "次"},
                {"label": "最近购买", "value": clean(row.get("recency")), "suffix": "天前"},
            ]
        ),
    ]
    if len(cats) >= 3:
        top = max(c["value"] or 0 for c in cats) or 1
        radar = {
            "tooltip": {},
            "radar": {"indicator": [{"name": c["name"], "max": round(top * 1.2, 2)} for c in cats]},
            "series": [
                {"type": "radar", "data": [{"name": "消费额", "value": [c["value"] or 0 for c in cats]}]}
            ],
        }
        blocks.append(chart("品类消费结构（元）", radar))
    detail = (
        f"这位客户累计消费 {float(row.get('total_spend') or 0):,.0f} 元，"
        f"购买 {float(row.get('purchase_freq') or 0):.0f} 次，"
        f"最近一次购买在 {float(row.get('recency') or 0):.0f} 天前，"
        f"属于「{row['cluster_name']}」/「{row['rfm_segment']}」，"
        f"预测下次活动响应概率 {float(row['prob']) * 100:.1f}%。"
    )
    blocks.append(text(detail))
    return blocks


# ------------------------------------------------------------------ 注册表
def insights_report(args: dict) -> list[dict]:
    """自动分析结论：一次把所有分析跑完，直接给出结论、证据和建议动作。"""
    data = store.insights
    items = data["insights"]
    blocks: list[dict] = [
        kpi(
            [
                {"label": "结论总数", "value": data["counts"]["total"], "suffix": "条"},
                {"label": "增长机会", "value": data["counts"]["opportunity"], "suffix": "条"},
                {"label": "风险预警", "value": data["counts"]["risk"], "suffix": "条"},
                {"label": "结构洞察", "value": data["counts"]["insight"], "suffix": "条"},
            ]
        ),
        text(data["headline"]),
    ]
    for item in items:
        blocks.append(text(f"【{item['severity_label']}】{item['title']}\n{item['conclusion']}\n建议：{item['action']}"))
    if data["actions"]:
        blocks.append(
            table(
                "按优先级排序的行动清单",
                [
                    {"key": "priority", "label": "优先级"},
                    {"key": "action", "label": "动作"},
                    {"key": "from", "label": "来自结论"},
                ],
                data["actions"],
            )
        )
    return blocks


TOOL_SPECS: list[dict] = [
    {
        "name": "overview_report",
        "description": "查看整体数据总览：客户规模、响应率、收入与消费水平、年龄结构、品类消费、响应率对比。适合「整体情况怎么样」这类问题。",
        "params": {},
        "run": overview_report,
    },
    {
        "name": "segment_report",
        "description": "按 RFM 做客户分层，给出 8 个客群的人数、消费贡献、响应率和运营策略。适合「客户怎么分层」「哪些客户最重要」这类问题。",
        "params": {},
        "run": segment_report,
    },
    {
        "name": "persona_report",
        "description": "查看客户画像（聚类得到的客群画像卡）。可以指定客群名称，不指定则返回全部客群。",
        "params": {"name": "客群名称，可为空"},
        "run": persona_report,
    },
    {
        "name": "propensity_report",
        "description": "预测哪些客户最可能响应下一次营销活动，给出模型效果、特征影响力和高潜客户名单。适合「该推给谁」「谁会买单」这类问题。",
        "params": {},
        "run": propensity_report,
    },
    {
        "name": "campaign_plan",
        "description": "为某个客群生成可执行的营销方案：圈人、选品、选渠道、定时点、话术、预算与 ROI 测算。",
        "params": {"segment": "客群名称", "budget": "预算金额，默认 20000"},
        "run": campaign_plan,
    },
    {
        "name": "category_report",
        "description": "品类结构分析与关联规则：哪个品类卖得好、买了 A 还会买 B，用于交叉销售。",
        "params": {},
        "run": category_report,
    },
    {
        "name": "customer_profile",
        "description": "查询单个客户的画像详情，需要提供 customer_id。",
        "params": {"customer_id": "客户编号，例如 C00001"},
        "run": customer_profile,
    },
    {
        "name": "insights_report",
        "description": "自动分析结论：把所有分析跑完后直接输出「发现了什么 + 证据 + 该做什么」，适合「给我结论」「有什么建议」「分析完总结一下」这类问题。",
        "params": {},
        "run": insights_report,
    },
]

TOOLS: dict[str, Callable[[dict], list[dict]]] = {t["name"]: t["run"] for t in TOOL_SPECS}


def public_specs() -> list[dict]:
    return [{"name": t["name"], "description": t["description"], "params": t["params"]} for t in TOOL_SPECS]
