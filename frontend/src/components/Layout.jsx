import { useEffect, useMemo, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { can, META, scopeStudents } from '../lib/data'
import { useRole } from '../lib/role'
import { Avatar, Icon, Mark } from './ui'

const STAFF_NAV = [
  { group: null, items: [
    ['/', 'dashboard', 'Dashboard'], ['/students', 'students', 'Students'], ['/staff', 'staff', 'HODs and faculty'],
    ['/analytics', 'analytics', 'Analytics'], ['/segments', 'segments', 'Segments'], ['/placement', 'placement', 'Placement'],
    ['/interventions', 'interventions', 'Interventions'],
  ] },
  { group: 'Tools', items: [['/assistant', 'assistant', 'AI assistant'], ['/sources', 'sources', 'Data sources']] },
  { group: 'About the data', items: [['/quality', 'quality', 'Data quality'], ['/how', 'help', 'How it works']] },
]
const STUDENT_NAV = [{ group: null, items: [['/me', 'user', 'My profile']] }]

function Search({ students }) {
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const [i, setI] = useState(0)
  const nav = useNavigate()
  const box = useRef(null)
  const hits = useMemo(() => {
    const t = q.trim().toLowerCase()
    if (t.length < 2) return []
    return students.filter((s) => s.name.toLowerCase().includes(t) || s.id.toLowerCase().includes(t)).slice(0, 7)
  }, [q, students])
  useEffect(() => {
    const close = (e) => box.current && !box.current.contains(e.target) && setOpen(false)
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])
  const go = (s) => { setQ(''); setOpen(false); nav(`/student/${s.id}`) }
  return (
    <div className="tb-search" ref={box}>
      <Icon name="search" size={16} />
      <input type="search" placeholder="Search by name or roll number" aria-label="Search students" value={q}
        onChange={(e) => { setQ(e.target.value); setOpen(true); setI(0) }} onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown') { e.preventDefault(); setI((x) => Math.min(x + 1, hits.length - 1)) }
          if (e.key === 'ArrowUp') { e.preventDefault(); setI((x) => Math.max(x - 1, 0)) }
          if (e.key === 'Enter' && hits[i]) go(hits[i])
          if (e.key === 'Escape') setOpen(false)
        }} />
      {open && hits.length > 0 && (
        <div className="tb-results" role="listbox">
          {hits.map((s, k) => (
            <button key={s.id} type="button" className={k === i ? 'on' : ''} role="option" aria-selected={k === i} onClick={() => go(s)}>
              <Avatar name={s.name} size={28} />
              <span><b className="strong">{s.name}</b> <span className="tiny">{s.id}, {s.dept} year {s.year}</span></span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default function Layout() {
  const { role, setRole } = useRole()
  const S = useMemo(() => scopeStudents(role), [role])
  const student = role.kind === 'student'
  const newly = student ? 0 : S.filter((s) => s.new).length
  const [open, setOpen] = useState(false)
  const loc = useLocation()
  const nav = useNavigate()
  useEffect(() => { setOpen(false); window.scrollTo(0, 0) }, [loc.pathname])
  const logout = () => { setRole(null); nav('/') }
  const groups = student
    ? STUDENT_NAV
    : STAFF_NAV.map((g) => ({ ...g, items: g.items.filter(([to]) => can(role, to)) })).filter((g) => g.items.length)
  const label = (to, l) => (to === '/students' && role.kind === 'mentor' ? 'My students' : to === '/staff' && role.kind === 'hod' ? 'Mentors' : l)
  return (
    <div className="app">
      <aside className={`sb ${open ? 'open' : ''}`} aria-label="Menu">
        <div className="sb-brand">
          <span className="logo-tile"><Mark size={20} /></span>
          <div><b>EarlySignal</b><span>{META.college}</span></div>
        </div>
        {groups.map((g) => (
          <nav key={g.group || 'main'} aria-label={g.group || 'Main'}>
            {g.group && <div className="sb-group">{g.group}</div>}
            {g.items.map(([to, icon, l]) => (
              <NavLink key={to} to={to} end={to === '/'} className={({ isActive }) => `nav ${isActive ? 'active' : ''}`}>
                <Icon name={icon} size={18} />{label(to, l)}
              </NavLink>
            ))}
          </nav>
        ))}
        <div className="sb-user">
          <b>{role.name}</b><span>{role.title}</span>
        </div>
      </aside>
      <div className="main">
        <header className="topbar">
          <button type="button" className="icon-btn menu-btn" aria-label="Open menu" onClick={() => setOpen((o) => !o)}><Icon name="menu" /></button>
          <div className="tb-term"><b>{META.semester}</b>, week {META.week} of {META.weeks}</div>
          {!student && <Search students={S} />}
          {student && <span className="spacer" />}
          {!student && newly > 0 && (
            <button type="button" className="tb-alerts" onClick={() => nav('/students?quick=new')} title="Students who became high risk this week">
              <Icon name="bell" size={16} /><b>{newly}</b><span>new this week</span>
            </button>
          )}
          <div className="tb-user">
            <Avatar name={role.name} size={32} />
            <div><b>{role.name}</b><span>{role.title}</span></div>
            <button type="button" className="icon-btn" onClick={logout} aria-label="Sign out" title="Sign out"><Icon name="logout" size={18} /></button>
          </div>
        </header>
        <div className="content">
          <Outlet />
        </div>
      </div>
    </div>
  )
}
