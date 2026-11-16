import { useState, type FormEvent } from 'react'

import { CameraScan, cameraSupported } from '@/components/CameraScan'
import { Alert, PageTitle } from '@/components/ui'
import { api } from '@/lib/api'
import { day, RESTRICTION_LABEL } from '@/lib/format'
import { currentPosition } from '@/lib/location'
import { useLoad } from '@/lib/useLoad'
import type { Check, Child, Handover, IdCheckMethod } from '@/lib/types'

type Mode = 'scan' | 'code'

/** Where this phone is, when the nursery has a geofence; nothing otherwise. */
async function where(fenced: boolean) {
  return fenced ? { position: await currentPosition() } : {}
}

export function Door() {
  const [mode, setMode] = useState<Mode>('scan')
  const fence = useLoad<{ enabled: boolean }>('/door/geofence')
  const fenced = Boolean(fence.data?.enabled)
  const [check, setCheck] = useState<Check | null>(null)
  const [done, setDone] = useState<Handover | null>(null)

  const reset = () => {
    setCheck(null)
    setDone(null)
  }

  return (
    <>
      <PageTitle title="Door check" sub="Scan the collector’s pass, or enter their code against the child. Every check is recorded." />
      {done ? (
        <Outcome handover={done} onNext={reset} />
      ) : check ? (
        <Result check={check} onDecided={setDone} onBack={reset} />
      ) : (
        <>
          <div className="mb-4 grid max-w-md grid-cols-2 gap-2">
            {(['scan', 'code'] as Mode[]).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`btn ${mode === m ? 'btn-primary' : 'btn-secondary'}`}
              >
                {m === 'scan' ? 'Scan pass' : 'Enter code'}
              </button>
            ))}
          </div>
          {fenced && (
            <p className="mb-3 max-w-md text-sm text-slate-600">
              This nursery has a geofence: each check sends this phone’s location. Allow location if asked.
            </p>
          )}
          {mode === 'scan' ? <ScanPass fenced={fenced} onChecked={setCheck} /> : <EnterCode fenced={fenced} onChecked={setCheck} />}
        </>
      )}
    </>
  )
}

function ScanPass({ fenced, onChecked }: { fenced: boolean; onChecked: (check: Check) => void }) {
  const [token, setToken] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [camera, setCamera] = useState(false)
  const supported = cameraSupported()

  const submit = async (value: string) => {
    setError(null)
    try {
      onChecked(
        await api<Check>('/door/check/pass', { method: 'POST', json: { token: value.trim(), ...(await where(fenced)) } }),
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not check the pass.')
    }
  }


  return (
    <div className="card max-w-md space-y-4">
      {error && <Alert>{error}</Alert>}
      {supported && (
        <>
          {camera ? (
            <CameraScan
              onFound={(value) => {
                setCamera(false)
                void submit(value)
              }}
              onError={(message) => {
                setError(message)
                setCamera(false)
              }}
              onClose={() => setCamera(false)}
            />
          ) : (
            <button className="btn btn-primary w-full py-3 text-base" onClick={() => setCamera(true)}>
              Scan with the camera
            </button>
          )}
        </>
      )}
      <form
        onSubmit={(event: FormEvent) => {
          event.preventDefault()
          if (token.trim()) void submit(token)
        }}
        className="space-y-2"
      >
        <label className="block">
          <span className="label">{supported ? 'Or paste / use a scanner' : 'Scan with a QR scanner, or paste the pass'}</span>
          <input className="input font-mono" value={token} onChange={(e) => setToken(e.target.value)} placeholder="CP1.…" autoFocus={!supported} />
        </label>
        <button className="btn btn-secondary w-full" disabled={!token.trim()}>
          Check pass
        </button>
      </form>
    </div>
  )
}

function EnterCode({ fenced, onChecked }: { fenced: boolean; onChecked: (check: Check) => void }) {
  const children = useLoad<Child[]>('/door/children')
  const [childId, setChildId] = useState('')
  const [code, setCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState('')

  const visible = (children.data ?? []).filter((c) => c.full_name.toLowerCase().includes(filter.toLowerCase()))
  // React shows the first child as selected whenever the chosen one is not in
  // the list (nothing picked yet, or filtered out), and clicking an option that
  // already looks selected fires no change. So the child staff can see
  // highlighted is the one checked, rather than a disabled button.
  const chosen = visible.some((c) => c.id === childId) ? childId : (visible[0]?.id ?? '')

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    try {
      onChecked(
        await api<Check>('/door/check/code', { method: 'POST', json: { child_id: chosen, code, ...(await where(fenced)) } }),
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not check the code.')
    }
  }

  return (
    <form onSubmit={submit} className="card max-w-md space-y-4">
      {error && <Alert>{error}</Alert>}
      <label className="block">
        <span className="label">Child being collected</span>
        <input className="input mb-2" placeholder="Search by name" value={filter} onChange={(e) => setFilter(e.target.value)} />
        <select className="input" value={chosen} onChange={(e) => setChildId(e.target.value)} required size={Math.min(6, Math.max(2, visible.length))}>
          {visible.map((c) => (
            <option key={c.id} value={c.id}>
              {c.full_name}
              {c.room ? ` · ${c.room}` : ''}
            </option>
          ))}
        </select>
      </label>
      <label className="block">
        <span className="label">The collector’s 6-digit code</span>
        <input
          className="input text-center font-mono text-2xl tracking-widest"
          inputMode="numeric"
          autoComplete="off"
          maxLength={7}
          value={code}
          onChange={(e) => setCode(e.target.value)}
          required
        />
      </label>
      <button className="btn btn-primary w-full" disabled={!chosen || code.replace(/\D/g, '').length !== 6}>
        Check code
      </button>
    </form>
  )
}

function Result({ check, onDecided, onBack }: { check: Check; onDecided: (h: Handover) => void; onBack: () => void }) {
  const [refusing, setRefusing] = useState(false)
  const [reason, setReason] = useState('')
  const [method, setMethod] = useState<IdCheckMethod | null>(null)
  const methods: { value: IdCheckMethod; title: string; help: string }[] = [
    { value: 'photo_id', title: 'Photo ID', help: 'The name on it matches the collector’s.' },
    { value: 'known_to_staff', title: 'I know them', help: 'You have seen them collect before.' },
    ...(check.note_for_staff
      ? [{ value: 'password' as const, title: 'Password', help: 'They gave the password in the parent’s note.' }]
      : []),
  ]
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const decide = async (release: boolean) => {
    setBusy(true)
    setError(null)
    try {
      onDecided(
        await api<Handover>(`/door/checks/${check.check_id}/decision`, {
          method: 'POST',
          json: { release, reason: release ? null : reason, id_check_method: release ? method : null },
        }),
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not record the decision.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={`card max-w-xl border-2 ${check.can_release ? 'border-emerald-500' : 'border-red-500'}`}>
      <p className={`text-xl font-bold ${check.can_release ? 'text-emerald-700' : 'text-red-700'}`}>
        {check.can_release ? '✓ Authorised' : '✕ Do not release'}
      </p>
      <p className="mt-1 text-sm text-slate-700">{check.message}</p>
      {error && <div className="mt-3"><Alert>{error}</Alert></div>}

      {check.restrictions.length > 0 && (
        <div className="mt-4 rounded-lg border-2 border-red-500 bg-red-50 p-3 text-sm" role="alert">
          <p className="font-bold text-red-800">Never release {check.child_name?.split(' ')[0] ?? 'this child'} to:</p>
          <ul className="mt-1 list-disc pl-5">
            {check.restrictions.map((r) => (
              <li key={r.person_name}>
                <b>{r.person_name}</b> <span className="text-red-800">({RESTRICTION_LABEL[r.reason]})</span>
              </li>
            ))}
          </ul>
          <p className="mt-1 text-red-800">If the person at the door is one of them, keep the child inside and tell the manager.</p>
        </div>
      )}

      {(check.child_name || check.collector_name) && (
        <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
          {check.child_name && (
            <div>
              <dt className="text-slate-500">Child</dt>
              <dd className="font-semibold">
                {check.child_name}
                {check.room ? ` · ${check.room}` : ''}
              </dd>
            </div>
          )}
          {check.collector_name && (
            <div>
              <dt className="text-slate-500">Collector</dt>
              <dd className="font-semibold">
                {check.collector_name}
                {check.collector_relationship ? ` · ${check.collector_relationship}` : ''}
              </dd>
            </div>
          )}
          {check.authorised_by_name && (
            <div>
              <dt className="text-slate-500">Authorised by</dt>
              <dd>{check.authorised_by_name}</dd>
            </div>
          )}
          {check.collector_phone && (
            <div>
              <dt className="text-slate-500">Collector’s phone</dt>
              <dd>
                <a className="text-brand-700 underline" href={`tel:${check.collector_phone}`}>
                  {check.collector_phone}
                </a>
              </dd>
            </div>
          )}
          {check.kind && (
            <div>
              <dt className="text-slate-500">Type</dt>
              <dd>{check.kind === 'one_off' ? 'One-off (this pass then stops)' : 'Regular'}{check.valid_until ? `, until ${day(check.valid_until)}` : ''}</dd>
            </div>
          )}
          {check.note_for_staff && (
            <div className="col-span-2 rounded-lg bg-amber-50 p-2">
              <dt className="text-amber-800">Note from the parent</dt>
              <dd>{check.note_for_staff}</dd>
            </div>
          )}
        </dl>
      )}

      {check.can_release && !refusing && (
        <fieldset className="mt-4 rounded-lg bg-slate-100 p-3 text-sm">
          <legend className="sr-only">How did you check who the collector is?</legend>
          <p className="mb-2 font-semibold">How did you check this is {check.collector_name}?</p>
          <div className="grid gap-2 sm:grid-cols-3">
            {methods.map((m) => (
              <label
                key={m.value}
                className={`flex cursor-pointer items-start gap-2 rounded-lg border bg-white p-2 ${method === m.value ? 'border-brand-600 ring-2 ring-brand-100' : 'border-slate-300'}`}
              >
                <input type="radio" name="id-check" className="mt-0.5 size-4 shrink-0" checked={method === m.value} onChange={() => setMethod(m.value)} />
                <span>
                  <b>{m.title}</b>
                  <span className="block text-xs text-slate-600">{m.help}</span>
                </span>
              </label>
            ))}
          </div>
          <p className="mt-2 text-xs text-slate-600">Recorded with the handover. If you cannot confirm who they are, refuse.</p>
        </fieldset>
      )}

      <div className="mt-5 flex flex-wrap gap-2">
        {check.can_release && !refusing && (
          <>
            <button className="btn btn-success" disabled={busy || !method} onClick={() => decide(true)}>
              Release {check.child_name?.split(' ')[0]}
            </button>
            <button className="btn btn-secondary" disabled={busy} onClick={() => setRefusing(true)}>
              Refuse
            </button>
          </>
        )}
        {refusing && (
          <div className="w-full space-y-2">
            <label className="block">
              <span className="label">Why was the child not released?</span>
              <input className="input" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. no photo ID" autoFocus />
            </label>
            <button className="btn btn-danger" disabled={busy || !reason.trim()} onClick={() => decide(false)}>
              Record refusal
            </button>
          </div>
        )}
        <button className="btn btn-secondary" onClick={onBack}>
          {check.can_release ? 'Cancel' : 'Check again'}
        </button>
      </div>
    </div>
  )
}

function Outcome({ handover, onNext }: { handover: Handover; onNext: () => void }) {
  const released = handover.outcome === 'released'
  return (
    <div className="card max-w-xl">
      <p className={`text-xl font-bold ${released ? 'text-emerald-700' : 'text-red-700'}`}>
        {released ? `${handover.child_name} released to ${handover.collector_name}` : `${handover.child_name} not released`}
      </p>
      <p className="mt-1 text-sm text-slate-600">Recorded. The child’s parents have been notified.</p>
      <button className="btn btn-primary mt-4" onClick={onNext}>
        Next collection
      </button>
    </div>
  )
}
