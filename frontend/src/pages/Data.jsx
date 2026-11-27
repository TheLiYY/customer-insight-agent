import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { Card, ErrorBox, Kpi, Loading, Table, Tag } from '../components/ui'
import { num } from '../lib/format'

const CAP_LABELS = [
  ['has_income', '收入字段'],
  ['has_monetary', '消费金额'],
  ['has_recency', '最近购买时间'],
  ['has_frequency', '购买频次'],
  ['has_response', '活动响应标签'],
]

export default function Data() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.dataset().then(setData).catch(setError)
  }, [])

  if (error) return <ErrorBox error={error} />
  if (!data) return <Loading text="正在读取数据字典…" />

  const caps = data.capabilities || {}
  const contract = data.contract || {}
  const mapping = contract.mapping || {}
  // mapping.rows 是数组（每项含 target/label/source/confidence/how）；兼容旧的对象形态
  const mappingRows = (Array.isArray(mapping.rows) ? mapping.rows : Object.entries(mapping.rows || {}).map(([key, info]) => ({ target: key, ...info }))).map((info, i) => ({
    key: info.target || String(i),
    field: info.target,
    label: info.label || info.target,
    source: info.source,
    confidence: info.confidence || '—',
    how: info.how || '',
  }))
  // 后端返回的品类/渠道可能是 [{key, name}] 数组，也可能是 { key: 中文名 } 对象
  const toPairs = (items) =>
    Array.isArray(items)
      ? items.map((it) => ({ key: it.key, key2: it.key, label: it.name || it.label }))
      : Object.entries(items || {}).map(([key, label]) => ({ key, key2: key, label }))
  const catRows = toPairs(data.categories)
  const chRows = toPairs(data.channels)

  return (
    <>
      <div className="kpi-row" style={{ gridTemplateColumns: 'repeat(4, minmax(0, 1fr))' }}>
        <Kpi label="客户样本" value={num(data.rows)} suffix="行" hint={`原始 ${num(data.raw_rows)} 行`} />
        <Kpi label="特征字段" value={num(data.columns)} suffix="列" hint="规范化之后的字段" />
        <Kpi label="重复行" value={num(data.duplicate_rows)} hint="已按整行去重" tone="teal" />
        <Kpi label="数据粒度" value={contract.grain_label || '客户级宽表'} hint="决定后续怎么聚合" tone="accent" />
      </div>

      <Card title="当前使用的数据" >
        <p style={{ marginTop: 0, lineHeight: 1.9 }}>{data.desc}</p>
        <ul className="bullets">
          <li>
            数据来源：
            <a className="link" href={data.source_page || '#'} target="_blank" rel="noreferrer">
              {data.source_page || data.source}
            </a>
          </li>
          <li>
            原始体量：{num(data.raw_rows)} 行 × {num(data.raw_columns)} 列；清洗后 {num(data.rows)} 行 × {num(data.columns)} 列。
          </li>
          <li>
            可读 Excel：<span className="code-inline">{data.excel}</span>（原始数据 / 客户明细 / 字段字典 / 数据来源四个工作表）
          </li>
        </ul>
      </Card>

      <Card title="能力开关" >
        <div className="tag-row">
          {CAP_LABELS.map(([key, label]) => (
            <Tag key={key} color={caps[key] ? '#0f9d58' : '#8c8f9a'}>
              {label} {caps[key] ? '✓' : '✗'}
            </Tag>
          ))}
          {Object.entries(caps.categories || {}).length ? <Tag color="#3b6cf6">{Object.keys(caps.categories).length} 个品类</Tag> : null}
          {Object.entries(caps.channels || {}).length ? <Tag color="#3b6cf6">{Object.keys(caps.channels).length} 个渠道</Tag> : null}
        </div>
        <p className="muted small" style={{ marginBottom: 0 }}>
          其中「活动响应标签」决定响应预测页是否可用；没有品类列时关联规则与选品模块会自动隐藏。
        </p>
      </Card>

      <Card
        title="字段自动映射"
        
 >
        <Table
          rowKey="key"
          columns={[
            { key: 'field', title: '标准字段', render: (r) => <span className="code-inline">{r.field}</span> },
            { key: 'source', title: '来自源表列' },
            { key: 'confidence', title: '置信度', width: 90 },
            { key: 'how', title: '处理方式' },
          ]}
          rows={mappingRows}
 />
      </Card>

      {catRows.length || chRows.length ? (
        <div className="grid grid-2">
          <Card title="识别到的品类" >
            <Table
              rowKey="key"
              columns={[
                { key: 'key2', title: '内部字段', render: (r) => <span className="code-inline">{r.key2}</span> },
                { key: 'label', title: '品类名' },
              ]}
              rows={catRows}
 />
          </Card>
          <Card title="识别到的渠道" >
            <Table
              rowKey="key"
              columns={[
                { key: 'key2', title: '内部字段', render: (r) => <span className="code-inline">{r.key2}</span> },
                { key: 'label', title: '渠道名' },
              ]}
              rows={chRows}
 />
          </Card>
        </div>
      ) : null}

      <Card title="字段字典" >
        <Table
          rowKey="name"
          columns={[
            { key: 'name', title: '字段名', render: (r) => <span className="code-inline">{r.name}</span> },
            { key: 'label', title: '中文名' },
            { key: 'type', title: '类型', width: 90 },
            { key: 'desc', title: '说明' },
          ]}
          rows={data.fields}
 />
      </Card>

      <Card title="数据处理流程" >
        <ol className="bullets" style={{ paddingLeft: 20 }}>
          <li><strong>读取</strong>：支持内置数据集、任意 CSV/Excel 文件，也支持直接指向你公司导出的客户表。</li>
          <li><strong>识别</strong>：按别名表自动判断哪列是客户编号、金额、频次、最近购买时间（见上表）。</li>
          <li><strong>清洗</strong>：整行去重；收入做 99 分位截断，避免极端值把聚类带偏；年龄裁剪到 18-90 岁。</li>
          <li><strong>兼容</strong>：订单明细（一单一行）会自动按客户聚合；缺失的金额/频次用可得字段兜底，并在下方 warnings 里说明。</li>
          <li><strong>落盘</strong>：输出 Excel（给业务看）、processed/customers.csv（给程序读）、mapping.json（匹配明细）和 dataset_meta.json（元信息）。</li>
        </ol>
      </Card>

      {contract.mapping && contract.mapping.unused_columns && contract.mapping.unused_columns.length ? (
        <Card title="没有用上的列" >
          <p className="code-inline" style={{ lineHeight: 2 }}>{contract.mapping.unused_columns.join('、')}</p>
        </Card>
      ) : null}

      {data.warnings && data.warnings.length ? (
        <Card title="本次预处理给出的提醒" >
          <ul className="bullets">
            {data.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </Card>
      ) : null}

      <Card title="口径说明与局限" >
        <ul className="bullets">
          <li>
            <strong>样本量</strong>：当前 {num(data.rows)} 条客户记录，足够跑通全流程和演示模型；正式业务请换成自己的全量客户表。
          </li>
          <li>
            <strong>标签定义</strong>：响应预测的正样本是「接受了最近一次促销活动」，属于典型的不均衡二分类。
          </li>
          <li>
            <strong>ROI 是估算值</strong>：客单价用该人群历史人均消费代替，「预期响应率」是模型概率的均值，实际投放后应回填真实转化校准。
          </li>
          <li>
            <strong>隐私</strong>：公开数据集已脱敏；换成公司数据时，客户编号等身份信息建议先做哈希或替换。
          </li>
          <li>
            <strong>图表怎么看</strong>：每张图在说什么、怎么读、能得出什么结论，见仓库 <code>docs/CHART_GUIDE.md</code>。
          </li>
        </ul>
      </Card>
    </>
  )
}
