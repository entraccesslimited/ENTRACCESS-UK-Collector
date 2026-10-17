import { useState, type FormEvent } from 'react'

import { CameraScan, cameraSupported } from '@/components/CameraScan'
import { Alert, PageTitle } from '@/components/ui'
import { api } from '@/lib/api'
import { day } from '@/lib/format'
import { currentPosition } from '@/lib/location'
import { useLoad } from '@/lib/useLoad'
import type { Check, Child, Handover } from '@/lib/types'

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

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    try {
      onChecked(
        await api<Check>('/door/check/code', { method: 'POST', json: { child_id: childId, code, ...(await where(fenced)) } }),
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
        <select className="input" value={childId} onChange={(e) => setChildId(e.target.value)} required size={Math.min(6, Math.max(2, visible.length))}>
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
      <button className="btn btn-primary w-full" disabled={!childId || code.replace(/\D/g, '').length !== 6}>
        Check code
      </button>
    </form>
  )
}

function Result({ check, onDecided, onBack }: { check: Check; onDecided: (h: Handover) => void; onBack: () => void }) {
  const [refusing, setRefusing] = useState(false)
  const [reason, setReason] = useState('')
  const [idChecked, setIdChecked] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const decide = async (release: boolean) => {
    setBusy(true)
    setError(null)
    try {
      onDecided(
        await api<Handover>(`/door/checks/${check.check_id}/decision`, {
          method: 'POST',
          json: { release, reason: release ? null : reason, id_checked: release && idChecked },
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
        <label className="mt-4 flex items-start gap-3 rounded-lg bg-slate-100 p-3 text-sm">
          <input type="checkbox" className="mt-0.5 size-5 shrink-0" checked={idChecked} onChange={(e) => setIdChecked(e.target.checked)} />
          <span>
            <b>Photo ID seen, or I know this collector.</b> Check the name matches before releasing. This is recorded with the handover.
          </span>
        </label>
      )}

      <div className="mt-5 flex flex-wrap gap-2">
        {check.can_release && !refusing && (
          <>
            <button className="btn btn-success" disabled={busy || !idChecked} onClick={() => decide(true)}>
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
