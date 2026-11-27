import { useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'
import { Card, ErrorBox, Kpi, Loading, Table, Tag } from '../components/ui'

const SEVERITY = {
  opportunity: { label: '增长机会', color: '#0f9d58' },
  risk: { label: '风险预警', color: '#e5484d' },
  insight: { label: '结构洞察', color: '#3b6cf6' },
}

const FILTERS = [
  { key: 'all', label: '全部结论' },
  { key: 'opportunity', label: '增长机会' },
  { key: 'risk', label: '风险预警' },
  { key: 'insight', label: '结构洞察' },
]

/**
 * 自动结论页：
 * 后端把「总览 / RFM / 聚类 / 响应预测 / 关联规则」全部跑完之后，
 * 用规则把数字翻译成「发现了什么 → 证据是什么 → 该做什么」，
 * 这里只是一层展示，不需要前端再做任何推导。
 */
export default function Insights({ onNavigate }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [filter, setFilter] = useState('all')

  useEffect(() => {
    api.insights().then(setData).catch(setError)
  }, [])

  const insights = useMemo(() => {
    if (!data) return []
    return filter === 'all' ? data.insights : data.insights.filter((i) => i.severity === filter)
  }, [data, filter])

  if (error) return <ErrorBox error={error} />
  if (!data) return <Loading text="正在跑分析并生成结论…" />

  const c = data.counts
  // 数据里没有的指标后端会返回 null，这里直接不显示，避免出现 0.0% / 0.000 这种误导
  const stats = [
    ['客户数', data.stats.customers],
    ['大盘响应率', data.stats.response_rate != null ? `${(data.stats.response_rate * 100).toFixed(1)}%` : null],
    ['前 20% 客户营收占比', data.stats.top20_revenue_share != null ? `${(data.stats.top20_revenue_share * 100).toFixed(1)}%` : null],
    ['响应模型 AUC', data.stats.auc != null ? data.stats.auc.toFixed(3) : null],
    ['头部名单提升度', data.stats.top_decile_lift != null ? `${data.stats.top_decile_lift.toFixed(2)}×` : null],
  ].filter(([, v]) => v != null)

  return (
    <>
      <div className="kpi-row">
        <Kpi label="自动生成结论" value={c.total} suffix="条" hint="全部来自真实数据计算" tone="accent" />
        {c.opportunity > 0 && (
          <Kpi label="增长机会" value={c.opportunity} suffix="条" hint="可以直接投预算的地方" tone="teal" />
        )}
        {c.risk > 0 && <Kpi label="风险预警" value={c.risk} suffix="条" hint="不处理会掉营收" tone="rose" />}
        {c.insight > 0 && <Kpi label="结构洞察" value={c.insight} suffix="条" hint="解释「为什么是这样」" />}
      </div>

      <Card title="一句话结论">
        <p style={{ fontSize: 15, lineHeight: 1.9, margin: 0 }}>{data.headline}</p>
        <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap', marginTop: 14, fontSize: 12, color: '#6b7280' }}>
          {stats.map(([label, value]) => (
            <span key={label}>
              {label} {value}
            </span>
          ))}
        </div>
      </Card>

      <div className="tabs" style={{ marginBottom: 12 }}>
        {FILTERS.filter((f) => f.key === 'all' || (c[f.key] || 0) > 0).map((f) => (
          <button
            key={f.key}
            type="button"
            className={`tab ${filter === f.key ? 'active' : ''}`}
            onClick={() => setFilter(f.key)}
 >
            {f.label}
          </button>
        ))}
      </div>

      {insights.map((item) => (
        <Card key={item.id}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
            <Tag color={SEVERITY[item.severity].color}>{item.severity_label}</Tag>
            <strong style={{ fontSize: 15 }}>{item.title}</strong>
            <span style={{ marginLeft: 'auto', fontSize: 12, color: '#9ca3af' }}>{item.category}</span>
          </div>
          <p style={{ margin: '0 0 10px', lineHeight: 1.85, fontSize: 14 }}>{item.conclusion}</p>
          <ul style={{ margin: '0 0 10px', paddingLeft: 18, fontSize: 13, color: '#4b5563', lineHeight: 1.9 }}>
            {item.evidence.map((ev, i) => (
              <li key={i}>{ev}</li>
            ))}
          </ul>
          <p style={{ margin: 0, fontSize: 13, lineHeight: 1.8, padding: '10px 12px', background: '#f6f8fc', borderRadius: 8 }}>
            <b>建议动作：</b>
            {item.action}
          </p>
        </Card>
      ))}

      <Card title="行动清单" >
        <Table
          columns={[
            { key: 'priority', title: '优先级', width: 80, align: 'center' },
            { key: 'action', title: '要做的事' },
            { key: 'from', title: '来自哪条结论', width: 200 },
          ]}
          rows={data.actions}
 />
        {onNavigate && (
          <button type="button" className="link-btn" style={{ marginTop: 12 }} onClick={() => onNavigate('campaign')}>
            去生成对应客群的营销方案 →
          </button>
        )}
      </Card>
    </>
  )
}
