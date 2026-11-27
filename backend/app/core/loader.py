"""文件读取层：把 CSV / Excel / JSON 读成 DataFrame。

为什么单独抽出来：
    命令行脚本（scripts/prepare_data.py）和网页上传接口（/api/import/*）
    都要读用户文件，如果各写一份，早晚会出现「命令行能读、页面读不了」的问题。
    这里统一处理分隔符嗅探、编码回退、Excel 多 sheet，两边共用同一套逻辑。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

EXCEL_SUFFIXES = {".xlsx", ".xlsm", ".xls"}
JSON_SUFFIXES = {".json"}
TEXT_SUFFIXES = {".csv", ".tsv", ".txt", ".dat"}

SUPPORTED = EXCEL_SUFFIXES | JSON_SUFFIXES | TEXT_SUFFIXES


def is_supported(path: str | Path) -> bool:
    return Path(path).suffix.lower() in SUPPORTED


def sheet_names(path: str | Path) -> list[str]:
    """Excel 返回全部 sheet 名；其他格式返回空列表。"""
    p = Path(path)
    if p.suffix.lower() not in EXCEL_SUFFIXES:
        return []
    try:
        with pd.ExcelFile(p, engine="openpyxl") as book:
            return [str(name) for name in book.sheet_names]
    except Exception:  # noqa: BLE001 - 老 .xls 或损坏文件，交给 read_any 报具体错误
        return []


def sniff_sep(path: str | Path, encoding: str | None = None) -> str:
    """猜分隔符：分号 / 制表符 / 逗号 三者取出现次数最多的。"""
    p = Path(path)
    try:
        head = p.read_text(encoding=encoding or "utf-8", errors="ignore")[:4096]
    except Exception:  # noqa: BLE001
        return ","
    counts = {";": head.count(";"), "\t": head.count("\t"), ",": head.count(",")}
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else ","


def read_any(
    path: str | Path,
    sheet: str | int | None = None,
    sep: str | None = None,
    encoding: str | None = None,
    nrows: int | None = None,
) -> pd.DataFrame:
    """读取任意支持的表格文件，返回 DataFrame（不做任何字段改名）。"""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"文件不存在：{p}")
    suffix = p.suffix.lower()

    if suffix in EXCEL_SUFFIXES:
        return pd.read_excel(p, sheet_name=sheet if sheet not in (None, "") else 0, engine="openpyxl", nrows=nrows)

    if suffix in JSON_SUFFIXES:
        frame = pd.read_json(p)
        return frame.head(nrows) if nrows else frame

    if suffix == ".tsv" and not sep:
        sep = "\t"
    sep = sep or sniff_sep(p, encoding)
    try:
        return pd.read_csv(p, sep=sep, encoding=encoding or "utf-8", nrows=nrows)
    except UnicodeDecodeError:
        return pd.read_csv(p, sep=sep, encoding=encoding or "gbk", nrows=nrows)
    except pd.errors.ParserError:
        # 分隔符猜错时最常见的报错，退回 python 引擎自动嗅探
        return pd.read_csv(p, sep=None, engine="python", encoding=encoding or "utf-8", nrows=nrows)
