"""数据准备脚本：把「任意一份客户数据」加工成项目使用的标准表。

用法：
    # 1) 默认：iFood 公开数据集（自动下载，失败用仓库内置样本）
    python scripts/prepare_data.py

    # 2) 用内置的三个演示数据集
    python scripts/prepare_data.py --dataset mall     # 商场会员（200 行，无日期无金额）
    python scripts/prepare_data.py --dataset bank     # 银行电话营销名单（4119 行，有响应标记）

    # 3) 用你自己的 CSV / Excel（推荐路径）
    python scripts/prepare_data.py --file "D:\\data\\我的客户报表.xlsx" --sheet Sheet1
    python scripts/prepare_data.py --file data\\orders.csv            # 订单明细也能自动聚合

    # 4) 字段识别不准时，改 mapping.json 后重新生成
    python scripts/prepare_data.py --file xxx.csv --mapping backend/data/processed/mapping.json

产物：
    backend/data/processed/customers.csv         标准客户表（后端只读这一个）
    backend/data/processed/mapping.json          字段映射契约（可手工改）
    backend/data/processed/dataset_meta.json     字段字典 + 数据能力清单
    backend/data/processed/Customer_Insight_Report.xlsx 由 export_report.py 生成
    backend/data/raw/                           原始数据副本 + 原始数据 Excel

设计要点（换数据的核心）：
    真正的逻辑都在 backend/app/core/schema.py（数据契约层）。本脚本只负责
    「找到数据 -> 调用契约层 -> 落盘三个文件」，所以换数据的成本很低。
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.core import schema as contract  # noqa: E402

RAW = BACKEND / "data" / "raw"
PROCESSED = BACKEND / "data" / "processed"
RAW_CSV = RAW / "ifood_df.csv"
EXCEL = RAW / "Customer_Personality_Analysis.xlsx"
OUT_CSV = PROCESSED / "customers.csv"
META = PROCESSED / "dataset_meta.json"
MAPPING = PROCESSED / "mapping.json"

FIXED_TS = datetime(2026, 1, 1)
FIXED_ZIP_TS = (2026, 1, 1, 0, 0, 0)

# 三个内置数据集：都来自公开渠道，都能用 CDN 直接下载
PRESETS: dict[str, dict] = {
    "ifood": {
        "name": "iFood 营销活动客户数据（Customer Personality Analysis）",
        "desc": "巴西食品电商的客户画像与营销活动响应数据，2205 行 39 列，含收入、六品类消费额、购买渠道、历史活动响应。",
        "urls": [
            "https://cdn.jsdelivr.net/gh/nailson/ifood-data-business-analyst-test@master/ifood_df.csv",
            "https://raw.githubusercontent.com/nailson/ifood-data-business-analyst-test/master/ifood_df.csv",
        ],
        "sample": RAW / "ifood_df_sample.csv",
        "sep": ",",
        "page": "https://www.kaggle.com/datasets/imakash3011/customer-personality-analysis",
    },
    "mall": {
        "name": "商场会员消费评分（Mall Customers）",
        "desc": "200 位商场会员的年龄、性别、年收入与消费评分。没有金额、没有日期，用来演示「数据能力不全时系统怎么降级」。",
        "urls": [
            "https://cdn.jsdelivr.net/gh/NelakurthiSudheer/Mall-Customers-Segmentation@main/Dataset/Mall_Customers.csv",
        ],
        "sample": None,
        "sep": ",",
        "page": "https://www.kaggle.com/datasets/vjchoudhary7/customer-segmentation-tutorial-in-python",
    },
    "bank": {
        "name": "银行电话营销名单（Bank Marketing, UCI）",
        "desc": "4119 位银行客户的营销触达记录，含年龄段、职业、婚姻、学历、联系历史与是否认购（y）。没有金额，但有真实的正负样本。",
        "urls": [
            "https://cdn.jsdelivr.net/gh/justmarkham/DAT8@master/data/bank-additional.csv",
        ],
        "sample": None,
        "sep": ";",
        "page": "https://archive.ics.uci.edu/dataset/222/bank+marketing",
    },
}


# ---------------------------------------------------------------------------
# 读取
# ---------------------------------------------------------------------------
def _http_get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 customer-insight-agent"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - 只读公开数据
        return resp.read()


def download(preset: dict) -> pd.DataFrame:
    """多镜像下载；全部失败时回退到仓库内置样本。"""
    for url in preset["urls"]:
        try:
            data = _http_get(url)
            if len(data) < 1_000:
                print(f"[warn] 内容过短，跳过：{url}")
                continue
            frame = pd.read_csv(io.BytesIO(data), sep=preset["sep"])
            print(f"[ok] 已下载 {len(frame)} 行 × {len(frame.columns)} 列：{url}")
            return frame
        except Exception as exc:  # noqa: BLE001 - 网络环境千差万别，全部失败再回退
            print(f"[warn] 下载失败（{type(exc).__name__}）：{url}")
    sample = preset.get("sample")
    if sample and Path(sample).exists():
        print(f"[warn] 改用仓库内置样本：{Path(sample).name}")
        return pd.read_csv(sample)
    raise SystemExit("下载失败，且没有可用的内置样本。请用 --file 指定本地文件。")


def load_any(path: str, sheet: str | None, sep: str | None, encoding: str | None) -> pd.DataFrame:
    """读取本地文件：支持 csv / tsv / txt / xlsx / xls / json（读取细节见 core/loader.py）。"""
    from app.core.loader import read_any

    p = Path(path)
    if not p.exists():
        raise SystemExit(f"文件不存在：{p}")
    frame = read_any(p, sheet=sheet, sep=sep, encoding=encoding)
    used_sep = sep or ("" if p.suffix.lower() in (".xlsx", ".xls", ".xlsm", ".json") else "自动判断")
    print(f"[ok] 已读取 {p.name}：{len(frame)} 行 × {len(frame.columns)} 列（分隔符 {used_sep or '—'}）")
    return frame


# ---------------------------------------------------------------------------
# 产物
# ---------------------------------------------------------------------------
def _field_dict(df: pd.DataFrame, mapping: dict, caps: dict) -> list[dict]:
    """生成字段字典（中文名 + 类型 + 来源列 + 说明）。"""
    labels = {k: v["label"] for k, v in contract.STANDARD_FIELDS.items()}
    descs = {k: v.get("desc", "") for k, v in contract.STANDARD_FIELDS.items()}
    labels["age_group"] = "年龄段"
    descs["age_group"] = "按年龄分箱：18-30 / 31-40 / 41-50 / 51-60 / 60+"
    for key, label in caps["categories"].items():
        labels[key] = label
        descs[key] = f"品类消费额：{label}"
    for key, label in caps["channels"].items():
        labels[key] = label
        descs[key] = f"渠道购买次数：{label}"
    rows = []
    for col in df.columns:
        if col in labels:
            label, kind, desc = labels[col], _dtype(df[col]), descs.get(col, "")
        else:
            label, kind, desc = col, _dtype(df[col]), "源数据自带字段"
        rows.append({"name": col, "label": label, "type": kind, "desc": desc})
    return rows


def _dtype(series: pd.Series) -> str:
    kind = series.dtype.kind
    if kind in "ifu":
        return "number"
    if kind == "b":
        return "category"
    if kind == "M":
        return "date"
    return "category"


def write_excel(raw: pd.DataFrame, customers: pd.DataFrame, fields: list[dict], info: dict) -> None:
    """把原始数据 + 客户明细 + 字段字典写成一个可复现的 Excel。"""
    EXCEL.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(EXCEL, engine="openpyxl", datetime_format="yyyy-mm-dd") as writer:
        raw.head(5000).to_excel(writer, sheet_name="原始数据", index=False)
        customers.head(5000).to_excel(writer, sheet_name="客户明细", index=False)
        pd.DataFrame(fields).to_excel(writer, sheet_name="字段字典", index=False)
        pd.DataFrame(
            [{"项目": k, "内容": v} for k, v in info.items()]
        ).to_excel(writer, sheet_name="数据来源", index=False)
    normalize_zip_timestamps(EXCEL)


def normalize_zip_timestamps(path: Path) -> None:
    """重写 zip 条目时间戳，让同样的输入产生完全一致的字节，git 不会反复变脏。"""
    tmp = path.with_suffix(path.suffix + ".tmp")
    with zipfile.ZipFile(path, "r") as src, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            new = zipfile.ZipInfo(item.filename, date_time=FIXED_ZIP_TS)
            new.compress_type = zipfile.ZIP_DEFLATED
            new.external_attr = item.external_attr
            dst.writestr(new, data)
    tmp.replace(path)
    # docProps/core.xml 里有保存时间，一起抹平
    with zipfile.ZipFile(path, "r") as zf:
        items = {i.filename: zf.read(i.filename) for i in zf.infolist()}
    if "docProps/core.xml" in items:
        text = items["docProps/core.xml"].decode("utf-8")
        text = re.sub(r"<dcterms:modified[^>]*>[^<]*</dcterms:modified>", "<dcterms:modified>2026-01-01T00:00:00Z</dcterms:modified>", text)
        text = re.sub(r"<dcterms:created[^>]*>[^<]*</dcterms:created>", "<dcterms:created>2026-01-01T00:00:00Z</dcterms:created>", text)
        items["docProps/core.xml"] = text.encode("utf-8")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as dst:
        for name, data in items.items():
            new = zipfile.ZipInfo(name, date_time=FIXED_ZIP_TS)
            new.compress_type = zipfile.ZIP_DEFLATED
            dst.writestr(new, data)


def write_meta(df: pd.DataFrame, fields: list[dict], preset: dict, mapping: dict, ctx: dict, raw_rows: int, raw_cols: int, dup_rows: int = 0) -> dict:
    caps = ctx["capabilities"]
    meta = {
        "name": preset["name"],
        "preset": preset.get("key", "custom"),
        "source": preset["name"],
        "source_page": preset.get("page", ""),
        "desc": preset["desc"],
        "excel": EXCEL.name,
        "rows": int(len(df)),
        "columns": int(df.shape[1]),
        "raw_rows": int(raw_rows),
        "raw_columns": int(raw_cols),
        "missing_cells": int(df.isna().sum().sum()),
        "duplicate_rows": int(dup_rows),
        "generated_at": "2026-01-01（固定，保证可复现构建）",
        "fields": fields,
        # ↓ 新增：换数据后上层需要知道的事情
        "contract": {
            "grain": mapping["grain"],
            "grain_label": "订单明细（已按客户聚合）" if mapping["grain"] == "transaction" else "客户级宽表",
            "mapping": contract.describe(mapping, ctx),
            "reference_date": ctx.get("reference_date", ""),
        },
        "capabilities": caps,
        "categories": caps["categories"],
        "channels": caps["channels"],
        "warnings": ctx.get("warnings", []),
    }
    META.parent.mkdir(parents=True, exist_ok=True)
    META.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    MAPPING.write_text(
        json.dumps(
            {
                "grain": mapping["grain"],
                "mapping": mapping["mapping"],
                "transaction": mapping["transaction"],
                "dates": mapping.get("dates", {}),
                "channel_label": mapping.get("channel_label"),
                "categories": mapping["categories"],
                "channels": mapping["channels"],
                "unused_columns": mapping.get("unused_columns", []),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return meta


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="把任意客户数据加工成项目标准表")
    parser.add_argument("--dataset", choices=sorted(PRESETS), default=None, help="用内置数据集（ifood/mall/bank）")
    parser.add_argument("--file", help="本地数据文件（csv/xlsx/tsv/json），优先于 --dataset")
    parser.add_argument("--sheet", help="Excel 的 sheet 名")
    parser.add_argument("--sep", help="CSV 分隔符（默认自动判断）")
    parser.add_argument("--encoding", help="文件编码（默认 utf-8，失败自动试 gbk）")
    parser.add_argument("--mapping", help="复用 mapping.json，跳过自动识别")
    parser.add_argument("--title", help="数据集显示名称（默认用文件名）")
    parser.add_argument("--refresh", action="store_true", help="强制重新联网下载，忽略本地缓存")
    parser.add_argument("--no-excel", action="store_true", help="不生成原始数据 Excel")
    args = parser.parse_args(argv)

    PROCESSED.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)

    # 1) 拿数据
    if args.file:
        raw = load_any(args.file, args.sheet, args.sep, args.encoding)
        preset = {
            "key": "custom",
            "name": args.title or Path(args.file).stem,
            "desc": f"来自本地文件 {Path(args.file).name}",
            "page": "",
        }
    else:
        key = args.dataset or "ifood"
        preset = dict(PRESETS[key], key=key)
        cached = RAW / f"{key}.csv"
        print(f"[info] 数据集：{preset['name']}")
        if cached.exists() and not args.refresh:
            # 优先用仓库里已有的原始数据：离线环境（Docker 构建、没网）也能生成同样的结果
            raw = pd.read_csv(cached, sep=preset["sep"])
            print(f"[skip] 使用仓库内原始数据：{cached.relative_to(ROOT)}（要重新下载加 --refresh）")
        else:
            raw = download(preset)
            raw.to_csv(cached, index=False, encoding="utf-8")

    raw.columns = [str(c).strip() for c in raw.columns]
    raw = raw.dropna(how="all")
    before_rows = len(raw)
    raw = raw.drop_duplicates()
    dup_rows = before_rows - len(raw)
    if dup_rows:
        print(f"[ok] 去掉重复行 {dup_rows} 条")

    # 2) 识别字段（或复用已有契约）
    if args.mapping:
        mapping = json.loads(Path(args.mapping).read_text(encoding="utf-8"))
        print(f"[ok] 复用字段映射：{args.mapping}")
    else:
        mapping = contract.detect(raw)
        print(f"[ok] 自动识别：粒度={mapping['grain']}，匹配 {len(mapping['mapping'])} 个标准字段，"
              f"品类 {len(mapping['categories'])} 个，渠道 {len(mapping['channels'])} 个")

    # 3) 转标准表
    customers, ctx = contract.build_customers(raw, mapping)
    mins = {k: round(float(customers[k].mean()), 2) for k in ("income", "total_spend", "age") if k in customers.columns}
    print(f"[ok] customers.csv shape={customers.shape}  " + "  ".join(f"平均{k}={v}" for k, v in mins.items()))

    # 4) 落盘
    customers.to_csv(OUT_CSV, index=False, encoding="utf-8")
    if args.file:
        # 用本地文件时留一份原始副本，便于复现"当时到底喂了什么进去"
        raw.to_csv(RAW / "source_raw.csv", index=False, encoding="utf-8")
    fields = _field_dict(customers, mapping, ctx["capabilities"])
    info = {
        "数据集": preset["name"],
        "说明": preset["desc"],
        "来源页面": preset.get("page", ""),
        "原始规模": f"{len(raw)} 行 × {len(raw.columns)} 列",
        "标准表规模": f"{len(customers)} 行 × {customers.shape[1]} 列",
        "数据粒度": "订单明细（已按客户聚合）" if mapping["grain"] == "transaction" else "客户级宽表",
        "参考日期": ctx.get("reference_date", ""),
    }
    if not args.no_excel:
        write_excel(raw, customers, fields, info)
        print(f"[ok] Excel：{EXCEL.relative_to(ROOT)}")

    meta = write_meta(customers, fields, preset, mapping, ctx, len(raw), raw.shape[1], dup_rows)
    caps = meta["capabilities"]
    flags = " ".join(
        f"{k}={'✓' if caps[k] else '✗'}"
        for k in ("has_monetary", "has_recency", "has_frequency", "has_income", "has_response", "association", "propensity")
    )
    print(f"[ok] 数据能力：{flags}")
    for warn in meta["warnings"]:
        print(f"[warn] {warn}")
    print(f"[ok] 产物：{OUT_CSV.relative_to(ROOT)}、{MAPPING.relative_to(ROOT)}、{META.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
