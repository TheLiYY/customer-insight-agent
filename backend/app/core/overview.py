"""总览看板数据。所有图表都输出 ECharts 能直接吃的结构。"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .config import CATEGORY_FIELDS, CHANNEL_FIELDS
from .utils import clean, pct

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
        "response_rate": clean(float(df["response"].mean())),
        "response_count": int(df["response"].sum()),
        "avg_income": clean(float(df["income"].mean())),
        "avg_spend": clean(float(df["total_spend"].mean())),
        "avg_freq": clean(float(df["purchase_freq"].mean())),
        "avg_recency": clean(float(df["recency"].mean())),
        "total_revenue": clean(float(df["total_spend"].sum())),
        "dormant_rate": clean(float((df["recency"] > 75).mean())),
        "dormant_count": int((df["recency"] > 75).sum()),
        "complain_rate": clean(float(df["complain"].mean())),
        "discount_dependence": clean(float(df["num_deals"].sum()) / max(float(df["purchase_freq"].sum()), 1)),
    }


def _counts(series: pd.Series, order: list[str] | None = None) -> list[dict]:
    vc = series.value_counts()
    if order:
        vc = vc.reindex([o for o in order if o in vc.index])
    total = float(vc.sum()) or 1.0
    return [{"name": str(k), "value": int(v), "ratio": pct(v, total)} for k, v in vc.items()]


def age_distribution(df: pd.DataFrame) -> list[dict]:
    return _counts(df["age_group"], ["18-30", "31-40", "41-50", "51-60", "60+"])


def education_distribution(df: pd.DataFrame) -> list[dict]:
    return _counts(df["education"])


def marital_distribution(df: pd.DataFrame) -> list[dict]:
    label = {
        "Single": "单身",
        "Married": "已婚",
        "Together": "同居",
        "Divorced": "离异",
        "Widow": "丧偶",
    }
    vc = df["marital_status"].map(lambda x: label.get(x, x)).value_counts()
    total = float(vc.sum()) or 1.0
    return [{"name": str(k), "value": int(v), "ratio": pct(v, total)} for k, v in vc.items()]


def income_buckets(df: pd.DataFrame, bins: int = 6) -> list[dict]:
    values = df["income"].dropna()
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
    rows = []
    for field, label in CATEGORY_FIELDS.items():
        rows.append({"name": label, "value": clean(float(df[field].sum()))})
    total = sum(r["value"] or 0 for r in rows) or 1.0
    for r in rows:
        r["ratio"] = pct(r["value"], total)
    rows.sort(key=lambda r: -(r["value"] or 0))
    return rows


def channel_mix(df: pd.DataFrame) -> list[dict]:
    rows = []
    for field, label in CHANNEL_FIELDS.items():
        rows.append({"name": label, "value": clean(float(df[field].sum()))})
    total = sum(r["value"] or 0 for r in rows) or 1.0
    for r in rows:
        r["ratio"] = pct(r["value"], total)
    return rows


def response_by(df: pd.DataFrame, field: str) -> list[dict]:
    """分组的响应率对比：谁最容易被打动。"""
    grouped = df.groupby(field)["response"].agg(["mean", "count"]).reset_index()
    grouped = grouped[grouped["count"] >= 10]
    grouped = grouped.sort_values("mean", ascending=False)
    return [
        {
            "name": str(row[field]),
            "value": clean(float(row["mean"])),
            "count": int(row["count"]),
        }
        for _, row in grouped.iterrows()
    ]


def histogram(df: pd.DataFrame, field: str, bins: int = 12, label: str = "") -> list[dict]:
    values = df[field].dropna()
    if values.empty:
        return []
    counts, edges = np.histogram(values, bins=bins)
    rows = []
    for i, c in enumerate(counts):
        rows.append(
            {
                "name": f"{edges[i]:.0f}~{edges[i + 1]:.0f}",
                "value": int(c),
                "label": label,
            }
        )
    return rows


def correlation(df: pd.DataFrame) -> dict:
    sub = df[list(CORR_FIELDS.keys())].astype(float)
    corr = sub.corr().fillna(0)
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
        "income": income_buckets(df),
        "category": category_spend(df),
        "channel": channel_mix(df),
        "response_by_age": response_by(df, "age_group"),
        "response_by_education": response_by(df, "education"),
        "spend_hist": histogram(df, "total_spend", 10),
        "recency_hist": histogram(df, "recency", 10),
        "correlation": correlation(df),
    }
