"""KMeans 客群聚类（基于 scikit-learn）。

关键设计：
1. 先用 StandardScaler 标准化——收入是几万、频次是十几，不标准化的话距离会被收入完全主导；
2. KMeans(n_init=10) 内置 k-means++ 多次初始化，取簇内平方和最小的一次；
3. 用轮廓系数（silhouette）评估「簇内紧、簇间远」，取值 -1~1，越大越好；
4. 聚类编号本身没有业务含义，这里按「综合价值得分」重新排序命名，
   保证每次跑出来的「核心高价值客群」都还是最值钱的那一群。
"""
from __future__ import annotations

import warnings
from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score as sk_silhouette
from sklearn.preprocessing import StandardScaler

from .utils import clean

# Windows + MKL 下 sklearn 会对 KMeans 抛一条与结果无关的「内存泄漏」提示，
# 我们的数据只有一两千行、跑几百毫秒，这条警告纯属噪音，直接屏蔽。
warnings.filterwarnings(
    "ignore",
    message="KMeans is known to have a memory leak on Windows with MKL",
    category=UserWarning,
)

# 按综合得分排名给出的客群名称（k 大于 6 时自动补编号）
NAME_POOL = [
    "核心高价值客群",
    "稳定贡献客群",
    "潜力成长客群",
    "长尾基础客群",
    "边缘低频客群",
    "待观察客群",
]


def fit_kmeans(
    matrix: np.ndarray, k: int, seed: int = 42, n_init: int = 10
) -> tuple[KMeans, StandardScaler, np.ndarray, float]:
    """标准化 → 拟合 KMeans，返回 (模型, 标准化器, 标准化后的矩阵, 轮廓系数)。"""
    scaler = StandardScaler()
    scaled = scaler.fit_transform(matrix)
    model = KMeans(n_clusters=k, n_init=n_init, random_state=seed)
    labels = model.fit_predict(scaled)
    # 大样本下轮廓系数是 O(n²)，抽样计算即可，结果稳定且快
    sample = min(len(scaled), 1500)
    sil = float(sk_silhouette(scaled, labels, sample_size=sample, random_state=seed))
    return model, scaler, scaled, sil


def run_clustering(
    df: pd.DataFrame, features: list[str], k: int = 4, seed: int = 42
) -> dict[str, Any]:
    """对给定特征做 KMeans，并把人话讲得通的客群名、状态、规模算出来。"""
    k = max(2, min(k, len(df) // 20 or 2))
    matrix = df[features].to_numpy(dtype=float)
    model, scaler, scaled, sil = fit_kmeans(matrix, k=k, seed=seed)
    labels = model.labels_

    work = df.copy()
    work["cluster"] = labels.astype(int)

    # 簇级画像统计
    stats = (
        work.groupby("cluster")
        .agg(
            size=("customer_id", "count"),
            avg_spend=("total_spend", "mean"),
            avg_freq=("purchase_freq", "mean"),
            avg_recency=("recency", "mean"),
            avg_income=("income", "mean"),
            avg_age=("age", "mean"),
            response_rate=("response", "mean"),
        )
        .reset_index()
    )

    # 综合得分：花得多、来得勤、最近买过 = 高价值
    def z(col: str) -> pd.Series:
        v = stats[col]
        return (v - v.mean()) / (v.std() or 1)

    stats["score"] = (
        0.5 * z("avg_spend") + 0.3 * z("avg_freq") - 0.2 * z("avg_recency")
    ).round(4)
    stats = stats.sort_values("score", ascending=False).reset_index(drop=True)

    naming = {}
    for rank, row in stats.iterrows():
        base = NAME_POOL[rank] if rank < len(NAME_POOL) else f"客群{rank + 1}"
        naming[int(row["cluster"])] = base

    recency_line = float(df["recency"].mean()) * 1.15
    clusters = []
    for rank, row in stats.iterrows():
        cid = int(row["cluster"])
        status = "活跃" if row["avg_recency"] <= recency_line else "沉默预警"
        clusters.append(
            {
                "cluster": cid,
                "name": naming[cid],
                "rank": rank + 1,
                "status": status,
                "size": int(row["size"]),
                "ratio": clean(row["size"] / len(work)),
                "avg_spend": clean(row["avg_spend"]),
                "avg_freq": clean(row["avg_freq"]),
                "avg_recency": clean(row["avg_recency"]),
                "avg_income": clean(row["avg_income"]),
                "avg_age": clean(row["avg_age"]),
                "response_rate": clean(row["response_rate"]),
            }
        )

    work["cluster_name"] = work["cluster"].map(naming)

    # 把标准化中心还原成原始量纲，便于解释「这个簇典型客户长什么样」
    centers_raw = scaler.inverse_transform(model.cluster_centers_)

    return {
        "labels": work["cluster_name"],
        "table": work,
        "k": k,
        "inertia": clean(model.inertia_),
        "silhouette": clean(sil),
        "features": features,
        "centers_raw": clean(np.round(centers_raw, 3).tolist()),
        "clusters": clusters,
    }


def elbow_curve(
    df: pd.DataFrame, features: list[str], ks: list[int], seed: int = 42
) -> list[dict]:
    """肘部法则数据：k 越大惯性越小，找「下降明显变缓」的拐点。"""
    matrix = df[features].to_numpy(dtype=float)
    points = []
    for k in ks:
        if k < 2 or k >= len(df) // 10:
            continue
        model, _, _, sil = fit_kmeans(matrix, k=k, seed=seed)
        points.append(
            {
                "k": k,
                "inertia": clean(model.inertia_),
                "silhouette": clean(sil),
            }
        )
    return points
