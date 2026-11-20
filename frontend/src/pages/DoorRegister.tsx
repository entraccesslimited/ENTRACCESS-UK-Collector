import { useCallback, useEffect, useMemo, useState } from 'react'

import { Alert, Pill } from '@/components/ui'
import { api, ApiError } from '@/lib/api'
import { ABSENCE_LABEL, clock } from '@/lib/format'
import { addMark, isOffline, load, newId, pendingFor, removeMark, save, settle, type PendingMark } from '@/lib/offlineRegister'
import type { AbsenceReason, Register, RegisterChild, SyncResult } from '@/lib/types'

const CACHE_KEY = 'collector.register.cache.v1'

function cached(): Register | null {
  try {
    const raw = localStorage.getItem(CACHE_KEY)
    return raw ? (JSON.parse(raw) as Register) : null
  } catch {
    return null
  }
}

function remember(register: Register) {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify(register))
  } catch {
    // Without storage the register still works while the page stays open.
  }
}

/** The arrival register: staff mark each child in as they arrive.
 *
 *  It keeps working without signal. A mark made offline waits on the phone
 *  with the time it was made, and is sent as soon as the phone reconnects. */
export function DoorRegister() {
  const [register, setRegister] = useState<Register | null>(cached)
  const [queue, setQueue] = useState<PendingMark[]>(load)
  const [offline, setOffline] = useState(typeof navigator !== 'undefined' && !navigator.onLine)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [filter, setFilter] = useState('')
  const [absentFor, setAbsentFor] = useState<RegisterChild | null>(null)

  const keep = useCallback((next: PendingMark[]) => {
    save(next)
    setQueue(next)
  }, [])

  const refresh = useCallback(async () => {
    try {
      const fresh = await api<Register>('/door/register')
      setRegister(fresh)
      remember(fresh)
      setOffline(false)
    } catch (err) {
      if (isOffline(err)) setOffline(true)
      else setError(err instanceof Error ? err.message : 'Could not load the register.')
    }
  }, [])

  const flush = useCallback(async () => {
    const waiting = load()
    if (waiting.length === 0) return
    try {
      const { results } = await api<{ results: SyncResult[] }>('/door/register/sync', { method: 'POST', json: { marks: waiting } })
      const { queue: left, refused } = settle(load(), results)
      keep(left)
      setOffline(false)
      setNotice(
        refused.length
          ? `Sent the marks made offline. Not recorded: ${refused.join(' ')}`
          : `Sent ${results.length} mark${results.length === 1 ? '' : 's'} made offline, with the times they were made.`,
      )
      await refresh()
    } catch (err) {
      if (isOffline(err)) setOffline(true)
    }
  }, [keep, refresh])

  useEffect(() => {
    void refresh().then(flush)
    const online = () => void flush()
    const gone = () => setOffline(true)
    window.addEventListener('online', online)
    window.addEventListener('offline', gone)
    const timer = window.setInterval(() => void flush(), 30_000)
    return () => {
      window.removeEventListener('online', online)
      window.removeEventListener('offline', gone)
      window.clearInterval(timer)
    }
  }, [refresh, flush])

  const markIn = async (child: RegisterChild) => {
    setError(null)
    setNotice(null)
    const clientId = newId()
    try {
      await api('/door/register/arrivals', { method: 'POST', json: { child_id: child.child_id, client_id: clientId } })
      await refresh()
    } catch (err) {
      if (isOffline(err)) {
        setOffline(true)
        keep(addMark(load(), child.child_id, new Date(), clientId))
      } else {
        setError(err instanceof Error ? err.message : 'Could not mark the child in.')
      }
    }
  }

  const undo = async (child: RegisterChild) => {
    setError(null)
    if (pendingFor(queue, child.child_id)) {
      keep(removeMark(load(), child.child_id))
      return
    }
    try {
      await api(`/door/register/arrivals/${child.child_id}`, { method: 'DELETE' })
      await refresh()
    } catch (err) {
      setError(isOffline(err) ? 'Undoing a mark needs signal. Try again when this phone is back online.' : err instanceof Error ? err.message : 'Could not undo.')
    }
  }

  const rows = useMemo(() => {
    const all = register?.children ?? []
    const wanted = filter.trim().toLowerCase()
    return all
      .filter((c) => !wanted || c.full_name.toLowerCase().includes(wanted) || (c.room ?? '').toLowerCase().includes(wanted))
      .sort((a, b) => Number(b.expected) - Number(a.expected) || a.full_name.localeCompare(b.full_name))
  }, [register, filter])

  const expected = (register?.children ?? []).filter((c) => c.expected && !c.absence_reason)
  const inCount = (register?.children ?? []).filter((c) => c.arrived_at || pendingFor(queue, c.child_id)).length

  return (
    <div className="max-w-2xl space-y-4">
      {offline && (
        <div className="rounded-lg border-2 border-amber-400 bg-amber-50 p-3 text-sm" role="status">
          <b>No signal.</b> You can keep marking children in: {queue.length} mark{queue.length === 1 ? '' : 's'} waiting on this
          phone, sent with the time each was made as soon as it reconnects. Door checks need signal.
        </div>
      )}
      {!offline && queue.length > 0 && (
        <div className="rounded-lg bg-amber-50 p-3 text-sm">
          {queue.length} mark{queue.length === 1 ? '' : 's'} waiting to send.{' '}
          <button className="font-semibold text-brand-700 underline" onClick={() => void flush()}>
            Send now
          </button>
        </div>
      )}
      {notice && <div className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</div>}
      {error && <Alert>{error}</Alert>}

      <div className="card flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-slate-600">
          <b className="text-lg text-ink">{inCount}</b> in of <b>{expected.length}</b> expected today
          {register?.arrival_alert_at ? ` · parents are told at ${register.arrival_alert_at.slice(0, 5)} if a child is not in` : ''}
        </p>
        <input className="input max-w-[14rem]" placeholder="Search by name or room" value={filter} onChange={(e) => setFilter(e.target.value)} />
      </div>

      {!register && <p className="text-sm text-slate-600">Loading the register…</p>}

      <ul className="card divide-y divide-slate-100 p-0">
        {rows.map((c) => {
          const pending = pendingFor(queue, c.child_id)
          const isIn = Boolean(c.arrived_at || pending)
          return (
            <li key={c.child_id} className={`flex flex-wrap items-center justify-between gap-2 px-4 py-3 ${c.expected ? '' : 'opacity-60'}`}>
              <div>
                <p className="font-medium">{c.full_name}</p>
                <p className="text-xs text-slate-500">
                  {c.room ?? 'No room'}
                  {!c.expected && ' · not booked in today'}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {c.collected_at ? (
                  <Pill tone="slate">Gone home {clock(c.collected_at)} with {c.collected_by}</Pill>
                ) : c.absence_reason ? (
                  <Pill tone="slate">Off today · {ABSENCE_LABEL[c.absence_reason]}</Pill>
                ) : isIn ? (
                  <>
                    <Pill tone="green">
                      In {clock(c.arrived_at ?? pending?.occurred_at ?? '')}
                      {pending ? ' · waiting to send' : c.arrived_offline ? ' · marked offline' : ''}
                    </Pill>
                    <button className="text-xs text-slate-500 underline" onClick={() => void undo(c)}>
                      Undo
                    </button>
                  </>
                ) : (
                  <>
                    <button className="btn btn-primary" onClick={() => void markIn(c)}>
                      Mark in
                    </button>
                    {!offline && (
                      <button className="btn btn-secondary" onClick={() => setAbsentFor(c)}>
                        Off today
                      </button>
                    )}
                  </>
                )}
              </div>
            </li>
          )
        })}
      </ul>

      {absentFor && register && (
        <PhonedInAbsence
          child={absentFor}
          day={register.day}
          onDone={async () => {
            setAbsentFor(null)
            await refresh()
          }}
        />
      )}
    </div>
  )
}

function PhonedInAbsence({ child, day, onDone }: { child: RegisterChild; day: string; onDone: () => void }) {
  const [reason, setReason] = useState<AbsenceReason>('ill')
  const [note, setNote] = useState('')
  const [error, setError] = useState<string | null>(null)
  const save = async () => {
    try {
      await api('/door/register/absences', { method: 'POST', json: { child_id: child.child_id, day, reason, note: note || null } })
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not record the absence.')
    }
  }
  return (
    <div className="card space-y-3 border-2 border-brand-200">
      <p className="font-semibold">{child.full_name} is off today</p>
      {error && <Alert>{error}</Alert>}
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block">
          <span className="label">Reason</span>
          <select className="input" value={reason} onChange={(e) => setReason(e.target.value as AbsenceReason)}>
            {(Object.keys(ABSENCE_LABEL) as AbsenceReason[]).map((r) => (
              <option key={r} value={r}>
                {ABSENCE_LABEL[r]}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="label">Note (optional)</span>
          <input className="input" value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. mum rang at 8:10" />
        </label>
      </div>
      <div className="flex gap-2">
        <button className="btn btn-primary" onClick={() => void save()}>
          Record absence
        </button>
        <button className="btn btn-secondary" onClick={onDone}>
          Cancel
        </button>
      </div>
    </div>
  )
}
