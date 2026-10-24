// The Round 1 AI assistant: a plain-English question becomes a filter over the student list (src/nlq.py rule_parse).
// Numbers always come from the data. Questions it cannot turn into a filter get a polite pointer to the admin.
import { B, DEPTS, MENTORS } from './data'

const GET = {
  dept: (s) => s.dept, year: (s) => s.year, section: (s) => s.sec, residence: (s) => s.res, gender: (s) => s.gender,
  first_graduate: (s) => s.fg, mentor: (s) => s.mentor, band: (s) => s.band, acad_risk: (s) => s.ar, placement_risk: (s) => s.pr,
  segment: (s) => s.seg, newly_flagged: (s) => s.new, attendance_shortage: (s) => s.short,
}
const val = (s, f) => (GET[f] ? GET[f](s) : s.v[f])

const NUM_FIELDS = [
  ['projected attendance', 'projected_attendance'], ['attendance', 'att_pct'], ['cgpa|gpa', 'cgpa'],
  ['success score|score', 'success_score'], ['academic health', 'academic'], ['engagement', 'engagement'],
  ['placement readiness', 'placement'], ['arrears?|backlogs?', 'backlogs'], ['cia|internal marks?|marks', 'cia1_pct'],
  ['lms logins?|logins?', 'lms_avg'], ['coding', 'best_coding'], ['aptitude', 'best_aptitude'],
  ['mock interviews?|mocks?', 'mock_interviews'], ['certifications?', 'certifications'],
]
const CMP = [['below|under|less than|lower than|<', '<'], ['at most|<=|no more than', '<='],
  ['above|over|more than|greater than|higher than|>', '>'], ['at least|>=|min(?:imum)?', '>=']]
const LABEL = {
  projected_attendance: 'projected attendance', att_pct: 'attendance', cgpa: 'CGPA', success_score: 'Success Score', academic: 'academic health',
  engagement: 'engagement', placement: 'placement readiness', backlogs: 'arrears', cia1_pct: 'CIA-1 marks', lms_avg: 'LMS logins',
  best_coding: 'coding', best_aptitude: 'aptitude', mock_interviews: 'mock interviews', certifications: 'certifications',
}
const OPW = { '<': 'below', '<=': 'at most', '>': 'above', '>=': 'at least' }

export const EXAMPLES = [
  'CSE 3rd years with attendance below 75', 'Final years with CGPA above 8 and no mock interviews', 'High risk day scholars in ECE',
  'Hidden strugglers in IT', 'Students newly flagged this week', 'Hostel students in IT with coding below 40',
]

export function parse(question) {
  const q = question.replace(/hidden strugglers/gi, 'silent strugglers')
  let text = q.toLowerCase()
  const F = []
  const expl = []
  const pats = [['CSE', /\bcse\b|computer science/], ['ECE', /\bece\b|electronics/], ['MECH', /\bmech\b|mechanical/], ['IT', /\bIT\b|information tech/]]
  for (const d of DEPTS) if (!pats.some(([c]) => c === d.code)) pats.push([d.code, new RegExp(`\\b${d.code.toLowerCase()}\\b`)])
  const depts = pats.filter(([d, re]) => re.test(d === 'IT' ? q : text)).map(([d]) => d)
  if (depts.length) { F.push({ field: 'dept', op: 'in', value: depts }); expl.push(depts.join(' and ')) }
  const years = [[1, /\b(1st|first)\b|year 1/], [2, /\b(2nd|second|ii)\b|year 2/], [3, /\b(3rd|third|iii)\b|year 3/], [4, /\b(4th|fourth|final|iv)\b|year 4/]]
    .filter(([, re]) => re.test(text)).map(([y]) => y)
  if (years.length) { F.push({ field: 'year', op: 'in', value: years }); expl.push(`year ${years.join(' and ')}`) }
  for (const [pat, field] of NUM_FIELDS) {
    for (const [cpat, op] of CMP) {
      const m = text.match(new RegExp(`(?:${pat})\\s*(?:is\\s*|of\\s*)?(?:${cpat})\\s*(\\d+(?:\\.\\d+)?)`))
      if (m) {
        F.push({ field, op, value: Number(m[1]) })
        expl.push(`${LABEL[field]} ${OPW[op]} ${m[1]}`)
        text = text.replace(m[0], ' ')
        break
      }
    }
  }
  if (/high[- ]risk|high academic risk/.test(text)) { F.push({ field: 'acad_risk', op: 'in', value: ['High'] }); expl.push('high academic risk') }
  else if (/at[- ]risk|medium risk|risky/.test(text)) { F.push({ field: 'acad_risk', op: 'in', value: ['High', 'Medium'] }); expl.push('academic risk high or moderate') }
  if (text.includes('placement risk')) { F.push({ field: 'placement_risk', op: 'in', value: ['High', 'Medium'] }); expl.push('placement risk high or moderate') }
  if (/declin|falling|dropp|disengag/.test(text)) { F.push({ field: 'lms_change', op: '<=', value: -0.25 }); expl.push('LMS activity falling') }
  if (/shortage|detain|below 75/.test(text) && !F.some((f) => f.field === 'att_pct')) { F.push({ field: 'attendance_shortage', op: '==', value: true }); expl.push('heading for attendance shortage') }
  if (/new(ly)?|this week/.test(text)) { F.push({ field: 'newly_flagged', op: '==', value: true }); expl.push('newly high risk this week') }
  if (/no mock|zero mock|without mock/.test(text)) { F.push({ field: 'mock_interviews', op: '==', value: 0 }); expl.push('no mock interviews') }
  if (text.includes('hostel')) { F.push({ field: 'residence', op: '==', value: 'Hostel' }); expl.push('hostellers') }
  if (/day scholar/.test(text)) { F.push({ field: 'residence', op: '==', value: 'Day Scholar' }); expl.push('day scholars') }
  if (/\b(girls|female|women)\b/.test(text)) { F.push({ field: 'gender', op: '==', value: 'F' }); expl.push('female') }
  if (/\b(boys|male|men)\b/.test(text)) { F.push({ field: 'gender', op: '==', value: 'M' }); expl.push('male') }
  if (/first[- ]graduate/.test(text)) { F.push({ field: 'first_graduate', op: '==', value: 'Yes' }); expl.push('first-graduate') }
  for (const g of B.segments) {
    const key = g.name.toLowerCase().split(':')[0].split(',')[0]
    if (text.includes(key)) { F.push({ field: 'segment', op: '==', value: g.name }); expl.push(`group "${g.name}"`) }
  }
  for (const m of MENTORS) {
    const surname = m.name.split(/\s+/).at(-1).toLowerCase()
    if (surname.length > 3 && text.includes(surname)) { F.push({ field: 'mentor', op: '==', value: m.name }); expl.push(`mentor ${m.name}`) }
  }
  let sort = { field: 'acad_prob', desc: true }
  if (/lowest|worst|bottom/.test(text)) sort = { field: 'success_score', desc: false }
  else if (/best|top performers|highest score/.test(text)) sort = { field: 'success_score', desc: true }
  const lim = text.match(/\b(?:top|first|show)\s+(\d+)/)
  return { filters: F, sort, limit: lim ? Number(lim[1]) : 200, explanation: expl.join(', ') }
}

export function apply(students, spec) {
  let out = students
  for (const f of spec.filters) {
    out = out.filter((s) => {
      const x = val(s, f.field)
      if (f.op === 'in') return f.value.map((v) => String(v).toLowerCase()).includes(String(x).toLowerCase())
      if (f.op === '==') return typeof f.value === 'boolean' ? !!x === f.value : typeof f.value === 'number' ? Number(x) === f.value : String(x).toLowerCase() === String(f.value).toLowerCase()
      if (x == null) return false
      return { '<': x < f.value, '<=': x <= f.value, '>': x > f.value, '>=': x >= f.value }[f.op]
    })
  }
  const k = spec.sort.field
  out = [...out].sort((a, b) => (spec.sort.desc ? val(b, k) - val(a, k) : val(a, k) - val(b, k)))
  return out.slice(0, spec.limit)
}
