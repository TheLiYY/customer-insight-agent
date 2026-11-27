"""数据导入接口：在网页上直接上传一份客户表格，整套分析立刻换成这份数据。

流程分两步，故意的：
    1. POST /api/import/inspect  —— 先「试读」：只解析不落盘，把自动识别结果、
       数据能力、预警、前几行样本返回给前端，让用户确认「系统认对了没有」；
    2. POST /api/import/apply    —— 用户点确认后才真正重建标准表并刷新所有分析。

这样即使识别错了（比如把「年收入」认成了「月收入」），也只是预览错，
不会把线上正在用的数据覆盖掉。

真正干活的是 scripts/prepare_data.py（命令行和页面共用同一条流水线），
这里只负责：收文件 → 校验 → 调脚本 → 让缓存失效。
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel

from ..core import schema as contract
from ..core.config import DATA_DIR, PROJECT_DIR
from ..core.dataset import capabilities as dataset_capabilities
from ..core.loader import is_supported, read_any, sheet_names
from ..core.store import store

router = APIRouter(prefix="/api/import", tags=["数据导入"])

UPLOADS_DIR = DATA_DIR / "uploads"
MAX_BYTES = 40 * 1024 * 1024  # 40MB，客户级宽表足够用了
KEEP_FILES = 30
_LOCK = threading.Lock()  # 同一时间只允许一个导入任务，避免两次重建互相覆盖

PRESET_LABELS = {
    "ifood": "iFood 营销活动客户数据（2205 行）",
    "mall": "商场会员消费评分（200 行）",
    "bank": "银行电话营销名单（4119 行）",
}


# ---------------------------------------------------------------- 工具函数
def _safe_name(name: str) -> str:
    """只保留文件名本身，去掉路径与危险字符（防目录穿越 / Windows 保留字符）。"""
    base = Path(str(name or "upload")).name
    cleaned = "".join(ch if (ch.isalnum() or ch in "._-") else "_" for ch in base)
    cleaned = cleaned.strip("._") or "upload"
    return cleaned[-80:]


def _store_upload(file: UploadFile, payload: bytes) -> Path:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = UPLOADS_DIR / f"{stamp}_{_safe_name(file.filename)}"
    target.write_bytes(payload)
    _prune_uploads()
    return target


def _prune_uploads() -> None:
    files = sorted(UPLOADS_DIR.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[KEEP_FILES:]:
        try:
            old.unlink()
        except OSError:
            pass


def _resolve(token: str) -> Path:
    """把前端回传的文件名还原成上传目录内的真实路径。"""
    name = _safe_name(token)
    path = UPLOADS_DIR / name
    if not path.exists():
        raise HTTPException(status_code=404, detail="上传的文件已不存在，请重新上传")
    return path


def _cell(value: Any) -> Any:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    if isinstance(value, (int, float, bool)):
        return value
    return str(value)


def _table(frame: pd.DataFrame, limit: int = 6) -> dict[str, Any]:
    head = frame.head(limit)
    return {
        "columns": [str(c) for c in head.columns],
        "rows": [[_cell(v) for v in row] for row in head.itertuples(index=False, name=None)],
        "total_rows": int(len(frame)),
    }


def _summary() -> dict[str, Any]:
    """读当前生效的数据集，给前端刷新用。"""
    meta = store.meta
    caps = dataset_capabilities()
    return {
        "name": meta.get("source", ""),
        "source_page": meta.get("source_page", ""),
        "desc": meta.get("desc", ""),
        "rows": int(len(store.df)),
        "columns": int(store.df.shape[1]),
        "raw_rows": int(meta.get("raw_rows", 0)),
        "raw_columns": int(meta.get("raw_columns", 0)),
        "grain": meta.get("contract", {}).get("grain_label", ""),
        "reference_date": meta.get("contract", {}).get("reference_date", ""),
        "capabilities": caps,
        "warnings": meta.get("warnings", []),
        "generated_at": meta.get("generated_at", ""),
    }


def _run_prepare(args: list[str], timeout: int = 300) -> dict[str, Any]:
    """调用命令行流水线重建标准表。命令行与页面共用同一份实现，避免两套逻辑。"""
    script = PROJECT_DIR / "scripts" / "prepare_data.py"
    if not script.exists():
        raise HTTPException(status_code=500, detail=f"找不到数据脚本：{script}")

    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    started = time.perf_counter()
    try:
        proc = subprocess.run(  # noqa: S603 - 参数由服务端拼装，不含用户可控字符串
            [sys.executable, str(script), *args],
            cwd=str(PROJECT_DIR),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail=f"处理超时（{timeout}s），请换一份更小的数据试试") from exc

    log = [line for line in (proc.stdout or "").splitlines() if line.strip()]
    if proc.returncode != 0:
        tail = "\n".join(log[-8:]) or (proc.stderr or "")[-800:]
        raise HTTPException(status_code=400, detail=f"数据重建失败：\n{tail}")
    return {"took_ms": int((time.perf_counter() - started) * 1000), "log": log[-12:]}


def _warm() -> None:
    """导入完成后后台预热一次，用户点进页面时不用等。"""
    try:
        _ = store.overview, store.cluster, store.propensity, store.insights
    except Exception:  # noqa: BLE001 - 预热失败不影响主流程
        pass


def _refresh() -> dict[str, Any]:
    store.reload()
    summary = _summary()
    threading.Thread(target=_warm, daemon=True).start()
    return summary


# ---------------------------------------------------------------- 试读
@router.post("/inspect")
async def inspect(file: UploadFile = File(...), sheet: str | None = Form(default=None)) -> dict[str, Any]:
    """只解析不落盘：告诉用户「这份表我认出了什么」。"""
    if not is_supported(file.filename or ""):
        raise HTTPException(
            status_code=400,
            detail="只支持 .xlsx / .xls / .csv / .tsv / .json，Excel 请另存为 xlsx 后重试",
        )
    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="文件是空的")
    if len(payload) > MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"文件超过 {MAX_BYTES // 1024 // 1024}MB，请先精简后再传")

    path = _store_upload(file, payload)
    sheets = sheet_names(path)

    try:
        frame = read_any(path, sheet=sheet, nrows=None)
    except Exception as exc:  # noqa: BLE001 - 用户文件千奇百怪，统一转成可读报错
        raise HTTPException(status_code=400, detail=f"文件读不出来：{type(exc).__name__}: {exc}") from exc

    frame.columns = [str(c).strip() for c in frame.columns]
    frame = frame.dropna(how="all")
    before = len(frame)
    frame = frame.drop_duplicates()
    dropped = before - len(frame)
    if frame.empty:
        raise HTTPException(status_code=400, detail="这张表没有数据行（可能选错了 sheet）")

    try:
        mapping = contract.detect(frame)
        customers, ctx = contract.build_customers(frame, mapping)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"字段识别失败：{type(exc).__name__}: {exc}") from exc

    described = contract.describe(mapping, ctx)
    caps = ctx["capabilities"]
    return {
        "file": path.name,
        "name": Path(file.filename or path.name).name,
        "size": len(payload),
        "sheets": sheets,
        "sheet": sheet or (sheets[0] if sheets else ""),
        "raw_rows": int(before),
        "raw_columns": int(frame.shape[1]),
        "dropped_duplicates": int(dropped),
        "grain": described["grain"],
        "grain_label": described["grain_label"],
        "output_rows": int(len(customers)),
        "output_columns": int(customers.shape[1]),
        "output_columns_list": [str(c) for c in customers.columns],
        "matched": len(mapping["mapping"]),
        "mapping": described["rows"],
        "unused_columns": described["unused_columns"],
        "categories": [{"key": k, "name": v} for k, v in caps["categories"].items()],
        "channels": [{"key": k, "name": v} for k, v in caps["channels"].items()],
        "capabilities": caps,
        "warnings": described["warnings"],
        "reference_date": ctx.get("reference_date", ""),
        "preview": _table(frame),
        "output_preview": _table(customers),
        "columns_dropped": described["unused_columns"],
    }


# ---------------------------------------------------------------- 应用
class ApplyRequest(BaseModel):
    file: str
    sheet: str | None = None
    sep: str | None = None
    encoding: str | None = None


@router.post("/apply")
def apply(req: ApplyRequest) -> dict[str, Any]:
    """确认导入：重建标准表 → 刷新所有分析 → 返回新数据集概况。"""
    path = _resolve(req.file)
    title = path.name.split("_", 2)[-1] if "_" in path.name else path.name
    args = ["--file", str(path), "--title", title]
    if req.sheet:
        args += ["--sheet", req.sheet]
    if req.sep:
        args += ["--sep", req.sep]
    if req.encoding:
        args += ["--encoding", req.encoding]

    with _LOCK:
        result = _run_prepare(args)
        summary = _refresh()
    return {"ok": True, **result, "dataset": summary}


# ---------------------------------------------------------------- 模板下载
TEMPLATE_HEADERS = {
    "客户级宽表": [
        "客户编号", "客户姓名", "年龄", "性别", "收入", "学历", "婚姻状况", "子女数",
        "最近消费日期", "注册日期", "累计消费", "购买次数", "优惠次数", "月访问次数",
        "是否响应", "是否投诉",
    ],
    "订单明细": [
        "订单号", "客户编号", "下单时间", "订单金额", "数量", "单价", "商品品类", "渠道", "年龄", "性别",
    ],
}


@router.get("/template")
def download_template() -> Response:
    """下载一份字段模板（xlsx）。

    真实客户数据通常不是这个格式，这个模板的作用是「告诉用户哪些字段有用、长什么样」，
    用户可以照着改自己的表头，也可以完全不用它——系统是自动识别列名的。
    """
    from io import BytesIO

    from openpyxl import Workbook

    wb = Workbook()
    first = True
    for title, headers in TEMPLATE_HEADERS.items():
        ws = wb.active if first else wb.create_sheet()
        first = False
        ws.title = title
        ws.append(headers)
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.fill = PatternFill("solid", fgColor="E8EEFF")
        if title == "客户级宽表":
            ws.append([
                "C0001", "张三", 34, "女", 18000, "本科", "已婚", 1,
                "2025-11-02", "2023-03-18", 5280.5, 12, 3, 9, 1, 0,
            ])
        else:
            ws.append(["SO20251102001", "C0001", "2025-11-02", 399.0, 2, 199.5, "葡萄酒", "线上商城", 34, "女"])
        for idx, col in enumerate(headers, start=1):
            ws.column_dimensions[get_column_letter(idx)].width = max(10, min(22, len(col) * 2.4))

    notes = wb.create_sheet("填写说明")
    for line in [
        ["CustLens 数据模板说明"],
        ["1", "两张表二选一：一张客户级宽表（一行一个客户），或一张订单明细（一行一笔订单，系统自动按客户汇总）。"],
        ["2", "列名可以不一样：中英文、带空格、常见叫法（收入/年收入/月薪、最近消费时间/上次购买时间）都能自动认出来。"],
        ["3", "必备：能定位到客户的编号列。有金额或消费次数，才能做 RFM 与价值分层。"],
        ["4", "想要「响应预测」：需要一列历史活动结果（是否响应/是否购买/y、yes/no）。没有这一列，其他分析照常可用。"],
        ["5", "日期列请写成 2025-11-02 或 2025/11/2；金额可以带 ¥ 和千分位，系统会自动清洗。"],
        ["6", "手机号、姓名、地址这类隐私列可以保留，系统不会把它们用于建模，也不会上传到任何第三方。"],
    ]:
        notes.append(line)
    notes.column_dimensions["A"].width = 8
    notes.column_dimensions["B"].width = 110

    buffer = BytesIO()
    wb.save(buffer)
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="custlens-data-template.xlsx"'},
    )


# ---------------------------------------------------------------- 演示数据 / 重置
class PresetRequest(BaseModel):
    dataset: str = "ifood"


@router.post("/preset")
def load_preset(req: PresetRequest) -> dict[str, Any]:
    """切回内置数据集，或直接载入演示数据（mall / bank）。"""
    key = (req.dataset or "ifood").strip().lower()
    if key not in PRESET_LABELS:
        raise HTTPException(status_code=400, detail=f"未知数据集：{req.dataset}，可选 {', '.join(PRESET_LABELS)}")
    with _LOCK:
        result = _run_prepare(["--dataset", key])
        summary = _refresh()
    return {"ok": True, **result, "dataset": summary, "label": PRESET_LABELS[key]}


@router.get("/presets")
def presets() -> dict[str, Any]:
    return {"presets": [{"key": k, "label": v} for k, v in PRESET_LABELS.items()]}


# ---------------------------------------------------------------- 历史与当前
@router.get("/history")
def history() -> dict[str, Any]:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    items = []
    for path in sorted(UPLOADS_DIR.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)[:20]:
        stat = path.stat()
        items.append(
            {
                "file": path.name,
                "name": path.name.split("_", 2)[-1],
                "size": stat.st_size,
                "uploaded_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                "sheets": sheet_names(path),
            }
        )
    meta = store.meta
    return {
        "uploads": items,
        "current": {
            "name": meta.get("source", ""),
            "rows": int(len(store.df)),
            "columns": int(store.df.shape[1]),
            "grain": meta.get("contract", {}).get("grain_label", ""),
        },
        "limits": {"max_mb": MAX_BYTES // 1024 // 1024, "keep": KEEP_FILES},
    }
