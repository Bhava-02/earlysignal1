import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { mean, scopeStudents } from '../lib/data'
import { apply, EXAMPLES, parse } from '../lib/ask'
import { adminEmail } from '../lib/auth'
import { pct } from '../lib/format'
import { useRole } from '../lib/role'
import { Card, PageHead, RiskPill, Who } from '../components/ui'

function Results({ rows }) {
  const nav = useNavigate()
  const [n, setN] = useState(10)
  return (
    <div className="table-wrap" style={{ marginTop: 10, border: '1px solid var(--line)', borderRadius: 4 }}>
      <table className="list">
        <thead><tr><th>Name</th><th className="hide-sm">Class</th><th className="r">CGPA</th><th className="r">Score</th><th>Risk</th><th className="hide-sm">Main reason</th></tr></thead>
        <tbody>
          {rows.slice(0, n).map((s) => (
            <tr key={s.id} className="click" onClick={() => nav(`/student/${s.id}`)}>
              <td><Who s={s} sub={`${s.id}, ${s.dept} Y${s.year}`} plain /></td><td className="small hide-sm">{s.dept} Y{s.year}</td><td className="r num">{s.v.cgpa.toFixed(1)}</td>
              <td className="r num strong">{Math.round(s.v.success_score)}</td><td><RiskPill level={s.ar} /></td><td className="small hide-sm">{s.reasons[0] || 'No strong warning signs'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > n && <div className="pager"><span>Showing {n} of {rows.length}</span><button type="button" className="btn sm" onClick={() => setN((x) => x + 10)}>Show 10 more</button></div>}
    </div>
  )
}

export default function Assistant() {
  const { role } = useRole()
  const V = useMemo(() => scopeStudents(role), [role])
  const [q, setQ] = useState('')
  const [log, setLog] = useState([])
  const end = useRef(null)
  useEffect(() => { if (log.length) end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [log])
  const ask = (text) => {
    const t = (text ?? q).trim()
    if (!t) return
    setQ('')
    const spec = parse(t)
    if (!spec.filters.length) { setLog((l) => [...l, { q: t, sorry: true }]); return }
    const rows = apply(V, spec)
    setLog((l) => [...l, { q: t, spec, rows }])
  }
  const avg = mean(V.map((s) => s.v.success_score))
  return (
    <div style={{ maxWidth: 1000 }}>
      <PageHead title="AI assistant" sub="Ask in plain English. You get the matching students and a short answer. Numbers always come from the data." />
      <Card title="Try one of these">
        <div className="chips">{EXAMPLES.map((e) => <button key={e} type="button" onClick={() => ask(e)}>{e}</button>)}</div>
      </Card>
      <div className="chat" style={{ marginTop: 16 }}>
        {log.length === 0 && <p className="muted small">Type a question in the box at the bottom of the page.</p>}
        {log.map((m, i) => (
          <div key={i} className="chat">
            <div className="q">{m.q}</div>
            <div className="a">
              {m.sorry ? (
                <p>Sorry, I can only answer questions about your students' data here, such as a department, a year, attendance, CGPA, risk or a student group.
                  For anything else, please mail your queries to <a href={`mailto:${adminEmail()}`}>{adminEmail()}</a>.</p>
              ) : m.rows.length ? (
                <>
                  <p><b className="ink">{m.rows.length} students</b> match ({m.spec.explanation}). Their average Success Score is <b className="ink">{Math.round(mean(m.rows.map((s) => s.v.success_score)))}</b> against {Math.round(avg)} overall,
                    and <b className="ink">{pct(m.rows.filter((s) => s.ar === 'High').length / m.rows.length)}</b> are at high risk.</p>
                  <Results rows={m.rows} />
                </>
              ) : <p>No students match ({m.spec.explanation}). Try loosening one condition.</p>}
              <p className="tiny" style={{ marginTop: 8 }}>{m.sorry ? 'No filter could be read from this question.' : 'Understood by the built-in reader.'}</p>
            </div>
          </div>
        ))}
        <div ref={end} />
      </div>
      <form className="askbar" onSubmit={(e) => { e.preventDefault(); ask() }}>
        <input type="text" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask about your students, e.g. hostel students in IT with coding below 40" aria-label="Your question" />
        <button type="submit" className="btn primary">Ask</button>
      </form>
    </div>
  )
}
