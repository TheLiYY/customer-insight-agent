import { useEffect, useState } from 'react'
import { api } from './lib/api'
import Overview from './pages/Overview'
import Insights from './pages/Insights'
import Segments from './pages/Segments'
import Personas from './pages/Personas'
import Propensity from './pages/Propensity'
import Campaign from './pages/Campaign'
import Agent from './pages/Agent'
import Import from './pages/Import'
import Data from './pages/Data'

const NAV = [
  { key: 'overview', icon: '📊', label: '数据总览', component: Overview },
  { key: 'insights', icon: '📌', label: '自动结论', component: Insights },
  { key: 'personas', icon: '👥', label: '客户画像', component: Personas },
  { key: 'segments', icon: '🧩', label: 'RFM 分层', component: Segments },
  { key: 'propensity', icon: '🎯', label: '响应预测', component: Propensity },
  { key: 'campaign', icon: '🚀', label: '营销方案', component: Campaign },
  { key: 'agent', icon: '💬', label: 'Agent 助手', component: Agent },
  { key: 'import', icon: '📥', label: '导入数据', component: Import },
  { key: 'data', icon: '🗂️', label: '数据说明', component: Data },
]

export default function App() {
  // 页面状态跟地址栏的 # 同步：刷新不丢当前页，也方便把某一页直接发给别人
  const [page, setPage] = useState(() => window.location.hash.replace(/^#\/?/, '') || 'overview')
  const [health, setHealth] = useState(null)
  const [error, setError] = useState('')
  const [refreshKey, setRefreshKey] = useState(0)

  function loadHealth() {
    api
      .health()
      .then((h) => {
        setHealth(h)
        setError('')
      })
      .catch((err) => setError(err.message))
  }

  useEffect(() => {
    loadHealth()
  }, [])

  useEffect(() => {
    const onHashChange = () => setPage(window.location.hash.replace(/^#\/?/, '') || 'overview')
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  function navigate(key) {
    setPage(key)
    if (window.location.hash !== `#/${key}`) window.location.hash = `#/${key}`
  }

  // 导入新数据后：刷新侧边栏统计，并把所有页面重新挂载一次（组件挂载时才会重新取数）
  function handleDataChanged() {
    loadHealth()
    setRefreshKey((k) => k + 1)
  }

  const current = NAV.find((n) => n.key === page) || NAV[0]
  const Page = current.component

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">CL</div>
          <div className="brand-text">
            <strong>CustLens</strong>
            <span>客户洞察 · 精准营销</span>
          </div>
        </div>
        <nav className="nav">
          {NAV.map((item) => (
            <button
              key={item.key}
              type="button"
              className={page === item.key ? 'active' : ''}
              onClick={() => navigate(item.key)}
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
          <h1>{current.label}</h1>
          {health && (
            <span className={`badge-llm ${health.llm_enabled ? '' : 'off'}`}>
              {health.llm_enabled ? 'LLM 在线模式' : '离线规则模式'}
            </span>
          )}
        </div>
        {error && <div className="error-box">无法连接后端：{error}（请先运行 python backend/run.py）</div>}
        <Page
          key={`${current.key}-${refreshKey}`}
          onNavigate={navigate}
          onDataChanged={handleDataChanged}
        />
      </main>
    </div>
  )
}
