import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { Card, ErrorBox, Kpi, Loading, Table, Tag } from '../components/ui'
import { num } from '../lib/format'

const CAP_LABELS = {
  has_income: '收入字段',
  has_monetary: '消费金额',
  has_recency: '最近购买时间',
  has_frequency: '购买频次',
  has_response: '活动响应标签',
}
const ACCEPT = '.xlsx,.xlsm,.xls,.csv,.tsv,.txt,.json'

export default function Import({ onNavigate, onDataChanged }) {
  const inputRef = useRef(null)
  const [dragging, setDragging] = useState(false)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [inspect, setInspect] = useState(null)
  const [sheet, setSheet] = useState('')
  const [done, setDone] = useState(null)
  const [presets, setPresets] = useState([])
  const [history, setHistory] = useState([])

  useEffect(() => {
    api.importPresets().then((r) => setPresets(r.presets || [])).catch(() => {})
    refreshHistory()
  }, [])

  function refreshHistory() {
    api.importHistory().then(setHistory).catch(() => {})
  }

  async function handleFile(file, nextSheet = '') {
    if (!file) return
    setError('')
    setDone(null)
    setInspect(null)
    setBusy('正在试读文件、识别字段…')
    try {
      const data = await api.importInspect(file, nextSheet)
      setInspect(data)
      setSheet(data.sheet || '')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
      refreshHistory()
    }
  }

  function onDrop(event) {
    event.preventDefault()
    setDragging(false)
    const file = event.dataTransfer.files && event.dataTransfer.files[0]
    handleFile(file)
  }

  async function applyInspect() {
    if (!inspect) return
    setBusy('正在重建标准表并刷新全部分析…')
    setError('')
    try {
      const res = await api.importApply({ file: inspect.file, sheet: sheet || inspect.sheet })
      setDone(res)
      setInspect(null)
      refreshHistory()
      if (onDataChanged) onDataChanged()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  async function applyPreset(key) {
    setBusy('正在载入演示数据…')
    setError('')
    setDone(null)
    try {
      const res = await api.importPreset(key)
      setDone(res)
      if (onDataChanged) onDataChanged()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  async function applyHistory(item) {
    setBusy('正在应用历史文件…')
    setError('')
    try {
      const res = await api.importApply({ file: item.file })
      setDone(res)
      if (onDataChanged) onDataChanged()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  const current = history.current

  return (
    <div className="grid">
      <ErrorBox error={error ? { message: error } : null} />

      <Card
        title="上传一份客户表格"
        extra={
          current ? (
            <span className="muted small">
              当前数据：{current.rows} 行 · {current.name}
            </span>
          ) : null
        }
      >
        <div
          className={`dropzone ${dragging ? 'dragging' : ''}`}
          onDragOver={(e) => {
            e.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current && inputRef.current.click()}
          role="button"
          tabIndex={0}
        >
          <div className="dropzone-icon">📥</div>
          <strong>把 Excel / CSV 拖到这里，或点一下选择文件</strong>
          <span className="muted small">支持 .xlsx / .xls / .csv / .tsv / .json，单个文件最大 {history.limits?.max_mb || 40}MB</span>
          <span className="muted small">不用改表头：中英文列名、订单明细、多 sheet 都能自动识别</span>
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT}
            style={{ display: 'none' }}
            onChange={(e) => {
              const file = e.target.files && e.target.files[0]
              handleFile(file)
              e.target.value = ''
            }}
          />
        </div>

        {busy && <Loading text={busy} />}

        {done && (
          <div className="success-box">
            <strong>已切换数据：{done.dataset?.name}</strong>
            <p className="muted small">
              {num(done.dataset?.raw_rows)} 行原始数据 → 标准表 {num(done.dataset?.rows)} 位客户 × {done.dataset?.columns} 个字段
              {done.dataset?.grain ? ` · ${done.dataset.grain}` : ''}
              {done.took_ms ? ` · 用时 ${(done.took_ms / 1000).toFixed(1)}s` : ''}
            </p>
            <button type="button" className="link-btn" onClick={() => onNavigate && onNavigate('overview')}>
              去看看新的分析结果 →
            </button>
          </div>
        )}
      </Card>

      {inspect && (
        <>
          <Card
            title="第 1 步：确认字段识别结果"
            extra={<Tag color="#3b6cf6">{inspect.name}</Tag>}
          >
            <div className="kpis">
              <Kpi label="原始数据" value={num(inspect.raw_rows)} suffix={` 行 × ${inspect.raw_columns} 列`} hint={inspect.sheets?.length ? `sheet：${inspect.sheet}` : 'CSV / JSON'} />
              <Kpi label="标准表" value={num(inspect.output_rows)} suffix={` 位客户 × ${inspect.output_columns} 列`} hint={inspect.grain_label} />
              <Kpi label="命中标准字段" value={inspect.matched} suffix=" 个" hint="其余列自动忽略或用作品类/渠道" />
              <Kpi label="去掉重复行" value={num(inspect.dropped_duplicates)} suffix=" 行" hint="完全相同的行只保留一条" />
            </div>

            {inspect.sheets && inspect.sheets.length > 1 && (
              <div className="field-row">
                <label>选择 sheet</label>
                <select
                  value={sheet}
                  onChange={(e) => {
                    const next = e.target.value
                    setSheet(next)
                    const file = inputRef.current?.files?.[0]
                    if (file) handleFile(file, next)
                  }}
                >
                  {inspect.sheets.map((name) => (
                    <option key={name} value={name}>
                      {name}
                    </option>
                  ))}
                </select>
                <span className="muted small">切换 sheet 会重新试读一次</span>
              </div>
            )}

            <div className="tag-row">
              {Object.entries(CAP_LABELS).map(([key, label]) => (
                <Tag key={key} color={inspect.capabilities[key] ? '#0f9d58' : '#8c8f9a'}>
                  {inspect.capabilities[key] ? '✓ ' : '✗ '}
                  {label}
                </Tag>
              ))}
              <Tag color={inspect.capabilities.propensity ? '#0f9d58' : '#8c8f9a'}>
                {inspect.capabilities.propensity ? '✓ ' : '✗ '}响应预测可用
              </Tag>
            </div>

            {inspect.warnings && inspect.warnings.length > 0 && (
              <div className="warn-box">
                {inspect.warnings.map((w) => (
                  <p key={w} className="small">
                    · {w}
                  </p>
                ))}
              </div>
            )}

            <div className="field-row">
              <button type="button" className="btn primary" onClick={applyInspect} disabled={!!busy}>
                就用这份数据，开始分析
              </button>
              <button type="button" className="btn" onClick={() => setInspect(null)} disabled={!!busy}>
                取消
              </button>
              <span className="muted small">应用后所有页面会立刻换成这份数据，可随时切回内置数据集。</span>
            </div>
          </Card>

          <Card title="字段自动映射">
            <Table
              columns={[
                { key: 'label', title: '标准字段' },
                { key: 'target', title: '内部字段名' },
                { key: 'source', title: '来自你的列' },
                { key: 'confidence', title: '置信度', width: 80 },
                { key: 'how', title: '识别依据' },
              ]}
              rows={inspect.mapping}
            />
            {inspect.unused_columns && inspect.unused_columns.length > 0 && (
              <p className="muted small">没用上的列：{inspect.unused_columns.join('、')}</p>
            )}
          </Card>

          <Card title="原始数据预览（前 6 行）">
            <Table
              columns={inspect.preview.columns.map((c) => ({ key: c, title: c }))}
              rows={inspect.preview.rows.map((row, i) => {
                const obj = { _key: i }
                inspect.preview.columns.forEach((c, j) => {
                  obj[c] = row[j]
                })
                return obj
              })}
              rowKey="_key"
            />
          </Card>
        </>
      )}

      <Card title="或者直接用内置数据集" extra={<span className="muted small">不用联网，随时切回来</span>}>
        <div className="btn-row">
          {presets.map((p) => (
            <button key={p.key} type="button" className="btn" onClick={() => applyPreset(p.key)} disabled={!!busy}>
              {p.label}
            </button>
          ))}
        </div>
      </Card>

      <Card title="最近上传" extra={<span className="muted small">只保留最近 {history.limits?.keep || 30} 个文件</span>}>
        <Table
          columns={[
            { key: 'name', title: '文件' },
            { key: 'uploaded_at', title: '上传时间', width: 150 },
            { key: 'size', title: '大小', width: 100, align: 'right', render: (r) => `${(r.size / 1024).toFixed(0)} KB` },
            {
              key: 'act',
              title: '',
              width: 110,
              align: 'right',
              render: (r) => (
                <button type="button" className="link-btn" onClick={() => applyHistory(r)} disabled={!!busy}>
                  直接应用
                </button>
              ),
            },
          ]}
          rows={history.uploads || []}
          rowKey="file"
          empty="还没有上传过文件"
        />
      </Card>
    </div>
  )
}
