// Data sources (admin and principal): connect read-only to the college's ERP and Moodle databases and sync, or upload
// the Excel template. Same steps as the Round 1 page; the work is done by the EarlySignal server (api.py).
import { useEffect, useMemo, useState } from 'react'
import { B, META } from '../lib/data'
import { adminKey, api, follow, server, setAdminKey } from '../lib/server'
import { Card, Icon, PageHead, Pill, Seg, Stat, Tabs } from '../components/ui'

const STATUS = { ok: ['OK', 'p-low'], warn: ['Check', 'p-med'], skip: ['Skipped', 'p-grey'], error: ['Fix', 'p-high'] }
const RANK = { error: 3, warn: 2, ok: 1, skip: 0 }
const reload = () => { window.location.hash = '#/'; window.location.reload() }

// ---------------------------------------------------------------- shared pieces
function Checks({ checks }) {
  const by = {}
  for (const c of checks) (by[c.sheet] ||= []).push(c)
  return (
    <div className="checks">
      {Object.entries(by).map(([sheet, list]) => {
        const worst = list.reduce((a, c) => (RANK[c.status] > RANK[a] ? c.status : a), 'skip')
        return (
          <div key={sheet} className="chk">
            <Pill kind={STATUS[worst][1]}>{STATUS[worst][0]}</Pill>
            <b>{sheet}</b>
            <span>{list.map((c) => c.text).join(' ')}</span>
          </div>
        )
      })}
    </div>
  )
}

function Log({ lines, running }) {
  if (!lines.length && !running) return null
  return (
    <div className="log" aria-live="polite">
      {lines.slice(-14).map((l, i) => <div key={i}>{l}</div>)}
      {running && <div className="muted">Working...</div>}
    </div>
  )
}

function Rows({ columns, rows, note }) {
  return (
    <div style={{ marginTop: 10 }}>
      {note && <p className="tiny" style={{ marginBottom: 6 }}>{note}</p>}
      <div className="table-wrap" style={{ maxHeight: 320, border: '1px solid var(--line)', borderRadius: 8 }}>
        <table className="list">
          <thead><tr>{columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
          <tbody>{rows.map((r, i) => <tr key={i}>{r.map((v, k) => <td key={k} className="small nowrap">{v == null ? '' : String(v)}</td>)}</tr>)}</tbody>
        </table>
      </div>
    </div>
  )
}

// A background job (start the demo server, sync, upload, reset), with its progress lines.
function useJob() {
  const [lines, setLines] = useState([])
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')
  const run = async (start) => {
    setLines([]); setError(''); setRunning(true)
    try {
      const { job } = await start()
      const j = await follow(job, (l) => setLines((x) => [...x, l]))
      return j
    } catch (e) {
      setError(e.message)
      return null
    } finally {
      setRunning(false)
    }
  }
  return { lines, running, error, run, setError }
}

function currentSource(src) {
  if (META.using_sample) return 'Showing: sample college data.'
  if (src?.type === 'server') return `Showing: live server data (${META.college}), synced ${src.synced_at || ''}.`
  if (src?.type === 'upload') return `Showing: your uploaded data (${META.college}), uploaded ${src.uploaded_at || ''}.`
  return `Showing: ${META.college} data.`
}

// ---------------------------------------------------------------- college server
function ServerForm({ title, value, onChange, dialects }) {
  const set = (k) => (e) => onChange({ ...value, [k]: k === 'port' ? e.target.value.replace(/\D/g, '') : e.target.value })
  const pick = (e) => {
    const d = dialects.find((x) => x.name === e.target.value)
    onChange({ ...value, dialect: d.name, port: String(d.port || '') })
  }
  return (
    <div className="stack" style={{ gap: 10 }}>
      <div className="strong">{title}</div>
      <label className="fi">Database type
        <select value={value.dialect} onChange={pick}>{dialects.map((d) => <option key={d.name}>{d.name}</option>)}</select>
      </label>
      <div className="two-col">
        <label className="fi">Server address<input type="text" value={value.host} onChange={set('host')} placeholder="e.g. 10.0.4.12 or erp.college.edu.in" /></label>
        <label className="fi">Port<input type="text" inputMode="numeric" value={value.port} onChange={set('port')} /></label>
      </div>
      <label className="fi">Database name<input type="text" value={value.database} onChange={set('database')} placeholder={title.startsWith('Moodle') ? 'e.g. moodle' : 'e.g. college_erp'} /></label>
      <div className="two-col">
        <label className="fi">Read-only username<input type="text" value={value.username} onChange={set('username')} autoComplete="off" /></label>
        <label className="fi">Password<input type="password" value={value.password} onChange={set('password')} autoComplete="new-password" />
          <span className="hint">Used for this session only. Never saved.</span>
        </label>
      </div>
    </div>
  )
}

const blank = (d) => ({ dialect: d?.name || 'MySQL / MariaDB', host: '', port: String(d?.port || 3306), database: '', username: '', password: '' })
const fromSaved = (s, dialects) => (s && s.dialect && s.dialect !== 'SQLite file'
  ? { dialect: s.dialect, host: s.host || '', port: String(s.port || ''), database: s.database || '', username: s.username || '', password: '' }
  : blank(dialects[0]))

function LookInside({ body, tables }) {
  const opts = tables.map((t) => `${t.server === 'erp' ? 'ERP' : 'Moodle'} · ${t.table}`)
  const [pick, setPick] = useState(() => Math.max(0, opts.indexOf('ERP · attendance')))
  const [res, setRes] = useState(null)
  const [busy, setBusy] = useState(false)
  if (!tables.length) return null
  const show = async () => {
    setBusy(true)
    try {
      const t = tables[pick]
      setRes(await api('preview', { method: 'POST', body: { ...body, server: t.server, table: t.table } }))
    } catch (e) {
      setRes({ ok: false, error: e.message })
    }
    setBusy(false)
  }
  return (
    <details className="more">
      <summary>Look inside the server: raw tables, read live</summary>
      <div className="more-body">
        <p className="small muted">The data exactly as the college systems keep it. Pick a table to read its first rows straight from the database (read-only).</p>
        {tables[0].rows != null && (
          <div className="table-wrap" style={{ maxHeight: 220, border: '1px solid var(--line)', borderRadius: 8, margin: '10px 0' }}>
            <table className="list"><thead><tr><th>Database</th><th>Table</th><th className="r">Rows</th></tr></thead>
              <tbody>{tables.map((t) => <tr key={t.server + t.table}><td>{t.server === 'erp' ? 'ERP' : 'Moodle'}</td><td>{t.table}</td><td className="r num">{t.rows?.toLocaleString('en-IN')}</td></tr>)}</tbody></table>
          </div>
        )}
        <div className="row wrap" style={{ alignItems: 'flex-end' }}>
          <label className="fi" style={{ flex: '1 1 240px' }}>Table<select value={pick} onChange={(e) => setPick(Number(e.target.value))}>{opts.map((o, i) => <option key={o} value={i}>{o}</option>)}</select></label>
          <button type="button" className="btn" onClick={show} disabled={busy}><Icon name="layers" size={16} />{busy ? 'Reading...' : 'Show the first rows'}</button>
        </div>
        {res && (res.ok ? <Rows columns={res.columns} rows={res.rows} note={`${res.sql}: first ${res.rows.length} rows in ${res.secs} s.`} /> : <p className="err" style={{ marginTop: 10 }}>{res.error}</p>)}
      </div>
    </details>
  )
}

function ProveLive({ onChanged }) {
  const [st, setSt] = useState(null)
  const [pick, setPick] = useState('')
  const [err, setErr] = useState('')
  const job = useJob()
  const load = () => api('demo/live').then((r) => { setSt(r); setPick((p) => p || r.candidates?.[0]?.roll || '') }).catch((e) => setErr(e.message))
  useEffect(() => { load() }, [])
  if (!st) return null
  const record = async () => {
    setErr('')
    try { await api('demo/live', { method: 'POST', body: { roll: pick } }); await load(); onChanged?.() } catch (e) { setErr(e.message) }
  }
  const undo = async () => { await job.run(() => api('demo/undo', { method: 'POST' })); await load() }
  const sim = st.sim
  return (
    <Card title="Prove it's live: change the server, then sync"
      sub="Play the college's own systems for a moment: record on the demo server that a student who is doing well stopped coming to class from week 7. The dashboard changes only after EarlySignal syncs. (EarlySignal itself never writes: this button acts as the college's attendance system and Moodle.)">
      {!sim && !st.candidates.length && <p className="note">Sync from the demo server first (step 3), then come back here.</p>}
      {!sim && st.candidates.length > 0 && (
        <div className="row wrap" style={{ alignItems: 'flex-end' }}>
          <label className="fi" style={{ flex: '1 1 320px' }}>Student
            <select value={pick} onChange={(e) => setPick(e.target.value)}>
              {st.candidates.map((c) => <option key={c.roll} value={c.roll}>{c.name} ({c.roll}, {c.dept} year {c.year}): score {c.score}, attendance {c.att}%</option>)}
            </select>
          </label>
          <button type="button" className="btn primary" onClick={record} disabled={!pick}>Record it on the college server</button>
        </div>
      )}
      {sim && (
        <div className="stack" style={{ gap: 12 }}>
          <p className="ok">The server now says {sim.name} ({sim.roll}) was absent for {sim.change.attendance} class hours since {sim.change.from_date}, with {sim.change.logins} Moodle log-ins and {sim.change.submissions} assignment submissions removed.</p>
          {!sim.synced && <p className="small"><b className="ink">Now press "Sync now and build" in step 3.</b> EarlySignal will read the changed records and every page will update.</p>}
          {sim.synced && st.after && (
            <div className="table-wrap" style={{ border: '1px solid var(--line)', borderRadius: 8 }}>
              <table className="list">
                <thead><tr><th>What EarlySignal shows for {sim.name}</th><th>Before</th><th>After sync</th></tr></thead>
                <tbody>
                  {[['Attendance this semester', `${Math.round(sim.before.att)}%`, `${Math.round(st.after.att)}%`],
                    ['Moodle log-ins per week', sim.before.lms?.toFixed(1), st.after.lms?.toFixed(1)],
                    ['Assignments submitted', `${Math.round(sim.before.asg)}%`, `${Math.round(st.after.asg)}%`],
                    ['Attendance by semester end (75% needed)', `${Math.round(sim.before.proj)}%`, `${Math.round(st.after.proj)}%`],
                    ['Risk level', sim.before.risk, st.after.risk], ['Main reason shown to the mentor', sim.before.reason, st.after.reason],
                    ['Success Score', Math.round(sim.before.score), Math.round(st.after.score)], ['Group', sim.before.segment, st.after.segment]]
                    .map(([k, a, b]) => <tr key={k}><td>{k}</td><td>{a}</td><td className="strong">{b}</td></tr>)}
                </tbody>
              </table>
            </div>
          )}
          <div className="row wrap">
            {sim.synced && <a className="btn" href={`#/student/${sim.roll}`} onClick={(e) => { e.preventDefault(); window.location.hash = `#/student/${sim.roll}`; window.location.reload() }}><Icon name="user" size={16} />Open {sim.name}'s profile</a>}
            <button type="button" className="btn" onClick={undo} disabled={job.running}>{job.running ? 'Rebuilding the demo server...' : 'Undo: rebuild the demo server'}</button>
          </div>
          <Log lines={job.lines} running={job.running} />
        </div>
      )}
      {(err || job.error) && <p className="err" style={{ marginTop: 10 }}>{err || job.error}</p>}
    </Card>
  )
}

function ServerTab({ info, reloadInfo }) {
  const dialects = info.dialects.filter((d) => d.name !== 'SQLite file')
  const [mode, setMode] = useState(info.conn?.mode === 'server' ? 'server' : 'demo')
  const [erp, setErp] = useState(() => fromSaved(info.conn?.erp, dialects))
  const [useLms, setUseLms] = useState(!!info.conn?.lms && info.conn.lms.dialect !== 'SQLite file')
  const [lms, setLms] = useState(() => fromSaved(info.conn?.lms, dialects))
  const [tested, setTested] = useState(null)
  const [demoTables, setDemoTables] = useState([])
  const [slots, setSlots] = useState(info.slots)
  const [slot, setSlot] = useState(info.slots[0]?.slot)
  const [sql, setSql] = useState(info.slots[0]?.sql || '')
  const [qmsg, setQmsg] = useState(null)
  const [runRes, setRunRes] = useState(null)
  const [report, setReport] = useState({})
  const [name, setName] = useState(info.conn?.college_name || (mode === 'demo' ? 'Demo College' : ''))
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState('')
  const demoJob = useJob()
  const syncJob = useJob()
  const resetJob = useJob()

  useEffect(() => { if (info.demo_exists) api('demo/tables').then((r) => setDemoTables(r.tables)).catch(() => {}) }, [info.demo_exists])
  useEffect(() => { const s = slots.find((x) => x.slot === slot); setSql(s ? s.sql : ''); setQmsg(null); setRunRes(null) }, [slot]) // eslint-disable-line react-hooks/exhaustive-deps

  const cfg = (v) => ({ dialect: v.dialect, host: v.host.trim(), port: v.port ? Number(v.port) : null, database: v.database.trim(), username: v.username.trim() })
  const body = mode === 'demo' ? { mode: 'demo' }
    : { mode: 'server', erp: cfg(erp), lms: useLms ? cfg(lms) : null, passwords: { erp: erp.password, lms: useLms ? lms.password : '' } }
  const ready = mode === 'demo' ? info.demo_exists : !!erp.database.trim()

  const startDemo = async () => { await demoJob.run(() => api('demo/start', { method: 'POST' })); reloadInfo() }
  const test = async () => {
    setBusy('test'); setTested(null)
    try { setTested(await api('test', { method: 'POST', body })) } catch (e) { setTested({ error: e.message }) }
    setBusy('')
  }
  const saveQuery = async (value) => {
    setQmsg(null)
    try {
      const r = await api('queries', { method: 'POST', body: { slot, sql: value } })
      setSlots((xs) => xs.map((x) => (x.slot === slot ? { ...x, sql: value ?? x.default, edited: r.edited } : x)))
      if (value === null) setSql(slots.find((x) => x.slot === slot).default)
      setQmsg({ ok: true, text: value === null ? 'Back to the default query.' : 'Saved.' })
    } catch (e) { setQmsg({ ok: false, text: e.message }) }
  }
  const runQuery = async () => {
    setBusy('run'); setRunRes(null)
    const s = slots.find((x) => x.slot === slot)
    try { setRunRes(await api('preview', { method: 'POST', body: { ...body, server: s.server, sql } })) } catch (e) { setRunRes({ ok: false, error: e.message }) }
    setBusy('')
  }
  const sync = async () => {
    setResult(null)
    const j = await syncJob.run(() => api('sync', { method: 'POST', body: { ...body, college_name: name } }))
    if (j) {
      setResult(j.result)
      if (j.result?.report) setReport(Object.fromEntries(j.result.report.map((r) => [r.slot, r])))
    }
  }
  const reset = async () => {
    const j = await resetJob.run(() => api('reset', { method: 'POST' }))
    if (j?.state === 'done') reload()
  }
  const testTables = tested && !tested.error
    ? ['erp', 'lms'].filter((k) => tested[k]?.ok).flatMap((k) => tested[k].tables.map((t) => ({ server: k, table: t, rows: null }))) : []
  const lookTables = mode === 'demo' ? demoTables.map((t) => ({ server: t.db === 'ERP' ? 'erp' : 'lms', table: t.table, rows: t.rows })) : testTables
  const cur = slots.find((x) => x.slot === slot)
  const att = demoTables.filter((t) => t.table === 'attendance').reduce((a, t) => a + t.rows, 0)

  return (
    <div className="stack">
      <div className="flow">
        <div><div className="h"><span>1</span>Connect read-only</div><div className="d">The college's IT team creates a <b>read-only login</b> on the ERP database (and on Moodle, if used). EarlySignal can look, never change.</div></div>
        <div><div className="h"><span>2</span>Map once</div><div className="d">A few <b>SELECT queries</b> tell EarlySignal where students, marks and attendance live. Defaults fit common ERPs; IT adjusts table names once.</div></div>
        <div><div className="h"><span>3</span>Sync every night</div><div className="d">New attendance, marks and LMS activity flow in <b>automatically</b> and every page rebuilds. No more spreadsheets.</div></div>
      </div>

      <Card title="1. Connect" right={<Seg value={mode} onChange={(m) => { setMode(m); setTested(null); if (!name || name === 'Demo College') setName(m === 'demo' ? 'Demo College' : '') }} label="Server"
        options={[{ value: 'demo', label: 'Demo college server' }, { value: 'server', label: "My college's server" }]} />}>
        {mode === 'demo' ? (
          <div className="stack" style={{ gap: 12 }}>
            <p className="small muted">A demo college ERP and a Moodle LMS, laid out the way colleges really store data: attendance is one row per student per class hour, and Moodle uses its own table names. Built from the sample college, so you can try every step.</p>
            {!info.demo_exists ? (
              <div className="row"><button type="button" className="btn primary" onClick={startDemo} disabled={demoJob.running}><Icon name="sources" size={16} />{demoJob.running ? 'Creating the demo databases (about 15 seconds)...' : 'Start the demo server'}</button></div>
            ) : (
              <div className="stats k3">
                <Stat label="ERP database" value={demoTables.filter((t) => t.db === 'ERP').length} unit="tables" sub="students, marks, attendance" />
                <Stat label="Attendance rows" value={att.toLocaleString('en-IN')} sub="one per student per class hour" />
                <Stat label="Moodle database" value={demoTables.filter((t) => t.db === 'Moodle').length} unit="tables" sub="logins and assignments" />
              </div>
            )}
            <Log lines={demoJob.lines} running={demoJob.running} />
            {demoJob.error && <p className="err">{demoJob.error}</p>}
          </div>
        ) : (
          <div className="stack" style={{ gap: 14 }}>
            <div className="grid g2" style={{ gap: 24 }}>
              <ServerForm title="College ERP database (needed)" value={erp} onChange={setErp} dialects={dialects} />
              <div className="stack" style={{ gap: 10 }}>
                <label className="row small strong" style={{ gap: 8 }}><input type="checkbox" checked={useLms} onChange={(e) => setUseLms(e.target.checked)} />We use Moodle (optional)</label>
                {useLms && <ServerForm title="Moodle database" value={lms} onChange={setLms} dialects={dialects} />}
              </div>
            </div>
            <div className="row"><button type="button" className="btn" onClick={test} disabled={!erp.database.trim() || busy === 'test'}><Icon name="link" size={16} />{busy === 'test' ? 'Testing...' : 'Test connection'}</button></div>
            {tested?.error && <p className="err">{tested.error}</p>}
            {tested && !tested.error && ['erp', 'lms'].filter((k) => tested[k]).map((k) => (
              <p key={k} className={tested[k].ok ? 'ok' : 'err'}>{k === 'erp' ? 'ERP' : 'Moodle'}: {tested[k].message}</p>
            ))}
            <p className="tiny">EarlySignal must be able to reach the server: run it inside the campus network or over the college VPN. Ask IT for a login that can only SELECT. Supported: MySQL / MariaDB, PostgreSQL, SQL Server, Oracle.</p>
          </div>
        )}
        <LookInside body={body} tables={lookTables} />
      </Card>

      <Card title="2. Map your tables" sub="EarlySignal reads with these SELECT queries. They match the demo server and a typical ERP; for a real college the IT team changes table and column names once. Anything that is not a single SELECT is refused." flush>
        <div className="table-wrap">
          <table className="list">
            <thead><tr><th>What it reads</th><th>From</th><th>Needed?</th><th>Query</th><th className="hide-sm">Last run</th></tr></thead>
            <tbody>
              {slots.map((s) => {
                const r = report[s.slot]
                return (
                  <tr key={s.slot} className={`click ${s.slot === slot ? 'sel' : ''}`} onClick={() => setSlot(s.slot)}>
                    <td>{s.label}</td><td>{s.server === 'erp' ? 'ERP' : 'Moodle'}</td>
                    <td>{s.need ? <Pill kind="p-brand">Needed</Pill> : <Pill>Optional</Pill>}</td>
                    <td className="small">{s.edited ? 'Edited' : 'Default'}</td>
                    <td className="small hide-sm">{!r ? '-' : r.error ? `Error: ${r.error.slice(0, 60)}` : `${r.rows?.toLocaleString('en-IN')} rows in ${r.secs} s`}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        <div className="pad stack" style={{ gap: 10 }}>
          <label className="fi">See or edit a query
            <select value={slot} onChange={(e) => setSlot(e.target.value)}>{slots.map((s) => <option key={s.slot} value={s.slot}>{s.label}</option>)}</select>
          </label>
          <textarea className="sql" value={sql} onChange={(e) => setSql(e.target.value)} spellCheck={false} aria-label="SQL query" rows={9} />
          <div className="row wrap">
            <button type="button" className="btn" onClick={() => saveQuery(sql.trim() === cur?.default ? null : sql)}><Icon name="check" size={16} />Save query</button>
            <button type="button" className="btn" onClick={() => saveQuery(null)} disabled={!cur?.edited && sql === cur?.default}>Reset to default</button>
            <button type="button" className="btn" onClick={runQuery} disabled={!ready || busy === 'run'}><Icon name="play" size={14} />{busy === 'run' ? 'Running...' : 'Run on the server'}</button>
          </div>
          {qmsg && <p className={qmsg.ok ? 'ok' : 'err'}>{qmsg.text}</p>}
          {runRes && (runRes.ok ? <Rows columns={runRes.columns} rows={runRes.rows} note={`First ${runRes.rows.length} rows, straight from the database (${runRes.secs} s, read-only).`} /> : <p className="err">{runRes.error}</p>)}
        </div>
      </Card>

      <Card title="3. Sync and build" foot="Reads the latest data, checks it, and rebuilds every page in about a minute. If anything fails, the dashboard keeps the previous data.">
        <div className="row wrap" style={{ alignItems: 'flex-end', gap: 12 }}>
          <label className="fi" style={{ flex: '1 1 260px' }}>College name<input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Sri Venkateswara College of Engineering" /></label>
          <button type="button" className="btn primary" onClick={sync} disabled={!ready || syncJob.running}><Icon name="sources" size={16} />{syncJob.running ? 'Syncing...' : 'Sync now and build'}</button>
          <button type="button" className="btn" onClick={reset} disabled={META.using_sample || resetJob.running}>{resetJob.running ? 'Switching back...' : 'Switch back to the sample college'}</button>
        </div>
        <Log lines={[...syncJob.lines, ...resetJob.lines]} running={syncJob.running || resetJob.running} />
        {(syncJob.error || resetJob.error) && <p className="err" style={{ marginTop: 10 }}>{syncJob.error || resetJob.error}</p>}
        {result && (
          <div className="stack" style={{ gap: 10, marginTop: 12 }}>
            {result.report?.length > 0 && (
              <Rows columns={['What it reads', 'Rows', 'Seconds', 'Problem']} rows={result.report.map((r) => [r.label, r.rows == null ? '-' : r.rows.toLocaleString('en-IN'), r.secs, r.error || ''])} />
            )}
            {(result.notes || []).map((n) => <p key={n} className="tiny">{n}</p>)}
            {(result.errors || []).map((e) => <p key={e} className="err">{e}</p>)}
            {result.checks?.length > 0 && <Checks checks={result.checks} />}
            {result.built ? (
              <div className="ok row wrap">Done. Every page now uses the data from the college server.<span className="spacer" /><button type="button" className="btn sm primary" onClick={reload}>Open the updated dashboard</button></div>
            ) : result.ok ? <p className="err">The data was read and checked, but the rebuild did not finish, so the previous data is kept.</p>
              : result.checks?.length ? <p className="err">The data was read, but some checks failed (marked Fix). Adjust the queries in step 2.</p> : null}
          </div>
        )}
      </Card>

      {mode === 'demo' && info.demo_exists && <ProveLive />}

      <details className="card more">
        <summary className="card-head"><h2>Automatic nightly sync</h2></summary>
        <div className="pad stack" style={{ gap: 8 }}>
          <p className="small">Run EarlySignal on a computer <b>inside the campus network</b> (or connected over the college VPN), connect once on this page, then add one line to the scheduler. Every night it reads the new attendance, marks and Moodle activity and rebuilds every page. If the server is down, the previous day's data stays.</p>
          <p className="small strong">Linux (cron):</p>
          <pre className="code">0 2 * * *  cd /path/to/earlysignal && EARLYSIGNAL_ERP_PASSWORD='...' EARLYSIGNAL_LMS_PASSWORD='...' python -m src.sync &gt;&gt; sync.log 2&gt;&amp;1</pre>
          <p className="small"><b className="ink">Windows (Task Scheduler):</b> run <code>python -m src.sync</code> in the EarlySignal folder every night, with the two passwords set as environment variables. To try it on the demo server: <code>python -m src.sync --demo</code>.</p>
        </div>
      </details>
      <details className="card more">
        <summary className="card-head"><h2>How colleges store this data, and how EarlySignal reaches it</h2></summary>
        <div className="table-wrap">
          <table className="list">
            <thead><tr><th>Data</th><th>Where it usually lives</th><th>How EarlySignal reads it</th></tr></thead>
            <tbody>
              {[['Students, attendance, internal marks, results', "College ERP database (MySQL, PostgreSQL, SQL Server or Oracle) on a campus server or the vendor's cloud", "Read-only SQL login (or the vendor's report API)"],
                ['Online activity, assignments', 'Moodle database (MySQL or PostgreSQL)', "Read-only SQL login on Moodle's own tables"],
                ['University exam results', 'Excel or PDF from the university portal, often imported into the ERP', 'From the ERP once imported, or the Excel upload'],
                ['Placement training, events, feedback', 'Excel sheets and Google Forms kept by each office', 'The Excel upload tab, until they move into the ERP']].map((r) => <tr key={r[0]}>{r.map((c) => <td key={c} className="small">{c}</td>)}</tr>)}
            </tbody>
          </table>
        </div>
        <div className="pad">
          <p className="small"><b className="ink">What the college needs to provide:</b> a read-only database login, network access from the EarlySignal machine (same campus network or VPN), and approval under its data policy. Under India's Digital Personal Data Protection Act, 2023 the college stays responsible for its students' data, so EarlySignal reads only the columns it needs, never writes, and never stores passwords.</p>
        </div>
      </details>
    </div>
  )
}

// ---------------------------------------------------------------- Excel upload
function ExcelTab({ info }) {
  const [files, setFiles] = useState([])
  const [check, setCheck] = useState(null)
  const [checking, setChecking] = useState(false)
  const [name, setName] = useState(META.using_sample ? '' : META.college)
  const [result, setResult] = useState(null)
  const buildJob = useJob()
  const resetJob = useJob()
  const upload = async (list) => {
    setFiles(list); setCheck(null); setResult(null)
    if (!list.length) return
    setChecking(true)
    const form = new FormData()
    for (const f of list) form.append('files', f, f.name)
    try { setCheck(await api('upload/check', { method: 'POST', form })) } catch (e) { setCheck({ ok: false, error: e.message }) }
    setChecking(false)
  }
  const build = async () => {
    const j = await buildJob.run(() => api('upload/build', { method: 'POST', body: { token: check.token, college_name: name } }))
    if (j) { setResult(j.result); setCheck(null) }
  }
  const reset = async () => {
    const j = await resetJob.run(() => api('reset', { method: 'POST' }))
    if (j?.state === 'done') reload()
  }
  const f = check?.facts
  return (
    <div className="stack">
      <Card title="1. Download the template">
        <div className="grid g2" style={{ gap: 24 }}>
          <div className="stack" style={{ gap: 10 }}>
            <p className="small muted">One Excel file with a sheet for each kind of record. Only the first three sheets are needed.</p>
            <a className="btn primary" href="api/template" download><Icon name="download" size={16} />Download the template (Excel)</a>
            {info.example && <a className="btn" href="api/example" download><Icon name="file" size={16} />Download a filled example</a>}
            {info.example && <p className="tiny">360 sample CSE students, to see what goes where. You can upload it to try the steps.</p>}
            <ol className="steps">
              <li><span className="small">Use the <b>same Roll No</b> in every sheet.</span></li>
              <li><span className="small"><b>Semester</b> means the semester number, 1 to 8.</span></li>
              <li><span className="small">Include <b>this semester and the two before it</b>. The early warning learns from the two past semesters.</span></li>
            </ol>
          </div>
          <div>
            {info.sheets.map((s) => (
              <div key={s.name} className="sheetrow"><b>{s.name}</b>{s.required ? <Pill kind="p-brand">Needed</Pill> : <Pill>Optional</Pill>}<span>{s.per}</span></div>
            ))}
            <p className="tiny" style={{ marginTop: 8 }}>Column names can differ a little (CIA 1, Internal 1 and Test 1 all work). Example rows are ignored. Separate CSV files, one per sheet, also work.</p>
          </div>
        </div>
      </Card>

      <Card title="2. Upload the filled file">
        <label className="drop">
          <input type="file" accept=".xlsx,.xlsm,.csv" multiple onChange={(e) => upload([...e.target.files])} />
          <Icon name="download" size={20} style={{ transform: 'rotate(180deg)' }} />
          <span><b>Choose the Excel workbook</b>, or one CSV per sheet</span>
          {files.length > 0 && <span className="tiny">{files.map((x) => x.name).join(', ')}</span>}
        </label>
        {checking && <p className="small muted" style={{ marginTop: 10 }}>Reading and checking your file...</p>}
        {check?.error && <p className="err" style={{ marginTop: 10 }}>{check.error}</p>}
        {check?.checks && (
          <div className="stack" style={{ gap: 10, marginTop: 12 }}>
            <Checks checks={check.checks} />
            {check.notes.map((n) => <p key={n} className="tiny">{n}</p>)}
            {check.ok ? <p className="ok">Ready: {f.students.toLocaleString('en-IN')} students in {f.depts} department(s). Week {f.week} of {f.weeks_per_sem} this semester.</p>
              : <p className="err">Fix the items marked Fix in your file and upload it again.</p>}
          </div>
        )}
      </Card>

      <Card title="3. Build your dashboard" foot="Takes about a minute. If anything goes wrong, nothing changes. Only the college name is typed; semesters, current week and departments are read from your file.">
        <div className="row wrap" style={{ alignItems: 'flex-end', gap: 12 }}>
          <label className="fi" style={{ flex: '1 1 260px' }}>College name<input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Sri Venkateswara College of Engineering" /></label>
          <button type="button" className="btn primary" onClick={build} disabled={!check?.ok || buildJob.running}><Icon name="star" size={16} />{buildJob.running ? 'Building...' : 'Build my dashboard'}</button>
          <button type="button" className="btn" onClick={reset} disabled={META.using_sample || resetJob.running}>{resetJob.running ? 'Switching back...' : 'Switch back to the sample college'}</button>
        </div>
        <Log lines={[...buildJob.lines, ...resetJob.lines]} running={buildJob.running || resetJob.running} />
        {(buildJob.error || resetJob.error) && <p className="err" style={{ marginTop: 10 }}>{buildJob.error || resetJob.error}</p>}
        {result && (result.built
          ? <div className="ok row wrap" style={{ marginTop: 12 }}>Done. Every page now uses your college's data.<span className="spacer" /><button type="button" className="btn sm primary" onClick={reload}>Open the updated dashboard</button></div>
          : <p className="err" style={{ marginTop: 12 }}>{(result.errors || []).join(' ') || 'The data could not be processed, so nothing was changed.'}</p>)}
      </Card>
    </div>
  )
}

// ---------------------------------------------------------------- page
function NoServer() {
  const src = B.quality.sources.filter((s) => s.rows_in > 0)
  return (
    <div className="stack">
      <p className="note">This copy of EarlySignal is the offline single file, so it cannot connect to a server or take an upload. Open the version hosted on the EarlySignal server (the Hugging Face Space) to use both options below.</p>
      <div className="grid g2">
        <Card title="College server (automatic)">
          <ol className="steps">{['IT creates a read-only database login for EarlySignal', 'EarlySignal reads the ERP and Moodle with SELECT-only queries', 'A nightly sync rebuilds every score and early warning'].map((t) => <li key={t}><span>{t}</span></li>)}</ol>
        </Card>
        <Card title="Excel upload (manual)">
          <ol className="steps">{['Download the template', 'Fill the three needed sheets: Students, Marks, Attendance', 'Upload the file: checks run and every page updates'].map((t) => <li key={t}><span>{t}</span></li>)}</ol>
        </Card>
      </div>
      <Card title="Where the current data came from" flush>
        <div className="table-wrap">
          <table className="list">
            <thead><tr><th>Data</th><th>System</th><th className="hide-sm">Student identifier used</th><th className="r">Records</th><th className="r">Matched</th></tr></thead>
            <tbody>{src.map((s) => <tr key={s.source}><td className="strong">{s.source}</td><td>{s.system}</td><td className="small hide-sm">{s.identifier}</td><td className="r num">{s.rows_in.toLocaleString('en-IN')}</td><td className="r num">{s.link_rate}%</td></tr>)}</tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}

export default function Sources() {
  const srv = server()
  const [info, setInfo] = useState(null)
  const [err, setErr] = useState('')
  const [tab, setTab] = useState('server')
  const [key, setKey] = useState(adminKey())
  const load = useMemo(() => () => api('source').then(setInfo).catch((e) => setErr(e.message)), [])
  useEffect(() => { if (srv) load() }, [srv, load])
  return (
    <div>
      <PageHead title="Data sources" sub="Connect EarlySignal to the college's own servers, or upload an Excel file." />
      {!srv ? <NoServer /> : (
        <div className="stack">
          <p className="note">{currentSource(info?.source)} Last updated {META.built_at}.</p>
          {srv.admin_key && (
            <div className="filterbar" style={{ marginBottom: 0 }}>
              <label className="fi" style={{ flex: '1 1 260px' }}>Admin key (needed to change data on this server)
                <input type="password" value={key} onChange={(e) => setKey(e.target.value)} autoComplete="off" />
              </label>
              <button type="button" className="btn" onClick={() => setAdminKey(key.trim())}>Use this key</button>
            </div>
          )}
          {err && <p className="err">{err}</p>}
          {info && (
            <div>
              <Tabs value={tab} onChange={setTab} tabs={[['server', 'College server (automatic)'], ['excel', 'Excel upload (manual)']]} />
              {tab === 'server' ? <ServerTab info={info} reloadInfo={load} /> : <ExcelTab info={info} />}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
