# 客户洞察 Agent ｜ Customer Insight Agent

> 一条链路解决四件事：**看懂客户**（画像）→ **算准谁买**（响应预测）→ **说清怎么卖**（营销方案）→ **能对话问数据**（Agent）。

基于公开的 **iFood 营销活动客户数据**，把「客户画像 · 精准推送 · 个性化营销策略」做成一个可以真跑起来、能被追问、能被讲清楚的全栈项目：

- **后端**：Python + FastAPI，RFM 分层、K-Means 聚类、逻辑回归响应预测、Apriori 关联规则、营销方案生成，全部**手写实现**（不依赖 scikit-learn），每个算法都能一行一行讲明白。
- **前端**：React 18 + Vite + ECharts，7 个页面，看板、画像、建模、方案、对话一站式。
- **Agent**：支持在线大模型 Function Calling，**没有 API Key 也能用**（离线规则引擎兜底），保证任何机器上都能演示。

---

## 1. 它解决什么业务问题

| 业务问题 | 项目里的答案 | 对应页面 / 接口 |
| --- | --- | --- |
| 我的客户都是什么人？ | 26 个字段的客户宽表 + 分布看板 + 相关系数热力图 | `总览` / `GET /api/overview` |
| 哪些客户值钱、哪些要流失？ | 8 类 RFM 分层（R/F/M 各 1–5 分）+ 分层矩阵 + 各层策略 | `客户分层` / `GET /api/segments` |
| 客户能分成几种人？ | K-Means 聚类成 4 类客群，自动命名 + 画像标签 + 偏好品类/渠道 | `客户画像` / `GET /api/personas` |
| 下次活动谁会响应？ | 逻辑回归输出 0–1 响应概率，附 AUC/精确率/召回率/十分位 Lift | `响应预测` / `GET /api/propensity` |
| 预算 3 万该怎么花？ | 圈人（概率排序）+ 选品（偏好+关联）+ 渠道 + 时机 + 文案 + ROI | `营销方案` / `POST /api/campaign/plan` |
| 能不能直接问？ | 自然语言对话，自动调用分析工具并渲染图表/表格 | `智能助理` / `POST /api/agent/chat` |

**当前数据下的核心结论（可复现）**

- 930 位清洗后客户，历史营收集中度高：**前 4 类聚类客群中最大的「核心高价值客群」占 32.8%**，贡献营收占比明显高于人数占比。
- 最近一次营销活动的**基线响应率仅 13.55%**，但响应模型把客户按概率排序后，**前 10% 人群响应率 66.7%，Lift ≈ 4.9** —— 同样的预算投前 10% 的人群，效率接近翻 5 倍。
- 模型 AUC **≈ 0.89**，在阈值 0.58 下精确率 0.48 / 召回率 0.80 / F1 0.60。
- 品类关联最强的是 **水果 → 甜食**（支持度 72.5%、置信度 89.3%、提升度 1.09），可作为组合加购的推荐依据。

---

## 2. 技术栈

| 层 | 选型 | 说明 |
| --- | --- | --- |
| 后端框架 | FastAPI + Uvicorn | 自动生成 `/docs` 交互式 API 文档 |
| 数据处理 | pandas + numpy | 宽表清洗、分位打分、矩阵运算 |
| 算法 | 手写 K-Means / 逻辑回归 / Apriori / RFM | 不依赖 scikit-learn，便于讲解与二次改造 |
| Agent | OpenAI 兼容协议 Function Calling + 规则引擎兜底 | 无 Key 也能跑 |
| 前端 | React 18 + Vite 5 + ECharts 5 | 单页应用，构建后由后端直接托管 |
| 报表 | XlsxWriter | 导出带原生图表的 Excel 分析报告 |

---

## 3. 目录结构

```
customer-insight-agent/
├── backend/
│   ├── app/
│   │   ├── main.py                # FastAPI 入口，挂载 /api 与前端构建产物 /app
│   │   ├── api/routes.py          # 数据分析 REST 接口
│   │   ├── agent/                 # Agent：工具注册、编排、对话接口
│   │   │   ├── tools.py           # 7 个分析工具 + 4 种渲染块
│   │   │   ├── orchestrator.py    # 在线 LLM 编排 + 离线规则引擎
│   │   │   └── routes.py          # /api/agent/chat
│   │   └── core/                  # 分析内核
│   │       ├── rfm.py             # RFM 八分层
│   │       ├── clustering.py      # K-Means + 轮廓系数 + 自动命名
│   │       ├── persona.py         # 客群画像与标签
│   │       ├── propensity.py      # 逻辑回归响应预测 + Lift
│   │       ├── association.py     # Apriori 关联规则
│   │       ├── campaign.py        # 营销方案生成（圈人/选品/渠道/ROI）
│   │       ├── overview.py        # 总览指标与分布
│   │       ├── store.py           # 数据仓库单例（懒计算 + 缓存）
│   │       ├── dataset.py         # 读取清洗后数据与字段字典
│   │       ├── config.py          # 路径、字段映射、环境变量
│   │       └── utils.py           # 数值清洗、百分比等工具
│   ├── data/
│   │   ├── raw/                   # 原始数据 + 原始数据 Excel（含字段字典）
│   │   └── processed/             # 清洗后客户宽表、字段元数据、分析报告 Excel
│   ├── tests/smoke_test.py        # 18 个接口/对话用例冒烟测试
│   ├── requirements.txt
│   └── run.py                     # python backend/run.py 一键启动
├── frontend/
│   ├── src/pages/                 # 总览/分层/画像/预测/方案/对话/数据说明
│   ├── src/components/            # ECharts 封装、通用 UI
│   ├── src/lib/                   # API 封装、格式化与配色
│   ├── dist/                      # 已构建产物（后端直接托管，克隆即可用）
│   └── vite.config.js             # base=/app/，dev 代理 /api
├── scripts/
│   ├── prepare_data.py            # 下载 → 清洗 → 生成 Excel/CSV/字段元数据
│   └── export_report.py           # 生成《客户洞察分析报告》Excel（含图表）
├── docs/
│   ├── PROJECT_GUIDE.md           # 项目讲解稿（架构、算法、演示、答辩问答）
│   └── API.md                     # 接口字段说明
├── environment.yml                # Conda 环境
└── .github/workflows/ci.yml       # GitHub Actions：多版本 Python + 前端构建
```

---

## 4. 快速开始

### 方式 A：Conda（推荐，与开发环境一致）

```bash
# 1. 建环境
conda env create -f environment.yml
conda activate customer-insight

# 2. 准备数据（会尝试在线下载完整数据；失败则使用仓库内置样例）
python scripts/prepare_data.py

# 3. 启动（后端同时托管前端页面）
python backend/run.py
```

### 方式 B：已有 Python 环境

```bash
python -m pip install -r backend/requirements.txt
python scripts/prepare_data.py
python backend/run.py
```

### 打开

| 地址 | 内容 |
| --- | --- |
| http://127.0.0.1:8000/app/ | 前端界面 |
| http://127.0.0.1:8000/docs | Swagger 交互式 API 文档 |
| http://127.0.0.1:8000/api/health | 健康检查（含数据规模、模型状态） |

### 前端开发模式（改页面时用）

```bash
cd frontend
npm install          # 或 pnpm install
npm run dev          # http://127.0.0.1:5173 ，/api 自动代理到 8000
npm run build        # 重新生成 dist，后端随即生效
```

> 只需演示、不改前端时，**不需要装 Node**：`dist/` 已经构建好并被后端托管。

---

## 5. 数据说明

### 5.1 来源

- 数据集：**Customer Personality Analysis**（iFood 营销活动客户数据，Kaggle 公开数据集）
- 使用镜像：`https://raw.githubusercontent.com/nailson/ifood-data-business-analyst-test/master/ifood_df.csv`
- 该镜像已是**特征工程版**宽表：2205 行 × 39 列（收入、家庭成员、六品类消费、三类渠道购买次数、历史活动响应、婚姻/教育 one-hot 等）

### 5.2 仓库内置样例

为保证**离线、无网络也能一键跑通**，仓库内置了 `backend/data/raw/ifood_df_sample.csv`（1001 行真实样本）：

| 场景 | 行为 |
| --- | --- |
| 能联网 | `prepare_data.py` 下载完整 2205 行 → 清洗得到约 2200 位客户 |
| 不能联网 / 下载失败 | 自动回退到内置样例 → 清洗得到 **930 位客户** |

当前仓库内 `data/processed` 与文档中的数字，均基于 **930 位客户**的样例跑出，可稳定复现。

### 5.3 清洗规则（`scripts/prepare_data.py`）

| 处理 | 规则 |
| --- | --- |
| 主键 | 生成 `customer_id`（C00001…），便于对话里点名查询 |
| 年龄 | `Age` 截断到 18–90，并按 18–30 / 31–40 / 41–50 / 51–60 / 60+ 分箱 |
| 收入 | 上截断到 99 分位，避免极端值拉偏聚类 |
| 婚姻 / 教育 | 从 one-hot 反解为单列分类 |
| 消费 | 六个 `Mnt*` 品类 → 统一 `mnt_*` 命名，`total_spend` 为总消费 |
| 频次 | `purchase_freq` = 线上 + 目录 + 门店购买次数 |
| 标签 | `response` 为最近一次营销活动是否响应（0/1），即预测目标 |

产物：

| 文件 | 内容 |
| --- | --- |
| `backend/data/raw/ifood_df.csv` | 原始宽表副本 |
| `backend/data/raw/Customer_Personality_Analysis.xlsx` | 原始数据 Excel（客户明细 / 字段字典 / 数据来源） |
| `backend/data/processed/customers.csv` | 清洗后客户宽表（930 × 26） |
| `backend/data/processed/dataset_meta.json` | 字段中英文名、类型、业务含义 |
| `backend/data/processed/Customer_Insight_Report.xlsx` | 分析报告（9 个 sheet + 4 张原生图表） |

> 上面两个 Excel 使用固定文档时间戳生成：同一份数据重复运行，产物字节完全一致，所以放进 git 也不会出现无意义的二进制改动。

---

## 6. 算法说明（都给得出公式）

### 6.1 RFM 分层

- 对 R（最近购买间隔，越小越好）、F（购买频次）、M（消费金额）分别做**五分位打分**（1–5 分）
- R/F/M 各 ≥3 记为「高」，组合成 8 类客群：重要价值 / 重要保持 / 重要发展 / 重要挽留 / 一般价值 / 一般保持 / 一般发展 / 一般挽留
- 输出：每层人数、营收贡献、平均 R/F/M、响应率、对应运营策略

### 6.2 K-Means 客群聚类

- 特征：收入、总消费、购买频次、最近购买间隔、折扣购买数、月访问次数、年龄（标准化后）
- 手写实现：**k-means++ 初始化 + 10 次随机重启**取最优，用**轮廓系数**评估 k=2..6
- 客群按 `0.5·z(消费) + 0.3·z(频次) − 0.2·z(间隔)` 排名自动命名（核心高价值 → 边缘低频）
- 当前结果：k=4，轮廓系数 ≈ 0.22

### 6.3 响应概率预测（逻辑回归）

- 13 个特征：收入、年龄、消费、频次、最近间隔、折扣依赖、月访问、孩童年数、历史活动接受数、品类偏好占比等
- **类别加权**解决 13.5% 正样本不平衡；L2 正则 + 批量梯度下降
- 70/30 划分评估后在**验证集做阈值网格搜索**（0.05–0.80，最大化 F1），再用最优阈值报告测试集指标
- 输出：AUC、准确率、精确率、召回率、F1、混淆矩阵、特征系数（可解释谁在推高响应）、**十分位 Lift 表**

### 6.4 关联规则（Apriori）

- 把每位客户购买过的品类当作一个「购物篮」，挖掘 1~2 元频繁项集
- 指标：支持度 support、置信度 confidence、提升度 lift，用于「买了 A 的人更可能买 B」

### 6.5 营销方案生成

输入：目标客群 + 预算 + 单客成本 + 折扣力度，输出一套可直接执行的动作：

1. **圈人**：按响应概率排序取 Top N，N = 预算 ÷ 单客成本（覆盖客群比例可解释）
2. **选品**：该客群消费最高的品类 Top3 + 关联规则给出的加购组合
3. **渠道**：按该客群在各渠道的购买量占比选主渠道（线上商城 / 邮购目录 / 门店）
4. **时机**：按平均最近购买间隔分「3 天内 / 7 天内 / 14 天内」三档
5. **ROI**：`预计营收 = 圈选人数 × 响应率 × 客单价`，`ROI = 预计营收 ÷ 触达成本`

---

## 7. Agent 是怎么工作的

```
用户提问 ──► 意图路由 ──► 调用分析工具 ──► 结构化 JSON ──► 渲染成 文本/KPI/图表/表格
             │
             ├─ 在线模式：把 7 个工具注册成 function calling，交给大模型决定调用哪个、传什么参数
             └─ 离线模式：关键词 + 正则（预算、客户ID、客群名）解析意图，走同一套工具
```

7 个工具：`overview_report`（整体概览）、`segment_report`（RFM 分层）、`persona_report`（客群画像）、`propensity_report`（响应预测）、`campaign_plan`（营销方案）、`category_report`（品类与关联）、`customer_profile`（单个客户画像）。

**在线模式配置**（不配则自动使用离线模式）：

```bash
# PowerShell
$env:LLM_BASE_URL="https://api.deepseek.com/v1"
$env:LLM_API_KEY="sk-xxxx"
$env:LLM_MODEL="deepseek-chat"
python backend/run.py
```

```bash
# Bash
export LLM_BASE_URL="https://api.deepseek.com/v1"
export LLM_API_KEY="sk-xxxx"
export LLM_MODEL="deepseek-chat"
python backend/run.py
```

启动日志与 `GET /api/health` 中的 `llm_enabled` 会告诉你当前是否为在线模式。

---

## 8. 主要接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 健康检查、数据规模、在线/离线模式 |
| GET | `/api/dataset` | 数据来源、行列数、26 个字段字典 |
| GET | `/api/overview` | KPI、年龄/学历/婚姻/收入分布、品类与渠道、响应率、相关系数矩阵 |
| GET | `/api/segments` | RFM 8 分层明细、F×M 矩阵、营收矩形树图 |
| GET | `/api/personas` | 聚类结果、轮廓系数、4 个客群画像与标签 |
| GET | `/api/clusters/elbow?k_max=6` | 不同 k 的肘部曲线与轮廓系数 |
| GET | `/api/propensity` | 模型指标、特征系数、Lift 表、高潜客户 Top 名单 |
| GET | `/api/association` | 品类关联规则、渗透率与客单价 |
| GET | `/api/customers` | 客户明细分页（支持筛选、排序） |
| GET | `/api/customers/{id}` | 单个客户详情 |
| GET | `/api/campaign/options` | 可选客群列表（聚类 / RFM） |
| POST | `/api/campaign/plan` | 生成营销方案 |
| POST | `/api/agent/chat` | 对话分析（返回结构化渲染块） |
| GET | `/api/agent/suggestions` | 推荐问题 |

字段级说明见 [`docs/API.md`](docs/API.md)。

---

## 9. 测试与报表

```bash
# 18 个接口/对话用例，不启动服务器（TestClient）
python backend/tests/smoke_test.py

# 导出《客户洞察分析报告》Excel
python scripts/export_report.py
```

冒烟测试覆盖：11 个 GET 接口 + 7 条自然语言对话（意图是否命中正确工具）。

---

## 10. 常见问题

**Q：为什么不用 scikit-learn？**
A：项目要求能讲清每个算法的内部过程。K-Means、逻辑回归、Apriori 都用 numpy/pandas 手写（合计约 400 行），既减少依赖，也让「为什么这个客户被预测为高潜力」可以逐项拆开。生产环境可直接替换为 sklearn / LightGBM。

**Q：为什么客群聚类只有 4 类？**
A：k 由轮廓系数与肘部法共同决定，k=4 时轮廓系数最高（当前数据 ≈0.22）。数据本身区分度有限（消费品类高度相关），所以轮廓系数不高属于正常现象，这一点在文档里如实说明。

**Q：数据量只有 930 行，结论可信吗？**
A：这是公开的营销活动数据，用于**展示方法论与工程实现**。上升到生产需要：更大规模数据、时间窗滚动验证、A/B 实验校验 ROI。

**Q：Agent 没有大模型 Key 能用吗？**
A：能。离线规则引擎覆盖 7 类意图，演示效果与在线模式一致，只是不能回答开放式问题。

---

## 11. 已知限制与后续计划

- 关联规则只做到 2 元项集，可扩展到 3 元 + FP-Growth 提速
- 响应模型是线性模型，可对比 GBDT / 特征交叉；当前 AUC ≈0.89，提升空间在特征工程
- 尚未接入真实触达通道（短信/企微/邮件），可在 `campaign.py` 增加发送适配器
- 缺少 A/B 实验与 ROI 回流闭环，这是从「分析工具」走向「营销系统」的关键一步
- 前端为单页应用，生产部署建议 Nginx 反代 + gunicorn 多 worker

---

## 12. 上传到 GitHub

仓库已经初始化好（分支 `main`，4 个提交，60 个受版本控制的文件），你只需要建远程仓库并推送：

```bash
# 1. 在 GitHub 上新建一个空仓库（不要勾选 README / .gitignore）
#    例如 https://github.com/<你的用户名>/customer-insight-agent

# 2. 关联远程并推送（在本项目根目录执行）
git remote add origin https://github.com/<你的用户名>/customer-insight-agent.git
git branch -M main
git push -u origin main
```

首次推送会要求登录。推荐用 **Personal Access Token**（GitHub → Settings → Developer settings → Personal access tokens），把它当密码粘贴即可；或先执行 `gh auth login` 用 GitHub CLI 登录。

> 用 SSH 的话：`git remote add origin git@github.com:<用户名>/customer-insight-agent.git`，需要本地已配置 SSH Key。

**提交历史（已生成）**

| 提交 | 内容 |
| --- | --- |
| `chore: 初始化项目骨架与数据流水线` | 目录结构、数据清洗脚本、原始/清洗后数据与 Excel |
| `feat(backend): …分析内核与 API` | RFM / 聚类 / 画像 / 预测 / 关联 / 方案 + 13 个接口 + Agent + 测试 |
| `feat(frontend): …七页看板与对话界面` | React 页面、ECharts 封装、构建产物 |
| `docs: README、讲解稿、API 文档与 CI` | 文档与 GitHub Actions |

推送完成后，建议在仓库里打开 **Actions** 标签页确认 CI 跑通（Python 3.11/3.12/3.13 冒烟测试 + 前端构建）。

---

## 13. 许可

MIT License，数据集版权归原始发布方（Kaggle: Customer Personality Analysis）所有，仅用于学习与研究。
