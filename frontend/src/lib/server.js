// The EarlySignal server (api.py), when the app is opened from it. Opened as a plain file or from a static host,
// SERVER stays null and the app works on the data inside it, with codes shown on screen.
let SERVER = null
let CONFIG = {}

export const server = () => SERVER
export const config = () => CONFIG

async function getJSON(path, ms) {
  const ctl = new AbortController()
  const t = setTimeout(() => ctl.abort(), ms)
  try {
    const r = await fetch(path, { signal: ctl.signal, cache: 'no-store', headers: { Accept: 'application/json' } })
    if (!r.ok || !(r.headers.get('content-type') || '').includes('json')) return null
    return await r.json()
  } catch {
    return null
  } finally {
    clearTimeout(t)
  }
}

// Called once before the app is drawn. Returns the latest data from the server, if there is one.
export async function boot() {
  if (!/^https?:$/.test(window.location.protocol)) return null
  const health = await getJSON('api/health', 5000)
  if (health && health.app === 'earlysignal') {
    SERVER = health
    CONFIG = (await getJSON('api/config', 5000)) || {}
    return getJSON('api/bundle', 60000)
  }
  CONFIG = (await getJSON('earlysignal-config.json', 4000)) || {}
  return null
}

export async function refreshHealth() {
  const h = await getJSON('api/health', 5000)
  if (h && h.app === 'earlysignal') SERVER = h
  return SERVER
}

// ---------------------------------------------------------------- calls to the server
const KEY = 'es.adminKey'
export function adminKey() {
  try { return window.sessionStorage.getItem(KEY) || '' } catch { return '' }
}
export function setAdminKey(k) {
  try { window.sessionStorage.setItem(KEY, k) } catch { /* storage blocked: key lasts until the page closes */ }
}

export async function api(path, { method = 'GET', body, form } = {}) {
  const headers = { Accept: 'application/json' }
  const key = adminKey()
  if (key) headers['X-Admin-Key'] = key
  let payload
  if (form) payload = form
  else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }
  let r
  try {
    r = await fetch(`api/${path}`, { method, headers, body: payload, cache: 'no-store' })
  } catch {
    throw new Error('The EarlySignal server could not be reached. Check your connection and try again.')
  }
  let data = null
  try { data = await r.json() } catch { /* not JSON */ }
  if (!r.ok) {
    const msg = data?.error || data?.detail || `The server answered with an error (${r.status}).`
    const e = new Error(typeof msg === 'string' ? msg : 'The server could not do that.')
    e.status = r.status
    throw e
  }
  return data
}

// Follow a background job (sync, upload, reset) until it ends. onLine gets each progress line.
export async function follow(jobId, onLine) {
  let since = 0
  for (;;) {
    const j = await api(`jobs/${jobId}?since=${since}`)
    for (const l of j.lines) onLine?.(l)
    since = j.next
    if (j.state !== 'running') return j
    await new Promise((res) => setTimeout(res, 1200))
  }
}
