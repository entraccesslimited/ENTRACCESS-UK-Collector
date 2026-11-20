import { useEffect, useState, type ReactNode } from 'react'
import QRCode from 'qrcode'

import { STATUS_LABEL } from '@/lib/format'
import type { CheckResult } from '@/lib/types'

export function Badge({ status }: { status: CheckResult }) {
  const tone =
    status === 'valid'
      ? 'bg-emerald-100 text-emerald-800'
      : status === 'not_yet_valid'
        ? 'bg-amber-100 text-amber-800'
        : 'bg-slate-200 text-slate-700'
  return <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${tone}`}>{STATUS_LABEL[status]}</span>
}

export function Pill({ tone = 'slate', children }: { tone?: 'slate' | 'green' | 'amber' | 'red'; children: ReactNode }) {
  const style = {
    slate: 'bg-slate-200 text-slate-700',
    green: 'bg-emerald-100 text-emerald-800',
    amber: 'bg-amber-100 text-amber-800',
    red: 'bg-red-100 text-red-800',
  }[tone]
  return <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${style}`}>{children}</span>
}

export function Alert({ tone = 'error', children }: { tone?: 'error' | 'ok' | 'info'; children: ReactNode }) {
  const style =
    tone === 'error'
      ? 'border-red-200 bg-red-50 text-red-800'
      : tone === 'ok'
        ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
        : 'border-brand-100 bg-brand-50 text-brand-700'
  return (
    <div role={tone === 'error' ? 'alert' : 'status'} className={`rounded-lg border px-3 py-2 text-sm ${style}`}>
      {children}
    </div>
  )
}

export function PageTitle({ title, sub }: { title: string; sub?: string }) {
  return (
    <div className="mb-5">
      <h1 className="text-2xl font-bold tracking-tight text-ink">{title}</h1>
      {sub && <p className="mt-1 text-sm text-slate-600">{sub}</p>}
    </div>
  )
}

export function Modal({ open, title, onClose, children }: { open: boolean; title: string; onClose: () => void; children: ReactNode }) {
  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/50 p-0 sm:items-center sm:p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="max-h-[92vh] w-full overflow-y-auto rounded-t-2xl bg-white p-5 shadow-xl sm:max-w-lg sm:rounded-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button className="rounded p-1 text-slate-500 hover:bg-slate-100" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}

export function QR({ text, size = 240 }: { text: string; size?: number }) {
  const [svg, setSvg] = useState('')
  useEffect(() => {
    QRCode.toString(text, { type: 'svg', margin: 1, errorCorrectionLevel: 'M' })
      .then(setSvg)
      .catch(() => setSvg(''))
  }, [text])
  return (
    <div
      role="img"
      aria-label="Collector pass QR code"
      style={{ width: size, height: size }}
      className="mx-auto rounded-lg bg-white p-2"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  )
}

export function Stat({ label, value, tone = 'slate' }: { label: string; value: number; tone?: 'slate' | 'green' | 'red' | 'amber' }) {
  const colour = { slate: 'text-ink', green: 'text-emerald-700', red: 'text-red-700', amber: 'text-amber-700' }[tone]
  return (
    <div className="card">
      <p className="text-sm text-slate-500">{label}</p>
      <p className={`mt-1 text-3xl font-bold ${colour}`}>{value}</p>
    </div>
  )
}
