import { useState, type FormEvent } from 'react'

import { Alert, Badge, Modal, PageTitle, QR } from '@/components/ui'
import { api } from '@/lib/api'
import { code, todayIso, validity } from '@/lib/format'
import { useLoad } from '@/lib/useLoad'
import type { Authorisation, Child, Kind, PassInfo } from '@/lib/types'

export function ParentHome() {
  const children = useLoad<Child[]>('/parent/children')
  return (
    <>
      <PageTitle
        title="Who can collect"
        sub="Add the people who may collect your child. Each gets a pass and a daily code; staff check it at the door, and you can remove anyone instantly."
      />
      {children.error && <Alert>{children.error}</Alert>}
      {children.data?.length === 0 && (
        <Alert tone="info">No children are linked to your account yet. Ask the nursery to link you.</Alert>
      )}
      <div className="space-y-6">
        {children.data?.map((child) => <ChildCollectors key={child.id} child={child} />)}
      </div>
    </>
  )
}

function ChildCollectors({ child }: { child: Child }) {
  const list = useLoad<Authorisation[]>(`/parent/children/${child.id}/collectors`)
  const [adding, setAdding] = useState(false)
  const [showing, setShowing] = useState<Authorisation | null>(null)
  const [showOld, setShowOld] = useState(false)

  const current = list.data?.filter((a) => a.status === 'valid' || a.status === 'not_yet_valid') ?? []
  const past = list.data?.filter((a) => !(a.status === 'valid' || a.status === 'not_yet_valid')) ?? []

  return (
    <section className="card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">{child.full_name}</h2>
          {child.room && <p className="text-sm text-slate-500">{child.room}</p>}
        </div>
        <button className="btn btn-primary" onClick={() => setAdding(true)}>
          Add a collector
        </button>
      </div>

      {list.error && <div className="mt-3"><Alert>{list.error}</Alert></div>}
      {current.length === 0 && !list.loading && (
        <p className="mt-4 text-sm text-slate-500">Nobody besides you is authorised to collect {child.full_name.split(' ')[0]}.</p>
      )}
      <ul className="mt-4 divide-y divide-slate-100">
        {current.map((auth) => (
          <li key={auth.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
            <div>
              <p className="font-medium">
                {auth.collector_name} <span className="text-sm font-normal text-slate-500">· {auth.collector_relationship}</span>
              </p>
              <p className="text-sm text-slate-600">{validity(auth)}</p>
            </div>
            <div className="flex items-center gap-2">
              <Badge status={auth.status} />
              <button className="btn btn-secondary" onClick={() => setShowing(auth)}>
                Pass &amp; code
              </button>
            </div>
          </li>
        ))}
      </ul>

      {past.length > 0 && (
        <div className="mt-2">
          <button className="text-sm text-brand-700 underline-offset-2 hover:underline" onClick={() => setShowOld(!showOld)}>
            {showOld ? 'Hide' : 'Show'} {past.length} past or removed
          </button>
          {showOld && (
            <ul className="mt-2 divide-y divide-slate-100 text-sm text-slate-600">
              {past.map((auth) => (
                <li key={auth.id} className="flex items-center justify-between py-2">
                  <span>
                    {auth.collector_name} · {validity(auth)}
                  </span>
                  <Badge status={auth.status} />
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <AddCollector
        child={child}
        open={adding}
        onClose={() => setAdding(false)}
        onAdded={async (auth) => {
          setAdding(false)
          await list.reload()
          setShowing(auth)
        }}
      />
      {showing && (
        <PassDialog
          auth={showing}
          onClose={() => setShowing(null)}
          onChanged={async () => {
            await list.reload()
          }}
        />
      )}
    </section>
  )
}

function AddCollector({
  child,
  open,
  onClose,
  onAdded,
}: {
  child: Child
  open: boolean
  onClose: () => void
  onAdded: (auth: Authorisation) => void
}) {
  const [kind, setKind] = useState<Kind>('one_off')
  const [form, setForm] = useState({
    collector_name: '',
    collector_relationship: '',
    collector_phone: '',
    note_for_staff: '',
    on_date: todayIso(),
    from_time: '',
    until_time: '',
    start_date: todayIso(),
    end_date: '',
  })
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const set = (key: keyof typeof form) => (event: { target: { value: string } }) =>
    setForm({ ...form, [key]: event.target.value })

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    const body =
      kind === 'one_off'
        ? {
            kind,
            on_date: form.on_date,
            from_time: form.from_time || null,
            until_time: form.until_time || null,
          }
        : { kind, start_date: form.start_date || null, end_date: form.end_date || null }
    try {
      const auth = await api<Authorisation>(`/parent/children/${child.id}/collectors`, {
        method: 'POST',
        json: {
          collector_name: form.collector_name,
          collector_relationship: form.collector_relationship,
          collector_phone: form.collector_phone,
          note_for_staff: form.note_for_staff || null,
          ...body,
        },
      })
      onAdded(auth)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not add the collector.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal open={open} title={`Who is collecting ${child.full_name.split(' ')[0]}?`} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        {error && <Alert>{error}</Alert>}
        <div className="grid grid-cols-2 gap-2">
          {(['one_off', 'regular'] as Kind[]).map((k) => (
            <button
              type="button"
              key={k}
              onClick={() => setKind(k)}
              className={`rounded-lg border p-3 text-left text-sm ${kind === k ? 'border-brand-500 bg-brand-50' : 'border-slate-300'}`}
            >
              <span className="block font-semibold">{k === 'one_off' ? 'Just once' : 'Regularly'}</span>
              <span className="text-slate-600">{k === 'one_off' ? 'One collection, then the pass stops.' : 'Any day, with a new code each day.'}</span>
            </button>
          ))}
        </div>
        <label className="block">
          <span className="label">Their full name</span>
          <input className="input" value={form.collector_name} onChange={set('collector_name')} required />
        </label>
        <div className="grid grid-cols-2 gap-3">
          <label className="block">
            <span className="label">Relationship</span>
            <input className="input" placeholder="Grandparent" value={form.collector_relationship} onChange={set('collector_relationship')} required />
          </label>
          <label className="block">
            <span className="label">Their phone</span>
            <input className="input" type="tel" placeholder="07700 900123" value={form.collector_phone} onChange={set('collector_phone')} required />
          </label>
        </div>
        {kind === 'one_off' ? (
          <div className="grid grid-cols-3 gap-3">
            <label className="col-span-3 block sm:col-span-1">
              <span className="label">Day</span>
              <input className="input" type="date" value={form.on_date} min={todayIso()} onChange={set('on_date')} required />
            </label>
            <label className="block">
              <span className="label">From (optional)</span>
              <input className="input" type="time" value={form.from_time} onChange={set('from_time')} />
            </label>
            <label className="block">
              <span className="label">Until (optional)</span>
              <input className="input" type="time" value={form.until_time} onChange={set('until_time')} />
            </label>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="label">First day</span>
              <input className="input" type="date" value={form.start_date} min={todayIso()} onChange={set('start_date')} />
            </label>
            <label className="block">
              <span className="label">Last day (optional)</span>
              <input className="input" type="date" value={form.end_date} onChange={set('end_date')} />
            </label>
          </div>
        )}
        <label className="block">
          <span className="label">Anything staff should know (optional)</span>
          <input className="input" placeholder="e.g. will ask for our family password" value={form.note_for_staff} onChange={set('note_for_staff')} maxLength={300} />
        </label>
        <div className="flex justify-end gap-2">
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary" disabled={busy}>
            {busy ? 'Adding…' : 'Authorise'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

function PassDialog({ auth, onClose, onChanged }: { auth: Authorisation; onClose: () => void; onChanged: () => Promise<void> }) {
  const pass = useLoad<PassInfo>(`/parent/collectors/${auth.id}/pass`)
  const [confirming, setConfirming] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const share = async () => {
    if (!pass.data) return
    const text = `Your pass to collect from the nursery: ${pass.data.share_url}`
    try {
      if (navigator.share) await navigator.share({ title: 'Collection pass', text, url: pass.data.share_url })
      else {
        await navigator.clipboard.writeText(pass.data.share_url)
        setMessage('Link copied. Send it to the collector by text or WhatsApp.')
      }
    } catch {
      /* the share sheet was closed */
    }
  }

  const act = async (path: 'revoke' | 'reissue') => {
    setError(null)
    try {
      await api(`/parent/collectors/${auth.id}/${path}`, { method: 'POST' })
      await onChanged()
      if (path === 'revoke') onClose()
      else {
        await pass.reload()
        setMessage('New pass and code issued. The old ones no longer work.')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'That did not work.')
    }
  }

  return (
    <Modal open title={auth.collector_name} onClose={onClose}>
      <div className="space-y-4">
        <p className="text-sm text-slate-600">
          {auth.collector_relationship} · {validity(auth)}
        </p>
        {error && <Alert>{error}</Alert>}
        {message && <Alert tone="ok">{message}</Alert>}
        {pass.data && (
          <>
            <QR text={pass.data.token} />
            <div className="rounded-lg bg-slate-100 p-3 text-center">
              <p className="text-xs uppercase tracking-wide text-slate-500">Today’s code</p>
              <p className="font-mono text-3xl font-bold tracking-widest">{code(pass.data.code_today)}</p>
              <p className="mt-1 text-xs text-slate-500">
                {auth.kind === 'regular' ? 'A new code each day. ' : ''}For a collector without a phone: read it to them, and they give it at the door.
              </p>
            </div>
            <button className="btn btn-primary w-full" onClick={share}>
              Send the pass to {auth.collector_name.split(' ')[0]}
            </button>
          </>
        )}
        <div className="flex flex-wrap justify-between gap-2 border-t border-slate-100 pt-4">
          <button className="btn btn-secondary" onClick={() => act('reissue')}>
            New pass &amp; code
          </button>
          {confirming ? (
            <button className="btn btn-danger" onClick={() => act('revoke')}>
              Yes, remove now
            </button>
          ) : (
            <button className="btn btn-secondary text-red-700" onClick={() => setConfirming(true)}>
              Remove this collector
            </button>
          )}
        </div>
      </div>
    </Modal>
  )
}
