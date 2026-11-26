"""数据加载与字段注册中心。

项目要能换数据（iFood、银行名单、公司自己的订单表……），所以「有哪些品类、有哪些渠道、
这份数据能做什么」不再写死在代码里，而是由 scripts/prepare_data.py 生成、
后端在这里统一读取（dataset_meta.json）。各分析模块只调 categories() / channels()。
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pandas as pd

from .config import CATEGORY_FIELDS, CHANNEL_FIELDS, CUSTOMERS_CSV, META_JSON

# 标准数值字段（换数据时可能有缺失，下面会按列过滤）
BASE_NUMERIC = [
    "age",
    "income",
    "children",
    "recency",
    "tenure_days",
    "total_spend",
    "value_score",
    "num_deals",
    "purchase_freq",
    "web_visits_month",
    "accepted_total",
    "complain",
    "response",
]


@lru_cache(maxsize=1)
def load_customers(path: str | None = None) -> pd.DataFrame:
    """加载清洗后的客户明细表。结果按路径缓存，避免重复读盘。"""
    csv_path = Path(path) if path else CUSTOMERS_CSV
    if not csv_path.exists():
        raise FileNotFoundError(
            f"未找到客户明细 {csv_path}，请先在项目根目录执行: python scripts/prepare_data.py"
        )
    df = pd.read_csv(csv_path)
    # 只把标准数值字段强制转成数值；品类/渠道列本身由 CSV 读出来就是数值
    for col in BASE_NUMERIC:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ("education", "marital_status", "gender"):
        if col in df.columns:
            df[col] = df[col].fillna("Unknown").astype(str)
    if "age_group" in df.columns:
        df["age_group"] = df["age_group"].fillna("未知").astype(str)
    return df


@lru_cache(maxsize=1)
def load_meta() -> dict:
    if META_JSON.exists():
        return json.loads(META_JSON.read_text(encoding="utf-8"))
    return {}


def _pick_fields(meta_key: str, fallback: dict[str, str]) -> dict[str, str]:
    """优先用 meta 里识别出来的品类/渠道；老数据没有 meta 时回退到内置常量。"""
    meta = load_meta()
    fields = meta.get(meta_key) or {}
    df_cols = set(load_customers().columns)
    picked = {k: v for k, v in fields.items() if k in df_cols}
    if picked:
        return picked
    return {k: v for k, v in fallback.items() if k in df_cols}


@lru_cache(maxsize=1)
def categories() -> dict[str, str]:
    """品类字段 -> 中文名。换数据后自动变化（比如这份数据只有 3 个品类）。"""
    return _pick_fields("categories", CATEGORY_FIELDS)


@lru_cache(maxsize=1)
def channels() -> dict[str, str]:
    """渠道字段 -> 中文名。"""
    return _pick_fields("channels", CHANNEL_FIELDS)


@lru_cache(maxsize=1)
def capabilities() -> dict:
    """数据能力清单：哪些模型/图表可用。"""
    meta = load_meta()
    caps = meta.get("capabilities")
    if caps:
        return caps
    # 兼容老版本生成的 meta：现场推断一份
    df = load_customers()
    from .schema import capabilities_of

    cats = {k: v for k, v in CATEGORY_FIELDS.items() if k in df.columns}
    chans = {k: v for k, v in CHANNEL_FIELDS.items() if k in df.columns}
    fake_mapping = {
        "categories": {k: {"source": k, "label": v} for k, v in cats.items()},
        "channels": {k: {"source": k, "label": v} for k, v in chans.items()},
    }
    return capabilities_of(df, fake_mapping)


def numeric_fields() -> list[str]:
    """有效数值字段：标准字段 + 动态品类/渠道。"""
    cols = set(load_customers().columns)
    return [c for c in BASE_NUMERIC + list(categories()) + list(channels()) if c in cols]


def clear_cache() -> None:
    """重新生成数据后清缓存（store.reload() 会调用）。"""
    for fn in (load_customers, load_meta, categories, channels, capabilities):
        fn.cache_clear()


def contract() -> dict:
    """返回数据契约（粒度、字段映射、警告），供前端「数据说明」页展示。"""
    meta = load_meta()
    return meta.get("contract", {}) or {}


def warnings() -> list[str]:
    return list(load_meta().get("warnings", []) or [])
