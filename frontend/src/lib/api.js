// 前后端分离：默认走同源的 /api（开发时由 Vite 代理、生产时由 Nginx/静态服务器代理），
// 也可以构建时用 VITE_API_BASE=http://127.0.0.1:8000/api 直连后端。
const BASE = import.meta.env.VITE_API_BASE || '/api'

async function request(path, init) {
  let resp
  try {
    resp = await fetch(`${BASE}${path}`, init)
  } catch (err) {
    throw new Error(`无法连接后端 ${BASE}（请确认后端已启动，且地址配置正确）`)
  }
  if (!resp.ok) {
    let detail = `${resp.status} ${resp.statusText}`
    try {
      const body = await resp.json()
      detail = body.detail || JSON.stringify(body)
    } catch (err) {
      /* 忽略解析失败 */
    }
    throw new Error(detail)
  }
  return resp.json()
}

export const api = {
  health: () => request('/health'),
  dataset: () => request('/dataset'),
  overview: () => request('/overview'),
  insights: () => request('/insights'),
  segments: () => request('/segments'),
  personas: () => request('/personas'),
  elbow: (kMax = 7) => request(`/clusters/elbow?k_max=${kMax}`),
  propensity: () => request('/propensity'),
  association: () => request('/association'),
  campaignOptions: () => request('/campaign/options'),
  plan: (payload) =>
    request('/campaign/plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  customers: (params = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== '' && v !== undefined && v !== null),
    ).toString()
    return request(`/customers?${qs}`)
  },
  customer: (id) => request(`/customers/${id}`),
  chat: (message, history) =>
    request('/agent/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, history }),
    }),
  suggestions: () => request('/agent/suggestions'),
  // 数据导入：先试读（不上线）→ 用户确认后再应用
  importPresets: () => request('/import/presets'),
  importHistory: () => request('/import/history'),
  importInspect: (file, sheet) => {
    const form = new FormData()
    form.append('file', file)
    if (sheet) form.append('sheet', sheet)
    return request('/import/inspect', { method: 'POST', body: form })
  },
  importApply: (payload) =>
    request('/import/apply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  importPreset: (dataset) =>
    request('/import/preset', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dataset }),
    }),
}
