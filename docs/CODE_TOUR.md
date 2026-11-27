# 代码导读（CODE TOUR）

> 目标：**看完这份文档，你能指着任意一个文件说清楚它在干什么、为什么这么写。**
> 文档不简化代码，只解释代码——遇到面试/答辩追问「这行为什么这么写」时，来这里找答案。

阅读顺序建议：

1. 先看「1. 全景图」建立心智模型（5 分钟）
2. 再看「3. 后端执行链路」跟着一次请求走完（15 分钟）
3. 然后按需查「4. 模块逐个讲」里的某个文件
4. 想动手改代码，直接跳「6. 常见二次开发」

---

## 1. 全景图

```
┌──────────────────────────────────────────────────────────────┐
│  浏览器  React + Vite + ECharts（frontend/）                  │
│  9 个页面：总览 / 自动结论 / 画像 / RFM / 响应预测 / 方案 /   │
│            导入数据 / Agent 对话 / 数据说明                   │
└───────────────────────────┬──────────────────────────────────┘
                            │ HTTP  JSON（/api/*）
┌───────────────────────────▼──────────────────────────────────┐
│  FastAPI（backend/app/）                                      │
│                                                              │
│  api/routes.py        ← 14 个分析接口                        │
│  agent/routes.py      ← 对话接口                             │
│         │                                                    │
│         ▼                                                    │
│  core/store.py   ←  唯一的「结果仓库」，懒计算 + 缓存        │
│         │                                                    │
│   ┌─────┴──────┬──────────┬──────────┬───────────┐          │
│   ▼            ▼          ▼          ▼           ▼          │
│  rfm.py    clustering.py persona.py propensity.py association│
│   │            │          │          │           │          │
│   └────────────┴──────────┴──────────┴───────────┘          │
│                         │                                    │
│                    insights.py  ← 把数字翻译成结论            │
│                         │                                    │
│  data/processed/customers.csv（2021 × 25，脚本生成）          │
└──────────────────────────────────────────────────────────────┘
                            ▲
                            │ 生成
              scripts/prepare_data.py（下载 → 清洗 → Excel / CSV）
```

**一句话记住职责划分**：

| 层 | 职责 | 不要做的事 |
| --- | --- | --- |
| `scripts/` | 离线数据准备与导出 | 不要放业务逻辑 |
| `core/` | 纯计算，输入 DataFrame 输出 dict | 不要 import FastAPI |
| `api/` | 参数校验 + 调 store | 不要写算法 |
| `agent/` | 把计算能力包装成工具给人话调用 | 不要重复实现分析 |
| `frontend/` | 只负责展示 | 不要在前端做业务计算 |

---

## 2. 目录树与文件职责

```
customer-insight-agent/
├── backend/
│   ├── run.py                     # 启动入口（uvicorn），只做 sys.path 与端口
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py                # FastAPI 实例、CORS、异常兜底（纯 API，不托管前端）
│   │   ├── core/
│   │   │   ├── config.py          # 路径常量、字段中文映射、Settings
│   │   │   ├── utils.py           # clean/pct/quantile_score 等小工具
│   │   │   ├── dataset.py         # 读 CSV + 读 meta，带 lru_cache
│   │   │   ├── rfm.py             # RFM 五等分打分 + 8 分层 + 矩阵/矩形树
│   │   │   ├── clustering.py      # sklearn KMeans + 标准化 + 轮廓系数 + 命名
│   │   │   ├── persona.py         # 客群画像卡 + 规则打标签
│   │   │   ├── propensity.py      # sklearn 逻辑回归 + 阈值搜索 + AUC + Lift
│   │   │   ├── association.py     # mlxtend Apriori + 品类渗透率
│   │   │   ├── campaign.py        # 营销方案生成（圈人/选品/渠道/ROI）
│   │   │   ├── overview.py        # 总览页所有图表数据
│   │   │   ├── insights.py        # ★ 自动结论：指标 → 结论 + 证据 + 动作
│   │   │   └── store.py           # 单例仓库，懒加载 + 缓存
│   │   ├── api/routes.py          # 13 个 REST 接口
│   │   └── agent/
│   │       ├── tools.py           # 8 个工具 + 4 种渲染块
│   │       ├── orchestrator.py    # 意图识别 / 在线 function calling / 离线规则
│   │       └── routes.py          # /api/agent/chat
│   ├── data/raw/                  # 原始 CSV + 给业务看的 Excel
│   ├── data/processed/            # 清洗后的 customers.csv + 报告 xlsx
│   ├── tests/smoke_test.py        # 21 项接口/对话冒烟测试
│   └── tests/test_contract.py     # 52 项数据契约测试
├── frontend/
│   ├── vite.config.js             # dev 代理 /api → 8000
│   └── src/
│       ├── App.jsx                # 左侧导航 + 页面路由（自己写的极简路由）
│       ├── lib/api.js             # 所有 fetch 封装
│       ├── lib/format.js          # 数字/百分比/金额格式化 + 调色板
│       ├── components/Chart.jsx   # ECharts 封装（含 ResizeObserver + dispose）
│       ├── components/ui.jsx      # Card / Kpi / Table / Tag / Tabs
│       └── pages/*.jsx            # 9 个页面（含导入数据）
├── scripts/
│   ├── prepare_data.py            # 下载(或 --xlsx 读本地 Excel) + 清洗 + 生成 Excel/CSV/meta
│   ├── export_report.py           # 生成分析报告 Excel（9 个 sheet）
│   └── export_openapi.py          # 导出 OpenAPI / Postman 给 Apifox 用
├── deploy/                        # 部署相关（前端只走 Nginx，两种跑法）
│   ├── nginx.conf                 # 本机 Nginx：托管 dist + 反代 /api → 127.0.0.1:8000
│   ├── nginx.docker.conf          # 容器内 Nginx：托管 dist + 反代 /api → api:8000
│   ├── Dockerfile.api             # 后端镜像（Python 3.13 + 依赖 + 内置数据）
│   ├── Dockerfile.web             # 前端镜像（node:20 构建 → nginx 托管）
│   ├── docker-compose.bundle.yml  # 换机器用（无 build 段，配 images.tar）
│   ├── make-bundle.ps1            # 一键打离线部署包
│   ├── BUNDLE_README.md           # 部署包里给目标机看的三步说明
│   └── DOCKER.md                  # Docker 部署原理与排障表
├── docker-compose.yml             # 一键启动 web + api（带 build 段）
├── .dockerignore                  # 构建上下文排除项
└── docs/                          # README 之外的说明文档都在这里
```

---

## 3. 后端执行链路：跟着一次请求走完

### 3.1 启动

```
python backend/run.py
  → sys.path.insert(0, backend/)
  → uvicorn.run("app.main:app", host=127.0.0.1, port=8000)
      → app/main.py: app = FastAPI(...)
      → app.include_router(api.routes.router)
      → app.include_router(agent.routes.agent_router)
```

`run.py` 里没有业务代码，只做两件事：拼 `sys.path`、启 uvicorn。
好处是 IDE 里直接点运行也能跑，不用设环境变量。

### 3.2 一次「看客户画像」请求

```
GET /api/personas
  → api/routes.py::get_personas()
      → store.cluster          （第一次访问时触发计算，之后命中缓存）
          → clustering.run_clustering(rfm_df, CLUSTER_FEATURES, k=4, seed=42)
              → 取 7 个特征矩阵 → StandardScaler → KMeans(n_init=10)
              → sklearn silhouette_score
              → 按综合价值分排序 → 命名（核心高价值客群…）
              → 返回 {labels, table, k, silhouette, inertia, features, centers_raw, clusters}
      → store.personas
          → persona.build_all(cluster_table, clusters, df)
              → 每个簇算人群构成、价值指标、品类/渠道偏好、行为
              → _tags() 规则打标签
              → 生成 headline / summary
      → 组装成 JSON 返回
```

**为什么 `store.cluster` 第一次会很慢、后面很快**：
`Store` 里所有重计算都写成 `@property` + `if self._x is None` 的懒加载模式。
2021 行数据全内存计算，首次约 2 秒，之后毫秒级。
未来数据涨到百万级，把这个类换成「离线跑批 + DuckDB/Parquet 查询」即可，**接口层一行都不用改**。

### 3.3 一次 Agent 对话

```
POST /api/agent/chat  {"message": "分析完有什么结论？"}
  → agent/routes.py::chat()
      → orchestrator.chat(message, history)
          ├─ 若配置了 LLM_BASE_URL/LLM_API_KEY → llm_chat()
          │     → 发 SYSTEM_PROMPT + 工具定义给大模型
          │     → 模型返回 tool_calls → tools.TOOLS[name](args)
          │     → 把结果回传给模型 → 模型产出自然语言总结（最多 3 轮）
          │     → 任何异常都 fallback 到 rule_chat()
          └─ 否则 → rule_chat()
                → _detect_tool(message)  关键词打分选工具
                → 抽参数（预算、客群、客户编号）
                → tools.TOOLS[tool](args) → blocks
                → _reply_for() 配一句开场白
  → 返回 {reply, blocks, intent, args, mode:"rules"|"llm"}
```

**`blocks` 只有 4 种类型**，这是让「前端渲染」和「大模型选工具」都变简单的关键设计：

| 类型 | 结构 | 前端渲染成 |
| --- | --- | --- |
| `text` | `{type, content}` | 一段文字 |
| `kpi` | `{type, items:[{label,value,suffix}]}` | 一排指标卡 |
| `chart` | `{type, title, option, note}` | ECharts 图（option 直接给 ECharts） |
| `table` | `{type, title, columns, rows}` | 表格 |

**为什么这样设计**：如果让大模型直接生成 HTML 或 ECharts 配置，
它很容易编出不存在的字段，前端就崩了。
让工具输出**结构化积木**，大模型只负责「用文字把积木串起来」，稳定得多。

---

## 4. 模块逐个讲

### 4.1 `core/config.py` — 常量集中营

```python
BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent
CUSTOMERS_CSV = DATA_DIR / "processed" / "customers.csv"

CLUSTER_FEATURES = ["income", "total_spend", "purchase_freq",
                    "recency", "num_deals", "web_visits_month", "age"]
```

- 三个路径常量解决「从任何目录启动都能找到数据」。
- `CLUSTER_FEATURES` 是聚类的 7 个维度，改这里就改了画像的「观察角度」。
- `EDUCATION_LABELS` / `zh_education()`：把 `Graduation` 映射成「本科」，
  所有中文展示都走这两个函数，**统一口径只改一处**。

`Settings` 用 `@dataclass` 而不是 pydantic，
因为配置项少、想保持 `core/` 不依赖 Web 框架（`core/` 里不出现 FastAPI 是有意为之）。

### 4.2 `core/schema.py` — 数据契约层（「换数据也能跑」的核心）

这是全项目第二长的文件（约 770 行），但它只做一件事：**把任意一份客户表翻译成标准客户字段**。

```python
STANDARD_FIELDS = {
    "income":  {"label": "收入",  "type": "number",
                "aliases": ["income", "annualincome", "salary", "年收入", "工资", ...]},
    "recency": {"label": "最近购买间隔", "type": "number",
                "aliases": ["recency", "dayssincelastpurchase", "pdays", "未购买天数", ...]},
    ...
}

def detect(df) -> dict:          # 列名 → 标准字段的映射（含置信度与理由）
def build_customers(df, mapping, reference_date=None) -> tuple[DataFrame, dict]:
def capabilities_of(df, mapping) -> dict:   # 这份数据能算什么
```

工作流程（三步）：

1. **列名规范化 + 撞别名**：`normalize_name()` 去掉空格/下划线/括号并转小写，
   然后 `_alias_score()` 打分（3 完全相同 / 2 前缀 / 1 包含 / 0 不匹配）。
   长度 ≤2 的短别名（`id`、`y`、`age`）只允许完全匹配。
2. **内容校验**：数值列要求可转换率 ≥80%；二值列接受 `y/yes/no/是/否/1/0`；
   品类列要求均值 ≥1.0（排除 `Teenhome` 这种 0/1 标记）；渠道列要求均值 ≥0.5。
3. **类型转换与聚合**：`build_customers()` 里处理 one-hot 反解、`Kidhome + Teenhome`
   合并、订单明细按客户聚合、金额缺失时用消费评分代替、年龄分箱、收入 99 分位截尾。

`capabilities_of()` 输出「能力开关」（有没有收入/金额/间隔/频次/响应标签），
写进 `dataset_meta.json`，后端各模块和前端都靠它决定「降级还是渲染」。

> 为什么不把识别逻辑写进 `prepare_data.py`？因为 `scripts/` 只该负责「流程编排」，
> 「怎么认字段」是这个领域知识，放进 `core/` 才能被单测和别的脚本复用。

### 4.3 `core/dataset.py` — 数据注册中心

它是后端**唯一**读数据的地方，全部 `lru_cache`：

```python
@lru_cache(maxsize=1)
def load_customers(path=None) -> pd.DataFrame:      # 读 customers.csv，只对 BASE_NUMERIC 做数值化
@lru_cache(maxsize=1)
def load_meta() -> dict:                            # dataset_meta.json
def categories() -> dict:  # {"mnt_wines": "葡萄酒", ...}，优先 meta，回退 config
def channels() -> dict:    # {"num_web": "线上商城", ...}
def capabilities() -> dict:                         # 能力开关；没有 meta 时现场推断
def numeric_fields() -> list[str]:                  # 可参与聚类的数值列
def clear_cache() -> None:                          # store.reload() 里调
```

**踩过的坑**：`load_customers()` 早期内部调 `numeric_fields()`，而 `numeric_fields()`
又调 `load_customers()` → `RecursionError: maximum recursion depth exceeded`，所有接口 500。
现在 `load_customers()` 只对固定的 `BASE_NUMERIC` 列表做 `pd.to_numeric`，不再回头问 `numeric_fields()`。

`categories()` / `channels()` 是**动态的**：iFood 数据是 6 品类 3 渠道，
换成别的表可能就是 2 品类 1 渠道，所有模块遍历这两个函数，不再硬编码 `mnt_wines` 之类。

### 4.4 `core/rfm.py` — RFM 三把尺子

核心函数 `build_rfm(df)`：

1. `quantile_score(series, reverse=True/False)`：按五分位打 1–5 分。
2. **R 要反转**：间隔天数越小越好，所以 `reverse=True`。
3. 三个分数拼成 `rfm_score` 字符串（如 `"555"`）。
4. `>=3` 视为「高」，映射到 8 个中文分层名（`SEGMENTS` 字典里带 priority/desc/action）。
5. `segment_summary()` 按分层聚合，输出人数、营收占比、平均 R/F/M、响应率。

**最容易踩的坑**：所有人在 R/F/M 上都被切成五等分，
所以每个分数的样本量都是 20%，这是**分位打分的数学必然**，
不代表业务上真的均匀分布——讲的时候要主动说明。

### 4.5 `core/clustering.py` — sklearn KMeans

见 `GLOSSARY.md` 第 2 节。代码要点：

```python
scaler = StandardScaler()
scaled = scaler.fit_transform(matrix)
model = KMeans(n_clusters=k, n_init=10, random_state=seed)
sil = silhouette_score(scaled, labels, sample_size=min(n, 1500), random_state=seed)
```

- `sample_size`：轮廓系数是 O(n²)，抽样算结果就足够稳定（数据量大的时候尤其必要）。
- `centers_raw = scaler.inverse_transform(model.cluster_centers_)`：把中心点还原成真实业务量纲，
  前端展示的「平均收入 7.8 万」就是这么来的。
- 命名排序用 `score = 0.5*z(spend) + 0.3*z(freq) - 0.2*z(recency)`，
  这里的 0.5/0.3/0.2 是**业务权重假设**，不是数学推导结果，可以在答辩时说明。

### 4.6 `core/persona.py` — 从数字到「人」

输入：`cluster_table`（每个客户带 cluster 编号）、`clusters`（簇统计）、原始 df。
输出：每个客群一张卡：

```python
{
  "name": "核心高价值客群", "status": "活跃", "size": 687, "ratio": 0.361,
  "headline": "高收入 · 高价值 · 高频复购",
  "tags": ["高收入", "高价值", "近期活跃", "葡萄酒重度用户", "线下门店为主"],
  "demographics": {...},   # 年龄/学历/婚姻/有孩比例
  "value": {...},          # 收入/消费/频次/客单价/间隔/在网天数
  "categories": [...],     # 六品类消费
  "channels": [...],       # 三渠道次数
  "behavior": {...}        # 折扣依赖/月访问/活动接受率/响应率/投诉率
}
```

`_tags()` 是一堆 `if 指标 > 分位:` 的规则，**没有模型，纯业务经验**——
这类「规则 + 阈值」的标签在真实项目里比黑盒模型更受欢迎，因为运营能理解、能反驳、能改。

### 4.7 `core/propensity.py` — 响应预测

```python
model = LogisticRegression(class_weight="balanced", C=1.0, max_iter=2000, random_state=seed)
pipe = Pipeline([("scaler", StandardScaler()), ("lr", model)])
```

- 用 `Pipeline` 把标准化和模型绑在一起，避免「训练时标准化了、预测时忘了」这种经典 bug。
- 阈值搜索：`precision_recall_curve` 直接给出所有阈值下的 P/R，取 F1 最大处。
  **比手写 0.05~0.80 的 for 循环更快更准**（这是用 sklearn 的理由之一）。
- `roc_auc_score`、`confusion_matrix(labels=[0,1])` 都是现成的。
- 返回键保持稳定：`table / features / coefs / intercept / train_metrics / full_metrics / lift / base_rate / threshold`，
  前端和导出脚本都依赖这些键名，**改返回结构要同步改三处**（前端、export_report、tools）。

### 4.8 `core/association.py` — Apriori

```python
te = TransactionEncoder()
encoded = te.fit(transactions).transform(transactions)
freq = apriori(pd.DataFrame(encoded, columns=te.columns_), min_support=0.03, use_colnames=True, max_len=2)
rules = association_rules(freq, metric="confidence", min_threshold=0.15)
```

- `max_len=2`：只挖 1–2 个品类的组合，够用且能讲清楚。
- 只保留「单前件 → 单后件」，多对多规则业务上没法落地。
- 按 lift 降序取前 20，前端表格直接展示。
- **诚实说明**：本项目品类渗透率极高（都 90%+），lift 只在 1.05–1.10 之间，
  所以在自动结论里写的是「交叉销售要谨慎，建议组合套餐」而不是吹规则多强。

### 4.9 `core/campaign.py` — 方案生成器

`build_plan(df, scores, segment_field, segment, budget, cost_per_contact, discount, rules)`：

1. **圈人**：`N = budget / cost_per_contact`，取该客群内 `prob` 最高的 N 人。
2. **选品**：该客群品类消费 top3 + 关联规则里的 upsell。
3. **渠道**：三种渠道购买次数求和，取占比最高。
4. **时机**：按客群平均 recency 分三档（近期活跃 → 3 天内 / 中等 → 一周内 / 沉默 → 两周内）。
5. **ROI**：`预期响应人数 = N × 该批人平均概率`，`预期营收 = 响应人数 × 转化率 × 客单价`，
   `ROI = 预期营收 / budget`。
6. 输出话术 `copy`、优先级 `priority`、名单预览 `audience_preview`。

**为什么 ROI 一定 > 1**：因为客单价（几百元）远高于触达成本（8 元），
只要圈对人群，ROI 就好看。**这一点要主动说明**——
真实业务里还要算物流、退货、毛利，ROI 会低不少，别把演示值当成承诺。

### 4.10 `core/insights.py` — 自动结论（本次新增的核心能力）

这是「分析完自动出结论」的实现，也是最能体现"业务理解"的模块。

```python
def build_insights(df, kpis, segments, personas, prop, rules, penetration) -> dict:
    # 1. 价值集中度：前 20% 客户贡献多少营收、最大客群是整体的几倍
    # 2. 沉默风险：超过 75 天未购占比 ≥ 20% 触发预警
    # 3. 响应预测价值：Top10% 的 lift、能覆盖多少响应客户、AUC
    # 4. 品类结构：主品类营收占比
    # 5. 关联规则：lift ≥ 1.05 建议交叉销售，否则建议组合套餐
    # 6. 渠道结构：主要成交渠道
    # 7. 人群结构：学历/婚姻/年龄主力人群
    # 8. 利润健康：折扣依赖 ≥18%、投诉率 >1%
    # 9. 客群分化：哪些客群出现沉默预警
```

**设计要点**：

- **确定性规则，不是大模型生成**。每条结论都能追溯到具体数字，
  演示时被追问「这个结论怎么来的」可以直接报数。
- 三段式结构 `title / conclusion / evidence / action`：
  前端可以只显示标题（概览），也可以展开看证据链（答辩）。
- `actions` 按 `priority` 排序，形成「先做什么、后做什么」的执行清单。
- 配置了大模型时，这些结论会作为工具结果交给 Agent 复述，
  大模型只负责组织语言，**不会编造数字**。

**想加一条新结论**：在 `build_insights` 里加一个 `add(...)` 调用即可，
参数是 `(category, severity, title, conclusion, evidence, action, priority)`。
前端会自动渲染，不用改前端。

### 4.11 `core/overview.py` — 总览页数据

`kpis()` 算 12 个核心指标；其余函数各负责一张图：
`age_distribution` / `education_distribution` / `marital_distribution` /
`income_buckets` / `category_spend` / `channel_mix` / `response_by` /
`histogram` / `correlation`。

`correlation()` 用 `df[cols].corr()` 算皮尔逊相关矩阵，
返回 `{x: 列名, y: 列名, values: 二维数组}` 给前端画热力图。

### 4.12 `core/store.py` — 结果仓库

**这是后端的"心脏"**。所有重计算都在这里懒加载、缓存：

| property | 触发什么计算 | 前端哪个页用 |
| --- | --- | --- |
| `df` | 读 CSV | 全部 |
| `rfm` / `segment_summary` | RFM 打分 + 聚合 | RFM 分层 |
| `cluster` / `cluster_table` | KMeans | 客户画像 |
| `personas` | 画像卡 | 客户画像 |
| `propensity` / `scores` | 逻辑回归 | 响应预测 |
| `rules` / `penetration` | Apriori | 品类结构 |
| `overview` | 总览统计 | 数据总览 |
| `insights` | 自动结论 | 自动结论 |
| `enriched` | 明细 + 客群 + 概率（merge） | 客户明细表 |

**为什么用 `@property` 而不是在 `__init__` 里全算一遍**：
启动快（打开首页只算总览，不跑模型），而且某个模块报错不会拖垮整个服务。

**线程安全**：FastAPI 默认在线程池里跑同步函数，多个请求可能同时触发计算。
`_lock` 目前只用于 `reload()`，因为懒加载的计算是幂等的（重复算一次结果一样）。
数据量大到需要严格单例计算时，把 `if self._x is None` 换成双检锁即可。

### 4.13 `api/routes.py` — 14 个分析接口

全部是「取 store 的某个 property → 组装成 JSON」，几乎不含逻辑，所以很好读。
唯一有业务的是 `GET /api/customers`（分页 + 筛选 + 排序）和
`POST /api/campaign/plan`（Pydantic 校验参数后调 `store.plan()`）。

**接口设计约定**：

- 所有列表型字段统一 `[{name, value}]` 形状，前端图表组件不用写适配层。
- 百分比统一用 0–1 小数返回，前端 `pct()` 负责乘 100 加 `%`。
- 金额统一用元（浮点），前端 `money()` 负责「1.2 万」这种可读格式。

### 4.14 `agent/tools.py` — 工具箱

8 个工具，每个都是「取 store → 组装 blocks」：

| 工具 | 回答什么问题 |
| --- | --- |
| `overview_report` | 整体数据怎么样 |
| `insights_report` | 分析完有什么结论和建议（★ 新增） |
| `segment_report` | 客户怎么分层、哪些重要 |
| `persona_report` | 客户画像长什么样 |
| `propensity_report` | 该推给谁、谁会买 |
| `campaign_plan` | 生成营销方案 |
| `category_report` | 品类关联、怎么组合 |
| `customer_profile` | 某个客户 C00001 什么样 |

**为什么工具返回 blocks 而不是字符串**：见 3.3 节。

### 4.15 `agent/orchestrator.py` — 大脑

```python
def chat(message, history):
    if settings.llm_enabled:
        try:
            return llm_chat(message, history)     # 在线：function calling
        except Exception as exc:
            result = rule_chat(message, history)  # 兜底
            result["fallback_reason"] = f"{type(exc).__name__}: {exc}"
            return result
    return rule_chat(message, history)
```

- `_detect_tool()`：先看有没有客户编号（`C\d{5}`）→ 直接查明细；
  否则给每个意图的关键词打分，取最高分。
- `_extract_budget()`：正则支持「预算 20000」「2万」两种写法。
- `_extract_segment()`：把「高价值」「沉睡」等口语映射到正式客群名（`SEGMENT_ALIASES`）。
- 在线模式：`SYSTEM_PROMPT` 约束模型「必须先调工具再回答，不许编数字」，最多 3 轮工具调用。

**双模式的意义**：没有 API Key 也能完整演示；
有 Key 时对话更自然。答辩现场网络不稳也不会翻车。

### 4.16 `frontend/src/lib/api.js` — 所有请求的唯一出口

```js
const BASE = import.meta.env.VITE_API_BASE || '/api'
```

- 开发时 `/api` 由 Vite 代理到 `127.0.0.1:8000`（见 `vite.config.js`）。
- 生产部署到不同域名时，构建时设 `VITE_API_BASE=https://api.example.com/api`。
- 所有错误统一抛 `Error(detail)`，页面用 `ErrorBox` 统一展示。

### 4.17 `frontend/src/components/Chart.jsx` — ECharts 封装

```js
const chart = echarts.init(ref.current)
const ro = new ResizeObserver(() => chart.resize())
return () => { ro.disconnect(); chart.dispose() }
```

**两个必做动作**：
1. `ResizeObserver`：侧边栏收起/窗口缩放时图表跟着变，不会糊。
2. `dispose()`：组件卸载时销毁实例，避免内存泄漏（切换页面时尤其明显）。

### 4.18 `frontend/src/pages/Insights.jsx` — 自动结论页（新增）

纯展示：KPI 行 + 一句话结论 + 按严重程度过滤 + 每条结论一张卡（标签/标题/结论/证据/建议）+ 行动清单表。

**关键点**：页面里没有任何计算，所有文字都来自 `/api/insights`。
这样「结论怎么来的」永远只有一个地方需要维护（后端 `insights.py`）。

### 4.19 `core/loader.py` + `api/imports.py` — 上传自己的数据

这两块是「换数据」功能的全部后端代码，职责分得很干净：

- **`core/loader.py`**：只管「把文件变成一个 DataFrame」。Excel 用 openpyxl，JSON 用 `read_json`，
  CSV 先嗅探分隔符（分号/制表/逗号），再依次尝试 `utf-8` → `gbk`，失败时退回 `sep=None, engine="python"`。
  命令行的 `--file` 和页面上的拖拽上传都走这一个函数，所以两边对同一个文件的解析结果一定一致。
- **`api/imports.py`**：只管 HTTP 与生命周期。
  - `POST /inspect`：存一份临时上传 → `schema.detect()` + `schema.build_customers()` → 返回「会被怎么理解」，
    **不写 processed/，也不碰 store**，所以试读再多次，线上数据也不会变。
  - `POST /apply`：用 `subprocess` 调一次 `scripts/prepare_data.py --file ...`，成功后再 `store.reload()`，
    然后在后台线程里预热 overview/cluster/propensity/insights，避免用户点进页面时等首屏计算。
  - 上传文件落在 `backend/data/uploads/`，超过 30 个自动清理最旧的；文件名做了 `_safe_name()` 清洗，
    防目录穿越。

**为什么用 subprocess 而不是直接调函数**：清洗脚本已经是一个稳定、可单独运行的入口，
子进程调用能保证「命令行能跑 = 页面上能跑」，也避免把 numpy/pandas 的中间状态留在 Web 进程里。

### 4.20 `frontend/src/pages/Import.jsx` — 我的数据页（上传 + 试读 + 应用）

三段式界面：拖拽区 → 识别结果（KPI / 能力开关 / 字段映射表 / 原始数据预览）→ 应用按钮。
多 sheet 的文件会多出一个下拉框，切换后重新调 `/inspect` 再读一遍。

**关键点**：`apply` 成功后会调用父组件的 `onDataChanged()`，它做两件事——刷新侧边栏统计、
把页面 `key` 加一强制所有页面重新挂载（因为每个页面都是「挂载时取一次数」，重挂载就等于重新取数）。

---

## 5. 数据从哪来、到哪去

```
你的原始表（任意列名；内置 iFood 是 2205 行 × 39 列）
   │  ① scripts/prepare_data.py 读入：download() 多镜像下载 / --file 本地 csv·xlsx / --dataset 内置三套
   ▼
backend/data/raw/source_raw.csv（原始副本，可复现）
   │  ② core/schema.py::detect()   列名规范化 → 撞别名 → 内容校验 → mapping（哪个标准字段来自哪列）
   │      core/schema.py::build_customers()  类型转换 → one-hot 反解 → 订单明细聚合 → 分箱/截尾
   ▼
backend/data/processed/customers.csv（2021 行 × 25 列，标准字段）
   │  ③ 同时生成
   ├─→ backend/data/processed/mapping.json              （字段映射 + 置信度 + 未使用列，排查「为什么没认出来」）
   ├─→ backend/data/processed/dataset_meta.json         （字段字典 + capabilities 能力开关 + warnings）
   └─→ backend/data/raw/Customer_Personality_Analysis.xlsx（给业务看的 Excel：客户明细/字段字典/数据来源）
   │  ④ 后端启动后
   ▼
store 里各模块计算结果（各模块都读 dataset.categories()/channels()/capabilities()，不硬编码字段）
   │  ⑤ scripts/export_report.py
   ▼
backend/data/processed/Customer_Insight_Report.xlsx  （9 个 sheet + 4 张原生图表）
```

**这条链路的关键变化**：以前第 ② 步是 39 列硬编码映射（换数据必炸），
现在是 `schema.py` 自动识别 + `capabilities` 能力声明（换数据自动降级）。
三套数据（iFood / Mall / Bank）跑的都是同一条链路，只有第 ① 步的输入不同。

**为什么保留两份 Excel**：

- `Customer_Personality_Analysis.xlsx` 是**数据源**（训练/测试的输入，业务方也能直接打开看原始数据）；
- `Customer_Insight_Report.xlsx` 是**分析结果**（给不看网页的人看的报告）。

---

## 6. 常见二次开发

| 想做什么 | 改哪里 | 注意 |
| --- | --- | --- |
| 换数据集 | 什么都不用改：`python scripts/prepare_data.py --file 你的表.xlsx` | 列名认不出来就去 `core/schema.py` 的 `STANDARD_FIELDS` 里补别名；要跑响应预测得有 `response`/`y` 这类标签列。详见 [`DATA.md`](DATA.md) |
| 支持新平台/新导出格式 | `scripts/prepare_data.py` 的 `PRESETS` 加一条 | 填 name/desc/urls/sep 即可 |
| 改客群数量 | `config.py` 的 `Settings.cluster_k` | 名字池只有 6 个，k>6 会自动补编号 |
| 加画像标签 | `persona.py::_tags()` | 用分位数做阈值，别写死绝对值 |
| 加自动结论 | `insights.py::build_insights()` 里加一个 `add(...)` | 前端自动渲染，无需改前端 |
| 加 API | `api/routes.py` 加一个 `@router.get` | 记得在 `docs/API.md` 补说明 |
| 加 Agent 工具 | `tools.py` 写函数 + 加进 `TOOL_SPECS` | `params` 里声明参数，规则模式要在 `orchestrator` 里抽参数 |
| 改前端配色 | `frontend/src/lib/format.js` 的 `PALETTE` | 只改一处，全站生效 |
| 改部署地址 | 前端构建时 `VITE_API_BASE`；后端 CORS 在 `config.py` | 见 README「部署」一节 |

---

## 7. 调试技巧

```powershell
# 1. 只看后端算得对不对（不启服务）
python -c "import sys; sys.path.insert(0,'backend'); from app.core.store import store; print(store.insights['headline'])"

# 2. 跑全量冒烟测试
python backend/tests/smoke_test.py

# 2.1 只想看「换数据后字段还认得对不对」
python backend/tests/test_contract.py

# 3. 看某个接口的原始 JSON
python -c "import sys,json; sys.path.insert(0,'backend'); from fastapi.testclient import TestClient; from app.main import app; print(json.dumps(TestClient(app).get('/api/propensity').json(), ensure_ascii=False, indent=2)[:2000])"

# 4. 重新生成数据与报告
python scripts/prepare_data.py
python scripts/export_report.py
```

**常见报错对照**：

| 报错 | 原因 | 解决 |
| --- | --- | --- |
| `ModuleNotFoundError: fastapi` | 没装依赖 / 用错解释器 | 激活 venv 后再跑，见 README |
| 前端 `无法连接后端` | 后端没启动或端口不对 | 先 `python backend/run.py`，确认 8000 端口 |
| 页面空白 + 控制台 /assets 404 | Nginx 的 root 没指向 frontend/dist | 看 `deploy/README.md` 排障表，`nginx -t` 后 reload |
| `pydantic_core` 版本冲突 | 混用了不同 Python 版本的包 | 删掉旧的 `.deps`/重装 venv |

---

## 8. 代码里几个"有意为之"的选择

1. **`core/` 不 import FastAPI**：让核心算法可以脱离 Web 单独跑（脚本、Notebook、定时任务都能复用）。
2. **算法用 sklearn / mlxtend，不手写**：可维护、有文档、能解释，是工程实践的正确选择。
3. **不做前端状态管理库**：9 个页面、每个页面一次 fetch，`useState` 足够；引入 Redux 只会增加理解成本。
4. **不做数据库**：2021 行 CSV 读取耗时 <100ms，上数据库反而增加部署复杂度。数据涨到十万级时换 DuckDB 即可。
5. **Agent 双模式 + 规则兜底**：演示稳定性的优先级高于"看起来高级"。
6. **自动结论文案写死在代码里**：保证每条结论可追溯到数字，不会出现"大模型编了个不存在的 30%"。
7. **部署只保留 Nginx 一种前端方式**：静态托管 + `/api` 反代同源，省掉 CORS 与跨域调试；本机与容器只是换一份 conf。

---

## 9. 部署链路（Docker 版是怎么跑起来的）

想让别人也能跑，最省事的是两个容器。执行 `docker compose up -d --build` 之后发生的事：

```
① 构建阶段（只在这台「打包机」上发生，且只需要一次）
   deploy/Dockerfile.web
     node:20 → npm i -g pnpm → pnpm install → pnpm build → 产出 /app/dist
     ↓ 把 dist 拷进 nginx:stable-alpine 的 /usr/share/nginx/html
   deploy/Dockerfile.api
     python:3.13-slim → pip install -r backend/requirements.txt（含 sklearn/mlxtend）
     → 拷 backend/ 与 scripts/ → 跑一次 prepare_data.py（离线，用仓库自带原始 CSV）
     ↑ 所以镜像里的 customers.csv 与代码版本永远一致

② 运行阶段
   api 容器：uvicorn app.main:app --host 0.0.0.0 --port 8000（不向宿主机发布端口）
   web 容器：nginx 监听 80，宿主机 8080 → 容器 80
             /            → 静态文件（index.html 不缓存，/assets 强缓存 1 年）
             /api/        → proxy_pass http://api:8000（容器内网 DNS 解析服务名 api）
             /docs /openapi.json → 同样反代，Apifox/浏览器可直接打开
             /healthz     → 返回 ok，给容器 HEALTHCHECK 用

③ 依赖顺序
   api 的 HEALTHCHECK 打 /api/health，compose 用 depends_on: service_healthy
   等 api 真起来了才起 web，避免首次打开页面接口 502

④ 换机器
   docker save 两个镜像 → images.tar；目标机 docker load → compose up -d
   基础镜像层也在 tar 里，所以目标机不需要联网、不需要源码
```

**为什么前端镜像不在运行期装 Node**：多阶段构建让"构建依赖"只存在于第一阶段，
最终镜像只有 Nginx + 静态文件（约 50MB），体积小、启动快、攻击面小。

**为什么 api 不发布端口**：只有 Nginx 对外，后端端口在宿主机上根本不存在，
减少暴露面；同时浏览器只访问一个源，天然没有跨域问题。

排障与端口/数据替换见 [`deploy/DOCKER.md`](../deploy/DOCKER.md)。
