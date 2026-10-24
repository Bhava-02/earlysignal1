import { useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { B, META, mean, scopeStudents, scopeText } from '../lib/data'
import { pct } from '../lib/format'
import { useRole } from '../lib/role'
import { Columns, Donut, SERIES } from '../components/charts'
import { Card, Icon, PageHead, Pill, Stat, Who } from '../components/ui'

const greeting = () => {
  const h = new Date().getHours()
  return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening'
}

export default function Dashboard() {
  const { role } = useRole()
  const nav = useNavigate()
  const V = useMemo(() => scopeStudents(role), [role])
  const W = META.week
  const tr = B.trend.filter((r) => r.dept === (role.dept || 'All'))
  const now = mean(V.map((s) => s.v.success_score))
  const then = tr.find((r) => r.week === W - 3)?.success ?? now
  const d = now - then
  const hi = V.filter((s) => s.ar === 'High').length
  const newly = V.filter((s) => s.new).length
  const y34 = V.filter((s) => s.year >= 3)
  const ready = y34.length ? y34.filter((s) => s.pr === 'Low').length / y34.length : 0
  const acad = (s) => s.ar === 'High'
  const plc = (s) => s.pr === 'High'
  const parts = [
    { name: 'Academic risk only', value: V.filter((s) => acad(s) && !plc(s)).length, color: SERIES[0] },
    { name: 'Placement risk only', value: V.filter((s) => plc(s) && !acad(s)).length, color: SERIES[1] },
    { name: 'Both', value: V.filter((s) => acad(s) && plc(s)).length, color: SERIES[2] },
  ]
  const total = parts.reduce((a, p) => a + p.value, 0)
  const top = useMemo(() => V.filter(acad).sort((a, b) => Number(b.new) - Number(a.new) || b.v.acad_prob - a.v.acad_prob).slice(0, 6), [V])
  const crit = V.filter((s) => s.seg === 'Critical: Act This Week').length
  const hidden = V.filter((s) => s.seg === 'Silent Strugglers').length
  const short = V.filter((s) => s.short).length
  const rec = V.filter((s) => s.short && s.v.required_rate_for_75 <= 95).length
  const trendData = tr.map((r) => ({ week: r.week, success: r.success, academic: r.academic, engagement: r.engagement }))

  return (
    <div className="stack">
      <PageHead title={`${greeting()}, ${role.name}!`} sub={`Here's what is happening with ${scopeText(role)} this week.`} />
      <div className="stats">
        <Stat label="Total students" value={V.length.toLocaleString('en-IN')}
          sub={role.kind === 'mentor' ? 'Your mentees' : `${new Set(V.map((s) => s.dept)).size} department${new Set(V.map((s) => s.dept)).size === 1 ? '' : 's'}`} to="/students" />
        <Stat label="At-risk students" value={hi} sub={`${newly} new this week`} trend={newly ? 'bad' : ''} to="/students?risk=High" />
        <Stat label="Average Success Score" value={now.toFixed(1)} unit="/ 100" sub={`${Math.abs(d).toFixed(1)} since week ${W - 3}`}
          trend={d > 0.05 ? 'good' : d < -0.05 ? 'bad' : ''} />
        <Stat label="Placement-ready" value={pct(ready)} sub={`of ${y34.length} 3rd and 4th years`} to="/placement" />
      </div>

      <div className="grid g-main">
        <Card title="Student Success trend" sub="Average score this semester, week by week">
          <Columns data={trendData} x="week" xfmt={(w) => `Wk ${w}`} fmt={(v) => Number(v).toFixed(1)} yfmt={(v) => v} domain={[0, 100]} height={270}
            title={(l) => `Week ${l}`}
            series={[{ key: 'success', name: 'Overall', color: SERIES[0] }, { key: 'academic', name: 'Academic', color: SERIES[1] }, { key: 'engagement', name: 'Engagement', color: SERIES[3] }]} />
        </Card>
        <Card title="Risk distribution">
          <Donut data={parts} total={total} caption="with a high risk" />
          <div style={{ marginTop: 10 }}>
            {parts.map((p) => (
              <div className="kvl" key={p.name}>
                <span className="row" style={{ gap: 8 }}><i style={{ width: 10, height: 10, borderRadius: 2, background: p.color, display: 'inline-block' }} />{p.name}</span>
                <span>{p.value} ({pct(p.value / Math.max(total, 1))})</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="grid g-main">
        <Card title="Students needing attention" flush right={<Link to="/students?risk=High" className="small nowrap">View all</Link>}>
          <div className="table-wrap">
            <table className="list">
              <thead><tr><th>Student</th><th>Risk</th><th className="r">Score</th></tr></thead>
              <tbody>
                {top.map((s) => (
                  <tr key={s.id} className="click" onClick={() => nav(`/student/${s.id}`)}>
                    <td><Who s={s} sub={s.reasons[0]} /></td>
                    <td><div className="row" style={{ gap: 4, flexWrap: 'wrap' }}>
                      {plc(s) ? <Pill kind="p-high">Both</Pill> : <Pill kind="p-high">Academic</Pill>}
                      {s.new && <Pill kind="p-solid">New</Pill>}
                    </div></td>
                    <td className="r num strong">{Math.round(s.v.success_score)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {top.length === 0 && <p className="empty">No high-risk students right now.</p>}
          </div>
        </Card>
        <Card title="This week's priorities" foot={<Link to="/segments" className="row" style={{ gap: 6 }}><Icon name="segments" size={15} />See all groups and plans</Link>}>
          <ol className="steps">
            {[
              [`Meet ${crit} students who need action this week`, 'Several warning signs at once.'],
              [`Check in with ${hidden} hidden strugglers`, 'Marks look fine, but effort is dropping.'],
              [`Warn ${short} students about attendance`, `${rec} can still reach 75% if they attend almost every class.`],
            ].map(([t, x]) => <li key={t}><div><b>{t}</b><div className="small muted">{x}</div></div></li>)}
          </ol>
        </Card>
      </div>
    </div>
  )
}
