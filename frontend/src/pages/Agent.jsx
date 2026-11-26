import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import Chart from '../components/Chart'
import { num } from '../lib/format'

function Block({ block }) {
  if (block.type === 'text') return <p>{block.content}</p>

  if (block.type === 'kpi') {
    return (
      <div className="block-kpi">
        {block.items.map((it) => (
          <div key={it.label}>
            <span>{it.label}</span>
            <strong>
              {typeof it.value === 'number' ? num(it.value, Number.isInteger(it.value) ? 0 : 2) : it.value}
              {it.suffix && <em style={{ fontStyle: 'normal', fontSize: 12, color: '#6b7280' }}>{it.suffix}</em>}
            </strong>
          </div>
        ))}
      </div>
    )
  }

  if (block.type === 'chart') {
    return (
      <div className="block-chart">
        {block.title && <p className="chart-caption">{block.title}</p>}
        <Chart option={block.option} height={240} />
        {block.note && <p className="chart-caption">{block.note}</p>}
      </div>
    )
  }

  if (block.type === 'table') {
    return (
      <div>
        {block.title && <p className="chart-caption" style={{ padding: '6px 0 0' }}>{block.title}</p>}
        <div className="block-table">
          <table>
            <thead>
              <tr>
                {block.columns.map((c) => (
                  <th key={c.key}>{c.title}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {block.rows.map((row, i) => (
                <tr key={i}>
                  {block.columns.map((c) => (
                    <td key={c.key}>
                      {typeof row[c.key] === 'number' ? num(row[c.key], Number.isInteger(row[c.key]) ? 0 : 2) : String(row[c.key] ?? '')}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  return null
}

export default function Agent() {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      text: '你好，我是客户洞察助手。你可以直接问我数据情况、客户分层、画像、响应预测，或者让我给某个客群出一个营销方案。',
      blocks: [],
      mode: 'rules',
    },
  ])
  const [suggestions, setSuggestions] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const logRef = useRef(null)

  useEffect(() => {
    api.suggestions().then(setSuggestions).catch(() => {})
  }, [])

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [messages])

  const send = async (text) => {
    const question = (text ?? input).trim()
    if (!question || busy) return
    setInput('')
    setBusy(true)
    const history = messages
      .filter((m) => m.role !== 'system')
      .map((m) => ({ role: m.role, content: m.text || '' }))
    setMessages((prev) => [...prev, { role: 'user', text: question }])
    try {
      const res = await api.chat(question, history)
      setMessages((prev) => [...prev, { role: 'assistant', text: res.reply, blocks: res.blocks || [], mode: res.mode }])
    } catch (err) {
      setMessages((prev) => [...prev, { role: 'assistant', text: `抱歉，出错了：${err.message}`, blocks: [] }])
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="chat">
      <div className="chat-log" ref={logRef}>
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            <div className="avatar">{m.role === 'user' ? '我' : 'AI'}</div>
            <div className="bubble">
              {m.text && <p>{m.text}</p>}
              {(m.blocks || []).map((b, j) => (
                <Block key={j} block={b} />
              ))}
            </div>
          </div>
        ))}
        {busy && (
          <div className="msg assistant">
            <div className="avatar">AI</div>
            <div className="bubble">
              <p className="muted">正在调数据、算指标…</p>
            </div>
          </div>
        )}
      </div>

      <div className="chips">
        {suggestions.map((s) => (
          <button key={s.label} type="button" className="chip" onClick={() => send(s.message)} disabled={busy}>
            {s.label}
          </button>
        ))}
      </div>

      <div className="chat-input">
        <input
          value={input}
          placeholder="例如：给重要价值客户出一个 2 万的营销方案"
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') send()
          }}
        />
        <button type="button" className="btn primary" onClick={() => send()} disabled={busy || !input.trim()}>
          发送
        </button>
      </div>
    </div>
  )
}
