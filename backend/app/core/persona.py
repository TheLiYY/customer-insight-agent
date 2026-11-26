"""客户画像：把一个聚类结果翻译成「人」的样子。

输出包含：身份标签、人口属性、消费能力、渠道偏好、品类偏好、行为特征、营销策略。
前端直接把它渲染成画像卡片，Agent 也用它来组织话术。

换数据注意：这份代码不假设某个字段一定存在。缺收入就不打「高收入」标签，
缺品类就不显示品类偏好（categories 为空数组），前端会自动隐藏对应区块。
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from .config import zh_education, zh_marital
from .dataset import categories as categories_of
from .dataset import channels as channels_of
from .utils import clean, mean_of, num, pct, sum_of


def _share(counter: pd.Series) -> list[dict]:
    total = float(counter.sum()) or 1.0
    return [{"name": str(k), "value": int(v), "ratio": pct(v, total)} for k, v in counter.items()]


def _value_counts(df: pd.DataFrame, col: str, labeler=None) -> pd.Series:
    if col not in df.columns:
        return pd.Series(dtype=int)
    series = df[col].astype(str).str.strip()
    if labeler is not None:
        series = series.map(labeler)
    series = series[series.str.len() > 0]
    return series.value_counts()


def _tags(sub: pd.DataFrame, overall: pd.DataFrame) -> list[str]:
    """用可解释的阈值规则打标签，方便业务方理解和复用。只对有数据的维度打标签。"""
    tags: list[str] = []

    if "income" in sub.columns:
        base = mean_of(overall, "income")
        avg_income = mean_of(sub, "income")
        if base > 0 and avg_income >= base * 1.2:
            tags.append("高收入")
        elif base > 0 and avg_income <= base * 0.8:
            tags.append("价格敏感")

    if "total_spend" in sub.columns:
        base = mean_of(overall, "total_spend")
        avg_spend = mean_of(sub, "total_spend")
        if base > 0 and avg_spend >= base * 1.4:
            tags.append("高价值")
        elif base > 0 and avg_spend <= base * 0.6:
            tags.append("低客单")

    if "recency" in sub.columns:
        avg_recency = mean_of(sub, "recency")
        if avg_recency <= 30:
            tags.append("近期活跃")
        elif avg_recency >= 75:
            tags.append("濒临流失")

    if "purchase_freq" in sub.columns:
        base = mean_of(overall, "purchase_freq")
        avg_freq = mean_of(sub, "purchase_freq")
        if base > 0 and avg_freq >= base * 1.2:
            tags.append("高频复购")
        elif base > 0 and avg_freq <= base * 0.7:
            tags.append("低频")

    if "age" in sub.columns:
        avg_age = mean_of(sub, "age")
        if avg_age >= 55:
            tags.append("银发群体")
        elif 0 < avg_age <= 38:
            tags.append("年轻客群")

    if "children" in sub.columns and mean_of(sub, "children") >= 0.5:
        tags.append("有孩家庭")

    # 品类偏好：占比超过 40% 视为重度用户
    cats = categories_of()
    if cats:
        cat_mean = {f: mean_of(sub, f) for f in cats}
        cat_total = sum(cat_mean.values()) or 1.0
        top_field = max(cat_mean, key=cat_mean.get)
        if cat_mean[top_field] / cat_total >= 0.4:
            tags.append(f"{cats[top_field]}重度用户")

    # 渠道偏好
    chans = channels_of()
    if chans:
        channel = {f: sum_of(sub, f) for f in chans}
        ch_total = sum(channel.values()) or 1.0
        top_channel = max(channel, key=channel.get)
        if channel[top_channel] / ch_total >= 0.45:
            tags.append(f"{chans[top_channel]}为主")

    if "num_deals" in sub.columns:
        freq = max(mean_of(sub, "purchase_freq"), 1e-6)
        if mean_of(sub, "num_deals") / freq >= 0.3:
            tags.append("折扣依赖")

    if "accepted_total" in sub.columns and mean_of(sub, "accepted_total") >= 0.4:
        tags.append("活动敏感型")

    return tags[:6]


def build_persona(
    sub: pd.DataFrame,
    cluster: dict[str, Any],
    overall: pd.DataFrame,
    revenue_total: float,
) -> dict[str, Any]:
    """单个客群的完整画像。"""
    avg_age = mean_of(sub, "age")
    avg_income = mean_of(sub, "income")
    avg_spend = mean_of(sub, "total_spend")
    avg_freq = mean_of(sub, "purchase_freq")
    avg_recency = mean_of(sub, "recency")
    order_value = avg_spend / avg_freq if avg_freq else 0.0

    cats = categories_of()
    categories = [{"name": label, "value": clean(mean_of(sub, field))} for field, label in cats.items()]
    cat_total = sum(c["value"] or 0 for c in categories) or 1.0
    for c in categories:
        c["ratio"] = pct(c["value"], cat_total)
    categories.sort(key=lambda c: -(c["value"] or 0))

    chans = channels_of()
    ch_total = sum(sum_of(sub, f) for f in chans) or 1.0
    channels = [
        {"name": label, "value": clean(sum_of(sub, field) / ch_total), "count": clean(sum_of(sub, field))}
        for field, label in chans.items()
    ]
    channels.sort(key=lambda c: -(c["value"] or 0))

    tags = _tags(sub, overall)
    headline = " · ".join(tags[:3]) if tags else "数据维度有限，标签待补充"

    education = _value_counts(sub, "education", zh_education)
    marital = _value_counts(sub, "marital_status", zh_marital)
    age_group = _value_counts(sub, "age_group")

    parts = []
    if "age" in sub.columns:
        parts.append(f"平均 {avg_age:.0f} 岁")
    if len(education):
        parts.append(f"{education.index[0]}学历为主")
    if "income" in sub.columns:
        parts.append(f"平均收入约 {avg_income:,.0f}")
    if "total_spend" in sub.columns:
        parts.append(f"累计消费 {avg_spend:,.0f}")
    if "purchase_freq" in sub.columns:
        parts.append(f"购买 {avg_freq:.0f} 次")
    if "recency" in sub.columns:
        parts.append(f"最近一次在 {avg_recency:.0f} 天前")
    if categories:
        parts.append(f"最偏好{categories[0]['name']}")
    summary = "，".join(parts) + "。" if parts else "该客群可用字段较少，建议补充客户级明细。"

    persona = {
        "cluster": cluster["cluster"],
        "name": cluster["name"],
        "status": cluster["status"],
        "rank": cluster["rank"],
        "size": int(len(sub)),
        "ratio": pct(len(sub), len(overall)),
        "revenue": clean(float(sub["total_spend"].sum())) if "total_spend" in sub.columns else 0.0,
        "revenue_ratio": pct(float(sub["total_spend"].sum()), revenue_total) if "total_spend" in sub.columns else 0.0,
        "headline": headline,
        "tags": tags,
        "summary": summary,
        "demographics": {
            "avg_age": clean(avg_age),
            "age_group": _share(age_group)[:3],
            "education": _share(education)[:3],
            "marital": _share(marital)[:3],
            "gender": _share(_value_counts(sub, "gender"))[:3],
            "children_rate": clean(num(sub, "children").gt(0).mean()) if "children" in sub.columns else None,
        },
        "value": {
            "avg_income": clean(avg_income),
            "avg_spend": clean(avg_spend),
            "avg_freq": clean(avg_freq),
            "avg_order_value": clean(order_value),
            "avg_recency": clean(avg_recency),
            "avg_tenure_days": clean(mean_of(sub, "tenure_days")),
        },
        "categories": categories,
        "channels": channels,
        "behavior": {
            "discount_dependence": clean(mean_of(sub, "num_deals") / max(avg_freq, 1e-6)),
            "web_visits_month": clean(mean_of(sub, "web_visits_month")),
            "accepted_rate": clean(mean_of(sub, "accepted_total") / 5),
            "response_rate": clean(mean_of(sub, "response")) if "response" in sub.columns else None,
            "complain_rate": clean(mean_of(sub, "complain")) if "complain" in sub.columns else None,
        },
    }
    return persona


def build_all(
    cluster_table: pd.DataFrame, clusters: list[dict], overall: pd.DataFrame
) -> list[dict[str, Any]]:
    revenue_total = float(overall["total_spend"].sum()) if "total_spend" in overall.columns else 0.0
    personas = []
    for cluster in clusters:
        sub = cluster_table[cluster_table["cluster"] == cluster["cluster"]]
        if sub.empty:
            continue
        personas.append(build_persona(sub, cluster, overall, revenue_total))
    personas.sort(key=lambda p: p["rank"])
    return personas
