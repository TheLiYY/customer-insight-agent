# 客户洞察 Agent ｜ Customer Insight Agent

> 一条链路解决五件事：**看懂客户**（画像）→ **算准谁买**（响应预测）→ **说清怎么卖**（营销方案）→ **自动出结论**（洞察）→ **能对话问数据**（Agent）。

基于 Kaggle 公开的 **iFood 营销活动客户数据（2205 行 × 39 列）**，把「客户画像 · 精准推送 · 个性化营销策略」做成一个能真跑、能被追问、能被讲清楚的全栈项目：

- **后端**：Python + FastAPI，RFM 分层、K-Means 聚类、逻辑回归响应预测、Apriori 关联规则、**自动结论**、营销方案生成。算法用 **scikit-learn / mlxtend** 现成实现，工程可靠、可维护。
- **前端**：React 18 + Vite + ECharts，**8 个页面**，看板、画像、建模、方案、自动结论、对话一站式。
- **架构**：**前后端完全分离**（前端可独立部署 / 反代），后端只提供纯 JSON API。
- **Agent**：支持在线大模型 Function Calling，**没有 API Key 也能用**（离线规则引擎兜底），任何机器上都能演示。

---

## 1. 它解决什么业务问题

| 业务问题 | 项目里的答案 | 对应页面 / 接口 |
| --- | --- | --- |
| 我的客户都是什么人？ | 客户宽表 + 分布看板 + 相关系数热力图 | `数据总览` / `GET /api/overview` |
| 分析跑完了，结论是什么？ | **10 条自动结论**（机会 / 风险 / 洞察）+ 证据 + 行动清单 | `自动结论` / `GET /api/insights` |
| 哪些客户值钱、哪些要流失？ | 8 类 RFM 分层（R/F/M 各 1–5 分）+ 分层矩阵 + 各层策略 | `客户分层` / `GET /api/segments` |
| 客户能分成几种人？ | K-Means 聚类成 4 类客群，自动命名 + 画像标签 + 偏好品类/渠道 | `客户画像` / `GET /api/personas` |
| 下次活动谁会响应？ | 逻辑回归输出 0–1 响应概率，附 AUC/精确率/召回率/十分位 Lift | `响应预测` / `GET /api/propensity` |
| 预算 2000 元该怎么花？ | 圈人（概率排序）+ 选品（偏好+关联）+ 渠道 + 时机 + 文案 + ROI | `营销方案` / `POST /api/campaign/plan` |
| 能不能直接问？ | 自然语言对话，自动调用分析工具并渲染图表/表格 | `智能助理` / `POST /api/agent/chat` |

**当前数据下的核心结论（可复现）**

- **2021 位**清洗后客户，历史营收 **1,054,533 元**；前 20% 客户贡献了 **53.6%** 的营收。
- 最近一次营销活动**基线响应率 15.39%**（311 人响应）；响应模型按概率排序后，**前 10% 人群响应率是平均水平的 4.51 倍**。
- 模型 **AUC 0.8827**，阈值 0.78 下：准确率 0.891 / 精确率 0.690 / 召回率 0.527 / F1 0.5976。
- 聚类 k=4（轮廓系数 0.2163）：核心高价值客群 687 人、潜力成长客群 508 人、长尾基础客群 465 人（沉默预警）、稳定贡献客群 361 人。
- 品类关联最强的是 **甜食 → 鱼类**（支持度 73.3%、置信度 90.0%、提升度 1.09）；品类渗透率普遍在 90% 以上，所以 lift 不高——**这一点在结论里如实写出，并转成"组合套餐"建议**，而不是夸大规则价值。
- 风险项：**23.7% 客户超 75 天未下单**；折扣依赖 18.5%；投诉率 1.0%。

---

## 2. 技术栈

| 层 | 选型 | 说明 |
| --- | --- | --- |
| 后端框架 | FastAPI + Uvicorn | 自动生成 OpenAPI，可导入 Apifox / Postman |
| 数据处理 | pandas + numpy | 宽表清洗、分位打分、矩阵运算 |
| 机器学习 | **scikit-learn 1.9**（KMeans / StandardScaler / silhouette_score / LogisticRegression / precision_recall_curve / roc_auc_score / confusion_matrix） | 现成实现，参数与评估都标准化 |
| 关联规则 | **mlxtend 0.25**（TransactionEncoder / apriori / association_rules） | 工程可用、文档完善 |
| Agent | OpenAI 兼容 Function Calling + 规则引擎兜底 | 无 Key 也能跑 |
| 前端 | React 18 + Vite 5 + ECharts 5 | 独立构建，`VITE_API_BASE` 指向后端 |
| 报表 | XlsxWriter | 导出带原生图表的 Excel 分析报告 |
| 文档 | OpenAPI 3.1 + Postman v2.1 | 一键导入 Apifox 做接口管理 |

---

## 3. 目录结构

```
customer-insight-agent/
├── backend/                       # 纯 API 服务（不托管前端）
│   ├── app/
│   │   ├── main.py                # FastAPI 实例、CORS、异常兜底
│   │   ├── api/routes.py          # 14 个分析 REST 接口 + /api/capabilities
│   │   ├── agent/                 # Agent：工具注册、编排、对话接口
│   │   │   ├── tools.py           # 8 个分析工具 + 4 种渲染块
│   │   │   ├── orchestrator.py    # 在线 LLM 编排 + 离线规则引擎
│   │   │   └── routes.py          # /api/agent/chat
│   │   └── core/                  # 分析内核（不依赖 FastAPI，可脱离 Web 复用）
│   │       ├── rfm.py             # RFM 八分层
│   │       ├── clustering.py      # sklearn KMeans + 轮廓系数 + 自动命名
│   │       ├── persona.py         # 客群画像与标签
│   │       ├── propensity.py      # sklearn 逻辑回归 + 阈值搜索 + Lift
│   │       ├── association.py     # mlxtend Apriori 关联规则
│   │       ├── insights.py        # ★ 自动结论引擎（指标 → 结论 + 证据 + 动作）
│   │       ├── campaign.py        # 营销方案生成（圈人/选品/渠道/ROI）
│   │       ├── overview.py        # 总览指标与分布
│   │       ├── store.py           # 结果仓库单例（懒计算 + 缓存）
│   │       ├── schema.py          # ★ 数据契约层：任意客户表 → 标准客户字段
│   │       ├── dataset.py         # 数据注册中心：读清洗结果 + 能力开关（capabilities）
│   │       ├── config.py          # 路径、字段中文映射、环境变量
│   │       └── utils.py           # 数值清洗、百分比等工具
│   ├── data/
│   │   ├── raw/                   # 原始数据 + 原始数据 Excel（含字段字典）
│   │   └── processed/             # 清洗后客户宽表、字段元数据、分析报告 Excel
│   ├── tests/smoke_test.py        # 21 个接口/对话用例冒烟测试
│   ├── tests/test_contract.py     # 52 项契约层用例（换数据后识别是否还准）
│   ├── requirements.txt
│   └── run.py                     # python backend/run.py 一键启动
├── frontend/                      # 独立前端工程
│   ├── src/pages/                 # 总览/自动结论/分层/画像/预测/方案/对话/数据说明
│   ├── src/components/            # ECharts 封装、通用 UI
│   ├── src/lib/                   # API 封装（支持 VITE_API_BASE）、格式化与配色
│   ├── dist/                      # 已构建产物（由 Nginx 托管）
│   └── vite.config.js             # dev 代理 /api → 8000
├── scripts/
│   ├── prepare_data.py            # 下载/读本地表/Excel → 自动识别字段 → 清洗 → 生成 Excel/CSV/元数据
│   ├── export_report.py           # 生成《客户洞察分析报告》Excel（含图表）
│   ├── export_openapi.py          # 导出 OpenAPI / Postman 集合（导入 Apifox）
│   ├── dev-start.ps1              # ★ 一键起后端 + Nginx（自动清旧进程、建 nginx 目录）
│   └── dev-stop.ps1               # 一键停掉后端与 Nginx
├── deploy/
│   ├── nginx.conf                 # ★ 本机 Nginx 部署配置（静态站点 + /api 反代）
│   ├── README.md                  # Nginx 部署步骤与排障表
│   ├── Dockerfile.api             # 后端镜像（Python 3.13 + 依赖 + 内置数据）
│   ├── Dockerfile.web             # 前端镜像（node 构建 → nginx 托管）
│   ├── nginx.docker.conf          # 容器内站点配置
│   ├── docker-compose.bundle.yml  # 换机器用的无 build 版 compose
│   ├── make-bundle.ps1            # 一键打离线部署包（镜像 + compose）
│   └── DOCKER.md                  # ★ Docker 部署说明（换机器零环境）
├── docker-compose.yml             # 一键启动：web(Nginx) + api(FastAPI)
├── .dockerignore
├── docs/
│   ├── PROJECT_GUIDE.md           # 项目讲解稿（架构、算法、演示、答辩问答）
│   ├── CODE_TOUR.md               # ★ 代码导读（逐文件讲清"为什么这么写"）
│   ├── GLOSSARY.md                # ★ 术语词典（热力图怎么读、AUC/Lift 是什么）
│   ├── DATA.md                    # ★ 换数据指南（别名表、映射置信度、能力降级）
│   ├── API.md                     # 接口字段说明
│   ├── openapi.json               # OpenAPI 3.1（Apifox / Swagger 可导入）
│   └── API.postman.json           # Postman v2.1 集合（Apifox 可导入）
├── environment.yml                # Conda 环境
└── .github/workflows/ci.yml       # GitHub Actions：多版本 Python + 前端构建
```

---

## 4. 快速开始

### 一键启动（Windows，推荐）

```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev-start.ps1   # 起后端 8000 + Nginx 8080
powershell -ExecutionPolicy Bypass -File scripts\dev-stop.ps1    # 全部停掉
```

脚本按顺序做这几件事：检查数据（没有就先生成）→ 清掉占用 8000 的旧进程 → 起后端并等健康检查通过 →
**清掉残留的旧 nginx 进程**（最容易踩的坑：旧配置的 nginx 还在占 8080，看起来像"改配置没生效"）→
补齐 nginx 需要的 `logs/`、`temp/` 目录 → 起 Nginx → 探活。参数：`-NoNginx`（只起后端）、`-BackendPort 8010`（换端口）。

以下是手动方式，便于理解每一步在做什么。

### 方式 A：Conda（推荐）

```bash
conda env create -f environment.yml
conda activate customer-insight
python scripts/prepare_data.py      # 拉数据 + 清洗 + 生成 Excel
python backend/run.py               # 后端 → http://127.0.0.1:8000
```

### 方式 B：已有 Python 环境（venv）

```bash
python -m venv .venv --system-site-packages
.venv\Scripts\activate              # Windows
pip install -r backend/requirements.txt
python scripts/prepare_data.py
python backend/run.py
```

### 方式 C：Docker（换机器最省事，推荐交付/演示用）

目标机器**只要装了 Docker**，不用 Python、不用 Node、不用装依赖：

```bash
docker compose up -d --build      # 首次构建几分钟，之后启动几秒
# 浏览器打开 http://localhost:8080
```

换一台电脑时甚至不需要源码和网络：先在有 Docker 的机器上打离线包，

```powershell
powershell -ExecutionPolicy Bypass -File deploy\make-bundle.ps1   # 生成 dist-bundle/（镜像 + compose + 说明）
```

把 `dist-bundle` 拷过去，然后 `docker load -i images.tar` → `docker compose up -d` 即可。

两者的分工：**本机改代码用 venv + Nginx**，**交付/换机用 Docker**。容器结构（只有 Nginx 对外暴露端口，
后端在容器内网、由 Nginx 反代 `/api`）与排障表见 **[deploy/DOCKER.md](deploy/DOCKER.md)**。

### 启动前端（Nginx 托管，前后端分离）

前端**只用 Nginx 部署**：Nginx 托管 `frontend/dist`，并把 `/api/` 反代到后端 8000，浏览器只访问一个地址。

```bash
# 1. 构建（已有 dist 可跳过；改了前端源码才需要）
cd frontend
npm install && npm run build        # 产物在 frontend/dist

# 2. 装 Nginx（Windows）
winget install --id nginxinc.nginx -e --source winget

# 3. 起 Nginx（前缀目录就是 deploy/）
cd ../deploy
New-Item -ItemType Directory -Force logs, temp | Out-Null
nginx -p "D:/projects/customer-insight-agent/deploy" -c nginx.conf -t      # 检查配置
nginx -p "D:/projects/customer-insight-agent/deploy" -c nginx.conf         # 启动
```

改配置后重载：`nginx -p <deploy 目录> -c nginx.conf -s reload`；停止：把 `-s reload` 换成 `-s stop`。
完整步骤、Linux/systemd 部署与排障表见 **[deploy/README.md](deploy/README.md)**。

> 懒得手动敲？`powershell -ExecutionPolicy Bypass -File scripts\dev-start.ps1` 会自动完成上面三步，
> 并顺手清掉残留的旧 nginx 进程。

> 开发调试才用 `cd frontend && npm run dev`（5173，热更新，Vite 自动代理 /api）；
> **部署与演示统一走 Nginx**，不需要其它静态服务器。

| 地址 | 内容 |
| --- | --- |
| http://127.0.0.1:8080 | 前端界面（Nginx 托管 dist + 反代 /api） |
| http://127.0.0.1:8080/docs | Swagger 交互式 API 文档（经 Nginx 反代） |
| http://127.0.0.1:8000/docs | 直连后端的 Swagger / ReDoc |
| http://127.0.0.1:8000/api/health | 健康检查（数据规模、模型状态、在线/离线模式） |

> **前端连哪个后端**：经 Nginx 反代后是同源，不需要 `VITE_API_BASE`；若前端要部署到
> 与后端不同的域名，构建前设 `VITE_API_BASE=https://your-api.com/api`，
> 并把该域名加进 `backend/app/core/config.py` 的 CORS 白名单。

### 用 Apifox 管理接口

```bash
python scripts/export_openapi.py     # 生成 docs/openapi.json + docs/API.postman.json
```

然后任选其一：

1. **Apifox → 项目设置 → 导入数据 → OpenAPI/Swagger**，选 `docs/openapi.json`；
2. **Apifox → 导入数据 → Postman**，选 `docs/API.postman.json`（自带分组与示例请求体）。

导入后即可在 Apifox 里做接口调试、Mock、自动化测试。

---

## 5. 数据说明

### 5.1 来源（真实公开数据）

- 数据集：**Customer Personality Analysis**（iFood 营销活动客户数据，Kaggle 公开数据集）
- 原始页：<https://www.kaggle.com/datasets/imakash3011/customer-personality-analysis>
- 仓库使用镜像（已做特征工程版本的宽表）：`https://cdn.jsdelivr.net/gh/nailson/ifood-data-business-analyst-test@master/ifood_df.csv`
- 规模：**2205 行 × 39 列**（收入、家庭成员、六品类消费、三类渠道购买次数、历史 5 次活动响应、婚姻/教育 one-hot 等）

`prepare_data.py` 内置**三个镜像**依次尝试（jsDelivr → raw.githubusercontent → gcore），全部失败才回退仓库内置的 `ifood_df_sample.csv`（1001 行真实样本），保证离线也能跑。

### 5.2 训练/测试的"Excel 数据"

项目里的数据分析与建模**全部基于 Excel 可打开的真实数据**：

| 文件 | 用途 |
| --- | --- |
| `backend/data/raw/ifood.csv` | 原始宽表（2205 × 39），Excel 可直接打开；同时是离线缓存（换数据后这里会变成 `mall.csv` / `bank.csv`） |
| `backend/data/raw/Customer_Personality_Analysis.xlsx` | **数据源 Excel**（客户明细 / 字段字典 / 数据来源），业务方可直接核对 |
| `backend/data/processed/customers.csv` | 清洗后建模用宽表（2021 × 25），Excel 可直接打开 |
| `backend/data/processed/Customer_Insight_Report.xlsx` | **分析结果 Excel**（9 个 sheet + 4 张原生图表），给不看网页的人看 |

> 两个 Excel 只是"可交付的落地形式"；模型训练与测试读的是 `customers.csv`，
> 由 `prepare_data.py` 从 2205 行原始数据清洗而来（去重 184 行 → 2021 行有效客户）。

**想完全用自己手上的 Excel 训练？** 直接把表丢进去就行，列名不用改：

```bash
python scripts/prepare_data.py --file "D:/你的数据/客户数据.xlsx"
# 指定工作表：python scripts/prepare_data.py --file 客户数据.xlsx --sheet 客户明细
```

脚本会读取 Excel、自动识别列名（中英文都行）、清洗建模，
所以「Excel 数据」和「联网下载的数据」走的是**同一条流水线**。

### 5.4 换一份数据也能跑（数据契约层）

这件事不是"表头必须和 Kaggle 一样"，而是**任意客户表都能跑**：

```bash
python scripts/prepare_data.py --dataset mall      # 商场会员：只有年龄/性别/收入/消费评分
python scripts/prepare_data.py --dataset bank      # 银行营销：有 y 响应标签、没有金额
python scripts/prepare_data.py --file 我的客户表.xlsx
```

`backend/app/core/schema.py` 是一个**数据契约层**：把任意列名翻译成项目内部的标准字段（`customer_id` / `income` / `recency` / `total_spend` / `response`…，再按实际数据补上品类、渠道列），
翻译不了的就标记为"缺失"，下游模块自动降级——没有金额就不算 ROI、没有响应标签就不做响应预测，而不是报错。

换数据后前端会自动调整：总览页隐藏算不出来的图，响应预测页显示说明卡，数据说明页展示字段映射与未使用的列。

| 内置数据集 | 有效客户 | 能算什么 |
| --- | --- | --- |
| iFood（默认） | 2021 | 全部能力 |
| Mall Customers | 200 | 画像 / 聚类（无金额、无响应） |
| Bank Marketing | 4119 | 画像 / 聚类 / 响应预测（无金额） |

细节（别名表、`mapping.json` 怎么看、订单明细自动聚合、怎么加自己的别名）：见 **[`docs/DATA.md`](docs/DATA.md)**。

### 5.3 清洗规则（`scripts/prepare_data.py`）

| 处理 | 规则 |
| --- | --- |
| 主键 | 自动识别客户编号；没有就生成 `customer_id`（C00001…），便于对话里点名查询 |
| 年龄 | `Age` 截断到 18–90，并按 18–30 / 31–40 / 41–50 / 51–60 / 60+ 分箱 |
| 收入 | 上截断到 99 分位，避免极端值拉偏聚类 |
| 婚姻 / 教育 | 从 one-hot 反解为单列分类（并映射中文：本科 / 硕士 / 博士…） |
| 消费 | 六个 `Mnt*` 品类 → 统一 `mnt_*` 命名，`total_spend` 为总消费；品类列是**自动识别**的，换数据也能认 |
| 频次 | `purchase_freq` = 线上 + 目录 + 门店购买次数；没有渠道列时用订单数或"有消费记 1 次"兜底 |
| 标签 | `response` 为最近一次营销活动是否响应（0/1），即预测目标；没有该列则响应预测自动关闭 |

> 两个 Excel 使用固定文档时间戳生成：同一份数据重复运行，产物字节完全一致，放进 git 不会出现无意义的二进制改动。

---

## 6. 算法说明

### 6.1 RFM 分层

- 对 R（最近购买间隔，越小越好）、F（购买频次）、M（消费金额）分别做**五分位打分**（1–5 分，R 方向反转）
- R/F/M 各 ≥3 记为「高」，组合成 8 类客群：重要价值 / 重要保持 / 重要发展 / 重要挽留 / 一般价值 / 一般保持 / 一般发展 / 一般挽留
- 输出：每层人数、营收贡献、平均 R/F/M、响应率、对应运营策略

### 6.2 K-Means 客群聚类（scikit-learn）

```python
scaled = StandardScaler().fit_transform(matrix)
model  = KMeans(n_clusters=4, n_init=10, random_state=42)
sil    = silhouette_score(scaled, model.labels_, sample_size=1500, random_state=42)
centers = scaler.inverse_transform(model.cluster_centers_)   # 还原成业务量纲
```

- 特征：收入、总消费、购买频次、最近购买间隔、折扣购买数、月访问次数、年龄（标准化后）
- 客群按 `0.5·z(消费) + 0.3·z(频次) − 0.2·z(间隔)` 排名自动命名（核心高价值 → 长尾基础）
- 当前结果：**k=4，轮廓系数 0.2163**，肘部曲线见 `/api/clusters/elbow`

### 6.3 响应概率预测（scikit-learn 逻辑回归）

```python
pipe = Pipeline([("scaler", StandardScaler()),
                 ("lr", LogisticRegression(class_weight="balanced", C=1.0, max_iter=2000))])
prec, rec, thr = precision_recall_curve(y_val, prob_val)
best = thr[np.argmax(2*prec*rec/(prec+rec+1e-12))]   # F1 最大处取阈值 → 0.78
```

- 13 个特征：收入、年龄、消费、频次、最近间隔、折扣依赖、月访问、孩童年数、历史活动接受数、品类偏好占比等
- `class_weight="balanced"` 解决 15.5% 正样本不平衡；`stratify` 保证训练/验证正样本比例一致
- 70/30 分层切分 → 在**验证集用 PR 曲线选阈值** → 报告测试集指标 → 再用全量数据重训出分
- 输出：AUC、准确率、精确率、召回率、F1、混淆矩阵、特征系数（可解释谁在推高响应）、**十分位 Lift 表**

### 6.4 关联规则（mlxtend Apriori）

```python
te      = TransactionEncoder()
encoded = te.fit(transactions).transform(transactions)
freq    = apriori(pd.DataFrame(encoded, columns=te.columns_), min_support=0.03, use_colnames=True, max_len=2)
rules   = association_rules(freq, metric="confidence", min_threshold=0.15)
```

- 把每位客户购买过的品类当作一个「购物篮」，挖掘 1~2 元频繁项集
- 只保留「单前件 → 单后件」规则（业务上可落地），按 lift 降序
- 指标：支持度 support、置信度 confidence、提升度 lift

### 6.5 自动结论引擎（`core/insights.py`）

分析完自动回答"所以呢？"，产出 **10 条结论**，每条都是 `标题 + 结论 + 证据链 + 建议动作`：

| 类别 | 覆盖的判断 |
| --- | --- |
| 价值结构 | 营收集中度（前 20% 占比）、Top 客群相对整体的倍数 |
| 流失风险 | 超 75 天未购客户占比 ≥ 20% 触发预警、哪些客群已沉默 |
| 投放效率 | 响应模型 Top10% 的 Lift、能覆盖多少响应客户、AUC 水平 |
| 商品结构 | 主品类营收占比、关联规则是否足够强（lift ≥ 1.05 才建议交叉销售） |
| 渠道结构 | 主成交渠道占比 |
| 人群结构 | 主力学历 / 婚姻 / 年龄 |
| 利润健康 | 折扣依赖 ≥ 18%、投诉率 > 1% 预警 |

**关键设计**：结论由**确定性规则**生成，每条都能追到具体数字；配置大模型时，它只负责"把这些结论讲得更好听"，不负责编数字。

### 6.6 营销方案生成

输入：目标客群 + 预算 + 单客成本 + 折扣力度，输出一套可直接执行的动作：

1. **圈人**：按响应概率排序取 Top N，N = 预算 ÷ 单客成本
2. **选品**：该客群消费最高的品类 Top3 + 关联规则给出的加购组合
3. **渠道**：按该客群在各渠道的购买量占比选主渠道
4. **时机**：按平均最近购买间隔分「本周三 19:00–21:00 / 一周内 / 两周内」三档
5. **ROI**：`预计营收 = 圈选人数 × 平均响应概率 × 客单价`，`ROI = 预计营收 ÷ 触达成本`

示例（核心高价值客群，预算 2000 元，单客 8 元）：圈选 250 人 → 预计响应 209 人 → 预计营收 16,388 元 → **ROI 7.19**。

---

## 7. Agent 是怎么工作的

```
用户提问 ──► 意图路由 ──► 调用分析工具 ──► 结构化 JSON ──► 渲染成 文本/KPI/图表/表格
             │
             ├─ 在线模式：把 8 个工具注册成 function calling，交给大模型决定调用哪个、传什么参数
             └─ 离线模式：关键词 + 正则（预算、客户ID、客群名）解析意图，走同一套工具
```

8 个工具：`overview_report`（整体概览）、`insights_report`（自动结论）、`segment_report`（RFM 分层）、`persona_report`（客群画像）、`propensity_report`（响应预测）、`campaign_plan`（营销方案）、`category_report`（品类与关联）、`customer_profile`（单个客户画像）。

**在线模式配置**（不配则自动使用离线模式）：

```powershell
$env:LLM_BASE_URL="https://api.deepseek.com/v1"
$env:LLM_API_KEY="sk-xxxx"
$env:LLM_MODEL="deepseek-chat"
python backend/run.py
```

启动日志与 `GET /api/health` 中的 `llm_enabled` 会告诉你当前是否为在线模式；响应里的 `mode` 字段取值为 `llm` 或 `rules`。

---

## 8. 主要接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 健康检查、数据规模、在线/离线模式 |
| GET | `/api/dataset` | 数据来源、行列数、字段字典、**字段自动映射**、未使用列、预处理提醒 |
| GET | `/api/capabilities` | **能力开关**：这份数据能算画像/聚类/响应预测/关联规则吗 |
| GET | `/api/overview` | KPI、年龄/学历/婚姻/收入分布、品类与渠道、响应率、相关系数矩阵 |
| GET | `/api/insights` | **自动结论**（可按 `severity` / `category` 过滤） |
| GET | `/api/segments` | RFM 8 分层明细、F×M 矩阵、营收矩形树图 |
| GET | `/api/personas` | 聚类结果、轮廓系数、4 个客群画像与标签 |
| GET | `/api/clusters/elbow?k_max=6` | 不同 k 的肘部曲线与轮廓系数 |
| GET | `/api/propensity` | 模型指标、特征系数、Lift 表、高潜客户 Top 名单；无响应标签时返回 `available=false` |
| GET | `/api/association` | 品类关联规则、渗透率与客单价 |
| GET | `/api/customers` | 客户明细分页（支持筛选、排序） |
| GET | `/api/customers/{id}` | 单个客户详情 |
| GET | `/api/campaign/options` | 可选客群列表（聚类 / RFM） |
| POST | `/api/campaign/plan` | 生成营销方案 |
| POST | `/api/agent/chat` | 对话分析（返回结构化渲染块） |
| GET | `/api/agent/suggestions` | 推荐问题 |

字段级说明见 [`docs/API.md`](docs/API.md)，机器可读定义见 [`docs/openapi.json`](docs/openapi.json)。

---

## 9. 测试与报表

```bash
python backend/tests/smoke_test.py     # 21 个接口/对话用例，不启动服务器
python backend/tests/test_contract.py  # 52 项契约层用例：换数据后字段识别还对不对
python scripts/export_report.py        # 导出《客户洞察分析报告》Excel
python scripts/export_openapi.py       # 导出 OpenAPI / Postman 给 Apifox
```

冒烟测试覆盖：13 个 GET 接口 + 8 条自然语言对话（意图是否命中正确工具），当前 **21/21 通过**。

契约层测试用**现场造表**的方式验证 6 类真实场景，当前 **52/52 通过**：

| 用例 | 验证什么 |
| --- | --- |
| iFood 宽表 | 数值列识别、one-hot 学历反解、`Kidhome+Teenhome` 合并、渠道相加得频次 |
| 订单明细表 | 判成 transaction 粒度、按客户聚合消费额/频次/最近间隔、品类透视 |
| 中文列名表 | 「客户编号/年龄/年收入/消费金额」全家桶能直接认出来 |
| 文本二值标签 | `y = yes/no` 能当响应标签（UCI Bank Marketing 那种） |
| 极简表 | 只有年龄+性别时不崩、能力降级、RFM 补零并给警告 |
| 自定义别名 | 加一行别名后「薪资等级」这类怪列名立刻能被认成收入 |

这两组测试都不需要网络、不需要起服务器，所以 CI 里是硬性门禁。

---

## 10. 文档地图

| 文档 | 给谁看 | 解决什么问题 |
| --- | --- | --- |
| [`docs/GLOSSARY.md`](docs/GLOSSARY.md) | 你自己 / 答辩听众 | AUC、Lift、轮廓系数、热力图、置信度……**每个术语都配本项目真实数字和"怎么讲"话术** |
| [`docs/CODE_TOUR.md`](docs/CODE_TOUR.md) | 你自己 / 面试官 | 逐个文件讲清职责、执行链路、为什么这么设计；含二次开发手册 |
| [`docs/PROJECT_GUIDE.md`](docs/PROJECT_GUIDE.md) | 汇报现场 | 30 秒 / 3 分钟 / 8 分钟三套讲稿 + 14 个高频追问 |
| [`docs/API.md`](docs/API.md) | 前后端联调 | 16 个接口的字段级说明与示例 |
| [`docs/DATA.md`](docs/DATA.md) | 想用自己的客户数据 | **换数据指南**：`--file`、字段别名表、映射置信度、能力降级、订单明细自动聚合 |
| [`deploy/DOCKER.md`](deploy/DOCKER.md) | 交付 / 换机器 | 镜像结构、一键启动、离线部署包、11 条排障表 |
| [`deploy/README.md`](deploy/README.md) | 本机运维 | Nginx 部署步骤、Linux systemd、缓存策略对照 |

---

## 11. 常见问题

**Q：为什么用 scikit-learn 而不是手写算法？**
A：手写能讲清楚原理，但生产项目更该用经过验证的实现——`StandardScaler` 防数据泄漏、`precision_recall_curve` 比手写阈值循环更准、`class_weight` 处理不平衡是标准做法。算法原理在 [`docs/GLOSSARY.md`](docs/GLOSSARY.md) 里讲透，代码交给库，**两者不冲突**。

**Q：为什么前后端分离而不是后端托管前端？**
A：分离后前端可独立部署与独立回滚，后端只提供 JSON API，也便于接 App / 小程序。部署统一走 Nginx（`deploy/nginx.conf`）：静态资源由 Nginx 直接托管，`/api/` 反代到 FastAPI，同源无 CORS；演示时也是这一套，不需要额外的静态服务器进程。

**Q：为什么客群聚类只有 4 类、轮廓系数只有 0.22？**
A：k 由轮廓系数与肘部法共同确定。消费类数据本身特征高度相关（收入、消费、频次天然正相关），轮廓系数不会很高，0.2 左右是这类数据的正常范围——**如实说明比硬凑一个好看的数字更专业**。

**Q：数据量 2021 行，结论可信吗？**
A：这是公开营销活动数据，用于**验证方法论与工程链路**。上生产需要：更大样本、时间窗滚动验证、A/B 实验校验 ROI。项目在自动结论里也标出了这些局限。

**Q：只有 Docker、没有 Python 的电脑能跑吗？**
A：能，而且这是推荐的交付方式。`docker compose up -d --build` 一条命令起 web + api，环境全在镜像里；换机器时用 `deploy/make-bundle.ps1` 打离线包（`docker load` + `up -d`），官方镜像层也一起打包，目标机不需要联网。详见 [`deploy/DOCKER.md`](deploy/DOCKER.md)。

**Q：Agent 没有大模型 Key 能用吗？**
A：能。离线规则引擎覆盖 8 类意图，演示效果一致，只是不能回答开放式问题。

---

## 12. 已知限制与后续计划

- 关联规则只做到 2 元项集，可扩展到 3 元 + FP-Growth 提速
- 响应模型是线性模型，下一步可对比 LightGBM / 特征交叉；当前 AUC 0.8827，提升空间主要在特征工程
- ROI 未计入物流、退货、毛利，属于"理想口径"，上线前需接真实成本
- 尚未接入真实触达通道（短信/企微/邮件），可在 `campaign.py` 增加发送适配器
- 缺少 A/B 实验与 ROI 回流闭环，这是从"分析工具"走向"营销系统"的关键一步

---

## 13. 上传到 GitHub

本机已安装 Git（`C:\Program Files\Git\cmd\git.exe`，v2.56.1）。仓库已初始化（分支 `main`），你只需建远程仓库并推送：

```bash
# 1. 在 GitHub 上新建空仓库（不要勾选 README / .gitignore）
#    例如 https://github.com/<你的用户名>/customer-insight-agent

# 2. 关联远程并推送（在本项目根目录执行）
git remote add origin https://github.com/<你的用户名>/customer-insight-agent.git
git branch -M main
git push -u origin main
```

首次推送会要求登录：用 **Personal Access Token**（GitHub → Settings → Developer settings → Personal access tokens）当密码粘贴，或先 `gh auth login`。

> 用 SSH：`git remote add origin git@github.com:<用户名>/customer-insight-agent.git`，需本地已配置 SSH Key。

推送后到仓库 **Actions** 标签页确认 CI 通过（Python 3.11/3.12/3.13 冒烟测试 + 前端构建）。

---

## 14. 许可

MIT License，数据集版权归原始发布方（Kaggle: Customer Personality Analysis）所有，仅用于学习与研究。
