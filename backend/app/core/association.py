"""品类关联规则（简化版 Apriori）。

问题：买了葡萄酒的人，有多大比例会顺手买肉类？
用支持度（一起出现的概率）、置信度（买了 A 之后再买 B 的概率）、提升度（比随机高多少倍）回答。
"""
from __future__ import annotations

from itertools import combinations
from typing import Any

import pandas as pd

from .config import CATEGORY_FIELDS
from .utils import clean, pct


def build_transactions(df: pd.DataFrame, min_amount: float = 1.0) -> list[set[str]]:
    """把每行客户转成「买过的品类集合」。金额 > 阈值的品类才算买过。"""
    labels = list(CATEGORY_FIELDS.values())
    fields = list(CATEGORY_FIELDS.keys())
    transactions: list[set[str]] = []
    for row in df[fields].to_numpy(dtype=float):
        basket = {labels[i] for i, v in enumerate(row) if v is not None and v >= min_amount and v > 0}
        if basket:
            transactions.append(basket)
    return transactions


def _support(transactions: list[set[str]], items: tuple[str, ...]) -> float:
    target = set(items)
    hit = sum(1 for t in transactions if target.issubset(t))
    return hit / len(transactions) if transactions else 0.0


def mine_rules(
    df: pd.DataFrame, min_support: float = 0.03, min_confidence: float = 0.15, max_items: int = 2
) -> list[dict[str, Any]]:
    """搜索 1~max_items 元的频繁项集，生成「A -> B」规则。"""
    transactions = build_transactions(df)
    if not transactions:
        return []
    labels = list(CATEGORY_FIELDS.values())
    rules: list[dict[str, Any]] = []
    for size in range(1, max_items + 1):
        for items in combinations(labels, size):
            sup = _support(transactions, items)
            if sup < min_support:
                continue
            for i, head in enumerate(items):
                antecedent = items[i]
                consequent = tuple(x for x in items if x != antecedent)
                sup_a = _support(transactions, (antecedent,))
                sup_c = _support(transactions, consequent)
                if sup_a == 0 or sup_c == 0:
                    continue
                confidence = sup / sup_a
                lift = confidence / sup_c
                if confidence < min_confidence:
                    continue
                rules.append(
                    {
                        "antecedent": antecedent,
                        "consequent": " + ".join(consequent),
                        "support": clean(sup),
                        "confidence": clean(confidence),
                        "lift": clean(lift),
                        "count": int(round(sup * len(transactions))),
                    }
                )
    rules.sort(key=lambda r: (-(r["lift"] or 0), -(r["confidence"] or 0)))
    # 同一组 A->B 可能被重复生成（对称），去重后保留最高分
    seen: set[tuple[str, str]] = set()
    deduped = []
    for r in rules:
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
                "buyer_avg_spend": clean(df.loc[df[field] > 0, field].mean()) if buyers else 0.0,
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
