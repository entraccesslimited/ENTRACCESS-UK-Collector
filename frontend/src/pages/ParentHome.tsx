import { useRef, useState, type FormEvent } from 'react'

import { SharePass } from '@/components/SharePass'
import { Alert, Badge, Modal, PageTitle, QR } from '@/components/ui'
import { api } from '@/lib/api'
import { ABSENCE_LABEL, code, day, todayIso, validity } from '@/lib/format'
import { shrink } from '@/lib/photo'
import { useLoad } from '@/lib/useLoad'
import type { Absence, AbsenceReason, Authorisation, Child, Kind, PassInfo } from '@/lib/types'

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
  const [absent, setAbsent] = useState(false)

  const current = list.data?.filter((a) => a.status === 'valid' || a.status === 'not_yet_valid') ?? []
  const past = list.data?.filter((a) => !(a.status === 'valid' || a.status === 'not_yet_valid')) ?? []

  return (
    <section className="card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">{child.full_name}</h2>
          {child.room && <p className="text-sm text-slate-500">{child.room}</p>}
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="btn btn-secondary" onClick={() => setAbsent(!absent)}>
            {absent ? 'Close' : `${child.full_name.split(' ')[0]} is off`}
          </button>
          <button className="btn btn-primary" onClick={() => setAdding(true)}>
            Add a collector
          </button>
        </div>
      </div>
      {absent && <Absences child={child} />}

      {list.error && <div className="mt-3"><Alert>{list.error}</Alert></div>}
      {current.length === 0 && !list.loading && (
        <p className="mt-4 text-sm text-slate-500">Nobody besides you is authorised to collect {child.full_name.split(' ')[0]}.</p>
      )}
      <ul className="mt-4 divide-y divide-slate-100">
        {current.map((auth) => (
          <li key={auth.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
            <div className="flex items-center gap-3">
              <CollectorPhoto auth={auth} onChanged={() => void list.reload()} />
              <div>
              <p className="font-medium">
                {auth.collector_name} <span className="text-sm font-normal text-slate-500">· {auth.collector_relationship}</span>
              </p>
              <p className="text-sm text-slate-600">{validity(auth)}</p>
              {auth.source === 'setting' && <p className="text-xs text-slate-500">Added by the nursery from your registration form</p>}
              </div>
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
  const [photo, setPhoto] = useState<string | null>(null)
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
      if (photo) {
        try {
          await api(`/parent/collectors/${auth.id}/photo`, { method: 'PUT', json: { data_url: photo } })
        } catch {
          // The collector is added either way; the photo can be added from the list.
        }
      }
      setPhoto(null)
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
        <PhotoPicker value={photo} onChange={setPhoto} onError={setError} />
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
            <SharePass auth={auth} pass={pass.data} logPath={`/parent/collectors/${auth.id}/shared`} />
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


function PhotoPicker({
  value,
  onChange,
  onError,
}: {
  value: string | null
  onChange: (dataUrl: string | null) => void
  onError: (message: string) => void
}) {
  const input = useRef<HTMLInputElement>(null)
  return (
    <div className="flex items-center gap-3 rounded-lg bg-slate-50 p-3">
      {value ? (
        <img src={value} alt="The collector" className="size-16 rounded-lg object-cover ring-1 ring-slate-300" />
      ) : (
        <div className="grid size-16 place-items-center rounded-lg bg-slate-200 text-xs text-slate-500">No photo</div>
      )}
      <div className="text-sm">
        <p className="font-medium">A photo helps staff recognise them (optional)</p>
        <p className="text-xs text-slate-600">Only staff see it, at the door. It is deleted when this collector can no longer collect.</p>
        <div className="mt-1 flex gap-3">
          <button type="button" className="text-brand-700 underline" onClick={() => input.current?.click()}>
            {value ? 'Change photo' : 'Add a photo'}
          </button>
          {value && (
            <button type="button" className="text-slate-500 underline" onClick={() => onChange(null)}>
              Remove
            </button>
          )}
        </div>
      </div>
      <input
        ref={input}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={async (event) => {
          const file = event.target.files?.[0]
          event.target.value = ''
          if (!file) return
          try {
            onChange(await shrink(file))
          } catch (err) {
            onError(err instanceof Error ? err.message : 'That photo could not be used.')
          }
        }}
      />
    </div>
  )
}

function CollectorPhoto({ auth, onChanged }: { auth: Authorisation; onChanged: () => void }) {
  const input = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [version, setVersion] = useState(0)
  const url = `/api/parent/collectors/${auth.id}/photo`

  const upload = async (file: File) => {
    setBusy(true)
    setError(null)
    try {
      await api(`/parent/collectors/${auth.id}/photo`, { method: 'PUT', json: { data_url: await shrink(file) } })
      setVersion(version + 1)
      onChanged()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not add the photo.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col items-center gap-1">
      <button
        type="button"
        className="size-12 overflow-hidden rounded-lg bg-slate-200 text-[10px] leading-tight text-slate-600 ring-1 ring-slate-300"
        onClick={() => input.current?.click()}
        title={auth.has_photo ? 'Change photo' : 'Add a photo'}
        disabled={busy}
      >
        {auth.has_photo ? <img src={`${url}?v=${version}`} alt={auth.collector_name} className="size-full object-cover" /> : busy ? '…' : 'Add photo'}
      </button>
      {auth.has_photo && (
        <button
          type="button"
          className="text-[10px] text-slate-500 underline"
          onClick={async () => {
            await api(`/parent/collectors/${auth.id}/photo`, { method: 'DELETE' })
            onChanged()
          }}
        >
          Remove
        </button>
      )}
      {error && <span className="max-w-[8rem] text-[10px] text-red-700">{error}</span>}
      <input
        ref={input}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0]
          event.target.value = ''
          if (file) void upload(file)
        }}
      />
    </div>
  )
}

function Absences({ child }: { child: Child }) {
  const list = useLoad<Absence[]>(`/parent/children/${child.id}/absences`)
  const [form, setForm] = useState<{ day: string; reason: AbsenceReason; note: string }>({ day: todayIso(), reason: 'ill', note: '' })
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState<string | null>(null)
  const first = child.full_name.split(' ')[0]

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    setSaved(null)
    try {
      await api(`/parent/children/${child.id}/absences`, {
        method: 'POST',
        json: { day: form.day, reason: form.reason, note: form.note || null },
      })
      setSaved(`The nursery knows ${first} is off on ${day(form.day)}.`)
      setForm({ ...form, note: '' })
      await list.reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not tell the nursery.')
    }
  }

  return (
    <div className="mt-4 rounded-lg bg-slate-50 p-4">
      <p className="font-semibold">Tell the nursery {first} is off</p>
      <p className="text-sm text-slate-600">So they do not chase you when {first} is not in.</p>
      {error && <div className="mt-2"><Alert>{error}</Alert></div>}
      {saved && <div className="mt-2"><Alert tone="ok">{saved}</Alert></div>}
      <form onSubmit={submit} className="mt-3 grid gap-3 sm:grid-cols-3">
        <label className="block">
          <span className="label">Day</span>
          <input className="input" type="date" min={todayIso()} value={form.day} onChange={(e) => setForm({ ...form, day: e.target.value })} required />
        </label>
        <label className="block">
          <span className="label">Reason</span>
          <select className="input" value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value as AbsenceReason })}>
            {(Object.keys(ABSENCE_LABEL) as AbsenceReason[]).map((r) => (
              <option key={r} value={r}>
                {ABSENCE_LABEL[r]}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="label">Note (optional)</span>
          <input className="input" value={form.note} maxLength={300} onChange={(e) => setForm({ ...form, note: e.target.value })} />
        </label>
        <div className="sm:col-span-3">
          <button className="btn btn-primary">Tell the nursery</button>
        </div>
      </form>
      {(list.data?.length ?? 0) > 0 && (
        <ul className="mt-4 divide-y divide-slate-200 text-sm">
          {list.data?.map((a) => (
            <li key={a.id} className="flex items-center justify-between py-2">
              <span>
                {day(a.day)} · {ABSENCE_LABEL[a.reason]}
                {a.note ? ` · ${a.note}` : ''}
              </span>
              <button
                className="text-slate-500 underline"
                onClick={async () => {
                  await api(`/parent/absences/${a.id}/cancel`, { method: 'POST' })
                  await list.reload()
                }}
              >
                Cancel
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
