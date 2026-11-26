"""导出 OpenAPI 描述文件，供 Apifox / Postman / Swagger UI 导入。

产物：
- docs/openapi.json     完整的 OpenAPI 3.1 描述（Apifox「导入 → OpenAPI/Swagger」直接选它）
- docs/API.postman.json Postman Collection v2.1（Postman「Import」直接选它）

用法：
    python scripts/export_openapi.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

DOCS = ROOT / "docs"
DOCS.mkdir(exist_ok=True)

# 每个接口一条示例，导入后可以直接点「发送」看到真实数据
EXAMPLES: dict[tuple[str, str], dict] = {
    ("get", "/api/agent/chat"): {"message": "分析完之后有什么结论和建议？", "history": []},
    ("post", "/api/campaign/plan"): {
        "segment": "核心高价值客群",
        "budget": 2000,
        "cost_per_contact": 8,
        "discount": 0.1,
    },
}


def group_of(path: str) -> str:
    """给接口分组，导入 Apifox 后是整齐的目录树。"""
    rules = [
        ("/api/agent", "Agent 对话"),
        ("/api/campaign", "营销方案"),
        ("/api/customers", "客户明细"),
        ("/api/propensity", "响应预测"),
        ("/api/segments", "RFM 分层"),
        ("/api/personas", "客户画像"),
        ("/api/clusters", "客户画像"),
        ("/api/association", "品类结构"),
        ("/api/insights", "自动结论"),
        ("/api/overview", "数据总览"),
        ("/api/dataset", "基础信息"),
        ("/api/health", "基础信息"),
    ]
    for prefix, name in rules:
        if path.startswith(prefix):
            return name
    return "其他"


def main() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    schema = app.openapi()
    schema["info"]["description"] = (
        "客户画像 · 精准推送 · 个性化营销策略。\n\n"
        "本地启动后可直接浏览 /docs（Swagger UI）；"
        "本文件用于导入 Apifox / Postman。"
    )
    out = DOCS / "openapi.json"
    out.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] {out} ({out.stat().st_size / 1024:.1f} KB)")

    # ---- 生成 Postman Collection v2.1 ----
    client = TestClient(app)
    items: list[dict] = []
    groups: dict[str, list[dict]] = {}
    for path, methods in schema.get("paths", {}).items():
        for method, op in methods.items():
            if method.lower() not in {"get", "post"}:
                continue
            tag = group_of(path)
            url_path = path.replace("{", ":").replace("}", "")
            # 路径参数给个能用的示例值
            if ":name" in url_path:
                url_path = url_path.replace(":name", "核心高价值客群")
            if ":customer_id" in url_path:
                url_path = url_path.replace(":customer_id", "C00001")

            request: dict = {
                "method": method.upper(),
                "header": [],
                "url": {
                    "raw": f"{{{{base_url}}}}{url_path}",
                    "host": ["{{base_url}}"],
                    "path": [p for p in url_path.split("/") if p],
                },
                "description": op.get("summary") or op.get("description") or "",
            }

            params = op.get("parameters") or []
            query = [p for p in params if p.get("in") == "query"]
            if query:
                qs = [{"key": p["name"], "value": "", "description": p.get("description", "")} for p in query]
                request["url"]["query"] = qs
                request["url"]["raw"] += "?" + "&".join(f"{q['key']}={q['value']}" for q in qs)

            body = EXAMPLES.get((method.lower(), path))
            if body:
                request["header"].append({"key": "Content-Type", "value": "application/json"})
                request["body"] = {"mode": "raw", "raw": json.dumps(body, ensure_ascii=False, indent=2)}
                request["url"]["raw"] = request["url"]["raw"].split("?")[0]
                request["url"].pop("query", None)

            item = {
                "name": op.get("summary") or f"{method.upper()} {path}",
                "request": request,
                "response": [],
            }
            groups.setdefault(tag, []).append(item)

    for tag, its in groups.items():
        items.append({"name": tag, "item": its})

    collection = {
        "info": {
            "name": "Customer Insight Agent API",
            "description": "客户画像 / 精准推送 / 个性化营销策略 后端接口",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "variable": [{"key": "base_url", "value": "http://127.0.0.1:8000"}],
        "item": items,
    }
    out2 = DOCS / "API.postman.json"
    out2.write_text(json.dumps(collection, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] {out2} ({out2.stat().st_size / 1024:.1f} KB)")

    # 顺手验证：导出后仍能正常请求（避免「文档是旧的」这种事故）
    r = client.get("/api/health")
    assert r.status_code == 200, r.text
    print(f"[ok] 接口自检 health={r.json()['status']} customers={r.json()['customers']}")


if __name__ == "__main__":
    main()
