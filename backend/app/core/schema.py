"""数据契约层（Data Contract）：把「各种客户数据」翻译成项目内部统一的标准表。

为什么需要这一层？
    真实项目里，数据永远不是你现在手上这一份：可能是 iFood 那种已经算好 39 列的宽表，
    也可能是银行营销名单（带 y 响应标记），还可能是公司导出的「订单明细」（一行一个订单，
    同一个客户出现很多次）。如果分析代码直接写死 39 个列名，换一份数据就全崩了。

这一层做四件事：
    1. 列名归一化：把 "Annual Income (k$)"、"客户编号"、"Total Spend" 都变成可比对的小写串。
    2. 自动识别：用别名表把源列映射到标准字段（customer_id / age / income / recency ...），
       每一列都能给出「是怎么匹配上的」以及「置信度」，写进 mapping.json 供人检查与手工覆盖。
    3. 粒度转换：识别出这是「客户级宽表」还是「订单级明细表」。如果是明细表，
       就自动按客户聚合成宽表（金额求和、订单数计次、最近一次下单算 recency、最早一单算入会时长）。
    4. 能力清单：算完告诉上层「这份数据能做什么」——有没有金额、有没有响应标记、
       有几个品类、几个渠道。后端的模型和前端页面据此决定显示什么、隐藏什么。

这个模块只依赖 pandas / numpy，不依赖项目其它代码，方便 scripts/prepare_data.py 直接调用。
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# 1. 标准字段定义：key 是项目内部使用的列名，aliases 是常见的源列名
# ---------------------------------------------------------------------------
# match: 匹配方式 exact(完全相同) / prefix(前缀) / contains(包含)，用来给置信度打分
STANDARD_FIELDS: dict[str, dict[str, Any]] = {
    "customer_id": {
        "label": "客户编号",
        "type": "id",
        "desc": "每个客户的唯一标识；没有就用行号生成",
        "aliases": [
            "customerid", "customer_id", "id", "userid", "user_id", "memberid", "member_id",
            "custid", "cust_id", "clientid", "client_id", "customerkey", "customernumber",
            "客户id", "客户编号", "客户号", "用户id", "用户编号", "会员id", "会员号", "顾客编号", "编号",
        ],
        "required": True,
    },
    "age": {
        "label": "年龄",
        "type": "number",
        "desc": "客户年龄，用于分箱与画像",
        "aliases": ["age", "customerage", "年龄", "客户年龄", "岁数"],
    },
    "gender": {
        "label": "性别",
        "type": "category",
        "desc": "性别，用于画像拆解",
        "aliases": ["gender", "sex", "性别", "客户性别"],
    },
    "income": {
        "label": "收入",
        "type": "number",
        "desc": "收入或收入水平评分；不同数据集单位不同（元/千元/评分）",
        "aliases": [
            "income", "annualincome", "yearincome", "yearlyincome", "salary", "totalsalary",
            "monthlyincome", "earnings", "收入", "年收入", "月收入", "家庭收入", "工资", "薪资",
        ],
    },
    "education": {
        "label": "学历",
        "type": "category",
        "desc": "学历层级",
        "aliases": ["education", "edu", "educationlevel", "degree", "学历", "教育", "文化程度", "教育程度"],
    },
    "marital_status": {
        "label": "婚姻状况",
        "type": "category",
        "desc": "婚姻状态",
        "aliases": ["marital", "maritalstatus", "marriage", "married", "婚姻", "婚姻状况", "婚否", "婚姻状态"],
    },
    "children": {
        "label": "子女数",
        "type": "number",
        "desc": "家中子女数量（kidhome + teenhome 合并）",
        "aliases": ["children", "kids", "numchildren", "childcount", "子女数", "孩子数", "子女"],
    },
    "recency": {
        "label": "最近购买间隔",
        "type": "number",
        "desc": "距离上次购买/互动的天数，越小越活跃",
        "aliases": [
            "recency", "recencydays", "dayssincelast", "dayssincelastpurchase", "lastpurchasedays",
            "dayslastorder", "daysoflastorder", "pdays", "最近购买间隔", "最近一次购买天数",
            "距上次购买天数", "上次购买间隔", "未购买天数",
        ],
    },
    "purchase_freq": {
        "label": "购买频次",
        "type": "number",
        "desc": "一段时间内的购买/互动次数",
        "aliases": [
            "frequency", "freq", "purchasefrequency", "orders", "ordercount", "numorders",
            "numtransactions", "transactions", "previous", "campaign",
            "购买次数", "订单数", "交易次数", "下单次数", "购买频次", "消费次数",
        ],
    },
    "total_spend": {
        "label": "累计消费",
        "type": "number",
        "desc": "客户累计消费金额；没有金额时可能用消费评分代替（会在 warnings 里注明）",
        "aliases": [
            "totalspend", "monetary", "mnttotal", "totalamount", "amount", "totalrevenue",
            "lifetimevalue", "spend", "revenue", "sales", "累计消费", "消费额", "消费金额",
            "总消费", "累计金额", "交易金额", "金额", "客单价",
        ],
    },
    "value_score": {
        "label": "消费评分",
        "type": "number",
        "desc": "没有金额时的替代指标（如商场的 Spending Score）",
        "aliases": ["spendingscore", "valuescore", "score", "消费评分", "消费得分", "价值评分"],
    },
    "tenure_days": {
        "label": "在网天数",
        "type": "number",
        "desc": "成为客户至今的天数",
        "aliases": [
            "tenure", "tenuredays", "customerdays", "dayssincejoined", "accountage", "在网天数",
            "注册天数", "入会天数", "客户天数", "账龄",
        ],
    },
    "num_deals": {
        "label": "折扣次数",
        "type": "number",
        "desc": "使用折扣/优惠券的次数",
        "aliases": ["numdeals", "numdealpurchases", "discountcount", "couponcount", "折扣次数", "优惠次数", "用券次数"],
    },
    "web_visits_month": {
        "label": "月访问次数",
        "type": "number",
        "desc": "最近一个月访问/浏览次数",
        "aliases": ["numwebvisitsmonth", "webvisitsmonth", "visits", "visitcount", "sessions", "月访问次数", "访问次数", "浏览次数"],
    },
    "accepted_total": {
        "label": "历史活动接受数",
        "type": "number",
        "desc": "历史营销活动累计接受次数，是响应预测最强特征之一",
        "aliases": ["acceptedcmpoverall", "acceptedcmp", "campaignaccepted", "acceptedtotal", "历史活动接受数", "活动接受次数"],
    },
    "response": {
        "label": "活动响应",
        "type": "binary",
        "desc": "是否响应了营销活动：1=响应/购买，0=未响应",
        "aliases": [
            "response", "y", "target", "converted", "label", "clicked", "accepted",
            "churn", "是否响应", "响应", "是否购买", "是否转化", "是否点击", "购买意向",
        ],
    },
    "complain": {
        "label": "是否投诉",
        "type": "binary",
        "desc": "是否有投诉记录",
        "aliases": ["complain", "complaint", "complained", "complaintcount", "投诉", "是否投诉", "投诉次数"],
    },
}

# 交易明细表里可能出现的列
TRANSACTION_FIELDS: dict[str, dict[str, Any]] = {
    "order_id": {
        "label": "订单号",
        "type": "id",
        "aliases": ["invoice", "invoiceno", "invoicenumber", "orderid", "order_id", "orderno", "ordernumber", "订单号", "订单编号", "发票号", "交易号"],
    },
    "order_date": {
        "label": "下单时间",
        "type": "date",
        "aliases": ["invoicedate", "orderdate", "order_date", "purchasedate", "tradedate", "date", "datetime", "transdate",
                    "下单时间", "下单日期", "购买时间", "交易时间", "订单日期", "日期"],
    },
    "amount": {
        "label": "订单金额",
        "type": "number",
        "aliases": ["amount", "totalamount", "salesamount", "lineamount", "revenue", "订单金额", "金额", "小计", "交易金额"],
    },
    "quantity": {"label": "数量", "type": "number", "aliases": ["quantity", "qty", "数量", "件数", "购买数量"]},
    "unit_price": {"label": "单价", "type": "number", "aliases": ["unitprice", "price", "单价", "价格"]},
    "product_category": {
        "label": "商品品类",
        "type": "category",
        "aliases": ["category", "productcategory", "categoryname", "producttype", "品类", "商品品类", "类目", "商品类别", "品类名称"],
    },
}

# 品类 / 渠道的常见中文标签（值是列名里可能出现的关键词）
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "葡萄酒": ["wine", "葡萄酒"],
    "水果": ["fruit", "水果"],
    "肉类": ["meat", "肉类", "牛肉", "猪肉"],
    "鱼类": ["fish", "鱼类", "海鲜"],
    "甜食": ["sweet", "cand", "糖果", "甜食", "零食", "巧克力"],
    "金饰礼品": ["gold", "珠宝", "金饰", "礼品"],
    "饮品": ["beverage", "drink", "饮品", "饮料", "咖啡", "茶"],
    "生鲜": ["fresh", "生鲜", "果蔬"],
    "日化": ["daily", "personalcare", "洗护", "日化", "清洁"],
    "家居": ["home", "furniture", "家居", "家电"],
    "服饰": ["apparel", "clothing", "fashion", "服饰", "服装", "鞋"],
    "数码": ["digital", "electronics", "3c", "数码", "电子"],
}

CHANNEL_KEYWORDS: dict[str, list[str]] = {
    "线上商城": ["web", "online", "app", "h5", "小程序", "线上", "电商", "网店", "商城"],
    "邮购目录": ["catalog", "mail", "directmail", "目录", "邮购", "直邮"],
    "线下门店": ["store", "shop", "offline", "pos", "线下", "门店", "到店", "实体店"],
    "电话营销": ["phone", "callcenter", "telemarketing", "电话", "外呼", "电销"],
}

# 品类/渠道列必须「是数值列」才算消费额/次数，这些词排除掉（id、数量、价格不是消费额）
_EXCLUDE_HINTS = ["id", "编号", "code", "代码", "count", "频次", "间隔", "days", "天数", "单价", "price", "数量", "qty"]

# 已知品类/渠道用固定的内部字段名，保证不同数据集里的「葡萄酒」都叫 mnt_wines，前端文案不用改
CATEGORY_KEYS = {
    "葡萄酒": "mnt_wines",
    "水果": "mnt_fruits",
    "肉类": "mnt_meat",
    "鱼类": "mnt_fish",
    "甜食": "mnt_sweet",
    "金饰礼品": "mnt_gold",
}
CHANNEL_KEYS = {
    "线上商城": "num_web",
    "邮购目录": "num_catalog",
    "线下门店": "num_store",
    "电话营销": "num_phone",
}


def normalize_name(name: str) -> str:
    """列名归一化：小写、去掉空格/下划线/标点/括号，保留中文与字母数字。

    "Annual Income (k$)" -> "annualincomek"
    "客户 编号"          -> "客户编号"
    """
    text = str(name).strip().lower()
    text = re.sub(r"[\s_\-./\\()\[\]{}（）【】:：,，、|*%$#@!?+]+", "", text)
    return text


def _alias_score(column_norm: str, alias: str) -> int:
    """给「源列 <-> 别名」的匹配打分：3=完全相同，2=前缀，1=包含，0=不匹配。"""
    alias = alias.lower()
    short = len(alias) <= 2
    if column_norm == alias:
        return 3
    # 短别名（y / id / age）只允许完全匹配，否则 "y" 会命中一堆列
    if short:
        return 0
    if column_norm.startswith(alias) or alias.startswith(column_norm):
        return 2
    if alias in column_norm:
        return 1
    return 0


def _pick(df: pd.DataFrame, spec: dict[str, Any], taken: set[str]) -> tuple[str | None, int]:
    """在 DataFrame 里为某个标准字段挑最合适的源列，返回 (列名, 分数)。"""
    best: tuple[str | None, int] = (None, 0)
    for col in df.columns:
        if col in taken:
            continue
        norm = normalize_name(col)
        for alias in spec.get("aliases", []):
            score = _alias_score(norm, alias)
            if score > best[1]:
                best = (col, score)
    return best


def _is_numeric(series: pd.Series) -> bool:
    if series.dtype.kind in "ifu":
        return True
    sample = series.dropna().astype(str).head(50)
    if sample.empty:
        return False
    converted = pd.to_numeric(sample.str.replace(",", "", regex=False).str.replace("%", "", regex=False), errors="coerce")
    return converted.notna().mean() >= 0.8


BINARY_TOKENS = {"y", "yes", "true", "1", "1.0", "t", "n", "no", "false", "0", "0.0", "f", "是", "否", "有", "无", "成功", "失败"}


def _is_binary_like(series: pd.Series) -> bool:
    """判断一列是不是「是/否」这类二值列（y=yes/no、是/否、1/0 都算）。"""
    values = series.dropna().astype(str).str.strip().str.lower().unique()
    if len(values) == 0 or len(values) > 3:
        return False
    return set(values) <= BINARY_TOKENS


def _looks_like_category(col: str) -> tuple[str | None, str]:
    """判断一列是不是「品类消费额」，返回 (品类中文名, 依据)。"""
    norm = normalize_name(col)
    if any(hint in norm for hint in _EXCLUDE_HINTS):
        return None, ""
    for label, keys in CATEGORY_KEYWORDS.items():
        for key in keys:
            if normalize_name(key) in norm:
                return label, f"列名含「{key}」"
    # 常见前缀写法：mnt_xxx / amount_xxx / spend_xxx / 品类_xxx
    if re.match(r"^(mnt|amount|spend|cat|category|品类|类目)", norm) and len(norm) > 4:
        if any(bad in norm for bad in ("total", "regular", "average", "avg", "sum", "all", "合计", "总计")):
            return None, ""
        return norm, "列名以 mnt/amount/spend/品类 开头"
    return None, ""


def _looks_like_channel(col: str) -> tuple[str | None, str]:
    norm = normalize_name(col)
    if "num" not in norm and "count" not in norm and "渠道" not in norm:
        # 渠道列通常是 num_web / 渠道A 这种，纯 "online" 也可能是标签列，交给数值校验
        pass
    for label, keys in CHANNEL_KEYWORDS.items():
        for key in keys:
            if normalize_name(key) in norm:
                return label, f"列名含「{key}」"
    return None, ""


def detect(df: pd.DataFrame) -> dict[str, Any]:
    """自动识别源表结构：标准字段、品类列、渠道列、粒度、日期/金额列。"""
    taken: set[str] = set()
    mapping: dict[str, dict[str, Any]] = {}

    # iFood 这类数据里学历/婚姻是 one-hot 的 5 列，先排除掉，后面统一反解成一列
    onehot_edu = [c for c in df.columns if normalize_name(c).startswith("education") and len(normalize_name(c)) > len("education")]
    onehot_mar = [c for c in df.columns if normalize_name(c).startswith("marital") and len(normalize_name(c)) > len("marital")]
    if len(onehot_edu) >= 2:
        taken |= {c for c in onehot_edu if normalize_name(c) not in ("educationlevel",)}
    if len(onehot_mar) >= 2:
        taken |= set(onehot_mar)

    for key, spec in STANDARD_FIELDS.items():
        col, score = _pick(df, spec, taken)
        if col is None:
            continue
        # 数值字段要求确实是数值列，否则放弃（例如 "ID" 列里有字符串）；
        # 二值字段（是否响应/是否投诉）允许 y=yes/no、是/否 这种文本取值
        if spec["type"] == "number" and not _is_numeric(df[col]):
            continue
        if spec["type"] == "binary" and not (_is_numeric(df[col]) or _is_binary_like(df[col])):
            continue
        if key == "customer_id" and df[col].nunique() < max(2, int(len(df) * 0.05)):
            # 只有 5% 的不同值，不可能是客户编号
            continue
        mapping[key] = {"source": col, "score": score, "confidence": {3: "高", 2: "中", 1: "低"}[score]}
        taken.add(col)

    # 家庭结构：iFood 这类数据集把子女拆成 kidhome / teenhome 两列，合并成一个 children
    if "children" not in mapping:
        kids = next((c for c in df.columns if normalize_name(c) in ("kidhome", "childrenhome", "kids")), None)
        teens = next((c for c in df.columns if normalize_name(c) in ("teenhome", "teenshome", "teens")), None)
        if kids and teens and _is_numeric(df[kids]) and _is_numeric(df[teens]):
            mapping["children"] = {
                "source": f"{kids} + {teens}",
                "score": 3,
                "confidence": "高",
                "how": "家庭子女数（儿童 + 青少年合并）",
            }
            taken |= {kids, teens}

    # 交易明细相关列（只认强匹配：金额/数量/单价这类列名不能靠「包含」猜出来）
    tx: dict[str, dict[str, Any]] = {}
    for key, spec in TRANSACTION_FIELDS.items():
        col, score = _pick(df, spec, taken)
        if col is None:
            continue
        if key in ("amount", "quantity", "unit_price") and not _is_numeric(df[col]):
            continue
        if key in ("amount", "quantity", "unit_price") and score < 2:
            continue
        if df[col].nunique(dropna=True) <= 1:
            continue  # 常量列（Z_Revenue 这种）
        if key == "product_category" and df[col].nunique() > 60:
            continue  # 品类太多说明是商品名而不是品类
        if key == "order_date" and normalize_name(col) in ("dayofweek", "weekday", "month", "dayofmonth", "quarter", "year"):
            continue  # 「周几/月份」这种列不是下单日期
        tx[key] = {"source": col, "score": score}
        taken.add(col)

    # 品类列：数值列 + 列名像品类 + 真的像「金额」（均值 ≥ 1，0/1 的 one-hot 列会被排除）
    categories: dict[str, dict[str, str]] = {}
    for col in df.columns:
        if col in taken or not _is_numeric(df[col]):
            continue
        if df[col].nunique(dropna=True) <= 1 or float(df[col].fillna(0).mean()) < 1.0:
            continue
        label, why = _looks_like_category(col)
        if label:
            key = CATEGORY_KEYS.get(label) or _slug(col)
            while key in categories or key in taken:
                key = f"{key}_2"
            categories[key] = {"source": col, "label": label, "why": why}
            taken.add(col)

    # 渠道列：数值列 + 列名像渠道（线上/门店/目录/电话）
    channels: dict[str, dict[str, str]] = {}
    for col in df.columns:
        if col in taken or not _is_numeric(df[col]):
            continue
        if df[col].nunique(dropna=True) <= 1 or float(df[col].fillna(0).mean()) < 0.5:
            continue
        label, why = _looks_like_channel(col)
        if label:
            key = CHANNEL_KEYS.get(label) or _slug(col)
            while key in channels or key in taken:
                key = f"{key}_2"
            channels[key] = {"source": col, "label": label, "why": why}
            taken.add(col)

    # 判断粒度：有客户编号重复 + 有订单号/日期/金额 => 订单明细
    grain = "customer"
    reasons: list[str] = []
    id_col = mapping.get("customer_id", {}).get("source")
    if id_col is not None:
        dup = float(df[id_col].duplicated().mean())
        has_tx_evidence = any(k in tx for k in ("order_id", "order_date", "amount"))
        if dup > 0.3 and has_tx_evidence:
            grain = "transaction"
            reasons.append(f"客户编号有 {dup:.0%} 重复行，且存在订单号/日期/金额列")
        elif dup > 0.3:
            reasons.append(f"客户编号有 {dup:.0%} 重复行，但没有订单级证据，按客户级处理（可能取最近一行）")

    unused = [c for c in df.columns if c not in taken]
    return {
        "mapping": mapping,
        "transaction": tx,
        "categories": categories,
        "channels": channels,
        "grain": grain,
        "grain_reasons": reasons,
        "unused_columns": unused,
    }


def _slug(name: str) -> str:
    """把源列名转成安全的内部字段名：保留字母数字与中文，空格转下划线。"""
    text = str(name).strip()
    text = re.sub(r"[^\w\u4e00-\u9fa5]+", "_", text, flags=re.UNICODE)
    text = re.sub(r"_+", "_", text).strip("_")
    return text.lower() if text.isascii() else text


def _to_number(series: pd.Series) -> pd.Series:
    if series.dtype.kind in "ifu":
        return series.astype(float)
    cleaned = series.astype(str).str.replace(",", "", regex=False).str.replace("%", "", regex=False)
    return pd.to_numeric(cleaned, errors="coerce")


_TRUE_TOKENS = {"1", "y", "yes", "true", "t", "success", "successful", "是", "已购买", "购买", "响应", "正样本", "churn", "流失"}
_FALSE_TOKENS = {"0", "n", "no", "false", "f", "failure", "否", "未购买", "未响应", "负样本"}


def _to_binary(series: pd.Series) -> pd.Series:
    """把 y/yes/no/是/否/1/0 统一成 0/1。"""
    if series.dtype.kind in "ifu":
        return (series.astype(float) > 0).astype(int)
    text = series.astype(str).str.strip().str.lower()
    uniq = set(text.dropna().unique()[:20])
    if uniq <= {"yes", "no"} or uniq <= {"y", "n"} or uniq <= {"是", "否"} or uniq <= {"true", "false"}:
        return text.isin(list(_TRUE_TOKENS)).astype(int)
    numeric = pd.to_numeric(text, errors="coerce")
    if numeric.notna().mean() >= 0.9:
        return (numeric.fillna(0) > 0).astype(int)
    return text.isin(list(_TRUE_TOKENS)).astype(int)


def _to_date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


def _education_from_onehot(df: pd.DataFrame) -> pd.Series | None:
    """iFood 原始数据里学历是 5 个 one-hot 列，这里反解成一列。"""
    prefix = [c for c in df.columns if normalize_name(c).startswith("education")]
    if len(prefix) < 2:
        return None
    names = [c.replace("education_", "") for c in prefix]
    idx = df[prefix].to_numpy().argmax(axis=1)
    return pd.Series([names[i] for i in idx], index=df.index)


def _marital_from_onehot(df: pd.DataFrame) -> pd.Series | None:
    prefix = [c for c in df.columns if normalize_name(c).startswith("marital")]
    if len(prefix) < 2:
        return None
    names = [c.replace("marital_", "") for c in prefix]
    idx = df[prefix].to_numpy().argmax(axis=1)
    return pd.Series([names[i] for i in idx], index=df.index)


def _age_group(age: pd.Series) -> pd.Series:
    bins = [0, 30, 40, 50, 60, 200]
    labels = ["18-30", "31-40", "41-50", "51-60", "60+"]
    return pd.cut(age, bins=bins, labels=labels, right=True).astype(str).replace("nan", "未知")


def build_customers(
    df: pd.DataFrame,
    mapping: dict[str, Any],
    *,
    reference_date: datetime | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """按契约把源表转成标准客户表。

    返回 (标准表, 契约信息)。契约信息包含：粒度为谁做了什么聚合、品类/渠道、警告、能力。
    """
    ctx: dict[str, Any] = {"warnings": [], "aggregations": []}
    work = df.copy()
    work.columns = [str(c).strip() for c in work.columns]

    std = {k: v["source"] for k, v in mapping["mapping"].items()}
    tx = {k: v["source"] for k, v in mapping["transaction"].items()}

    # 参考日期：默认取数据里最晚的一单（保证每次构建结果一致），没有日期列才用今天
    if reference_date is not None:
        ref = pd.Timestamp(reference_date)
        ctx["reference_date"] = "手工指定"
    elif tx.get("order_date") is not None:
        ref = _to_date(work[tx["order_date"]]).max()
        ctx["reference_date"] = f"取数据内最晚日期 {ref.date()}"
    else:
        ref = pd.Timestamp(datetime.now(timezone.utc).replace(tzinfo=None))
        ctx["reference_date"] = "取构建当天（无日期列）"

    # ---------- 情况 A：订单明细，先按客户聚合 ----------
    if mapping["grain"] == "transaction":
        id_col = std.get("customer_id")
        if id_col is None:
            raise ValueError("识别为订单明细，但没有找到客户编号列")
        agg = work.groupby(id_col, dropna=False)
        out = pd.DataFrame(index=agg.size().index)
        out.index.name = "customer_id"

        amount_col = std.get("total_spend") or tx.get("amount")
        if amount_col is None and {"quantity", "unit_price"} <= set(tx):
            work["__amount"] = _to_number(work[tx["quantity"]]) * _to_number(work[tx["unit_price"]])
            amount_col = "__amount"
        if amount_col is not None:
            out["total_spend"] = agg[amount_col].sum().astype(float)
            ctx["aggregations"].append(f"total_spend = {amount_col} 求和")
        if tx.get("order_id") is not None:
            out["purchase_freq"] = agg[tx["order_id"]].nunique().astype(float)
            ctx["aggregations"].append("purchase_freq = 订单号去重计数")
        else:
            out["purchase_freq"] = agg.size().astype(float)
            ctx["aggregations"].append("purchase_freq = 明细行数")
        if tx.get("order_date") is not None:
            dates = _to_date(work[tx["order_date"]])
            work["__date"] = dates
            last = work.groupby(id_col)["__date"].max()
            first = work.groupby(id_col)["__date"].min()
            out["recency"] = (ref - last).dt.days.astype(float)
            out["tenure_days"] = (ref - first).dt.days.astype(float)
            ctx["aggregations"].append("recency = 最近一单距今天数；tenure_days = 首单距今天数")
        for key in ("age", "income", "tenure_days"):
            src = std.get(key)
            if src is not None:
                out[key] = agg[src].mean() if key != "tenure_days" else out.get("tenure_days")
        # 品类：明细里有「品类」列就透视，没有就用现成的品类列
        cat_col = tx.get("product_category")
        if cat_col is not None and amount_col is not None:
            pivot = work.pivot_table(index=id_col, columns=cat_col, values=amount_col, aggfunc="sum", fill_value=0.0)
            for col in pivot.columns:
                out[_slug(col)] = pivot[col]
            ctx["warnings"].append("明细表里的「品类」列已按客户透视成品类消费额")
        # 没有客户级的 品类/渠道 列，则保留源表里的静态列（取第一个非空值）
        for key in ("gender", "education", "marital_status", "children"):
            src = std.get(key)
            if src is not None:
                out[key] = agg[src].first()
        out = out.reset_index()
    # ---------- 情况 B：已经是客户级宽表 ----------
    else:
        out = pd.DataFrame(index=work.index)
        for key, src in std.items():
            if key in ("customer_id",):
                continue
            if "+" in str(src):  # 合并列（子女数 = Kidhome + Teenhome）
                parts = [p.strip() for p in str(src).split("+") if p.strip() in work.columns]
                if parts:
                    total = pd.Series(0.0, index=work.index)
                    for part in parts:
                        total = total + _to_number(work[part])
                    out[key] = total
                    ctx["aggregations"].append(f"{key} = " + " + ".join(parts))
                continue
            if src in work.columns:
                out[key] = work[src]
        out["customer_id"] = work[std["customer_id"]] if "customer_id" in std else [f"C{i:05d}" for i in range(1, len(work) + 1)]
        # one-hot 反解（iFood 原始表）
        if "education" not in out.columns:
            edu = _education_from_onehot(work)
            if edu is not None:
                out["education"] = edu
                ctx["aggregations"].append("学历由 education_* 的 one-hot 列反解")
        if "marital_status" not in out.columns:
            mar = _marital_from_onehot(work)
            if mar is not None:
                out["marital_status"] = mar
                ctx["aggregations"].append("婚姻状况由 marital_* 的 one-hot 列反解")
        if "children" not in out.columns:
            kid = next((c for c in work.columns if normalize_name(c) in ("kidhome", "childrenhome")), None)
            teen = next((c for c in work.columns if normalize_name(c) in ("teenhome", "teenshome")), None)
            if kid is not None or teen is not None:
                out["children"] = (work[kid].fillna(0) if kid is not None else 0) + (work[teen].fillna(0) if teen is not None else 0)
                ctx["aggregations"].append("子女数 = Kidhome + Teenhome")

    # ---------- 品类 / 渠道列 ----------
    for key, info in mapping["categories"].items():
        src = info["source"]
        if key in out.columns:
            continue
        if mapping["grain"] == "customer":
            out[key] = work[src]
        else:
            # 明细表里如果有「品类金额」列，就按客户求和
            try:
                out[key] = work.groupby(std.get("customer_id", work.index.name))[src].sum()
            except Exception:  # pragma: no cover - 极少数异常结构
                pass
    for key, info in mapping["channels"].items():
        src = info["source"]
        if key in out.columns:
            continue
        if mapping["grain"] == "customer":
            out[key] = work[src]
        else:
            try:
                out[key] = work.groupby(std.get("customer_id", work.index.name))[src].sum()
            except Exception:  # pragma: no cover
                pass

    # ---------- 类型与清洗 ----------
    for key in ("age", "income", "recency", "purchase_freq", "total_spend", "value_score",
                "tenure_days", "num_deals", "web_visits_month", "accepted_total", "children"):
        if key in out.columns:
            out[key] = _to_number(out[key])
    if "response" in out.columns:
        out["response"] = _to_binary(out["response"])
    if "complain" in out.columns:
        out["complain"] = _to_binary(out["complain"])
    for key in ("gender", "education", "marital_status"):
        if key in out.columns:
            out[key] = out[key].astype(str).str.strip().replace({"nan": "", "None": ""})

    # 没有购买频次：先看能不能用各渠道购买次数相加（iFood 就是这种结构）
    if "purchase_freq" not in out.columns and mapping["channels"]:
        cols = [k for k in mapping["channels"] if k in out.columns]
        if cols:
            out["purchase_freq"] = out[cols].fillna(0).sum(axis=1)
            ctx["aggregations"].append("purchase_freq = 各渠道购买次数之和（" + "、".join(cols) + "）")
    # 还没有就用「有消费记为 1 次」兜底
    if "purchase_freq" not in out.columns and "total_spend" in out.columns:
        out["purchase_freq"] = (out["total_spend"] > 0).astype(float)
        ctx["warnings"].append("缺少购买频次列，暂按「有消费记为 1 次」估算")

    # 没有金额时用「消费评分」代替（明确写进 warnings，避免误读）
    if "total_spend" not in out.columns and "value_score" in out.columns:
        out["total_spend"] = out["value_score"]
        ctx["warnings"].append("这份数据没有消费金额，暂用「消费评分」代替金额参与分层（分层含义会变，注意看页面提示）")

    # 补齐 RFM 必需的三个字段，缺失时置 0 并记录
    for key, label in (("recency", "最近购买间隔"), ("purchase_freq", "购买频次"), ("total_spend", "累计消费")):
        if key not in out.columns:
            out[key] = 0.0
            ctx["warnings"].append(f"缺少「{label}」列，该维度全为 0，RFM 分层结果仅供参考")

    if "age" in out.columns:
        out["age"] = out["age"].clip(18, 90)
        out["age_group"] = _age_group(out["age"])
    if "income" in out.columns and out["income"].notna().any():
        cap = float(out["income"].quantile(0.99))
        out["income"] = out["income"].clip(upper=cap)

    # 去掉关键指标全空的行（金额与收入是后续模型的输入）
    before = len(out)
    core_cols = [c for c in ("total_spend", "income") if c in out.columns]
    out = out.dropna(subset=core_cols)
    if len(out) != before:
        ctx["warnings"].append(f"剔除了 {before - len(out)} 行金额/收入为空的记录")

    out["customer_id"] = out["customer_id"].astype(str)
    out = out.drop_duplicates(subset=["customer_id"]).reset_index(drop=True)

    # 列顺序：标准字段在前，品类渠道在后
    head = [c for c in ["customer_id", "age", "age_group", "gender", "income", "education", "marital_status",
                        "children", "tenure_days", "recency", "purchase_freq", "total_spend",
                        "num_deals", "web_visits_month", "accepted_total", "response", "complain"] if c in out.columns]
    rest = [c for c in out.columns if c not in head]
    out = out[head + rest]
    out = out.fillna({"total_spend": 0.0, "purchase_freq": 0.0, "recency": 0.0})

    capabilities = capabilities_of(out, mapping)
    ctx["capabilities"] = capabilities
    return out, ctx


def capabilities_of(df: pd.DataFrame, mapping: dict[str, Any] | None = None) -> dict[str, Any]:
    """计算「这份数据能做什么」，驱动后端的模型门控与前端的空态提示。

    注意：只统计「规范化之后」的客户表，品类/渠道一律来自 mapping，
    不要再按列名扫一遍——否则 web_visits_month 这类标准字段会被误认成渠道。
    """
    categories = {k: v["label"] for k, v in (mapping or {}).get("categories", {}).items() if k in df.columns}
    channels = {k: v["label"] for k, v in (mapping or {}).get("channels", {}).items() if k in df.columns}

    # 品类列必须真的有区分度（不是全 0）才算
    categories = {k: v for k, v in categories.items() if k in df.columns and float(df[k].fillna(0).sum()) > 0}

    def spread(col: str) -> bool:
        return col in df.columns and float(df[col].fillna(0).std(ddof=0)) > 0

    response_ok = False
    positives = 0
    if "response" in df.columns:
        positives = int(df["response"].fillna(0).sum())
        response_ok = positives >= 30 and 0 < positives < len(df)

    demo = {k: bool(k in df.columns and df[k].notna().any()) for k in ("age", "gender", "education", "marital_status", "children", "income")}

    return {
        "customers": int(len(df)),
        "has_income": spread("income"),
        "has_monetary": spread("total_spend"),
        "has_recency": spread("recency"),
        "has_frequency": spread("purchase_freq"),
        "has_response": response_ok,
        "response_positive": positives,
        "categories": categories,
        "channels": channels,
        "demographics": demo,
        "clustering": sum(1 for c in ("income", "total_spend", "purchase_freq", "recency", "num_deals", "web_visits_month", "age") if spread(c)) >= 2,
        "rfm": spread("recency") and spread("total_spend"),
        "association": len(categories) >= 2,
        "propensity": response_ok,
        "campaign": spread("total_spend") or bool(categories),
    }


def describe(mapping: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """生成给前端「数据说明」页用的可读映射表。"""
    rows = []
    for key, info in mapping["mapping"].items():
        spec = STANDARD_FIELDS.get(key, {})
        rows.append({
            "target": key,
            "label": spec.get("label", key),
            "source": info["source"],
            "confidence": info.get("confidence", "高"),
            "how": "列名完全一致" if info.get("score", 3) == 3 else "列名包含别名",
        })
    for key, info in mapping["categories"].items():
        rows.append({"target": key, "label": info["label"], "source": info["source"], "confidence": "高", "how": f"品类识别：{info.get('why', '')}"})
    for key, info in mapping["channels"].items():
        rows.append({"target": key, "label": info["label"], "source": info["source"], "confidence": "高", "how": f"渠道识别：{info.get('why', '')}"})
    return {
        "grain": mapping["grain"],
        "grain_label": "订单明细（按客户聚合）" if mapping["grain"] == "transaction" else "客户级宽表",
        "rows": rows,
        "unused_columns": mapping.get("unused_columns", []),
        "aggregations": ctx.get("aggregations", []),
        "warnings": ctx.get("warnings", []),
    }
