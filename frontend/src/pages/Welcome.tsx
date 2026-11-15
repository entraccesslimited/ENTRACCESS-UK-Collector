import { Link, Navigate } from 'react-router-dom'

import { homeFor, PORTALS, useSession, type PortalKey } from '@/lib/session'

const BLURB: Record<PortalKey, string> = {
  parent: 'Authorise who collects your child, send them their pass, and see every collection.',
  nursery: 'Managers and staff: check collectors at the door, and keep the handover record.',
  company: 'ENTRACCESS UK: set nurseries and schools up and see how each is running.',
}

/** The front door: three portals, one sign-in. */
export function Welcome() {
  const { me, loading } = useSession()
  if (loading) return <p className="p-8 text-center text-slate-500">Loading…</p>
  if (me) return <Navigate to={homeFor(me)} replace />
  return (
    <div className="min-h-screen bg-ink px-4 py-10 text-white">
      <div className="mx-auto max-w-4xl">
        <div className="flex items-center gap-3">
          <img src="/favicon.svg" alt="" className="size-12 rounded-xl" />
          <div>
            <h1 className="text-2xl font-bold">ENTRACCESS UK Collector</h1>
            <p className="text-slate-300">Every handover, authorised.</p>
          </div>
          <Link to="/" className="ml-auto text-sm text-slate-300 underline hover:text-white">
            Back to the website
          </Link>
        </div>
        <div className="mt-8 grid gap-4 md:grid-cols-3">
          {(Object.keys(PORTALS) as PortalKey[]).map((key) => (
            <Link
              key={key}
              to={`/sign-in?portal=${key}`}
              className="rounded-2xl bg-white p-5 text-ink shadow-lg transition hover:-translate-y-0.5 hover:shadow-xl"
            >
              <h2 className="text-lg font-semibold">{PORTALS[key].title}</h2>
              <p className="mt-2 text-sm text-slate-600">{BLURB[key]}</p>
              <span className="mt-4 inline-block text-sm font-semibold text-brand-700">Sign in →</span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  )
}
