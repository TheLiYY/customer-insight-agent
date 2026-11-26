import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import Chart from '../components/Chart'
import { Card, ErrorBox, Kpi, Loading, Table, Tag } from '../components/ui'
import { PALETTE, axisStyle, money, num, pct } from '../lib/format'

export default function Campaign({ onNavigate }) {
  const [options, setOptions] = useState(null)
  const [by, setBy] = useState('cluster')
  const [segment, setSegment] = useState('')
  const [budget, setBudget] = useState(2000)
  const [cost, setCost] = useState(8)
  const [discount, setDiscount] = useState(0.1)
  const [plan, setPlan] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    api
      .campaignOptions()
      .then((data) => {
        setOptions(data)
        setSegment(data.clusters[0]?.name || '')
      })
      .catch(setError)
  }, [])

  const list = by === 'cluster' ? options?.clusters || [] : (options?.rfm || []).filter((r) => r.size > 0)

  const changeBy = (next) => {
    setBy(next)
    const target = next === 'cluster' ? options?.clusters : options?.rfm
    setSegment(target?.[0]?.name || '')
    setPlan(null)
  }

  const run = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.plan({
        segment,
        by,
        budget: Number(budget),
        cost_per_contact: Number(cost),
        discount: Number(discount),
      })
      setPlan(res)
    } catch (err) {
      setError(err)
    } finally {
      setLoading(false)
    }
  }

  if (!options) return error ? <ErrorBox error={error} /> : <Loading text="正在加载人群列表…" />

  return (
    <>
      <div className="grid grid-side">
        <Card title="方案参数" >
          <div className="field">
            <label>分层方式</label>
            <div className="radio-row">
              <button type="button" className={by === 'cluster' ? 'active' : ''} onClick={() => changeBy('cluster')}>
                算法画像群
              </button>
              <button type="button" className={by === 'rfm' ? 'active' : ''} onClick={() => changeBy('rfm')}>
                RFM 分层
              </button>
            </div>
          </div>

          <div className="field">
            <label>目标人群</label>
            <select value={segment} onChange={(e) => setSegment(e.target.value)}>
              {list.map((item) => (
                <option key={item.name} value={item.name}>
                  {item.name}（{item.size} 人）
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <label>活动预算（元）</label>
            <input type="number" min={1000} step={1000} value={budget} onChange={(e) => setBudget(e.target.value)} />
          </div>

          <div className="field">
            <label>单次触达成本（元/人）</label>
            <input type="number" min={0.5} step={0.5} value={cost} onChange={(e) => setCost(e.target.value)} />
          </div>

          <div className="field">
            <label>折扣力度</label>
            <select value={discount} onChange={(e) => setDiscount(Number(e.target.value))}>
              <option value={0.05}>5% 小额优惠</option>
              <option value={0.1}>10% 常规优惠</option>
              <option value={0.12}>12% 中等力度</option>
              <option value={0.2}>20% 强力促销</option>
            </select>
          </div>

          <button type="button" className="btn primary" style={{ width: '100%' }} onClick={run} disabled={loading || !segment}>
            {loading ? '正在生成…' : '生成营销方案'}
          </button>
          <p className="muted small" style={{ marginTop: 12, marginBottom: 0 }}>
            预算 ÷ 触达成本 = 最多可联系的人数；系统按预测响应概率从高到低圈人，圈不满就全量覆盖。
          </p>
        </Card>

        <div>
          {error && <ErrorBox error={error} />}
          {!plan && (
            <Card title="等待生成" >
              <p className="muted" style={{ lineHeight: 2 }}>
                一个可执行的营销方案至少要说清楚五件事：<strong>推给谁</strong>（人群）、<strong>推什么</strong>（选品）、
                <strong>从哪推</strong>（渠道）、<strong>什么时候推</strong>（时机）、<strong>说什么</strong>（话术），
                最后还要能算清楚 <strong>花多少、回多少</strong>（ROI）。
              </p>
              <p className="muted" style={{ lineHeight: 2, marginBottom: 0 }}>
                本页把这五件事 + ROI 全部自动生成，参数一改结果就跟着变，方便现场演示「预算 2 万 vs 5 万」的差别。
              </p>
            </Card>
          )}

          {plan && (
            <>
              <div className="kpi-row" style={{ gridTemplateColumns: 'repeat(3, minmax(0, 1fr))' }}>
                <Kpi label="触达人数" value={num(plan.selected)} suffix="人" hint={`覆盖人群 ${pct(plan.coverage)}`} />
                <Kpi label="预期响应率" value={pct(plan.expected_conv_rate)} tone="teal" hint={`约 ${num(plan.expected_responses)} 人下单`} />
                <Kpi label="预期 GMV" value={money(plan.expected_revenue)} tone="accent" hint={`客单价 ${money(plan.avg_order_value, 1)}`} />
                <Kpi label="预算消耗" value={money(plan.cost)} hint={`总预算 ${money(plan.budget)}`} />
                <Kpi label="ROI" value={num(plan.roi, 2)} suffix="倍" tone="amber" hint="预期 GMV ÷ 活动成本" />
                <Kpi label="优先级" value={plan.priority} tone="rose" hint={plan.goal} />
              </div>

              <Card title="执行卡" >
                <div className="stat-grid">
                  <div className="stat">
                    <span>营销目标</span>
                    <strong style={{ fontSize: 15 }}>{plan.goal}</strong>
                  </div>
                  <div className="stat">
                    <span>最优渠道</span>
                    <strong style={{ fontSize: 15 }}>{plan.channel}</strong>
                  </div>
                  <div className="stat">
                    <span>推荐时机</span>
                    <strong style={{ fontSize: 15 }}>{plan.timing}</strong>
                  </div>
                  <div className="stat">
                    <span>优惠策略</span>
                    <strong style={{ fontSize: 15 }}>{plan.offer}</strong>
                  </div>
                </div>

                <div style={{ marginTop: 16 }}>
                  <p className="muted small" style={{ marginBottom: 6 }}>推荐选品</p>
                  {plan.products.map((p) => (
                    <Tag key={p.name} color="#3b6cf6">
                      {p.name} · 人均 {money(p.avg_spend)}
                    </Tag>
                  ))}
                  {plan.upsell.map((u) => (
                    <Tag key={`${u.from}-${u.to}`} color="#12b8a6">
                      连带：买{u.from} → 也可能买{u.to}
                    </Tag>
                  ))}
                </div>

                <div style={{ marginTop: 14, background: '#f8faff', border: '1px dashed #c9d6f5', borderRadius: 12, padding: '14px 16px' }}>
                  <p className="muted small" style={{ margin: '0 0 6px' }}>触达话术</p>
                  <p style={{ margin: 0, lineHeight: 1.9 }}>{plan.copy}</p>
                </div>
              </Card>

              <div className="grid grid-2">
                {plan.products.length ? (
                  <Card title="选品结构" >
                    <Chart
                      height={240}
                      option={{
                        tooltip: { trigger: 'item', formatter: '{b}<br/>人均 {c} 元（{d}%）' },
                        legend: { bottom: 0, icon: 'circle', itemWidth: 8, itemHeight: 8, textStyle: { fontSize: 12 } },
                        series: [
                          {
                            type: 'pie',
                            radius: ['40%', '66%'],
                            center: ['50%', '43%'],
                            label: { formatter: '{b} {d}%', fontSize: 11, color: '#6b7280' },
                            data: plan.products.map((p, i) => ({
                              name: p.name,
                              value: Number(Number(p.avg_spend).toFixed(1)),
                              itemStyle: { color: PALETTE[i % PALETTE.length] },
                            })),
                          },
                        ],
                      }}
 />
                  </Card>
                ) : null}

                {plan.channel_mix.length ? (
                  <Card title="渠道配比" >
                    <Chart
                      height={240}
                      option={{
                        grid: { left: 44, right: 20, top: 20, bottom: 30 },
                        tooltip: { trigger: 'axis', valueFormatter: (v) => `${Number(v).toFixed(1)}%` },
                        xAxis: { type: 'category', data: plan.channel_mix.map((c) => c.name), ...axisStyle },
                        yAxis: { type: 'value', axisLabel: { formatter: '{value}%' }, ...axisStyle },
                        series: [
                          {
                            type: 'bar',
                            barWidth: '44%',
                            data: plan.channel_mix.map((c, i) => ({
                              value: Number((c.ratio * 100).toFixed(1)),
                              itemStyle: { color: PALETTE[i % PALETTE.length], borderRadius: [6, 6, 0, 0] },
                            })),
                            label: { show: true, position: 'top', formatter: '{c}%', color: '#6b7280', fontSize: 11 },
                          },
                        ],
                      }}
 />
                  </Card>
                ) : null}
              </div>

              <Card title="圈定名单（前 10 位）"  extra={
                <button type="button" className="btn" onClick={() => onNavigate('agent')}>
                  去 Agent 里继续问
                </button>
              }>
                <Table
                  rowKey="customer_id"
                  columns={[
                    { key: 'customer_id', title: '客户' },
                    { key: 'prob', title: '响应概率', align: 'right', render: (r) => pct(r.prob) },
                    { key: 'total_spend', title: '累计消费', align: 'right', render: (r) => money(r.total_spend) },
                    { key: 'purchase_freq', title: '下单次数', align: 'right', render: (r) => num(r.purchase_freq) },
                    { key: 'recency', title: '最近购买', align: 'right', render: (r) => `${num(r.recency)} 天前` },
                  ]}
                  rows={plan.audience_preview}
 />
              </Card>
            </>
          )}
        </div>
      </div>
    </>
  )
}

