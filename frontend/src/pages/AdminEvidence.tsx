import { useSearchParams } from 'react-router-dom'

import { Alert } from '@/components/ui'
import { day, FLAG_LABEL, ID_CHECK_LABEL, RESTRICTION_LABEL, STATUS_LABEL, when } from '@/lib/format'
import { useLoad } from '@/lib/useLoad'
import type { Evidence } from '@/lib/types'

const KIND_LABEL: Record<string, string> = {
  released: 'Released',
  refused: 'Refused',
  blocked: 'Check refused',
  authorisation: 'Collector',
  contact: 'Contact',
  contacts: 'Contacts',
  restriction: 'Never-release',
  pass: 'Pass sent',
  child: 'Child',
  signouts: 'Register',
  reconciliation: 'Register',
}

/** One printable document: what the record holds about collections in a period. */
export function AdminEvidence() {
  const [params] = useSearchParams()
  const query = params.toString()
  const pack = useLoad<Evidence>(`/admin/evidence?${query}`)
  const e = pack.data
  const date = (iso: string) => day(`${iso}T12:00:00Z`)

  return (
    <article className="evidence space-y-6 print:text-[11px]">
      <div className="flex flex-wrap gap-2 print:hidden">
        <button className="btn btn-primary" onClick={() => window.print()} disabled={!e}>
          Print or save as PDF
        </button>
        <a className="btn btn-secondary" href={`/api/admin/evidence.csv?${query}`}>
          Timeline as CSV
        </a>
      </div>
      {pack.error && <Alert>{pack.error}</Alert>}
      {pack.loading && <p className="text-sm text-slate-500">Building the evidence pack…</p>}
      {e && (
        <>
          <header className="border-b border-slate-300 pb-3">
            <p className="text-xs uppercase tracking-wide text-slate-500">Collection evidence pack</p>
            <h1 className="text-2xl font-bold">{e.nursery_name}</h1>
            <p className="text-sm">
              {e.child_name ?? 'All children'} · {date(e.start)} to {date(e.end)}
            </p>
            <p className="text-xs text-slate-500">
              Generated {when(e.generated_at)} by {e.generated_by}, from the ENTRACCESS UK Collector record. Handovers and door
              checks in this record cannot be edited.
            </p>
          </header>

          <Section title="Summary">
            <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm sm:grid-cols-3">
              {[
                ['Released', e.kpis.releases],
                ['Refused by staff', e.kpis.refusals],
                ['Refused by the app', e.kpis.blocked_checks],
                ['Collectors added (parents / nursery)', `${e.kpis.collectors_added_by_parents} / ${e.kpis.contacts_added_by_nursery}`],
                ['Collectors removed', e.kpis.collectors_removed],
                ['Never-release in force', e.kpis.restrictions_in_force],
                ['Days reconciled', `${e.kpis.registers_imported} of ${e.kpis.days_with_releases} with releases`],
                ['Reconciliation flags', Object.values(e.kpis.reconciliation_flags).reduce((a, b) => a + (b ?? 0), 0)],
                [
                  'ID checks',
                  Object.entries(e.kpis.id_checks)
                    .map(([m, n]) => `${m === 'not_recorded' ? 'not recorded' : ID_CHECK_LABEL[m as keyof typeof ID_CHECK_LABEL]} ${n}`)
                    .join(', ') || '—',
                ],
              ].map(([label, value]) => (
                <div key={String(label)}>
                  <dt className="text-slate-500">{label}</dt>
                  <dd className="font-semibold">{value}</dd>
                </div>
              ))}
            </dl>
          </Section>

          <Section title="Never-release list" empty={e.restrictions.length === 0 ? 'Nobody in this period.' : undefined}>
            <Rows
              head={['Child', 'Person', 'Reason', 'Reference', 'Added', 'Ended']}
              rows={e.restrictions.map((r) => [
                r.child_name,
                r.person_name,
                RESTRICTION_LABEL[r.reason],
                r.reference ?? '—',
                `${day(r.created_at)}, ${r.created_by_name}`,
                r.ended_at ? day(r.ended_at) : 'In force',
              ])}
            />
          </Section>

          <Section title="Who could collect" empty={e.collectors.length === 0 ? 'No collectors in this period.' : undefined}>
            <Rows
              head={['Child', 'Collector', 'Type', 'Authorised by', 'From', 'Ended']}
              rows={e.collectors.map((c) => [
                c.child_name,
                `${c.collector_name} (${c.collector_relationship})`,
                `${c.kind === 'one_off' ? 'One-off' : 'Regular'}${c.source === 'setting' ? ', nursery contact' : ''}`,
                c.authorised_by_name,
                day(c.created_at),
                c.revoked_at ? `Removed ${day(c.revoked_at)}` : c.used_at ? `Used ${day(c.used_at)}` : c.valid_until ? `Until ${day(c.valid_until)}` : 'Current',
              ])}
            />
          </Section>

          <Section
            title="Register reconciliation"
            empty={e.registers.length === 0 ? 'No sign-out register was imported in this period.' : e.flagged.length === 0 ? `Every reconciled day matched (${e.registers.length} days).` : undefined}
          >
            <Rows
              head={['Day', 'Child', 'Register', 'Door', 'Flags']}
              rows={e.flagged.map((f) => [
                date(f.day),
                f.child_name,
                f.signed_out_at ? `${when(f.signed_out_at)}${f.register_collected_by ? `, ${f.register_collected_by}` : ''}` : '—',
                f.released_at ? `${when(f.released_at)}, ${f.collector_name}` : 'Not released',
                f.flags.map((x) => FLAG_LABEL[x]).join('; '),
              ])}
            />
          </Section>

          <Section title="Timeline" empty={e.events.length === 0 ? 'Nothing recorded in this period.' : undefined}>
            <Rows
              head={['When', 'What', 'Child', 'Detail', 'Who']}
              rows={e.events.map((ev) => [when(ev.at), KIND_LABEL[ev.kind] ?? ev.kind, ev.child || '—', readable(ev.detail), ev.who])}
            />
          </Section>
          <p className="text-xs text-slate-500">
            This pack supports the setting’s own safeguarding records. It is not a regulatory certification.
          </p>
        </>
      )}
    </article>
  )
}

/** Door results appear in the detail as their code; show the staff wording. */
function readable(detail: string): string {
  return detail.replace(/Check refused: ([a-z ]+)/, (_m, code: string) => {
    const label = STATUS_LABEL[code.trim().replace(/ /g, '_') as keyof typeof STATUS_LABEL]
    return `Check refused: ${label ?? code}`
  })
}

function Section({ title, empty, children }: { title: string; empty?: string; children?: React.ReactNode }) {
  return (
    <section className="break-inside-avoid-page">
      <h2 className="mb-2 border-b border-slate-200 pb-1 text-lg font-semibold">{title}</h2>
      {empty ? <p className="text-sm text-slate-500">{empty}</p> : children}
    </section>
  )
}

function Rows({ head, rows }: { head: string[]; rows: (string | number)[][] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr>
            {head.map((h) => (
              <th key={h} className="text-left">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => (
                <td key={j} className="align-top">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
