import { NavLink, Outlet, useNavigate } from 'react-router-dom'

import { useSession } from '@/lib/session'

const NAV = {
  parent: [
    { to: '/parent', label: 'Collectors' },
    { to: '/parent/history', label: 'History' },
  ],
  staff: [{ to: '/door', label: 'Door check' }],
  admin: [
    { to: '/admin', label: 'Today' },
    { to: '/door', label: 'Door check' },
    { to: '/admin/handovers', label: 'Handovers' },
    { to: '/admin/activity', label: 'Activity' },
    { to: '/admin/children', label: 'Children' },
    { to: '/admin/people', label: 'People' },
    { to: '/admin/settings', label: 'Settings' },
  ],
  operator: [
    { to: '/company', label: 'Nurseries' },
    { to: '/company/enquiries', label: 'Enquiries' },
  ],
}

export function Layout() {
  const { me, signOut } = useSession()
  const navigate = useNavigate()
  if (!me) return null
  return (
    <div className="min-h-screen">
      <header className="bg-ink text-white">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <div className="flex items-center gap-2">
            <img src="/favicon.svg" alt="" className="size-7 rounded-md" />
            <div className="leading-tight">
              <p className="text-sm font-semibold">ENTRACCESS UK</p>
              <p className="text-xs text-slate-300">{me.nursery_name}</p>
            </div>
          </div>
          <nav className="flex flex-1 flex-wrap gap-1">
            {NAV[me.role].map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end
                className={({ isActive }) =>
                  `rounded-md px-3 py-1.5 text-sm ${isActive ? 'bg-white/15 font-semibold' : 'text-slate-300 hover:text-white'}`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="flex items-center gap-3 text-sm">
            <span className="hidden text-slate-300 sm:inline">{me.full_name}</span>
            <button
              className="rounded-md border border-white/30 px-3 py-1 hover:bg-white/10"
              onClick={async () => {
                await signOut()
                navigate('/sign-in')
              }}
            >
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
