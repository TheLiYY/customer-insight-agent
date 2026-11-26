"""Agent 编排：把一句人话变成「调哪个工具 + 参数是什么 + 怎么总结」。

两种模式：
- 在线模式：接 OpenAI 兼容接口，用 function calling 让大模型自己选工具（需要配置 LLM_BASE_URL/LLM_API_KEY）；
- 离线模式：关键词规则匹配。没有 API Key 也能跑通全流程，答辩演示更稳。
"""
from __future__ import annotations

import json
import re
from typing import Any

from . import tools
from ..core.config import settings
from ..core.store import store

# 关键词 → 工具。越靠前优先级越高。
INTENTS: list[dict[str, Any]] = [
    {
        "tool": "insights_report",
        "keywords": ["结论", "洞察", "自动分析", "总结", "发现", "下一步", "怎么办", "建议", "该做什么", "分析完", "怎么看"],
    },
    {
        "tool": "campaign_plan",
        "keywords": ["方案", "推送", "营销", "活动", "投放", "触达", "话术", "预算", "促销", "怎么卖"],
    },
    {
        "tool": "propensity_report",
        "keywords": ["预测", "谁会", "谁会买", "响应", "概率", "转化", "打分", "名单", "该推给谁", "买账"],
    },
    {
        "tool": "customer_profile",
        "keywords": ["单个客户", "客户详情", "这位客户是谁"],
    },
    {
        "tool": "persona_report",
        "keywords": ["画像", "人群", "客群", "标签", "聚类", "长什么样", "用户特征", "分群"],
    },
    {
        "tool": "segment_report",
        "keywords": ["分层", "rfm", "价值", "重要", "等级", "八类", "客户分类"],
    },
    {
        "tool": "category_report",
        "keywords": ["品类", "关联", "交叉销售", "买什么", "商品", "组合"],
    },
    {
        "tool": "overview_report",
        "keywords": ["总览", "整体", "概况", "大盘", "数据", "怎么样", "多少"],
    },
]

SEGMENT_ALIASES = {
    "高价值": "核心高价值客群",
    "核心": "核心高价值客群",
    "忠诚": "稳定贡献客群",
    "稳定": "稳定贡献客群",
    "潜力": "潜力成长客群",
    "成长": "潜力成长客群",
    "长尾": "长尾基础客群",
    "基础": "长尾基础客群",
    "边缘": "边缘低频客群",
    "沉睡": "长尾基础客群",
    "流失": "长尾基础客群",
}


def _detect_tool(message: str) -> str:
    text = message.lower()
    # 句子里出现了客户编号，说明问的是「某一个人」，直接查明细
    if re.search(r"c\d{3,6}", text, re.IGNORECASE):
        return "customer_profile"
    best, best_score = "overview_report", 0
    for intent in INTENTS:
        score = sum(1 for kw in intent["keywords"] if kw.lower() in text)
        if score > best_score:
            best, best_score = intent["tool"], score
    return best


def _extract_budget(message: str) -> float | None:
    m = re.search(r"(?:预算|花费|投入)\D{0,4}(\d+(?:\.\d+)?)\s*(万|w|W|元|块)?", message)
    if not m:
        m = re.search(r"(\d+(?:\.\d+)?)\s*(万|w|W)\b", message)
    if not m:
        return None
    value = float(m.group(1))
    unit = (m.group(2) or "") if m.lastindex and m.lastindex >= 2 else ""
    if unit in {"万", "w", "W"}:
        value *= 10000
    return value if value > 0 else None


def _extract_segment(message: str) -> str | None:
    names = [p["name"] for p in store.personas] + [s["name"] for s in store.segment_summary]
    for name in names:
        if name in message:
            return name
    for alias, target in SEGMENT_ALIASES.items():
        if alias in message:
            if target in names:
                return target
    return None


def _extract_customer(message: str) -> str | None:
    m = re.search(r"(C\d{3,6})", message, re.IGNORECASE)
    return m.group(1).upper() if m else None


def _reply_for(tool_name: str, args: dict, blocks: list[dict]) -> str:
    """给规则模式配一句人话开场白，让前端看起来像在对话。"""
    intro = {
        "overview_report": "这是当前客户资产的整体情况：",
        "segment_report": "我按 RFM 把客户拆成了 8 个层级，优先级从上到下：",
        "persona_report": "基于消费行为和人口属性，客户可以聚成几类清晰的画像：",
        "propensity_report": "我训练了一个响应预测模型，按「会不会买单」给每位客户排了序：",
        "campaign_plan": "方案已经生成，圈人、选品、渠道、话术和 ROI 都在下面：",
        "category_report": "品类结构和关联关系如下，可以拿来做交叉销售：",
        "customer_profile": "这位客户的画像如下：",
        "insights_report": "我把所有分析跑完之后，自动整理出这些结论：",
    }.get(tool_name, "分析结果如下：")

    tail = ""
    if tool_name == "campaign_plan" and args.get("segment"):
        tail = f"（目标客群：{args['segment']}）"
    return intro + tail


def rule_chat(message: str, history: list[dict] | None = None) -> dict[str, Any]:
    """离线模式：关键词选工具 → 执行 → 拼装回复。"""
    tool_name = _detect_tool(message)
    args: dict[str, Any] = {}

    segment = _extract_segment(message)
    budget = _extract_budget(message)

    if tool_name == "campaign_plan":
        args["segment"] = segment or (store.personas[0]["name"] if store.personas else "")
        if budget:
            args["budget"] = budget
    elif tool_name == "persona_report":
        if segment:
            args["name"] = segment
    elif tool_name == "customer_profile":
        args["customer_id"] = _extract_customer(message) or store.enriched.iloc[0]["customer_id"]
    elif tool_name == "propensity_report" and budget:
        args["budget"] = budget

    blocks = tools.TOOLS[tool_name](args) if tool_name in tools.TOOLS else [tools.text("暂时没有这个能力。")]

    return {
        "reply": _reply_for(tool_name, args, blocks),
        "blocks": blocks,
        "intent": tool_name,
        "args": args,
        "mode": "rules",
    }


# ------------------------------------------------------------------ 在线模式
def _tool_schema() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": spec["name"],
                "description": spec["description"],
                "parameters": {
                    "type": "object",
                    "properties": {
                        key: {"type": "string", "description": desc}
                        for key, desc in spec["params"].items()
                    },
                    "required": [],
                },
            },
        }
        for spec in tools.public_specs()
    ]


SYSTEM_PROMPT = (
    "你是一位资深的数据分析师兼增长运营专家，服务于一家食品零售商的营销团队。\n"
    "你的任务是根据用户问题，调用合适的工具拿到真实数据，再用中文给出结论和可执行建议。\n"
    "要求：\n"
    "1. 必须调用工具获取数据，不要凭空编造数字；\n"
    "2. 回答控制在 4 句话以内，先给结论，再给动作；\n"
    "3. 涉及营销时，说清楚「推给谁、推什么、什么时候推、怎么推、预期效果」。"
)


def llm_chat(message: str, history: list[dict] | None = None) -> dict[str, Any]:
    """在线模式：OpenAI 兼容的 function calling 循环（最多 3 轮工具调用）。"""
    import httpx

    url = settings.llm_base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {settings.llm_api_key}", "Content-Type": "application/json"}
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for item in (history or [])[-6:]:
        if item.get("role") in {"user", "assistant"}:
            messages.append({"role": item["role"], "content": item.get("content", "")})
    messages.append({"role": "user", "content": message})

    blocks: list[dict] = []
    called: list[str] = []
    reply = ""

    with httpx.Client(timeout=settings.llm_timeout) as client:
        for _ in range(3):
            payload = {
                "model": settings.llm_model,
                "messages": messages,
                "tools": _tool_schema(),
                "tool_choice": "auto",
                "temperature": 0.3,
            }
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            choice = data["choices"][0]["message"]
            messages.append(choice)

            tool_calls = choice.get("tool_calls") or []
            if not tool_calls:
                reply = choice.get("content") or ""
                break

            for call in tool_calls:
                name = call["function"]["name"]
                try:
                    args = json.loads(call["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                called.append(name)
                try:
                    result = tools.TOOLS[name](args)
                except Exception as exc:  # 工具失败也要把原因交回给模型
                    result = [tools.text(f"工具 {name} 执行失败：{exc}")]
                blocks.extend(result)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": json.dumps({"ok": True, "blocks": len(result)}, ensure_ascii=False),
                    }
                )

    if not reply:
        reply = _reply_for(called[-1] if called else "overview_report", {}, blocks)

    return {
        "reply": reply,
        "blocks": blocks,
        "intent": called[-1] if called else "overview_report",
        "args": {},
        "mode": "llm",
    }


def chat(message: str, history: list[dict] | None = None) -> dict[str, Any]:
    """统一入口：优先在线模型，失败自动降级到规则引擎，保证永不 500。"""
    if settings.llm_enabled:
        try:
            return llm_chat(message, history)
        except Exception as exc:  # noqa: BLE001
            result = rule_chat(message, history)
            result["mode"] = "rules"
            result["fallback_reason"] = f"{type(exc).__name__}: {exc}"
            return result
    return rule_chat(message, history)


def suggestions() -> list[dict]:
    """给前端的快捷问题，降低「不会提问」的门槛。"""
    return [
        {"label": "自动分析结论", "message": "分析完之后有什么结论和建议？"},
        {"label": "整体数据怎么样？", "message": "先看看整体数据情况"},
        {"label": "客户怎么分层？", "message": "客户按 RFM 怎么分层？哪些最重要？"},
        {"label": "看看客户画像", "message": "帮我看看客户画像和人群特征"},
        {"label": "该推给谁？", "message": "预测一下哪些客户最可能响应下次活动"},
        {"label": "生成营销方案", "message": "给核心高价值客群生成一个营销方案，预算 20000"},
        {"label": "品类怎么搭？", "message": "哪些品类有关联，可以怎么组合销售？"},
    ]
