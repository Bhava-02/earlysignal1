// Accounts: built-in demo staff accounts, one account per student (roll number), and accounts created on the
// Create account page (kept in this browser). Sign-in codes go to the account's real email (through the server) or
// phone (through Firebase) when those are set up; built-in demo accounts have no real email or phone, so their code
// is shown on screen.
import { BY_ID, DEPTS, KIND_LABEL, META, store } from './data'
import { config } from './server'

export const DOMAIN = 'college.edu.in'
export const adminEmail = () => config().adminEmail || `admin@${DOMAIN}`
export const STUDENT_PASSWORD = 'student123'
const HOD_NAMES = { CSE: 'Dr. R. Lakshmi', IT: 'Dr. A. Sundar', ECE: 'Dr. J. Srinivasan', MECH: 'Dr. S. Murugan' }

export function mentorUsername(name) {
  const parts = name.replace(/^(Dr|Prof|Mr|Ms|Mrs)\.?\s+/i, '').split(/\s+/)
  const first = parts[0].replace(/[^A-Za-z]/g, '').toLowerCase()
  const rest = parts.slice(1).join('').replace(/[^A-Za-z]/g, '').toLowerCase()
  return `${first}${rest ? `.${rest}` : ''}`
}
const phone = (n) => `98400${String(10000 + n).slice(-5)}`

// Built-in accounts (passwords are demo passwords). Built from the current data, so they follow an upload.
let builtCache = { meta: null, list: [] }
export function builtIn() {
  if (builtCache.meta !== META) builtCache = { meta: META, list: makeBuiltIn() }
  return builtCache.list
}
const makeBuiltIn = () => [
  { username: 'admin', email: `admin@${DOMAIN}`, phone: phone(1), pw: 'admin123', name: 'Administrator', kind: 'admin' },
  { username: 'principal', email: `principal@${DOMAIN}`, phone: phone(2), pw: 'principal123', name: 'Dr. V. Rajendran', kind: 'principal' },
  ...DEPTS.map((d, i) => ({
    username: `hod.${d.code.toLowerCase()}`, email: `hod.${d.code.toLowerCase()}@${DOMAIN}`, phone: phone(10 + i), pw: 'hod123',
    name: HOD_NAMES[d.code] || `Head of ${d.code}`, kind: 'hod', dept: d.code,
  })),
  ...META.mentors.map((m, i) => ({
    username: mentorUsername(m.name), email: `${mentorUsername(m.name)}@${DOMAIN}`, phone: phone(100 + i), pw: 'faculty123',
    name: m.name, kind: 'mentor', mentor: m.name, dept: m.dept,
  })),
].map((u) => ({ ...u, builtIn: true }))

export const created = () => store.get('es.accounts', [])

function studentAccount(roll) {
  const s = BY_ID[roll.toUpperCase()]
  if (!s) return null
  return { username: s.id, email: `${s.id.toLowerCase()}@${DOMAIN}`, phone: '', pw: STUDENT_PASSWORD, name: s.name, kind: 'student', roll: s.id, dept: s.dept, builtIn: true }
}

// Simple one-way hash so created passwords are not stored as typed (demo only).
export function hash(text) {
  let h1 = 0xdeadbeef ^ text.length
  let h2 = 0x41c6ce57 ^ text.length
  for (let i = 0; i < text.length; i++) {
    const c = text.charCodeAt(i)
    h1 = Math.imul(h1 ^ c, 2654435761)
    h2 = Math.imul(h2 ^ c, 1597334677)
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909)
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909)
  return (4294967296 * (2097151 & h2) + (h1 >>> 0)).toString(36)
}

export function findAccount(login) {
  const id = login.trim().toLowerCase()
  if (!id) return null
  const mine = created().find((u) => u.username.toLowerCase() === id || u.email.toLowerCase() === id)
  if (mine) return mine
  const b = builtIn().find((u) => u.username === id || u.email === id)
  if (b) return b
  const roll = id.endsWith(`@${DOMAIN}`) ? id.split('@')[0] : id
  return studentAccount(roll)
}

// The account that uses this (Google) email, if any. Only created accounts carry real emails.
export function findAccountByEmail(email) {
  const e = (email || '').trim().toLowerCase()
  if (!e) return null
  return created().find((u) => u.email.toLowerCase() === e) || null
}

// Built-in demo accounts have made-up emails and phones, so codes for them are never sent anywhere.
export const realContact = (u) => !u.builtIn

export function checkPassword(u, pw) {
  return u.pwHash ? u.pwHash === hash(`${u.username.toLowerCase()}:${pw}`) : u.pw === pw
}

export const needsOtp = (u) => u.kind !== 'student'

// What the app keeps about the signed-in user (never the password)
export function session(u) {
  const title = u.kind === 'hod' ? `Head of department, ${u.dept}` : u.kind === 'mentor' ? `Class mentor, ${u.dept}`
    : u.kind === 'student' ? `Student, ${u.dept}` : KIND_LABEL[u.kind]
  return { username: u.username, name: u.name, kind: u.kind, dept: u.dept, mentor: u.mentor, roll: u.roll, title, email: u.email }
}

export function usernameTaken(name) {
  const id = name.trim().toLowerCase()
  return !!(created().some((u) => u.username.toLowerCase() === id) || builtIn().some((u) => u.username === id) || BY_ID[id.toUpperCase()])
}
export function emailTaken(email) {
  const e = email.trim().toLowerCase()
  return created().some((u) => u.email.toLowerCase() === e) || builtIn().some((u) => u.email === e)
}

export function createAccount(a) {
  const list = created()
  const acc = {
    username: a.username.trim(), email: a.email.trim().toLowerCase(), phone: a.phone.replace(/\D/g, '').slice(-10), name: a.name.trim(),
    kind: a.kind, dept: a.dept || undefined, mentor: a.mentor || undefined, roll: a.roll ? a.roll.toUpperCase() : undefined,
    pwHash: hash(`${a.username.trim().toLowerCase()}:${a.password}`), createdAt: new Date().toISOString(),
  }
  if (acc.kind === 'student' && acc.roll) acc.dept = BY_ID[acc.roll]?.dept
  list.push(acc)
  store.set('es.accounts', list)
  return acc
}

export function allAccounts() {
  return [...builtIn(), ...created()]
}

export const maskPhone = (p) => (p ? `+91 ${'•'.repeat(6)}${p.slice(-4)}` : '')
export const e164 = (p) => `+91${String(p).replace(/\D/g, '').slice(-10)}`
export function maskEmail(e) {
  const [a, b] = e.split('@')
  return `${a.slice(0, 2)}${'•'.repeat(Math.max(2, a.length - 2))}@${b}`
}
export const newOtp = () => String(Math.floor(100000 + Math.random() * 900000))
