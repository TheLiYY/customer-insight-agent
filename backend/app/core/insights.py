"""自动分析：把前面所有计算结果翻译成「人话结论」。

设计思路：
1. 不引入大模型也能跑——全部是「拿指标 → 套业务阈值 → 生成结论与动作」的确定性规则，
   好处是每条结论都能追溯到具体数字，演示时经得起追问；
2. 配置了大模型时，这些结论会作为工具结果交给 Agent，让它用更自然的语言复述；
3. 每条结论都拆成 title / conclusion / evidence / action 四段，
   前端可以只展示标题，也可以展开看证据链。
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from .config import zh_education, zh_marital
from .dataset import channels as channels_of
from .dataset import categories as categories_of
from .utils import clean, mean_of, sum_of

SEVERITY_LABELS = {
    "opportunity": "增长机会",
    "risk": "风险预警",
    "insight": "结构洞察",
}


def _money(value: float) -> str:
    if value >= 10000:
        return f"{value / 10000:.1f} 万元"
    return f"{value:,.0f} 元"


def _pct(value: float) -> str:
    return f"{(value or 0) * 100:.1f}%"


def _top20_share(df: pd.DataFrame) -> float:
    """把客户按消费额从高到低排，前 20% 的人贡献了多少营收。"""
    if df.empty:
        return 0.0
    values = df["total_spend"].sort_values(ascending=False).to_numpy()
    k = max(1, int(len(values) * 0.2))
    total = values.sum() or 1.0
    return float(values[:k].sum() / total)


def _main_group(df: pd.DataFrame, field: str, labeler=None, order=None) -> tuple[str, float]:
    if field not in df.columns:
        return "", 0.0
    counts = df[field].astype(str).str.strip()
    counts = counts[counts.str.len() > 0].value_counts()
    if counts.empty:
        return "未知", 0.0
    name = str(counts.index[0])
    if labeler:
        name = labeler(name)
    return name, float(counts.iloc[0] / counts.sum())


def build_insights(
    df: pd.DataFrame,
    kpis: dict[str, Any],
    segments: list[dict],
    personas: list[dict],
    prop: dict[str, Any],
    rules: list[dict],
    penetration: list[dict],
) -> dict[str, Any]:
    insights: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []

    def add(
        category: str,
        severity: str,
        title: str,
        conclusion: str,
        evidence: list[str],
        action: str,
        priority: int = 2,
    ) -> None:
        insights.append(
            {
                "id": f"I{len(insights) + 1:02d}",
                "category": category,
                "severity": severity,
                "severity_label": SEVERITY_LABELS[severity],
                "title": title,
                "conclusion": conclusion,
                "evidence": evidence,
                "action": action,
            }
        )
        actions.append({"priority": priority, "action": action, "from": title})

    customers = int(kpis["customers"])
    total_revenue = float(kpis.get("total_revenue") or 0)
    avg_spend = float(kpis.get("avg_spend") or 0)
    base_rate = float(kpis.get("response_rate") or 0)

    # ---------- 1. 价值集中度 ----------
    top20 = _top20_share(df)
    top_seg = max(segments, key=lambda s: s.get("revenue") or 0) if segments else None
    if top_seg and total_revenue > 0:
        add(
            "价值结构",
            "insight",
            f"{top_seg['name']}是营收主力",
            (
                f"{top_seg['name']}共 {top_seg['count']} 人（占 {_pct(top_seg['ratio'])}），"
                f"贡献了 {_pct(top_seg['revenue_ratio'])} 的营收，"
                f"人均消费 {_money(top_seg['avg_spend'])}，"
                f"是整体人均（{_money(avg_spend)}）的 {top_seg['avg_spend'] / max(avg_spend, 1):.1f} 倍。"
            ),
            [
                f"前 20% 高消费客户贡献了 {_pct(top20)} 的营收（共 {customers} 人，营收 {_money(total_revenue)}）",
                f"{top_seg['name']} 人数占比 {_pct(top_seg['ratio'])}，营收占比 {_pct(top_seg['revenue_ratio'])}",
                f"该客群活动响应率 {_pct(top_seg['response_rate'])}，整体响应率 {_pct(base_rate)}",
            ],
            "对核心高价值客群做「会员等级 + 新品优先购」，不要用大额折扣，避免稀释毛利。",
            priority=1,
        )

    # ---------- 2. 沉默客户风险 ----------
    dormant_rate = float(kpis.get("dormant_rate") or 0)
    dormant_count = int(kpis.get("dormant_count") or 0)
    if dormant_rate >= 0.2:
        add(
            "客户健康度",
            "risk",
            f"{_pct(dormant_rate)} 的客户已经 75 天没有下单",
            (
                f"共 {dormant_count} 位客户最近购买间隔超过 75 天，"
                f"整体最近购买间隔均值 {float(kpis.get('avg_recency') or 0):.0f} 天。"
                "这批人是最容易流失、也最容易用低频唤醒成本捞回来的一群。"
            ),
            [
                f"沉默客户 {dormant_count} 人，占比 {_pct(dormant_rate)}",
                f"客户平均最近购买间隔 {float(kpis.get('avg_recency') or 0):.0f} 天",
                f"客户平均购买频次 {float(kpis.get('avg_freq') or 0):.1f} 次",
            ],
            "对 75–120 天未购买客户发一次「专属回归券」，覆盖成本低于新客获取成本。",
            priority=1,
        )
    else:
        add(
            "客户健康度",
            "opportunity",
            "客户活跃度整体健康",
            f"仅 {_pct(dormant_rate)} 的客户超过 75 天未下单（{dormant_count} 人），客户盘面相对稳定。",
            [f"沉默客户 {dormant_count} 人，占比 {_pct(dormant_rate)}"],
            "保持现有触达节奏，把预算优先投到高潜客户上。",
            priority=3,
        )

    # ---------- 3. 响应预测的价值 ----------
    lift = prop.get("lift") or []
    metrics = prop.get("train_metrics") or {}
    if lift:
        top1 = lift[0]
        add(
            "精准触达",
            "opportunity",
            f"前 10% 客户的响应率是平均水平的 {float(top1.get('lift') or 0):.2f} 倍",
            (
                f"按响应概率排序，最靠前的 {top1['customers']} 位客户实际响应率 "
                f"{_pct(top1['response_rate'])}，而全量客户只有 {_pct(prop.get('base_rate') or 0)}；"
                f"同样的预算只投这 10%，能覆盖到 {_pct(top1.get('captured') or 0)} 的响应客户。"
            ),
            [
                f"测试集 AUC = {float(metrics.get('auc') or 0):.3f}（0.5 等于随机猜）",
                f"最优判定阈值 = {float(prop.get('threshold') or 0):.2f}，F1 = {float(metrics.get('f1') or 0):.3f}",
                f"第 1 组 {top1['customers']} 人响应率 {_pct(top1['response_rate'])}，提升度 {float(top1['lift']):.2f}",
            ],
            "把营销名单按响应概率排序，先投 Top 20%，剩余预算再往下延展。",
            priority=1,
        )
    else:
        add(
            "精准触达",
            "risk",
            "这份数据暂时做不了响应预测",
            (prop.get("reason") or "缺少「是否响应」字段或有效样本不足。")
            + " 没有响应标签就没法训练转化概率模型，精准名单只能退化成规则圈人。",
            [
                "需要一列「是否响应/是否转化」的历史结果（0/1 或 是/否），至少 60 位客户",
                f"当前数据可用字段：{'、'.join(list(df.columns)[:12])}……",
            ],
            "补一列历史活动的响应结果后重跑 prepare_data.py，即可恢复响应预测与 Lift 分析。",
            priority=1,
        )

    # ---------- 4. 品类结构 ----------
    if penetration:
        top_cat = max(penetration, key=lambda p: p.get("revenue") or 0)
        second = sorted(penetration, key=lambda p: -(p.get("revenue") or 0))[1:2]
        ev = [
            f"{top_cat['name']}：渗透率 {_pct(top_cat['penetration'])}，营收占比 {_pct(top_cat.get('revenue_ratio') or 0)}",
        ]
        if second:
            ev.append(
                f"{second[0]['name']}：渗透率 {_pct(second[0]['penetration'])}，营收占比 {_pct(second[0].get('revenue_ratio') or 0)}"
            )
        labels = "、".join(categories_of().values())
        add(
            "品类结构",
            "insight",
            f"{top_cat['name']}承担了 {_pct(top_cat.get('revenue_ratio') or 0)} 的营收",
            (
                f"{top_cat['name']}是绝对主品类，人均消费 {_money(top_cat['avg_spend'])}，"
                f"{_pct(top_cat['penetration'])} 的客户买过；"
                f"全部品类（{labels}）营收结构见证据。"
            ),
            ev,
            f"以{top_cat['name']}做引流款，用「主品类 + 高毛利小品类」的组合套餐拉高客单价。",
            priority=2,
        )

    # ---------- 5. 关联规则 ----------
    if rules:
        best = rules[0]
        if float(best.get("lift") or 0) >= 1.05:
            add(
                "交叉销售",
                "opportunity",
                f"「{best['antecedent']} → {best['consequent']}」有正向关联",
                (
                    f"买过{best['antecedent']}的客户里有 {_pct(best['confidence'])} 也买了{best['consequent']}，"
                    f"比随机情况高 {float(best['lift']):.2f} 倍（提升度 > 1 才算真实关联）。"
                ),
                [
                    f"支持度 {_pct(best['support'])}：{best['count']} 位客户同时买了两者",
                    f"置信度 {_pct(best['confidence'])}，提升度 {float(best['lift']):.2f}",
                ],
                f"在{best['antecedent']}的详情页/购物车推荐{best['consequent']}，做成组合立减。",
            )
        else:
            add(
                "交叉销售",
                "insight",
                "品类之间互补性偏弱，交叉推荐要谨慎",
                (
                    f"最强规则的提升度只有 {float(best.get('lift') or 0):.2f}（接近 1 说明只是同时买得多，"
                    "并不是「买了 A 就更想买 B」），单靠关联推荐提升有限。"
                ),
                [
                    f"最强规则：{best['antecedent']} → {best['consequent']}",
                    f"支持度 {_pct(best['support'])}，置信度 {_pct(best['confidence'])}",
                ],
                "改用「品类组合套餐 / 满减门槛」推动跨品类购买，而不是单条关联推荐。",
            )

    # ---------- 6. 渠道结构 ----------
    chans = channels_of()
    channel = {label: sum_of(df, field) for field, label in chans.items()}
    ch_total = sum(channel.values()) or 0.0
    if channel and ch_total > 0:
        ch_sorted = sorted(channel.items(), key=lambda kv: -kv[1])
        ch_name, ch_value = ch_sorted[0]
        add(
            "渠道结构",
            "insight",
            f"{ch_name}是主要成交渠道（{_pct(ch_value / ch_total)}）",
            (
                "从购买次数看，"
                + "，".join(f"{name} {_pct(value / ch_total)}" for name, value in ch_sorted)
                + "；渠道结构决定了触达方式的选择。"
            ),
            [f"{name}：{value:,.0f} 次购买，占比 {_pct(value / ch_total)}" for name, value in ch_sorted],
            f"预算优先投{ch_name}，同时用线上触达做低频客户的低成本唤醒。",
            priority=2,
        )

    # ---------- 7. 人群结构 ----------
    edu_name, edu_ratio = _main_group(df, "education", zh_education)
    mar_name, mar_ratio = _main_group(df, "marital_status", zh_marital)
    age_name, age_ratio = _main_group(df, "age_group")
    avg_age = mean_of(df, "age")
    demo_parts = []
    demo_evidence = []
    if mar_ratio:
        demo_parts.append(f"{mar_name}客户占 {_pct(mar_ratio)}")
        demo_evidence.append(f"{mar_name}：{_pct(mar_ratio)}")
    if edu_ratio:
        demo_parts.append(f"{edu_name}学历占 {_pct(edu_ratio)}")
        demo_evidence.append(f"{edu_name}：{_pct(edu_ratio)}")
    if age_ratio:
        demo_parts.append(f"年龄以 {age_name} 为主（{_pct(age_ratio)}）")
        demo_evidence.append(f"{age_name}：{_pct(age_ratio)} 的人集中在这一段")
    if avg_age:
        demo_parts.append(f"整体平均年龄 {avg_age:.0f} 岁")
    if kpis.get("avg_income"):
        demo_parts.append(f"平均家庭年收入 {_money(float(kpis.get('avg_income') or 0))}")
    if demo_parts:
        title = (
            f"{mar_name}+{edu_name} 是主力人群" if (mar_ratio and edu_ratio) else "人群结构特征"
        )
        add(
            "人群结构",
            "insight",
            title,
            "，".join(demo_parts) + "。",
            demo_evidence,
            "素材与权益设计按主力人群的偏好来定：家庭消费场景 + 品质导向。",
            priority=3,
        )

    # ---------- 8. 折扣依赖与投诉 ----------
    discount = float(kpis.get("discount_dependence") or 0)
    complain = float(kpis.get("complain_rate") or 0)
    if discount >= 0.18:
        add(
            "利润健康度",
            "risk",
            f"折扣购买占比 {_pct(discount)}，促销依赖偏高",
            (
                "折扣单占总购买次数的比例偏高，长期用降价换量会压缩毛利、"
                "也会训练客户只在促销时下单。"
            ),
            [
                f"折扣购买次数占总购买次数 {_pct(discount)}",
                f"平均购买频次 {float(kpis.get('avg_freq') or 0):.1f} 次/人",
            ],
            "把大额折扣换成「满件数送 / 会员专属价」，保住毛利的同时维持促销力度。",
            priority=2,
        )
    if complain > 0.01:
        add(
            "服务体验",
            "risk",
            f"投诉客户占 {_pct(complain)}",
            f"{int(round(complain * customers))} 位客户在过去两年投诉过，投诉客户几乎不会再响应营销活动，"
            "营销名单里应当排除他们。",
            [f"投诉率 {_pct(complain)}，对应 {int(round(complain * customers))} 人"],
            "投诉客户不要进营销名单，先做服务补救，再考虑复购召回。",
            priority=2,
        )

    # ---------- 9. 客群活跃度分化 ----------
    silent = [p for p in personas if p.get("status") == "沉默预警"]
    if silent:
        names = "、".join(p["name"] for p in silent)
        add(
            "客群分化",
            "risk",
            f"{len(silent)} 个客群出现沉默预警",
            f"{names} 的平均购买间隔明显高于整体，需要单独设计唤醒动作，而不是躺在大盘活动里。",
            [
                f"{p['name']}：{p['size']} 人，平均 {float(p['value']['avg_recency']):.0f} 天未购买"
                for p in silent
            ],
            "针对沉默预警客群单独发召回活动，与核心客群的日常运营分开投。",
            priority=2,
        )

    # ---------- 汇总 ----------
    actions.sort(key=lambda a: a["priority"])
    has_revenue = bool(total_revenue and total_revenue > 0)
    parts: list[str] = []
    if has_revenue:
        parts.append(f"{customers} 位客户里，前 20% 贡献了 {_pct(top20)} 的营收")
    elif base_rate:
        parts.append(f"{customers} 位客户整体响应率 {_pct(base_rate)}")
    else:
        parts.append(f"这份数据共 {customers} 位客户")
    if lift:
        parts.append(f"按响应概率筛选后的头部名单，转化率是平均水平的 {float(lift[0]['lift']):.2f} 倍")
    else:
        parts.append("这份数据没有响应标签，暂时用 RFM 分层 + 客群画像来做精准圈人")
    headline = "；".join(parts) + "。"

    return {
        "headline": headline,
        "counts": {
            "total": len(insights),
            "opportunity": sum(1 for i in insights if i["severity"] == "opportunity"),
            "risk": sum(1 for i in insights if i["severity"] == "risk"),
            "insight": sum(1 for i in insights if i["severity"] == "insight"),
        },
        "insights": insights,
        "actions": [
            {"priority": idx + 1, "action": a["action"], "from": a["from"]}
            for idx, a in enumerate(actions[:6])
        ],
        "stats": {
            "customers": customers,
            "total_revenue": clean(total_revenue),
            "avg_spend": clean(avg_spend),
            "response_rate": clean(base_rate),
            "top20_revenue_share": clean(top20),
            "dormant_rate": clean(dormant_rate),
            "auc": clean(float((prop.get("train_metrics") or {}).get("auc") or 0)),
            "top_decile_lift": clean(float((lift[0] if lift else {}).get("lift") or 0)),
        },
    }
