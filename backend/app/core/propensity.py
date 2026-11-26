"""响应预测：判断「下一个营销活动，谁会买单」。

模型：scikit-learn 的 L2 正则逻辑回归（class_weight="balanced" 处理类别不平衡）。
为什么用逻辑回归而不是 XGBoost/LightGBM：
1. 输出的是可解释概率，业务方要的正是「这个客户大概率会响应」；
2. 每个特征的系数可以直接讲成「收入每高一个标准差，转化概率往哪边推」；
3. 两千多条样本、13 个特征，树模型的边际收益很低，可解释性的损失却很大。
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, precision_recall_curve, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

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
        "confusion": {
            "tp": int(tp),
            "fp": int(fp),
            "fn": int(fn),
            "tn": int(tn),
        },
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
        class_weight="balanced",  # 正样本只有 15%，不加权模型会直接全预测 0
        C=1.0,
        max_iter=2000,
        random_state=seed,
    )


def train(df: pd.DataFrame, threshold: float = 0.3, seed: int = 42) -> dict[str, Any]:
    """训练 + 评估 + 给每个客户打分。"""
    x_raw = df[FEATURES].to_numpy(dtype=float)
    y = df["response"].to_numpy(dtype=int)

    # 分层抽样：保证训练集/测试集的正样本比例一致（正样本只有 15%，随机切容易偏）
    x_tr, x_te, y_tr, y_te = train_test_split(
        x_raw, y, test_size=0.3, random_state=seed, stratify=y
    )
    scaler = StandardScaler().fit(x_tr)
    model = _make_model(seed).fit(scaler.transform(x_tr), y_tr)
    p_te = model.predict_proba(scaler.transform(x_te))[:, 1]

    # 默认 0.5 阈值在 15% 正样本下几乎不报警，用 PR 曲线找 F1 最大的阈值
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
            "feature": FEATURE_LABELS[f],
            "key": f,
            "coef": clean(float(c)),
            "direction": "正向" if c > 0 else "负向",
        }
        for f, c in zip(FEATURES, model_full.coef_[0])
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
    full_metrics["auc"] = clean(float(roc_auc_score(y, p_all)))

    return {
        "table": scores,
        "features": FEATURES,
        "coefs": coefs,
        "intercept": clean(float(model_full.intercept_[0])),
        "train_metrics": test_metrics,
        "full_metrics": full_metrics,
        "lift": lift_table(y, p_all),
        "base_rate": clean(float(y.mean())),
        "threshold": threshold,
    }
