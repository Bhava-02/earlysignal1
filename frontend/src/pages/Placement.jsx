import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { B, DEPTS, META, scopeStudents } from '../lib/data'
import { pct } from '../lib/format'
import { useRole } from '../lib/role'
import { COL, HBars, RAMP } from '../components/charts'
import { Card, PageHead, RiskPill, Stat, Who } from '../components/ui'

export default function Placement() {
  const { role } = useRole()
  const nav = useNavigate()
  const Y = useMemo(() => scopeStudents(role).filter((s) => s.year >= 3), [role])
  const [only, setOnly] = useState(false)
  const [page, setPage] = useState(0)
  if (!Y.length) return <div><PageHead title="Placement readiness" /><p className="note">No 3rd or 4th year students in your view.</p></div>
  const pm = B.placement
  const o = pm.odds
  const bsjs = Y.filter((s) => s.seg === 'Book-smart, Job-shy')
  const units = [['One more mock interview', o.mock_interviews], ['10 more coding points', o.best_coding ** 10], ['10 more aptitude points', o.best_aptitude ** 10],
    ['10 more soft-skills points', o.soft_skill_score ** 10], ['One more certification', o.certifications]]
    .map(([name, v]) => ({ name, v: Math.round((v - 1) * 100) })).sort((a, b) => b.v - a.v)
  const depts = DEPTS.map((d) => d.code).filter((d) => Y.some((s) => s.dept === d))
  const byDept = depts.map((d) => {
    const g = Y.filter((s) => s.dept === d)
    const f = (l) => Math.round((100 * g.filter((s) => s.pr === l).length) / g.length)
    return { d, notready: f('High'), almost: f('Medium'), ready: f('Low'), n: g.length }
  })
  let show = Y.filter((s) => s.pr === 'High' || s.pr === 'Medium').sort((a, b) => a.v.placement_prob - b.v.placement_prob)
  if (only) show = show.filter((s) => s.seg === 'Book-smart, Job-shy')
  const size = 10
  const view = show.slice(page * size, (page + 1) * size)
  return (
    <div className="stack">
      <PageHead title="Placement readiness" sub="How ready 3rd and 4th years are for campus placements, and what makes the biggest difference, learned from last year's graduates." />
      <div className="stats">
        <Stat label="Placement-ready" value={pct(Y.filter((s) => s.pr === 'Low').length / Y.length)} sub={`of ${Y.length} 3rd and 4th years`} />
        <Stat label="Not ready yet" value={Y.filter((s) => s.pr === 'High').length} unit="students" sub="need a placement plan" />
        <Stat label="Good marks, not job-ready" value={bsjs.length} unit="students" sub="CGPA fine, skills not" />
        <Stat label="Not eligible today" value={pct(Y.filter((s) => !s.v.eligible).length / Y.length)} sub={`CGPA below ${META.cgpa_min} or arrears`} />
      </div>
      <div className="grid g2">
        <Card title="What gets students placed here" sub="How much each change raised the odds of getting placed, last year">
          <HBars data={units} y="name" yWidth={170} series={[{ key: 'v', name: 'Higher odds', color: COL.c1 }]} fmt={(v) => `${v}%`} />
          <p className="small" style={{ marginTop: 8 }}><span className="strong">Takeaway: </span>mock interviews matter far more than certificates, yet {pct(Y.filter((s) => s.v.mock_interviews === 0).length / Y.length)} of these students have not done one.</p>
        </Card>
        <Card title="Readiness by department" foot={`Last year ${pct(pm.rate)} were placed: ${pct(pm.eligible_rate)} of eligible students, ${pct(pm.ineligible_rate)} of the rest.`}>
          <HBars data={byDept} y="d" yWidth={64} stacked domain={[0, 100]} fmt={(v) => `${v}%`} title={(l, p) => `${l}: ${p.n} students`}
            series={[{ key: 'notready', name: 'Not ready', color: RAMP[0] }, { key: 'almost', name: 'Almost', color: RAMP[1] }, { key: 'ready', name: 'Ready', color: RAMP[2] }]} />
        </Card>
      </div>
      <Card title="Students who need a placement plan" flush
        right={<label className="row small" style={{ gap: 6 }}><input type="checkbox" checked={only} onChange={(e) => { setOnly(e.target.checked); setPage(0) }} />Only good marks, not job-ready</label>}>
        <div className="table-wrap">
          <table className="list">
            <thead><tr><th>Name</th><th className="hide-sm">Class</th><th className="r">CGPA</th><th>Placement</th><th className="r">Chance</th><th className="r hide-sm">Mock interviews</th><th className="hide-sm">Biggest gap</th></tr></thead>
            <tbody>
              {view.map((s) => (
                <tr key={s.id} className="click" onClick={() => nav(`/student/${s.id}`)}>
                  <td><Who s={s} sub={`${s.id}, ${s.dept} Y${s.year}`} plain /></td><td className="small hide-sm">{s.dept} Y{s.year}</td><td className="r num">{s.v.cgpa.toFixed(1)}</td>
                  <td><RiskPill level={s.pr} /></td><td className="r num strong">{pct(s.v.placement_prob)}</td>
                  <td className="r num hide-sm">{Math.round(s.v.mock_interviews)}</td><td className="small hide-sm">{s.preasons[0] || 'None'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {show.length === 0 && <p className="empty">No students need a placement plan in this view.</p>}
        </div>
        {show.length > size && (
          <div className="pager">
            <span>{page * size + 1} to {Math.min(show.length, (page + 1) * size)} of {show.length}</span>
            <button type="button" className="btn sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Previous</button>
            <button type="button" className="btn sm" disabled={(page + 1) * size >= show.length} onClick={() => setPage((p) => p + 1)}>Next</button>
          </div>
        )}
      </Card>
    </div>
  )
}
