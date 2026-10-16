import { useState, type FormEvent } from 'react'

import { Alert, PageTitle, Stat } from '@/components/ui'
import { api } from '@/lib/api'
import { day } from '@/lib/format'
import { useLoad } from '@/lib/useLoad'
import type { CompanyOverview, NurseryRow } from '@/lib/types'

/** The company portal: every nursery, by the numbers. No child is ever named here. */
export function CompanyHome() {
  const overview = useLoad<CompanyOverview>('/company/overview')
  const list = useLoad<NurseryRow[]>('/company/nurseries')
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [confirming, setConfirming] = useState<string | null>(null)

  const reload = async () => {
    await Promise.all([overview.reload(), list.reload()])
  }

  const toggle = async (row: NurseryRow) => {
    setError(null)
    try {
      await api(`/company/nurseries/${row.id}/${row.active ? 'suspend' : 'reactivate'}`, { method: 'POST' })
      setMessage(
        row.active
          ? `${row.name} suspended. Nobody there can sign in until it is reactivated; nothing has been deleted.`
          : `${row.name} reactivated.`,
      )
      setConfirming(null)
      await reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'That did not work.')
    }
  }

  return (
    <>
      <PageTitle title="Nurseries" sub="Every nursery on ENTRACCESS UK Collector. Counts only: children’s and families’ details stay with each nursery." />
      {overview.data && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat label="Nurseries active" value={overview.data.active_nurseries} tone="green" />
          <Stat label="Children" value={overview.data.children} />
          <Stat label="Collections, last 30 days" value={overview.data.collections_30d} />
          <Stat label="Door exceptions, last 30 days" value={overview.data.exceptions_30d} tone="amber" />
        </div>
      )}
      <div className="mt-4 space-y-2">
        {error && <Alert>{error}</Alert>}
        {message && <Alert tone="ok">{message}</Alert>}
      </div>

      <section className="card mt-4 overflow-x-auto p-0">
        <table className="w-full">
          <thead className="bg-slate-50">
            <tr>
              <th>Nursery</th>
              <th>Children</th>
              <th>Parents</th>
              <th>Room leaders</th>
              <th>Collectors</th>
              <th>Collections (30 days)</th>
              <th>Exceptions (30 days)</th>
              <th>Geofence</th>
              <th />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {list.data?.map((row) => (
              <tr key={row.id} className={row.active ? '' : 'bg-slate-50 text-slate-400'}>
                <td>
                  <span className="font-medium">{row.name}</span>
                  <span className="block text-xs text-slate-500">
                    {row.slug} · since {day(row.created_at)} · {row.managers} manager{row.managers === 1 ? '' : 's'}
                    {!row.active && ' · suspended'}
                  </span>
                </td>
                <td>{row.children}</td>
                <td>{row.parents}</td>
                <td>{row.room_leaders}</td>
                <td>{row.active_collectors}</td>
                <td>{row.collections_30d}</td>
                <td className={row.exceptions_30d ? 'text-amber-700' : ''}>{row.exceptions_30d}</td>
                <td>{row.geofence_on ? 'On' : 'Off'}</td>
                <td className="text-right">
                  {confirming === row.id ? (
                    <button className={`btn ${row.active ? 'btn-danger' : 'btn-success'}`} onClick={() => toggle(row)}>
                      {row.active ? 'Yes, suspend' : 'Yes, reactivate'}
                    </button>
                  ) : (
                    <button className="btn btn-secondary" onClick={() => setConfirming(row.id)}>
                      {row.active ? 'Suspend' : 'Reactivate'}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {list.data?.length === 0 && <p className="p-4 text-sm text-slate-500">No nurseries yet.</p>}
      </section>

      <AddNursery onAdded={async (name) => {
        setMessage(`${name} is set up. Give the manager their password in person or by phone; they add everyone else.`)
        await reload()
      }} />
    </>
  )
}

function AddNursery({ onAdded }: { onAdded: (name: string) => Promise<void> }) {
  const blank = { name: '', slug: '', manager_name: '', manager_email: '', manager_password: '' }
  const [form, setForm] = useState(blank)
  const [slugTouched, setSlugTouched] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const slugify = (name: string) =>
    name
      .toLowerCase()
      .replace(/\(.*?\)/g, '')
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 50)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api('/company/nurseries', { method: 'POST', json: form })
      const name = form.name
      setForm(blank)
      setSlugTouched(false)
      await onAdded(name)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not set the nursery up.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="card mt-6 grid gap-3 sm:grid-cols-2">
      <h2 className="text-lg font-semibold sm:col-span-2">Set up a nursery</h2>
      {error && <div className="sm:col-span-2"><Alert>{error}</Alert></div>}
      <label>
        <span className="label">Nursery name</span>
        <input
          className="input"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value, slug: slugTouched ? form.slug : slugify(e.target.value) })}
          placeholder="Little Acorns Nursery, Sheffield"
          required
        />
      </label>
      <label>
        <span className="label">Address (letters, numbers, hyphens)</span>
        <input
          className="input font-mono"
          value={form.slug}
          onChange={(e) => {
            setSlugTouched(true)
            setForm({ ...form, slug: e.target.value })
          }}
          placeholder="little-acorns-sheffield"
          required
        />
      </label>
      <label>
        <span className="label">First manager’s name</span>
        <input className="input" value={form.manager_name} onChange={(e) => setForm({ ...form, manager_name: e.target.value })} required />
      </label>
      <label>
        <span className="label">First manager’s email</span>
        <input className="input" type="email" value={form.manager_email} onChange={(e) => setForm({ ...form, manager_email: e.target.value })} required />
      </label>
      <label className="sm:col-span-2">
        <span className="label">Starting password for the manager (at least 10 characters)</span>
        <input
          className="input"
          type="text"
          autoComplete="new-password"
          value={form.manager_password}
          onChange={(e) => setForm({ ...form, manager_password: e.target.value })}
          minLength={10}
          required
        />
      </label>
      <div className="sm:col-span-2">
        <button className="btn btn-primary" disabled={busy || form.manager_password.length < 10}>
          {busy ? 'Setting up…' : 'Set up nursery'}
        </button>
      </div>
    </form>
  )
}
