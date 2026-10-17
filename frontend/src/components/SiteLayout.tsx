import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'

import { ThemeToggle } from '@/components/ThemeToggle'

const LINKS = [
  { href: '/#how', label: 'How it works' },
  { href: '/prototype', label: 'Try it' },
  { href: '/#safeguards', label: 'Safeguards' },
  { href: '/#pricing', label: 'Pricing' },
  { href: '/#faq', label: 'Questions' },
  { href: '/#contact', label: 'Contact' },
]

/** The public website's frame: header with the page sections, footer with the legal bits. */
export function SiteLayout({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="site min-h-screen bg-paper text-slate-800">
      <header className="sticky top-0 z-40 border-b border-slate-200 bg-paper/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-2 px-4 py-3 sm:gap-4">
          <Link to="/" className="flex shrink-0 items-center gap-2">
            <img src="/favicon.svg" alt="" className="size-8 rounded-[9px] sm:size-9" />
            <span className="leading-tight">
              <span className="block whitespace-nowrap font-display text-[0.85rem] font-extrabold tracking-wide text-ink sm:text-[0.95rem]">
                ENTRACCESS <span className="text-brand-600">UK</span>
              </span>
              <span className="block text-xs font-medium text-slate-500">Collector</span>
            </span>
          </Link>
          <nav className="ml-auto hidden items-center gap-6 text-sm font-medium lg:flex">
            {LINKS.map((l) => (
              <a key={l.href} href={l.href} className="whitespace-nowrap text-slate-600 hover:text-ink">
                {l.label}
              </a>
            ))}
          </nav>
          <ThemeToggle className="ml-auto lg:ml-0" />
          <a href="/#contact" className="btn btn-primary whitespace-nowrap px-3 text-xs sm:px-4 sm:text-sm lg:ml-0">
            Book a demo
          </a>
          <button className="rounded-full p-2 text-slate-600 lg:hidden" aria-label="Menu" aria-expanded={open} onClick={() => setOpen(!open)}>
            ☰
          </button>
        </div>
        {open && (
          <nav className="border-t border-slate-200 px-4 py-2 lg:hidden">
            {LINKS.map((l) => (
              <a key={l.href} href={l.href} onClick={() => setOpen(false)} className="block py-2 text-slate-700">
                {l.label}
              </a>
            ))}
          </nav>
        )}
      </header>
      <main>{children}</main>
      <footer className="border-t-[3px] border-brand-600 bg-midnight text-[#cbd5e1]">
        <div className="mx-auto grid max-w-6xl gap-6 px-4 py-10 text-sm md:grid-cols-2">
          <div>
            <p className="font-display font-extrabold tracking-wide text-white">
              ENTRACCESS <span className="text-brand-500">UK</span> Collector
            </p>
            <p className="mt-1">Every handover, authorised. Safe, recorded child collection for UK nurseries.</p>
          </div>
          <div className="space-y-1">
            <p className="font-semibold text-white">Company</p>
            <Link to="/privacy" className="block hover:text-white">Privacy and data protection</Link>
            <a href="/#contact" className="block hover:text-white">Contact us</a>
          </div>
        </div>
        <p className="border-t border-white/10 px-4 py-4 text-center text-xs">
          © 2026 ENTRACCESS UK LTD. Registered in England and Wales.
        </p>
      </footer>
    </div>
  )
}
