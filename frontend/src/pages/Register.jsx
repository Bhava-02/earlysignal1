import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { BY_ID, DEPTS, MENTORS } from '../lib/data'
import { createAccount, emailTaken, usernameTaken } from '../lib/auth'
import { AuthFrame } from './Login'

const ROLES = [
  ['admin', 'Admin'], ['principal', 'Principal'], ['hod', 'Head of department (HOD)'], ['mentor', 'Class mentor'], ['student', 'Student'],
]

export default function Register() {
  const nav = useNavigate()
  const g = useLocation().state?.google
  const [f, setF] = useState({ name: g?.name || '', phone: '', email: g?.email || '', kind: '', dept: '', mentor: '', roll: '', username: '', password: '', confirm: '' })
  const [errs, setErrs] = useState({})
  const set = (k) => (e) => {
    const v = e.target.value
    setF((x) => ({ ...x, [k]: v, ...(k === 'kind' ? { dept: '', mentor: '', roll: '' } : {}), ...(k === 'dept' ? { mentor: '' } : {}) }))
    setErrs((x) => ({ ...x, [k]: undefined }))
  }

  const validate = () => {
    const e = {}
    if (f.name.trim().length < 3) e.name = 'Enter your full name.'
    const digits = f.phone.replace(/\D/g, '')
    if (!/^(91)?[6-9]\d{9}$/.test(digits)) e.phone = 'Enter a 10-digit mobile number.'
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(f.email.trim())) e.email = 'Enter a valid email address.'
    else if (emailTaken(f.email)) e.email = 'An account with this email already exists.'
    if (!f.kind) e.kind = 'Choose your role.'
    if ((f.kind === 'hod' || f.kind === 'mentor') && !f.dept) e.dept = 'Choose your department.'
    if (f.kind === 'mentor' && !f.mentor) e.mentor = 'Choose your name from the faculty list.'
    if (f.kind === 'student') {
      if (!BY_ID[f.roll.trim().toUpperCase()]) e.roll = 'This roll number is not in the college records.'
    }
    if (!/^[A-Za-z0-9._-]{4,30}$/.test(f.username.trim())) e.username = 'Use 4 to 30 letters, numbers, dots, dashes or underscores.'
    else if (usernameTaken(f.username)) e.username = 'This username is already taken.'
    if (f.password.length < 8 || !/[A-Za-z]/.test(f.password) || !/\d/.test(f.password)) e.password = 'Use at least 8 characters, with letters and numbers.'
    if (f.confirm !== f.password) e.confirm = 'The passwords do not match.'
    return e
  }
  const submit = (ev) => {
    ev.preventDefault()
    const e = validate()
    setErrs(e)
    if (Object.keys(e).length) return
    const acc = createAccount({ ...f, mentor: f.kind === 'mentor' ? f.mentor : undefined, dept: f.kind === 'hod' || f.kind === 'mentor' ? f.dept : undefined })
    nav('/', { replace: true, state: { created: acc.username } })
  }
  const E = ({ k }) => (errs[k] ? <span className="hint" style={{ color: 'var(--hi-fg)' }}>{errs[k]}</span> : null)
  const linked = f.kind === 'student' ? BY_ID[f.roll.trim().toUpperCase()] : null

  return (
    <AuthFrame wide>
      <h1>Create an account</h1>
      <p className="muted small" style={{ marginTop: 4 }}>After you create your account you will be taken to the sign-in page.</p>
      {g && <p className="ok" style={{ marginTop: 12 }}>Signed in to Google as {g.email}. Finish your account below; after that, Continue with Google signs you in.</p>}
      <form onSubmit={submit} noValidate>
        <label className="f">Full name<input type="text" value={f.name} onChange={set('name')} autoComplete="name" /><E k="name" /></label>
        <div className="two">
          <label className="f">Phone number<input type="tel" value={f.phone} onChange={set('phone')} autoComplete="tel" placeholder="10-digit mobile number" /><E k="phone" /></label>
          <label className="f">Email<input type="email" value={f.email} onChange={set('email')} autoComplete="email" /><E k="email" /></label>
        </div>
        <label className="f">Role
          <select value={f.kind} onChange={set('kind')}>
            <option value="">Choose a role</option>
            {ROLES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <E k="kind" />
        </label>
        {(f.kind === 'hod' || f.kind === 'mentor') && (
          <div className="two">
            <label className="f">Department
              <select value={f.dept} onChange={set('dept')}>
                <option value="">Choose a department</option>
                {DEPTS.map((d) => <option key={d.code} value={d.code}>{d.code}, {d.name}</option>)}
              </select>
              <E k="dept" />
            </label>
            {f.kind === 'mentor' && (
              <label className="f">Your name in the faculty list
                <select value={f.mentor} onChange={set('mentor')} disabled={!f.dept}>
                  <option value="">{f.dept ? 'Choose your name' : 'Choose a department first'}</option>
                  {MENTORS.filter((m) => m.dept === f.dept).map((m) => <option key={m.name} value={m.name}>{m.name} ({m.students} students)</option>)}
                </select>
                <E k="mentor" />
              </label>
            )}
          </div>
        )}
        {f.kind === 'student' && (
          <label className="f">Roll number<input type="text" value={f.roll} onChange={set('roll')} placeholder="e.g. 23CS045" />
            {linked ? <span className="hint">Linked to {linked.name}, {linked.dept} year {linked.year}</span> : <E k="roll" />}
          </label>
        )}
        <label className="f">Username<input type="text" value={f.username} onChange={set('username')} autoComplete="username" /><E k="username" /></label>
        <div className="two">
          <label className="f">Password<input type="password" value={f.password} onChange={set('password')} autoComplete="new-password" /><E k="password" /></label>
          <label className="f">Confirm password<input type="password" value={f.confirm} onChange={set('confirm')} autoComplete="new-password" /><E k="confirm" /></label>
        </div>
        <button type="submit" className="btn primary">Create account</button>
      </form>
      <div className="auth-alt">Already have an account? <Link to="/">Sign in</Link></div>
    </AuthFrame>
  )
}
