import { initials, pct } from '../lib/format'
import { RISK_WORD } from '../lib/data'

const P = {
  dashboard: 'M4 4h6v7H4zM14 4h6v4h-6zM14 12h6v8h-6zM4 15h6v5H4z',
  students: 'M16 19v-1.5a3.5 3.5 0 0 0-3.5-3.5h-5A3.5 3.5 0 0 0 4 17.5V19M10 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Zm10 8v-1.5a3.5 3.5 0 0 0-2.5-3.35M15.5 4.15a3.5 3.5 0 0 1 0 6.7',
  analytics: 'M3 17l5-5 4 3 7-8M17 7h3v3M4 21h16',
  segments: 'M7 3.5 10.5 9.5h-7L7 3.5ZM17 10a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7ZM3.5 13.5h7v7h-7zM17 13.5l3.5 3.5-3.5 3.5-3.5-3.5 3.5-3.5Z',
  placement: 'M9 6V4.5A1.5 1.5 0 0 1 10.5 3h3A1.5 1.5 0 0 1 15 4.5V6M4 7h16a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1Zm-1 5h18',
  interventions: 'M9 4h6v3H9zM8 5.5H6a1 1 0 0 0-1 1V20a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V6.5a1 1 0 0 0-1-1h-2M9 14l2 2 4-4',
  assistant: 'M4 5h12v8H8l-4 3V5Zm4 11v1a1 1 0 0 0 1 1h7l4 3V10a1 1 0 0 0-1-1h-1',
  sources: 'M7 18a4 4 0 0 1-.9-7.9 6 6 0 0 1 11.6 1.4A3.5 3.5 0 0 1 17.5 18H7Zm5-8v6m0-6-2.5 2.5M12 10l2.5 2.5',
  quality: 'M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3Zm0 0v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3',
  fairness: 'M12 3v18M5 7h14M5 7l-3 7a4 4 0 0 0 6 0L5 7Zm14 0-3 7a4 4 0 0 0 6 0l-3-7ZM8 21h8',
  help: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm-2.5-11.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6V14m0 3h.01',
  search: 'M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14Zm9 2-4-4',
  bell: 'M6 16V11a6 6 0 1 1 12 0v5l1.5 2h-15L6 16Zm4 3a2 2 0 0 0 4 0',
  logout: 'M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3M10 16l-4-4 4-4M6 12h10',
  back: 'M15 18l-6-6 6-6',
  arrow: 'M5 12h14m-5-5 5 5-5 5',
  download: 'M12 4v11m0 0-4-4m4 4 4-4M5 20h14',
  play: 'M8 5v14l11-7L8 5Z',
  menu: 'M4 7h16M4 12h16M4 17h16',
  cap: 'M2 10l10-5 10 5-10 5-10-5Zm4 2v5c3 2 9 2 12 0v-5m4-2v6',
  alert: 'M12 4 2.5 20h19L12 4Zm0 6v4m0 3h.01',
  star: 'M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8-5.2-2.8-5.2 2.8 1-5.8-4.3-4.1 5.9-.9L12 3.5Z',
  target: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-4a5 5 0 1 0 0-10 5 5 0 0 0 0 10Zm0-4a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z',
  book: 'M5 4h10a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3V4Zm0 13a3 3 0 0 1 3-3h10',
  calendar: 'M5 5h14a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1Zm-1 5h16M8 3v4m8-4v4',
  laptop: 'M5 6h14v9H5zM3 18h18',
  trend: 'M3 17l6-6 4 4 8-8M15 7h6v6',
  drop: 'M3 7l6 6 4-4 8 8M15 17h6v-6',
  layers: 'M12 3l9 5-9 5-9-5 9-5Zm-9 9 9 5 9-5',
  check: 'M5 12.5l4.5 4.5L19 7',
  x: 'M6 6l12 12M18 6 6 18',
  spark: 'M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Z',
  server: 'M4 4h16v6H4zM4 14h16v6H4zM7 7h.01M7 17h.01',
  file: 'M7 3h7l5 5v13H7V3Zm7 0v5h5M10 13h6M10 17h6',
  link: 'M10 14a4 4 0 0 0 5.66 0l3-3a4 4 0 0 0-5.66-5.66l-1 1M14 10a4 4 0 0 0-5.66 0l-3 3a4 4 0 0 0 5.66 5.66l1-1',
  flag: 'M5 21V4m0 0h11l-2 4 2 4H5',
  down: 'M7 10l5 5 5-5',
  up: 'M7 14l5-5 5 5',
  right: 'M9 6l6 6-6 6',
  user: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm-7 8a7 7 0 0 1 14 0',
  mail: 'M4 6h16v12H4zM4 7l8 6 8-6',
  info: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-10v6m0-9h.01',
  lock: 'M6 11h12v9H6zM8.5 11V8a3.5 3.5 0 0 1 7 0v3',
  phone: 'M8 3h8a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Zm3 15h2',
  staff: 'M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Zm-6 9a6 6 0 0 1 12 0M17 7h4M19 5v4',
  shield: 'M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6l7-3Z',
}

export function Icon({ name, size = 18, stroke = 1.8, ...rest }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={stroke}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...rest}>
      <path d={P[name]} />
    </svg>
  )
}

// The product mark: three rising bars, drawn in the current text colour.
export function Mark({ size = 24 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <rect x="3" y="13" width="4" height="8" rx="1" fill="currentColor" opacity="0.55" />
      <rect x="10" y="8" width="4" height="13" rx="1" fill="currentColor" opacity="0.8" />
      <rect x="17" y="3" width="4" height="18" rx="1" fill="currentColor" />
    </svg>
  )
}

export function Avatar({ name, size = 32 }) {
  return (
    <span className="av" aria-hidden="true" style={{ width: size, height: size, fontSize: Math.max(11, Math.round(size / 2.7)) }}>
      {initials(name)}
    </span>
  )
}

// One cell of a KPI strip (place inside <div className="kpis">).
export function Kpi({ label, value, unit, sub, trend, to }) {
  const body = (
    <>
      <div className="l">{label}</div>
      <div className="v num">{value}{unit ? <small>{unit}</small> : null}</div>
      {sub && (
        <div className={`s ${trend || ''}`}>
          {trend === 'bad' && <Icon name="down" size={14} stroke={2.2} />}
          {trend === 'good' && <Icon name="up" size={14} stroke={2.2} />}
          <span>{sub}</span>
        </div>
      )}
    </>
  )
  return to ? <a className="kpi" href={`#${to}`}>{body}</a> : <div className="kpi">{body}</div>
}

// KPI card: label, value, change line (no icon)
export function Stat({ label, value, unit, sub, trend, to }) {
  const body = (
    <>
      <div style={{ minWidth: 0 }}>
        <div className="l">{label}</div>
        <div className="v num">{value}{unit ? <small>{unit}</small> : null}</div>
        {sub && (
          <div className={`s ${trend || ''}`}>
            {trend === 'bad' && <Icon name="down" size={14} stroke={2.2} />}
            {trend === 'good' && <Icon name="up" size={14} stroke={2.2} />}
            <span>{sub}</span>
          </div>
        )}
      </div>
    </>
  )
  return to ? <a className="stat" href={`#${to}`}>{body}</a> : <div className="stat">{body}</div>
}

export function Ring({ score, label = 'Success Score' }) {
  return (
    <div className="ring" style={{ background: `conic-gradient(var(--brand) ${score * 3.6}deg, var(--brand-50) 0)` }}>
      <div><b className="num">{Math.round(score)}</b><span>{label}</span></div>
    </div>
  )
}

const PILL = {
  High: 'p-high', Medium: 'p-med', Low: 'p-grey', 'Not on track': 'p-high', 'Almost ready': 'p-med', 'On track': 'p-grey',
  'Early stage': 'p-grey', Urgent: 'p-high', None: 'p-grey',
  'At Risk': 'p-high', 'Needs Attention': 'p-med', 'On Track': 'p-grey', Thriving: 'p-grey', 'Pre-placement': 'p-grey',
}

export function Pill({ kind = 'p-grey', children, title }) {
  return <span className={`pill ${kind}`} title={title}>{children}</span>
}

export function RiskPill({ level, p, word }) {
  const label = word ?? RISK_WORD[level] ?? level
  return <span className={`pill ${PILL[level] || 'p-grey'}`}>{label}{p != null ? ` ${pct(p)}` : ''}</span>
}

const PRIO = { Urgent: 'p-high', High: 'p-med', Medium: 'p-brand', Low: 'p-grey', None: 'p-grey' }
export function PriorityPill({ p }) {
  return <span className={`pill ${PRIO[p] || 'p-grey'}`}>{p === 'None' || !p ? 'No action' : p}</span>
}

export function Meter({ value }) {
  return <div className="meter"><i style={{ width: `${Math.max(0, Math.min(100, value))}%` }} /></div>
}

export function Card({ title, sub, right, children, flush = false, foot, className = '', style }) {
  return (
    <section className={`card ${flush ? 'flush' : ''} ${className}`} style={style}>
      {(title || right) && (
        <div className="card-head">
          <div style={{ minWidth: 0 }}>{title && <h2>{title}</h2>}{sub && <p>{sub}</p>}</div>
          {right}
        </div>
      )}
      <div className="card-body">{children}</div>
      {foot && <div className="card-foot">{foot}</div>}
    </section>
  )
}

export function Tabs({ tabs, value, onChange }) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map(([k, l]) => (
        <button key={k} type="button" role="tab" aria-selected={value === k} className={value === k ? 'on' : ''} onClick={() => onChange(k)}>{l}</button>
      ))}
    </div>
  )
}

export function Seg({ value, options, onChange, label }) {
  return (
    <div className="seg" role="group" aria-label={label}>
      {options.map((o) => (
        <button key={o.value} type="button" className={value === o.value ? 'on' : ''} aria-pressed={value === o.value} onClick={() => onChange(o.value)}>{o.label}</button>
      ))}
    </div>
  )
}

export function Select({ label, value, onChange, options, all }) {
  return (
    <label className="fi">{label}
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        {all && <option value="">{all}</option>}
        {options.map((o) => (typeof o === 'object' ? <option key={o.value} value={o.value}>{o.label}</option> : <option key={o} value={o}>{o}</option>))}
      </select>
    </label>
  )
}

export function Kvl({ items }) {
  return <div>{items.map(([k, v]) => <div key={k} className="kvl"><span>{k}</span><span>{v}</span></div>)}</div>
}

export function Who({ s, sub, badge, plain }) {
  return (
    <div className="who">
      <Avatar name={s.name} />
      <div><b>{s.name}</b>{!plain && <> <span className="tiny">{s.dept}, year {s.year}</span></>}{badge && <> <span className="pill p-solid" style={{ marginLeft: 4 }}>{badge}</span></>}{sub && <span className="sub">{sub}</span>}</div>
    </div>
  )
}

export function PageHead({ title, sub, right }) {
  return (
    <div className="page-head">
      <div><h1>{title}</h1>{sub && <p className="sub">{sub}</p>}</div>
      {right}
    </div>
  )
}
