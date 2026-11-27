import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import Chart from '../components/Chart'
import { Card, ErrorBox, Kpi, Loading, Table, Tag } from '../components/ui'
import { PALETTE, axisStyle, money, num, pct } from '../lib/format'

export default function Segments() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.segments().then(setData).catch(setError)
  }, [])

  if (error) return <ErrorBox error={error} />
  if (!data) return <Loading text="正在计算 RFM 分层…" />

  const segs = data.segments
  const important = segs.filter((s) => s.name.startsWith('重要'))
  const importantCount = important.reduce((s, x) => s + x.count, 0)
  const importantRevenue = important.reduce((s, x) => s + x.revenue, 0)
  const totalRevenue = segs.reduce((s, x) => s + x.revenue, 0)
  const biggest = [...segs].sort((a, b) => b.count - a.count)[0]
  const topRevenue = [...segs].sort((a, b) => b.revenue - a.revenue)[0]

  const columns = [
    {
      key: 'name',
      title: '客户分层',
      render: (r) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Tag color={`hsl(${(r.priority - 1) * 32}, 70%, 46%)`}>P{r.priority}</Tag>
          <strong>{r.name}</strong>
        </div>
      ),
    },
    { key: 'count', title: '人数', align: 'right', render: (r) => num(r.count) },
    { key: 'ratio', title: '人数占比', align: 'right', render: (r) => pct(r.ratio) },
    { key: 'revenue_ratio', title: '营收占比', align: 'right', render: (r) => pct(r.revenue_ratio) },
    { key: 'avg_spend', title: '人均消费', align: 'right', render: (r) => money(r.avg_spend) },
    { key: 'avg_freq', title: '人均次数', align: 'right', render: (r) => num(r.avg_freq, 1) },
    { key: 'avg_recency', title: '最近购买', align: 'right', render: (r) => `${num(r.avg_recency, 0)} 天前` },
    { key: 'response_rate', title: '响应率', align: 'right', render: (r) => pct(r.response_rate) },
    { key: 'score', title: 'R / F / M', align: 'center', render: (r) => `${num(r.avg_r, 1)} / ${num(r.avg_f, 1)} / ${num(r.avg_m, 1)}` },
  ]

  return (
    <>
      <div className="kpi-row">
        <Kpi label="分层数量" value={segs.length} suffix="层" hint="R × F × M 交叉" />
        <Kpi label="重要客户" value={num(importantCount)} suffix="人" hint={pct(importantCount / segs.reduce((s, x) => s + x.count, 0))} tone="accent" />
        <Kpi label="重要客户营收" value={pct(importantRevenue / totalRevenue)} tone="teal" hint={money(importantRevenue)} />
        <Kpi label="主力分层" value={topRevenue.name} hint={`${num(topRevenue.count)} 人 · 贡献 ${pct(topRevenue.revenue_ratio)} 营收`} tone="amber" />
        <Kpi label="模型口径" value="5 分位" hint="R / F / M 各自等频打分 1-5" />
      </div>

      <Card title="RFM 分层结果" >
        <Table columns={columns} rows={segs} rowKey="name" />
      </Card>

      <div className="grid grid-2">
        <Card title="客户结构（面积 = 人数）" >
          <Chart
            height={300}
            option={{
              tooltip: {
                formatter: (p) => `${p.name}<br/>人数 ${num(p.value)}<br/>营收 ${money(p.data.revenue)}`,
              },
              series: [
                {
                  type: 'treemap',
                  roam: false,
                  nodeClick: false,
                  breadcrumb: { show: false },
                  itemStyle: { borderColor: '#fff', borderWidth: 3, gapWidth: 3 },
                  label: { show: true, formatter: '{b}\n{c} 人', fontSize: 12, color: '#fff' },
                  color: PALETTE,
                  data: data.treemap,
                },
              ],
            }}
 />
        </Card>

        <Card title="F（频次）× M（金额）分布" >
          <Chart
            height={300}
            option={{
              tooltip: { position: 'top', formatter: (p) => `${p.data[1]} × ${p.data[0]}<br/>${num(p.data[2])} 人` },
              grid: { left: 44, right: 30, top: 20, bottom: 50 },
              // 有格子里的数字就够了，图例隐藏但保留配色
              visualMap: {
                show: false,
                min: 0,
                max: Math.max(...data.matrix.values.flat()),
                inRange: { color: ['#eef2ff', '#c7d5ff', '#7d9cf7', '#3b6cf6', '#1e3fa8'] },
              },
              xAxis: { type: 'category', data: data.matrix.rows, name: 'F', ...axisStyle },
              yAxis: { type: 'category', data: data.matrix.cols, name: 'M', ...axisStyle },
              series: [
                {
                  type: 'heatmap',
                  data: data.matrix.values.flatMap((row, i) => row.map((v, j) => [i, j, v])),
                  label: { show: true, fontSize: 11, color: '#1f2430' },
                },
              ],
            }}
 />
        </Card>
      </div>

      <Card title="每一层该怎么打" >
        <div className="table-wrap" style={{ maxHeight: 'none' }}>
          <table>
            <thead>
              <tr>
                <th style={{ width: 160 }}>分层</th>
                <th style={{ width: 340 }}>人群特征</th>
                <th>运营动作</th>
              </tr>
            </thead>
            <tbody>
              {segs.map((s) => (
                <tr key={s.name}>
                  <td>
                    <Tag color={`hsl(${(s.priority - 1) * 32}, 70%, 46%)`}>P{s.priority}</Tag>
                    <strong>{s.name}</strong>
                  </td>
                  <td className="muted">{s.desc}</td>
                  <td>{s.action}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  )
}
