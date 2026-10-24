import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { DEPTS, isLead, META, MENTORS, RISK_WORD, scopeStudents } from '../lib/data'
import { builtIn } from '../lib/auth'
import { tablePdf } from '../lib/pdf'
import { useRole } from '../lib/role'
import { Avatar, Icon, PageHead, RiskPill, Seg } from '../components/ui'

const QUICK = [['', 'Everyone'], ['new', 'New this week'], ['short', 'Attendance shortage'], ['hidden', 'Hidden strugglers']]
export const hodOf = () => Object.fromEntries(builtIn().filter((u) => u.kind === 'hod').map((u) => [u.dept, u.name]))

export default function Students() {
  const { role } = useRole()
  const nav = useNavigate()
  const [sp, setSp] = useSearchParams()
  const g = (k) => sp.get(k) || ''
  const set = (k, v, extra = {}) => {
    const n = new URLSearchParams(sp)
    for (const [kk, vv] of Object.entries({ [k]: v, ...extra })) { if (vv) n.set(kk, vv); else n.delete(kk) }
    setSp(n, { replace: true })
  }
  const base = useMemo(() => scopeStudents(role), [role])
  const lead = isLead(role)
  const HOD_OF = hodOf()
  const dept = role.kind === 'hod' ? role.dept : g('dept')
  const mentors = MENTORS.filter((m) => (!dept || m.dept === dept) && base.some((s) => s.mentor === m.name))
  const rows = useMemo(() => {
    const q = g('q').toLowerCase()
    return base.filter((s) => {
      if (q && !(s.name.toLowerCase().includes(q) || s.id.toLowerCase().includes(q) || s.dept.toLowerCase() === q)) return false
      if (g('dept') && s.dept !== g('dept')) return false
      if (g('mentor') && s.mentor !== g('mentor')) return false
      if (g('year') && String(s.year) !== g('year')) return false
      if (g('risk') && s.ar !== g('risk')) return false
      if (g('seg') && s.seg !== g('seg')) return false
      const k = g('quick')
      if (k === 'new' && !s.new) return false
      if (k === 'short' && !s.short) return false
      if (k === 'hidden' && s.seg !== 'Silent Strugglers') return false
      return true
    }).sort((a, b) => b.v.acad_prob - a.v.acad_prob)
  }, [base, sp]) // eslint-disable-line react-hooks/exhaustive-deps
  const [page, setPage] = useState(0)
  useEffect(() => setPage(0), [sp])
  const size = 12
  const view = rows.slice(page * size, (page + 1) * size)
  const years = [...new Set(base.map((s) => s.year))].sort()
  const showMentor = role.kind !== 'mentor'
  const scopeLine = [g('dept') && `${g('dept')} department`, g('mentor') && `mentor ${g('mentor')}`, g('year') && `year ${g('year')}`,
    g('risk') && RISK_WORD[g('risk')].toLowerCase()].filter(Boolean).join(', ')
  const pdf = () => tablePdf({
    title: 'Student list', file: `students_week${META.week}.pdf`,
    subtitle: `${rows.length} students${scopeLine ? `: ${scopeLine}` : ''}. Sorted by risk, highest first.`,
    head: ['Roll no', 'Name', 'Dept', 'Year', ...(showMentor ? ['Mentor'] : []), 'CGPA', 'Score', 'Risk status'],
    rows: rows.map((s) => [s.id, s.name, s.dept, s.year, ...(showMentor ? [s.mentor] : []), s.v.cgpa.toFixed(1), Math.round(s.v.success_score), RISK_WORD[s.ar]]),
  })
  return (
    <div>
      <PageHead title={role.kind === 'mentor' ? 'My students' : 'Student directory'} sub="Search and filter every student. Open anyone to see their full profile." />
      <div className="filterbar">
        <label className="fi" style={{ flex: '1 1 220px' }}>Search<input type="search" value={g('q')} placeholder="Search by name, roll number or department" onChange={(e) => set('q', e.target.value)} /></label>
        {lead && (
          <label className="fi">Department and HOD
            <select value={g('dept')} onChange={(e) => set('dept', e.target.value, { mentor: '' })}>
              <option value="">All departments</option>
              {DEPTS.map((d) => <option key={d.code} value={d.code}>{d.code}{HOD_OF[d.code] ? ` (HOD ${HOD_OF[d.code]})` : ''}</option>)}
            </select>
          </label>
        )}
        {showMentor && (
          <label className="fi">Class mentor
            <select value={g('mentor')} onChange={(e) => set('mentor', e.target.value)}>
              <option value="">All mentors</option>
              {mentors.map((m) => <option key={m.name} value={m.name}>{m.name}{lead && !dept ? ` (${m.dept})` : ''}</option>)}
            </select>
          </label>
        )}
        <label className="fi">Year<select value={g('year')} onChange={(e) => set('year', e.target.value)}><option value="">All years</option>{years.map((y) => <option key={y} value={y}>Year {y}</option>)}</select></label>
        <label className="fi">Risk status<select value={g('risk')} onChange={(e) => set('risk', e.target.value)}>
          <option value="">All</option><option value="High">At risk (high)</option><option value="Medium">Moderate</option><option value="Low">Low risk</option>
        </select></label>
      </div>
      <div className="row wrap" style={{ marginBottom: 16, gap: 12 }}>
        <Seg value={g('quick')} onChange={(v) => set('quick', v)} label="Quick view" options={QUICK.map(([v, l]) => ({ value: v, label: l }))} />
        {g('seg') && <span className="pill p-brand">Group: {g('seg')} <button type="button" className="link-btn" aria-label="Remove group filter" onClick={() => set('seg', '')}><Icon name="x" size={12} /></button></span>}
      </div>
      <section className="card">
        <div className="card-head">
          <div><h2>{rows.length.toLocaleString('en-IN')} students</h2><p>Sorted by risk, highest first</p></div>
          <button type="button" className="btn" onClick={pdf} disabled={!rows.length}><Icon name="download" size={16} />Download list (PDF)</button>
        </div>
        <div className="table-wrap">
          <table className="list">
            <thead><tr><th>Name</th><th>Department</th><th>Year</th>{showMentor && <th className="hide-sm">Mentor</th>}<th className="r">CGPA</th><th className="r">Success Score</th><th>Risk status</th></tr></thead>
            <tbody>
              {view.map((s) => (
                <tr key={s.id} className="click" onClick={() => nav(`/student/${s.id}`)}>
                  <td><div className="who"><Avatar name={s.name} /><div><b>{s.name}</b><span className="sub">{s.id}</span></div></div></td>
                  <td>{s.dept}</td><td>{s.year}</td>
                  {showMentor && <td className="small hide-sm">{s.mentor}</td>}
                  <td className="r num">{s.v.cgpa.toFixed(1)}</td>
                  <td className="r num strong">{Math.round(s.v.success_score)}</td>
                  <td><RiskPill level={s.ar} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length === 0 && <p className="empty">No students match these filters.</p>}
        </div>
        {rows.length > size && (
          <div className="pager">
            <span>{page * size + 1} to {Math.min(rows.length, (page + 1) * size)} of {rows.length}</span>
            <button type="button" className="btn sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Previous</button>
            <button type="button" className="btn sm" disabled={(page + 1) * size >= rows.length} onClick={() => setPage((p) => p + 1)}>Next</button>
          </div>
        )}
      </section>
    </div>
  )
}
