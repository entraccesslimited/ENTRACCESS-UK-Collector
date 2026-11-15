import { useState, type FormEvent } from 'react'

import { Alert, PageTitle } from '@/components/ui'
import { api } from '@/lib/api'
import { useSession } from '@/lib/session'
import { useLoad } from '@/lib/useLoad'
import type { Person, Role } from '@/lib/types'

const ROLE_LABEL: Record<Role, string> = {
  admin: 'Manager',
  staff: 'Room leader',
  parent: 'Parent',
  operator: 'ENTRACCESS UK',
}

export function AdminPeople() {
  const { me } = useSession()
  const people = useLoad<Person[]>('/admin/people')
  const blank = { email: '', full_name: '', phone: '', role: 'parent' as Role, password: '' }
  const [form, setForm] = useState(blank)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  // The default is the email: they choose their own password from a link, so
  // nobody else knows it. A starting password is for somebody you will hand
  // it to in person.
  const [setItMyself, setSetItMyself] = useState(false)

  const add = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    setMessage(null)
    try {
      const { password, ...rest } = form
      await api('/admin/people', {
        method: 'POST',
        json: { ...rest, phone: form.phone || null, ...(setItMyself ? { password } : {}) },
      })
      setMessage(
        setItMyself
          ? `${form.full_name} added and emailed where to sign in. Give them their password in person or by phone, never by email.`
          : `${form.full_name} added. We have emailed ${form.email} a link to choose their own password.`,
      )
      setForm(blank)
      setSetItMyself(false)
      await people.reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not add them.')
    }
  }

  const resend = async (person: Person) => {
    setError(null)
    setMessage(null)
    try {
      await api(`/admin/people/${person.id}/resend-invitation`, { method: 'POST' })
      setMessage(`A new link is on its way to ${person.email}.`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not send the invitation again.')
    }
  }

  const deactivate = async (person: Person) => {
    setError(null)
    try {
      await api(`/admin/people/${person.id}/deactivate`, { method: 'POST' })
      await people.reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not switch them off.')
    }
  }

  return (
    <>
      <PageTitle title="People" sub="Managers, room leaders and parents. Parents are linked to their children on the Children page." />
      {error && <Alert>{error}</Alert>}
      {message && <Alert tone="ok">{message}</Alert>}
      <form onSubmit={add} className="card my-4 grid gap-3 sm:grid-cols-2">
        <label>
          <span className="label">Full name</span>
          <input className="input" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required />
        </label>
        <label>
          <span className="label">Email</span>
          <input className="input" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
        </label>
        <label>
          <span className="label">Phone (optional)</span>
          <input className="input" type="tel" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
        </label>
        <label>
          <span className="label">Role</span>
          <select className="input" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Role })}>
            <option value="parent">Parent</option>
            <option value="staff">Room leader</option>
            <option value="admin">Manager</option>
          </select>
        </label>
        <label className="flex items-start gap-2 text-sm sm:col-span-2">
          <input type="checkbox" className="mt-1" checked={setItMyself} onChange={(e) => setSetItMyself(e.target.checked)} />
          <span>
            Set a starting password myself
            <span className="block text-xs text-slate-500">
              {setItMyself
                ? 'They are emailed where to sign in, never the password. Give it to them yourself.'
                : 'Left unticked, they are emailed a link to choose their own password. Nobody else ever knows it.'}
            </span>
          </span>
        </label>
        {setItMyself && (
          <label className="sm:col-span-2">
            <span className="label">Starting password (at least 10 characters)</span>
            <input className="input" type="text" autoComplete="new-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required minLength={10} />
          </label>
        )}
        <div className="sm:col-span-2">
          <button className="btn btn-primary" disabled={!form.full_name || !form.email || (setItMyself && form.password.length < 10)}>
            {setItMyself ? 'Add person' : 'Add and send invitation'}
          </button>
        </div>
      </form>
      <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead className="bg-slate-50">
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Role</th>
              <th />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {people.data?.map((p) => (
              <tr key={p.id} className={p.active ? '' : 'text-slate-400'}>
                <td className="font-medium">{p.full_name}</td>
                <td>{p.email}</td>
                <td>
                  {ROLE_LABEL[p.role]}
                  {p.invitation_pending && (
                    <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800">
                      Invitation sent
                    </span>
                  )}
                </td>
                <td className="space-x-2 text-right whitespace-nowrap">
                  {p.active && p.invitation_pending && (
                    <button className="btn btn-secondary" onClick={() => resend(p)}>
                      Resend invitation
                    </button>
                  )}
                  {p.active && p.id !== me?.id ? (
                    <button className="btn btn-secondary" onClick={() => deactivate(p)}>
                      Switch off
                    </button>
                  ) : (
                    !p.active && 'Switched off'
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
