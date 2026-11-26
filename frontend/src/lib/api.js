const BASE = import.meta.env.VITE_API_BASE || '/api'

async function request(path, init) {
  const resp = await fetch(`${BASE}${path}`, init)
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
}
