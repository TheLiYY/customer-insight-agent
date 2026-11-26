import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import Chart from '../components/Chart'
import { Card, ErrorBox, Kpi, Loading } from '../components/ui'
import { PALETTE, axisStyle, money, num, pct } from '../lib/format'

const grid = { left: 44, right: 20, top: 24, bottom: 34 }

export default function Overview() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.overview().then(setData).catch(setError)
  }, [])

  if (error) return <ErrorBox error={error} />
  if (!data) return <Loading />

  const k = data.kpis

  return (
    <>
      <div className="kpi-row">
        <Kpi label="客户总数" value={num(k.customers)} suffix="人" hint="清洗后有效客户" />
        <Kpi label="活动响应率" value={pct(k.response_rate)} tone="accent" hint={`${k.response_count} 人参与上次活动`} />
        <Kpi label="平均家庭收入" value={money(k.avg_income)} tone="teal" hint="年收入" />
        <Kpi label="近两年人均消费" value={money(k.avg_spend)} tone="teal" hint={`累计营收 ${money(k.total_revenue)}`} />
        <Kpi label="平均下单次数" value={num(k.avg_freq, 1)} suffix="次" hint="线上+目录+门店" />
        <Kpi label="沉睡客户占比" value={pct(k.dormant_rate)} tone="rose" hint={`${k.dormant_count} 人超 75 天未购`} />
      </div>

      <div className="grid grid-2">
        <Card title="年龄结构" subtitle="客户主要集中在 41-60 岁，属于成熟家庭消费群体">
          <Chart
            height={260}
            option={{
              grid,
              tooltip: { trigger: 'axis' },
              xAxis: { type: 'category', data: data.age.map((d) => d.name), ...axisStyle },
              yAxis: { type: 'value', ...axisStyle },
              series: [
                {
                  type: 'bar',
                  barWidth: '46%',
                  data: data.age.map((d) => d.value),
                  itemStyle: { color: PALETTE[0], borderRadius: [6, 6, 0, 0] },
                  label: { show: true, position: 'top', color: '#6b7280', fontSize: 11 },
                },
              ],
            }}
          />
        </Card>

        <Card title="学历分布" subtitle="已婚 + 本科学历是主力人群">
          <Chart
            height={260}
            option={{
              tooltip: { trigger: 'item', formatter: '{b}<br/>{c} 人（{d}%）' },
              legend: { bottom: 0, icon: 'circle', itemWidth: 8, itemHeight: 8, textStyle: { fontSize: 12 } },
              series: [
                {
                  type: 'pie',
                  radius: ['44%', '68%'],
                  center: ['50%', '44%'],
                  itemStyle: { borderColor: '#fff', borderWidth: 2 },
                  label: { formatter: '{b}\n{d}%', fontSize: 11, color: '#6b7280' },
                  data: data.education.map((d, i) => ({ name: d.name, value: d.value, itemStyle: { color: PALETTE[i % PALETTE.length] } })),
                },
              ],
            }}
          />
        </Card>
      </div>

      <div className="grid grid-2">
        <Card title="品类消费结构" subtitle="葡萄酒贡献了超过一半的销售额，是绝对的核心品类">
          <Chart
            height={260}
            option={{
              grid: { left: 70, right: 40, top: 16, bottom: 24 },
              tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
              xAxis: { type: 'value', ...axisStyle },
              yAxis: { type: 'category', data: data.category.map((d) => d.name).reverse(), ...axisStyle },
              series: [
                {
                  type: 'bar',
                  barWidth: '54%',
                  data: data.category
                    .map((d) => ({ value: d.value, itemStyle: { color: PALETTE[0], borderRadius: [0, 6, 6, 0] } }))
                    .reverse(),
                  label: {
                    show: true,
                    position: 'right',
                    formatter: (p) => money(p.value),
                    color: '#6b7280',
                    fontSize: 11,
                  },
                },
              ],
            }}
          />
        </Card>

        <Card title="购买渠道构成" subtitle="线下门店仍是主要成交场景，线上商城可进一步挖掘">
          <Chart
            height={260}
            option={{
              tooltip: { trigger: 'item', formatter: '{b}<br/>{c} 单（{d}%）' },
              legend: { bottom: 0, icon: 'circle', itemWidth: 8, itemHeight: 8, textStyle: { fontSize: 12 } },
              series: [
                {
                  type: 'pie',
                  radius: '62%',
                  center: ['50%', '44%'],
                  label: { formatter: '{b} {d}%', fontSize: 11, color: '#6b7280' },
                  data: data.channel.map((d, i) => ({ name: d.name, value: d.value, itemStyle: { color: PALETTE[i % PALETTE.length] } })),
                },
              ],
            }}
          />
        </Card>
      </div>

      <div className="grid grid-2">
        <Card title="各年龄段活动响应率" subtitle="年轻客户对营销活动的响应明显更高，但人群基数小">
          <Chart
            height={250}
            option={{
              grid,
              tooltip: { trigger: 'axis', valueFormatter: (v) => `${(v * 100).toFixed(1)}%` },
              xAxis: { type: 'category', data: data.response_by_age.map((d) => d.name), ...axisStyle },
              yAxis: { type: 'value', axisLabel: { formatter: '{value}%' }, ...axisStyle },
              series: [
                {
                  type: 'line',
                  smooth: true,
                  symbolSize: 8,
                  data: data.response_by_age.map((d) => Number((d.value * 100).toFixed(2))),
                  itemStyle: { color: PALETTE[3] },
                  areaStyle: { opacity: 0.12, color: PALETTE[3] },
                  lineStyle: { width: 2.5 },
                },
              ],
            }}
          />
        </Card>

        <Card title="近两年消费额分布" subtitle="长尾客户占比高，头部客户贡献主要营收">
          <Chart
            height={270}
            option={{
              grid: { left: 48, right: 20, top: 24, bottom: 62 },
              tooltip: { trigger: 'axis' },
              xAxis: {
                type: 'category',
                data: data.spend_hist.map((d) => d.name),
                ...axisStyle,
                axisLabel: { ...axisStyle.axisLabel, interval: 0, rotate: 32, fontSize: 10, margin: 10 },
              },
              yAxis: { type: 'value', ...axisStyle },
              series: [
                {
                  type: 'bar',
                  barWidth: '68%',
                  data: data.spend_hist.map((d) => d.value),
                  itemStyle: { color: PALETTE[1], borderRadius: [5, 5, 0, 0] },
                },
              ],
            }}
          />
        </Card>
      </div>

      <Card title="核心指标相关性" subtitle="收入与消费额高度正相关；近一次购买距今越久（Recency 大），消费越少">
        <Chart
          height={430}
          option={{
            tooltip: {
              position: 'top',
              formatter: (p) => `${data.correlation.x[p.data[0]]} × ${data.correlation.y[p.data[1]]}<br/>相关系数 ${p.data[2].toFixed(2)}`,
            },
            grid: { left: 96, right: 30, top: 20, bottom: 84 },
            xAxis: { type: 'category', data: data.correlation.x, splitArea: { show: true }, ...axisStyle, axisLabel: { ...axisStyle.axisLabel, rotate: 30 } },
            yAxis: { type: 'category', data: data.correlation.y, splitArea: { show: true }, ...axisStyle },
            visualMap: {
              min: -1,
              max: 1,
              calculable: true,
              orient: 'horizontal',
              left: 'center',
              bottom: 6,
              inRange: { color: ['#ef5b7b', '#f8fafc', '#3b6cf6'] },
              textStyle: { fontSize: 11 },
            },
            series: [
              {
                type: 'heatmap',
                data: data.correlation.values.flatMap((row, i) =>
                  row.map((v, j) => [j, i, Number(v.toFixed(3))]),
                ),
                label: { show: true, fontSize: 10, color: '#334155', formatter: (p) => p.data[2].toFixed(2) },
                emphasis: { itemStyle: { shadowBlur: 8, shadowColor: 'rgba(0,0,0,0.2)' } },
              },
            ],
          }}
        />
        <p style={{ margin: '10px 4px 0', fontSize: 12, lineHeight: 1.7, color: '#6b7280' }}>
          读图方法：每一格是「行指标」和「列指标」的相关系数，取值 -1 到 +1。
          <b> 蓝色越深越接近 +1</b>（两个指标同涨同跌，比如收入与消费额 0.80 表示强正相关）；
          <b> 红色越深越接近 -1</b>（一个涨另一个跌，比如月访问次数与消费额）；
          接近白色（±0.1 以内）说明两者几乎没有线性关系。对角线恒为 1（自己和自己的相关）。
          完整术语解释见仓库 docs/GLOSSARY.md。
        </p>
      </Card>
    </>
  )
}
