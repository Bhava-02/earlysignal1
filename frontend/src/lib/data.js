// Everything the app shows comes from one data file written by the Round 1 pipeline (src/web_export_r1.py).
// The single-file build carries it inside; the server build fetches the latest copy from the server at start-up
// (main.jsx calls setData before the app is drawn), so an upload or a sync shows on every page.
import bundle from '@bundle'
import { createModel } from './model'

export let B = null
export let META = null
export let STUDENTS = []
export let BY_ID = {}
export let DEPTS = []
export let DEPT_NAME = {}
export let MENTORS = []
export let SEG = {}
export let MODEL = null

export function setData(b) {
  B = b
  META = b.meta
  STUDENTS = b.students
  BY_ID = Object.fromEntries(STUDENTS.map((s) => [s.id, s]))
  DEPTS = META.depts
  DEPT_NAME = Object.fromEntries(DEPTS.map((d) => [d.code, d.name]))
  MENTORS = META.mentors
  SEG = Object.fromEntries(B.segments.map((g) => [g.name, g]))
  MODEL = createModel(b)
}
export const hasData = () => !!B
if (bundle && bundle.meta) setData(bundle)

export const RISK_WORD = { High: 'At Risk', Medium: 'Moderate', Low: 'Low Risk', 'Pre-placement': 'Pre-placement' }

// Display names for the seven groups (as on the Round 1 segments page)
export const SEG_LOOK = {
  'Book-smart, Job-shy': ['High academic, low placement', 'cap', 'Strong marks but not yet ready for placements.'],
  'Critical: Act This Week': ['High risk: act this week', 'alert', 'Several warning signs at once, in studies and attendance.'],
  'Silent Strugglers': ['Hidden strugglers', 'search', 'Marks look fine, but logins, assignments or attendance are falling.'],
  'Academic Catch-up': ['Needs academic support', 'book', 'Low CGPA, arrears or low internal marks.'],
  'Busy but Slipping': ['High engagement, low academics', 'calendar', 'Very active in events while academics fall behind.'],
  'Placement-Ready Stars': ['Placement ready', 'star', 'Strong profile, ready for placements. Good peer mentors.'],
  'Steady Middle': ['Steady', 'check', 'No urgent flags. Regular check-ins keep them on track.'],
}
export const SEG_ORDER = ['Book-smart, Job-shy', 'Critical: Act This Week', 'Silent Strugglers', 'Academic Catch-up',
  'Busy but Slipping', 'Placement-Ready Stars', 'Steady Middle']
export const SEG_SHORT = {
  'Critical: Act This Week': 'Act this week', 'Silent Strugglers': 'Hidden struggler', 'Busy but Slipping': 'Busy but slipping',
  'Academic Catch-up': 'Academic catch-up', 'Book-smart, Job-shy': 'Good marks, not job-ready',
  'Placement-Ready Stars': 'Ready and thriving', 'Steady Middle': 'Steady',
}

// ---------------------------------------------------------------- who sees what
export const KIND_LABEL = { admin: 'Admin', principal: 'Principal', hod: 'Head of department', mentor: 'Class mentor', student: 'Student' }
const STAFF = ['admin', 'principal', 'hod', 'mentor']
const LEADS = ['admin', 'principal']
export const ACCESS = {
  '/': STAFF, '/students': STAFF, '/student': STAFF, '/analytics': STAFF, '/segments': STAFF, '/placement': STAFF,
  '/interventions': STAFF, '/assistant': STAFF, '/staff': ['admin', 'principal', 'hod'], '/sources': LEADS,
  '/quality': LEADS, '/how': STAFF,
}
export const can = (role, path) => !!role && (ACCESS[path] || []).includes(role.kind)
export const isLead = (role) => LEADS.includes(role?.kind)

export function scopeStudents(role) {
  if (!role) return []
  if (role.kind === 'hod') return STUDENTS.filter((s) => s.dept === role.dept)
  if (role.kind === 'mentor') return STUDENTS.filter((s) => s.mentor === role.mentor)
  if (role.kind === 'student') return STUDENTS.filter((s) => s.id === role.roll)
  return STUDENTS
}

export function scopeText(role) {
  if (!role) return 'the whole college'
  if (role.kind === 'hod') return `the ${role.dept} department`
  if (role.kind === 'mentor') return 'your mentees'
  return 'the whole college'
}

// localStorage only for this browser's conveniences (sign-in, created accounts, action log); always guarded
export const store = {
  get(key, fallback) {
    try {
      const v = window.localStorage.getItem(key)
      return v ? JSON.parse(v) : fallback
    } catch {
      return fallback
    }
  },
  set(key, value) {
    try {
      window.localStorage.setItem(key, JSON.stringify(value))
    } catch {
      /* private window or blocked storage: keep working without saving */
    }
  },
}

export const mean = (arr) => (arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0)
export function groupBy(arr, f) {
  const m = {}
  for (const x of arr) (m[f(x)] ||= []).push(x)
  return m
}
