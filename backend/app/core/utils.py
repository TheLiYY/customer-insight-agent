"""通用工具：JSON 安全化、百分位打分、文本截断。"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd


def clean(value: Any) -> Any:
    """把 numpy / pandas / NaN 转成可 JSON 序列化的原生类型。"""
    if value is None:
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        f = float(value)
        return None if (math.isnan(f) or math.isinf(f)) else round(f, 4)
    if isinstance(value, float):
        return None if (math.isnan(value) or math.isinf(value)) else round(value, 4)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [clean(v) for v in value]
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    return value


def pct(part: float, whole: float, digits: int = 4) -> float:
    """安全的百分比计算，返回 0-1 之间的小数。"""
    if not whole:
        return 0.0
    return round(float(part) / float(whole), digits)


def quantile_score(series: pd.Series, higher_is_better: bool = True, q: int = 5) -> pd.Series:
    """按分位数把连续指标打成 1..q 分，遇到重复边界自动降级分箱数。"""
    if series.nunique() <= 1:
        return pd.Series([max(1, q // 2)] * len(series), index=series.index)
    try:
        ranked = series.rank(method="first")
        labels = list(range(1, q + 1))
        scores = pd.qcut(ranked, q=q, labels=labels).astype(int)
    except ValueError:  # 分箱数超过唯一值个数
        ranked = series.rank(method="first")
        n = max(1, series.nunique())
        scores = pd.qcut(ranked, q=n, labels=list(range(1, n + 1))).astype(int)
        scores = ((scores - 1) * (q - 1) / max(1, n - 1)).round().astype(int) + 1
    if not higher_is_better:
        scores = (q + 1) - scores
    return scores.astype(int)


def top_share(counter: pd.Series, n: int = 3) -> list[dict]:
    """取分布前 n 项，返回 [{name, value, ratio}]。"""
    total = float(counter.sum()) or 1.0
    out = []
    for name, value in counter.head(n).items():
        out.append({"name": str(name), "value": int(value), "ratio": pct(value, total)})
    return out


def money(value: float) -> float:
    return round(float(value), 2)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def num(df: pd.DataFrame, col: str) -> pd.Series:
    """取数值列；列不存在时返回等长的 0 序列。

    换数据时很多字段可能没有（比如银行名单没有消费额），
    各分析模块统一用这个函数取值，缺字段就退化成 0，不抛 KeyError。
    """
    if col not in df.columns:
        return pd.Series(0.0, index=df.index, dtype="float64")
    return pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype("float64")


def mean_of(df: pd.DataFrame, col: str) -> float:
    if col not in df.columns or len(df) == 0:
        return 0.0
    value = float(num(df, col).mean())
    return 0.0 if math.isnan(value) else value


def sum_of(df: pd.DataFrame, col: str) -> float:
    if col not in df.columns or len(df) == 0:
        return 0.0
    value = float(num(df, col).sum())
    return 0.0 if math.isnan(value) else value


def has_value(df: pd.DataFrame, col: str) -> bool:
    """字段存在且有正值（全 0 的列等于没有）。"""
    return col in df.columns and float(num(df, col).abs().sum()) > 0

