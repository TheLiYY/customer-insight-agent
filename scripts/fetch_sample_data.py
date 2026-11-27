"""下载三份市面上的真实客户/销售数据，用于测试「上传我的数据」这条链路。

用法：
    python scripts/fetch_sample_data.py            # 全部下载到 test-data/
    python scripts/fetch_sample_data.py --only superstore

三份数据的用途：
    superstore_sales.csv  零售订单明细（订单号/日期/金额/品类/客户名）——最接近门店与电商的销售表
    online_retail.csv     英国电商 54 万行交易明细（只有数量×单价，没有金额列）——压力测试
    telco_customers.csv   运营商客户级宽表（在网时长/月费/累计费用/是否流失）——客户级 CRM 表
"""

from __future__ import annotations

import io
import sys
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "test-data"

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122 Safari/537.36"
}

SOURCES = {
    "online_retail": "https://archive.ics.uci.edu/static/public/352/online+retail.zip",
    "superstore": "https://cdn.jsdelivr.net/gh/curran/data@gh-pages/superstoreSales/superstoreSales.csv",
    "telco": "https://cdn.jsdelivr.net/gh/visharadsingh/telco_customer_churn_analysis@main/"
    "WA_Fn-UseC_-Telco-Customer-Churn.csv",
}


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=180) as resp:
        return resp.read()


def save_superstore() -> None:
    df = pd.read_csv(io.BytesIO(fetch(SOURCES["superstore"])), encoding="latin-1")
    df.to_csv(OUT / "superstore_sales.csv", index=False, encoding="utf-8")
    print(f"[ok] superstore_sales.csv   {df.shape[0]} 行 x {df.shape[1]} 列（零售订单明细）")


def save_telco() -> None:
    df = pd.read_csv(io.BytesIO(fetch(SOURCES["telco"])), encoding="utf-8")
    df.to_csv(OUT / "telco_customers.csv", index=False, encoding="utf-8")
    print(f"[ok] telco_customers.csv    {df.shape[0]} 行 x {df.shape[1]} 列（客户级宽表）")


def save_online_retail() -> None:
    raw = fetch(SOURCES["online_retail"])
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        name = next(n for n in zf.namelist() if n.endswith(".xlsx"))
        payload = zf.read(name)
    df = pd.read_excel(io.BytesIO(payload), sheet_name="Online Retail")
    df.to_csv(OUT / "online_retail.csv", index=False, encoding="utf-8")
    print(f"[ok] online_retail.csv      {df.shape[0]} 行 x {df.shape[1]} 列（交易明细，文件约 48MB）")


TASKS = {"superstore": save_superstore, "telco": save_telco, "online_retail": save_online_retail}


def main() -> None:
    OUT.mkdir(exist_ok=True)
    if "--only" in sys.argv:
        key = sys.argv[sys.argv.index("--only") + 1]
        TASKS[key]()
        return
    for task in TASKS.values():
        try:
            task()
        except Exception as exc:  # noqa: BLE001
            print(f"[fail] {exc}")
    print(f"\n文件已放到 {OUT}")


if __name__ == "__main__":
    main()
