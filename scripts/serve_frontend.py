"""只用一个标准库启动「前端 + 反向代理」的小服务器（不需要 Node、不需要 Nginx）。

用途：答辩/演示时如果机器上没装 Node，也能把已经构建好的 frontend/dist 跑起来，
并且把 /api 请求转发给 8000 端口的 FastAPI，避免跨域配置。

用法：
    python scripts/serve_frontend.py            # 打开 http://127.0.0.1:5173
    python scripts/serve_frontend.py --port 8080 --backend http://127.0.0.1:8000

注意：生产环境建议用 Nginx 托管 dist 并反代 /api，这个脚本只是「单文件演示用」。
"""
from __future__ import annotations

import argparse
import http.client
import json
import mimetypes
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "frontend" / "dist"


class Handler(SimpleHTTPRequestHandler):
    backend = "http://127.0.0.1:8000"
    dist = DIST

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(self.dist), **kwargs)

    # ---------------- 反代 /api ----------------
    def _proxy(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        target = f"{self.backend}{parsed.path}"
        if parsed.query:
            target += f"?{parsed.query}"

        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None

        req = urllib.request.Request(target, data=body, method=self.command)
        for key in ("Content-Type", "Accept"):
            if self.headers.get(key):
                req.add_header(key, self.headers[key])

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                payload = resp.read()
                self.send_response(resp.status)
                ctype = resp.headers.get("Content-Type", "application/json")
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
        except urllib.error.HTTPError as exc:
            payload = exc.read()
            self.send_response(exc.code)
            self.send_header("Content-Type", exc.headers.get("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except (urllib.error.URLError, http.client.HTTPException, OSError) as exc:
            payload = json.dumps(
                {"detail": f"后端未启动或不可达：{self.backend}（{exc}）"}, ensure_ascii=False
            ).encode("utf-8")
            self.send_response(502)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802 - 标准库要求的方法名
        if self.path.startswith("/api/"):
            return self._proxy()
        path = urllib.parse.urlparse(self.path).path
        file_path = self.dist / path.lstrip("/")
        # SPA 路由回退：找不到文件时统一返回 index.html
        if path != "/" and not file_path.exists():
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        if self.path.startswith("/api/"):
            return self._proxy()
        self.send_error(405)

    def end_headers(self) -> None:
        # 本地演示禁用缓存，改完代码刷新就能看到
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        if "/api/" in (self.path or ""):
            sys.stderr.write(f"[api] {fmt % args}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="托管 frontend/dist 并反代 /api 到后端")
    parser.add_argument("--port", type=int, default=5173)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--backend", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    if not DIST.exists():
        raise SystemExit(
            "找不到 frontend/dist，请先构建前端：\n"
            "  cd frontend && npm install && npm run build\n"
            "或开发模式直接跑：cd frontend && npm run dev"
        )

    Handler.backend = args.backend.rstrip("/")
    mimetypes.add_type("application/javascript", ".js")
    mimetypes.add_type("text/css", ".css")

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"前端静态站点: http://{args.host}:{args.port}")
    print(f"API 反向代理: /api -> {Handler.backend}/api")
    print("Ctrl+C 退出")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
