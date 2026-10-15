import { useState, type FormEvent } from 'react'

import { Alert, PageTitle } from '@/components/ui'
import { api } from '@/lib/api'
import { useSession } from '@/lib/session'
import { useLoad } from '@/lib/useLoad'
import type { Person, Role } from '@/lib/types'

const ROLE_LABEL: Record<Role, string> = { admin: 'Manager', staff: 'Staff', parent: 'Parent' }

export function AdminPeople() {
  const { me } = useSession()
  const people = useLoad<Person[]>('/admin/people')
  const blank = { email: '', full_name: '', phone: '', role: 'parent' as Role, password: '' }
  const [form, setForm] = useState(blank)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const add = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    setMessage(null)
    try {
      await api('/admin/people', { method: 'POST', json: { ...form, phone: form.phone || null } })
      setMessage(`${form.full_name} added. Give them their password in person or by phone, never by email.`)
      setForm(blank)
      await people.reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not add them.')
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
      <PageTitle title="People" sub="Managers, door staff and parents. Parents are linked to their children on the Children page." />
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
            <option value="staff">Door staff</option>
            <option value="admin">Manager</option>
          </select>
        </label>
        <label className="sm:col-span-2">
          <span className="label">Starting password (at least 10 characters)</span>
          <input className="input" type="text" autoComplete="new-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required minLength={10} />
        </label>
        <div className="sm:col-span-2">
          <button className="btn btn-primary" disabled={form.password.length < 10}>
            Add person
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
                <td>{ROLE_LABEL[p.role]}</td>
                <td className="text-right">
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
