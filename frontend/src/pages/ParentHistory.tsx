import { Alert, PageTitle } from '@/components/ui'
import { when } from '@/lib/format'
import { useLoad } from '@/lib/useLoad'
import type { Handover } from '@/lib/types'

export function ParentHistory() {
  const history = useLoad<Handover[]>('/parent/handovers')
  return (
    <>
      <PageTitle title="Collection history" sub="Every time your child was collected, or someone was turned away." />
      {history.error && <Alert>{history.error}</Alert>}
      {history.data?.length === 0 && <p className="text-sm text-slate-500">Nothing yet.</p>}
      <ul className="space-y-3">
        {history.data?.map((h) => (
          <li key={h.id} className="card">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-semibold">
                {h.child_name} {h.outcome === 'released' ? 'collected by' : 'not released to'} {h.collector_name}
              </p>
              <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${h.outcome === 'released' ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800'}`}>
                {h.outcome === 'released' ? 'Released' : 'Refused'}
              </span>
            </div>
            <p className="mt-1 text-sm text-slate-600">
              {when(h.occurred_at)} · {h.collector_relationship} · authorised by {h.authorised_by_name} · checked by {h.staff_name}
            </p>
            {h.refusal_reason && <p className="mt-1 text-sm text-red-700">Reason: {h.refusal_reason}</p>}
          </li>
        ))}
      </ul>
    </>
  )
}
