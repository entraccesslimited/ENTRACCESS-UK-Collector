import { useState } from 'react'

import { Alert, PageTitle } from '@/components/ui'
import { todayIso, when } from '@/lib/format'
import { useLoad } from '@/lib/useLoad'
import type { Activity } from '@/lib/types'

const KINDS: Record<string, { label: string; tone: string }> = {
  handover: { label: 'Door', tone: 'bg-emerald-100 text-emerald-800' },
  authorisation: { label: 'Collectors', tone: 'bg-brand-50 text-brand-700' },
  child: { label: 'Children', tone: 'bg-amber-100 text-amber-800' },
  person: { label: 'People', tone: 'bg-amber-100 text-amber-800' },
  parent: { label: 'People', tone: 'bg-amber-100 text-amber-800' },
  geofence: { label: 'Settings', tone: 'bg-slate-200 text-slate-700' },
  handovers: { label: 'Export', tone: 'bg-slate-200 text-slate-700' },
}

/** Everything that happened at the nursery, newest first, in one place. */
export function AdminActivity() {
  const [start, setStart] = useState(todayIso())
  const [end, setEnd] = useState(todayIso())
  const rows = useLoad<Activity[]>(`/admin/activity?start=${start}&end=${end}`)
  return (
    <>
      <PageTitle
        title="Activity"
        sub="Who added or removed collectors, who changed access, and every decision at the door. Nothing here can be edited."
      />
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <label>
          <span className="label">From</span>
          <input className="input" type="date" value={start} onChange={(e) => setStart(e.target.value)} />
        </label>
        <label>
          <span className="label">To</span>
          <input className="input" type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
        </label>
      </div>
      {rows.error && <Alert>{rows.error}</Alert>}
      <div className="card p-0">
        <ul className="divide-y divide-slate-100">
          {rows.data?.map((a, i) => {
            const kind = KINDS[a.kind] ?? { label: a.kind, tone: 'bg-slate-200 text-slate-700' }
            return (
              <li key={i} className="flex flex-wrap items-start gap-3 px-4 py-3 text-sm">
                <span className="w-28 shrink-0 whitespace-nowrap text-slate-500">{when(a.at)}</span>
                <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold ${kind.tone}`}>{kind.label}</span>
                <span className="min-w-0 flex-1">
                  {a.what}
                  <span className="block text-xs text-slate-500">{a.who}</span>
                </span>
              </li>
            )
          })}
        </ul>
        {rows.data?.length === 0 && <p className="p-4 text-sm text-slate-500">Nothing recorded in this period.</p>}
      </div>
    </>
  )
}
