"""总览看板数据。所有图表都输出 ECharts 能直接吃的结构。

换数据注意：任何一个维度缺字段时对应函数返回 []，前端不画这张图，
不会因为「这份数据没有学历字段」而整页报错。
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .config import zh_education, zh_marital
from .dataset import channels as channels_of
from .dataset import categories as categories_of
from .utils import clean, mean_of, num, pct, sum_of

CORR_FIELDS = {
    "income": "收入",
    "total_spend": "消费额",
    "purchase_freq": "频次",
    "recency": "最近间隔",
    "num_deals": "折扣次数",
    "web_visits_month": "月访问",
    "accepted_total": "活动接受",
    "age": "年龄",
}


def kpis(df: pd.DataFrame) -> dict[str, Any]:
    total = len(df)
    return {
        "customers": total,
        "response_rate": clean(mean_of(df, "response")) if "response" in df.columns else None,
        "response_count": int(num(df, "response").sum()) if "response" in df.columns else None,
        "avg_income": clean(mean_of(df, "income")) if "income" in df.columns else None,
        "avg_spend": clean(mean_of(df, "total_spend")),
        "avg_freq": clean(mean_of(df, "purchase_freq")),
        "avg_recency": clean(mean_of(df, "recency")),
        "total_revenue": clean(sum_of(df, "total_spend")),
        "dormant_rate": clean(float(num(df, "recency").gt(75).mean())) if "recency" in df.columns else None,
        "dormant_count": int(num(df, "recency").gt(75).sum()) if "recency" in df.columns else None,
        "complain_rate": clean(mean_of(df, "complain")) if "complain" in df.columns else None,
        "discount_dependence": clean(
            sum_of(df, "num_deals") / max(sum_of(df, "purchase_freq"), 1)
        ),
    }


def _counts(series: pd.Series, order: list[str] | None = None) -> list[dict]:
    vc = series.dropna().astype(str).str.strip()
    vc = vc[vc.str.len() > 0].value_counts()
    if order:
        vc = vc.reindex([o for o in order if o in vc.index])
    total = float(vc.sum()) or 1.0
    return [{"name": str(k), "value": int(v), "ratio": pct(v, total)} for k, v in vc.items()]


def age_distribution(df: pd.DataFrame) -> list[dict]:
    if "age_group" not in df.columns:
        return []
    return _counts(df["age_group"], ["18-30", "31-40", "41-50", "51-60", "60+"])


def education_distribution(df: pd.DataFrame) -> list[dict]:
    if "education" not in df.columns:
        return []
    return _counts(df["education"].map(zh_education))


def marital_distribution(df: pd.DataFrame) -> list[dict]:
    if "marital_status" not in df.columns:
        return []
    return _counts(df["marital_status"].map(zh_marital))


def gender_distribution(df: pd.DataFrame) -> list[dict]:
    if "gender" not in df.columns:
        return []
    return _counts(df["gender"])


def income_buckets(df: pd.DataFrame, bins: int = 6) -> list[dict]:
    if "income" not in df.columns:
        return []
    values = pd.to_numeric(df["income"], errors="coerce").dropna()
    if values.empty:
        return []
    edges = np.quantile(values, np.linspace(0, 1, bins + 1))
    edges = np.unique(np.round(edges, 2))
    if len(edges) < 2:
        return []
    cut = pd.cut(values, bins=edges, include_lowest=True)
    vc = cut.value_counts().sort_index()
    total = float(vc.sum()) or 1.0
    rows = []
    for interval, v in vc.items():
        label = f"{interval.left / 1000:.0f}k-{interval.right / 1000:.0f}k"
        rows.append({"name": label, "value": int(v), "ratio": pct(v, total)})
    return rows


def category_spend(df: pd.DataFrame) -> list[dict]:
    rows = [
        {"name": label, "value": clean(sum_of(df, field))}
        for field, label in categories_of().items()
    ]
    if not rows:
        return []
    total = sum(r["value"] or 0 for r in rows) or 1.0
    for r in rows:
        r["ratio"] = pct(r["value"], total)
    rows.sort(key=lambda r: -(r["value"] or 0))
    return rows


def channel_mix(df: pd.DataFrame) -> list[dict]:
    rows = [
        {"name": label, "value": clean(sum_of(df, field))}
        for field, label in channels_of().items()
    ]
    if not rows:
        return []
    total = sum(r["value"] or 0 for r in rows) or 1.0
    for r in rows:
        r["ratio"] = pct(r["value"], total)
    rows.sort(key=lambda r: -(r["value"] or 0))
    return rows


def response_by(df: pd.DataFrame, field: str, labeler=None) -> list[dict]:
    """分组的响应率对比：谁最容易被打动。labeler 用于把英文取值转成中文展示。"""
    if field not in df.columns or "response" not in df.columns:
        return []
    grouped = df.groupby(field)["response"].agg(["mean", "count"]).reset_index()
    grouped = grouped[grouped["count"] >= 10]
    grouped = grouped.sort_values("mean", ascending=False)
    return [
        {
            "name": labeler(str(row[field])) if labeler else str(row[field]),
            "value": clean(float(row["mean"])),
            "count": int(row["count"]),
        }
        for _, row in grouped.iterrows()
    ]


def histogram(df: pd.DataFrame, field: str, bins: int = 12, label: str = "") -> list[dict]:
    if field not in df.columns:
        return []
    values = pd.to_numeric(df[field], errors="coerce").dropna()
    if values.empty:
        return []
    counts, edges = np.histogram(values, bins=bins)
    return [
        {"name": f"{edges[i]:.0f}~{edges[i + 1]:.0f}", "value": int(c), "label": label}
        for i, c in enumerate(counts)
    ]


def correlation(df: pd.DataFrame) -> dict:
    """相关性热力图。只保留实际存在且不是常量的字段。"""
    usable = [c for c in CORR_FIELDS if c in df.columns and num(df, c).nunique() > 1]
    if len(usable) < 2:
        return {"x": [], "y": [], "values": []}
    corr = df[usable].astype(float).corr().fillna(0)
    return {
        "x": [CORR_FIELDS[c] for c in corr.columns],
        "y": [CORR_FIELDS[c] for c in corr.index],
        "values": [
            [clean(corr.iloc[i, j]) for j in range(len(corr.columns))]
            for i in range(len(corr.index))
        ],
    }


def build_overview(df: pd.DataFrame) -> dict[str, Any]:
    return {
        "kpis": kpis(df),
        "age": age_distribution(df),
        "education": education_distribution(df),
        "marital": marital_distribution(df),
        "gender": gender_distribution(df),
        "income": income_buckets(df),
        "category": category_spend(df),
        "channel": channel_mix(df),
        "response_by_age": response_by(df, "age_group"),
        "response_by_education": response_by(df, "education", zh_education),
        "spend_hist": histogram(df, "total_spend", 10),
        "recency_hist": histogram(df, "recency", 10),
        "correlation": correlation(df),
    }
