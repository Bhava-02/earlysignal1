// The interventions log (Round 1 "Record what was done"), kept in this browser.
import { useSyncExternalStore } from 'react'
import { META, store } from './data'

export const STATUSES = ['Pending', 'Planned', 'In progress', 'Done', 'Could not reach']
const KEY = 'es.actions'
let cache = store.get(KEY, [])
const subs = new Set()
const emit = () => subs.forEach((f) => f())

export function logActions(rows) {
  const at = new Date().toISOString()
  cache = [...cache, ...rows.map((r, i) => ({ id: `${Date.now()}-${i}-${r.roll_no}`, logged_at: at, week: META.week, status: 'Planned', ...r }))]
  store.set(KEY, cache)
  emit()
}

export function setStatus(id, status) {
  cache = cache.map((a) => (a.id === id ? { ...a, status } : a))
  store.set(KEY, cache)
  emit()
}

export function useActions() {
  return useSyncExternalStore((f) => { subs.add(f); return () => subs.delete(f) }, () => cache)
}

// latest status per student
export function latestStatus(actions) {
  const m = {}
  for (const a of [...actions].sort((x, y) => x.logged_at.localeCompare(y.logged_at))) m[a.roll_no] = a.status
  return m
}
