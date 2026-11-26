"""客户画像：把一个聚类结果翻译成「人」的样子。

输出包含：身份标签、人口属性、消费能力、渠道偏好、品类偏好、行为特征、营销策略。
前端直接把它渲染成画像卡片，Agent 也用它来组织话术。
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from .config import CATEGORY_FIELDS, CHANNEL_FIELDS, zh_education, zh_marital
from .utils import clean, pct, top_share


def _share(counter: pd.Series) -> list[dict]:
    total = float(counter.sum()) or 1.0
    return [
        {"name": str(k), "value": int(v), "ratio": pct(v, total)}
        for k, v in counter.items()
    ]


def _tags(sub: pd.DataFrame, overall: pd.DataFrame) -> list[str]:
    """用可解释的阈值规则打标签，方便业务方理解和复用。"""
    tags: list[str] = []
    avg_income = float(sub["income"].mean())
    avg_spend = float(sub["total_spend"].mean())
    avg_recency = float(sub["recency"].mean())
    avg_freq = float(sub["purchase_freq"].mean())
    avg_age = float(sub["age"].mean())

    if avg_income >= overall["income"].mean() * 1.2:
        tags.append("高收入")
    elif avg_income <= overall["income"].mean() * 0.8:
        tags.append("价格敏感")

    if avg_spend >= overall["total_spend"].mean() * 1.4:
        tags.append("高价值")
    elif avg_spend <= overall["total_spend"].mean() * 0.6:
        tags.append("低客单")

    if avg_recency <= 30:
        tags.append("近期活跃")
    elif avg_recency >= 75:
        tags.append("濒临流失")

    if avg_freq >= overall["purchase_freq"].mean() * 1.2:
        tags.append("高频复购")
    elif avg_freq <= overall["purchase_freq"].mean() * 0.7:
        tags.append("低频")

    if avg_age >= 55:
        tags.append("银发群体")
    elif avg_age <= 38:
        tags.append("年轻客群")

    if float(sub["kidhome"].mean()) >= 0.5:
        tags.append("有孩家庭")

    # 品类偏好：占比超过 40% 视为重度用户
    cat_mean = {f: float(sub[f].mean()) for f in CATEGORY_FIELDS}
    cat_total = sum(cat_mean.values()) or 1.0
    top_field = max(cat_mean, key=cat_mean.get)
    if cat_mean[top_field] / cat_total >= 0.4:
        tags.append(f"{CATEGORY_FIELDS[top_field]}重度用户")

    # 渠道偏好
    channel = {f: float(sub[f].sum()) for f in CHANNEL_FIELDS}
    ch_total = sum(channel.values()) or 1.0
    top_channel = max(channel, key=channel.get)
    if channel[top_channel] / ch_total >= 0.45:
        tags.append(f"{CHANNEL_FIELDS[top_channel]}为主")

    freq = max(avg_freq, 1e-6)
    if float(sub["num_deals"].mean()) / freq >= 0.3:
        tags.append("折扣依赖")

    if float(sub["accepted_total"].mean()) >= 0.4:
        tags.append("活动敏感型")

    return tags[:6]


def build_persona(
    sub: pd.DataFrame,
    cluster: dict[str, Any],
    overall: pd.DataFrame,
    revenue_total: float,
) -> dict[str, Any]:
    """单个客群的完整画像。"""
    avg_age = float(sub["age"].mean())
    avg_income = float(sub["income"].mean())
    avg_spend = float(sub["total_spend"].mean())
    avg_freq = float(sub["purchase_freq"].mean())
    avg_recency = float(sub["recency"].mean())
    order_value = avg_spend / avg_freq if avg_freq else 0.0

    categories = []
    for field, label in CATEGORY_FIELDS.items():
        categories.append({"name": label, "value": clean(float(sub[field].mean()))})
    cat_total = sum(c["value"] or 0 for c in categories) or 1.0
    for c in categories:
        c["ratio"] = pct(c["value"], cat_total)
    categories.sort(key=lambda c: -(c["value"] or 0))

    channels = []
    ch_total = float(sum(float(sub[f].sum()) for f in CHANNEL_FIELDS)) or 1.0
    for field, label in CHANNEL_FIELDS.items():
        ch = float(sub[field].sum())
        channels.append({"name": label, "value": clean(ch / ch_total), "count": clean(ch)})
    channels.sort(key=lambda c: -(c["value"] or 0))

    tags = _tags(sub, overall)
    headline = " · ".join(tags[:3]) if tags else "待补充标签"

    education = sub["education"].map(zh_education).value_counts()
    marital = sub["marital_status"].map(zh_marital).value_counts()
    age_group = sub["age_group"].value_counts()

    persona = {
        "cluster": cluster["cluster"],
        "name": cluster["name"],
        "status": cluster["status"],
        "rank": cluster["rank"],
        "size": int(len(sub)),
        "ratio": pct(len(sub), len(overall)),
        "revenue": clean(float(sub["total_spend"].sum())),
        "revenue_ratio": pct(float(sub["total_spend"].sum()), revenue_total),
        "headline": headline,
        "tags": tags,
        "summary": (
            f"平均 {avg_age:.0f} 岁，{education.index[0] if len(education) else '未知'}学历为主，"
            f"家庭年收入约 {avg_income:,.0f} 元，近两年消费 {avg_spend:,.0f} 元、"
            f"下单 {avg_freq:.0f} 次，最近一次购买在 {avg_recency:.0f} 天前，"
            f"最偏好的品类是{categories[0]['name']}。"
        ),
        "demographics": {
            "avg_age": clean(avg_age),
            "age_group": _share(age_group)[:3],
            "education": _share(education)[:3],
            "marital": _share(marital)[:3],
            "children_rate": clean(float((sub["kidhome"] + sub["teenhome"] > 0).mean())),
        },
        "value": {
            "avg_income": clean(avg_income),
            "avg_spend": clean(avg_spend),
            "avg_freq": clean(avg_freq),
            "avg_order_value": clean(order_value),
            "avg_recency": clean(avg_recency),
            "avg_tenure_days": clean(float(sub["tenure_days"].mean())),
        },
        "categories": categories,
        "channels": channels,
        "behavior": {
            "discount_dependence": clean(float(sub["num_deals"].mean()) / max(avg_freq, 1e-6)),
            "web_visits_month": clean(float(sub["web_visits_month"].mean())),
            "accepted_rate": clean(float(sub["accepted_total"].mean()) / 5),
            "response_rate": clean(float(sub["response"].mean())),
            "complain_rate": clean(float(sub["complain"].mean())),
        },
    }
    return persona


def build_all(
    cluster_table: pd.DataFrame, clusters: list[dict], overall: pd.DataFrame
) -> list[dict[str, Any]]:
    revenue_total = float(overall["total_spend"].sum())
    personas = []
    for cluster in clusters:
        sub = cluster_table[cluster_table["cluster"] == cluster["cluster"]]
        if sub.empty:
            continue
        personas.append(build_persona(sub, cluster, overall, revenue_total))
    personas.sort(key=lambda p: p["rank"])
    return personas
