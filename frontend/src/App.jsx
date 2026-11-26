import { useEffect, useState } from 'react'
import { api } from './lib/api'
import Overview from './pages/Overview'
import Segments from './pages/Segments'
import Personas from './pages/Personas'
import Propensity from './pages/Propensity'
import Campaign from './pages/Campaign'
import Agent from './pages/Agent'
import Data from './pages/Data'

const NAV = [
  { key: 'overview', icon: '📊', label: '数据总览', component: Overview },
  { key: 'personas', icon: '👥', label: '客户画像', component: Personas },
  { key: 'segments', icon: '🧩', label: 'RFM 分层', component: Segments },
  { key: 'propensity', icon: '🎯', label: '响应预测', component: Propensity },
  { key: 'campaign', icon: '🚀', label: '营销方案', component: Campaign },
  { key: 'agent', icon: '💬', label: 'Agent 助手', component: Agent },
  { key: 'data', icon: '🗂️', label: '数据说明', component: Data },
]

export default function App() {
  const [page, setPage] = useState('overview')
  const [health, setHealth] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch((err) => setError(err.message))
  }, [])

  const current = NAV.find((n) => n.key === page) || NAV[0]
  const Page = current.component

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">CI</div>
          <div className="brand-text">
            <strong>Customer Insight</strong>
            <span>客户洞察 · 精准营销</span>
          </div>
        </div>
        <nav className="nav">
          {NAV.map((item) => (
            <button
              key={item.key}
              type="button"
              className={page === item.key ? 'active' : ''}
              onClick={() => setPage(item.key)}
            >
              <span className="nav-icon">{item.icon}</span>
              {item.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-foot">
          {health ? (
            <>
              数据 {health.customers} 位客户
              <br />
              分群 {health.segments} 个 · v{health.version}
              <br />
              {health.llm_enabled ? '大模型：已接入' : '大模型：未接入（规则引擎）'}
            </>
          ) : (
            '正在连接后端…'
          )}
        </div>
      </aside>

      <main className="main">
        <div className="page-head">
          <div>
            <h1>{current.label}</h1>
            <p>{PAGE_DESC[current.key]}</p>
          </div>
          {health && (
            <span className={`badge-llm ${health.llm_enabled ? '' : 'off'}`}>
              {health.llm_enabled ? 'LLM 在线模式' : '离线规则模式'}
            </span>
          )}
        </div>
        {error && <div className="error-box">无法连接后端：{error}（请先运行 python backend/run.py）</div>}
        <Page onNavigate={setPage} />
      </main>
    </div>
  )
}

const PAGE_DESC = {
  overview: '先把数据看明白：客户是谁、买了什么、从哪买、对活动的反应如何。',
  personas: '用 K-Means 把客户分成若干可解释的画像群体，每一群都能直接对应一套打法。',
  segments: 'RFM 三维打分，把客户放进 8 个经典分层里，判断该投多少资源。',
  propensity: '逻辑回归预测「下一次活动谁会买」，配合提升度曲线决定该联系多少人。',
  campaign: '选人群、定预算、出选品/渠道/话术/ROI，一键生成可执行的营销方案。',
  agent: '用自然语言提问，Agent 会调用上面的分析能力并把结果画出来。',
  data: '数据来源、字段字典与预处理口径，方便复现与二次开发。',
}
