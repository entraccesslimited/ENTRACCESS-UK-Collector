import { useState } from 'react'

import { Alert, PageTitle } from '@/components/ui'
import { todayIso, when } from '@/lib/format'
import { useLoad } from '@/lib/useLoad'
import type { Handover } from '@/lib/types'

function daysAgo(n: number): string {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return d.toLocaleDateString('en-CA', { timeZone: 'Europe/London' })
}

export function AdminHandovers() {
  const [start, setStart] = useState(daysAgo(30))
  const [end, setEnd] = useState(todayIso())
  const query = `start=${start}&end=${end}`
  const rows = useLoad<Handover[]>(`/admin/handovers?${query}`)
  return (
    <>
      <PageTitle title="Handovers" sub="Who collected each child, who authorised it and who checked it. This record cannot be edited." />
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <label>
          <span className="label">From</span>
          <input className="input" type="date" value={start} onChange={(e) => setStart(e.target.value)} />
        </label>
        <label>
          <span className="label">To</span>
          <input className="input" type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
        </label>
        <a className="btn btn-secondary" href={`/api/admin/handovers.csv?${query}`}>
          Export CSV
        </a>
      </div>
      {rows.error && <Alert>{rows.error}</Alert>}
      <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead className="bg-slate-50">
            <tr>
              <th>When</th>
              <th>Child</th>
              <th>Outcome</th>
              <th>Collector</th>
              <th>Authorised by</th>
              <th>Checked by</th>
              <th>ID</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.data?.map((h) => (
              <tr key={h.id}>
                <td className="whitespace-nowrap">{when(h.occurred_at)}</td>
                <td>{h.child_name}</td>
                <td>
                  <span className={h.outcome === 'released' ? 'text-emerald-700' : 'text-red-700'}>
                    {h.outcome === 'released' ? 'Released' : `Refused: ${h.refusal_reason}`}
                  </span>
                </td>
                <td>
                  {h.collector_name} <span className="text-slate-500">· {h.collector_relationship}</span>
                </td>
                <td>{h.authorised_by_name}</td>
                <td>{h.staff_name}</td>
                <td className="whitespace-nowrap">{h.outcome === 'released' ? (h.id_checked ? '✓ Checked' : 'Not recorded') : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.data?.length === 0 && <p className="p-4 text-sm text-slate-500">No handovers in this period.</p>}
      </div>
    </>
  )
}
