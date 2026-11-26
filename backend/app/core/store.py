"""分析结果仓库：所有重计算结果只算一次，API 层直接取。

数据量只有几百到几千行，全部放在内存里最快；换成百万级数据时把这里换成
离线跑批 + Parquet/DuckDB 即可，接口层不用动。
"""
from __future__ import annotations

import threading
import time
from typing import Any

import pandas as pd

from .config import CLUSTER_FEATURES, settings
from . import association, campaign, clustering, dataset, insights, overview, persona, propensity, rfm


class Store:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started_at = time.time()
        self._df: pd.DataFrame | None = None
        self._rfm: pd.DataFrame | None = None
        self._cluster: dict[str, Any] | None = None
        self._personas: list[dict] | None = None
        self._prop: dict[str, Any] | None = None
        self._rules: list[dict] | None = None
        self._overview: dict[str, Any] | None = None
        self._penetration: list[dict] | None = None
        self._insights: dict[str, Any] | None = None

    # ---------- 基础数据 ----------
    @property
    def df(self) -> pd.DataFrame:
        if self._df is None:
            self._df = dataset.load_customers()
        return self._df

    @property
    def meta(self) -> dict:
        return dataset.load_meta()

    # ---------- RFM ----------
    @property
    def rfm(self) -> pd.DataFrame:
        if self._rfm is None:
            self._rfm = rfm.build_rfm(self.df)
        return self._rfm

    @property
    def segment_summary(self) -> list[dict]:
        return rfm.segment_summary(self.rfm)

    # ---------- 聚类与画像 ----------
    @property
    def cluster(self) -> dict[str, Any]:
        if self._cluster is None:
            self._cluster = clustering.run_clustering(
                self.rfm, CLUSTER_FEATURES, k=settings.cluster_k, seed=settings.random_state
            )
        return self._cluster

    @property
    def cluster_table(self) -> pd.DataFrame:
        return self.cluster["table"]

    @property
    def personas(self) -> list[dict]:
        if self._personas is None:
            self._personas = persona.build_all(self.cluster_table, self.cluster["clusters"], self.df)
        return self._personas

    # ---------- 响应预测 ----------
    @property
    def propensity(self) -> dict[str, Any]:
        if self._prop is None:
            self._prop = propensity.train(self.df, seed=settings.random_state)
        return self._prop

    @property
    def scores(self) -> pd.DataFrame:
        return self.propensity["table"]

    # ---------- 关联规则 ----------
    @property
    def rules(self) -> list[dict]:
        if self._rules is None:
            self._rules = association.mine_rules(self.df)
        return self._rules

    @property
    def penetration(self) -> list[dict]:
        if self._penetration is None:
            self._penetration = association.penetration(self.df)
        return self._penetration

    # ---------- 总览 ----------
    @property
    def overview(self) -> dict[str, Any]:
        if self._overview is None:
            self._overview = overview.build_overview(self.df)
        return self._overview

    # ---------- 自动结论 ----------
    @property
    def insights(self) -> dict[str, Any]:
        if self._insights is None:
            self._insights = insights.build_insights(
                self.df,
                self.overview["kpis"],
                self.segment_summary,
                self.personas,
                self.propensity,
                self.rules,
                self.penetration,
            )
        return self._insights

    # ---------- 组合视图 ----------
    @property
    def enriched(self) -> pd.DataFrame:
        """明细表 + RFM 客群 + 聚类客群 + 转化概率。前端表格与导出都用它。"""
        table = self.cluster_table.merge(
            self.scores[["customer_id", "prob", "decile", "rank"]],
            on="customer_id",
            how="left",
        )
        return table

    def plan(self, segment: str, budget: float, cost_per_contact: float, discount: float) -> dict:
        return campaign.build_plan(
            self.cluster_table,
            self.scores,
            segment_field="cluster_name",
            segment=segment,
            budget=budget,
            cost_per_contact=cost_per_contact,
            discount=discount,
            rules=self.rules,
        )

    def plan_rfm(self, segment: str, budget: float, cost_per_contact: float, discount: float) -> dict:
        return campaign.build_plan(
            self.cluster_table,
            self.scores,
            segment_field="rfm_segment",
            segment=segment,
            budget=budget,
            cost_per_contact=cost_per_contact,
            discount=discount,
            rules=self.rules,
        )

    def status(self) -> dict:
        return {
            "customers": int(len(self.df)),
            "segments": len(self.segment_summary),
            "clusters": len(self.personas),
            "rules": len(self.rules),
            "uptime_seconds": round(time.time() - self._started_at, 1),
        }

    def reload(self) -> None:
        """数据更新后重新计算（留的钩子，方便未来接定时任务）。"""
        with self._lock:
            dataset.load_customers.cache_clear()
            self._df = None
            self._rfm = None
            self._cluster = None
            self._personas = None
            self._prop = None
            self._rules = None
            self._overview = None
            self._penetration = None
            self._insights = None


store = Store()
