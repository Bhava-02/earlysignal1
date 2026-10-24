import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { META } from '../lib/data'
import { checkPassword, e164, findAccount, findAccountByEmail, maskEmail, maskPhone, needsOtp, newOtp, realContact, session } from '../lib/auth'
import { confirmSms, firebaseMessage, firebaseReady, googleSignIn, sendSms } from '../lib/firebase'
import { api, server } from '../lib/server'
import { useRole } from '../lib/role'
import { Icon, Mark } from '../components/ui'

const DEMO_MINUTES = 5
const MAX_TRIES = 5
const RESEND = 30

export function AuthFrame({ children, wide }) {
  return (
    <div className="auth">
      <header className="auth-top"><span className="logo-tile sm"><Mark size={18} /></span><b>EarlySignal</b><span>{META.college}</span></header>
      <main className="auth-main"><div className={`auth-card ${wide ? 'wide' : ''}`}>{children}</div></main>
      <footer className="auth-foot">{META.college}. Student success portal. For authorised staff and students only.</footer>
      <div id="recaptcha-box" />
    </div>
  )
}

export function GoogleButton({ onClick, busy, label = 'Continue with Google' }) {
  return (
    <button type="button" className="btn google" onClick={onClick} disabled={busy}>
      {busy ? 'Opening Google...' : label}
    </button>
  )
}

// Second step for staff: a one-time code by email or SMS (or on screen for demo accounts / when nothing is set up).
function Verify({ user, onDone, onBack }) {
  const channels = []
  if (realContact(user)) {
    if (server()?.email_codes && user.email) channels.push('email')
    if (firebaseReady() && user.phone) channels.push('sms')
  }
  const demo = channels.length === 0
  const [sent, setSent] = useState(null) // { kind, at, challenge?, handle?, code?, expires? }
  const [code, setCode] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState('')
  const [tries, setTries] = useState(0)
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [])

  const send = async (kind) => {
    setErr(''); setCode(''); setBusy(kind); setTries(0)
    const at = Date.now()
    setNow(at)
    try {
      if (kind === 'demo') {
        setSent({ kind, at, code: newOtp(), expires: at + DEMO_MINUTES * 60000 })
      } else if (kind === 'email') {
        const r = await api('otp/email', { method: 'POST', body: { email: user.email, name: user.name } })
        setSent({ kind, at, challenge: r.challenge, expires: at + r.minutes * 60000 })
      } else {
        const handle = await sendSms(e164(user.phone), 'recaptcha-box')
        setSent({ kind, at, handle })
      }
    } catch (e) {
      setErr(kind === 'sms' ? firebaseMessage(e) : e.message)
    }
    setBusy('')
  }
  useEffect(() => { if (demo) send('demo') }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const wrong = (left) => {
    if (left <= 0) {
      setSent(null)
      setErr('Too many incorrect codes. Ask for a new code.')
      return
    }
    setErr(`That code is not correct. ${left} attempt${left === 1 ? '' : 's'} left.`)
  }
  const verify = async (e) => {
    e.preventDefault()
    setErr('')
    if (sent.expires && Date.now() > sent.expires) { setErr('This code has expired. Send a new code.'); return }
    setBusy('verify')
    try {
      if (sent.kind === 'demo') {
        if (code === sent.code) { onDone(); return }
        const t = tries + 1
        setTries(t)
        wrong(MAX_TRIES - t)
      } else if (sent.kind === 'email') {
        const r = await api('otp/verify', { method: 'POST', body: { challenge: sent.challenge, code } })
        if (r.ok) { onDone(); return }
        if (r.reason === 'wrong') wrong(r.left)
        else { setSent(null); setErr(r.reason === 'locked' ? 'Too many incorrect codes. Ask for a new code.' : 'This code has expired. Send a new code.') }
      } else {
        const phone = await confirmSms(sent.handle, code)
        if (phone.replace(/\D/g, '').slice(-10) === String(user.phone).replace(/\D/g, '').slice(-10)) { onDone(); return }
        setErr('That phone number does not belong to this account.')
      }
    } catch (ex) {
      if (sent.kind === 'sms') {
        if (ex?.code === 'auth/invalid-verification-code') { const t = tries + 1; setTries(t); wrong(MAX_TRIES - t) } else setErr(firebaseMessage(ex))
      } else setErr(ex.message)
    }
    setBusy('')
  }

  const where = (k) => (k === 'email' ? maskEmail(user.email) : maskPhone(user.phone))
  const wait = sent ? Math.max(0, RESEND - Math.floor((now - sent.at) / 1000)) : 0
  const left = sent?.expires ? Math.max(0, Math.floor((sent.expires - now) / 1000)) : null
  const other = sent && channels.find((k) => k !== sent.kind)
  return (
    <>
      <h1>Verify it's you</h1>
      {!sent && !demo && (
        <>
          <p className="muted small" style={{ marginTop: 4 }}>Choose where to get a 6-digit sign-in code.</p>
          <div className="channels" style={{ marginTop: 18 }}>
            {channels.map((k) => (
              <button key={k} type="button" className="channel" onClick={() => send(k)} disabled={!!busy}>
                <span className="ic"><Icon name={k === 'email' ? 'mail' : 'phone'} size={18} /></span>
                <span><b>{busy === k ? 'Sending...' : k === 'email' ? 'Email me a code' : 'Text me a code'}</b>{where(k)}</span>
              </button>
            ))}
          </div>
          {err && <div className="err" role="alert" style={{ marginTop: 14 }}>{err}</div>}
        </>
      )}
      {sent && (
        <>
          <p className="muted small" style={{ marginTop: 4 }}>
            {sent.kind === 'demo' ? 'Enter the 6-digit sign-in code.' : `We sent a 6-digit code to ${where(sent.kind)}.`}
          </p>
          <form onSubmit={verify} noValidate>
            {sent.kind === 'demo' && (
              <div className="demo-code">
                {realContact(user) ? 'Codes by email and SMS are not set up on this copy, so your code is shown here: '
                  : 'This is a built-in demo account with no real email or phone, so your code is shown here: '}<b>{sent.code}</b>
              </div>
            )}
            <label className="f">One-time code
              <input className="otp" type="text" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} autoFocus
                onChange={(e) => { setCode(e.target.value.replace(/\D/g, '')); setErr('') }} />
            </label>
            {left != null && <div className="hint">{left > 0 ? `Code expires in ${Math.floor(left / 60)}:${String(left % 60).padStart(2, '0')}` : 'Code expired'}</div>}
            {err && <div className="err" role="alert">{err}</div>}
            <button type="submit" className="btn primary" disabled={code.length !== 6 || busy === 'verify'}>{busy === 'verify' ? 'Checking...' : 'Verify and sign in'}</button>
          </form>
        </>
      )}
      {demo && !sent && err && <div className="err" role="alert" style={{ marginTop: 14 }}>{err}</div>}
      <div className="auth-alt row wrap" style={{ justifyContent: 'space-between', gap: 8 }}>
        {sent && <button type="button" className="link-btn" disabled={wait > 0 || !!busy} onClick={() => send(sent.kind)}>{wait > 0 ? `Send a new code in ${wait}s` : 'Send a new code'}</button>}
        {other && <button type="button" className="link-btn" onClick={() => { setSent(null); setErr('') }}>{other === 'email' ? 'Get the code by email instead' : 'Get the code by SMS instead'}</button>}
        <button type="button" className="link-btn" onClick={onBack}>Use a different account</button>
      </div>
    </>
  )
}

export default function Login() {
  const { setRole } = useRole()
  const loc = useLocation()
  const nav = useNavigate()
  const createdName = loc.state?.created
  const [login, setLogin] = useState(createdName || '')
  const [pw, setPw] = useState('')
  const [show, setShow] = useState(false)
  const [err, setErr] = useState('')
  const [help, setHelp] = useState(false)
  const [verifyFor, setVerifyFor] = useState(null)
  const [noAccount, setNoAccount] = useState(null)
  const [gBusy, setGBusy] = useState(false)

  const proceed = (u) => (needsOtp(u) ? setVerifyFor(u) : setRole(session(u)))
  const signIn = (e) => {
    e.preventDefault()
    if (!login.trim() || !pw) { setErr('Enter your username and password.'); return }
    const u = findAccount(login)
    if (!u || !checkPassword(u, pw)) { setErr('The username or password is incorrect.'); return }
    proceed(u)
  }
  const google = async () => {
    setErr('')
    if (!firebaseReady()) {
      setErr('Continue with Google is not switched on for this copy yet. The admin adds the Firebase settings to the server (see the setup guide).')
      return
    }
    setGBusy(true)
    try {
      const g = await googleSignIn()
      const u = findAccountByEmail(g.email)
      if (u) proceed(u)
      else setNoAccount(g)
    } catch (ex) {
      setErr(firebaseMessage(ex))
    }
    setGBusy(false)
  }
  const back = () => { setVerifyFor(null); setNoAccount(null); setPw(''); setErr('') }

  if (verifyFor) {
    return <AuthFrame><Verify user={verifyFor} onDone={() => setRole(session(verifyFor))} onBack={back} /></AuthFrame>
  }
  if (noAccount) {
    return (
      <AuthFrame>
        <h1>No account for this Google email</h1>
        <p className="muted small" style={{ marginTop: 6 }}>You signed in to Google as <b className="ink">{noAccount.email}</b>, but no EarlySignal account uses this email yet.</p>
        <div className="stack" style={{ gap: 10, marginTop: 20 }}>
          <button type="button" className="btn primary" style={{ height: 38 }} onClick={() => nav('/register', { state: { google: noAccount } })}>Create an account with this email</button>
          <button type="button" className="btn" style={{ height: 38 }} onClick={back}>Back to sign in</button>
        </div>
      </AuthFrame>
    )
  }
  return (
    <AuthFrame>
      <h1>Sign in</h1>
      <p className="muted small" style={{ marginTop: 4 }}>Use your username and password, or your Google account. Staff confirm with a one-time code.</p>
      <div style={{ marginTop: 20 }}><GoogleButton onClick={google} busy={gBusy} /></div>
      <div className="or">or</div>
      <form onSubmit={signIn} noValidate style={{ marginTop: 0 }}>
        {createdName && !err && <div className="ok" role="status">Account created. Sign in with your username and password.</div>}
        <label className="f">Username
          <input type="text" value={login} onChange={(e) => { setLogin(e.target.value); setErr('') }} autoComplete="username" autoFocus={!createdName} />
          <span className="hint">Your username, college email, or roll number for students</span>
        </label>
        <label className="f">Password
          <div className="pw">
            <input type={show ? 'text' : 'password'} value={pw} onChange={(e) => { setPw(e.target.value); setErr('') }} autoComplete="current-password" autoFocus={!!createdName} />
            <button type="button" className="link-btn" onClick={() => setShow((x) => !x)} aria-label={show ? 'Hide password' : 'Show password'}>{show ? 'Hide' : 'Show'}</button>
          </div>
        </label>
        {err && <div className="err" role="alert">{err}</div>}
        <button type="submit" className="btn primary">Sign in</button>
      </form>
      <div style={{ marginTop: 14, fontSize: 13 }}>
        <button type="button" className="link-btn" onClick={() => setHelp((x) => !x)} aria-expanded={help}>Forgot your password?</button>
        {help && <p className="muted" style={{ marginTop: 6 }}>Ask the college IT helpdesk or the admin to reset it.</p>}
      </div>
      <div className="auth-alt">New here? <Link to="/register">Create an account</Link></div>
    </AuthFrame>
  )
}
