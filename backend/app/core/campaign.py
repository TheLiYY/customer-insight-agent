"""营销方案生成：把「画像 + 预测概率 + 品类偏好」落成一份可执行的活动方案。

思路：
1. 圈人：取目标客群里预测转化概率最高的 N 个人（预算决定 N）；
2. 选品：该客群的品类偏好 TOP3 + 关联规则里的「加购项」（没有品类字段就跳过）；
3. 选渠道：客群自身的高频渠道（没有渠道字段就用「线上触达」兜底）；
4. 定时点：按最近购买间隔决定「激活」还是「促复购」；
5. 算账：预期触达人数、预期响应数、预期 GMV、ROI。
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from .dataset import channels as channels_of
from .dataset import categories as categories_of
from .utils import clean, mean_of, num, pct, sum_of

START_BUDGET = 20000.0
START_COST = 4.0


def _parse_money(text: float | str, default: float) -> float:
    try:
        return float(text)
    except (TypeError, ValueError):
        return default


def build_plan(
    df: pd.DataFrame,
    scores: pd.DataFrame | None,
    segment_field: str,
    segment: str,
    budget: float = START_BUDGET,
    cost_per_contact: float = START_COST,
    discount: float = 0.12,
    rules: list[dict] | None = None,
) -> dict[str, Any]:
    """为指定客群生成一份营销方案。"""
    merged = df.copy()
    base_rate = mean_of(df, "response") if "response" in df.columns else 0.1
    base_rate = base_rate or 0.1
    if scores is not None and not scores.empty:
        merged = merged.merge(scores[["customer_id", "prob", "rank"]], on="customer_id", how="left")
        merged["prob"] = num(merged, "prob")
        merged.loc[merged["prob"] <= 0, "prob"] = base_rate
    else:
        merged["prob"] = base_rate
        merged["rank"] = range(1, len(merged) + 1)

    pool = merged[merged[segment_field] == segment].copy()
    if pool.empty:
        return {"ok": False, "message": f"没有找到客群「{segment}」的数据"}

    capacity = max(1, int(_parse_money(budget, START_BUDGET) / max(cost_per_contact, 0.01)))
    n_top = int(min(capacity, len(pool)))
    pool = pool.sort_values("prob", ascending=False)
    selected = pool.head(n_top)

    expected_responses = float(num(selected, "prob").sum())
    spend = sum_of(selected, "total_spend")
    freq = sum_of(selected, "purchase_freq")
    avg_order = spend / max(freq, 1)
    revenue = expected_responses * avg_order * (1 + discount * 0.3)
    cost = n_top * cost_per_contact
    roi = (revenue - cost) / cost if cost else 0.0

    # 品类偏好（人均消费额）
    cats = categories_of()
    products: list[dict] = []
    if cats:
        cat_means = {label: mean_of(selected, field) for field, label in cats.items()}
        cat_total = sum(cat_means.values()) or 1.0
        top_categories = sorted(cat_means.items(), key=lambda kv: -kv[1])
        products = [
            {"name": name, "avg_spend": clean(value), "ratio": pct(value, cat_total)}
            for name, value in top_categories[:3]
            if value > 0
        ]

    upsell = []
    if rules and products:
        for rule in rules[:5]:
            if any(p["name"] == rule["antecedent"] for p in products):
                upsell.append(
                    {"from": rule["antecedent"], "to": rule["consequent"], "lift": rule["lift"]}
                )
    upsell = upsell[:2]

    # 渠道
    chans = channels_of()
    if chans:
        channel_sum = {label: sum_of(selected, field) for field, label in chans.items()}
        ch_total = sum(channel_sum.values()) or 1.0
        channel_rows = sorted(channel_sum.items(), key=lambda kv: -kv[1])
        primary_channel = channel_rows[0][0]
        channel_mix = [{"name": n, "ratio": pct(v, ch_total)} for n, v in channel_rows]
    else:
        primary_channel = "线上触达"
        channel_mix = [{"name": "线上触达", "ratio": 1.0}]

    # 时机
    avg_recency = mean_of(selected, "recency")
    if avg_recency >= 70:
        timing = "48 小时内触达（沉默人群，越快越好）"
        goal = "唤回沉睡客户"
        offer = f"专属回归礼：满额立减 {int(discount * 100)}% + 免运费"
    elif 0 < avg_recency <= 25:
        timing = "下一个会员日前 3 天预热"
        goal = "提升复购频次"
        offer = f"会员加购券：第二件 {int(discount * 100)}% OFF"
    else:
        timing = "本周三 19:00-21:00 推送"
        goal = "拉升客单价"
        offer = f"组合套装立减 {int(discount * 100)}%"

    avg_age = mean_of(selected, "age")
    if products:
        top_cat = products[0]["name"]
        copy_text = (
            f"根据你常买的{top_cat}，我们为你挑了 {top_cat} 限时组合，{offer}。"
            f"点击{primary_channel}专属页即可领取。"
        )
    else:
        copy_text = f"为你量身准备了专属权益，{offer}。点击{primary_channel}即可领取。"

    preview_cols = [c for c in ("customer_id", "prob", "total_spend", "purchase_freq", "recency") if c in selected.columns]
    sample = selected.head(10)[preview_cols].to_dict(orient="records")

    return {
        "ok": True,
        "segment": segment,
        "segment_size": int(len(pool)),
        "selected": int(n_top),
        "coverage": pct(n_top, len(pool)),
        "goal": goal,
        "timing": timing,
        "offer": offer,
        "channel": primary_channel,
        "channel_mix": channel_mix,
        "products": products,
        "upsell": upsell,
        "copy": copy_text,
        "budget": clean(budget),
        "cost_per_contact": clean(cost_per_contact),
        "cost": clean(cost),
        "expected_responses": clean(expected_responses),
        "expected_conv_rate": clean(expected_responses / max(n_top, 1)),
        "avg_order_value": clean(avg_order),
        "expected_revenue": clean(revenue),
        "roi": clean(roi),
        "priority": "P0 立即执行" if roi >= 2 else ("P1 本周执行" if roi >= 1 else "P2 观察"),
        "audience_preview": [{**r, "prob": clean(r["prob"])} for r in sample],
        "avg_age": clean(avg_age),
        "kpi": {
            "触达人数": int(n_top),
            "预期响应率": clean(expected_responses / max(n_top, 1)),
            "预期 GMV": clean(revenue),
            "预算消耗": clean(cost),
            "ROI": clean(roi),
        },
    }
