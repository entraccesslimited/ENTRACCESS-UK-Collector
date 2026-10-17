import { useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from 'react'

import { CameraScan, cameraSupported } from '@/components/CameraScan'
import { SiteLayout } from '@/components/SiteLayout'
import { QR } from '@/components/ui'
import {
  CODE_LIMIT,
  LABEL,
  MESSAGES,
  Refused,
  checkCode,
  checkPass,
  codeFor,
  csv,
  decide,
  hhmm,
  passFor,
  releasedToday,
  startingWorld,
  status,
  tamper,
  uid,
  type Collector,
  type DoorCheck,
  type Kind,
  type Result,
  type World,
} from '@/lib/prototype'

/** What a visitor proves by their own actions, one tick each. */
const EVIDENCE = [
  ['authorised', 'A collector authorised', 'A parent adds someone and they can collect.'],
  ['released', 'A handover recorded', 'Released after an ID check, and both parents told.'],
  ['removed', 'Removal enforced', 'A collector the parent removed is refused at the door.'],
  ['time', 'Wrong time refused', 'A one-off collector too early or too late is refused.'],
  ['forged', 'Altered or old pass refused', 'A tampered pass, or one since replaced, is refused.'],
  ['twice', 'A child goes home once', 'A second collector for a child already collected is refused.'],
  ['locked', 'Code guessing stopped', `${CODE_LIMIT} wrong codes for one child pause code entry.`],
] as const
type EvidenceKey = (typeof EVIDENCE)[number][0]

const SCENARIOS: { title: string; steps: string[] }[] = [
  {
    title: 'Normal collection',
    steps: [
      'In “What the collector has”, pick Lucy Shah (Leo’s grandmother) and press “Show at the door”.',
      'At the door, read the result and the note Priya left for staff. Tick the ID check.',
      'Release Leo. Both parents are told, and the manager’s record updates.',
    ],
  },
  {
    title: 'A one-off collector',
    steps: [
      'As Priya, add a one-off collector for Maya: a neighbour, today 15:00 to 18:00.',
      'Show their pass at the door now (14:30): refused, starts later. Move the clock on 30 minutes and try again.',
      'Release Maya, then show the same pass again: a one-off pass works once.',
    ],
  },
  {
    title: 'Last-minute removal',
    steps: [
      'As Priya, add a one-off collector for Leo. Plans change: press “Remove”.',
      'Show their pass at the door: refused, removed by the parent, and the attempt is recorded.',
    ],
  },
  {
    title: 'Altered or replaced pass',
    steps: [
      'Show any pass at the door, then press “Alter one character” and check again: refused as not genuine.',
      'As a parent, press “Send a new pass” on a collector, then show the old one: refused as replaced.',
    ],
  },
  {
    title: 'Two collectors, one child',
    steps: [
      'Release Leo to his mum, Priya.',
      'Now show Dev’s (his dad’s) pass for Leo: refused, already collected, with when and by whom.',
    ],
  },
  {
    title: 'No smartphone',
    steps: [
      'Raj Patel, Ruby’s grandfather, has no smartphone. As Sarah, press “Pass & code” on Raj to see the six-digit code she reads him.',
      'At the door, choose “Enter code”, pick Ruby and type that code.',
      `Try a wrong code ${CODE_LIMIT} times for one child: code entry pauses and staff are told to call the parent.`,
    ],
  },
]

export function Prototype() {
  const world = useRef<World>(startingWorld())
  const [, setVersion] = useState(0)
  const refresh = () => setVersion((v) => v + 1)
  const [scenario, setScenario] = useState(0)
  const [proved, setProved] = useState<Set<EvidenceKey>>(new Set())
  const [presented, setPresented] = useState<{ token: string; at: number } | null>(null)
  const prove = (key: EvidenceKey) => setProved((s) => (s.has(key) ? s : new Set(s).add(key)))
  const w = world.current

  const reset = () => {
    world.current = startingWorld()
    setProved(new Set())
    setPresented(null)
    refresh()
  }

  return (
    <SiteLayout>
      <section className="hero-grid border-b border-slate-200">
        <div className="mx-auto max-w-7xl px-4 py-12">
          <p className="inline-block rounded-full bg-brand-50 px-3 py-1 text-xs font-bold tracking-widest text-brand-700">
            INTERACTIVE PROTOTYPE
          </p>
          <h1 className="mt-4 max-w-3xl text-4xl leading-tight text-ink md:text-5xl">One child, four people, one record.</h1>
          <p className="mt-4 max-w-3xl text-lg text-slate-600">
            Try ENTRACCESS UK Collector from every side at once: the parent who authorises, the collector who arrives, the room
            leader at the door and the manager who keeps the record. Break it on purpose. Everything you do is checked by the
            same rules as the live app.
          </p>
          <div className="mt-6 rounded-2xl border border-slate-200 bg-surface p-4 text-sm text-slate-600">
            <b className="text-ink">Sample families only.</b> This runs entirely in your browser: passes are really signed and
            checked here, nothing is sent anywhere, and it all resets when you leave or press Reset. Please don’t type in real
            names. The emails parents would receive are shown on screen instead of being sent.
          </div>
        </div>
      </section>

      <div className="mx-auto max-w-7xl space-y-6 px-4 py-8">
        <Evidence proved={proved} />

        <section className="card">
          <div className="flex flex-wrap items-center gap-2">
            {SCENARIOS.map((s, i) => (
              <button
                key={s.title}
                onClick={() => setScenario(i)}
                className={`btn ${scenario === i ? 'btn-primary' : 'btn-secondary'} text-xs sm:text-sm`}
              >
                <span className="font-mono opacity-70">{String(i + 1).padStart(2, '0')}</span> {s.title}
              </button>
            ))}
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-midnight px-4 py-2 font-mono text-sm text-white">🕑 {hhmm(w.clock)}</span>
            <button className="btn btn-secondary" onClick={() => { w.clock += 30; refresh() }}>+30 min</button>
            <button className="btn btn-secondary" onClick={() => { w.clock += 120; refresh() }}>+2 h</button>
            <button className="btn btn-secondary" onClick={reset}>Reset</button>
          </div>
          <div className="mt-4 rounded-2xl border-l-4 border-brand-600 bg-mist p-4">
            <p className="text-xs font-bold tracking-widest text-brand-600">SCENARIO {String(scenario + 1).padStart(2, '0')}</p>
            <h2 className="mt-1 text-xl text-ink">{SCENARIOS[scenario].title}</h2>
            <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-slate-700">
              {SCENARIOS[scenario].steps.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
          </div>
        </section>

        <div className="grid gap-6 lg:grid-cols-3">
          <ParentPanel world={w} refresh={refresh} prove={prove} />
          <CollectorPanel world={w} onShow={(token) => setPresented({ token, at: Date.now() })} />
          <DoorPanel world={w} refresh={refresh} prove={prove} presented={presented} />
        </div>
        <ManagerPanel world={w} />
      </div>
    </SiteLayout>
  )
}

function Panel({ who, title, children, id }: { who: string; title: string; children: ReactNode; id?: string }) {
  return (
    <section id={id} className="card flex flex-col scroll-mt-20">
      <p className="text-xs font-bold tracking-widest text-brand-600">{who}</p>
      <h2 className="mb-4 text-xl text-ink">{title}</h2>
      {children}
    </section>
  )
}

function Evidence({ proved }: { proved: Set<EvidenceKey> }) {
  return (
    <section className="card">
      <p className="text-xs font-bold tracking-widest text-brand-600">EVIDENCE FROM YOUR ACTIONS</p>
      <h2 className="text-xl text-ink">
        {proved.size} of {EVIDENCE.length} safeguards seen working
      </h2>
      <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4 xl:grid-cols-7">
        {EVIDENCE.map(([key, title, text]) => (
          <div key={key} className={`rounded-xl border p-3 ${proved.has(key) ? 'border-emerald-300 bg-emerald-50' : 'border-slate-200'}`}>
            <span
              className={`grid size-7 place-items-center rounded-full text-sm font-bold ${proved.has(key) ? 'bg-emerald-600 text-white' : 'border border-slate-300 text-slate-400'}`}
            >
              {proved.has(key) ? '✓' : '–'}
            </span>
            <p className={`mt-2 text-sm font-semibold ${proved.has(key) ? 'text-emerald-900' : 'text-ink'}`}>{title}</p>
            <p className={`mt-1 text-xs ${proved.has(key) ? 'text-emerald-800' : 'text-slate-500'}`}>{text}</p>
          </div>
        ))}
      </div>
    </section>
  )
}

function Tag({ result }: { result: Result }) {
  const tone =
    result === 'valid'
      ? 'bg-emerald-100 text-emerald-800'
      : result === 'not_yet_valid'
        ? 'bg-amber-100 text-amber-800'
        : 'bg-slate-200 text-slate-700'
  return <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold ${tone}`}>{LABEL[result]}</span>
}

// ---------------------------------------------------------------- parent

function ParentPanel({ world, refresh, prove }: { world: World; refresh: () => void; prove: (k: EvidenceKey) => void }) {
  const [parentId, setParentId] = useState('priya')
  const parent = world.parents.find((p) => p.id === parentId)!
  const blank = { childId: parent.childIds[0], name: '', relationship: '', kind: 'one_off' as Kind, from: '15:00', until: '18:00', note: '' }
  const [form, setForm] = useState(blank)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => setForm((f) => ({ ...f, childId: parent.childIds[0] })), [parent])

  const minutes = (t: string) => Number(t.slice(0, 2)) * 60 + Number(t.slice(3, 5))
  const add = (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    if (form.name.trim().length < 2 || !form.relationship.trim()) return setError('Give their name and how they know the child.')
    if (form.kind === 'one_off' && minutes(form.until) <= minutes(form.from)) return setError('The window has to end after it starts.')
    world.collectors.push({
      id: uid('c'),
      childId: form.childId,
      name: form.name.trim(),
      relationship: form.relationship.trim(),
      phone: '07700 900199',
      note: form.note.trim(),
      kind: form.kind,
      from: form.kind === 'one_off' ? minutes(form.from) : 0,
      until: form.kind === 'one_off' ? minutes(form.until) : null,
      authorisedBy: parent.name,
      version: 1,
      revokedAt: null,
      usedAt: null,
    })
    const child = world.children.find((c) => c.id === form.childId)!
    world.audit.push({ at: world.clock, who: parent.name, what: `Authorised ${form.name.trim()} (${form.relationship.trim()}) for ${child.name}` })
    prove('authorised')
    setForm({ ...blank, childId: form.childId })
    refresh()
  }

  const remove = (c: Collector) => {
    c.revokedAt = world.clock
    world.audit.push({ at: world.clock, who: parent.name, what: `Removed ${c.name} as a collector` })
    refresh()
  }
  const reissue = (c: Collector) => {
    c.version += 1
    world.audit.push({ at: world.clock, who: parent.name, what: `Sent ${c.name} a new pass; the old one stops working` })
    refresh()
  }
  const notices = world.notices.filter((n) => n.to === parent.name)

  return (
    <Panel who="PARENT" title="Who may collect">
      <label className="mb-3 block">
        <span className="label">Signed in as</span>
        <select className="input" value={parentId} onChange={(e) => setParentId(e.target.value)}>
          {world.parents.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name} — {p.childIds.map((id) => world.children.find((c) => c.id === id)!.name.split(' ')[0]).join(' & ')}
            </option>
          ))}
        </select>
      </label>

      {parent.childIds.map((childId) => {
        const child = world.children.find((c) => c.id === childId)!
        return (
          <div key={childId} className="mb-3">
            <p className="text-sm font-semibold text-ink">
              {child.name} <span className="font-normal text-slate-500">· {child.room}</span>
            </p>
            <ul className="mt-1 divide-y divide-slate-100 rounded-xl border border-slate-200">
              {world.collectors
                .filter((c) => c.childId === childId)
                .map((c) => {
                  const s = status(c, world.clock)
                  return (
                    <li key={c.id} className="px-3 py-2 text-sm">
                      <p>
                        <span className="font-medium text-ink">{c.name}</span>{' '}
                        <span className="text-slate-500">
                          {c.relationship} · {c.kind === 'one_off' ? `once, ${hhmm(c.from)}–${hhmm(c.until!)}` : 'regular'}
                        </span>
                      </p>
                      <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
                      <Tag result={s} />
                      {c.revokedAt === null && (
                        <>
                          <CodeReveal collector={c} />
                          <button className="text-xs text-brand-700 underline" onClick={() => reissue(c)}>
                            Send a new pass
                          </button>
                          <button className="text-xs text-red-700 underline" onClick={() => remove(c)}>
                            Remove
                          </button>
                        </>
                      )}
                      </div>
                    </li>
                  )
                })}
            </ul>
          </div>
        )
      })}

      <form onSubmit={add} className="mt-2 space-y-2 rounded-xl border border-dashed border-slate-300 p-3">
        <p className="text-sm font-semibold text-ink">Add a collector</p>
        {error && <p className="text-sm text-red-700">{error}</p>}
        <div className="grid grid-cols-2 gap-2">
          <select className="input" value={form.childId} onChange={(e) => setForm({ ...form, childId: e.target.value })}>
            {parent.childIds.map((id) => (
              <option key={id} value={id}>
                For {world.children.find((c) => c.id === id)!.name.split(' ')[0]}
              </option>
            ))}
          </select>
          <select className="input" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value as Kind })}>
            <option value="one_off">Once, today</option>
            <option value="regular">Regularly</option>
          </select>
        </div>
        <input className="input" placeholder="Their name, e.g. Ben Carter" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <input className="input" placeholder="Relationship, e.g. Neighbour" value={form.relationship} onChange={(e) => setForm({ ...form, relationship: e.target.value })} />
        {form.kind === 'one_off' && (
          <div className="grid grid-cols-2 gap-2">
            <label className="text-xs text-slate-500">
              From
              <input className="input" type="time" value={form.from} onChange={(e) => setForm({ ...form, from: e.target.value })} />
            </label>
            <label className="text-xs text-slate-500">
              Until
              <input className="input" type="time" value={form.until} onChange={(e) => setForm({ ...form, until: e.target.value })} />
            </label>
          </div>
        )}
        <input className="input" placeholder="Note for staff (optional)" value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />
        <button className="btn btn-primary w-full">Authorise</button>
      </form>

      <p className="mt-4 text-sm font-semibold text-ink">Messages to {parent.name.split(' ')[0]}</p>
      {notices.length === 0 ? (
        <p className="mt-1 text-xs text-slate-500">Nothing yet. Every parent of the child hears about every collection.</p>
      ) : (
        <ul className="mt-1 space-y-1">
          {[...notices].reverse().map((n, i) => (
            <li key={i} className="rounded-lg bg-mist px-3 py-2 text-xs text-slate-700">
              <span className="font-mono text-slate-500">{hhmm(n.at)}</span> {n.text}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}

/** The parent's “Pass & code”: today's six-digit code, to read to someone without a smartphone. */
function CodeReveal({ collector }: { collector: Collector }) {
  const [code, setCode] = useState<string | null>(null)
  const [open, setOpen] = useState(false)
  useEffect(() => {
    if (!open) return
    let live = true
    void codeFor(collector).then((c) => live && setCode(c))
    return () => {
      live = false
    }
  }, [open, collector, collector.version])
  return open ? (
    <span className="rounded-md bg-mist px-2 py-0.5 font-mono text-sm tracking-widest text-ink" title="Today’s code">
      {code ?? '······'}
    </span>
  ) : (
    <button className="text-xs text-brand-700 underline" onClick={() => setOpen(true)}>
      Pass &amp; code
    </button>
  )
}

// ---------------------------------------------------------------- collector

function CollectorPanel({ world, onShow }: { world: World; onShow: (token: string) => void }) {
  // Lucy's pass is open from the start, so there is always a QR code to scan.
  const [selected, setSelected] = useState<string | null>('leo-lucy')
  const [latest, setLatest] = useState<{ id: string; version: number; token: string; code: string } | null>(null)
  const current = world.collectors.find((c) => c.id === selected) ?? null
  // Only ever this collector's current pass: while a new one is being signed,
  // there is none, rather than the previous collector's.
  const pass = current && latest && latest.id === current.id && latest.version === current.version ? latest : null

  useEffect(() => {
    if (!current) return
    let live = true
    const { id, version } = current
    void Promise.all([passFor(current), codeFor(current)]).then(
      ([token, code]) => live && setLatest({ id, version, token, code }),
    )
    return () => {
      live = false
    }
    // A new pass after "Send a new pass" is a new version.
  }, [current, current?.version])

  // What the collector holds stays what they were sent, even after a reissue:
  // that is how an old pass reaches the door.
  const [held, setHeld] = useState<Record<string, string>>({})
  useEffect(() => {
    if (current && pass && !held[current.id]) setHeld((h) => ({ ...h, [current.id]: pass.token }))
  }, [current, pass, held])
  const token = current ? held[current.id] ?? pass?.token : undefined
  const stale = Boolean(current && pass && token && token !== pass.token)

  return (
    <Panel who="COLLECTOR" title="What the collector has">
      <p className="mb-3 text-sm text-slate-600">
        The parent sends each collector a link to their pass, by text or WhatsApp. Someone without a smartphone gets a six-digit code from the parent instead.
      </p>
      {current && pass && token && (
        <div className="mb-4 rounded-2xl bg-[#111a2e] p-4 text-center text-white">
          <p className="text-xs tracking-widest text-[#93c5fd]">COLLECTOR PASS · LITTLE ACORNS (DEMO)</p>
          <p className="mt-1 font-semibold">{current.name}</p>
          <div className="mt-3">
            <QR text={token} size={170} />
          </div>
          {stale && <p className="mt-2 text-xs text-amber-300">This is the pass they were first sent. The parent has since sent a new one.</p>}
          <button className="btn btn-primary mt-3 w-full" onClick={() => onShow(token)}>
            Show at the door
          </button>
          {stale && (
            <button className="btn mt-2 w-full border border-white/30 text-white" onClick={() => setHeld((h) => ({ ...h, [current.id]: pass.token }))}>
              Open the new pass instead
            </button>
          )}
          <p className="mt-2 text-[11px] text-[#94a3b8]">The pass names no child and no date: only a signed reference this nursery can check.</p>
        </div>
      )}
      <p className="mb-2 text-xs font-semibold text-brand-700">Tap a collector to open the pass they were sent.</p>
      <ul className="space-y-1">
        {world.collectors.map((c) => {
          const child = world.children.find((x) => x.id === c.childId)!
          return (
            <li key={c.id}>
              <button
                onClick={() => setSelected(c.id)}
                className={`flex w-full items-center gap-2 rounded-xl border px-3 py-2 text-left text-sm ${selected === c.id ? 'border-brand-500 bg-brand-50' : 'border-slate-200'}`}
              >
                <span className="min-w-0 flex-1">
                  <span className="font-medium text-ink">{c.name}</span>{' '}
                  <span className="text-slate-500">for {child.name.split(' ')[0]}</span>
                </span>
                <Tag result={status(c, world.clock)} />
              </button>
            </li>
          )
        })}
      </ul>
    </Panel>
  )
}

// ---------------------------------------------------------------- door

function DoorPanel({
  world,
  refresh,
  prove,
  presented,
}: {
  world: World
  refresh: () => void
  prove: (k: EvidenceKey) => void
  presented: { token: string; at: number } | null
}) {
  const [mode, setMode] = useState<'pass' | 'code'>('pass')
  const [token, setToken] = useState('')
  const [childId, setChildId] = useState(world.children[0].id)
  const [code, setCode] = useState('')
  const [check, setCheck] = useState<DoorCheck | null>(null)
  const [idChecked, setIdChecked] = useState(false)
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState<string | null>(null)
  const [camera, setCamera] = useState(false)
  const [cameraError, setCameraError] = useState<string | null>(null)

  const noteResult = (k: DoorCheck) => {
    if (k.result === 'revoked') prove('removed')
    if (k.result === 'not_yet_valid' || k.result === 'expired' || k.result === 'already_used') prove('time')
    if (k.result === 'wrong_nursery' || k.result === 'reissued') prove('forged')
    if (k.result === 'already_collected') prove('twice')
    if (k.result === 'locked') prove('locked')
  }
  const begin = (k: DoorCheck) => {
    setCheck(k)
    setIdChecked(false)
    setReason('')
    setError(null)
    setDone(null)
    noteResult(k)
    refresh()
  }

  useEffect(() => {
    if (!presented) return
    setMode('pass')
    setToken(presented.token)
    void checkPass(world, presented.token).then((k) => {
      begin(k)
      // On a phone the panels are stacked; take the visitor to the door.
      if (window.matchMedia('(max-width: 1023px)').matches) {
        requestAnimationFrame(() => document.getElementById('door')?.scrollIntoView({ block: 'start' }))
      }
    })
    // Each press of "Show at the door" is a new check.
  }, [presented])

  const runPass = async (event?: FormEvent) => {
    event?.preventDefault()
    if (token.trim()) begin(await checkPass(world, token))
  }
  const runCode = async (event: FormEvent) => {
    event.preventDefault()
    if (code.trim()) begin(await checkCode(world, childId, code))
    setCode('')
  }
  const choose = (release: boolean) => {
    if (!check) return
    try {
      const h = decide(world, check, release, idChecked, reason)
      const child = world.children.find((c) => c.id === h.childId)!
      if (release) prove('released')
      setDone(release ? `${child.name} released to ${h.collector}. Both parents have been told.` : `Not released. ${child.name} stays; the parents have been told why.`)
      setCheck(null)
      refresh()
    } catch (err) {
      setError(err instanceof Refused ? err.message : 'That did not work.')
      if (err instanceof Refused && err.message.includes('already collected')) prove('twice')
    }
  }

  const collector = check?.collectorId ? world.collectors.find((c) => c.id === check.collectorId) : undefined
  const child = check?.childId ? world.children.find((c) => c.id === check.childId) : undefined
  const earlier = check?.result === 'already_collected' && child ? releasedToday(world, child.id) : undefined
  const message = earlier
    ? `${child!.name} was already collected at ${hhmm(earlier.at)} by ${earlier.collector} (${earlier.relationship}). Do not release.`
    : check
      ? MESSAGES[check.result]
      : ''

  return (
    <Panel id="door" who="ROOM LEADER" title="Door check">
      <div className="mb-3 grid grid-cols-2 gap-2">
        <button className={`btn ${mode === 'pass' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setMode('pass')}>
          Scan pass
        </button>
        <button className={`btn ${mode === 'code' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setMode('code')}>
          Enter code
        </button>
      </div>
      {mode === 'pass' && cameraSupported() && (
        <div className="mb-3">
          {camera ? (
            <CameraScan
              onFound={async (value) => {
                setCamera(false)
                setToken(value)
                begin(await checkPass(world, value))
              }}
              onError={(message) => {
                setCameraError(message)
                setCamera(false)
              }}
              onClose={() => setCamera(false)}
            />
          ) : (
            <>
              <button className="btn btn-primary w-full py-3 text-base" onClick={() => { setCameraError(null); setCamera(true) }}>
                Scan with the camera
              </button>
              <p className="mt-1 text-xs text-slate-500">
                Open this page on a second device too: show a pass there under “What the collector has”, and scan it here.
                The sample collectors’ passes work across devices.
              </p>
            </>
          )}
          {cameraError && <p className="mt-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{cameraError}</p>}
        </div>
      )}
      {mode === 'pass' ? (
        <form onSubmit={runPass} className="space-y-2">
          <textarea
            className="input min-h-20 font-mono text-xs"
            placeholder="A pass shown at the door appears here (CP1.…)"
            value={token}
            onChange={(e) => setToken(e.target.value)}
          />
          <div className="grid grid-cols-2 gap-2">
            <button className="btn btn-secondary" disabled={!token.trim()}>
              Check pass
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={!token.trim()}
              onClick={async () => {
                const altered = tamper(token)
                setToken(altered)
                begin(await checkPass(world, altered))
              }}
            >
              Alter one character
            </button>
          </div>
        </form>
      ) : (
        <form onSubmit={runCode} className="space-y-2">
          <select className="input" value={childId} onChange={(e) => setChildId(e.target.value)}>
            {world.children.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} · {c.room}
              </option>
            ))}
          </select>
          <input className="input font-mono tracking-widest" inputMode="numeric" placeholder="Six-digit code" value={code} onChange={(e) => setCode(e.target.value)} />
          <button className="btn btn-secondary w-full" disabled={!code.trim()}>
            Check code
          </button>
        </form>
      )}

      {done && <p className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{done}</p>}

      {check && (
        <div className={`mt-4 rounded-2xl border-2 p-4 ${check.result === 'valid' ? 'border-emerald-400' : 'border-red-400'}`}>
          <div className="flex items-center gap-2">
            <span className={`rounded-full px-3 py-1 text-sm font-bold ${check.result === 'valid' ? 'bg-emerald-600 text-white' : 'bg-red-600 text-white'}`}>
              {check.result === 'valid' ? 'AUTHORISED' : 'DO NOT RELEASE'}
            </span>
            <span className="text-xs text-slate-500">{LABEL[check.result]} · {hhmm(check.at)}</span>
          </div>
          <p className="mt-2 text-sm text-ink">{message}</p>
          {child && (
            <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
              <dt className="text-slate-500">Child</dt>
              <dd className="font-semibold text-ink">
                {child.name} · {child.room}
              </dd>
              {collector && (
                <>
                  <dt className="text-slate-500">Collector</dt>
                  <dd className="text-ink">
                    {collector.name} ({collector.relationship})
                  </dd>
                  {check.result === 'valid' && (
                    <>
                      <dt className="text-slate-500">Authorised by</dt>
                      <dd className="text-ink">{collector.authorisedBy}</dd>
                      <dt className="text-slate-500">Phone</dt>
                      <dd className="text-ink">{collector.phone}</dd>
                      {collector.note && (
                        <>
                          <dt className="text-slate-500">Note</dt>
                          <dd className="text-ink">{collector.note}</dd>
                        </>
                      )}
                    </>
                  )}
                </>
              )}
            </dl>
          )}
          {error && <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>}
          {check.result === 'valid' && (
            <div className="mt-4 space-y-2">
              <label className="flex items-start gap-2 text-sm text-ink">
                <input type="checkbox" className="mt-1" checked={idChecked} onChange={(e) => setIdChecked(e.target.checked)} />
                Photo ID seen, or the collector is known to me
              </label>
              <button className="btn btn-success w-full" onClick={() => choose(true)}>
                Release {child?.name.split(' ')[0]}
              </button>
              <div className="flex gap-2">
                <input className="input" placeholder="Reason, if not releasing" value={reason} onChange={(e) => setReason(e.target.value)} />
                <button className="btn btn-danger" onClick={() => choose(false)}>
                  Refuse
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </Panel>
  )
}

// ---------------------------------------------------------------- manager

function ManagerPanel({ world }: { world: World }) {
  const released = world.handovers.filter((h) => h.released)
  const refused = world.handovers.filter((h) => !h.released)
  const exceptions = world.checks.filter((k) => k.result !== 'valid')
  const download = () => {
    const url = URL.createObjectURL(new Blob([csv(world)], { type: 'text/csv' }))
    const a = Object.assign(document.createElement('a'), { href: url, download: 'collector-handovers-demo.csv' })
    a.click()
    URL.revokeObjectURL(url)
  }
  const stillHere = useMemo(() => world.children.filter((c) => !releasedToday(world, c.id)), [world, world.handovers.length])

  return (
    <Panel who="MANAGER" title="Today’s record">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          ['Collected', released.length],
          ['Not released', refused.length],
          ['Refused at the door', exceptions.length],
          ['Still at nursery', stillHere.length],
        ].map(([label, value]) => (
          <div key={label} className="rounded-xl border border-slate-200 p-3">
            <p className="font-display text-2xl font-extrabold text-ink">{value}</p>
            <p className="text-xs text-slate-500">{label}</p>
          </div>
        ))}
      </div>
      <div className="mt-5 grid gap-6 lg:grid-cols-2">
        <div>
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-ink">Handovers</h3>
            <button className="btn btn-secondary text-xs" onClick={download} disabled={world.handovers.length === 0}>
              Export CSV
            </button>
          </div>
          {world.handovers.length === 0 ? (
            <p className="mt-2 text-sm text-slate-500">No collections yet today.</p>
          ) : (
            <ul className="mt-2 divide-y divide-slate-100 text-sm">
              {[...world.handovers].reverse().map((h) => (
                <li key={h.id} className="py-2">
                  <span className="font-mono text-slate-500">{hhmm(h.at)}</span>{' '}
                  <b className="text-ink">{world.children.find((c) => c.id === h.childId)?.name}</b>{' '}
                  {h.released ? 'released to' : 'not released to'} {h.collector} ({h.relationship})
                  <span className="block text-xs text-slate-500">
                    Authorised by {h.authorisedBy} · {h.staff}
                    {h.released && h.idChecked ? ' · ID checked' : ''}
                    {h.reason ? ` · ${h.reason}` : ''}
                  </span>
                </li>
              ))}
            </ul>
          )}
          <p className="mt-2 text-xs text-slate-500">Handovers are append-only: nobody can edit or delete one afterwards.</p>
        </div>
        <div>
          <h3 className="font-semibold text-ink">Refused at the door</h3>
          {exceptions.length === 0 ? (
            <p className="mt-2 text-sm text-slate-500">None yet.</p>
          ) : (
            <ul className="mt-2 divide-y divide-slate-100 text-sm">
              {[...exceptions].reverse().map((k) => {
                const c = world.collectors.find((x) => x.id === k.collectorId)
                const ch = world.children.find((x) => x.id === k.childId)
                return (
                  <li key={k.id} className="flex items-center gap-2 py-2">
                    <span className="font-mono text-slate-500">{hhmm(k.at)}</span>
                    <span className="min-w-0 flex-1 text-ink">
                      {c ? c.name : 'Unknown pass'}
                      {ch ? ` for ${ch.name}` : ''} <span className="text-xs text-slate-500">by {k.method}</span>
                    </span>
                    <Tag result={k.result} />
                  </li>
                )
              })}
            </ul>
          )}
          <h3 className="mt-5 font-semibold text-ink">Activity</h3>
          <ul className="mt-2 space-y-1 text-xs text-slate-600">
            {[...world.audit].reverse().slice(0, 8).map((a, i) => (
              <li key={i}>
                <span className="font-mono text-slate-500">{hhmm(a.at)}</span> {a.what} <span className="text-slate-400">· {a.who}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <p className="mt-5 text-xs text-slate-500">
        The record supports your safeguarding practice and evidence. It does not replace your own policies or your staff’s judgement.
      </p>
    </Panel>
  )
}
