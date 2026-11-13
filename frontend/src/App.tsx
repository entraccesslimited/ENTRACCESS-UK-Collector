import { useEffect } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'

import { Layout } from '@/components/Layout'
import { homeFor, useSession } from '@/lib/session'
import { CompanyEnquiries } from '@/pages/CompanyEnquiries'
import { CompanyHome } from '@/pages/CompanyHome'
import { Privacy } from '@/pages/Privacy'
import { Prototype } from '@/pages/Prototype'
import { Website } from '@/pages/Website'
import { Welcome } from '@/pages/Welcome'
import type { Role } from '@/lib/types'
import { AdminChildren } from '@/pages/AdminChildren'
import { AdminActivity } from '@/pages/AdminActivity'
import { AdminHandovers } from '@/pages/AdminHandovers'
import { AdminPeople } from '@/pages/AdminPeople'
import { AdminReconciliation } from '@/pages/AdminReconciliation'
import { AdminSettings } from '@/pages/AdminSettings'
import { AdminToday } from '@/pages/AdminToday'
import { Door } from '@/pages/Door'
import { ParentHistory } from '@/pages/ParentHistory'
import { ParentHome } from '@/pages/ParentHome'
import { PublicPass } from '@/pages/PublicPass'
import { SignIn } from '@/pages/SignIn'

function Guard({ roles, children }: { roles: Role[]; children: JSX.Element }) {
  const { me, loading } = useSession()
  const location = useLocation()
  if (loading) return <p className="p-8 text-center text-slate-500">Loading…</p>
  if (!me) return <Navigate to={`/sign-in?next=${encodeURIComponent(location.pathname)}`} replace />
  if (!roles.includes(me.role)) return <Navigate to={homeFor(me)} replace />
  return children
}

declare global {
  interface Window {
    entraccessApp?: { update: () => void }
  }
}

export function App() {
  const location = useLocation()
  // Each portal is its own installable app; public/app-manifest.js picks
  // which one this address belongs to, and runs again on every navigation.
  useEffect(() => {
    window.entraccessApp?.update()
  }, [location.pathname, location.search])

  return (
    <Routes>
      <Route path="/" element={<Website />} />
      <Route path="/privacy" element={<Privacy />} />
      <Route path="/prototype" element={<Prototype />} />
      <Route path="/portals" element={<Welcome />} />
      <Route path="/sign-in" element={<SignIn />} />
      <Route path="/pass/:token" element={<PublicPass />} />
      <Route element={<Guard roles={['parent', 'staff', 'admin', 'operator']}><Layout /></Guard>}>
        <Route path="/parent" element={<Guard roles={['parent']}><ParentHome /></Guard>} />
        <Route path="/parent/history" element={<Guard roles={['parent']}><ParentHistory /></Guard>} />
        <Route path="/door" element={<Guard roles={['staff', 'admin']}><Door /></Guard>} />
        <Route path="/admin" element={<Guard roles={['admin']}><AdminToday /></Guard>} />
        <Route path="/admin/handovers" element={<Guard roles={['admin']}><AdminHandovers /></Guard>} />
        <Route path="/admin/reconcile" element={<Guard roles={['admin']}><AdminReconciliation /></Guard>} />
        <Route path="/admin/activity" element={<Guard roles={['admin']}><AdminActivity /></Guard>} />
        <Route path="/admin/children" element={<Guard roles={['admin']}><AdminChildren /></Guard>} />
        <Route path="/admin/people" element={<Guard roles={['admin']}><AdminPeople /></Guard>} />
        <Route path="/admin/settings" element={<Guard roles={['admin']}><AdminSettings /></Guard>} />
        <Route path="/company" element={<Guard roles={['operator']}><CompanyHome /></Guard>} />
        <Route path="/company/enquiries" element={<Guard roles={['operator']}><CompanyEnquiries /></Guard>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
