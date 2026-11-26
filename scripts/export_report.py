"""生成一份可直接交付的《客户洞察分析报告》Excel。

用法（项目根目录）：
    .venv\\Scripts\\python.exe scripts\\export_report.py

产物：backend/data/processed/Customer_Insight_Report.xlsx
内容：报告说明 / 核心指标 / RFM 分层 / 聚类画像 / 画像标签 / 响应预测 /
      关联规则 / 营销方案 / 高潜客户名单，并带原生 Excel 图表。
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import xlsxwriter  # noqa: E402

from app.core.store import store  # noqa: E402

OUT = ROOT / "backend" / "data" / "processed" / "Customer_Insight_Report.xlsx"

TITLE_FMT = dict(bold=True, font_size=15, font_color="#1f2d3d")
HEAD_FMT = dict(
    bold=True,
    font_color="#FFFFFF",
    bg_color="#2f6feb",
    border=1,
    border_color="#2f6feb",
    align="center",
    valign="vcenter",
    text_wrap=True,
)
CELL_FMT = dict(border=1, border_color="#dfe3e8", valign="vcenter")
NUM_FMT = dict(CELL_FMT, num_format="#,##0.00")
PCT_FMT = dict(CELL_FMT, num_format="0.0%")
INT_FMT = dict(CELL_FMT, num_format="#,##0")


def header(ws, row: int, cols: list[str], widths: list[int]) -> None:
    for i, (c, w) in enumerate(zip(cols, widths)):
        ws.write(row, i, c)
        ws.set_column(i, i, w)
    ws.set_row(row, 26)


def main() -> None:
    ov = store.overview
    kpi = ov["kpis"]
    seg = store.segment_summary
    personas = store.personas
    prop = store.propensity
    rules = store.rules
    plan = store.plan(
        segment=personas[0]["name"],
        budget=2000,
        cost_per_contact=8,
        discount=0.1,
    )
    meta = store.meta

    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb = xlsxwriter.Workbook(str(OUT))
    # 固定文档属性，保证重复运行产出字节一致（便于 git diff 与可复现构建）
    wb.set_properties(
        {
            "title": "客户洞察分析报告",
            "author": "Customer Insight Agent",
            "created": datetime(2026, 1, 1),
        }
    )
    fmt_title = wb.add_format(TITLE_FMT)
    fmt_note = wb.add_format(dict(italic=True, font_color="#7a8899", text_wrap=True))
    fmt_head = wb.add_format(HEAD_FMT)
    fmt_cell = wb.add_format(CELL_FMT)
    fmt_num = wb.add_format(NUM_FMT)
    fmt_pct = wb.add_format(PCT_FMT)
    fmt_int = wb.add_format(INT_FMT)
    fmt_bold = wb.add_format(dict(bold=True, border=1, border_color="#dfe3e8"))

    # ---------- 1. 报告说明 ----------
    ws = wb.add_worksheet("报告说明")
    ws.hide_gridlines(2)
    ws.set_column(0, 0, 18)
    ws.set_column(1, 1, 96)
    ws.write(0, 0, "客户洞察与精准营销分析报告", fmt_title)
    ws.write(1, 0, "生成口径", fmt_bold)
    ws.write(1, 1, "可复现构建（数据快照 2026-11，运行 scripts/export_report.py 可重新生成）", fmt_cell)
    rows = [
        ("数据来源", meta.get("source", "")),
        ("数据说明", "公开数据集 Customer Personality Analysis（iFood 营销活动），已清洗为结构化客户宽表。"),
        ("样本量", f"{int(kpi['customers'])} 位去重客户 / {store.df.shape[1]} 个字段"),
        ("分析模块", "RFM 价值分层 · K-Means 客群聚类 · 客户画像 · 响应概率预测 · 品类关联规则 · 营销方案生成"),
        ("标签口径", "R=最近一次购买距今天数（越小越好）；F=购买频次；M=消费金额。均按五分位打分 1-5。"),
        ("使用建议", "先看「核心指标」把握全局，再看「RFM 分层 / 聚类画像」定位人群，最后用「营销方案」「高潜名单」落地执行。"),
    ]
    r = 2
    for k, v in rows:
        ws.write(r, 0, k, fmt_bold)
        ws.write(r, 1, v, fmt_cell)
        r += 1
    ws.write(r + 1, 0, "注：本报告所有数值均由 backend 分析引擎实时计算，与前端页面 / API 结果一致。", fmt_note)

    # ---------- 2. 核心指标 ----------
    ws = wb.add_worksheet("核心指标")
    ws.write(0, 0, "核心经营指标", fmt_title)
    header(ws, 2, ["指标", "数值", "说明"], [24, 16, 52])
    kpi_rows = [
        ("客户总数", kpi["customers"], "去重后的有效客户数", fmt_int),
        ("平均年收入", kpi["avg_income"], "客户年收入均值（货币单位）", fmt_num),
        ("平均累计消费", kpi["avg_spend"], "客户历史消费总额均值", fmt_num),
        ("平均购买频次", kpi["avg_freq"], "线上+目录+门店购买次数均值", fmt_num),
        ("平均最近购买间隔", kpi["avg_recency"], "距最近一次购买的天数，越小越活跃", fmt_num),
        ("历史总营收", kpi["total_revenue"], "全部客户累计消费金额", fmt_num),
        ("营销响应率", kpi["response_rate"], "最近一次活动实际响应的客户占比", fmt_pct),
        ("响应客户数", kpi["response_count"], "最近一次活动响应的客户数", fmt_int),
        ("沉默客户占比", kpi["dormant_rate"], "最近购买间隔超过 60 天的客户占比", fmt_pct),
        ("折扣依赖度", kpi["discount_dependence"], "折扣购买次数占总购买次数的比例", fmt_pct),
        ("投诉率", kpi["complain_rate"], "过去两年有投诉记录的客户占比", fmt_pct),
    ]
    r = 3
    for name, val, desc, f in kpi_rows:
        ws.write(r, 0, name, fmt_cell)
        ws.write_number(r, 1, float(val), f)
        ws.write(r, 2, desc, fmt_cell)
        r += 1

    # 品类消费 + 条形图
    ws.write(1, 0, "", fmt_cell)
    start = r + 2
    ws.write(start, 0, "各品类平均消费", fmt_bold)
    header(ws, start + 1, ["品类", "人均消费"], [20, 16])
    for i, item in enumerate(ov["category"]):
        ws.write(start + 2 + i, 0, item["name"], fmt_cell)
        ws.write_number(start + 2 + i, 1, float(item["value"]), fmt_num)
    n = len(ov["category"])
    chart = wb.add_chart({"type": "bar"})
    chart.add_series(
        {
            "name": "人均消费",
            "categories": ["核心指标", start + 2, 0, start + 1 + n, 0],
            "values": ["核心指标", start + 2, 1, start + 1 + n, 1],
            "fill": {"color": "#2f6feb"},
        }
    )
    chart.set_title({"name": "品类人均消费（货币单位）"})
    chart.set_legend({"none": True})
    chart.set_size({"width": 520, "height": 300})
    ws.insert_chart(start + 2, 3, chart)

    # ---------- 3. RFM 分层 ----------
    ws = wb.add_worksheet("RFM分层")
    ws.write(0, 0, "RFM 八分层结果", fmt_title)
    cols = ["客群", "优先级", "人数", "人数占比", "贡献营收", "营收占比", "平均R", "平均F", "平均M", "平均消费", "响应率", "策略"]
    header(ws, 2, cols, [18, 8, 8, 10, 14, 10, 9, 9, 9, 12, 9, 60])
    r = 3
    for i, s in enumerate(seg):
        ws.write(r, 0, s["name"], fmt_cell)
        ws.write_number(r, 1, s["priority"], fmt_int)
        ws.write_number(r, 2, s["count"], fmt_int)
        ws.write_number(r, 3, s["ratio"], fmt_pct)
        ws.write_number(r, 4, s["revenue"], fmt_num)
        ws.write_number(r, 5, s["revenue_ratio"], fmt_pct)
        ws.write_number(r, 6, s["avg_r"], fmt_num)
        ws.write_number(r, 7, s["avg_f"], fmt_num)
        ws.write_number(r, 8, s["avg_m"], fmt_num)
        ws.write_number(r, 9, s["avg_spend"], fmt_num)
        ws.write_number(r, 10, s["response_rate"], fmt_pct)
        ws.write(r, 11, s["action"], fmt_cell)
        r += 1
    chart = wb.add_chart({"type": "column"})
    chart.add_series(
        {
            "name": "人数",
            "categories": ["RFM分层", 3, 0, 2 + len(seg), 0],
            "values": ["RFM分层", 3, 2, 2 + len(seg), 2],
            "fill": {"color": "#41ba41"},
            "data_labels": {"value": True},
        }
    )
    chart.add_series(
        {
            "name": "营收占比",
            "categories": ["RFM分层", 3, 0, 2 + len(seg), 0],
            "values": ["RFM分层", 3, 5, 2 + len(seg), 5],
            "y2_axis": True,
            "fill": {"color": "#ffbf00"},
        }
    )
    chart.set_title({"name": "各分层人数与营收占比"})
    chart.set_size({"width": 640, "height": 320})
    chart.set_y2_axis({"num_format": "0%"})
    ws.insert_chart(r + 2, 0, chart)

    # ---------- 4. 聚类画像 ----------
    ws = wb.add_worksheet("客群画像")
    ws.write(0, 0, f"K-Means 客群画像（k={store.cluster['k']}，轮廓系数 {store.cluster['silhouette']:.3f}）", fmt_title)
    cols = ["客群", "状态", "人数", "占比", "营收占比", "人均收入", "人均消费", "客单价", "购买频次", "最近购买", "响应率", "一句话概括"]
    header(ws, 2, cols, [18, 10, 8, 9, 10, 12, 12, 10, 10, 10, 9, 46])
    r = 3
    for p in personas:
        ws.write(r, 0, p["name"], fmt_cell)
        ws.write(r, 1, p["status"], fmt_cell)
        ws.write_number(r, 2, p["size"], fmt_int)
        ws.write_number(r, 3, p["ratio"], fmt_pct)
        ws.write_number(r, 4, p["revenue_ratio"], fmt_pct)
        ws.write_number(r, 5, p["value"]["avg_income"], fmt_num)
        ws.write_number(r, 6, p["value"]["avg_spend"], fmt_num)
        ws.write_number(r, 7, p["value"]["avg_order_value"], fmt_num)
        ws.write_number(r, 8, p["value"]["avg_freq"], fmt_num)
        ws.write_number(r, 9, p["value"]["avg_recency"], fmt_num)
        ws.write_number(r, 10, p["behavior"]["response_rate"], fmt_pct)
        ws.write(r, 11, p["headline"], fmt_cell)
        r += 1
    # 雷达图：四客群在 收入/消费/频次/活跃度 上的对比（活跃度=1-归一化recency）
    radar_start = r + 2
    ws.write(radar_start, 0, "客群对比", fmt_bold)
    dims = ["人均收入", "人均消费", "购买频次", "最近购买间隔"]
    header(ws, radar_start + 1, ["客群"] + dims, [18, 14, 14, 14, 16])
    for i, p in enumerate(personas):
        ws.write(radar_start + 2 + i, 0, p["name"], fmt_cell)
        ws.write_number(radar_start + 2 + i, 1, p["value"]["avg_income"], fmt_num)
        ws.write_number(radar_start + 2 + i, 2, p["value"]["avg_spend"], fmt_num)
        ws.write_number(radar_start + 2 + i, 3, p["value"]["avg_freq"], fmt_num)
        ws.write_number(radar_start + 2 + i, 4, p["value"]["avg_recency"], fmt_num)
    chart = wb.add_chart({"type": "column"})
    for i, p in enumerate(personas[:4]):
        row = radar_start + 2 + i
        chart.add_series(
            {
                "name": p["name"],
                "categories": ["客群画像", radar_start + 1, 1, radar_start + 1, 4],
                "values": ["客群画像", row, 1, row, 4],
            }
        )
    chart.set_title({"name": "客群四维对比"})
    chart.set_size({"width": 620, "height": 320})
    ws.insert_chart(radar_start + 2, 6, chart)

    # ---------- 5. 画像标签 ----------
    ws = wb.add_worksheet("画像标签")
    ws.write(0, 0, "客群标签与偏好", fmt_title)
    header(ws, 2, ["客群", "核心标签", "画像描述", "偏好品类(人均消费)"], [18, 40, 70, 46])
    r = 3
    for p in personas:
        ws.write(r, 0, p["name"], fmt_cell)
        ws.write(r, 1, " / ".join(p["tags"]), fmt_cell)
        ws.write(r, 2, p["summary"], fmt_cell)
        cats = "；".join(f"{c['name']} {c['value']:.1f}" for c in p["categories"][:3])
        ws.write(r, 3, cats, fmt_cell)
        r += 1

    # ---------- 6. 响应预测 ----------
    ws = wb.add_worksheet("响应预测")
    ws.write(0, 0, "营销响应概率模型（逻辑回归）", fmt_title)
    m = prop["train_metrics"]
    ws.write(2, 0, "模型评估", fmt_bold)
    header(ws, 3, ["指标", "数值"], [26, 16])
    metrics = [
        ("AUC", m["auc"]),
        ("准确率", m["accuracy"]),
        ("精确率", m["precision"]),
        ("召回率", m["recall"]),
        ("F1", m["f1"]),
        ("判定阈值", m["threshold"]),
        ("基线响应率", prop["base_rate"]),
    ]
    r = 4
    for name, val in metrics:
        ws.write(r, 0, name, fmt_cell)
        ws.write_number(r, 1, float(val), fmt_num)
        r += 1

    ws.write(2, 3, "特征权重（正=提升响应概率）", fmt_bold)
    header(ws, 3, ["特征", "系数", "方向"], [26, 14, 12])
    r = 4
    for c in prop["coefs"]:
        ws.write(r, 0, c["feature"], fmt_cell)
        ws.write_number(r, 1, c["coef"], fmt_num)
        ws.write(r, 2, "正向" if c["coef"] >= 0 else "负向", fmt_cell)
        r += 1

    lift_start = r + 2
    ws.write(lift_start, 0, "十分位提升度（Lift）", fmt_bold)
    header(ws, lift_start + 1, ["分位", "人数", "平均分", "响应率", "Lift", "累计捕获"], [10, 10, 12, 12, 10, 12])
    for i, item in enumerate(prop["lift"]):
        row = lift_start + 2 + i
        ws.write_number(row, 0, i + 1, fmt_int)
        ws.write_number(row, 1, item["customers"], fmt_int)
        ws.write_number(row, 2, item["avg_score"], fmt_num)
        ws.write_number(row, 3, item["response_rate"], fmt_pct)
        ws.write_number(row, 4, item["lift"], fmt_num)
        ws.write_number(row, 5, item["captured"], fmt_pct)
    chart = wb.add_chart({"type": "column"})
    chart.add_series(
        {
            "name": "响应率",
            "categories": ["响应预测", lift_start + 2, 0, lift_start + 1 + len(prop["lift"]), 0],
            "values": ["响应预测", lift_start + 2, 3, lift_start + 1 + len(prop["lift"]), 3],
            "fill": {"color": "#2f6feb"},
        }
    )
    chart.add_series(
        {
            "name": "Lift",
            "categories": ["响应预测", lift_start + 2, 0, lift_start + 1 + len(prop["lift"]), 0],
            "values": ["响应预测", lift_start + 2, 4, lift_start + 1 + len(prop["lift"]), 4],
            "y2_axis": True,
            "fill": {"color": "#ff7500"},
        }
    )
    chart.set_title({"name": "十分位响应率与 Lift"})
    chart.set_size({"width": 640, "height": 320})
    ws.insert_chart(3, 6, chart)

    # ---------- 7. 关联规则 ----------
    ws = wb.add_worksheet("关联规则")
    ws.write(0, 0, "品类关联规则（Apriori）", fmt_title)
    header(ws, 2, ["前项", "后项", "支持度", "置信度", "提升度", "订单数"], [16, 16, 12, 12, 10, 10])
    for i, rule in enumerate(rules):
        row = 3 + i
        ws.write(row, 0, rule["antecedent"], fmt_cell)
        ws.write(row, 1, rule["consequent"], fmt_cell)
        ws.write_number(row, 2, rule["support"], fmt_pct)
        ws.write_number(row, 3, rule["confidence"], fmt_pct)
        ws.write_number(row, 4, rule["lift"], fmt_num)
        ws.write_number(row, 5, rule["count"], fmt_int)

    pen_start = len(rules) + 6
    ws.write(pen_start, 0, "品类渗透率与客单价", fmt_bold)
    header(ws, pen_start + 1, ["品类", "渗透率", "覆盖人数"], [16, 12, 12])
    for i, item in enumerate(store.penetration):
        row = pen_start + 2 + i
        ws.write(row, 0, item["name"], fmt_cell)
        ws.write_number(row, 1, float(item["penetration"]), fmt_pct)
        ws.write_number(row, 2, int(item["buyers"]), fmt_int)

    # ---------- 8. 营销方案 ----------
    ws = wb.add_worksheet("营销方案")
    ws.write(0, 0, f"营销方案：{plan['segment']}（预算 {plan['budget']:,.0f} 元）", fmt_title)
    header(ws, 2, ["项目", "内容"], [22, 104])
    items = [
        ("目标客群", f"{plan['segment']}（共 {plan['segment_size']} 人）"),
        ("圈选人数", f"{plan['selected']} 人，覆盖客群 {plan['coverage']:.1%}"),
        ("活动目标", plan["goal"]),
        ("推荐渠道", plan["channel"]),
        ("触达时机", plan["timing"]),
        ("优惠策略", plan["offer"]),
        ("推荐商品", "、".join(p["name"] for p in plan["products"])),
        ("关联加购", "；".join(f"{u['from']} → {u['to']}（Lift {u['lift']:.2f}）" for u in plan["upsell"]) or "无明显强关联"),
        ("文案参考", plan["copy"]),
        ("触达成本", f"{plan['cost']:,.0f} 元（单客 {plan['cost_per_contact']:.1f} 元）"),
        ("预计响应", f"{plan['expected_responses']:.0f} 人（响应率 {plan['expected_conv_rate']:.1%}）"),
        ("预计营收", f"{plan['expected_revenue']:,.0f} 元"),
        ("预计 ROI", f"{plan['roi']:.2f}"),
        ("优先级", plan["priority"]),
    ]
    r = 3
    for k, v in items:
        ws.write(r, 0, k, fmt_bold)
        ws.write(r, 1, str(v), fmt_cell)
        ws.set_row(r, 22)
        r += 1

    # ---------- 9. 高潜名单 ----------
    ws = wb.add_worksheet("高潜客户名单")
    ws.write(0, 0, "响应概率 Top 100 客户（可直接用于触达）", fmt_title)
    header(ws, 2, ["客户ID", "所属客群", "RFM分层", "响应概率", "累计消费", "购买频次", "最近购买间隔"], [12, 20, 16, 12, 14, 10, 14])
    top = store.enriched.sort_values("prob", ascending=False).head(100)
    for i, (_, row) in enumerate(top.iterrows()):
        r = 3 + i
        ws.write(r, 0, row["customer_id"], fmt_cell)
        ws.write(r, 1, str(row.get("cluster_name", "")), fmt_cell)
        ws.write(r, 2, row.get("rfm_segment", ""), fmt_cell)
        ws.write_number(r, 3, float(row["prob"]), fmt_pct)
        ws.write_number(r, 4, float(row["total_spend"]), fmt_num)
        ws.write_number(r, 5, float(row["purchase_freq"]), fmt_num)
        ws.write_number(r, 6, float(row["recency"]), fmt_num)
    ws.freeze_panes(3, 0)

    wb.close()
    print(f"OK -> {OUT} ({OUT.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()



