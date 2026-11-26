"""本地启动脚本：python backend/run.py（等价于 uvicorn app.main:app）。

依赖装在项目的 .venv 里（见 README 的「环境准备」），无需额外设置 PYTHONPATH。
端口可以用环境变量改：BACKEND_HOST / BACKEND_PORT（默认 127.0.0.1:8000）。
"""
from __future__ import annotations

import os
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
    host = os.environ.get("BACKEND_HOST", "127.0.0.1")
    port = int(os.environ.get("BACKEND_PORT", "8000"))
    uvicorn.run("app.main:app", host=host, port=port, reload=False, log_level="info")
