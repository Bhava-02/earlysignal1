import { useCallback, useMemo, useState } from 'react'
import { HashRouter, Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import { can, store } from './lib/data'
import { RoleContext, useRole } from './lib/role'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import Students from './pages/Students'
import Student from './pages/Student'
import Analytics from './pages/Analytics'
import Segments from './pages/Segments'
import Placement from './pages/Placement'
import Interventions from './pages/Interventions'
import Assistant from './pages/Assistant'
import Staff from './pages/Staff'
import { How, Quality } from './pages/DataPages'
import Sources from './pages/Sources'

// A page the signed-in user is not allowed to open sends them to their home page.
function Guard({ path, children }) {
  const { role } = useRole()
  return can(role, path) ? children : <Navigate to="/" replace />
}

export default function App() {
  const [role, setRoleState] = useState(() => {
    const u = store.get('es.session', null)
    return u && u.kind ? u : null
  })
  const setRole = useCallback((u) => {
    setRoleState(u)
    store.set('es.session', u)
  }, [])
  const roleCtx = useMemo(() => ({ role, setRole }), [role, setRole])
  const g = (path, el) => <Guard path={path}>{el}</Guard>
  return (
    <RoleContext.Provider value={roleCtx}>
      <HashRouter>
        {!role ? (
          <Routes>
            <Route path="register" element={<Register />} />
            <Route path="*" element={<Login />} />
          </Routes>
        ) : role.kind === 'student' ? (
          <Routes>
            <Route element={<Layout />}>
              <Route path="me" element={<Student self />} />
              <Route path="*" element={<Navigate to="/me" replace />} />
            </Route>
          </Routes>
        ) : (
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<Dashboard />} />
              <Route path="students" element={g('/students', <Students />)} />
              <Route path="student/:id" element={g('/student', <Student />)} />
              <Route path="staff" element={g('/staff', <Staff />)} />
              <Route path="analytics" element={g('/analytics', <Analytics />)} />
              <Route path="segments" element={g('/segments', <Segments />)} />
              <Route path="placement" element={g('/placement', <Placement />)} />
              <Route path="interventions" element={g('/interventions', <Interventions />)} />
              <Route path="assistant" element={g('/assistant', <Assistant />)} />
              <Route path="sources" element={g('/sources', <Sources />)} />
              <Route path="quality" element={g('/quality', <Quality />)} />
              <Route path="how" element={g('/how', <How />)} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        )}
      </HashRouter>
    </RoleContext.Provider>
  )
}
