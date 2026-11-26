"""数据契约层单元测试。

冒烟测试（smoke_test.py）验证的是「用仓库自带数据，接口都能返回」；
这个文件验证的是「换一份长得不一样的数据，自动识别还对不对」。

所有用例都用代码现场造表，不依赖网络、不依赖仓库里的 CSV，
所以可以放心在 CI 里跑，也能直接用来说明这套识别规则到底管什么。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core import schema  # noqa: E402

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    """一条断言：打印 PASS/FAIL，失败时把关键信息一起打出来。"""
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"PASS {name}")
    else:
        FAIL += 1
        print(f"FAIL {name}{(' -> ' + detail) if detail else ''}")


def make_ifood_like(n: int = 80) -> pd.DataFrame:
    """模拟 iFood 那种「客户级宽表 + one-hot」结构。"""
    rng = np.random.default_rng(42)
    response = np.array([1] * (n // 2) + [0] * (n - n // 2))
    rng.shuffle(response)
    return pd.DataFrame(
        {
            "Income": rng.integers(20000, 80000, n).astype(float),
            "Kidhome": rng.integers(0, 3, n),
            "Teenhome": rng.integers(0, 3, n),
            "Recency": rng.integers(0, 100, n),
            "MntWines": rng.integers(0, 1000, n).astype(float),
            "MntFruits": rng.integers(0, 200, n).astype(float),
            "MntTotal": rng.integers(0, 2400, n).astype(float),
            "NumDealsPurchases": rng.integers(0, 6, n),
            "NumWebPurchases": rng.integers(1, 10, n),
            "NumCatalogPurchases": rng.integers(1, 8, n),
            "NumStorePurchases": rng.integers(1, 12, n),
            "NumWebVisitsMonth": rng.integers(1, 12, n),
            "Complain": rng.integers(0, 2, n),
            "Response": response,
            "Age": rng.integers(25, 75, n),
            "Customer_Days": rng.integers(300, 3000, n),
            "education_Graduation": (np.arange(n) % 2 == 0).astype(int),
            "education_PhD": (np.arange(n) % 2 == 1).astype(int),
            "marital_Single": (np.arange(n) % 3 == 0).astype(int),
            "marital_Married": (np.arange(n) % 3 != 0).astype(int),
        }
    )


def test_ifood_like() -> None:
    df = make_ifood_like()
    info = schema.detect(df)

    for key in ("income", "age", "recency", "total_spend", "response", "complain", "children"):
        check(f"宽表: 识别出 {key}", key in info["mapping"], str(info["mapping"].keys()))
    check("宽表: 粒度为客户级", info["grain"] == "customer", info["grain"])
    check("宽表: 品类识别出葡萄酒", "mnt_wines" in info["categories"], str(info["categories"].keys()))
    check("宽表: 渠道识别出 3 个", len(info["channels"]) == 3, str(info["channels"].keys()))
    # one-hot 列不应该被当成普通字段
    check("宽表: one-hot 学历列未被单独映射", all("education_" not in v["source"] for v in info["mapping"].values()))

    out, ctx = schema.build_customers(df, info)
    check("宽表: 行数不变", len(out) == len(df), f"{len(out)} != {len(df)}")
    check("宽表: 学历已反解成一列", "education" in out.columns)
    check("宽表: 学历取值来自 one-hot", set(out["education"].unique()) <= {"Graduation", "PhD"}, str(set(out["education"].unique())))
    check("宽表: 子女数为两列合并", "children" in out.columns and out["children"].max() <= 4)
    check("宽表: 频次由各渠道相加得到", "purchase_freq" in out.columns and out["purchase_freq"].max() > 0)
    caps = ctx["capabilities"]
    check("宽表: 六个能力开关都打开", all([caps["has_income"], caps["has_monetary"], caps["has_recency"], caps["has_frequency"], caps["has_response"], caps["propensity"]]))

    # 前端要把这份契约原样塞进 JSON，numpy 类型没转干净就会在这里炸
    try:
        json.dumps(schema.describe(info, ctx), ensure_ascii=False)
        check("宽表: 契约信息可 JSON 序列化", True)
    except TypeError as exc:  # pragma: no cover
        check("宽表: 契约信息可 JSON 序列化", False, str(exc))


def test_transaction() -> None:
    """订单明细表：一个客户多行，应该自动聚合成客户级宽表。"""
    df = pd.DataFrame(
        {
            "customer_id": ["A", "A", "A", "B", "B", "C"],
            "order_id": ["o1", "o1", "o2", "o3", "o4", "o5"],
            "order_date": [
                "2024-01-05", "2024-01-05", "2024-03-10",
                "2024-02-01", "2024-03-20",
                "2024-01-01",
            ],
            "amount": [100.0, 50.0, 30.0, 200.0, 20.0, 10.0],
            "product_category": ["葡萄酒", "水果", "葡萄酒", "肉类", "肉类", "水果"],
            "age": [30, 30, 30, 45, 45, 51],
        }
    )
    info = schema.detect(df)
    check("明细: 判定为订单明细", info["grain"] == "transaction", info["grain"])
    check("明细: 识别出订单号", "order_id" in info["transaction"])
    check("明细: 识别出下单时间", "order_date" in info["transaction"])
    # 「amount」既可能是明细的订单金额，也可能是宽表的累计消费；
    # 谁抢到都行，关键是 build 时要按客户求和（见下面的消费额断言）
    amount_src = info["transaction"].get("amount", {}).get("source") or info["mapping"].get("total_spend", {}).get("source")
    check("明细: 识别出金额列", amount_src == "amount", str(amount_src))

    out, ctx = schema.build_customers(df, info)
    out = out.set_index("customer_id")
    check("明细: 聚合成 3 个客户", len(out) == 3, str(len(out)))
    check("明细: 消费额求和", float(out.loc["A", "total_spend"]) == 180.0, str(out.loc["A", "total_spend"]))
    check("明细: 频次按订单号去重", float(out.loc["A", "purchase_freq"]) == 2.0, str(out.loc["A", "purchase_freq"]))
    # 参考日期取数据里最晚的一单 2024-03-20，A 最后一次是 03-10
    check("明细: 最近间隔按最晚日期算", float(out.loc["A", "recency"]) == 10.0, str(out.loc["A", "recency"]))
    check("明细: 品类透视成列", any(k.startswith("mnt_") or "葡萄酒" in k for k in out.columns) or "葡萄酒" in out.columns, str(list(out.columns)))
    check("明细: 能力开关至少能画像", ctx["capabilities"]["clustering"], json.dumps(ctx["capabilities"]["categories"], ensure_ascii=False))


def test_chinese_columns() -> None:
    """中文列名的表：公司自己导出的报表大多是这种。"""
    df = pd.DataFrame(
        {
            "客户编号": [f"VIP{i:03d}" for i in range(1, 61)],
            "年龄": np.random.default_rng(7).integers(20, 70, 60),
            "性别": ["女", "男"] * 30,
            "年收入": np.random.default_rng(8).integers(30000, 120000, 60),
            "消费金额": np.random.default_rng(9).integers(0, 5000, 60),
            "购买次数": np.random.default_rng(10).integers(1, 20, 60),
            "最近购买间隔": np.random.default_rng(11).integers(0, 200, 60),
            "学历": ["本科", "硕士", "大专"] * 20,
        }
    )
    info = schema.detect(df)
    for key in ("customer_id", "age", "gender", "income", "total_spend", "purchase_freq", "recency", "education"):
        check(f"中文列: 识别出 {key}", key in info["mapping"], str(info["mapping"].keys()))

    out, ctx = schema.build_customers(df, info)
    check("中文列: 客户编号保留原值", out.loc[0, "customer_id"] == "VIP001", str(out.loc[0, "customer_id"]))
    check("中文列: 消费金额数值化", abs(float(out["total_spend"].mean()) - df["消费金额"].mean()) < 1.0)
    caps = ctx["capabilities"]
    check("中文列: 有金额有收入", caps["has_monetary"] and caps["has_income"])
    check("中文列: 没有响应标签", not caps["has_response"] and not caps["propensity"])


def test_text_binary_label() -> None:
    """y = yes/no（UCI Bank Marketing 那种）：文本二值也要能认成响应标签。"""
    rng = np.random.default_rng(3)
    n = 240
    df = pd.DataFrame(
        {
            "age": rng.integers(25, 65, n),
            "campaign": rng.integers(1, 6, n),  # 历史联系次数 -> purchase_freq
            "pdays": rng.integers(0, 400, n),  # 距上次联系天数 -> recency
            "y": np.where(np.arange(n) % 6 == 0, "yes", "no"),
        }
    )
    info = schema.detect(df)
    check("文本二值: y 列被认成响应标签", info["mapping"].get("response", {}).get("source") == "y", json.dumps(info["mapping"], ensure_ascii=False))
    out, ctx = schema.build_customers(df, info)
    check("文本二值: yes/no 转成 1/0", set(out["response"].unique()) <= {0, 1}, str(sorted(out["response"].unique())))
    check("文本二值: 正样本数正确", int(out["response"].sum()) == int((np.arange(n) % 6 == 0).sum()))
    check("文本二值: 响应预测可用", ctx["capabilities"]["propensity"])


def test_degradation() -> None:
    """只有年龄+性别这种极简表：不能报错，能力应降级。"""
    df = pd.DataFrame(
        {
            "customer_id": [f"C{i}" for i in range(1, 41)],
            "age": np.random.default_rng(5).integers(20, 60, 40),
            "gender": ["女", "男"] * 20,
        }
    )
    info = schema.detect(df)
    out, ctx = schema.build_customers(df, info)
    caps = ctx["capabilities"]
    check("极简表: 仍然产出客户表", len(out) == 40, str(len(out)))
    check("极简表: 没有金额", not caps["has_monetary"])
    check("极简表: 没有响应标签", not caps["has_response"])
    check("极简表: 不做关联规则", not caps["association"])
    check("极简表: 给出警告而不是崩溃", len(ctx["warnings"]) >= 2, str(ctx["warnings"]))
    check("极简表: RFM 三列被补齐", {"recency", "purchase_freq", "total_spend"} <= set(out.columns))


def test_alias_add() -> None:
    """加自定义别名：公司表里把收入叫「薪资等级」。"""
    df = pd.DataFrame({"客户编号": [f"U{i}" for i in range(1, 31)], "薪资等级": np.arange(30) * 100.0})
    before = schema.detect(df)["mapping"]
    check("别名: 默认认不出「薪资等级」", "income" not in before, json.dumps(before, ensure_ascii=False))

    schema.STANDARD_FIELDS["income"]["aliases"].append("薪资等级")
    after = schema.detect(df)["mapping"]
    check("别名: 加完别名就能认出", after.get("income", {}).get("source") == "薪资等级", json.dumps(after, ensure_ascii=False))
    schema.STANDARD_FIELDS["income"]["aliases"].pop()


def main() -> int:
    print("=" * 60)
    print("数据契约层单元测试")
    print("=" * 60)
    test_ifood_like()
    test_transaction()
    test_chinese_columns()
    test_text_binary_label()
    test_degradation()
    test_alias_add()
    print("-" * 60)
    print(f"完成，通过 {PASS} 项，失败 {FAIL} 项")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
