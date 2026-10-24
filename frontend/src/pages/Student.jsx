import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { B, BY_ID, META, MODEL, RISK_WORD, scopeStudents, SEG_SHORT } from '../lib/data'
import { logActions, useActions } from '../lib/actions'
import { num, pct } from '../lib/format'
import { useRole } from '../lib/role'
import { COL, Columns, HBars } from '../components/charts'
import { Avatar, Card, Icon, Kvl, Meter, Pill, Ring, RiskPill, Stat, Tabs } from '../components/ui'

const ACTIONS = ['Mentor meeting', 'Remedial classes', 'Peer tutoring', 'Counselling referral', 'Parent call', 'Mock interview drive', 'Coding practice track', 'Other']
const PLACE_PILL = { High: 'p-high', Medium: 'p-med', Low: 'p-grey' }

function Overview({ s, self, res, onPlan, planned }) {
  const sheet = useMemo(() => MODEL.marksheet(s), [s])
  const [all, setAll] = useState(false)
  const total = sheet.reduce((a, r) => a + r.marks, 0)
  const lost = [...sheet].sort((a, b) => (b.outOf - b.marks) - (a.outOf - a.marks)).slice(0, 3)
  const items = [
    ['CGPA', s.v.cgpa.toFixed(2)], ['Attendance', `${Math.round(s.v.att_pct)}%`], ['Standing arrears', Math.round(s.v.backlogs)],
    ['LMS logins per week', s.v.lms_avg.toFixed(1)], ['Assignments submitted', pct(s.v.asg_rate)], ['Placement readiness', `${Math.round(s.v.placement)} / 100`],
    ...(self ? [] : [['Chance of failing a subject', pct(Math.min(s.v.acad_prob, 0.99))]]),
  ]
  const steps = res.steps.slice(0, 2)
  const first = res.steps[0] || 'Keep doing what works; consider them as a peer mentor.'
  return (
    <div className="stack">
      <div className="grid g3">
        <Card title="Key information"><Kvl items={items} /></Card>
        <Card title={`How the score of ${Math.round(s.v.success_score)} is made`} sub="Like a marksheet out of 100. Each item has maximum marks; marks depend on how good that item is.">
          {['Academics', 'Engagement', 'Placement readiness'].map((part) => {
            const g = sheet.filter((r) => r.part === part)
            const got = g.reduce((a, r) => a + r.marks, 0)
            const out = g.reduce((a, r) => a + r.outOf, 0)
            return (
              <div key={part} style={{ marginBottom: 10 }}>
                <div className="row small" style={{ marginBottom: 4 }}><span className="strong">{part}</span><span className="spacer" /><span className="num"><b className="ink">{got.toFixed(1)}</b> / {out.toFixed(0)}</span></div>
                <Meter value={out ? (100 * got) / out : 0} />
              </div>
            )
          })}
          <div className="kvl" style={{ borderTop: '1px solid var(--line)', marginTop: 4 }}><span className="strong">Success Score</span><span>{total.toFixed(0)} / 100</span></div>
          <div className="small strong" style={{ marginTop: 10 }}>Most marks lost on</div>
          {lost.map((r) => <div key={r.key} className="kvl small"><span>{r.item} <span className="muted">({r.value})</span></span><span>{r.marks.toFixed(1)} of {r.outOf.toFixed(1)}</span></div>)}
          <button type="button" className="link-btn small" style={{ marginTop: 8 }} onClick={() => setAll((x) => !x)}>{all ? 'Hide the full marksheet' : 'See the full marksheet'}</button>
        </Card>
        <div className="stack" style={{ gap: 12 }}>
          <Card title={self ? 'Areas to work on' : 'Why this student is flagged'}>
            <ul className="reasons">{(s.reasons.length ? s.reasons : ['No strong academic warning signs this week.']).map((r) => <li key={r}>{r}</li>)}</ul>
            {steps.length > 0 && <>
              <div className="small strong" style={{ marginTop: 12 }}>Suggested first steps</div>
              <ol className="steps">{steps.map((t) => <li key={t}><span className="small">{t}</span></li>)}</ol>
            </>}
          </Card>
          {s.year >= 3 && s.preasons.length > 0 && (
            <Card title="Placement gaps"><ul className="reasons">{s.preasons.map((r) => <li key={r}>{r}</li>)}</ul></Card>
          )}
        </div>
      </div>
      {all && (
        <Card title="Full marksheet" sub="Between zero marks and full marks, the marks go up evenly. Example: CGPA 5.0 gets 0, CGPA 9.5 gets full marks, and CGPA 7.25 gets half." flush>
          <div className="table-wrap">
            <table className="list">
              <thead><tr><th>Part</th><th>Item</th><th>This student</th><th>Zero marks at</th><th>Full marks at</th><th className="r">Marks</th><th className="r">Out of</th></tr></thead>
              <tbody>{sheet.map((r) => <tr key={r.key}><td className="small">{r.part}</td><td>{r.item}</td><td>{r.value}</td><td className="small">{r.zero}</td><td className="small">{r.full}</td><td className="r num strong">{r.marks.toFixed(1)}</td><td className="r num">{r.outOf.toFixed(1)}</td></tr>)}</tbody>
            </table>
          </div>
        </Card>
      )}
      {!self && (
        <div className="note row wrap" style={{ gap: 14 }}>
          <div style={{ flex: 1, minWidth: 240 }}><div className="strong">Recommended action</div><div className="small">Mentor meeting this week. {first}</div></div>
          <button type="button" className="btn primary" disabled={planned} onClick={onPlan}>{planned ? 'Action plan saved' : 'Create action plan'}</button>
        </div>
      )}
      {planned && !self && <p className="ok">Action plan saved. Follow it up on the Interventions page; see the full plan in the Action plan tab.</p>}
    </div>
  )
}

function Academic({ s }) {
  const sg = s.sgpa.map(([sem, v, ra]) => ({ sem: `Sem ${sem}`, sgpa: v, label: `${v.toFixed(1)}${ra ? ` (${ra} RA)` : ''}` }))
  return (
    <div className="grid g-main">
      <Card title="This semester's subjects" flush>
        <div className="table-wrap">
          <table className="list">
            <thead><tr><th>Subject</th><th className="r">Internal test (CIA-1, out of 50)</th><th style={{ width: '34%' }}>Attendance</th></tr></thead>
            <tbody>
              {s.subj.map(([code, name, cia, abs, att]) => (
                <tr key={code}><td>{name}<div className="tiny">{code}</div></td><td className="r num">{abs ? 'Absent' : cia == null ? '' : cia}</td>
                  <td><div className="row" style={{ gap: 8 }}><div style={{ flex: 1 }}><Meter value={att ?? 0} /></div><span className="num small" style={{ width: 36, textAlign: 'right' }}>{att == null ? '' : `${att}%`}</span></div></td></tr>
              ))}
            </tbody>
          </table>
          {s.subj.length === 0 && <p className="empty">No subjects recorded this semester.</p>}
        </div>
      </Card>
      <Card title="GPA by semester" foot={`CGPA ${s.v.cgpa.toFixed(2)}, standing arrears ${Math.round(s.v.backlogs)}. RA means re-appear (failed).`}>
        {sg.length ? <Columns data={sg} x="sem" series={[{ key: 'sgpa', name: 'SGPA', color: COL.c1 }]} fmt={(v) => Number(v).toFixed(2)} yfmt={(v) => v}
          domain={[0, 10]} labels labelKey="label" height={250} /> : <p className="empty">No finished semester yet.</p>}
      </Card>
    </div>
  )
}

function weekRows(s, key) {
  const now = s.wk.now?.[key] || []
  const last = s.wk.last?.[key] || []
  return Array.from({ length: META.weeks }, (_, i) => ({ week: i + 1, now: now[i] ?? null, last: last[i] ?? null }))
}
const WEEK_SERIES = [{ key: 'last', name: 'Last semester', color: COL.c3 }, { key: 'now', name: 'This semester', color: COL.c1 }]

function Attendance({ s }) {
  const need = s.v.required_rate_for_75
  const best = MODEL.projAtt(s, 1)
  return (
    <div className="grid g-main">
      <Card title="Attendance week by week" sub="This semester beside the same week last semester">
        <Columns data={weekRows(s, 'att')} x="week" xfmt={(w) => `Wk ${w}`} series={WEEK_SERIES} fmt={(v) => `${v}%`} domain={[0, 100]}
          refY={75} refLabel="75%" height={260} title={(l) => `Week ${l}`} />
      </Card>
      <Card title="Exam eligibility">
        <Kvl items={[['Attendance so far', `${Math.round(s.v.att_pct)}%`], ['Last 4 weeks', `${Math.round(s.v.att_recent)}%`],
          ['Projected at semester end', `${Math.round(s.v.projected_attendance)}%`], ['Needed to write exams', `${META.attendance_min}%`]]} />
        <div style={{ marginTop: 12 }}>
          {s.v.projected_attendance >= META.attendance_min ? <p className="ok">On track to stay eligible.</p>
            : need <= 100 ? <p className="warn">Must attend at least {Math.round(Math.max(need, 0))}% of the remaining classes to stay eligible.</p>
              : <p className="err">Cannot reach 75% even with full attendance (best case {Math.round(best)}%). Start the condonation or medical-leave process now.</p>}
        </div>
      </Card>
    </div>
  )
}

function Lms({ s }) {
  return (
    <div className="stack">
      <div className="grid g2">
        <Card title="LMS logins per week">
          <Columns data={weekRows(s, 'logins')} x="week" xfmt={(w) => `Wk ${w}`} series={WEEK_SERIES} fmt={(v) => Number(v).toFixed(0)} height={240} title={(l) => `Week ${l}`} />
        </Card>
        <Card title="Assignments submitted (of 2 a week)">
          <Columns data={weekRows(s, 'asg')} x="week" xfmt={(w) => `Wk ${w}`} series={WEEK_SERIES} fmt={(v) => Number(v).toFixed(0)} domain={[0, 2]} height={240} title={(l) => `Week ${l}`} />
        </Card>
      </div>
      <p className="tiny">LMS activity changed {s.v.lms_change > 0 ? '+' : ''}{Math.round(100 * s.v.lms_change)}% over the last 3 weeks; assignment completion {s.v.asg_change > 0 ? '+' : ''}{Math.round(100 * s.v.asg_change)} points.</p>
    </div>
  )
}

function Engagement({ s }) {
  return (
    <div className="grid g-main">
      <Card title="Activity this year">
        <Kvl items={[['Events and clubs', Math.round(s.v.activities)], ['Hackathons', Math.round(s.v.hackathons || 0)], ['Certifications', Math.round(s.v.certifications)],
          ['Satisfaction (survey, 1 to 5)', s.miss.satisfaction_missing ? 'No response' : s.v.satisfaction.toFixed(1)], ['Engagement score', `${Math.round(s.v.engagement)} / 100`]]} />
      </Card>
      <Card title="Events attended" flush>
        {s.ev.length ? (
          <div className="table-wrap" style={{ maxHeight: 300 }}>
            <table className="list"><thead><tr><th>Month</th><th>Type</th><th>Event</th></tr></thead>
              <tbody>{s.ev.map(([m, t, n], i) => <tr key={i}><td className="num">{m}</td><td>{t}</td><td>{n}</td></tr>)}</tbody></table>
          </div>
        ) : <p className="empty">No events recorded in the last 12 months.</p>}
      </Card>
    </div>
  )
}

function Placement({ s, self }) {
  if (s.year < 3) return <p className="note">Placement readiness is tracked from 3rd year. Early indicators: aptitude {Math.round(s.v.best_aptitude)}, technical skills {Math.round(s.v.technical_score)}.</p>
  const pa = B.placement.placed_avg
  const items = [['Aptitude', s.v.best_aptitude, pa.best_aptitude, 100], ['Coding', s.v.best_coding, pa.best_coding, 100],
    ['Soft skills', s.v.soft_skill_score, pa.soft_skill_score, 100], ['Mock interviews', s.v.mock_interviews, pa.mock_interviews, 5]]
    .map(([name, you, sen, max]) => ({ name, you: Math.round((100 * you) / max), seniors: Math.round((100 * sen) / max), yr: you, sr: sen }))
  return (
    <div className="grid g-main">
      <Card title="Compared with seniors who got placed" sub="Mock interviews are shown out of 5, scores out of 100">
        <HBars data={items} y="name" yWidth={120} domain={[0, 100]}
          fmt={(v, p, k) => (p && typeof p === 'object' ? Number(k === 'you' ? p.yr : p.sr).toFixed(p.name === 'Mock interviews' ? 1 : 0) : `${v}`)}
          series={[{ key: 'seniors', name: 'Placed seniors (average)', color: COL.c3 }, { key: 'you', name: self ? 'You' : 'This student', color: COL.c1 }]} />
      </Card>
      <Card title="Readiness">
        <Kvl items={[
          ...(self ? [] : [['Chance of getting placed', pct(s.v.placement_prob)]]),
          ['Placement readiness', RISK_WORD[s.pr] === 'Low Risk' ? 'Ready' : RISK_WORD[s.pr]],
          ['Eligible for most recruiters', s.v.eligible ? 'Yes' : 'No (CGPA or arrears)'], ['Mock interviews done', Math.round(s.v.mock_interviews)],
          ['Placement readiness score', `${Math.round(s.v.placement)} / 100`]]} />
      </Card>
    </div>
  )
}

function Skills({ s }) {
  return (
    <Card title="Skills test results">
      {[['technical_score', 'Technical skills'], ['soft_skill_score', 'Soft skills'], ['best_aptitude', 'Aptitude'], ['best_coding', 'Coding']]
        .filter(([k]) => !(k === 'best_coding' && s.year < 3)).map(([k, label]) => {
          const missing = s.miss[`${k}_missing`]
          return (
            <div key={k} style={{ marginBottom: 12 }}>
              <div className="row small" style={{ marginBottom: 4 }}><span>{label}</span><span className="spacer" /><b className="ink">{missing ? 'Not tested' : `${Math.round(s.v[k])} / 100`}</b></div>
              <Meter value={missing ? 0 : s.v[k]} />
            </div>
          )
        })}
    </Card>
  )
}

function Feedback({ s }) {
  return (
    <Card title="Faculty and student feedback">
      <Kvl items={[['Faculty participation rating (1 to 5)', s.v.faculty_rating?.toFixed(1)], ['Subjects rated 2 or below', Math.round(s.v.low_rating_subjects || 0)],
        ['Lowest faculty remark', s.remark || 'None'], ['Student satisfaction (1 to 5)', s.miss.satisfaction_missing ? 'No response' : s.v.satisfaction.toFixed(1)],
        ['Workload stress (1 to 5)', s.v.stress == null ? 'No response' : Math.round(s.v.stress)]]} />
    </Card>
  )
}

function guide(s, res) {
  const reasons = s.reasons.length ? s.reasons : ['no single strong warning sign']
  const declining = s.v.lms_change <= -0.25 || s.v.asg_change <= -0.2
  const opener = declining ? 'I noticed things have been a bit harder these last few weeks. How are you doing, honestly?' : 'I wanted to check in on how the semester is going for you.'
  return [
    ['What is happening', `Success Score ${Math.round(s.v.success_score)}/100 (${s.band}); academic risk ${s.ar}. Main signals: ${reasons.slice(0, 3).join('; ')}.`],
    ['Reasons to explore', 'Has anything changed recently (health, family, travel, money, workload)? Which subject or task feels hardest right now, and what would help?'],
    ['How to open', `"${opener}"`],
    ['Agreed next step', `${res.steps[0] || 'Agree one small, specific goal for this week'}; follow up in 7 days.`],
  ]
}

function ActionPlan({ s, self, res, role }) {
  const s0 = res.start
  const s1 = res.end
  const v = s.v
  const [ch, setCh] = useState({ attend_rate: Math.round(Math.min(100, Math.max(50, v.att_recent))), asg_rate: Math.round(v.asg_rate * 100), lms_avg: Math.min(10, Math.round(v.lms_avg * 2) / 2), arrears_cleared: 0, mock_add: 0, aptitude_add: 0 })
  const r2 = useMemo(() => MODEL.simulate(s, { attend_rate: ch.attend_rate / 100, asg_rate: ch.asg_rate / 100, lms_avg: ch.lms_avg, arrears_cleared: ch.arrears_cleared, mock_add: ch.mock_add, aptitude_add: ch.aptitude_add }), [s, ch])
  const sliders = [
    ['attend_rate', 'Attend this % of remaining classes', 50, 100, 1], ['asg_rate', 'Assignments submitted (%)', 0, 100, 1], ['lms_avg', 'LMS logins per week', 0, 10, 0.5],
    ...(v.backlogs > 0 ? [['arrears_cleared', 'Arrears cleared', 0, Math.round(v.backlogs), 1]] : []),
    ...(s.year >= 3 ? [['mock_add', 'Extra mock interviews', 0, 5, 1]] : []), ['aptitude_add', 'Aptitude score gain', 0, 30, 5],
  ]
  const acts = useActions().filter((a) => a.roll_no === s.id)
  const [form, setForm] = useState({ action: ACTIONS[0], owner: s.mentor, fu: Math.min(META.week + 2, META.weeks), note: '' })
  const [saved, setSaved] = useState(false)
  const save = (e) => {
    e.preventDefault()
    logActions([{ roll_no: s.id, name: s.name, dept: s.dept, action: form.action, owner: form.owner, note: form.note, follow_up_week: Number(form.fu), by: role.name }])
    setForm((f) => ({ ...f, note: '' }))
    setSaved(true)
  }
  const d = (a, b, inv) => {
    const x = b - a
    if (Math.abs(x) < 0.5) return null
    return <span className={`small ${(x > 0) !== !!inv ? 'good-t' : 'bad-t'}`}>{x > 0 ? 'up' : 'down'} {Math.abs(Math.round(x))}</span>
  }
  return (
    <div className="stack">
      <div className="grid g-main">
        <Card title="Path back on track" sub={`The smallest set of realistic changes, worked out with the same model that ${self ? 'tracks your progress' : 'flagged this student'}.`}>
          {v.projected_attendance < META.attendance_min && v.required_rate_for_75 > 100 && <p className="err" style={{ marginBottom: 10 }}>Attendance cannot reach 75% this semester. Start the condonation process with the HOD now.</p>}
          {!res.steps.length ? <p className="ok">Already on track. No changes needed.</p> : <ol className="steps">{res.steps.map((t) => <li key={t}><span>{t}</span></li>)}</ol>}
          {res.steps.length > 0 && (res.reached ? <p className="ok" style={{ marginTop: 10 }}>This plan brings {self ? 'you' : 'the student'} back on track.</p>
            : s1.prob < META.risk_medium ? <p className="note" style={{ marginTop: 10 }}>This plan removes the risk of failing. Placement goals need more time.</p>
              : <p className="warn" style={{ marginTop: 10 }}>Even this plan does not remove the risk fully. Add counselling and remedial classes.</p>)}
        </Card>
        <div className="stack">
          <Stat label="Success Score with the plan" value={`${Math.round(s0.score)} to ${Math.round(s1.score)}`} />
          {!self && <Stat label="Academic risk with the plan" value={`${MODEL.level(s0.prob)} to ${MODEL.level(s1.prob)}`}
            sub={`Chance of failing ${pct(Math.min(s0.prob, 0.99))} to ${pct(Math.min(s1.prob, 0.99))}`} trend={s1.prob < s0.prob ? 'good' : ''} />}
        </div>
      </div>
      <Card title="Try your own changes" sub="Move the sliders to see the effect on the forecasts">
        <div className="grid g3" style={{ gap: '12px 24px' }}>
          {sliders.map(([k, label, min, max, step]) => (
            <label key={k} className="slider"><span>{label}</span><b className="num ink">{ch[k]}</b>
              <input type="range" min={min} max={max} step={step} value={ch[k]} onChange={(e) => setCh((c) => ({ ...c, [k]: Number(e.target.value) }))} />
            </label>
          ))}
        </div>
        <div className="kpis" style={{ marginTop: 14, gridTemplateColumns: `repeat(${self ? 1 : s.year >= 3 ? 3 : 2}, minmax(0, 1fr))` }}>
          <div className="kpi"><div className="l">Success Score</div><div className="v num">{Math.round(r2.score)}</div><div className="s">{d(s0.score, r2.score)}</div></div>
          {!self && <div className="kpi"><div className="l">Chance of failing a subject</div><div className="v num">{pct(Math.min(r2.prob, 0.99))}</div><div className="s">{d(100 * s0.prob, 100 * r2.prob, true)}</div></div>}
          {!self && s.year >= 3 && <div className="kpi"><div className="l">Chance of getting placed</div><div className="v num">{pct(r2.pprob)}</div><div className="s">{d(100 * s0.pprob, 100 * r2.pprob)}</div></div>}
        </div>
      </Card>
      {!self && (
        <>
          <Card title="Conversation guide for the mentor">
            {guide(s, res).map(([h, t]) => <p key={h} style={{ marginBottom: 8 }}><span className="strong">{h}: </span>{t}</p>)}
          </Card>
          <Card title="Record what was done">
            <form onSubmit={save} className="stack" style={{ gap: 12 }}>
              <div className="row wrap" style={{ gap: 12, alignItems: 'flex-end' }}>
                <label className="fi" style={{ flex: '1 1 200px' }}>Action<select value={form.action} onChange={(e) => setForm({ ...form, action: e.target.value })}>{ACTIONS.map((a) => <option key={a}>{a}</option>)}</select></label>
                <label className="fi" style={{ flex: '1 1 180px' }}>Who will do it<input type="text" value={form.owner} onChange={(e) => setForm({ ...form, owner: e.target.value })} /></label>
                <label className="fi">Follow up in week<select value={form.fu} onChange={(e) => setForm({ ...form, fu: e.target.value })}>{Array.from({ length: META.weeks - META.week + 1 }, (_, i) => META.week + i).map((w) => <option key={w} value={w}>Week {w}</option>)}</select></label>
              </div>
              <label className="fi">Note (optional)<input type="text" value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} /></label>
              <div className="row"><button type="submit" className="btn primary">Save action</button>{saved && <span className="small" style={{ color: 'var(--lo-fg)' }}>Saved. Follow it up on the Interventions page.</span>}</div>
            </form>
            {acts.length > 0 && (
              <div className="table-wrap" style={{ marginTop: 14, border: '1px solid var(--line)', borderRadius: 4 }}>
                <table className="list"><thead><tr><th>When</th><th>Action</th><th>Owner</th><th>Status</th><th>Follow-up week</th><th>Note</th></tr></thead>
                  <tbody>{acts.map((a) => <tr key={a.id}><td className="small">{new Date(a.logged_at).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}</td><td>{a.action}</td><td className="small">{a.owner}</td><td><Pill kind="p-brand">{a.status}</Pill></td><td className="num">{a.follow_up_week}</td><td className="small">{a.note}</td></tr>)}</tbody></table>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  )
}

export default function Student({ self = false }) {
  const params = useParams()
  const { role } = useRole()
  const nav = useNavigate()
  const scope = useMemo(() => scopeStudents(role), [role])
  const opts = useMemo(() => [...scope].sort((a, b) => b.v.acad_prob - a.v.acad_prob), [scope])
  const id = self ? role.roll : params.id
  const [tab, setTab] = useState('overview')
  const s = BY_ID[id]
  const res = useMemo(() => (s ? MODEL.pathToGreen(s) : null), [s])
  const [plannedFor, setPlannedFor] = useState(null)
  if (!s) return <p className="empty">No student with roll number {id}. {!self && <Link to="/students">Back to the directory</Link>}</p>
  if (!scope.some((x) => x.id === id)) return <p className="empty">{s.name} is not in your view. <Link to="/students">Back to the directory</Link></p>
  const plan = () => {
    logActions([{ roll_no: s.id, name: s.name, dept: s.dept, action: 'Mentor meeting', owner: s.mentor, note: res.steps.slice(0, 3).join('; '), follow_up_week: Math.min(META.week + 2, META.weeks), by: role.name }])
    setPlannedFor(s.id)
  }
  const tabs = [['overview', 'Overview'], ['academic', 'Academic'], ['attendance', 'Attendance'], ['lms', 'LMS'], ['engagement', 'Engagement'],
    ['placement', 'Placement'], ['skills', 'Skills'], ...(self ? [] : [['feedback', 'Feedback']]), ['plan', self ? 'My plan' : 'Action plan']]
  return (
    <div>
      {!self && (
        <div className="row wrap" style={{ marginBottom: 12, gap: 12 }}>
          <button type="button" className="link-btn small" onClick={() => nav('/students')}><Icon name="back" size={15} />Back to directory</button>
          <span className="spacer" />
          <label className="fi" style={{ minWidth: 280 }}>Find a student
            <select value={s.id} onChange={(e) => { nav(`/student/${e.target.value}`); setTab('overview') }}>
              {opts.map((x) => <option key={x.id} value={x.id}>{x.name} ({x.id}, {x.dept} year {x.year})</option>)}
            </select>
          </label>
        </div>
      )}
      <section className="card" style={{ marginBottom: 16 }}>
        <div className="card-body">
          <div className="me-head">
            <Avatar name={s.name} size={60} />
            <div style={{ flex: 1, minWidth: 220 }}>
              <h1>{s.name}</h1>
              <div className="facts"><span>{s.id}</span><span>{s.dept}</span><span>Year {s.year}</span>{s.sec && <span>Section {s.sec}</span>}<span>Mentor: <b>{s.mentor}</b></span></div>
              <div className="row wrap" style={{ gap: 6, marginTop: 8 }}>
                {!self && <RiskPill level={s.ar} />}
                <Pill kind="p-brand">{SEG_SHORT[s.seg] || s.seg}</Pill>
                {s.year >= 3 && !self && <span className={`pill ${PLACE_PILL[s.pr] || 'p-grey'}`}>Placement: {RISK_WORD[s.pr]}</span>}
              </div>
            </div>
            <Ring score={s.v.success_score} />
          </div>
        </div>
      </section>
      <Tabs value={tab} onChange={setTab} tabs={tabs} />
      {tab === 'overview' && <Overview s={s} self={self} res={res} onPlan={plan} planned={plannedFor === s.id} />}
      {tab === 'academic' && <Academic s={s} />}
      {tab === 'attendance' && <Attendance s={s} />}
      {tab === 'lms' && <Lms s={s} />}
      {tab === 'engagement' && <Engagement s={s} />}
      {tab === 'placement' && <Placement s={s} self={self} />}
      {tab === 'skills' && <Skills s={s} />}
      {tab === 'feedback' && <Feedback s={s} />}
      {tab === 'plan' && <ActionPlan s={s} self={self} res={res} role={role} />}
    </div>
  )
}
