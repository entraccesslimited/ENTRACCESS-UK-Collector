import { useParams } from 'react-router-dom'

import { Badge, QR } from '@/components/ui'
import { validity } from '@/lib/format'
import { useLoad } from '@/lib/useLoad'
import type { PublicPass as Pass } from '@/lib/types'

/** What the collector opens from the link the parent sent: a pass to show at the door. */
export function PublicPass() {
  const { token = '' } = useParams()
  const pass = useLoad<Pass>(`/public/pass/${encodeURIComponent(token)}`)
  return (
    <div className="flex min-h-screen items-center justify-center bg-ink p-4">
      <div className="card w-full max-w-sm text-center">
        <img src="/favicon.svg" alt="" className="mx-auto size-10 rounded-lg" />
        {pass.error && <p className="mt-4 font-semibold text-red-700">This pass is not valid. Ask the parent to send it again.</p>}
        {pass.data && (
          <>
            <p className="mt-3 text-sm text-slate-500">{pass.data.nursery_name}</p>
            <h1 className="text-xl font-bold">{pass.data.collector_name}</h1>
            <p className="text-sm text-slate-600">collecting {pass.data.child_first_name}</p>
            <div className="my-4 flex justify-center">
              <Badge status={pass.data.status} />
            </div>
            {pass.data.status === 'valid' || pass.data.status === 'not_yet_valid' ? (
              <QR text={pass.data.token} size={260} />
            ) : (
              <p className="rounded-lg bg-slate-100 p-4 text-sm">This pass can no longer be used. Contact the parent.</p>
            )}
            <p className="mt-4 text-sm text-slate-600">{validity(pass.data)}</p>
            <p className="mt-3 text-xs text-slate-500">Show this at the door. Staff will also ask to see photo ID.</p>
          </>
        )}
      </div>
    </div>
  )
}
