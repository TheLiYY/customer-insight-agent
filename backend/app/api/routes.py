"""API 路由：把 store 里的分析结果暴露成 REST 接口。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..core.config import CATEGORY_FIELDS, settings
from ..core.store import store
from ..core.utils import clean

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------- 基础信息
@router.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.version,
        "llm_enabled": settings.llm_enabled,
        **store.status(),
    }


@router.get("/dataset")
def dataset_info() -> dict[str, Any]:
    meta = store.meta
    return {
        "source": meta.get("source", ""),
        "excel": meta.get("excel", ""),
        "rows": meta.get("rows", len(store.df)),
        "columns": meta.get("columns", len(store.df.columns)),
        "fields": meta.get("fields", []),
        "missing_cells": meta.get("missing_cells", 0),
        "duplicate_rows": meta.get("duplicate_rows", 0),
    }


# ---------------------------------------------------------------- 总览
@router.get("/overview")
def get_overview() -> dict[str, Any]:
    return store.overview


# ---------------------------------------------------------------- 自动结论
@router.get("/insights")
def get_insights(severity: str | None = None, category: str | None = None) -> dict[str, Any]:
    """自动分析结论：把统计结果翻译成结论 + 证据 + 建议动作。

    可选按严重程度（opportunity/risk/insight）与类别过滤。
    """
    data = store.insights
    items = data["insights"]
    if severity:
        items = [i for i in items if i["severity"] == severity]
    if category:
        items = [i for i in items if i["category"] == category]
    return {
        **data,
        "insights": items,
        "counts": {
            **data["counts"],
            "filtered": len(items),
        },
    }


# ---------------------------------------------------------------- RFM 分层
@router.get("/segments")
def get_segments() -> dict[str, Any]:
    from ..core import rfm as rfm_mod

    return {
        "segments": store.segment_summary,
        "matrix": rfm_mod.segment_matrix(store.rfm),
        "treemap": rfm_mod.segment_treemap(store.rfm),
        "score_distribution": {
            "R": store.rfm["r_score"].value_counts().sort_index().to_dict(),
            "F": store.rfm["f_score"].value_counts().sort_index().to_dict(),
            "M": store.rfm["m_score"].value_counts().sort_index().to_dict(),
        },
    }


# ---------------------------------------------------------------- 聚类画像
@router.get("/personas")
def get_personas() -> dict[str, Any]:
    return {
        "k": store.cluster["k"],
        "silhouette": store.cluster["silhouette"],
        "inertia": store.cluster["inertia"],
        "features": store.cluster["features"],
        "clusters": store.cluster["clusters"],
        "personas": store.personas,
    }


@router.get("/personas/{name}")
def get_persona(name: str) -> dict[str, Any]:
    for p in store.personas:
        if p["name"] == name:
            return p
    raise HTTPException(status_code=404, detail=f"客群 {name} 不存在")


@router.get("/clusters/elbow")
def get_elbow(k_max: int = Query(8, ge=2, le=10)) -> dict[str, Any]:
    from ..core import clustering

    points = clustering.elbow_curve(store.rfm, store.cluster["features"], list(range(2, k_max + 1)))
    return {"points": points}


# ---------------------------------------------------------------- 响应预测
@router.get("/propensity")
def get_propensity() -> dict[str, Any]:
    prop = store.propensity
    enriched = store.enriched.sort_values("prob", ascending=False)
    top = enriched.head(50)[
        ["customer_id", "cluster_name", "rfm_segment", "prob", "total_spend", "purchase_freq", "recency"]
    ].to_dict(orient="records")
    for row in top:
        row["prob"] = clean(row["prob"])
    return {
        "metrics": prop["train_metrics"],
        "full_metrics": prop["full_metrics"],
        "coefs": prop["coefs"],
        "lift": prop["lift"],
        "base_rate": prop["base_rate"],
        "threshold": prop["threshold"],
        "score_hist": _score_hist(enriched["prob"]),
        "top_customers": top,
    }


def _score_hist(series, bins: int = 10) -> list[dict]:
    import numpy as np

    values = series.dropna().to_numpy()
    if len(values) == 0:
        return []
    counts, edges = np.histogram(values, bins=bins, range=(0, 1))
    return [
        {"name": f"{edges[i]:.1f}-{edges[i + 1]:.1f}", "value": int(c)}
        for i, c in enumerate(counts)
    ]


# ---------------------------------------------------------------- 关联规则
@router.get("/association")
def get_association() -> dict[str, Any]:
    from ..core import association

    return {
        "rules": store.rules,
        "penetration": store.penetration,
        "basket_size": association.basket_size(store.df),
    }


# ---------------------------------------------------------------- 客户明细
@router.get("/customers")
def get_customers(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    segment: str | None = None,
    cluster: str | None = None,
    keyword: str | None = None,
    sort: str = "prob",
    order: str = "desc",
) -> dict[str, Any]:
    table = store.enriched.copy()
    if segment:
        table = table[table["rfm_segment"] == segment]
    if cluster:
        table = table[table["cluster_name"] == cluster]
    if keyword:
        kw = keyword.strip().lower()
        table = table[
            table["customer_id"].astype(str).str.lower().str.contains(kw, na=False)
            | table["education"].astype(str).str.lower().str.contains(kw, na=False)
            | table["marital_status"].astype(str).str.lower().str.contains(kw, na=False)
        ]
    if sort in table.columns:
        table = table.sort_values(sort, ascending=(order != "desc"))
    total = len(table)
    start = (page - 1) * size
    page_rows = table.iloc[start : start + size]

    columns = [
        "customer_id",
        "age",
        "age_group",
        "education",
        "marital_status",
        "income",
        "total_spend",
        "purchase_freq",
        "recency",
        "num_web",
        "num_store",
        "num_catalog",
        "rfm_segment",
        "cluster_name",
        "prob",
    ]
    rows = []
    for record in page_rows[columns].to_dict(orient="records"):
        rows.append({k: clean(v) for k, v in record.items()})
    return {"total": total, "page": page, "size": size, "rows": rows}


@router.get("/customers/{customer_id}")
def get_customer(customer_id: str) -> dict[str, Any]:
    table = store.enriched
    hit = table[table["customer_id"] == customer_id]
    if hit.empty:
        raise HTTPException(status_code=404, detail="客户不存在")
    row = hit.iloc[0].to_dict()
    row = {k: clean(v) for k, v in row.items()}
    row["categories"] = [
        {"name": label, "value": clean(row.get(field))} for field, label in CATEGORY_FIELDS.items()
    ]
    return row


# ---------------------------------------------------------------- 营销方案
class PlanRequest(BaseModel):
    segment: str = Field(..., description="客群名称")
    by: str = Field("cluster", description="cluster 或 rfm")
    budget: float = Field(20000, ge=0)
    cost_per_contact: float = Field(4, gt=0)
    discount: float = Field(0.12, ge=0, le=1)


@router.post("/campaign/plan")
def create_plan(req: PlanRequest) -> dict[str, Any]:
    if req.by == "rfm":
        plan = store.plan_rfm(req.segment, req.budget, req.cost_per_contact, req.discount)
    else:
        plan = store.plan(req.segment, req.budget, req.cost_per_contact, req.discount)
    if not plan.get("ok"):
        raise HTTPException(status_code=404, detail=plan.get("message", "生成失败"))
    return plan


@router.get("/campaign/options")
def campaign_options() -> dict[str, Any]:
    return {
        "clusters": [{"name": p["name"], "size": p["size"], "headline": p["headline"]} for p in store.personas],
        "rfm": [{"name": s["name"], "size": s["count"]} for s in store.segment_summary],
    }
