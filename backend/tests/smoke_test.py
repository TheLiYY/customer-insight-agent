"""端到端冒烟测试：不启动服务器，直接用 TestClient 跑一遍所有接口。

用法：python backend/tests/smoke_test.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

CASES = [
    ("GET", "/api/health", None),
    ("GET", "/api/dataset", None),
    ("GET", "/api/overview", None),
    ("GET", "/api/insights", None),
    ("GET", "/api/insights?severity=risk", None),
    ("GET", "/api/segments", None),
    ("GET", "/api/personas", None),
    ("GET", "/api/propensity", None),
    ("GET", "/api/association", None),
    ("GET", "/api/customers?size=3", None),
    ("GET", "/api/campaign/options", None),
    ("GET", "/api/agent/suggestions", None),
    ("GET", "/api/clusters/elbow?k_max=6", None),
]


def main() -> int:
    started = time.time()
    client = TestClient(app)
    failed = 0
    for method, path, payload in CASES:
        try:
            resp = client.request(method, path, json=payload)
            ok = resp.status_code == 200
            head = resp.text[:110].replace("\n", " ")
            print(f"{'PASS' if ok else 'FAIL'} {resp.status_code} {path} ({len(resp.text)}B) {head}")
            failed += 0 if ok else 1
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL {path} -> {type(exc).__name__}: {exc}")
            failed += 1

    # 对话链路
    for message in [
        "先看看整体数据情况",
        "分析完之后有什么结论和建议？",
        "客户按 RFM 怎么分层？",
        "帮我看看客户画像",
        "预测一下哪些客户最可能响应下次活动",
        "给核心高价值客群生成一个营销方案，预算 20000",
        "哪些品类有关联？",
        "查一下客户 C00001 的画像",
    ]:
        resp = client.post("/api/agent/chat", json={"message": message, "history": []})
        ok = resp.status_code == 200
        body = resp.json() if ok else {}
        blocks = len(body.get("blocks", []))
        print(f"{'PASS' if ok and blocks else 'FAIL'} chat[{message[:18]}] -> intent={body.get('intent')} blocks={blocks}")
        failed += 0 if (ok and blocks) else 1

    print(f"\n完成，用时 {time.time() - started:.2f}s，失败 {failed} 项")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
