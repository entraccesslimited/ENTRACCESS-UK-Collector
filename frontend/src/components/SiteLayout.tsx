import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'

import { homeFor, useSession } from '@/lib/session'

const LINKS = [
  { href: '/#how', label: 'How it works' },
  { href: '/#safeguards', label: 'Safeguards' },
  { href: '/#pricing', label: 'Pricing' },
  { href: '/#faq', label: 'Questions' },
  { href: '/#contact', label: 'Contact' },
]

/** The public website's frame: header with the portals, footer with the legal bits. */
export function SiteLayout({ children }: { children: ReactNode }) {
  const { me } = useSession()
  const [open, setOpen] = useState(false)
  return (
    <div className="min-h-screen bg-white text-slate-800">
      <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-3">
          <Link to="/" className="flex items-center gap-2">
            <img src="/favicon.svg" alt="" className="size-9 rounded-lg" />
            <span className="leading-tight">
              <span className="block text-sm font-bold text-ink">ENTRACCESS UK</span>
              <span className="block text-xs text-slate-500">Collector</span>
            </span>
          </Link>
          <nav className="ml-auto hidden items-center gap-5 text-sm md:flex">
            {LINKS.map((l) => (
              <a key={l.href} href={l.href} className="text-slate-600 hover:text-ink">
                {l.label}
              </a>
            ))}
          </nav>
          <Link to={me ? homeFor(me) : '/portals'} className="btn btn-primary ml-auto md:ml-0">
            {me ? 'Open your portal' : 'Sign in'}
          </Link>
          <button className="rounded-md p-2 md:hidden" aria-label="Menu" aria-expanded={open} onClick={() => setOpen(!open)}>
            ☰
          </button>
        </div>
        {open && (
          <nav className="border-t border-slate-200 px-4 py-2 md:hidden">
            {LINKS.map((l) => (
              <a key={l.href} href={l.href} onClick={() => setOpen(false)} className="block py-2 text-slate-700">
                {l.label}
              </a>
            ))}
          </nav>
        )}
      </header>
      <main>{children}</main>
      <footer className="bg-ink text-slate-300">
        <div className="mx-auto grid max-w-6xl gap-6 px-4 py-10 text-sm md:grid-cols-3">
          <div>
            <p className="font-semibold text-white">ENTRACCESS UK Collector</p>
            <p className="mt-1">Every handover, authorised. Safe, recorded child collection for UK nurseries.</p>
          </div>
          <div className="space-y-1">
            <p className="font-semibold text-white">Portals</p>
            <Link to="/sign-in?portal=parent" className="block hover:text-white">Parent portal</Link>
            <Link to="/sign-in?portal=nursery" className="block hover:text-white">Nursery portal</Link>
            <Link to="/sign-in?portal=company" className="block hover:text-white">Company portal</Link>
          </div>
          <div className="space-y-1">
            <p className="font-semibold text-white">Company</p>
            <Link to="/privacy" className="block hover:text-white">Privacy and data protection</Link>
            <a href="/#contact" className="block hover:text-white">Contact us</a>
          </div>
        </div>
        <p className="border-t border-white/10 px-4 py-4 text-center text-xs">
          © 2026 ENTRACCESS UK LTD. Registered in England and Wales. Early prototype, shown with made-up data.
        </p>
      </footer>
    </div>
  )
}
