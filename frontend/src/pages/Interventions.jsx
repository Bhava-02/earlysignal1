import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { B, META, scopeStudents, scopeText, SEG } from '../lib/data'
import { latestStatus, setStatus, STATUSES, useActions } from '../lib/actions'
import { weeklyReport } from '../lib/pdf'
import { pct } from '../lib/format'
import { useRole } from '../lib/role'
import { COL, HBars } from '../components/charts'
import { Card, Icon, PageHead, Pill, Stat, Tabs, Who } from '../components/ui'

const STATUS_PILL = { Pending: 'p-med', Planned: 'p-brand', 'In progress': 'p-brand', Done: 'p-low', 'Could not reach': 'p-high' }

const needsAction = (V) => V.filter((s) => s.ar === 'High' || s.seg === 'Silent Strugglers' || (s.year >= 3 && s.seg === 'Book-smart, Job-shy'))
  .sort((a, b) => b.v.acad_prob - a.v.acad_prob)

function issue(s) {
  if (s.seg === 'Book-smart, Job-shy') return 'Placement readiness'
  if (s.seg === 'Silent Strugglers') return 'Falling engagement'
  if (s.ar === 'High' && s.pr === 'High') return 'Academic and placement'
  return s.fam[0] || 'Academic risk'
}

function Suggested({ V, A }) {
  const nav = useNavigate()
  const latest = useMemo(() => latestStatus(A), [A])
  const [f, setF] = useState('')
  const [page, setPage] = useState(0)
  useEffect(() => setPage(0), [f])
  let N = needsAction(V).map((s) => ({ s, status: latest[s.id] || 'Pending' }))
  if (f) N = N.filter((x) => x.status === f)
  const size = 10
  return (
    <Card title={`${needsAction(V).length} students need an action`} sub="High risk, hidden strugglers, and final-year students with good marks who are not job-ready" flush
      right={<label className="fi">Status<select value={f} onChange={(e) => setF(e.target.value)}><option value="">All</option>{STATUSES.map((x) => <option key={x}>{x}</option>)}</select></label>}>
      <div className="table-wrap">
        <table className="list">
          <thead><tr><th>Student</th><th>Issue</th><th className="hide-sm">Suggested action</th><th className="hide-sm">Assigned to</th><th>Status</th></tr></thead>
          <tbody>
            {N.slice(page * size, (page + 1) * size).map(({ s, status }) => (
              <tr key={s.id} className="click" onClick={() => nav(`/student/${s.id}`)}>
                <td><Who s={s} sub={s.id} /></td><td className="small">{issue(s)}</td>
                <td className="small hide-sm">{SEG[s.seg].actions[0]}</td><td className="small hide-sm">{SEG[s.seg].owner}</td>
                <td><Pill kind={STATUS_PILL[status]}>{status}</Pill></td>
              </tr>
            ))}
          </tbody>
        </table>
        {N.length === 0 && <p className="empty">No students with this status.</p>}
      </div>
      {N.length > size && (
        <div className="pager">
          <span>{page * size + 1} to {Math.min(N.length, (page + 1) * size)} of {N.length}</span>
          <button type="button" className="btn sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Previous</button>
          <button type="button" className="btn sm" disabled={(page + 1) * size >= N.length} onClick={() => setPage((p) => p + 1)}>Next</button>
        </div>
      )}
    </Card>
  )
}

function Followups({ A }) {
  if (!A.length) {
    return <p className="note">No actions logged yet. Use Create action plan on a student's profile, or plan an action for a whole group on the Segments page.</p>
  }
  return (
    <div className="stack">
      <div className="stats">
        {['Planned', 'In progress', 'Done', 'Could not reach'].map((x) => (
          <Stat key={x} label={x} value={A.filter((a) => a.status === x).length} />
        ))}
      </div>
      <Card title="Actions logged" sub="Change a status and it is saved straight away" flush>
        <div className="table-wrap">
          <table className="list">
            <thead><tr><th>Student</th><th>Dept</th><th>Action</th><th className="hide-sm">Owner</th><th className="r">Follow-up week</th><th>Status</th><th className="hide-sm">Note</th></tr></thead>
            <tbody>
              {[...A].reverse().map((a) => (
                <tr key={a.id}>
                  <td><Link to={`/student/${a.roll_no}`} className="strong">{a.name}</Link><div className="tiny">{a.roll_no}</div></td>
                  <td>{a.dept}</td><td>{a.action}</td><td className="small hide-sm">{a.owner}</td><td className="r num">{a.follow_up_week}</td>
                  <td><select value={a.status} onChange={(e) => setStatus(a.id, e.target.value)} aria-label={`Status for ${a.name}`}>{STATUSES.slice(1).map((x) => <option key={x}>{x}</option>)}</select></td>
                  <td className="small hide-sm">{a.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}

function WhatWorks() {
  const acted = B.effects.filter((e) => e.action !== 'No action taken')
  if (!acted.length) return <p className="note">Not enough past actions to measure yet. As mentors log actions here, this chart fills in.</p>
  const best = acted[0]
  const data = acted.map((e) => ({ action: e.action, without: Math.round(100 * e.expected_without_action), with: Math.round(100 * e.fail_rate), red: e.fail_rate_reduction }))
  return (
    <Card title={`${best.action} worked best`} sub={`${pct(best.fail_rate_reduction)} fewer failures than in similar students who got no help`}
      foot={`Students flagged by the college's old alert (${META.alert_rule}). Mentors followed up on about 60%, based on time available, so the rest are a fair comparison.`}>
      <HBars data={data} y="action" yWidth={160} domain={[0, 60]} fmt={(v) => `${v}%`} title={(l, p) => `${l}: ${pct(p.red)} fewer failures`}
        series={[{ key: 'without', name: 'Similar students, no help', color: COL.c3 }, { key: 'with', name: 'Students who got this help', color: COL.c1 }]} />
      <p className="tiny" style={{ marginTop: 6 }}>Share of students who failed at least one subject.</p>
    </Card>
  )
}

export default function Interventions() {
  const { role } = useRole()
  const V = useMemo(() => scopeStudents(role), [role])
  const ids = useMemo(() => new Set(V.map((s) => s.id)), [V])
  const all = useActions()
  const A = all.filter((a) => ids.has(a.roll_no))
  const [tab, setTab] = useState('actions')
  const report = () => {
    const hi = V.filter((s) => s.ar === 'High').sort((a, b) => b.v.acad_prob - a.v.acad_prob).slice(0, 25)
    const segs = Object.entries(V.reduce((m, s) => ({ ...m, [s.seg]: (m[s.seg] || 0) + 1 }), {})).sort((a, b) => b[1] - a[1])
    weeklyReport({
      scope: scopeText(role), file: `weekly_report_week${META.week}.pdf`,
      kpis: [['Students', V.length], ['At high risk', hi.length ? V.filter((s) => s.ar === 'High').length : 0], ['New this week', V.filter((s) => s.new).length],
        ['Attendance shortage ahead', V.filter((s) => s.short).length], ['Actions logged', `${A.length} (${A.filter((a) => a.status === 'Done').length} done)`]],
      risk: hi.map((s) => [s.name, s.id, `${s.dept} Y${s.year}`, pct(Math.min(s.v.acad_prob, 0.99)), s.reasons[0] || '', s.mentor]),
      groups: segs.map(([g, n]) => [g, n, SEG[g].actions[0]]),
      effects: B.effects.map((e) => [e.action, Math.round(e.students), pct(e.fail_rate), pct(e.expected_without_action)]),
    })
  }
  return (
    <div>
      <PageHead title="Interventions and reports" sub="Track suggested actions, follow-ups and what works. Generate the weekly report."
        right={<button type="button" className="btn primary" onClick={report}><Icon name="download" size={16} />Generate report (PDF)</button>} />
      <Tabs value={tab} onChange={setTab} tabs={[['actions', 'Suggested actions'], ['followups', 'Follow-ups'], ['works', 'What works']]} />
      {tab === 'actions' && <Suggested V={V} A={A} />}
      {tab === 'followups' && <Followups A={A} />}
      {tab === 'works' && <WhatWorks />}
      <p className="tiny" style={{ marginTop: 12 }}>Actions are saved in this browser.</p>
    </div>
  )
}
