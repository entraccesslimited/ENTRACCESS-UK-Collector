import { useState } from 'react'
import { Link } from 'react-router-dom'

import { Alert, PageTitle, Stat } from '@/components/ui'
import { FLAG_LABEL, ID_CHECK_LABEL, STATUS_LABEL, todayIso } from '@/lib/format'
import { useLoad } from '@/lib/useLoad'
import type { Child, Kpis } from '@/lib/types'

export function daysAgo(n: number): string {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return d.toLocaleDateString('en-CA', { timeZone: 'Europe/London' })
}

export function AdminReports() {
  const [start, setStart] = useState(daysAgo(29))
  const [end, setEnd] = useState(todayIso())
  const [childId, setChildId] = useState('')
  const children = useLoad<Child[]>('/admin/children')
  const query = `start=${start}&end=${end}${childId ? `&child_id=${childId}` : ''}`
  const kpis = useLoad<Kpis>(`/admin/kpis?${query}`)
  const k = kpis.data

  return (
    <>
      <PageTitle title="Reports" sub="What happened at the door over a period, and an evidence pack for an inspection or a safeguarding review." />
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <label>
          <span className="label">From</span>
          <input className="input" type="date" value={start} max={end} onChange={(e) => setStart(e.target.value)} />
        </label>
        <label>
          <span className="label">To</span>
          <input className="input" type="date" value={end} max={todayIso()} onChange={(e) => setEnd(e.target.value)} />
        </label>
        <label>
          <span className="label">Child</span>
          <select className="input" value={childId} onChange={(e) => setChildId(e.target.value)}>
            <option value="">All children</option>
            {children.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.full_name}
              </option>
            ))}
          </select>
        </label>
        {!childId && (
          <a className="btn btn-secondary" href={`/api/admin/kpis.csv?start=${start}&end=${end}`}>
            Export KPIs (CSV)
          </a>
        )}
        <Link className="btn btn-primary" to={`/admin/evidence?${query}`}>
          Evidence pack
        </Link>
      </div>
      {kpis.error && <Alert>{kpis.error}</Alert>}
      {k && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Released" value={k.releases} tone="green" />
            <Stat label="Refused by staff" value={k.refusals} tone="red" />
            <Stat label="Refused by the app" value={k.blocked_checks} tone="amber" />
            <Stat label="Never-release in force" value={k.restrictions_in_force} />
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <Table
              title="How staff checked identity"
              rows={Object.entries(k.id_checks).map(([m, n]) => [m === 'not_recorded' ? 'Not recorded' : ID_CHECK_LABEL[m as keyof typeof ID_CHECK_LABEL], n ?? 0])}
              empty="No releases."
            />
            <Table
              title="Why the app refused a check"
              rows={Object.entries(k.blocked_by_result).map(([r, n]) => [STATUS_LABEL[r as keyof typeof STATUS_LABEL] ?? r, n ?? 0])}
              empty="None refused."
            />
            <Table title="Why staff refused" rows={k.refusal_reasons} empty="No refusals." />
            <Table
              title="Collectors"
              rows={[
                ['Added by parents', k.collectors_added_by_parents],
                ['of which one-off', k.one_off_collectors],
                ['Added by the nursery', k.contacts_added_by_nursery],
                ['Removed', k.collectors_removed],
                ['Passes sent', k.passes_shared],
                ['Never-release added', k.restrictions_added],
              ]}
            />
            <Table
              title="Sign-out register"
              rows={[
                ['Days with releases', k.days_with_releases],
                ['Days reconciled', k.registers_imported],
                ['Days with releases, not reconciled', k.days_without_register],
              ]}
            />
            <Table
              title="Reconciliation flags"
              rows={Object.entries(k.reconciliation_flags).map(([f, n]) => [FLAG_LABEL[f as keyof typeof FLAG_LABEL] ?? f, n ?? 0])}
              empty={k.registers_imported ? 'Every reconciled day matched.' : 'No register imported in this period.'}
            />
          </div>
        </div>
      )}
    </>
  )
}

function Table({ title, rows, empty }: { title: string; rows: [string, number][]; empty?: string }) {
  return (
    <section className="card">
      <h2 className="mb-2 font-semibold">{title}</h2>
      {rows.length === 0 ? (
        <p className="text-sm text-slate-500">{empty}</p>
      ) : (
        <table className="w-full text-sm">
          <tbody className="divide-y divide-slate-100">
            {rows.map(([label, value]) => (
              <tr key={label}>
                <td className="py-1.5">{label}</td>
                <td className="py-1.5 text-right font-semibold tabular-nums">{value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
