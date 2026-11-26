import { PALETTE } from '../lib/format'

export function Card({ title, subtitle, extra, children, className = '', style }) {
  return (
    <section className={`card ${className}`} style={style}>
      {(title || extra) && (
        <header className="card-head">
          <div>
            {title && <h3>{title}</h3>}
            {subtitle && <p className="muted small">{subtitle}</p>}
          </div>
          {extra}
        </header>
      )}
      <div className="card-body">{children}</div>
    </section>
  )
}

export function Kpi({ label, value, suffix, hint, tone }) {
  return (
    <div className={`kpi ${tone || ''}`}>
      <span className="kpi-label">{label}</span>
      <strong className="kpi-value">
        {value}
        {suffix && <em>{suffix}</em>}
      </strong>
      {hint && <span className="kpi-hint">{hint}</span>}
    </div>
  )
}

export function Tag({ children, color }) {
  return (
    <span className="tag" style={color ? { background: `${color}1a`, color } : undefined}>
      {children}
    </span>
  )
}

export function Table({ columns, rows, empty = '暂无数据', rowKey }) {
  if (!rows || rows.length === 0) return <p className="muted small">{empty}</p>
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} style={{ width: c.width, textAlign: c.align || 'left' }}>
                {c.title}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={rowKey ? row[rowKey] : i}>
              {columns.map((c) => (
                <td key={c.key} style={{ textAlign: c.align || 'left' }}>
                  {c.render ? c.render(row, i) : row[c.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function Tabs({ items, value, onChange }) {
  return (
    <div className="tabs">
      {items.map((it) => (
        <button
          key={it.key}
          type="button"
          className={`tab ${value === it.key ? 'active' : ''}`}
          onClick={() => onChange(it.key)}
        >
          {it.label}
        </button>
      ))}
    </div>
  )
}

export function Loading({ text = '正在计算…' }) {
  return <div className="placeholder">{text}</div>
}

export function ErrorBox({ error }) {
  if (!error) return null
  return <div className="error-box">接口请求失败：{String(error.message || error)}</div>
}

export function legendDots(items) {
  return items.map((it, i) => (
    <span key={it} className="legend-dot">
      <i style={{ background: PALETTE[i % PALETTE.length] }} />
      {it}
    </span>
  ))
}
