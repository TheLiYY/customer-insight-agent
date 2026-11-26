"""数据准备脚本：下载 / 清洗 / 生成 Excel 数据集。

运行：
    python scripts/prepare_data.py

产物：
    backend/data/raw/ifood_df.csv                      原始数据（公开数据集 ifood_df.csv）
    backend/data/raw/Customer_Personality_Analysis.xlsx 清洗后的 Excel（含字段字典）
    backend/data/processed/customers.csv               后端统一使用的建模宽表
    backend/data/processed/dataset_meta.json           数据元信息（行数、字段、质量报告）
"""
from __future__ import annotations

import json
import shutil
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "backend" / "data" / "raw"
PROCESSED = ROOT / "backend" / "data" / "processed"
RAW.mkdir(parents=True, exist_ok=True)
PROCESSED.mkdir(parents=True, exist_ok=True)

SOURCE_URL = "https://raw.githubusercontent.com/nailson/ifood-data-business-analyst-test/master/ifood_df.csv"
RAW_CSV = RAW / "ifood_df.csv"
EXCEL = RAW / "Customer_Personality_Analysis.xlsx"
OUT_CSV = PROCESSED / "customers.csv"
META = PROCESSED / "dataset_meta.json"

# 原始 CSV 中 one-hot 字段 -> 可读标签
MARITAL_COLS = {
    "marital_Divorced": "Divorced",
    "marital_Married": "Married",
    "marital_Single": "Single",
    "marital_Together": "Together",
    "marital_Widow": "Widow",
}
EDU_COLS = {
    "education_2n Cycle": "2n Cycle",
    "education_Basic": "Basic",
    "education_Graduation": "Graduation",
    "education_Master": "Master",
    "education_PhD": "PhD",
}

FIELD_DICT = [
    ("customer_id", "客户编号", "字符串", "系统生成的主键，格式 C00001"),
    ("age", "年龄", "整数", "由原始 Year_Birth 换算得到"),
    ("age_group", "年龄段", "字符串", "18-30 / 31-40 / 41-50 / 51-60 / 60+"),
    ("education", "学历", "字符串", "Basic / 2n Cycle / Graduation / Master / PhD"),
    ("marital_status", "婚姻状况", "字符串", "Single / Married / Together / Divorced / Widow"),
    ("income", "年收入", "浮点", "家庭年收入（已剔除 666666 等异常值）"),
    ("kidhome", "小孩数", "整数", "家中儿童数量"),
    ("teenhome", "青少年数", "整数", "家中青少年数量"),
    ("recency", "最近购买间隔", "整数", "距上次购买的天数，越小越活跃"),
    ("tenure_days", "在网天数", "整数", "成为客户至今天数"),
    ("mnt_wines", "葡萄酒消费", "浮点", "近两年葡萄酒消费金额"),
    ("mnt_fruits", "水果消费", "浮点", "近两年水果消费金额"),
    ("mnt_meat", "肉类消费", "浮点", "近两年肉类消费金额"),
    ("mnt_fish", "鱼类消费", "浮点", "近两年鱼类消费金额"),
    ("mnt_sweet", "甜食消费", "浮点", "近两年甜食消费金额"),
    ("mnt_gold", "金饰消费", "浮点", "近两年金饰/礼品消费金额"),
    ("total_spend", "总消费额", "浮点", "六大品类消费之和（RFM 中的 M）"),
    ("num_deals", "折扣购买次数", "整数", "使用折扣完成的购买次数"),
    ("num_web", "线上购买次数", "整数", "网站购买次数"),
    ("num_catalog", "目录购买次数", "整数", "邮购目录购买次数"),
    ("num_store", "门店购买次数", "整数", "线下门店购买次数"),
    ("purchase_freq", "购买频次", "整数", "三种渠道购买次数之和（RFM 中的 F）"),
    ("web_visits_month", "月均访问次数", "整数", "最近一个月访问网站次数"),
    ("accepted_total", "历史活动接受数", "整数", "前 5 次营销活动中接受的次数"),
    ("response", "本次活动响应", "0/1", "是否响应最近一次营销活动，建模标签"),
    ("complain", "是否投诉", "0/1", "近两年是否投诉过"),
]


def download() -> None:
    """优先联网下载完整数据集；失败时回退到仓库内置样本（离线可用）。"""
    if RAW_CSV.exists() and RAW_CSV.stat().st_size > 50_000:
        print(f"[skip] 原始数据已存在: {RAW_CSV}")
        return
    print(f"[get ] {SOURCE_URL}")
    try:
        req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = resp.read()
        RAW_CSV.write_bytes(data)
        print(f"[ok  ] 下载完整数据集: {RAW_CSV} ({len(data) / 1024:.0f} KB)")
    except Exception as exc:  # noqa: BLE001 - 离线环境回退到内置样本
        sample = RAW / "ifood_df_sample.csv"
        print(f"[warn] 下载失败({type(exc).__name__}: {exc})，回退内置样本 {sample.name}")
        if not sample.exists():
            raise SystemExit("既无法联网下载，也找不到内置样本文件") from exc
        shutil.copyfile(sample, RAW_CSV)
        print(f"[ok  ] 使用内置样本: {RAW_CSV} ({RAW_CSV.stat().st_size / 1024:.0f} KB)")


def pick_label(row: pd.Series, mapping: dict[str, str], default: str) -> str:
    for col, label in mapping.items():
        if col in row.index and row[col] == 1:
            return label
    return default


def build() -> pd.DataFrame:
    raw = pd.read_csv(RAW_CSV)
    raw = raw.drop_duplicates()

    df = pd.DataFrame()
    df["customer_id"] = [f"C{i:05d}" for i in range(1, len(raw) + 1)]
    df["age"] = raw["Age"].astype(int).clip(lower=18, upper=90)
    df["education"] = raw.apply(lambda r: pick_label(r, EDU_COLS, "Graduation"), axis=1)
    df["marital_status"] = raw.apply(lambda r: pick_label(r, MARITAL_COLS, "Single"), axis=1)
    df["income"] = raw["Income"].astype(float).clip(upper=raw["Income"].quantile(0.99))
    df["kidhome"] = raw["Kidhome"].astype(int)
    df["teenhome"] = raw["Teenhome"].astype(int)
    df["recency"] = raw["Recency"].astype(int)
    df["tenure_days"] = raw["Customer_Days"].astype(int)

    rename = {
        "MntWines": "mnt_wines",
        "MntFruits": "mnt_fruits",
        "MntMeatProducts": "mnt_meat",
        "MntFishProducts": "mnt_fish",
        "MntSweetProducts": "mnt_sweet",
        "MntGoldProds": "mnt_gold",
        "MntTotal": "total_spend",
    }
    for src, dst in rename.items():
        df[dst] = raw[src].astype(float)

    df["num_deals"] = raw["NumDealsPurchases"].astype(int)
    df["num_web"] = raw["NumWebPurchases"].astype(int)
    df["num_catalog"] = raw["NumCatalogPurchases"].astype(int)
    df["num_store"] = raw["NumStorePurchases"].astype(int)
    df["purchase_freq"] = df[["num_web", "num_catalog", "num_store"]].sum(axis=1)
    df["web_visits_month"] = raw["NumWebVisitsMonth"].astype(int)
    df["accepted_total"] = raw["AcceptedCmpOverall"].astype(int)
    df["response"] = raw["Response"].astype(int)
    df["complain"] = raw["Complain"].astype(int)

    bins = [0, 30, 40, 50, 60, 200]
    labels = ["18-30", "31-40", "41-50", "51-60", "60+"]
    df["age_group"] = pd.cut(df["age"], bins=bins, labels=labels).astype(str)
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.dropna(subset=["income", "total_spend"]).reset_index(drop=True)
    df["customer_id"] = [f"C{i:05d}" for i in range(1, len(df) + 1)]
    return df


def write_excel(df: pd.DataFrame) -> None:
    zh = {
        "customer_id": "客户编号", "age": "年龄", "age_group": "年龄段",
        "education": "学历", "marital_status": "婚姻状况", "income": "年收入",
        "kidhome": "小孩数", "teenhome": "青少年数", "recency": "最近购买间隔(天)",
        "tenure_days": "在网天数", "mnt_wines": "葡萄酒消费", "mnt_fruits": "水果消费",
        "mnt_meat": "肉类消费", "mnt_fish": "鱼类消费", "mnt_sweet": "甜食消费",
        "mnt_gold": "金饰消费", "total_spend": "总消费额", "num_deals": "折扣购买次数",
        "num_web": "线上购买次数", "num_catalog": "目录购买次数", "num_store": "门店购买次数",
        "purchase_freq": "购买频次", "web_visits_month": "月均访问次数",
        "accepted_total": "历史活动接受数", "response": "本次活动响应", "complain": "是否投诉",
    }
    detail = df.rename(columns=zh)
    field_df = pd.DataFrame(FIELD_DICT, columns=["字段名", "中文名", "类型", "说明"])
    source_df = pd.DataFrame(
        [
            ["数据集名称", "Customer Personality Analysis（iFood 营销活动数据）"],
            ["原始来源", "https://www.kaggle.com/datasets/imakash3011/customer-personality-analysis"],
            ["本仓库镜像", SOURCE_URL],
            ["样本量", f"{len(df)} 条客户记录，{df.shape[1]} 个字段"],
            ["时间口径", "近两年消费 + 最近一次营销活动结果"],
            ["使用说明", "仅用于教学/演示，字段含义见「字段字典」工作表"],
        ],
        columns=["项目", "内容"],
    )
    with pd.ExcelWriter(EXCEL, engine="openpyxl") as writer:
        detail.to_excel(writer, sheet_name="客户明细", index=False)
        field_df.to_excel(writer, sheet_name="字段字典", index=False)
        source_df.to_excel(writer, sheet_name="数据来源", index=False)
        for ws in writer.book.worksheets:
            for column_cells in ws.columns:
                width = max(len(str(c.value)) if c.value is not None else 8 for c in column_cells)
                ws.column_dimensions[column_cells[0].column_letter].width = min(max(width + 2, 10), 42)
    print(f"[ok  ] 写入 {EXCEL}")


def write_meta(df: pd.DataFrame) -> None:
    meta = {
        "rows": int(len(df)),
        "columns": int(df.shape[1]),
        "response_rate": round(float(df["response"].mean()), 4),
        "avg_income": round(float(df["income"].mean()), 2),
        "avg_spend": round(float(df["total_spend"].mean()), 2),
        "avg_age": round(float(df["age"].mean()), 1),
        "missing_cells": int(df.isna().sum().sum()),
        "duplicate_rows": int(df.duplicated().sum()),
        "fields": [{"name": n, "label": l, "type": t, "desc": d} for n, l, t, d in FIELD_DICT],
        "source": SOURCE_URL,
        "excel": str(EXCEL.relative_to(ROOT)).replace("\\", "/"),
    }
    META.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok  ] 写入 {META}")


def main() -> None:
    download()
    df = build()
    df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"[ok  ] 写入 {OUT_CSV}  shape={df.shape}")
    write_excel(df)
    write_meta(df)
    print(df.describe(include="all").T.head(30).to_string())
    print("响应率:", round(df["response"].mean() * 100, 2), "%")


if __name__ == "__main__":
    main()
