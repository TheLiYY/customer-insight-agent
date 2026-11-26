"""本地启动脚本：python backend/run.py（等价于 uvicorn app.main:app）。

依赖装在项目的 .venv 里（见 README 的「环境准备」），无需额外设置 PYTHONPATH。
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

try:
    import uvicorn  # noqa: F401
except ModuleNotFoundError:  # 给出人话提示，而不是一串 ModuleNotFoundError
    sys.exit(
        "未找到 uvicorn。请先激活虚拟环境：\n"
        r"  D:\projects\customer-insight-agent\.venv\Scripts\activate" "\n"
        "或直接安装依赖：\n"
        "  python -m pip install -r backend/requirements.txt"
    )

if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import uvicorn  # noqa: E402

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False, log_level="info")
