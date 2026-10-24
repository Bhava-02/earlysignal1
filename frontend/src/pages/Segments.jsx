import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { META, scopeStudents, SEG, SEG_LOOK, SEG_ORDER } from '../lib/data'
import { logActions } from '../lib/actions'
import { useRole } from '../lib/role'
import { Card, Icon, PageHead, RiskPill, Who } from '../components/ui'

export default function Segments() {
  const { role } = useRole()
  const nav = useNavigate()
  const V = useMemo(() => scopeStudents(role), [role])
  const counts = Object.fromEntries(SEG_ORDER.map((n) => [n, V.filter((s) => s.seg === n).length]))
  const [pick, setPick] = useState(SEG_ORDER[0])
  const [page, setPage] = useState(0)
  const [done, setDone] = useState({})
  const detail = useRef(null)
  const choose = (name) => { setPick(name); setTimeout(() => detail.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50) }
  useEffect(() => setPage(0), [pick])
  const seg = SEG[pick]
  const [label, , desc] = SEG_LOOK[pick]
  const G = useMemo(() => V.filter((s) => s.seg === pick).sort((a, b) => b.v.acad_prob - a.v.acad_prob), [V, pick])
  const placement = pick === 'Book-smart, Job-shy' || pick === 'Placement-Ready Stars'
  const size = 8
  const view = G.slice(page * size, (page + 1) * size)
  const planAll = () => {
    logActions(G.map((s) => ({ roll_no: s.id, name: s.name, dept: s.dept, action: seg.actions[0], owner: seg.owner, note: `Group plan: ${label}`,
      follow_up_week: Math.min(META.week + 2, META.weeks), by: role.name })))
    setDone((d) => ({ ...d, [pick]: G.length }))
  }
  return (
    <div className="stack">
      <PageHead title="Student segmentation" sub="Meaningful groups of students, each with a plan, so you can act on many students at once." />
      <div className="segcards">
        {SEG_ORDER.map((name) => {
          const [l, icon, d] = SEG_LOOK[name]
          return (
            <button key={name} type="button" className={`segcard ${pick === name ? 'on' : ''}`} onClick={() => choose(name)} aria-pressed={pick === name}>
              <span className="ic"><Icon name={icon} size={19} /></span>
              <span className="t">{l}</span>
              <span className="n"><b className="num">{counts[name]}</b>students</span>
              <span className="d">{d}</span>
              <span className="go">{pick === name ? 'Showing these students' : 'View students'}</span>
            </button>
          )
        })}
      </div>

      <div className="grid g-seg" ref={detail} style={{ scrollMarginTop: 70 }}>
        <Card title={label} sub={`${G.length} students. ${desc}`}>
          <p className="small"><span className="strong">Why they are here: </span>{seg.rule}.</p>
          <p className="small strong" style={{ marginTop: 12 }}>What to do (led by {seg.owner})</p>
          <ul className="reasons">{seg.actions.map((a) => <li key={a}>{a}</li>)}</ul>
          <p className="small" style={{ marginTop: 10 }}><span className="strong">It's working when: </span>{seg.kpi}.</p>
          {G.length > 0 && (
            <button type="button" className="btn primary" style={{ width: '100%', marginTop: 14 }} disabled={!!done[pick]} onClick={planAll}>
              {done[pick] ? 'Planned for this group' : `Plan the first action for all ${G.length}`}
            </button>
          )}
          {done[pick] && <p className="ok" style={{ marginTop: 10 }}>Added to Interventions for {done[pick]} students.</p>}
        </Card>
        <Card title={`Students in this group (${G.length})`} flush>
          <div className="table-wrap">
            <table className="list">
              <thead><tr><th>Name</th><th className="hide-sm">Class</th>{placement ? <><th className="r">CGPA</th><th>Placement</th><th className="hide-sm">Biggest gap</th></> : <><th>Risk</th><th className="hide-sm">Main reason</th></>}</tr></thead>
              <tbody>
                {view.map((s) => (
                  <tr key={s.id} className="click" onClick={() => nav(`/student/${s.id}`)}>
                    <td><Who s={s} sub={`${s.id}, ${s.dept} Y${s.year}`} plain /></td>
                    <td className="small hide-sm">{s.dept} Y{s.year}{s.sec ? ` ${s.sec}` : ''}</td>
                    {placement ? <>
                      <td className="r num">{s.v.cgpa.toFixed(1)}</td><td><RiskPill level={s.pr} /></td><td className="small hide-sm">{s.preasons[0] || 'None'}</td>
                    </> : <>
                      <td><RiskPill level={s.ar} /></td><td className="small hide-sm">{s.reasons[0] || 'No strong warning signs'}</td>
                    </>}
                  </tr>
                ))}
              </tbody>
            </table>
            {G.length === 0 && <p className="empty">No students in this group.</p>}
          </div>
          {G.length > size && (
            <div className="pager">
              <span>{page * size + 1} to {Math.min(G.length, (page + 1) * size)} of {G.length}</span>
              <button type="button" className="btn sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Previous</button>
              <button type="button" className="btn sm" disabled={(page + 1) * size >= G.length} onClick={() => setPage((p) => p + 1)}>Next</button>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
