import { Navigate, Route, Routes } from 'react-router-dom'

import { Layout } from '@/components/Layout'
import { homeFor, useSession } from '@/lib/session'
import type { Role } from '@/lib/types'
import { AdminChildren } from '@/pages/AdminChildren'
import { AdminHandovers } from '@/pages/AdminHandovers'
import { AdminPeople } from '@/pages/AdminPeople'
import { AdminSettings } from '@/pages/AdminSettings'
import { AdminToday } from '@/pages/AdminToday'
import { Door } from '@/pages/Door'
import { ParentHistory } from '@/pages/ParentHistory'
import { ParentHome } from '@/pages/ParentHome'
import { PublicPass } from '@/pages/PublicPass'
import { SignIn } from '@/pages/SignIn'

function Guard({ roles, children }: { roles: Role[]; children: JSX.Element }) {
  const { me, loading } = useSession()
  if (loading) return <p className="p-8 text-center text-slate-500">Loading…</p>
  if (!me) return <Navigate to="/sign-in" replace />
  if (!roles.includes(me.role)) return <Navigate to={homeFor(me)} replace />
  return children
}

function Home() {
  const { me, loading } = useSession()
  if (loading) return <p className="p-8 text-center text-slate-500">Loading…</p>
  return <Navigate to={me ? homeFor(me) : '/sign-in'} replace />
}

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/sign-in" element={<SignIn />} />
      <Route path="/pass/:token" element={<PublicPass />} />
      <Route element={<Guard roles={['parent', 'staff', 'admin']}><Layout /></Guard>}>
        <Route path="/parent" element={<Guard roles={['parent']}><ParentHome /></Guard>} />
        <Route path="/parent/history" element={<Guard roles={['parent']}><ParentHistory /></Guard>} />
        <Route path="/door" element={<Guard roles={['staff', 'admin']}><Door /></Guard>} />
        <Route path="/admin" element={<Guard roles={['admin']}><AdminToday /></Guard>} />
        <Route path="/admin/handovers" element={<Guard roles={['admin']}><AdminHandovers /></Guard>} />
        <Route path="/admin/children" element={<Guard roles={['admin']}><AdminChildren /></Guard>} />
        <Route path="/admin/people" element={<Guard roles={['admin']}><AdminPeople /></Guard>} />
        <Route path="/admin/settings" element={<Guard roles={['admin']}><AdminSettings /></Guard>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
