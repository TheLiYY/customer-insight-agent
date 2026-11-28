# 数据接入与字段映射

本文件说明如何接入自有数据：支持的文件格式、字段自动识别规则、字段别名扩展方式、能力开关与降级行为，以及五套实际数据的验证结果。

---

## 1. 设计动机

最初版本的 `prepare_data.py` 是**硬编码**的：它只认 `Ifood_df.csv` 那 39 个列名（`MntWines`、`Kidhome`、`AcceptedCmpOverall`…），少一列就报错。

这带来三个问题：

1. 换一份数据（比如公司 CRM 导出的客户表）要改代码；
2. 换一份数据（比如只有年龄+性别的商场会员表）要改代码；
3. 换个行业的表（比如银行电话营销名单）要改代码。

现在的做法是加一层**数据契约层（data contract）**：`backend/app/core/schema.py`。

它的职责只有一件事：**把任意一份客户表，翻译成项目内部的标准字段**；
翻译不了的字段就标记"缺失"，缺失之后下游各模块自动降级，而不是崩溃。

```
你的表（列名随便）
      │
      ▼  normalize_name()  去空格/下划线/括号、转小写、保留中文
      │
      ▼  _alias_score()    拿每个列名去撞别名表：3=完全相同 2=前缀 1=包含 0=不匹配
      │
      ▼  _is_numeric() / _is_binary_like()   再校验这一列的"内容"像不像
      │
      ▼  detect()          得到 mapping（标准字段 ← 源列）
      │
      ▼  build_customers() 类型转换、one-hot 反解、聚合、分箱、截尾
      │
      ▼  capabilities_of() 输出"这份数据能算什么"
      │
      ▼  customers.csv + mapping.json + dataset_meta.json
```

---

## 2. 三条使用路径

### 2.0 网页上传

打开前端的「我的数据」页，把文件拖进虚线框即可。流程是**两段式**：

1. **试读**：你只看到结果，不会动线上数据。页面会列出「原始 800 行 × 38 列 → 标准表 777 行 × 25 列」「命中 11 个标准字段」，以及每一列被认成了什么、置信度多少、哪些列没用上。
2. **应用**：点「用这份数据开始分析」，后端跑一次 `prepare_data.py --file ...`，完成后刷新缓存，全站立刻换成新数据。

页面上有「下载数据模板」，是一份空表 + 两套表头（客户级宽表 / 订单明细），按表头填写即可被完整识别。模板由后端现场生成：`GET /api/import/template`。

它和命令行走的是同一套读取与识别逻辑（`app/core/loader.py`、`app/core/schema.py`），所以**结果一致**。
接口细节见 [API.md](API.md#数据导入上传自己的客户表)。上传的文件放在 `backend/data/uploads/`，只保留最近 30 个，已被 `.gitignore` 排除。

> 说清楚一件事：前端**不再提供「切换内置数据集」的按钮**。内置数据（iFood / Mall / Bank）仍然保留，但只作为命令行与自动化测试的基准，日常使用就是你自己的文件。

### 2.1 内置三套数据（命令行 / 测试基准）

```bash
# 默认：iFood 客户画像（2205 行原始数据，跑完 2021 行有效客户）
python scripts/prepare_data.py

# 商场会员（200 行，只有编号/性别/年龄/收入/消费评分——没有金额、没有日期、没有响应标签）
python scripts/prepare_data.py --dataset mall

# 银行电话营销（4119 行，分号分隔，y=yes/no，有响应标签但没有金额）
python scripts/prepare_data.py --dataset bank
```

三套数据的作用不一样，讲项目时可以说：

| 数据集 | 行数 | 有的东西 | 没有的东西 | 用来证明什么 |
|---|---|---|---|---|
| iFood（默认） | 2205 → 2021 | 收入、6 品类消费、3 渠道、活动响应 | —— | 完整能力的基准 |
| Mall Customers | 200 → 200 | 年龄、性别、年收入、消费评分 | 金额、日期、响应、频次 | 只有人口属性也能出画像和聚类 |
| Bank Marketing | 4119 → 4119 | 年龄、职业、教育、婚姻、响应标签 y | 金额、收入、购买频次 | 有标签没金额，响应预测照样能练 |

切换数据集后**不用改任何代码**，前端会自动变：Bank 数据的总览页不会显示"人均消费"（因为没有金额），响应预测页正常显示（因为有 `y` 标签）。

### 2.2 用你自己的文件

```bash
# CSV（自动判断分隔符，UTF-8 失败自动试 GBK）
python scripts/prepare_data.py --file D:\data\客户表.csv

# Excel（指定 sheet，默认第一个）
python scripts/prepare_data.py --file D:\data\客户明细.xlsx --sheet Sheet1

# 分号分隔 + GBK 编码的老系统导出
python scripts/prepare_data.py --file D:\data\export.csv --sep ";" --encoding gbk
```

支持格式：`.csv` / `.xlsx` / `.xls` / `.tsv` / `.json`。

### 2.3 完整参数表

| 参数 | 作用 | 备注 |
|---|---|---|
| `--dataset {ifood,mall,bank}` | 用内置数据集 | 不写时默认 `ifood` |
| `--file PATH` | 用本地文件 | **优先于 `--dataset`** |
| `--sheet NAME` | 指定 Excel 的 sheet | 多 sheet 时必填 |
| `--sep CHAR` | 指定 CSV 分隔符 | 默认自动判断（`,` / `;` / `\t`） |
| `--encoding NAME` | 指定文件编码 | 默认 utf-8，失败自动试 gbk |
| `--mapping PATH` | 复用已有 `mapping.json`，跳过自动识别 | 适合列名每次都一样的场景 |
| `--refresh` | 强制重新联网下载 | 忽略本地缓存 |
| `--no-excel` | 不生成原始数据 Excel | 只想要 csv 时用 |
| `--title NAME` | 数据集显示名 | 网页上传时自动用文件名 |

**离线优先**：内置数据集第一次会联网下载并缓存到 `backend/data/raw/<key>.csv`；之后即使断网、或在 Docker 构建里，也会直接用缓存，保证**结果可复现**。

---

## 3. 自动识别是怎么工作的

### 3.1 三步走

1. **列名规范化**：`Annual Income (k$)` → `annualincomek`；`客户ID` → `客户id`。去掉空格、下划线、括号、标点，转小写，保留中文。
2. **撞别名表**：每个标准字段有一串别名（见第 4 节）。打分规则：
   - `3` = 完全相同，`2` = 前缀匹配，`1` = 包含，`0` = 不匹配；
   - 长度 ≤2 的短别名（`id`、`y`、`age`）**只允许完全相同**，否则 `y` 会命中一堆列。
3. **内容校验**：分数最高的列还要通过"内容像不像"的检查——
   - 数值字段：`_is_numeric()`，可转换率 ≥ 80%；
   - 二值字段：`_is_numeric()` 或 `_is_binary_like()`（`y/yes/no/是/否/1/0` 等）；
   - 品类字段：均值 ≥ 1.0（排除 `Teenhome` 这种 0/1 标记）；
   - 渠道字段：均值 ≥ 0.5。

### 3.2 置信度怎么读

`mapping.json` 和 Data 页里会显示每个字段的置信度：

| 分数 | 置信度显示 | 含义 | 建议 |
|---|---|---|---|
| 3 | 高 | 列名完全一致 | 可直接使用 |
| 2 | 中 | 前缀匹配（如 `Income` ↔ `annualincome`） | 建议扫一眼数据 |
| 1 | 低 | 只是包含关系（如 `zz_salary_note` ↔ `salary`） | **必须人工确认** |

低置信度的映射要当成"猜的"来看。项目在 `warnings` 里会把它们列出来。

### 3.3 常见误判与处理

自动识别很容易把所有列都"抢"走，下面这些规则是专门防这个的：

- **one-hot 列不参与匹配**：`education_Graduation`、`marital_Single` 这类列名以 `education`/`marital` 开头的、且同前缀有 ≥2 列的，判定为 one-hot，交给 `_education_from_onehot()` / `_marital_from_onehot()` 反解成单列。
- **交易字段不抢标准列**：`NumWebPurchases` 曾被识别成 `quantity`（因为别名里有 `num`）、`Z_Revenue` 被识别成 `amount`（因为别名里有 `revenue`）。现在 `amount/quantity/unit_price` 要求分数 ≥2 且该列不能是常量列。
- **`purchase_freq` 不抢渠道列**：别名里删掉了 `purchases`，否则 `NumWebPurchases`、`NumCatalogPurchases` 全被它吃掉。
- **`day_of_week` 不会被当成下单日期**：`order_date` 的别名删掉了 `day`，并额外排除 `dayofweek/weekday/month/dayofmonth/quarter/year`。
- **`web_visits_month` 不会被当成线上渠道**：渠道只从 mapping 推导，不按列名再扫一遍。

### 3.4 真实销售与会员数据的常见不规范

绝大多数公司的导出表都不是"算好的标准表"，下面四种情况会被自动兜住（都写进了 `mapping.json` 的 `how` 字段，能追溯）：

| 真实情况 | 长什么样 | 怎么处理 |
|---|---|---|
| 只有日期，没有"距今天数" | `最近消费时间 = 2025/10/08`、`入会日期 = 2024/03/12` | 识别成日期列，用**数据内最晚日期**作参考日，换算成 `recency`（最近购买间隔）和 `tenure_days`（在网天数）。参考日取数据内最晚的一单，保证同一份数据每次跑出来一致 |
| 金额带符号、千分位 | `￥1,234.56`、`1.2万` | 先去掉 `￥ / , / 元 / %`，再按结尾的 `万 / 千` 缩放，最后转数字 |
| 渠道、品类是**文字**而不是金额列 | 订单明细里 `来源渠道 = 天猫/抖音直播/门店/私域`、`商品类目 = 女装/家居` | 明细表按客户透视：品类 → 各品类消费额，渠道 → 各渠道下单次数；客户级表则按取值拆成 0/1 列。拆出来的列会注册回 `categories` / `channels`，所以渠道图、品类图、关联规则都能用 |
| 主键叫"会员卡号"而不是"客户编号" | `会员卡号 = VIP00001` | `customer_id` 的别名里收了 会员卡号 / 卡号 / 会员编号 / 顾客号 / 客户编码 / 买家编号 等 20 多种写法 |

实测口径（`docs/DATA.md` 第 8 节那张表用的就是这套判断）：

- 一份 2599 行的订单明细（会员卡号 / 下单时间 / 成交金额带 ￥ / 商品类目 / 来源渠道）→ 自动识别为**订单明细**，聚合出 419 位客户 × 14 列（含 5 个品类列、4 个渠道列），`has_monetary / has_recency / has_frequency` 全为 true。
- 一份 420 行的会员表（入会日期 / 最近消费时间 / 累计消费 / 消费次数 / 是否流失）→ 419 位客户 × 8 列，`recency` 由「最近消费时间」换算，`has_income=false`（表里确实没有收入）。

---

## 4. 字段别名表（想加自己的列名就看这里）

标准字段一共 17 个（`backend/app/core/schema.py` 的 `STANDARD_FIELDS`）。最常用的这些：

| 标准字段 | 中文含义 | 已支持的常见列名（部分） |
|---|---|---|
| `customer_id` | 客户编号 | `CustomerID`、`user_id`、`member_id`、`客户编号`、`会员号`、`编号` |
| `age` | 年龄 | `Age`、`customer_age`、`年龄`、`岁数` |
| `gender` | 性别 | `Gender`、`Sex`、`性别` |
| `income` | 收入 | `Income`、`Annual Income`、`salary`、`年收入`、`月收入`、`工资` |
| `education` | 学历 | `Education`、`degree`、`学历`、`教育程度` |
| `marital_status` | 婚姻 | `Marital_Status`、`marriage`、`婚姻状况`、`婚否` |
| `children` | 子女数 | `children`、`kids`、`子女数`（`Kidhome + Teenhome` 会自动相加） |
| `recency` | 最近购买间隔（天） | `Recency`、`days_since_last_purchase`、`pdays`、`未购买天数` |
| `purchase_freq` | 购买频次 | `frequency`、`orders`、`num_orders`、`previous`、`购买次数`、`订单数` |
| `total_spend` | 累计消费 | `MntTotal`、`monetary`、`amount`、`total_revenue`、`消费额`、`金额` |
| `value_score` | 消费评分 | `Spending Score`、`消费评分` |
| `tenure_days` | 在网天数 | `tenure`、`Customer_Days`、`注册天数`、`账龄` |
| `num_deals` | 折扣次数 | `NumDealsPurchases`、`discount_count`、`用券次数` |
| `web_visits_month` | 月访问次数 | `NumWebVisitsMonth`、`visits`、`访问次数` |
| `accepted_total` | 历史活动接受数 | `AcceptedCmpOverall`、`活动接受次数` |
| `response` | 活动响应 | `Response`、`y`、`target`、`converted`、`是否响应`、`是否转化` |
| `complain` | 是否投诉 | `Complain`、`complaint`、`是否投诉` |

> 完整名单见 `backend/app/core/schema.py` 第 32–161 行。

**加一个自己的别名**（比如公司表里收入列叫 `pay_level`）：

```python
# backend/app/core/schema.py 里找到 income，往 aliases 里加一句
"income": {
    ...
    "aliases": [..., "pay_level", "薪酬等级"],
},
```

加完重跑 `python scripts/prepare_data.py --file 你的表.csv` 即可生效。

---

## 5. 两种数据粒度

### 5.1 客户级宽表（一行 = 一个客户）

iFood、Mall、Bank 都是这种。直接逐列映射即可。

### 5.2 交易级明细（一行 = 一笔订单）

如果表是订单流水（同一客户出现多次），会自动识别成 `grain="transaction"` 并按客户聚合：

| 内部字段 | 聚合方式 | 说明 |
|---|---|---|
| `total_spend` | `amount` 求和 | 客户累计消费 |
| `purchase_freq` | `order_id` 去重计数 | 订单数 |
| `recency` | 参考日期 − 最近一单日期 | 越小越活跃 |
| `tenure_days` | 参考日期 − 最早一单日期 | 成为客户多久 |
| 品类消费 | 若表里有「品类」列，按客户 pivot | 每个品类一列 |

**参考日期**的取法很关键：

- 表里有下单日期 → 取**数据内的最晚日期**（保证同样的数据每次跑出同样结果）；
- 没有日期 → 取构建当天（会在 warnings 里提示"结果随运行日期变化"）。

### 5.3 判定条件

同时满足这三条才判交易级：

1. 客户编号重复率 > 30%；
2. 存在订单号 / 日期 / 金额之一；
3. 不是已经被判成客户级宽表的结构。

判定理由会写进 `mapping.json` 的 `grain_reasons`，Data 页也能看到。

---

## 6. capabilities：这份数据能算什么

每次跑完，`dataset_meta.json` 里会写一份"能力开关"：

```json
"capabilities": {
  "customers": 2021,
  "has_income": true,
  "has_monetary": true,
  "has_recency": true,
  "has_frequency": true,
  "has_response": true,
  "response_positive": 311,
  "categories": {"mnt_wines": "葡萄酒", "mnt_fruits": "水果"},
  "channels": {"num_web": "线上商城"},
  "demographics": {"age": true, "gender": false, "education": true, "marital_status": true, "children": true, "income": true},
  "clustering": true, "rfm": true, "association": true, "propensity": true, "campaign": true
}
```

各页面/接口据此降级：

| 缺失的东西 | 会怎样 |
|---|---|
| 没有 `income` | 收入相关图表隐藏，`avg_income` 返回 `null`（前端显示 `—`） |
| 没有金额（`total_spend`） | 消费分布/品类结构/ROI 隐藏；RFM 的 M 值不准（warning 提示） |
| 没有 `recency` | RFM 只剩 F/M 两维，分层仅供参考（warning 提示） |
| 没有 `purchase_freq` | 用各渠道次数之和兜底；再没有就"有消费记 1 次" |
| 没有 `response` | **响应预测页从导航里消失**（直接访问 URL 会回落到数据总览），`GET /api/propensity` 返回 `{"available": false, "reason": "..."}`；客户分层的「响应率」列、画像里的「活动响应率」、自动结论里的「精准触达」与响应相关指标一并隐藏；营销方案用 0.1 基线概率 |
| 没有任何品类列 | 关联规则、品类结构隐藏，营销方案不选品 |
| 没有 channel 列 | 渠道结构隐藏，方案默认"全渠道" |

前端判断依据就是 `GET /api/capabilities`，**没有的能力对应的页面/图表/指标列直接不出现**，不做"暂时不可用"的占位提示。

---

## 7. 产物清单

跑完 `prepare_data.py` 会写 4 个文件：

| 文件 | 内容 | 给谁看 |
|---|---|---|
| `backend/data/processed/customers.csv` | 标准字段的客户宽表（iFood 数据下为 25 列） | 后端（唯一数据来源） |
| `backend/data/processed/mapping.json` | 每个标准字段来自哪一列、置信度、用了什么处理 | 排查"为什么这列没被识别" |
| `backend/data/processed/dataset_meta.json` | 字段字典 + capabilities + warnings | 后端和前端 |
| `backend/data/raw/Customer_Personality_Analysis.xlsx` | 原始数据（前 5000 行）+ 客户明细 + 字段字典 + 数据来源 | **Excel 看数据用**（这就是"用 Excel 训练"的那份表） |

> `customers.csv` 用 UTF-8 编码，Excel 直接双击打开可能乱码（中文 Excel 默认 GBK）。
> 想看就用 `Customer_Personality_Analysis.xlsx`，或者用「数据 → 从文本/CSV」导入并选 UTF-8。

`mapping.json` 长这样：

```json
{
  "grain": "customer",
  "mapping": {
    "customer_id": {"source": "CustomerID", "score": 3, "confidence": "高", "how": "客户编号"},
    "income": {"source": "Annual Income (k$)", "score": 2, "confidence": "中", "how": "收入"},
    "children": {"source": "Kidhome + Teenhome", "score": 3, "confidence": "高", "how": "家庭子女数（儿童 + 青少年合并）"}
  },
  "categories": {"mnt_wines": "葡萄酒", "mnt_fruits": "水果"},
  "channels": {"num_web": "线上商城", "num_catalog": "邮购目录", "num_store": "线下门店"},
  "unused_columns": ["Z_CostContact", "Z_Revenue"]
}
```

`unused_columns` 很重要：**没被用上的列会列在这里**。如果发现你的"消费金额"列出现在这里，说明别名没匹配上，去第 4 节加别名。

---

## 8. 五套数据实测结果

前两套是仓库内置的基准数据，后三套是**市面上的真实客户/销售数据**，用 `python scripts/fetch_sample_data.py` 批量下载到 `test-data/`（不入库，48MB 的电商明细太大），然后在「我的数据」页面上传即可。

| 数据集 | 有效客户 | 能力 | 冒烟测试 |
|---|---|---|---|
| iFood（默认） | 2021 | 全部可用（画像/聚类/RFM/响应预测/关联规则/方案） | 21/21 PASS |
| Mall Customers | 200 | 画像、聚类可用；RFM 参考（缺频次与间隔）；无响应预测、无关联规则 | 21/21 PASS |
| Bank Marketing | 4119 | 画像、聚类、响应预测可用（y 作标签）；无金额，ROI 不可用 | 21/21 PASS |
| Superstore（零售订单明细） | 795 | 画像、RFM、关联规则、金额与 ROI 均可用 | 21/21 PASS |
| UCI Online Retail（54 万行） | 4373 | 画像、RFM 可用；金额由数量 × 单价计算 | 21/21 PASS |
| Telco Churn（客户级） | 7032 | 画像、金额可用；无响应预测（churn 为流失标签，不作为响应） | 21/21 PASS |

三套真实数据各自考的是什么：

- **Superstore**：8399 行订单明细，客户只有名字（`Customer Name`）没有编号，金额列叫 `Sales`，品类是 `Product Category`。它验证的是"没有编号、只有姓名也能按客户聚合"，以及文字品类能透视成列。
- **UCI Online Retail**：541909 行 × 8 列，没有金额列，只有 `Quantity` 和 `UnitPrice`，还有退货产生的负数数量。它验证的是大文件（48MB）和"数量 × 单价"自动算金额。
- **Telco Churn**：7043 行客户级宽表，`TotalCharges` 有 11 行是空格。它验证的是金额列带脏值时的清洗，以及 `Churn`（流失）**不会**被误当成"响应活动"。

Superstore 跑完的真实数字：795 位客户、人均消费 ¥18,762、人均 6.9 单、沉睡率 72.5%、前 20% 客户贡献 46.5% 营收、品类结构 Technology ¥598.4 万 / Furniture ¥517.9 万 / Office Supplies ¥375.3 万。

Mall 的 warnings（真实的降级提示）：

```
- 缺购买频次，按"有消费记 1 次"处理，RFM 的 F 维度仅供参考
- 缺最近购买间隔，RFM 的 R 维度用 0 填充，分层仅供参考
- 用「消费评分」代替消费金额，ROI 类指标不可用
```

Bank 的 headline（自动结论）：

```
4119 位客户整体响应率 10.9%；按响应概率筛选后的头部名单，转化率是平均水平的 3.06 倍。
```

注意 Bank 没有金额，所以"前 20% 贡献多少营收"这类结论自动消失了，只剩 3 条结论——**这就是"自动分析"该有的样子：数据支持什么就说什么**。

---

## 9. FAQ

**Q：我的表有中文列名，能认吗？**
能。`normalize_name()` 保留中文，别名表里 `收入`、`消费额`、`学历`、`子女数` 等都有。

**Q：我的表没有客户编号怎么办？**
会自动用行号生成 `C00001` 这种编号，并在 `warnings` 里提示。

**Q：我的表是订单明细，一个客户多行，能跑吗？**
能，见第 5 节。自动聚合，不用先自己做透视表。

**Q：一张 Excel 有多个 sheet 怎么办？**
用 `--sheet 名字` 指定。不指定时用第一个 sheet。

**Q：怎么确认识别对不对？**
打开前端「数据说明」页，看「字段自动映射」表（源列 → 标准字段 → 置信度），或者直接看 `mapping.json`。

**Q：数据换了之后 K 值、阈值要不要重调？**
不用。K 值默认 4（可用 `--k` 或修改 `Settings.cluster_k`），阈值是在验证集上按 F1 自动搜出来的，换数据会自己重算。

**Q：切换数据集后 git 变脏了，怎么恢复？**
数据产物是入库的（保证 Docker 构建离线可复现），所以切数据集会让 `backend/data` 出现改动。
想回到默认的 iFood 数据：

```bash
python scripts/prepare_data.py            # 切回 ifood（用仓库内缓存）
git checkout -- backend/data              # 丢弃这次跑出来的产物
```

**Q：跑完数据，需要重启后端吗？**
需要。数据在启动时加载并缓存（`store` 单例 + `lru_cache`），换数据后重启后端才会生效：
```bash
# 停掉原来的 uvicorn，然后重新启动
python backend/run.py
```

**Q：Docker 里能换数据吗？**
可以。把文件挂载进容器后覆盖启动命令：
```bash
docker compose run --rm api python /app/scripts/prepare_data.py --file /data/我的表.csv
```
或者改 `deploy/Dockerfile.api` 里 `RUN python /app/scripts/prepare_data.py` 这一行加参数。
