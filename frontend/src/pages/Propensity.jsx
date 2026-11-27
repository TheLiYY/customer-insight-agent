import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import Chart from '../components/Chart'
import { Card, ErrorBox, Kpi, Loading, Table } from '../components/ui'
import { PALETTE, axisStyle, money, num, pct } from '../lib/format'

export default function Propensity() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.propensity().then(setData).catch(setError)
  }, [])

  if (error) return <ErrorBox error={error} />
  if (!data) return <Loading text="正在训练响应预测模型…" />

  // 数据里没有「是否响应」标签时，这一页在导航里就不出现；走到这里兜底什么都不渲染
  if (data.available === false) return null

  const m = data.metrics
  const cf = m.confusion
  const best = data.lift[0]
  const positive = data.coefs.filter((c) => c.coef > 0).slice(0, 6)

  const columns = [
    { key: 'customer_id', title: '客户' },
    { key: 'cluster_name', title: '所属画像' },
    { key: 'rfm_segment', title: 'RFM 分层' },
    { key: 'prob', title: '响应概率', align: 'right', render: (r) => pct(r.prob) },
    { key: 'total_spend', title: '累计消费', align: 'right', render: (r) => money(r.total_spend) },
    { key: 'purchase_freq', title: '下单次数', align: 'right', render: (r) => num(r.purchase_freq) },
    { key: 'recency', title: '最近购买', align: 'right', render: (r) => `${num(r.recency)} 天前` },
  ]

  return (
    <>
      <div className="kpi-row">
        <Kpi label="AUC（验证集）" value={num(m.auc, 3)} hint="0.5 等于瞎猜，>0.8 说明区分能力好" tone="accent" />
        <Kpi label="准确率" value={pct(m.accuracy)} hint={`${cf.tp + cf.fp + cf.fn + cf.tn} 人验证集`} />
        <Kpi label="精确率" value={pct(m.precision)} hint={`预测会买的人里有 ${cf.tp} 个真买了`} tone="teal" />
        <Kpi label="召回率" value={pct(m.recall)} hint={`真会买的人里抓到了 ${cf.tp}/${cf.tp + cf.fn}`} tone="teal" />
        <Kpi label="F1" value={num(m.f1, 3)} hint="精确率与召回率的调和平均" />
        <Kpi label="判定阈值" value={num(data.threshold, 2)} hint="按 F1 网格搜索得到" tone="amber" />
      </div>

      <div className="grid grid-2">
        <Card
          title="提升度曲线：该联系多少人"
          
 >
          <Chart
            height={300}
            option={{
              grid: { left: 52, right: 56, top: 34, bottom: 32 },
              tooltip: { trigger: 'axis' },
              legend: { top: 0, icon: 'circle', itemWidth: 8, itemHeight: 8 },
              xAxis: { type: 'category', data: data.lift.map((d) => d.group), ...axisStyle },
              yAxis: [
                { type: 'value', name: '响应率', axisLabel: { formatter: (v) => `${(v * 100).toFixed(0)}%` }, ...axisStyle },
                { type: 'value', name: '提升倍数', ...axisStyle, splitLine: { show: false } },
              ],
              series: [
                {
                  name: '真实响应率',
                  type: 'bar',
                  barWidth: '52%',
                  data: data.lift.map((d) => Number((d.response_rate * 100).toFixed(2))),
                  itemStyle: { color: PALETTE[0], borderRadius: [5, 5, 0, 0] },
                },
                {
                  name: 'Lift 倍数',
                  type: 'line',
                  yAxisIndex: 1,
                  smooth: true,
                  symbolSize: 7,
                  data: data.lift.map((d) => Number(d.lift.toFixed(2))),
                  itemStyle: { color: PALETTE[2] },
                  lineStyle: { width: 2.5 },
                },
              ],
            }}
 />
        </Card>

        <Card title="什么因素驱动客户响应" >
          <Chart
            height={300}
            option={{
              grid: { left: 110, right: 40, top: 12, bottom: 24 },
              tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
              xAxis: { type: 'value', ...axisStyle },
              yAxis: {
                type: 'category',
                data: data.coefs.slice(0, 9).map((c) => c.feature).reverse(),
                ...axisStyle,
              },
              series: [
                {
                  type: 'bar',
                  barWidth: '52%',
                  data: data.coefs
                    .slice(0, 9)
                    .map((c) => ({
                      value: Number(c.coef.toFixed(3)),
                      itemStyle: { color: c.coef >= 0 ? PALETTE[1] : PALETTE[4], borderRadius: 4 },
                    }))
                    .reverse(),
                  label: { show: true, position: 'right', fontSize: 11, color: '#6b7280' },
                },
              ],
            }}
 />
        </Card>
      </div>

      <Card
        title="验证集混淆矩阵"
        
 >
        <div className="stat-grid">
          <div className="stat">
            <span>真正例 TP</span>
            <strong>{cf.tp}</strong>
          </div>
          <div className="stat">
            <span>假正例 FP</span>
            <strong>{cf.fp}</strong>
          </div>
          <div className="stat">
            <span>假负例 FN</span>
            <strong>{cf.fn}</strong>
          </div>
          <div className="stat">
            <span>真负例 TN</span>
            <strong>{cf.tn}</strong>
          </div>
        </div>
        <p className="muted small" style={{ marginTop: 12, marginBottom: 0 }}>
          招募成本 × 误触达 = 白花钱；漏掉真客户 = 少赚一笔。业务上可以根据单次触达成本，在上面的曲线里挑选「联系前 N%」的人数，
          而不是盲目全量群发。
        </p>
      </Card>

      <Card title="最可能响应的 Top 50 客户" >
        <Table columns={columns} rows={data.top_customers} rowKey="customer_id" />
      </Card>

      <Card title="正向驱动因素小结" >
        <ul className="bullets">
          {positive.map((c) => (
            <li key={c.key}>
              <strong>{c.feature}</strong>：系数 {num(c.coef, 3)}，{c.feature.includes('次数') || c.feature.includes('数') ? '数值越高' : '表现越好'}，响应概率越大。
            </li>
          ))}
        </ul>
      </Card>
    </>
  )
}
