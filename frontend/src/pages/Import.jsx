import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { Card, ErrorBox, Kpi, Loading, Table, Tag } from '../components/ui'
import { num } from '../lib/format'

const CAP_LABELS = {
  has_income: '收入',
  has_monetary: '消费金额',
  has_recency: '最近购买',
  has_frequency: '购买频次',
  has_response: '活动结果',
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
  const [history, setHistory] = useState({ uploads: [], current: null, limits: {} })

  useEffect(() => {
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
    setBusy('正在读取并识别字段…')
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

  async function applyHistory(item) {
    setBusy('正在应用这份文件…')
    setError('')
    setDone(null)
    try {
      const res = await api.importApply({ file: item.file })
      setDone(res)
      refreshHistory()
      if (onDataChanged) onDataChanged()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  const uploads = history.uploads || []

  return (
    <div className="grid">
      <ErrorBox error={error ? { message: error } : null} />

      <Card title="上传数据文件">
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
          <div className="dropzone-icon">📄</div>
          <strong>选择 Excel 或 CSV 文件</strong>
          <span className="quiet">支持 .xlsx / .xls / .csv / .tsv / .json，单个文件最大 {history.limits?.max_mb || 40}MB</span>
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

        <div className="row-between" style={{ marginTop: 12 }}>
          <a className="link-quiet" href="/api/import/template" download>
            下载数据模板
          </a>
          {history.uploads && uploads.length > 0 && (
            <span className="quiet">最近上传 {uploads.length} 个文件</span>
          )}
        </div>

        {busy && <Loading text={busy} />}

        {done && (
          <div className="success-box">
            <strong>已切换为你的数据：{done.dataset?.name}</strong>
            <p className="quiet" style={{ margin: '6px 0' }}>
              {num(done.dataset?.raw_rows)} 行原始数据 → {num(done.dataset?.rows)} 位客户 × {done.dataset?.columns} 个字段
              {done.dataset?.grain ? ` · ${done.dataset.grain}` : ''}
              {done.took_ms ? ` · 用时 ${(done.took_ms / 1000).toFixed(1)}s` : ''}
            </p>
            <button type="button" className="link-btn" onClick={() => onNavigate && onNavigate('overview')}>
              去看新的分析结果 →
            </button>
          </div>
        )}
      </Card>

      {inspect && (
        <>
          <Card title="识别结果" extra={<Tag color="#3b6cf6">{inspect.name}</Tag>}>
            <div className="kpis">
              <Kpi label="读到" value={num(inspect.raw_rows)} suffix={` 行 × ${inspect.raw_columns} 列`} hint={inspect.sheets?.length ? `sheet：${inspect.sheet}` : 'CSV / JSON'} />
              <Kpi label="整理成" value={num(inspect.output_rows)} suffix={` 位客户 × ${inspect.output_columns} 列`} hint={inspect.grain_label} />
              <Kpi label="认出的字段" value={inspect.matched} suffix=" 个" hint="其余列自动忽略或用作品类/渠道" />
              <Kpi label="去掉重复行" value={num(inspect.dropped_duplicates)} suffix=" 行" hint="完全相同的行只保留一条" />
            </div>

            {inspect.sheets && inspect.sheets.length > 1 && (
              <div className="field-row">
                <label>工作表</label>
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
                {inspect.capabilities.propensity ? '✓ ' : '✗ '}响应预测
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

            <div className="field-row" style={{ marginTop: 8 }}>
              <button type="button" className="btn primary" onClick={applyInspect} disabled={!!busy}>
                用这份数据开始分析
              </button>
              <button type="button" className="btn" onClick={() => setInspect(null)} disabled={!!busy}>
                换一个文件
              </button>
            </div>
          </Card>

          <Card
            title="字段对应关系"
            extra={<span className="quiet">列不认识时，可在 backend/app/core/schema.py 添加别名</span>}
          >
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
              <p className="quiet">没用上的列：{inspect.unused_columns.join('、')}</p>
            )}
          </Card>

          <Card title="文件前 6 行">
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

      {history.uploads && uploads.length > 0 && (
        <Card title="最近用过的文件" extra={<span className="quiet">最多保留 {history.limits?.keep || 30} 个</span>}>
          <Table
            columns={[
              { key: 'name', title: '文件' },
              { key: 'uploaded_at', title: '上传时间', width: 150 },
              { key: 'size', title: '大小', width: 100, align: 'right', render: (r) => `${(r.size / 1024).toFixed(0)} KB` },
              {
                key: 'act',
                title: '',
                width: 90,
                align: 'right',
                render: (r) => (
                  <button type="button" className="link-btn" onClick={() => applyHistory(r)} disabled={!!busy}>
                    再用一次
                  </button>
                ),
              },
            ]}
            rows={history.uploads.slice(0, 5)}
            rowKey="file"
            empty="还没有上传过文件"
          />
        </Card>
      )}
    </div>
  )
}
