"""KMeans 聚类（纯 numpy 实现，不依赖 scikit-learn）。

为什么自己写：
1. 部署轻量，只要 numpy 就能跑；
2. 每一步都能讲清楚——初始化、分配、更新中心、收敛判断。
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .utils import clean

# 按综合得分排名给出的客群名称（k 大于 6 时自动补编号）
NAME_POOL = [
    "核心高价值客群",
    "稳定贡献客群",
    "潜力成长客群",
    "长尾基础客群",
    "边缘低频客群",
    "待观察客群",
]


def _standardize(x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean = x.mean(axis=0)
    std = x.std(axis=0)
    std[std == 0] = 1.0
    return (x - mean) / std, mean, std


def _kmeans_plus_plus(x: np.ndarray, k: int, rng: np.random.Generator) -> np.ndarray:
    """k-means++ 初始化：让初始中心彼此尽量远，降低陷入局部最优的概率。"""
    n = x.shape[0]
    centers = [x[rng.integers(n)]]
    for _ in range(1, k):
        d2 = np.min(
            ((x[:, None, :] - np.array(centers)[None, :, :]) ** 2).sum(axis=2), axis=1
        )
        prob = d2 / d2.sum() if d2.sum() > 0 else np.ones(n) / n
        centers.append(x[rng.choice(n, p=prob)])
    return np.array(centers)


def _assign(x: np.ndarray, centers: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """返回 (每个样本最近的簇编号, 每个样本到最近中心的平方距离)。"""
    d2 = (
        (x**2).sum(axis=1)[:, None] - 2 * x @ centers.T + (centers**2).sum(axis=1)[None, :]
    )
    labels = d2.argmin(axis=1)
    return labels, d2[np.arange(len(x)), labels]


def kmeans(x: np.ndarray, k: int, n_init: int = 10, max_iter: int = 300, seed: int = 42):
    """标准 KMeans：多次随机初始化，取簇内平方和最小的一次。"""
    best: tuple[float, np.ndarray, np.ndarray] | None = None
    for i in range(n_init):
        rng = np.random.default_rng(seed + i)
        centers = _kmeans_plus_plus(x, k, rng)
        labels = np.zeros(len(x), dtype=int)
        for _ in range(max_iter):
            labels, _ = _assign(x, centers)
            new_centers = np.array(
                [
                    x[labels == j].mean(axis=0) if np.any(labels == j) else centers[j]
                    for j in range(k)
                ]
            )
            if np.allclose(new_centers, centers):
                centers = new_centers
                break
            centers = new_centers
        labels, dist = _assign(x, centers)
        inertia = float(dist.sum())
        if best is None or inertia < best[0]:
            best = (inertia, centers, labels)
    assert best is not None
    return best[1], best[2], best[0]


def silhouette_score(x: np.ndarray, labels: np.ndarray) -> float:
    """轮廓系数：衡量「簇内紧、簇间远」，取值 -1..1，越大越好。"""
    n = len(x)
    unique = np.unique(labels)
    if len(unique) < 2 or len(unique) >= n:
        return 0.0
    dist = np.sqrt(((x[:, None, :] - x[None, :, :]) ** 2).sum(axis=2))
    score = 0.0
    for i in range(n):
        same = labels == labels[i]
        same[i] = False
        if same.sum() == 0:
            continue
        a = dist[i, same].mean()
        b = min(
            dist[i, labels == other].mean() for other in unique if other != labels[i]
        )
        score += (b - a) / max(a, b) if max(a, b) > 0 else 0.0
    return float(score / n)


def run_clustering(
    df: pd.DataFrame, features: list[str], k: int = 4, seed: int = 42
) -> dict[str, Any]:
    """对给定特征做 KMeans，并把人话讲得通的客群名、状态、规模算出来。"""
    k = max(2, min(k, len(df) // 20 or 2))
    matrix = df[features].to_numpy(dtype=float)
    scaled, mean, std = _standardize(matrix)
    centers, labels, inertia = kmeans(scaled, k=k, seed=seed)
    sil = silhouette_score(scaled, labels)

    work = df.copy()
    work["cluster"] = labels

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

    stats["score"] = (0.5 * z("avg_spend") + 0.3 * z("avg_freq") - 0.2 * z("avg_recency")).round(4)
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

    return {
        "labels": work["cluster_name"],
        "table": work,
        "k": k,
        "inertia": clean(inertia),
        "silhouette": clean(sil),
        "features": features,
        "centers_raw": clean(np.round(centers * std + mean, 3).tolist()),
        "clusters": clusters,
    }


def elbow_curve(df: pd.DataFrame, features: list[str], ks: list[int], seed: int = 42) -> list[dict]:
    """肘部法则数据：k 越大惯性越小，找「下降明显变缓」的拐点。"""
    matrix = df[features].to_numpy(dtype=float)
    scaled, _, _ = _standardize(matrix)
    points = []
    for k in ks:
        if k < 2 or k >= len(df) // 10:
            continue
        _, labels, inertia = kmeans(scaled, k=k, seed=seed)
        points.append(
            {
                "k": k,
                "inertia": clean(inertia),
                "silhouette": clean(silhouette_score(scaled, labels)),
            }
        )
    return points
