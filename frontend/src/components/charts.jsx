// Every chart in the app is a bar chart built from these three pieces, so they all look and behave the same:
// teal for the main series, a lighter step of the same teal for comparisons, hairline grid, hover tooltip.
import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, LabelList, Pie, PieChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

export const COL = { c1: '#0f766e', c2: '#36998d', c3: '#6db8ad', grid: '#e6eded', axis: '#637275', ink: '#1b2a2c', text: '#3c4b4d' }
export const RAMP = [COL.c1, COL.c2, COL.c3] // ordinal: High, Medium, Low (dark to light)
// Only for charts with several series of different things (departments; overall, academic, engagement)
export const SERIES = ['#0d9488', '#4569d4', '#c98f1f', '#b0559c']
export const BAND_COLORS = ['#0d6b63', '#2f978a', '#5fb0a4', '#8cc6bc']

const tick = { fontSize: 12, fill: COL.axis }

// Round axis ticks: 0 to a clean top value in 4 or 5 even steps (0, 50, 100, 150, 200 rather than 0, 65, 130, 195).
export function niceTicks(max) {
  if (!(max > 0)) return [0, 1]
  const raw = max / 4
  const p = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 2.5, 5, 10].map((m) => m * p).find((x) => x >= raw - 1e-9)
  const top = Math.ceil(max / step - 1e-9) * step
  return Array.from({ length: Math.round(top / step) + 1 }, (_, i) => +(i * step).toFixed(6))
}
function axisFor(data, series, stacked, domain) {
  if (domain && typeof domain[1] === 'number') return { domain, ticks: niceTicks(domain[1]) }
  const vals = data.map((d) => (stacked ? series.reduce((a, s) => a + (Number(d[s.key]) || 0), 0) : Math.max(...series.map((s) => Number(d[s.key]) || 0))))
  const ticks = niceTicks(Math.max(0, ...vals))
  return { domain: [0, ticks[ticks.length - 1]], ticks }
}
const hover = { fill: 'rgba(15, 118, 110, 0.07)' }

// On phones, category labels get less room so the bars stay readable.
function useNarrow() {
  const q = () => typeof window !== 'undefined' && window.innerWidth < 600
  const [n, setN] = useState(q)
  useEffect(() => {
    const f = () => setN(q())
    window.addEventListener('resize', f)
    return () => window.removeEventListener('resize', f)
  }, [])
  return n
}

function Tip({ active, payload, label, fmt, title }) {
  if (!active || !payload?.length) return null
  return (
    <div className="ctip">
      <div className="t">{title ? title(label, payload[0]?.payload) : label}</div>
      {payload.map((p) => (
        <div className="r" key={p.dataKey}>
          <i style={{ background: p.payload?.color || p.color || p.fill }} />
          <b>{fmt(p.value, p.payload, p.dataKey)}</b>
          {payload.length > 1 && <span>{p.name}</span>}
        </div>
      ))}
    </div>
  )
}

export function Legend({ items }) {
  return (
    <div className="legend" aria-hidden="true">
      {items.map(([name, color]) => <span key={name}><i style={{ background: color }} />{name}</span>)}
    </div>
  )
}

// Vertical columns over a category axis (weeks, bands, semesters).
// series: [{ key, name, color }]. Two series sit side by side; stacked=true stacks them.
export function Columns({
  data, x, series, height = 240, fmt = (v) => v, xfmt = (v) => v, yfmt, domain, refY, refLabel, title, labels = false,
  stacked = false, legend = series.length > 1, labelKey,
}) {
  const ax = axisFor(data, series, stacked, domain)
  return (
    <div className="chart">
      {legend && <Legend items={series.map((s) => [s.name, s.color])} />}
      <div style={{ height }}>
        <ResponsiveContainer>
          <BarChart data={data} margin={{ top: labels ? 18 : 8, right: refLabel ? 44 : 8, left: 0, bottom: 0 }} barGap={2} barCategoryGap="22%">
            <CartesianGrid stroke={COL.grid} vertical={false} />
            <XAxis dataKey={x} tickFormatter={xfmt} tick={tick} axisLine={{ stroke: COL.grid }} tickLine={false} interval={data.length <= 12 ? 0 : 'preserveStartEnd'} minTickGap={2} />
            <YAxis tick={tick} axisLine={false} tickLine={false} width={40} domain={ax.domain} ticks={ax.ticks} tickFormatter={yfmt || fmt} interval={0} />
            <Tooltip cursor={hover} content={<Tip fmt={fmt} title={title || ((l) => xfmt(l))} />} />
            {refY != null && (
              <ReferenceLine y={refY} stroke={COL.c2} strokeWidth={1}
                label={refLabel ? { value: refLabel, position: 'right', fontSize: 11.5, fill: COL.axis } : undefined} />
            )}
            {series.map((s, i) => (
              <Bar key={s.key} isAnimationActive={false} dataKey={s.key} name={s.name} fill={s.color} maxBarSize={stacked ? 28 : 24}
                stackId={stacked ? 'a' : undefined} radius={!stacked || i === series.length - 1 ? [4, 4, 0, 0] : 0}>
                {labels && !stacked && <LabelList dataKey={labelKey || s.key} position="top" formatter={(v) => (v == null ? '' : labelKey ? v : fmt(v))} fontSize={12} fill={COL.text} />}
                {s.colors && data.map((d, k) => <Cell key={k} fill={s.colors[k % s.colors.length]} />)}
              </Bar>
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

// Horizontal bars over a category axis (departments, segments, reasons).
// One series shows its value at the bar end. Two series sit side by side; stacked=true stacks them.
export function HBars({
  data, y, series, fmt = (v) => v, yWidth = 120, domain, height, labels = true, stacked = false, title,
  legend = series.length > 1, onClick, rowH,
}) {
  const narrow = useNarrow()
  const yw = narrow ? Math.min(yWidth, 104) : yWidth
  const per = rowH || (stacked || series.length === 1 ? 36 : 46)
  const h = height || data.length * per + 24
  const ax = axisFor(data, series, stacked, domain)
  return (
    <div className="chart">
      {legend && <Legend items={series.map((s) => [s.name, s.color])} />}
      <div style={{ height: h }}>
        <ResponsiveContainer>
          <BarChart data={data} layout="vertical" margin={{ top: 0, right: labels ? 48 : 12, left: 0, bottom: 0 }} barGap={2} barCategoryGap="26%">
            <CartesianGrid stroke={COL.grid} horizontal={false} />
            <XAxis type="number" tick={tick} axisLine={false} tickLine={false} domain={ax.domain} ticks={ax.ticks} tickFormatter={fmt} interval={0} />
            <YAxis type="category" dataKey={y} width={yw} tick={{ fontSize: narrow ? 11.5 : 12.5, fill: COL.text }} axisLine={{ stroke: COL.grid }} tickLine={false} interval={0} />
            <Tooltip cursor={hover} content={<Tip fmt={fmt} title={title} />} />
            {series.map((s, i) => (
              <Bar key={s.key} isAnimationActive={false} dataKey={s.key} name={s.name} fill={s.color} maxBarSize={stacked ? 22 : series.length > 1 ? 14 : 20}
                stackId={stacked ? 'a' : undefined} radius={!stacked || i === series.length - 1 ? [0, 4, 4, 0] : 0}
                onClick={onClick ? (d) => onClick(d) : undefined} style={onClick ? { cursor: 'pointer' } : undefined}>
                {labels && !stacked && series.length === 1 && <LabelList dataKey={s.key} position="right" formatter={(v) => (v == null ? '' : fmt(v))} fontSize={12} fill={COL.text} />}
              </Bar>
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

// Pie chart with a hole and a total in the middle (Round 1 "Risk distribution")
export function Donut({ data, total, caption, height = 210 }) {
  return (
    <div style={{ height, position: 'relative' }}>
      <ResponsiveContainer>
        <PieChart>
          <Pie isAnimationActive={false} data={data} dataKey="value" nameKey="name" innerRadius="66%" outerRadius="96%"
            startAngle={90} endAngle={-270} stroke="#fff" strokeWidth={2}>
            {data.map((d) => <Cell key={d.name} fill={d.color} />)}
          </Pie>
          <Tooltip content={<Tip fmt={(v) => `${v} students`} title={(l, p) => p?.name} />} />
        </PieChart>
      </ResponsiveContainer>
      <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', pointerEvents: 'none', textAlign: 'center' }}>
        <div><b style={{ fontSize: 26, color: COL.ink, fontWeight: 600 }}>{total}</b><div className="tiny">{caption}</div></div>
      </div>
    </div>
  )
}
