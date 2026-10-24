import { useMemo, useState } from 'react'
import { B, DEPTS, isLead, META, mean, scopeStudents, scopeText } from '../lib/data'
import { pct } from '../lib/format'
import { useRole } from '../lib/role'
import { BAND_COLORS, COL, Columns, SERIES } from '../components/charts'
import { Card, Meter, PageHead, Seg, Stat } from '../components/ui'

const BANDS = ['At Risk', 'Needs Attention', 'On Track', 'Thriving']

// Weekly average of one weekly measure across students, for this semester ('now') or last semester ('last')
function weekly(S, sem, key, weeks) {
  return Array.from({ length: weeks }, (_, i) => {
    if (key === 'asg') {
      let sub = 0
      let due = 0
      for (const s of S) { sub += s.wk[sem]?.asg?.[i] || 0; due += s.wk[sem]?.due?.[i] || 0 }
      return due ? (100 * sub) / due : null
    }
    const v = S.map((s) => s.wk[sem]?.[key]?.[i]).filter((x) => x != null)
    return v.length ? mean(v) : null
  })
}

export default function Analytics() {
  const { role } = useRole()
  const all = useMemo(() => scopeStudents(role), [role])
  const [dsel, setDsel] = useState('')
  const [metric, setMetric] = useState('att')
  const V = dsel ? all.filter((s) => s.dept === dsel) : all
  const W = META.week
  const y34 = V.filter((s) => s.year >= 3)
  const attNow = mean(weekly(V, 'now', 'att', W).filter((x) => x != null))
  const attLast = mean(weekly(V, 'last', 'att', W).filter((x) => x != null))
  const lmsNow = mean(weekly(V, 'now', 'logins', W).filter((x) => x != null))
  const lmsLast = mean(weekly(V, 'last', 'logins', W).filter((x) => x != null))
  const dAtt = attNow - attLast
  const dLms = lmsNow - lmsLast

  const depts = DEPTS.map((d) => d.code).filter((d) => V.some((s) => s.dept === d))
  const riskData = META.risk_weeks.map((w, i) => {
    const row = { week: w }
    for (const d of depts) {
      const g = V.filter((s) => s.dept === d && s.risk[i] != null)
      row[d] = g.length ? Math.round((100 * g.filter((s) => s.risk[i] >= META.risk_medium).length) / g.length) : null
    }
    return row
  })
  const hi = V.filter((s) => s.ar === 'High')
  const fam = {}
  for (const s of hi) for (const f of new Set(s.fam)) fam[f] = (fam[f] || 0) + 1
  const factors = Object.entries(fam).sort((a, b) => b[1] - a[1]).slice(0, 6)

  const cmp = useMemo(() => {
    const now = weekly(V, 'now', metric, W)
    const last = weekly(V, 'last', metric, W)
    return now.map((v, i) => ({ week: i + 1, now: v == null ? null : +v.toFixed(1), last: last[i] == null ? null : +last[i].toFixed(1) })).filter((r) => r.now != null || r.last != null)
  }, [V, metric, W])
  const bands = BANDS.map((b) => ({ band: b, n: V.filter((s) => s.band === b).length }))
  const bt = B.backtest
  const curve = B.curve.map((c) => ({ week: c.week, model: Math.round(100 * c.recall), rule: Math.round(100 * c.rule) }))
  const cmpFmt = metric === 'logins' ? (v) => Number(v).toFixed(1) : (v) => `${Math.round(v)}%`

  return (
    <div className="stack">
      <PageHead title="Analytics and insights" sub={`Deeper trends for ${scopeText(role)}, and how this semester compares with last.`}
        right={isLead(role) && (
          <label className="fi">Department
            <select value={dsel} onChange={(e) => setDsel(e.target.value)}><option value="">All departments</option>{DEPTS.map((d) => <option key={d.code} value={d.code}>{d.code}</option>)}</select>
          </label>
        )} />
      <div className="stats">
        <Stat label="Academic performance" value={mean(V.map((s) => s.v.cgpa)).toFixed(2)} unit="avg CGPA" sub={`${pct(V.filter((s) => s.v.backlogs > 0).length / Math.max(V.length, 1))} have standing arrears`} />
        <Stat label="Attendance" value={`${Math.round(attNow)}%`} unit="this semester" sub={`${Math.abs(dAtt).toFixed(1)} pts vs last semester`} trend={Math.abs(dAtt) < 0.05 ? '' : dAtt > 0 ? 'good' : 'bad'} />
        <Stat label="Engagement" value={lmsNow.toFixed(1)} unit="LMS logins / week" sub={`${Math.abs(dLms).toFixed(1)} vs last semester`} trend={Math.abs(dLms) < 0.05 ? '' : dLms > 0 ? 'good' : 'bad'} />
        <Stat label="Placement" value={y34.length ? mean(y34.map((s) => s.v.mock_interviews)).toFixed(1) : 'n/a'} unit="mocks each"
          sub={y34.length ? `${pct(y34.filter((s) => s.pr === 'Low').length / y34.length)} placement-ready` : ''} />
      </div>

      <div className="grid g-main">
        <Card title="Students at risk, week by week" sub="Share of students at moderate or high risk of failing a subject, each week">
          <Columns data={riskData} x="week" xfmt={(w) => `Wk ${w}`} fmt={(v) => `${v}%`} height={290} title={(l) => `Week ${l}`}
            series={depts.map((d, i) => ({ key: d, name: d, color: SERIES[i % SERIES.length] }))} />
        </Card>
        <Card title="Risk factors" sub="Share of high-risk students showing each warning sign">
          {factors.map(([f, n]) => (
            <div key={f} style={{ marginBottom: 10 }}>
              <div className="row small" style={{ marginBottom: 4 }}><span>{f}</span><span className="spacer" /><b className="ink num">{pct(n / Math.max(hi.length, 1))}</b></div>
              <Meter value={(100 * n) / Math.max(hi.length, 1)} />
            </div>
          ))}
          {factors.length === 0 && <p className="empty">No high-risk students.</p>}
        </Card>
      </div>

      <div className="grid g-main">
        <Card title="This semester compared with last"
          right={<Seg value={metric} onChange={setMetric} label="Measure" options={[{ value: 'att', label: 'Attendance' }, { value: 'logins', label: 'LMS logins' }, { value: 'asg', label: 'Assignments submitted' }]} />}>
          <Columns data={cmp} x="week" xfmt={(w) => `Wk ${w}`} fmt={cmpFmt} height={270} title={(l) => `Week ${l}`}
            series={[{ key: 'last', name: 'Last semester', color: COL.c3 }, { key: 'now', name: 'This semester', color: COL.c1 }]} />
        </Card>
        <Card title="Success Score bands">
          <Columns data={bands} x="band" series={[{ key: 'n', name: 'Students', color: COL.c1, colors: BAND_COLORS }]} labels height={270} fmt={(v) => `${v}`} />
        </Card>
      </div>

      <Card title="Does the early warning work?"
        sub={`Tested on ${bt.test_semester}, a semester the model never saw. By week 6 it had flagged ${pct(bt.recall_by_week6)} of the students who went on to fail; the usual attendance and marks lists had flagged ${pct(bt.rule_recall_by_week6)}.`}>
        <Columns data={curve} x="week" xfmt={(w) => `Wk ${w}`} fmt={(v) => `${v}%`} domain={[0, 100]} height={280} title={(l) => `Week ${l}${l === META.cia1_week ? ' (internal marks published)' : ''}`}
          series={[{ key: 'rule', name: 'Usual lists', color: COL.c3 }, { key: 'model', name: 'EarlySignal', color: COL.c1 }]} />
        <p className="tiny" style={{ marginTop: 6 }}>Failing students already flagged by each week. Internal test marks are published in week {META.cia1_week}.</p>
      </Card>
    </div>
  )
}
