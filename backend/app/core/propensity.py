"""响应预测：判断「下一个营销活动，谁会买单」。

模型：scikit-learn 的 L2 正则逻辑回归（class_weight="balanced" 处理类别不平衡）。
为什么用逻辑回归而不是 XGBoost/LightGBM：
1. 输出的是可解释概率，业务方要的正是「这个客户大概率会响应」；
2. 每个特征的系数可以直接讲成「这个指标高一分，转化概率往哪边推」；
3. 一两千条样本、十来个特征，树模型的边际收益很低，可解释性的损失却很大。

换数据注意：特征列表按「这份数据实际有哪些列」动态生成；
如果这份数据没有 response 列（比如只做了分群的名单），直接返回 collected=False，
前端显示空态而不是报错。
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, precision_recall_curve, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from .dataset import channels as channels_of
from .dataset import categories as categories_of
from .dataset import numeric_fields
from .utils import clean

# 特征的展示顺序：先业务主指标，再渠道、品类
PREFERRED_ORDER = [
    "income",
    "total_spend",
    "purchase_freq",
    "recency",
    "num_deals",
    "web_visits_month",
    "accepted_total",
    "age",
    "children",
    "tenure_days",
]

BASE_LABELS = {
    "income": "年收入",
    "total_spend": "总消费额",
    "purchase_freq": "购买频次",
    "recency": "最近购买间隔",
    "num_deals": "折扣购买次数",
    "web_visits_month": "月访问次数",
    "accepted_total": "历史活动接受数",
    "age": "年龄",
    "children": "子女数",
    "tenure_days": "在网天数",
    "value_score": "价值评分",
}


def feature_list(df: pd.DataFrame) -> list[str]:
    """按当前数据实际存在的列，挑出可以用来建模的数值字段。"""
    cats = categories_of()
    chans = channels_of()
    labels = {**BASE_LABELS, **chans, **cats}
    available = [f for f in numeric_fields() if f in df.columns and f in labels]
    ordered = [f for f in PREFERRED_ORDER if f in available]
    rest = [f for f in available if f not in ordered]
    # 去掉常数列（全 0 的渠道/品类对模型没有信息量）
    return [f for f in ordered + rest if pd.to_numeric(df[f], errors="coerce").nunique() > 1]


def feature_labels(df: pd.DataFrame) -> dict[str, str]:
    labels = {**BASE_LABELS, **channels_of(), **categories_of()}
    return {f: labels.get(f, f) for f in feature_list(df)}


def _metrics(y: np.ndarray, p: np.ndarray, threshold: float = 0.5) -> dict[str, Any]:
    pred = (p >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "threshold": clean(threshold),
        "accuracy": clean((tp + tn) / len(y)),
        "precision": clean(precision),
        "recall": clean(recall),
        "f1": clean(f1),
        "confusion": {"tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn)},
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


def _make_model(seed: int) -> LogisticRegression:
    return LogisticRegression(
        class_weight="balanced",  # 正样本通常只有 10%-20%，不加权模型会直接全预测 0
        C=1.0,
        max_iter=2000,
        random_state=seed,
    )


def unavailable(reason: str) -> dict[str, Any]:
    """数据不足以训练模型时的返回结构（前端据此显示空态）。"""
    return {
        "available": False,
        "reason": reason,
        "table": pd.DataFrame(columns=["customer_id", "prob", "decile", "rank"]),
        "features": [],
        "coefs": [],
        "intercept": 0.0,
        "train_metrics": {},
        "full_metrics": {},
        "lift": [],
        "base_rate": 0.0,
        "threshold": 0.5,
        "score_hist": [],
    }


def score_hist(scores: np.ndarray, bins: int = 20) -> list[dict]:
    counts, edges = np.histogram(scores, bins=bins, range=(0, 1))
    return [
        {"name": f"{edges[i]:.2f}~{edges[i + 1]:.2f}", "value": int(c)}
        for i, c in enumerate(counts)
    ]


def train(df: pd.DataFrame, threshold: float = 0.3, seed: int = 42) -> dict[str, Any]:
    """训练 + 评估 + 给每个客户打分。"""
    if "response" not in df.columns:
        return unavailable("这份数据没有「是否响应」字段，无法训练响应预测模型。")
    y_all = pd.to_numeric(df["response"], errors="coerce").fillna(0).astype(int).to_numpy()
    if len(np.unique(y_all)) < 2:
        return unavailable("这份数据的「是否响应」只有一个取值，无法训练二分类模型。")
    if len(df) < 60:
        return unavailable(f"样本量只有 {len(df)} 条，少于 60 条不足以训练稳定模型。")

    features = feature_list(df)
    if not features:
        return unavailable("没有找到可用的数值特征列，无法训练模型。")
    labels = feature_labels(df)

    x_raw = df[features].apply(pd.to_numeric, errors="coerce").fillna(0.0).to_numpy(dtype=float)
    y = y_all

    # 分层抽样：保证训练集/测试集的正样本比例一致
    x_tr, x_te, y_tr, y_te = train_test_split(
        x_raw, y, test_size=0.3, random_state=seed, stratify=y
    )
    scaler = StandardScaler().fit(x_tr)
    model = _make_model(seed).fit(scaler.transform(x_tr), y_tr)
    p_te = model.predict_proba(scaler.transform(x_te))[:, 1]

    # 默认 0.5 阈值在低正样本率下几乎不报警，用 PR 曲线找 F1 最大的阈值
    prec, rec, thr = precision_recall_curve(y_te, p_te)
    f1_curve = 2 * prec[:-1] * rec[:-1] / np.maximum(prec[:-1] + rec[:-1], 1e-12)
    best_t = float(thr[int(np.argmax(f1_curve))]) if len(thr) else threshold
    threshold = round(best_t, 2)

    test_metrics = _metrics(y_te, p_te, threshold)
    test_metrics["auc"] = clean(float(roc_auc_score(y_te, p_te)))

    # 评估完成后用全量数据重新训练，用于实际打分
    scaler_full = StandardScaler().fit(x_raw)
    model_full = _make_model(seed).fit(scaler_full.transform(x_raw), y)
    p_all = model_full.predict_proba(scaler_full.transform(x_raw))[:, 1]

    coefs = [
        {
            "feature": labels.get(f, f),
            "key": f,
            "coef": clean(float(c)),
            "direction": "正向" if c > 0 else "负向",
        }
        for f, c in zip(features, model_full.coef_[0])
    ]
    coefs.sort(key=lambda r: -abs(r["coef"] or 0))

    scores = pd.DataFrame({"customer_id": df["customer_id"].values, "prob": p_all})
    scores["decile"] = pd.qcut(scores["prob"].rank(method="first"), 10, labels=False) + 1
    scores["decile"] = 11 - scores["decile"]  # 1 = 概率最高
    scores["rank"] = scores["prob"].rank(ascending=False, method="first").astype(int)

    full_metrics = _metrics(y, p_all, threshold)
    full_metrics["auc"] = clean(float(roc_auc_score(y, p_all)))

    return {
        "available": True,
        "reason": "",
        "table": scores,
        "features": features,
        "feature_labels": labels,
        "coefs": coefs,
        "intercept": clean(float(model_full.intercept_[0])),
        "train_metrics": test_metrics,
        "full_metrics": full_metrics,
        "lift": lift_table(y, p_all),
        "base_rate": clean(float(y.mean())),
        "threshold": threshold,
        "score_hist": score_hist(p_all),
    }
