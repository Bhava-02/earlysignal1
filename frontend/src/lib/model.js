// The Round 1 Success Score formula, early-warning model and placement model, re-run in the browser for the
// what-if sliders and the Path to Green. Same parameters as the Python pipeline (src/whatif.py), so numbers agree.

export const FRIENDLY = {
  cgpa: 'CGPA', cia1_pct: 'Internal test marks (CIA-1)', att_pct: 'Attendance', backlogs: 'Standing arrears',
  faculty_rating: 'Faculty rating', lms_avg: 'LMS logins per week', asg_rate: 'Assignments submitted',
  momentum: 'Recent effort trend', activities: 'Events and clubs', satisfaction: 'Satisfaction survey',
  best_aptitude: 'Aptitude score', best_coding: 'Coding score', mock_interviews: 'Mock interviews done',
  avg_mock_rating: 'Mock interview rating', technical_score: 'Technical skills', soft_skill_score: 'Soft skills',
  certifications: 'Certifications', eligible: 'Eligible for placements',
}
const PART = { academic: 'Academics', engagement: 'Engagement', placement: 'Placement readiness' }

export function fmtValue(k, v, s) {
  if (v == null) return 'none'
  if (k === 'cia1_pct' || k === 'att_pct') return `${Math.round(v)}%`
  if (k === 'asg_rate') return `${Math.round(v * 100)}%`
  if (k === 'cgpa') return v.toFixed(2)
  if (k === 'faculty_rating' || k === 'satisfaction' || k === 'avg_mock_rating') {
    return k === 'avg_mock_rating' && s && s.v.mock_interviews === 0 ? 'none yet' : `${v.toFixed(1)} / 5`
  }
  if (k === 'lms_avg') return v.toFixed(1)
  if (k === 'momentum') return v < -0.15 ? 'falling' : v > 0.15 ? 'rising' : 'steady'
  if (k === 'eligible') return v >= 0.5 ? 'Yes' : 'No'
  if (['best_aptitude', 'best_coding', 'technical_score', 'soft_skill_score'].includes(k)) return `${Math.round(v)} / 100`
  return `${Math.round(v)}`
}

const FLOOR = new Set(['faculty_rating', 'satisfaction', 'avg_mock_rating', 'lms_avg', 'activities', 'mock_interviews', 'certifications'])
const CEILING = new Set(['att_pct', 'faculty_rating', 'satisfaction', 'avg_mock_rating', 'asg_rate'])
function scaleText(k, v, end) {
  if (k === 'eligible') return v >= 0.5 ? 'Yes' : 'No'
  if (k === 'momentum') return v < 0 ? 'falling fast' : 'rising fast'
  if (k === 'backlogs') return end === 'zero' ? '4 or more' : '0'
  const t = k === 'cgpa' ? v.toFixed(1) : fmtValue(k, v)
  if (end === 'zero' && !FLOOR.has(k)) return `${t} or less`
  if (end === 'full' && !CEILING.has(k)) return `${t} or more`
  return t
}

function predict(p, x) {
  let z = p.intercept
  p.features.forEach((f, i) => {
    let v = x[f]
    if (v == null || Number.isNaN(v)) v = p.median[i]
    z += (p.coef[i] * (Number(v) - p.mean[i])) / p.scale[i]
  })
  return 1 / (1 + Math.exp(-z))
}

export function createModel(B) {
  const M = B.meta
  const IND = B.indicators

  const level = (p) => (p >= M.risk_high ? 'High' : p >= M.risk_medium ? 'Medium' : 'Low')
  const plevel = (p, eligible) => (p == null ? 'Pre-placement' : p < 0.35 || !eligible ? 'High' : p < 0.6 ? 'Medium' : 'Low')
  const projAtt = (s, rate) => (100 * (s.v.classes_attended + rate * s.v.classes_remaining)) / (s.v.classes_held + s.v.classes_remaining)

  function score(v, year) {
    const w = B.weights[String(year)] || B.weights['3']
    let total = 0
    const parts = { academic: [0, 0], engagement: [0, 0], placement: [0, 0] }
    for (const ind of IND) {
      if (!(ind.key in w)) continue
      let x = Math.min(1, Math.max(0, ((v[ind.key] ?? 0) - ind.lo) / (ind.hi - ind.lo)))
      if (ind.invert) x = 1 - x
      total += 100 * w[ind.key] * x
      parts[ind.part][0] += w[ind.key] * x
      parts[ind.part][1] += w[ind.key]
    }
    return { score: total, subs: Object.fromEntries(Object.entries(parts).map(([k, [a, b]]) => [k, b ? (100 * a) / b : 0])) }
  }

  function simulate(s, ch = {}) {
    const r = s.v
    const v = Object.fromEntries(IND.map((i) => [i.key, Number(r[i.key] ?? 0)]))
    let changed = false
    if (ch.attend_rate != null) { v.att_pct = Math.max(r.att_pct, projAtt(s, ch.attend_rate)); changed = true }
    if (ch.asg_rate != null) { v.asg_rate = Math.max(r.asg_rate, ch.asg_rate); changed = true }
    if (ch.lms_avg != null) { v.lms_avg = Math.max(r.lms_avg, ch.lms_avg); changed = true }
    v.mock_interviews += ch.mock_add || 0
    if (ch.mock_add && r.mock_interviews === 0) v.avg_mock_rating = 2.8
    v.best_aptitude = Math.min(99, v.best_aptitude + (ch.aptitude_add || 0))
    v.best_coding = Math.min(99, v.best_coding + (ch.coding_add || 0))
    v.certifications += ch.cert_add || 0
    v.backlogs = Math.max(0, v.backlogs - (ch.arrears_cleared || 0))
    v.eligible = v.cgpa >= M.cgpa_min && v.backlogs <= M.max_backlogs ? 1 : 0
    if (changed) v.momentum = Math.max(v.momentum, 0)
    const sc = score(v, s.year)
    const prob = predict(B.models.risk, {
      att_pct: v.att_pct, att_trend: changed ? Math.max(r.att_trend, 0) : r.att_trend, lms_avg: v.lms_avg,
      lms_change: changed ? Math.max(r.lms_change, 0) : r.lms_change, asg_rate: v.asg_rate,
      asg_change: changed ? Math.max(r.asg_change, 0) : r.asg_change, prior_cgpa: r.cgpa, backlogs: v.backlogs,
      cia1_pct: r.cia1_pct, cia1_absent: r.cia1_absent,
    })
    const pprob = s.year >= 3 ? predict(B.models.placement, { ...v, avg_mock_rating: v.mock_interviews === 0 ? 2.5 : v.avg_mock_rating }) : null
    return { score: sc.score, subs: sc.subs, prob, pprob, values: v }
  }

  function describe(s, plan) {
    const r = s.v
    const out = []
    for (const [k, v] of Object.entries(plan)) {
      if (k === 'attend_rate') out.push(`Attend ${Math.round(v * 100)}% of the remaining ~${Math.round(r.classes_remaining)} classes (attendance ends at ${Math.round(projAtt(s, v))}% instead of ${Math.round(r.projected_attendance)}%)`)
      else if (k === 'asg_rate') out.push(`Submit ${Math.round(v * 100)}% of assignments from now on (currently ${Math.round(r.asg_rate * 100)}%)`)
      else if (k === 'lms_avg') out.push(`Log in to the LMS ${v} or more times a week (currently ${r.lms_avg.toFixed(1)})`)
      else if (k === 'mock_add') out.push(`Complete ${v} mock interview${v > 1 ? 's' : ''} (done so far: ${Math.round(r.mock_interviews)})`)
      else if (k === 'aptitude_add') out.push(`Raise aptitude score by ${v} points through the placement cell's practice tests`)
      else if (k === 'coding_add') out.push(`Raise coding score by ${v} points (weekly practice track)`)
      else if (k === 'cert_add') out.push(`Earn ${v} relevant certification${v > 1 ? 's' : ''} (NPTEL or industry)`)
      else if (k === 'arrears_cleared') out.push(`Clear ${v} standing arrear${v > 1 ? 's' : ''} in the next attempt`)
    }
    return out
  }

  function pathToGreen(s, target = 55) {
    const r = s.v
    const year = s.year
    const cur0 = r.att_recent / 100
    const range = (n) => Array.from({ length: n }, (_, i) => i + 1)
    const levers = {
      attend_rate: { steps: [0.8, 0.85, 0.9, 0.95, 1.0].filter((x) => x > cur0 + 0.02), cost: 1 },
      asg_rate: { steps: [0.7, 0.8, 0.9, 1.0].filter((x) => x > r.asg_rate + 0.02), cost: 1 },
      lms_avg: { steps: [3, 4, 5, 6].filter((x) => x > r.lms_avg + 0.3), cost: 0.5 },
      mock_add: { steps: year >= 3 ? [1, 2, 3, 4] : [], cost: 1.5 },
      aptitude_add: { steps: [5, 10, 15], cost: 2 },
      coding_add: { steps: year >= 3 ? [5, 10, 15] : [], cost: 2 },
      cert_add: { steps: [1, 2], cost: 2 },
      arrears_cleared: { steps: range(Math.round(r.backlogs)).slice(0, 3), cost: 3 },
    }
    const utility = (x) => {
      let u = x.score - 80 * Math.max(0, x.prob - (M.risk_medium - 0.02))
      if (year >= 3) u += 40 * Math.min(x.pprob, 0.62) + (x.values.eligible ? 15 : 0)
      return u
    }
    const cgpaOk = r.cgpa >= M.cgpa_min
    const done = (x) => {
      let ok = x.score >= target - 0.5 && x.prob < M.risk_medium
      if (year >= 3) ok = ok && x.pprob >= 0.6 && (!!x.values.eligible || !cgpaOk)
      return ok
    }
    const plan = {}
    const pos = Object.fromEntries(Object.keys(levers).map((k) => [k, 0]))
    if (r.projected_attendance < M.attendance_min && r.required_rate_for_75 <= 100) {
      const need = r.required_rate_for_75 / 100
      const steps = levers.attend_rate.steps
      const first = steps.find((x) => x >= need)
      if (first != null) { plan.attend_rate = first; pos.attend_rate = steps.indexOf(first) + 1 }
    }
    const start = simulate(s, {})
    let cur = simulate(s, plan)
    for (let i = 0; i < 10; i++) {
      if (done(cur)) break
      let best = null
      for (const [k, L] of Object.entries(levers)) {
        if (pos[k] >= L.steps.length) continue
        const trial = { ...plan, [k]: L.steps[pos[k]] }
        const res = simulate(s, trial)
        const gain = (utility(res) - utility(cur)) / L.cost
        if (best == null || gain > best.gain) best = { gain, k, trial, res }
      }
      if (!best || best.gain <= 0.05) break
      Object.assign(plan, best.trial)
      cur = best.res
      pos[best.k]++
    }
    return { plan, start, end: cur, reached: done(cur), steps: describe(s, plan) }
  }

  function marksheet(s) {
    const w = B.weights[String(s.year)] || B.weights['3']
    return IND.filter((i) => i.key in w).map((i) => {
      const raw = s.v[i.key] ?? 0
      let x = Math.min(1, Math.max(0, (raw - i.lo) / (i.hi - i.lo)))
      if (i.invert) x = 1 - x
      const out = 100 * w[i.key]
      return {
        key: i.key, part: PART[i.part], item: FRIENDLY[i.key] || i.label, value: fmtValue(i.key, raw, s),
        zero: scaleText(i.key, i.invert ? i.hi : i.lo, 'zero'), full: scaleText(i.key, i.invert ? i.lo : i.hi, 'full'),
        marks: out * x, outOf: out,
      }
    })
  }

  return { simulate, pathToGreen, marksheet, level, plevel, projAtt }
}
