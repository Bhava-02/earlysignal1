export const pct = (p, d = 0) => (p == null || Number.isNaN(p) ? '–' : p > 0 && p < 0.005 && d === 0 ? 'under 1%' : `${(100 * p).toFixed(d)}%`)
export const num = (x, d = 0) => (x == null || Number.isNaN(x) ? '–' : Number(x).toFixed(d))
export const signed = (x, d = 0) => (x == null ? '–' : `${x > 0 ? '+' : ''}${Number(x).toFixed(d)}`)

export const LEVEL_TONE = {
  High: 'urgent', Medium: 'medium', Low: 'low',
  'Not on track': 'urgent', 'Almost ready': 'medium', 'On track': 'low', 'Early stage': 'quiet',
  Urgent: 'urgent', None: 'quiet',
}
export const PRIORITY_TONE = { Urgent: 'urgent', High: 'high', Medium: 'medium', Low: 'low', None: 'quiet' }

export function levelWord(key, level) {
  if (key === 'placement') return level
  return { High: 'High risk', Medium: 'Medium risk', Low: 'Low risk' }[level] || level
}

export function initials(name) {
  return name.split(/[\s/,.]+/).filter((w) => /^[A-Za-z]/.test(w)).slice(0, 2).map((w) => w[0]).join('').toUpperCase()
}

export function plural(n, word, many) {
  return `${n.toLocaleString('en-IN')} ${n === 1 ? word : many || `${word}s`}`
}

export function toCSV(rows, cols) {
  const esc = (v) => {
    const s = v == null ? '' : String(v)
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  return [cols.map((c) => esc(c.label)).join(','), ...rows.map((r) => cols.map((c) => esc(c.get(r))).join(','))].join('\n')
}

export function download(name, text) {
  const blob = new Blob([text], { type: 'text/csv;charset=utf-8' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = name
  document.body.appendChild(a)
  a.click()
  setTimeout(() => {
    URL.revokeObjectURL(a.href)
    a.remove()
  }, 500)
}
