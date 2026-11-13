import { useRef, useState, type FormEvent } from 'react'

import { SharePass } from '@/components/SharePass'
import { Alert, Badge, Modal, PageTitle, QR } from '@/components/ui'
import { api } from '@/lib/api'
import { code, day, RESTRICTION_LABEL, validity } from '@/lib/format'
import { useLoad } from '@/lib/useLoad'
import type { Authorisation, Child, Link, PassInfo, Person, Restriction, RestrictionReason } from '@/lib/types'

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
      <ImportContacts />
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
  const [sending, setSending] = useState<Authorisation | null>(null)

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
                  <span className="text-slate-500">
                    {a.source === 'setting' ? `nursery contact, added by ${a.authorised_by_name}` : `authorised by ${a.authorised_by_name}`}
                  </span>
                </span>
                <span className="flex items-center gap-2">
                  <Badge status={a.status} />
                  {a.source === 'setting' && (a.status === 'valid' || a.status === 'not_yet_valid') && (
                    <button className="btn btn-secondary" onClick={() => setSending(sending?.id === a.id ? null : a)}>
                      Pass &amp; send
                    </button>
                  )}
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
        {sending && <ContactPass auth={sending} onClose={() => setSending(null)} />}
        {child.active && <AddContact child={child} onAdded={(name) => run(async () => undefined, `${name} added. The parents have been emailed.`)} />}
        <NeverRelease child={child} onChanged={() => collectors.reload()} />
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

const REASONS: RestrictionReason[] = ['court_order', 'safeguarding', 'parent_request', 'other']

function NeverRelease({ child, onChanged }: { child: Child; onChanged: () => Promise<void> }) {
  const list = useLoad<Restriction[]>(`/admin/children/${child.id}/restrictions`)
  const empty = { person_name: '', reason: 'court_order' as RestrictionReason, reference: '', detail: '' }
  const [form, setForm] = useState(empty)
  const [adding, setAdding] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const run = async (fn: () => Promise<string>) => {
    setError(null)
    setMessage(null)
    try {
      setMessage(await fn())
      await Promise.all([list.reload(), onChanged()])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'That did not work.')
    }
  }

  const add = (event: FormEvent) => {
    event.preventDefault()
    void run(async () => {
      const made = await api<Restriction>(`/admin/children/${child.id}/restrictions`, {
        method: 'POST',
        json: { ...form, reference: form.reference || null, detail: form.detail || null },
      })
      setForm(empty)
      setAdding(false)
      return made.removed_collectors.length
        ? `${made.person_name} added. Removed as a collector: ${made.removed_collectors.join(', ')}.`
        : `${made.person_name} added to the never-release list.`
    })
  }

  const current = (list.data ?? []).filter((r) => !r.ended_at)
  const ended = (list.data ?? []).filter((r) => r.ended_at)

  return (
    <section className="rounded-lg border border-red-200 bg-red-50/50 p-3">
      <h3 className="font-semibold text-red-800">Never release to</h3>
      <p className="mb-2 text-xs text-slate-600">
        Room leaders see these names with every check for {child.full_name.split(' ')[0]}. Adding someone removes them as a
        collector at once, and parents cannot add them again.
      </p>
      {error && <div className="mb-2"><Alert>{error}</Alert></div>}
      {message && <div className="mb-2"><Alert tone="ok">{message}</Alert></div>}
      {current.length === 0 && <p className="text-sm text-slate-500">Nobody.</p>}
      <ul className="divide-y divide-red-100">
        {current.map((r) => (
          <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
            <span>
              <b>{r.person_name}</b> · {RESTRICTION_LABEL[r.reason]}
              {r.reference ? ` · ${r.reference}` : ''}
              {r.detail && <span className="block text-slate-600">{r.detail}</span>}
              <span className="block text-xs text-slate-500">
                Added {day(r.created_at)} by {r.created_by_name}
              </span>
            </span>
            <button
              className="btn btn-secondary"
              onClick={() =>
                run(async () => {
                  await api(`/admin/restrictions/${r.id}/end`, { method: 'POST' })
                  return `${r.person_name} is no longer on the list. Parents can add them as a collector again.`
                })
              }
            >
              End
            </button>
          </li>
        ))}
      </ul>
      {ended.length > 0 && (
        <details className="mt-1 text-xs text-slate-500">
          <summary className="cursor-pointer">Ended ({ended.length})</summary>
          <ul className="mt-1 space-y-1">
            {ended.map((r) => (
              <li key={r.id}>
                {r.person_name} · {RESTRICTION_LABEL[r.reason]} · {day(r.created_at)} to {r.ended_at ? day(r.ended_at) : ''}
              </li>
            ))}
          </ul>
        </details>
      )}
      {adding ? (
        <form onSubmit={add} className="mt-3 space-y-2">
          <label className="block">
            <span className="label">Full name, as on the order or record</span>
            <input className="input" value={form.person_name} onChange={(e) => setForm({ ...form, person_name: e.target.value })} required autoFocus />
          </label>
          <div className="flex flex-wrap gap-2">
            <label className="flex-1">
              <span className="label">Reason</span>
              <select className="input" value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value as RestrictionReason })}>
                {REASONS.map((r) => (
                  <option key={r} value={r}>
                    {RESTRICTION_LABEL[r]}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex-1">
              <span className="label">Reference (optional)</span>
              <input className="input" value={form.reference} maxLength={120} onChange={(e) => setForm({ ...form, reference: e.target.value })} placeholder="Order or case number" />
            </label>
          </div>
          <label className="block">
            <span className="label">Note for managers (optional)</span>
            <input className="input" value={form.detail} maxLength={500} onChange={(e) => setForm({ ...form, detail: e.target.value })} />
          </label>
          <div className="flex gap-2">
            <button className="btn btn-danger" disabled={form.person_name.trim().split(/\s+/).length < 2}>
              Add to the list
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => setAdding(false)}>
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <button className="btn btn-secondary mt-2" onClick={() => setAdding(true)}>
          Add someone
        </button>
      )}
    </section>
  )
}

function AddContact({ child, onAdded }: { child: Child; onAdded: (name: string) => void }) {
  const empty = { collector_name: '', collector_relationship: '', collector_phone: '', note_for_staff: '' }
  const [form, setForm] = useState(empty)
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const set = (key: keyof typeof form) => (event: { target: { value: string } }) => setForm({ ...form, [key]: event.target.value })

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    try {
      const made = await api<Authorisation>(`/admin/children/${child.id}/contacts`, {
        method: 'POST',
        json: { ...form, note_for_staff: form.note_for_staff || null },
      })
      setForm(empty)
      setOpen(false)
      onAdded(made.collector_name)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not add the contact.')
    }
  }

  if (!open) {
    return (
      <button className="btn btn-secondary" onClick={() => setOpen(true)}>
        Add a contact from the registration form
      </button>
    )
  }
  return (
    <form onSubmit={submit} className="space-y-2 rounded-lg border border-slate-200 p-3">
      <h3 className="font-semibold">Nursery contact</h3>
      <p className="text-xs text-slate-600">
        Someone the parents named on the registration form. They become a regular collector; both parents are emailed and can remove them.
      </p>
      {error && <Alert>{error}</Alert>}
      <input className="input" placeholder="Full name" value={form.collector_name} onChange={set('collector_name')} required />
      <div className="grid grid-cols-2 gap-2">
        <input className="input" placeholder="Relationship" value={form.collector_relationship} onChange={set('collector_relationship')} required />
        <input className="input" type="tel" placeholder="Phone" value={form.collector_phone} onChange={set('collector_phone')} required />
      </div>
      <input className="input" placeholder="Collection password (optional)" value={form.note_for_staff} maxLength={300} onChange={set('note_for_staff')} />
      <div className="flex gap-2">
        <button className="btn btn-primary">Add contact</button>
        <button type="button" className="btn btn-secondary" onClick={() => setOpen(false)}>
          Cancel
        </button>
      </div>
    </form>
  )
}

function ContactPass({ auth, onClose }: { auth: Authorisation; onClose: () => void }) {
  const pass = useLoad<PassInfo>(`/admin/collectors/${auth.id}/pass`)
  return (
    <section className="space-y-3 rounded-lg border border-brand-100 bg-brand-50/40 p-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">Pass for {auth.collector_name}</h3>
        <button className="text-sm text-slate-500" onClick={onClose}>
          Close
        </button>
      </div>
      {pass.error && <Alert>{pass.error}</Alert>}
      {pass.data && (
        <>
          <QR text={pass.data.token} size={180} />
          <p className="text-center font-mono text-2xl font-bold tracking-widest">{code(pass.data.code_today)}</p>
          <SharePass auth={auth} pass={pass.data} logPath={`/admin/collectors/${auth.id}/shared`} />
        </>
      )}
    </section>
  )
}

function ImportContacts() {
  const file = useRef<HTMLInputElement>(null)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const upload = async (chosen: File) => {
    setError(null)
    setMessage(null)
    setBusy(true)
    try {
      const result = await api<{ added: number; skipped: number }>('/admin/contacts/import', {
        method: 'POST',
        json: { csv: await chosen.text() },
      })
      setMessage(
        `${result.added} contact${result.added === 1 ? '' : 's'} added` +
          (result.skipped ? `, ${result.skipped} already there` : '') +
          '. Parents have been emailed the names added for their children.',
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not import the contacts.')
    } finally {
      setBusy(false)
      if (file.current) file.current.value = ''
    }
  }

  return (
    <div className="card mb-6 space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-semibold">Contacts from registration forms</h2>
          <p className="text-sm text-slate-600">
            Import the people parents named as able to collect: CSV with <span className="font-mono text-xs">Child, Contact name, Relationship, Phone</span> and optionally <span className="font-mono text-xs">Password</span>. All rows are added or none.
          </p>
        </div>
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
        <button className="btn btn-secondary" disabled={busy} onClick={() => file.current?.click()}>
          {busy ? 'Importing…' : 'Import contacts (CSV)'}
        </button>
      </div>
      {error && <Alert>{error}</Alert>}
      {message && <Alert tone="ok">{message}</Alert>}
    </div>
  )
}
