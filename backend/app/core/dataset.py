"""数据加载与字段常量。"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

from .config import CUSTOMERS_CSV, META_JSON, CATEGORY_FIELDS

NUMERIC_FIELDS = [
    "age",
    "income",
    "kidhome",
    "teenhome",
    "recency",
    "tenure_days",
    "total_spend",
    "num_deals",
    "num_web",
    "num_catalog",
    "num_store",
    "purchase_freq",
    "web_visits_month",
    "accepted_total",
    "complain",
    "response",
] + list(CATEGORY_FIELDS)


@lru_cache(maxsize=1)
def load_customers(path: str | None = None) -> pd.DataFrame:
    """加载清洗后的客户明细表。结果按路径缓存，避免重复读盘。"""
    csv_path = Path(path) if path else CUSTOMERS_CSV
    if not csv_path.exists():
        raise FileNotFoundError(
            f"未找到客户明细 {csv_path}，请先在项目根目录执行: python scripts/prepare_data.py"
        )
    df = pd.read_csv(csv_path)
    for col in NUMERIC_FIELDS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.fillna({"education": "Unknown", "marital_status": "Unknown", "age_group": "未知"})
    return df


@lru_cache(maxsize=1)
def load_meta() -> dict:
    import json

    if META_JSON.exists():
        return json.loads(META_JSON.read_text(encoding="utf-8"))
    return {}
