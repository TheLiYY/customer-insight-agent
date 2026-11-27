import { useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'
import Chart from '../components/Chart'
import { Card, ErrorBox, Kpi, Loading, Tag } from '../components/ui'
import { PALETTE, axisStyle, money, num, pct } from '../lib/format'

export default function Personas() {
  const [data, setData] = useState(null)
  const [elbow, setElbow] = useState(null)
  const [error, setError] = useState(null)
  const [active, setActive] = useState(0)

  useEffect(() => {
    api.personas().then(setData).catch(setError)
    api.elbow(7).then(setElbow).catch(() => {})
  }, [])

  const persona = useMemo(() => (data ? data.personas[active] : null), [data, active])

  if (error) return <ErrorBox error={error} />
  if (!data) return <Loading text="正在对客户做聚类与画像生成…" />

  const p = persona
  const demo = p.demographics
  const value = p.value

  return (
    <>
      <div className="kpi-row">
        <Kpi label="画像群体" value={data.k} suffix="群" hint="K-Means 聚类" />
        <Kpi label="轮廓系数" value={num(data.silhouette, 3)} hint="越接近 1 分群越清晰" tone="accent" />
        <Kpi label="组内平方和" value={num(data.inertia, 0)} hint="用来判断 K 是否合适" />
        <Kpi label="参与客户" value={num(data.personas.reduce((s, x) => s + x.size, 0))} suffix="人" />
        <Kpi label="当前群体规模" value={num(p.size)} suffix="人" hint={`占比 ${pct(p.ratio)}`} tone="teal" />
        <Kpi label="营收贡献" value={pct(p.revenue_ratio)} hint={`${money(p.revenue)}`} tone="amber" />
      </div>

      <div className="grid grid-side">
        <Card title="客户分群" >
          <div className="seg-list">
            {data.personas.map((item, i) => (
              <button
                key={item.cluster}
                type="button"
                className={`seg-item ${i === active ? 'active' : ''}`}
                onClick={() => setActive(i)}
 >
                <div className="seg-name">
                  <span>{item.name}</span>
                  <span className={item.status === '活跃' ? 'dot-live' : 'dot-warn'}>{item.status}</span>
                </div>
                <div className="seg-sub">
                  {num(item.size)} 人 · 占比 {pct(item.ratio)} · 人均 {money(item.avg_spend)}
                </div>
              </button>
            ))}
          </div>
        </Card>

        <div>
          <Card
            title={`${p.name} · 画像详情`}
            
            extra={<Tag color="#3b6cf6">{`营收占比 ${pct(p.revenue_ratio)}`}</Tag>}
 >
            <div className="persona-head">
              <div>
                <div className="headline">{p.summary.split('，')[0]}…</div>
              </div>
            </div>
            <div style={{ margin: '4px 0 12px' }}>
              {p.tags.map((t) => (
                <Tag key={t}>{t}</Tag>
              ))}
            </div>
            <p className="persona-summary">{p.summary}</p>

            <div className="stat-grid" style={{ marginTop: 14 }}>
              <div className="stat">
                <span>平均年龄</span>
                <strong>{num(demo.avg_age, 1)} 岁</strong>
              </div>
              <div className="stat">
                <span>平均年收入</span>
                <strong>{money(value.avg_income)}</strong>
              </div>
              <div className="stat">
                <span>人均累计消费</span>
                <strong>{money(value.avg_spend)}</strong>
              </div>
              <div className="stat">
                <span>平均下单次数</span>
                <strong>{num(value.avg_freq, 1)} 次</strong>
              </div>
              <div className="stat">
                <span>平均客单价</span>
                <strong>{money(value.avg_order_value, 1)}</strong>
              </div>
              <div className="stat">
                <span>最近购买距今</span>
                <strong>{num(value.avg_recency, 0)} 天</strong>
              </div>
              {p.behavior.response_rate != null && (
                <div className="stat">
                  <span>活动响应率</span>
                  <strong>{pct(p.behavior.response_rate)}</strong>
                </div>
              )}
              <div className="stat">
                <span>折扣依赖度</span>
                <strong>{pct(p.behavior.discount_dependence)}</strong>
              </div>
            </div>
          </Card>

          <div className="grid grid-2">
            <Card title="品类偏好" >
              <Chart
                height={250}
                option={{
                  grid: { left: 70, right: 50, top: 12, bottom: 24 },
                  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: (v) => money(v) },
                  xAxis: { type: 'value', ...axisStyle },
                  yAxis: { type: 'category', data: p.categories.map((c) => c.name).reverse(), ...axisStyle },
                  series: [
                    {
                      type: 'bar',
                      barWidth: '55%',
                      data: p.categories
                        .map((c) => ({ value: c.value, itemStyle: { color: PALETTE[1], borderRadius: [0, 6, 6, 0] } }))
                        .reverse(),
                      label: { show: true, position: 'right', formatter: (d) => `¥${Math.round(d.value)}`, color: '#6b7280', fontSize: 11 },
                    },
                  ],
                }}
 />
            </Card>

            <Card title="渠道结构" >
              <Chart
                height={250}
                option={{
                  grid: { left: 44, right: 20, top: 20, bottom: 30 },
                  tooltip: { trigger: 'axis', valueFormatter: (v) => `${(v * 100).toFixed(1)}%` },
                  xAxis: { type: 'category', data: p.channels.map((c) => c.name), ...axisStyle },
                  yAxis: { type: 'value', axisLabel: { formatter: '{value}%' }, ...axisStyle },
                  series: [
                    {
                      type: 'bar',
                      barWidth: '44%',
                      data: p.channels.map((c, i) => ({
                        value: Number((c.value * 100).toFixed(1)),
                        itemStyle: { color: PALETTE[i % PALETTE.length], borderRadius: [6, 6, 0, 0] },
                      })),
                      label: { show: true, position: 'top', formatter: '{c}%', color: '#6b7280', fontSize: 11 },
                    },
                  ],
                }}
 />
            </Card>
          </div>

          <Card title="人群构成明细" >
            <div className="grid grid-3">
              {[
                ['年龄段', demo.age_group],
                ['学历', demo.education],
                ['婚姻状况', demo.marital],
              ].map(([title, rows]) => (
                <div key={title}>
                  <p className="muted small" style={{ marginTop: 0 }}>{title}</p>
                  {rows.slice(0, 4).map((r) => (
                    <div key={r.name} style={{ display: 'flex', justifyContent: 'space-between', padding: '5px 0', borderBottom: '1px solid #f2f5fa' }}>
                      <span>{r.name}</span>
                      <span className="muted small">{num(r.value)} 人 · {pct(r.ratio)}</span>
                    </div>
                  ))}
                </div>
              ))}
            </div>
            <p className="muted small" style={{ marginBottom: 0, marginTop: 12 }}>
              有孩家庭占比 {pct(demo.children_rate)}，平均入会时长 {num(value.avg_tenure_days)} 天，每月网站访问 {num(p.behavior.web_visits_month, 1)} 次。
            </p>
          </Card>
        </div>
      </div>

      {elbow && (
        <Card title="K 值选择：肘部法则 + 轮廓系数" >
          <Chart
            height={280}
            option={{
              grid: { left: 56, right: 56, top: 30, bottom: 34 },
              tooltip: { trigger: 'axis' },
              legend: { top: 0, icon: 'circle', itemWidth: 8, itemHeight: 8 },
              xAxis: { type: 'category', data: elbow.points.map((d) => `K=${d.k}`), ...axisStyle },
              yAxis: [
                { type: 'value', name: '组内误差', ...axisStyle },
                { type: 'value', name: '轮廓系数', min: 0, max: 0.5, ...axisStyle, splitLine: { show: false } },
              ],
              series: [
                {
                  name: '组内误差 Inertia',
                  type: 'line',
                  smooth: true,
                  data: elbow.points.map((d) => Number(d.inertia.toFixed(0))),
                  itemStyle: { color: PALETTE[0] },
                  areaStyle: { opacity: 0.1, color: PALETTE[0] },
                },
                {
                  name: '轮廓系数',
                  type: 'line',
                  yAxisIndex: 1,
                  smooth: true,
                  data: elbow.points.map((d) => Number(d.silhouette.toFixed(3))),
                  itemStyle: { color: PALETTE[2] },
                  lineStyle: { type: 'dashed' },
                },
              ],
            }}
 />
        </Card>
      )}
    </>
  )
}
