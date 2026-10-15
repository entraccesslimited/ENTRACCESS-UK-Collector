import { useState, type FormEvent } from 'react'

import { Alert, Badge, Modal, PageTitle } from '@/components/ui'
import { api } from '@/lib/api'
import { validity } from '@/lib/format'
import { useLoad } from '@/lib/useLoad'
import type { Authorisation, Child, Link, Person } from '@/lib/types'

export function AdminChildren() {
  const children = useLoad<Child[]>('/admin/children')
  const links = useLoad<Link[]>('/admin/links')
  const people = useLoad<Person[]>('/admin/people')
  const [form, setForm] = useState({ full_name: '', room: '' })
  const [error, setError] = useState<string | null>(null)
  const [open, setOpen] = useState<Child | null>(null)

  const add = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    try {
      await api('/admin/children', { method: 'POST', json: { full_name: form.full_name, room: form.room || null } })
      setForm({ full_name: '', room: '' })
      await children.reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not add the child.')
    }
  }

  return (
    <>
      <PageTitle title="Children" sub="Link each child to their parents, so they can authorise collectors." />
      {error && <Alert>{error}</Alert>}
      <form onSubmit={add} className="card mb-6 flex flex-wrap items-end gap-3">
        <label className="flex-1">
          <span className="label">Child’s full name</span>
          <input className="input" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required />
        </label>
        <label>
          <span className="label">Room</span>
          <input className="input" value={form.room} onChange={(e) => setForm({ ...form, room: e.target.value })} />
        </label>
        <button className="btn btn-primary" disabled={form.full_name.trim().length < 2}>
          Add child
        </button>
      </form>
      <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead className="bg-slate-50">
            <tr>
              <th>Child</th>
              <th>Room</th>
              <th>Parents</th>
              <th />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {children.data?.map((c) => (
              <tr key={c.id} className={c.active ? '' : 'text-slate-400'}>
                <td className="font-medium">
                  {c.full_name} {!c.active && '(left)'}
                </td>
                <td>{c.room ?? '—'}</td>
                <td>
                  {links.data
                    ?.filter((l) => l.child_id === c.id)
                    .map((l) => l.parent_name)
                    .join(', ') || <span className="text-amber-700">None linked</span>}
                </td>
                <td className="text-right">
                  <button className="btn btn-secondary" onClick={() => setOpen(c)}>
                    Manage
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {open && (
        <ManageChild
          child={open}
          parents={(people.data ?? []).filter((p) => p.role === 'parent' && p.active)}
          onClose={() => setOpen(null)}
          onChanged={async () => {
            await Promise.all([children.reload(), links.reload()])
          }}
        />
      )}
    </>
  )
}

function ManageChild({ child, parents, onClose, onChanged }: { child: Child; parents: Person[]; onClose: () => void; onChanged: () => Promise<void> }) {
  const collectors = useLoad<Authorisation[]>(`/admin/children/${child.id}/collectors`)
  const [parentId, setParentId] = useState('')
  const [relationship, setRelationship] = useState('Parent')
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [confirmLeave, setConfirmLeave] = useState(false)

  const run = async (fn: () => Promise<unknown>, done: string) => {
    setError(null)
    try {
      await fn()
      setMessage(done)
      await Promise.all([collectors.reload(), onChanged()])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'That did not work.')
    }
  }

  return (
    <Modal open title={child.full_name} onClose={onClose}>
      <div className="space-y-5">
        {error && <Alert>{error}</Alert>}
        {message && <Alert tone="ok">{message}</Alert>}
        <section>
          <h3 className="mb-2 font-semibold">Link a parent</h3>
          <div className="flex flex-wrap gap-2">
            <select className="input flex-1" value={parentId} onChange={(e) => setParentId(e.target.value)}>
              <option value="">Choose a parent account…</option>
              {parents.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.full_name} ({p.email})
                </option>
              ))}
            </select>
            <input className="input w-32" value={relationship} onChange={(e) => setRelationship(e.target.value)} />
            <button
              className="btn btn-primary"
              disabled={!parentId}
              onClick={() =>
                run(
                  () => api('/admin/links', { method: 'POST', json: { parent_id: parentId, child_id: child.id, relationship_label: relationship } }),
                  'Parent linked.',
                )
              }
            >
              Link
            </button>
          </div>
          <p className="mt-1 text-xs text-slate-500">Only people with parental responsibility should be linked: they can authorise collectors.</p>
        </section>
        <section>
          <h3 className="mb-2 font-semibold">Collectors</h3>
          {collectors.data?.length === 0 && <p className="text-sm text-slate-500">None yet.</p>}
          <ul className="divide-y divide-slate-100">
            {collectors.data?.map((a) => (
              <li key={a.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                <span>
                  <b>{a.collector_name}</b> · {a.collector_relationship} · {validity(a)}
                  <br />
                  <span className="text-slate-500">authorised by {a.authorised_by_name}</span>
                </span>
                <span className="flex items-center gap-2">
                  <Badge status={a.status} />
                  {(a.status === 'valid' || a.status === 'not_yet_valid') && (
                    <button
                      className="btn btn-secondary text-red-700"
                      onClick={() => run(() => api(`/admin/collectors/${a.id}/revoke`, { method: 'POST' }), `${a.collector_name} removed.`)}
                    >
                      Remove
                    </button>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </section>
        {child.active && (
          <section className="border-t border-slate-100 pt-4">
            {confirmLeave ? (
              <button
                className="btn btn-danger"
                onClick={() => run(() => api(`/admin/children/${child.id}/leave`, { method: 'POST' }), `${child.full_name} marked as left; every collector removed.`)}
              >
                Yes, mark as left and remove all collectors
              </button>
            ) : (
              <button className="btn btn-secondary" onClick={() => setConfirmLeave(true)}>
                Child has left the nursery
              </button>
            )}
          </section>
        )}
      </div>
    </Modal>
  )
}
