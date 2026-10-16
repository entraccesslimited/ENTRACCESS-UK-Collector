import { useState } from 'react'

const KEY = 'entraccess-theme'

/**
 * Light or dark for the public website. public/theme.js sets the starting
 * theme before React loads, from a saved choice or else the device setting, so
 * the page never flashes the wrong one; this only flips it and remembers.
 */
export function ThemeToggle({ className = '' }: { className?: string }) {
  const [dark, setDark] = useState(() => document.documentElement.dataset.theme === 'dark')

  const flip = () => {
    const next = dark ? 'light' : 'dark'
    document.documentElement.dataset.theme = next
    try {
      localStorage.setItem(KEY, next)
    } catch {
      // Private browsing: the choice lasts for this page only.
    }
    setDark(!dark)
  }

  return (
    <button
      type="button"
      onClick={flip}
      aria-label={dark ? 'Switch to light theme' : 'Switch to dark theme'}
      className={`grid size-9 shrink-0 place-items-center rounded-full border border-slate-300 text-slate-600 transition hover:border-brand-500 hover:text-ink ${className}`}
    >
      {dark ? (
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" className="size-[18px]">
          <circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="1.8" />
          <path d="M12 2v2m0 16v2M2 12h2m16 0h2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
      ) : (
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" className="size-[18px]">
          <path d="M20 13.2A8 8 0 0 1 10.8 4a8 8 0 1 0 9.2 9.2Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
        </svg>
      )}
    </button>
  )
}
