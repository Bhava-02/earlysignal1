// HODs and faculty (admin and principal), or Mentors (HOD): see the students under each HOD and each class mentor.
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { DEPTS, isLead, mean, MENTORS, STUDENTS } from '../lib/data'
import { useRole } from '../lib/role'
import { Card, PageHead, Select, Tabs } from '../components/ui'
import { hodOf } from './Students'

const stats = (g) => ({
  n: g.length, high: g.filter((s) => s.ar === 'High').length, hidden: g.filter((s) => s.seg === 'Silent Strugglers').length,
  short: g.filter((s) => s.short).length, score: g.length ? mean(g.map((s) => s.v.success_score)) : 0,
})

function Departments() {
  const nav = useNavigate()
  const HOD_OF = hodOf()
  return (
    <Card title="Departments and their HODs" sub="Select a department to see all its students" flush>
      <div className="table-wrap">
        <table className="list">
          <thead><tr><th>Department</th><th>Head of department</th><th className="r">Class mentors</th><th className="r">Students</th><th className="r">At risk</th><th className="r hide-sm">Attendance shortage</th><th className="r">Average score</th></tr></thead>
          <tbody>
            {DEPTS.map((d) => {
              const x = stats(STUDENTS.filter((s) => s.dept === d.code))
              return (
                <tr key={d.code} className="click" onClick={() => nav(`/students?dept=${d.code}`)}>
                  <td><b className="strong">{d.code}</b><div className="tiny">{d.name}</div></td><td>{HOD_OF[d.code] || 'Not assigned'}</td>
                  <td className="r num">{MENTORS.filter((m) => m.dept === d.code).length}</td><td className="r num">{x.n}</td>
                  <td className="r num strong">{x.high}</td><td className="r num hide-sm">{x.short}</td><td className="r num">{x.score.toFixed(1)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

function Mentors({ fixedDept }) {
  const nav = useNavigate()
  const [dept, setDept] = useState(fixedDept || '')
  const [q, setQ] = useState('')
  const list = MENTORS.filter((m) => (!dept || m.dept === dept) && (!q || m.name.toLowerCase().includes(q.toLowerCase())))
  return (
    <Card title={fixedDept ? `Class mentors in ${fixedDept}` : 'Class mentors'} sub="Select a mentor to see the students they mentor" flush
      right={<div className="row wrap" style={{ gap: 10 }}>
        {!fixedDept && <Select label="Department" value={dept} onChange={setDept} all="All departments" options={DEPTS.map((d) => d.code)} />}
        <label className="fi">Search<input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Mentor name" /></label>
      </div>}>
      <div className="table-wrap">
        <table className="list">
          <thead><tr><th>Class mentor</th>{!fixedDept && <th>Department</th>}<th className="r">Students</th><th className="r">At risk</th><th className="r hide-sm">Hidden strugglers</th><th className="r hide-sm">Attendance shortage</th><th className="r">Average score</th></tr></thead>
          <tbody>
            {list.map((m) => {
              const x = stats(STUDENTS.filter((s) => s.mentor === m.name))
              return (
                <tr key={m.name} className="click" onClick={() => nav(`/students?mentor=${encodeURIComponent(m.name)}${fixedDept ? '' : `&dept=${m.dept}`}`)}>
                  <td className="strong">{m.name}</td>{!fixedDept && <td>{m.dept}</td>}<td className="r num">{x.n}</td><td className="r num strong">{x.high}</td>
                  <td className="r num hide-sm">{x.hidden}</td><td className="r num hide-sm">{x.short}</td><td className="r num">{x.score.toFixed(1)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
        {list.length === 0 && <p className="empty">No mentors match.</p>}
      </div>
    </Card>
  )
}

export default function Staff() {
  const { role } = useRole()
  const lead = isLead(role)
  const [tab, setTab] = useState(lead ? 'depts' : 'mentors')
  if (!lead) {
    return (
      <div>
        <PageHead title="Mentors" sub={`Class mentors in the ${role.dept} department and the students under each of them.`} />
        <Mentors fixedDept={role.dept} />
      </div>
    )
  }
  return (
    <div>
      <PageHead title="HODs and faculty" sub="See the students under every HOD and every class mentor." />
      <Tabs value={tab} onChange={setTab} tabs={[['depts', 'Departments and HODs'], ['mentors', 'Class mentors']]} />
      {tab === 'depts' && <Departments />}
      {tab === 'mentors' && <Mentors />}
    </div>
  )
}
