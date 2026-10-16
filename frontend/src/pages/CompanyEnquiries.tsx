import { Alert, PageTitle } from '@/components/ui'
import { api } from '@/lib/api'
import { when } from '@/lib/format'
import { useLoad } from '@/lib/useLoad'

interface Enquiry {
  id: string
  contact_name: string
  nursery_name: string
  email: string
  phone: string | null
  region: string | null
  children: string | null
  interest: string | null
  message: string | null
  created_at: string
  handled_at: string | null
  handled_by: string | null
}

const INTEREST: Record<string, string> = {
  pilot: 'Paid pilot',
  core: 'Core',
  safeguard_pro: 'Safeguard Pro',
  group: 'Group',
  question: 'Question',
}

/** Enquiries from the website, newest first. */
export function CompanyEnquiries() {
  const rows = useLoad<Enquiry[]>('/company/enquiries')
  const open = rows.data?.filter((r) => !r.handled_at) ?? []
  const done = rows.data?.filter((r) => r.handled_at) ?? []

  const handled = async (id: string) => {
    await api(`/company/enquiries/${id}/handled`, { method: 'POST' })
    await rows.reload()
  }

  return (
    <>
      <PageTitle title="Enquiries" sub="Settings that got in touch through the website. Reply from your own mailbox, then mark them handled." />
      {rows.error && <Alert>{rows.error}</Alert>}
      {rows.data && open.length === 0 && <p className="text-sm text-slate-500">Nothing waiting.</p>}
      <div className="space-y-3">
        {[...open, ...done].map((r) => (
          <div key={r.id} className={`card ${r.handled_at ? 'opacity-60' : ''}`}>
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <p className="font-semibold text-ink">
                  {r.nursery_name} <span className="font-normal text-slate-500">· {r.contact_name}</span>
                </p>
                <p className="text-sm text-slate-600">
                  <a className="text-brand-700 underline" href={`mailto:${r.email}`}>{r.email}</a>
                  {r.phone && <> · {r.phone}</>}
                  {r.region && <> · {r.region}</>}
                  {r.children && <> · {r.children} children</>}
                </p>
              </div>
              <div className="text-right text-xs text-slate-500">
                <p>{when(r.created_at)}</p>
                {r.interest && <p className="font-semibold text-slate-700">{INTEREST[r.interest] ?? r.interest}</p>}
              </div>
            </div>
            {r.message && <p className="mt-3 whitespace-pre-wrap text-sm">{r.message}</p>}
            <div className="mt-3">
              {r.handled_at ? (
                <p className="text-xs text-slate-500">Handled {when(r.handled_at)} by {r.handled_by}</p>
              ) : (
                <button className="btn btn-secondary" onClick={() => handled(r.id)}>
                  Mark handled
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </>
  )
}
