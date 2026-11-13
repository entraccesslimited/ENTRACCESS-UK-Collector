import { useRef, useState } from 'react'

import { Alert, PageTitle, Stat } from '@/components/ui'
import { api } from '@/lib/api'
import { clock, day, FLAG_LABEL, ID_CHECK_LABEL, todayIso, when } from '@/lib/format'
import { useLoad } from '@/lib/useLoad'
import type { Reconciliation, SignOutImport } from '@/lib/types'

const MAX_BYTES = 1_000_000

export function AdminReconciliation() {
  const [date, setDate] = useState(todayIso())
  const result = useLoad<Reconciliation>(`/admin/reconciliation?day=${date}`)
  const file = useRef<HTMLInputElement>(null)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const upload = async (chosen: File) => {
    setError(null)
    setMessage(null)
    if (chosen.size > MAX_BYTES) {
      setError('That file is too large. Export one day at a time.')
      return
    }
    setBusy(true)
    try {
      const imported = await api<SignOutImport>('/admin/sign-outs/import', {
        method: 'POST',
        json: { day: date, csv: await chosen.text(), source: chosen.name },
      })
      setMessage(`${imported.rows} sign-out${imported.rows === 1 ? '' : 's'} imported from ${imported.source}.`)
      await result.reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not import the register.')
    } finally {
      setBusy(false)
      if (file.current) file.current.value = ''
    }
  }

  const data = result.data
  const imported = data?.register_import

  return (
    <>
      <PageTitle
        title="Reconcile"
        sub="Compare the door record with the sign-out register from your nursery system. Every child who left should have been released at the door, to the person the register names."
      />
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <label>
          <span className="label">Day</span>
          <input className="input" type="date" max={todayIso()} value={date} onChange={(e) => setDate(e.target.value)} />
        </label>
        <input
          ref={file}
          type="file"
          accept=".csv,text/csv,text/plain"
          className="hidden"
          onChange={(e) => {
            const chosen = e.target.files?.[0]
            if (chosen) void upload(chosen)
          }}
        />
        <button className="btn btn-primary" disabled={busy} onClick={() => file.current?.click()}>
          {busy ? 'Importing…' : imported ? 'Import again' : 'Import sign-out register (CSV)'}
        </button>
        {imported && (
          <a className="btn btn-secondary" href={`/api/admin/reconciliation.csv?day=${date}`}>
            Export CSV
          </a>
        )}
      </div>

      {error && <div className="mb-4"><Alert>{error}</Alert></div>}
      {message && <div className="mb-4"><Alert tone="ok">{message}</Alert></div>}
      {result.error && <Alert>{result.error}</Alert>}

      {data && !imported && (
        <div className="card mb-4 text-sm text-slate-700">
          <p className="font-semibold">No register imported for {day(`${date}T12:00:00Z`)}.</p>
          <p className="mt-1">
            Export the day’s sign-outs from your nursery system as CSV. It needs a column for the child’s name (or first name
            and surname) and one for the time signed out. A “Collected by” column is checked against the door too.
          </p>
          <p className="mt-2 font-mono text-xs text-slate-500">Child,Signed out,Collected by<br />Maya Hughes,15:42,Grace Hughes</p>
        </div>
      )}

      {data && imported && (
        <>
          <p className="mb-3 text-sm text-slate-600">
            Register from <b>{imported.source}</b>, {imported.rows} sign-outs, imported {when(imported.imported_at)}
            {imported.imported_by_name ? ` by ${imported.imported_by_name}` : ''}.
          </p>
          <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-3">
            <Stat label="Need a look" value={data.flagged} tone={data.flagged ? 'red' : 'green'} />
            <Stat label="Matched" value={data.matched} tone="green" />
          </div>
        </>
      )}

      {data && data.lines.length > 0 && (
        <div className="card overflow-x-auto p-0">
          <table className="w-full">
            <thead className="bg-slate-50">
              <tr>
                <th>Child</th>
                <th>Register</th>
                <th>Door</th>
                <th>{imported ? 'Result' : ''}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.lines.map((line, index) => (
                <tr key={`${line.child_id ?? line.child_name}-${index}`} className={line.flags.length ? 'bg-red-50/60' : ''}>
                  <td className="font-medium">{line.child_name}</td>
                  <td className="whitespace-nowrap">
                    {line.signed_out_at ? (
                      <>
                        {clock(line.signed_out_at)}
                        {line.register_collected_by && <span className="block text-xs text-slate-500">{line.register_collected_by}</span>}
                      </>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td>
                    {line.released_at ? (
                      <>
                        {clock(line.released_at)} · {line.collector_name}
                        <span className="block text-xs text-slate-500">
                          {line.collector_relationship} · checked by {line.staff_name}
                          {line.id_check_method ? ` · ${ID_CHECK_LABEL[line.id_check_method]}` : ''}
                        </span>
                      </>
                    ) : (
                      <span className="text-slate-500">Not released</span>
                    )}
                    {line.refusals.map((r) => (
                      <span key={r} className="block text-xs text-red-700">Refused {r}</span>
                    ))}
                  </td>
                  <td>
                    {!imported ? null : line.flags.length === 0 ? (
                      <span className="text-emerald-700">✓ Matches</span>
                    ) : (
                      <ul className="space-y-0.5 text-sm font-medium text-red-700">
                        {line.flags.map((f) => (
                          <li key={f}>{FLAG_LABEL[f]}</li>
                        ))}
                      </ul>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {data && data.lines.length === 0 && imported && <p className="text-sm text-slate-500">No sign-outs or releases on this day.</p>}
    </>
  )
}
