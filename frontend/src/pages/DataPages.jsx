import { B, META, STUDENTS } from '../lib/data'
import { tablePdf } from '../lib/pdf'
import { pct } from '../lib/format'
import { COL, Columns, HBars, RAMP } from '../components/charts'
import { Card, Icon, Meter, PageHead, Stat } from '../components/ui'

const PARTS = { academic: 'Academic health', engagement: 'Engagement', placement: 'Placement readiness' }

// ---------------------------------------------------------------- Data quality
export function Quality() {
  const q = B.quality
  const s = q.summary
  const src = q.sources.filter((x) => x.rows_in > 0)
  const conf = ['High', 'Medium', 'Low'].map((l) => [l, STUDENTS.filter((x) => x.conf === l).length])
  const pdf = () => tablePdf({
    title: 'Records waiting for a manual check', file: 'manual_check.pdf', landscape: false,
    subtitle: `${q.review.length} records could not be matched to a student with certainty, so they were not guessed.`,
    head: ['Source', 'Record', 'Why'], rows: q.review.map((r) => [r.source, r.record, r.reason]),
  })
  return (
    <div className="stack">
      <PageHead title="Data quality" sub="Student data comes from many systems, each naming students differently. This is how it was cleaned and joined into one record per student." />
      <div className="stats">
        <Stat label="Files joined" value={s.source_files} sub="from the college's systems" />
        <Stat label="Records read" value={s.rows_in.toLocaleString('en-IN')} sub="attendance, marks, LMS and more" />
        <Stat label="Matched to a student" value={`${s.overall_link_rate}%`} sub="5 matching methods" />
        <Stat label="Manual check needed" value={q.review_size} unit="records" sub="never guessed" />
      </div>
      {B.identity && (
        <Card title={`One student, seven different IDs: ${B.identity.name}`} flush>
          <div className="table-wrap">
            <table className="list"><thead><tr><th>System</th><th>How this student appears</th><th className="hide-sm">How we linked it</th></tr></thead>
              <tbody>{B.identity.rows.map(([a, b, c]) => <tr key={a}><td className="strong">{a}</td><td className="num">{b}</td><td className="small hide-sm">{c}</td></tr>)}</tbody></table>
          </div>
        </Card>
      )}
      <div className="grid g-main">
        <Card title="How well each source matched">
          <HBars data={src.map((x) => ({ ...x, v: x.link_rate }))} y="source" yWidth={190} domain={[0, 100]} series={[{ key: 'v', name: 'Matched', color: COL.c1 }]} fmt={(v) => `${v}%`} />
        </Card>
        <Card title="Data confidence per student" foot="Confidence is the share of a student's score backed by real data, not filled-in values. Low usually means no survey response, no skills test, or a source the college has not uploaded.">
          {conf.map(([l, n]) => (
            <div key={l} style={{ marginBottom: 12 }}>
              <div className="row small" style={{ marginBottom: 4 }}><span>{l}</span><span className="spacer" /><b className="ink num">{n}</b></div>
              <Meter value={(100 * n) / Math.max(STUDENTS.length, 1)} />
            </div>
          ))}
        </Card>
      </div>
      <details className="card">
        <summary className="card-head" style={{ cursor: 'pointer' }}><h2>Cleaning done, source by source</h2></summary>
        <div className="table-wrap">
          <table className="list"><thead><tr><th>Source</th><th className="hide-sm">System</th><th className="hide-sm">Student ID used</th><th className="r">Rows</th><th className="r">Matched</th><th>What was fixed</th></tr></thead>
            <tbody>{src.map((x) => <tr key={x.source}><td className="strong">{x.source}</td><td className="hide-sm">{x.system}</td><td className="small hide-sm">{x.identifier}</td><td className="r num">{x.rows_in.toLocaleString('en-IN')}</td><td className="r num">{x.link_rate}%</td>
              <td className="small">{Object.entries(x.issues || {}).map(([k, v]) => `${k}: ${Number(v).toLocaleString('en-IN')}`).join('; ') || 'Nothing needed'}</td></tr>)}</tbody></table>
        </div>
      </details>
      <details className="card">
        <summary className="card-head" style={{ cursor: 'pointer' }}><h2>Records waiting for a manual check ({q.review_size})</h2></summary>
        <div className="card-body"><button type="button" className="btn" onClick={pdf} disabled={!q.review.length}><Icon name="download" size={16} />Download the list (PDF)</button></div>
        <div className="table-wrap" style={{ maxHeight: 320 }}>
          <table className="list"><thead><tr><th>Source</th><th>Record</th><th>Why</th></tr></thead>
            <tbody>{q.review.map((r, i) => <tr key={i}><td>{r.source}</td><td className="small">{r.record}</td><td className="small">{r.reason}</td></tr>)}</tbody></table>
        </div>
      </details>
    </div>
  )
}

// ---------------------------------------------------------------- How it works
export function How() {
  const bt = B.backtest
  const curve = B.curve.map((c) => ({ week: c.week, model: Math.round(100 * c.recall), rule: Math.round(100 * c.rule) }))
  const years = Object.keys(B.weights)
  const weightRows = years.map((y) => {
    const row = { year: `Year ${y}` }
    for (const p of Object.keys(PARTS)) row[p] = Math.round(100 * B.indicators.filter((i) => i.part === p && i.key in B.weights[y]).reduce((a, i) => a + B.weights[y][i.key], 0))
    return row
  })
  return (
    <div className="stack">
      <PageHead title="How scores work" sub="Two numbers appear everywhere in EarlySignal: the Success Score (how a student is doing now) and the risk level (how likely things are to go wrong this semester)." />
      <div className="grid g2">
        <Card title="Success Score, 0 to 100">
          <p>A mix of three parts, each built from things the college already records:</p>
          <ul className="reasons" style={{ margin: '8px 0' }}>
            <li><span className="strong">Academic health:</span> CGPA, internal test marks, attendance, arrears, faculty rating</li>
            <li><span className="strong">Engagement:</span> LMS logins, assignments, whether these are rising or falling, events and clubs, satisfaction survey</li>
            <li><span className="strong">Placement readiness:</span> aptitude, coding, mock interviews, skills tests, certifications, recruiter eligibility</li>
          </ul>
          <p><span className="strong">It works like a marksheet out of 100.</span> Each item has maximum marks. A student gets full marks at a top level (CGPA 9.5 or more), zero at a bottom level (CGPA 5.0 or less), and part marks in between. Every student's profile shows their full marksheet.</p>
          <p style={{ marginTop: 8 }}><b className="ink">70 and above</b> thriving, <b className="ink">55 to 70</b> on track, <b className="ink">40 to 55</b> needs attention, <b className="ink">below 40</b> at risk.</p>
        </Card>
        <Card title="Risk level">
          <p>Each week a model estimates the chance that a student fails at least one subject this semester. <b className="ink">High</b> is {pct(META.risk_high)} or more, <b className="ink">Medium</b> {pct(META.risk_medium)} to {pct(META.risk_high)}, <b className="ink">Low</b> below that.</p>
          <p style={{ marginTop: 8 }}><span className="strong">Does it work?</span> We tested it on a past semester it had never seen. By week 6 it had flagged <b className="ink">{pct(bt.recall_by_week6)}</b> of the students who went on to fail. The usual attendance and marks lists had flagged <b className="ink">{pct(bt.rule_recall_by_week6)}</b>.</p>
        </Card>
      </div>
      <Card title="Proof: the model warns earlier than the usual lists" sub="Share of failing students already flagged, week by week"
        foot={`Trained on ${bt.train_semester}, tested on ${bt.test_semester}. Internal test marks come out in week ${META.cia1_week}; before that, attendance, LMS and assignment signals show up weeks before marks do.`}>
        <Columns data={curve} x="week" xfmt={(w) => `Wk ${w}`} fmt={(v) => `${v}%`} domain={[0, 100]} height={290} title={(l) => `Week ${l}`}
          series={[{ key: 'rule', name: 'Usual lists (attendance shortage and low marks)', color: COL.c3 }, { key: 'model', name: 'EarlySignal', color: COL.c1 }]} />
      </Card>
      <Card title="How much each part counts" sub="Placement counts more as students get closer to placement season.">
        <HBars data={weightRows} y="year" yWidth={60} stacked domain={[0, 100]} fmt={(v) => `${v}%`}
          series={Object.entries(PARTS).map(([k, l], i) => ({ key: k, name: l, color: RAMP[i] }))} />
      </Card>
      <details className="card">
        <summary className="card-head" style={{ cursor: 'pointer' }}><h2>Every indicator and its weight</h2></summary>
        <div className="table-wrap">
          <table className="list">
            <thead><tr><th>Indicator</th><th>Part</th><th>Scored from 0 to 1 between</th>{years.map((y) => <th key={y} className="r">Year {y}</th>)}</tr></thead>
            <tbody>{B.indicators.map((i) => (
              <tr key={i.key}><td>{i.label}</td><td className="small">{PARTS[i.part]}</td><td className="small">{i.invert ? `${i.hi} and ${i.lo}` : `${i.lo} and ${i.hi}`}</td>
                {years.map((y) => <td key={y} className="r num">{i.key in B.weights[y] ? `${(100 * B.weights[y][i.key]).toFixed(1)}%` : '-'}</td>)}</tr>
            ))}</tbody>
          </table>
        </div>
      </details>
      <details className="card">
        <summary className="card-head" style={{ cursor: 'pointer' }}><h2>Limits and safeguards</h2></summary>
        <div className="card-body">
          <ul className="reasons">
            <li>This prototype uses realistic made-up data that mimics real campus systems, including their mistakes. Real data will be noisier, so the model should be re-checked every semester.</li>
            <li>Scores start a conversation with a student. They never decide anything about a student on their own.</li>
            <li>Placement weights were learned from last year's graduates and who got placed.</li>
            <li>The simple model was chosen on purpose: every flag can be explained in plain words.</li>
          </ul>
        </div>
      </details>
    </div>
  )
}
