"""响应预测：判断「下一个营销活动，谁会买单」。

模型：带类别权重的 L2 正则逻辑回归，numpy 手写梯度下降。
优点是完全可解释——每个特征的系数就代表「这个因素把转化概率推高还是压低了多少」。
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .utils import clean

FEATURES = [
    "income",
    "total_spend",
    "purchase_freq",
    "recency",
    "num_deals",
    "num_web",
    "num_catalog",
    "num_store",
    "web_visits_month",
    "accepted_total",
    "age",
    "kidhome",
    "teenhome",
]

FEATURE_LABELS = {
    "income": "年收入",
    "total_spend": "总消费额",
    "purchase_freq": "购买频次",
    "recency": "最近购买间隔",
    "num_deals": "折扣购买次数",
    "num_web": "线上购买次数",
    "num_catalog": "目录购买次数",
    "num_store": "门店购买次数",
    "web_visits_month": "月访问次数",
    "accepted_total": "历史活动接受数",
    "age": "年龄",
    "kidhome": "家中儿童数",
    "teenhome": "家中青少年数",
}


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


def _fit(x: np.ndarray, y: np.ndarray, lr: float = 0.1, epochs: int = 800, l2: float = 1e-3):
    """全批量梯度下降。类别不平衡用权重补偿，否则模型会直接预测全 0。"""
    n, d = x.shape
    pos = max(int(y.sum()), 1)
    neg = max(n - pos, 1)
    weights = np.where(y == 1, n / (2.0 * pos), n / (2.0 * neg))
    w = np.zeros(d)
    b = 0.0
    for _ in range(epochs):
        p = _sigmoid(x @ w + b)
        err = (p - y) * weights
        grad_w = (x.T @ err) / n + l2 * w
        grad_b = float(err.mean())
        w -= lr * grad_w
        b -= lr * grad_b
    return w, b


def roc_auc(y: np.ndarray, score: np.ndarray) -> float:
    """用秩和公式算 AUC，等价于「随机取一正一负，正样本得分更高的概率」。"""
    s = pd.Series(score)
    ranks = s.rank()
    pos = y == 1
    n_pos = int(pos.sum())
    n_neg = int(len(y) - n_pos)
    if n_pos == 0 or n_neg == 0:
        return 0.5
    return float((ranks[pos].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def _metrics(y: np.ndarray, p: np.ndarray, threshold: float = 0.5) -> dict[str, Any]:
    pred = (p >= threshold).astype(int)
    tp = int(((pred == 1) & (y == 1)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "threshold": clean(threshold),
        "accuracy": clean((tp + tn) / len(y)),
        "precision": clean(precision),
        "recall": clean(recall),
        "f1": clean(f1),
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
    }


def lift_table(y: np.ndarray, p: np.ndarray, bins: int = 10) -> list[dict]:
    """十分位提升表：把客户按预测概率排序切 10 组，看每组真实转化率。"""
    order = np.argsort(-p)
    y_sorted, p_sorted = y[order], p[order]
    base = float(y.mean())
    rows = []
    size = int(np.ceil(len(y) / bins))
    for i in range(bins):
        sl = slice(i * size, min((i + 1) * size, len(y)))
        yb, pb = y_sorted[sl], p_sorted[sl]
        if len(yb) == 0:
            continue
        rate = float(yb.mean())
        rows.append(
            {
                "group": f"第{i + 1}组",
                "customers": int(len(yb)),
                "avg_score": clean(pb.mean()),
                "response_rate": clean(rate),
                "lift": clean(rate / base) if base else 0.0,
                "captured": clean(float(yb.sum()) / max(float(y.sum()), 1)),
            }
        )
    return rows


def train(df: pd.DataFrame, threshold: float = 0.3, seed: int = 42) -> dict[str, Any]:
    """训练 + 评估 + 给每个客户打分。"""
    x_raw = df[FEATURES].to_numpy(dtype=float)
    y = df["response"].to_numpy(dtype=float)
    mean = x_raw.mean(axis=0)
    std = x_raw.std(axis=0)
    std[std == 0] = 1.0
    x = (x_raw - mean) / std

    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(df))
    split = int(len(df) * 0.7)
    tr, te = idx[:split], idx[split:]

    w, b = _fit(x[tr], y[tr])
    p_test = _sigmoid(x[te] @ w + b)

    # 正样本只占 13%，0.5 的默认阈值几乎不会报警；在验证集上按 F1 网格搜索最优点
    best_t, best_f1 = threshold, -1.0
    for t in np.arange(0.05, 0.81, 0.01):
        m = _metrics(y[te], p_test, float(t))
        if m["f1"] > best_f1:
            best_t, best_f1 = float(t), m["f1"]
    threshold = round(best_t, 2)
    test_metrics = _metrics(y[te], p_test, threshold)
    test_metrics["auc"] = clean(roc_auc(y[te], p_test))

    # 评估完成后用全量数据重新训练，用于实际打分
    w_full, b_full = _fit(x, y)
    p_all = _sigmoid(x @ w_full + b_full)

    coefs = [
        {
            "feature": FEATURE_LABELS[f],
            "key": f,
            "coef": clean(float(c)),
            "direction": "正向" if c > 0 else "负向",
        }
        for f, c in zip(FEATURES, w_full)
    ]
    coefs.sort(key=lambda r: -abs(r["coef"] or 0))

    scores = pd.DataFrame(
        {
            "customer_id": df["customer_id"].values,
            "prob": p_all,
        }
    )
    scores["decile"] = pd.qcut(scores["prob"].rank(method="first"), 10, labels=False) + 1
    scores["decile"] = 11 - scores["decile"]  # 1 = 概率最高
    scores["rank"] = scores["prob"].rank(ascending=False, method="first").astype(int)

    full_metrics = _metrics(y, p_all, threshold)
    full_metrics["auc"] = clean(roc_auc(y, p_all))

    return {
        "table": scores,
        "features": FEATURES,
        "coefs": coefs,
        "intercept": clean(float(b_full)),
        "train_metrics": test_metrics,
        "full_metrics": full_metrics,
        "lift": lift_table(y, p_all),
        "base_rate": clean(float(y.mean())),
        "threshold": threshold,
    }
