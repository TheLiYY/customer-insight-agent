import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { Card, ErrorBox, Kpi, Loading, Table } from '../components/ui'
import { num } from '../lib/format'

export default function Data() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.dataset().then(setData).catch(setError)
  }, [])

  if (error) return <ErrorBox error={error} />
  if (!data) return <Loading text="正在读取数据字典…" />

  return (
    <>
      <div className="kpi-row" style={{ gridTemplateColumns: 'repeat(4, minmax(0, 1fr))' }}>
        <Kpi label="客户样本" value={num(data.rows)} suffix="行" hint="清洗后的有效客户" />
        <Kpi label="特征字段" value={num(data.columns)} suffix="列" hint="包含 RFM 派生字段" />
        <Kpi label="缺失值" value={num(data.missing_cells)} hint="缺失会在预处理阶段剔除" tone="teal" />
        <Kpi label="重复行" value={num(data.duplicate_rows)} hint="按客户编号去重" tone="teal" />
      </div>

      <Card title="数据来源" subtitle="公开数据集 Customer Personality Analysis（iFood 营销活动数据）">
        <p style={{ marginTop: 0, lineHeight: 1.9 }}>
          数据来自 Kaggle 上的经典营销数据集 <strong>Customer Personality Analysis</strong>，原始版本有 2240 条客户记录、
          29 个字段，包含人口属性（出生年份、学历、婚姻、收入、子女数）、消费行为（六个品类的消费额、各渠道下单次数、
          折扣购买次数、网站访问次数）和五次历史促销活动的接受情况。它常被用来做客户分群和营销响应预测，正好对应本项目的三个目标。
        </p>
        <ul className="bullets">
          <li>
            原始下载地址：
            <a className="link" href={data.source} target="_blank" rel="noreferrer">
              {data.source}
            </a>
          </li>
          <li>
            预处理后的 Excel 文件：<span className="code-inline">{data.excel}</span>（包含「客户明细」「字段字典」「数据来源」三个工作表）
          </li>
          <li>
            本仓库内置了一份 <span className="code-inline">backend/data/raw/ifood_df_sample.csv</span> 作为离线兜底，
            脚本会先尝试联网下载完整数据，失败时自动回退到内置样本，保证任何人 clone 下来都能直接跑通。
          </li>
        </ul>
      </Card>

      <Card title="数据处理流程" subtitle="scripts/prepare_data.py 一条命令完成「下载 → 清洗 → 字段标准化 → 落盘」">
        <ol className="bullets" style={{ paddingLeft: 20 }}>
          <li><strong>下载</strong>：优先拉取完整 CSV，失败则使用内置样本。</li>
          <li><strong>清洗</strong>：按客户编号去重；收入做 99 分位截断，避免极端值把聚类带偏；年龄裁剪到 18-90 岁。</li>
          <li><strong>反解 one-hot</strong>：原始数据把学历、婚姻状况拆成了一堆 0/1 列，这里还原成可读的单列字段。</li>
          <li><strong>字段标准化</strong>：把 MntWines、NumWebPurchases 之类的列名改成语义清晰的 snake_case，并统一中文标签。</li>
          <li><strong>派生指标</strong>：年龄段分箱、客单价、家庭子女数、总购买次数等，直接供分析和建模使用。</li>
          <li><strong>落盘</strong>：输出 Excel（给业务看）、processed/customers.csv（给程序读）和 dataset_meta.json（元信息）。</li>
        </ol>
      </Card>

      <Card title="字段字典" subtitle="共 26 个字段，前端图表与后端分析都用这套口径">
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

      <Card title="口径说明与局限" subtitle="把话说在前面，比过度承诺更专业">
        <ul className="bullets">
          <li>
            <strong>样本量有限</strong>：受网络限制，仓库内置的是完整数据集的一部分（当前 <span className="code-inline">{data.rows}</span> 条），
            足够跑通全流程与演示模型，但正式业务需要全量数据；联网环境下运行 <span className="code-inline">prepare_data.py</span> 可自动获取完整版本。
          </li>
          <li>
            <strong>标签定义</strong>：模型预测的「响应」指客户是否接受了最近一次促销活动，属于二分类问题，正负样本比例约 1:6。
          </li>
          <li>
            <strong>ROI 是估算值</strong>：客单价用该人群的历史人均消费代替，「预期响应率」是模型概率的均值，
            实际投放后应回填真实转化数据持续校准。
          </li>
          <li>
            <strong>隐私</strong>：数据为公开脱敏数据集，不含真实姓名、电话等个人身份信息，客户编号是预处理时重新生成的。
          </li>
        </ul>
      </Card>
    </>
  )
}
