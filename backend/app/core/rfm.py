"""RFM 模型：用最近购买、购买频次、消费金额三个维度给客户打分并分层。

打分方式：三分位数（各 5 档，5 分最好），再按「高/低」组合归入 8 个经典客群。
"""
from __future__ import annotations

import pandas as pd

from .dataset import categories as categories_of
from .utils import clean, mean_of, pct, quantile_score

# 8 个 RFM 客群：key = (R是否高, F是否高, M是否高)
SEGMENTS: dict[str, dict] = {
    "重要价值客户": {
        "rule": (True, True, True),
        "priority": 1,
        "desc": "最近买过、买得又多又贵，是企业的现金牛。",
        "action": "VIP 专属权益 + 新品优先购；不要用大额折扣，重点是「被重视」的尊享感。",
    },
    "重要保持客户": {
        "rule": (False, True, True),
        "priority": 2,
        "desc": "历史贡献高，但最近一段时间没动静，有流失风险。",
        "action": "一对一回访 + 高价值唤回券，7 天内必须触达，晚了就真的走了。",
    },
    "重要发展客户": {
        "rule": (True, False, True),
        "priority": 3,
        "desc": "客单价高但来得不勤，属于「贵客但低频」。",
        "action": "提升购买频次：订阅制、品类扩展券、会员日提醒，把一次买变成常买。",
    },
    "重要挽留客户": {
        "rule": (False, False, True),
        "priority": 4,
        "desc": "曾经的大客户，现在又少来又久未到店。",
        "action": "强唤回：专属客服电话 + 限时大额权益，同时排查是否有服务或售后问题。",
    },
    "一般价值客户": {
        "rule": (True, True, False),
        "priority": 5,
        "desc": "活跃且高频，但客单价偏低。",
        "action": "向上销售：满减门槛、组合套装、加价购，把客单价拉起来。",
    },
    "一般保持客户": {
        "rule": (False, True, False),
        "priority": 6,
        "desc": "买得勤但金额小，且近期活跃度下降。",
        "action": "低成本自动化触达（短信/站内信）+ 小额优惠券，控制 ROI。",
    },
    "一般发展客户": {
        "rule": (True, False, False),
        "priority": 7,
        "desc": "最近有交互，但频次和金额都不高，可培养。",
        "action": "新手引导 + 首单/二单激励，先建立购买习惯再谈客单价。",
    },
    "一般挽留客户": {
        "rule": (False, False, False),
        "priority": 8,
        "desc": "三项指标全面走低，基本处于沉睡状态。",
        "action": "批量低成本唤醒或不投；把预算省下来给高潜人群。",
    },
}


def _segment_of(r_high: bool, f_high: bool, m_high: bool) -> str:
    for name, meta in SEGMENTS.items():
        if meta["rule"] == (r_high, f_high, m_high):
            return name
    return "一般挽留客户"


def build_rfm(df: pd.DataFrame) -> pd.DataFrame:
    """返回带 r/f/m 分数与客群标签的新表。"""
    out = df.copy()
    out["r_score"] = quantile_score(out["recency"], higher_is_better=False)
    out["f_score"] = quantile_score(out["purchase_freq"], higher_is_better=True)
    out["m_score"] = quantile_score(out["total_spend"], higher_is_better=True)
    out["rfm_score"] = out["r_score"].astype(str) + out["f_score"].astype(str) + out["m_score"].astype(str)
    out["rfm_segment"] = [
        _segment_of(r >= 3, f >= 3, m >= 3)
        for r, f, m in zip(out["r_score"], out["f_score"], out["m_score"])
    ]
    out["rfm_segment_priority"] = out["rfm_segment"].map(lambda s: SEGMENTS[s]["priority"])
    return out


def segment_summary(rfm: pd.DataFrame) -> list[dict]:
    """8 个客群的数量、占比、贡献与营销含义。"""
    total = len(rfm)
    revenue = float(rfm["total_spend"].sum())
    rows: list[dict] = []
    for name, meta in SEGMENTS.items():
        sub = rfm[rfm["rfm_segment"] == name]
        if sub.empty:
            continue
        rows.append(
            {
                "name": name,
                "priority": meta["priority"],
                "desc": meta["desc"],
                "action": meta["action"],
                "count": int(len(sub)),
                "ratio": pct(len(sub), total),
                "revenue": clean(float(sub["total_spend"].sum())),
                "revenue_ratio": pct(sub["total_spend"].sum(), revenue),
                "avg_r": clean(sub["r_score"].mean()),
                "avg_f": clean(sub["f_score"].mean()),
                "avg_m": clean(sub["m_score"].mean()),
                "avg_recency": clean(sub["recency"].mean()),
                "avg_freq": clean(sub["purchase_freq"].mean()),
                "avg_spend": clean(sub["total_spend"].mean()),
                "avg_income": clean(mean_of(sub, "income")),
                "avg_age": clean(mean_of(sub, "age")),
                "response_rate": clean(mean_of(sub, "response")),
                "complain_rate": clean(mean_of(sub, "complain")),
            }
        )
    rows.sort(key=lambda x: x["priority"])
    return rows


def segment_matrix(rfm: pd.DataFrame) -> dict:
    """F-M 交叉矩阵（行 = 频次档，列 = 金额档），供前端画热力图。"""
    matrix = pd.crosstab(rfm["f_score"], rfm["m_score"])
    return {
        "rows": [f"F{int(i)}" for i in matrix.index],
        "cols": [f"M{int(c)}" for c in matrix.columns],
        "values": [[int(v) for v in row] for row in matrix.values],
    }


def segment_treemap(rfm: pd.DataFrame) -> list[dict]:
    """腾图（treemap）数据：面积 = 人数，用于一眼看清结构。"""
    return [
        {"name": r["name"], "value": r["count"], "revenue": r["revenue"]}
        for r in segment_summary(rfm)
    ]


def top_segment_categories(rfm: pd.DataFrame, segment: str, limit: int = 3) -> list[dict]:
    """给定客群的品类偏好（按人均消费额排序）。品类随数据变化，没有品类字段就返回空。"""
    sub = rfm[rfm["rfm_segment"] == segment]
    if sub.empty:
        return []
    items = []
    for field, label in categories_of().items():
        items.append({"name": label, "value": clean(mean_of(sub, field))})
    if not items:
        return []
    items.sort(key=lambda x: -(x["value"] or 0))
    total = sum(v["value"] or 0 for v in items) or 1
    for it in items:
        it["ratio"] = pct(it["value"], total)
    return items[:limit]
