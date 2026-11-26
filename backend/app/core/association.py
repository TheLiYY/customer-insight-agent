"""品类关联规则（mlxtend 的 Apriori 实现）。

问题：买了葡萄酒的人，有多大比例会顺手买肉类？
用三个指标回答：
- 支持度 support：A 和 B 一起出现的比例（这个组合多常见）；
- 置信度 confidence：买了 A 之后又买 B 的比例（规则的可靠程度）；
- 提升度 lift：置信度 ÷ B 本身的出现比例（>1 说明「买 A」确实提高了「买 B」的概率，不是巧合）。
"""
from __future__ import annotations

from typing import Any

import pandas as pd
from mlxtend.frequent_patterns import apriori, association_rules
from mlxtend.preprocessing import TransactionEncoder

from .config import CATEGORY_FIELDS
from .utils import clean, pct


def build_transactions(df: pd.DataFrame, min_amount: float = 1.0) -> list[set[str]]:
    """把每行客户转成「买过的品类集合」。金额 > 阈值的品类才算买过。"""
    labels = list(CATEGORY_FIELDS.values())
    fields = list(CATEGORY_FIELDS.keys())
    transactions: list[set[str]] = []
    for row in df[fields].to_numpy(dtype=float):
        basket = {
            labels[i]
            for i, v in enumerate(row)
            if v is not None and v >= min_amount and v > 0
        }
        if basket:
            transactions.append(basket)
    return transactions


def _encode(transactions: list[set[str]]) -> pd.DataFrame:
    """把交易列表转成 mlxtend 需要的 0/1 矩阵。"""
    encoder = TransactionEncoder()
    matrix = encoder.fit(transactions).transform(transactions)
    return pd.DataFrame(matrix, columns=encoder.columns_)


def mine_rules(
    df: pd.DataFrame,
    min_support: float = 0.03,
    min_confidence: float = 0.15,
    max_items: int = 2,
) -> list[dict[str, Any]]:
    """用 Apriori 搜频繁项集，再生成「A -> B」规则，按提升度排序。"""
    transactions = build_transactions(df)
    if len(transactions) < 2:
        return []

    basket = _encode(transactions)
    n = len(transactions)

    freq = apriori(
        basket,
        min_support=min_support,
        use_colnames=True,
        max_len=max_items,
    )
    if freq.empty:
        return []

    rules = association_rules(freq, metric="confidence", min_threshold=min_confidence)
    if rules.empty:
        return []

    # 只保留「单个品类 -> 单个品类」的规则，讲起来最直观
    rules = rules[
        rules["consequents"].map(len).eq(1) & rules["antecedents"].map(len).eq(1)
    ]

    rows: list[dict[str, Any]] = []
    for _, r in rules.iterrows():
        antecedent = " + ".join(sorted(r["antecedents"]))
        consequent = " + ".join(sorted(r["consequents"]))
        rows.append(
            {
                "antecedent": antecedent,
                "consequent": consequent,
                "support": clean(float(r["support"])),
                "confidence": clean(float(r["confidence"])),
                "lift": clean(float(r["lift"])),
                "count": int(round(float(r["support"]) * n)),
            }
        )

    rows.sort(key=lambda x: (-(x["lift"] or 0), -(x["confidence"] or 0)))
    seen: set[tuple[str, str]] = set()
    deduped = []
    for r in rows:
        key = (r["antecedent"], r["consequent"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)
    return deduped[:20]


def penetration(df: pd.DataFrame) -> list[dict[str, Any]]:
    """品类渗透率：多少比例的客户买过该品类 + 人均消费额。"""
    total = len(df)
    rows = []
    for field, label in CATEGORY_FIELDS.items():
        buyers = int((df[field] > 0).sum())
        rows.append(
            {
                "name": label,
                "buyers": buyers,
                "penetration": pct(buyers, total),
                "avg_spend": clean(df[field].mean()),
                "buyer_avg_spend": clean(df.loc[df[field] > 0, field].mean())
                if buyers
                else 0.0,
                "revenue": clean(df[field].sum()),
            }
        )
    rows.sort(key=lambda r: -(r["revenue"] or 0))
    total_rev = sum(r["revenue"] or 0 for r in rows) or 1
    for r in rows:
        r["revenue_ratio"] = pct(r["revenue"], total_rev)
    return rows


def basket_size(df: pd.DataFrame) -> list[dict[str, Any]]:
    """一单买几个品类的人数分布。"""
    counts = []
    for row in df[list(CATEGORY_FIELDS.keys())].to_numpy(dtype=float):
        counts.append(int((row > 0).sum()))
    series = pd.Series(counts).value_counts().sort_index()
    total = len(series) or 1
    return [
        {"name": f"{int(k)} 个品类", "value": int(v), "ratio": pct(v, total)}
        for k, v in series.items()
    ]
