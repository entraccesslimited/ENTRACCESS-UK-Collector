/**
 * The Collector's rules, run in the browser for the public prototype.
 *
 * Mirrors app/collection.py closely enough that what a visitor sees here is
 * what a nursery would see live: signed passes, daily six-digit codes checked
 * against one child, one-off collectors who can be used once, instant removal,
 * a pause after five wrong codes, and a child released once a day. Nothing is
 * stored or sent anywhere; a reload starts again.
 */

export type Kind = 'regular' | 'one_off'

export type Result =
  | 'valid'
  | 'unreadable'
  | 'wrong_nursery'
  | 'revoked'
  | 'reissued'
  | 'not_yet_valid'
  | 'expired'
  | 'already_used'
  | 'already_collected'
  | 'wrong_code'
  | 'locked'

/** The same words staff see at the door in the live app. */
export const MESSAGES: Record<Result, string> = {
  valid: "Authorised. Check the collector's ID, then release or refuse.",
  unreadable: 'That is not a collector pass. Do not release the child.',
  wrong_nursery: 'This pass was not issued by this nursery. Do not release.',
  revoked: 'The parent has removed this collector. Do not release the child.',
  reissued: 'This is an old pass that has been replaced. Do not release.',
  not_yet_valid: 'This collector is not authorised yet. Do not release.',
  expired: 'This authorisation has ended. Do not release the child.',
  already_used: 'This one-off pass has already been used. Do not release.',
  already_collected: 'This child has already been collected today. Do not release.',
  wrong_code: 'That code does not match any collector for this child.',
  locked: 'Too many wrong codes for this child. Call the parent.',
}

export const LABEL: Record<Result, string> = {
  valid: 'Authorised',
  unreadable: 'Not a pass',
  wrong_nursery: 'Not genuine',
  revoked: 'Removed',
  reissued: 'Replaced',
  not_yet_valid: 'Starts later',
  expired: 'Ended',
  already_used: 'Used',
  already_collected: 'Already collected',
  wrong_code: 'Wrong code',
  locked: 'Paused',
}

export interface Child {
  id: string
  name: string
  room: string
}

export interface Parent {
  id: string
  name: string
  childIds: string[]
}

export interface Collector {
  id: string
  childId: string
  name: string
  relationship: string
  phone: string
  note: string
  kind: Kind
  /** Minutes after midnight, today. A regular collector is open all day. */
  from: number
  until: number | null
  authorisedBy: string
  version: number
  revokedAt: number | null
  usedAt: number | null
}

export interface DoorCheck {
  id: string
  at: number
  method: 'pass' | 'code'
  result: Result
  childId: string | null
  collectorId: string | null
  staff: string
}

export interface Handover {
  id: string
  at: number
  checkId: string
  childId: string
  collectorId: string
  collector: string
  relationship: string
  authorisedBy: string
  staff: string
  released: boolean
  reason: string | null
  idChecked: boolean
}

export interface Notice {
  at: number
  to: string
  text: string
}

export interface World {
  clock: number
  children: Child[]
  parents: Parent[]
  collectors: Collector[]
  checks: DoorCheck[]
  handovers: Handover[]
  notices: Notice[]
  audit: { at: number; who: string; what: string }[]
}

export const STAFF = 'Sam Taylor (room leader)'
export const MANAGER = 'Amira Khan (manager)'
/** A decision has to follow the check promptly, as in the live app. */
export const DECISION_MINUTES = 10
export const CODE_LIMIT = 5
export const CODE_WINDOW_MINUTES = 15

export const hhmm = (minutes: number) =>
  `${String(Math.floor(minutes / 60) % 24).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`

let counter = 0
export const uid = (prefix: string) => `${prefix}-${(++counter).toString(36)}-${Math.random().toString(36).slice(2, 6)}`

/** The families and collectors every scenario starts from. */
export function startingWorld(): World {
  const children: Child[] = [
    { id: 'leo', name: 'Leo Shah', room: 'Caterpillars' },
    { id: 'maya', name: 'Maya Shah', room: 'Butterflies' },
    { id: 'ruby', name: 'Ruby Evans', room: 'Caterpillars' },
  ]
  const parents: Parent[] = [
    { id: 'priya', name: 'Priya Shah', childIds: ['leo', 'maya'] },
    { id: 'dev', name: 'Dev Shah', childIds: ['leo', 'maya'] },
    { id: 'sarah', name: 'Sarah Evans', childIds: ['ruby'] },
  ]
  // Fixed ids, with the fixed key below, so a sample collector's pass shown on
  // one device scans on another: a laptop showing the pass, a phone at the door.
  const regular = (childId: string, name: string, relationship: string, by: string, phone: string): Collector => ({
    id: `${childId}-${name.split(' ')[0].toLowerCase()}`,
    childId,
    name,
    relationship,
    phone,
    note: '',
    kind: 'regular',
    from: 0,
    until: null,
    authorisedBy: by,
    version: 1,
    revokedAt: null,
    usedAt: null,
  })
  return {
    clock: 14 * 60 + 30,
    children,
    parents,
    collectors: [
      regular('leo', 'Priya Shah', 'Mother', 'Priya Shah', '07700 900101'),
      regular('leo', 'Dev Shah', 'Father', 'Priya Shah', '07700 900102'),
      { ...regular('leo', 'Lucy Shah', 'Grandparent', 'Priya Shah', '07700 900103'), note: 'Usually walks; tall, grey coat.' },
      regular('maya', 'Priya Shah', 'Mother', 'Priya Shah', '07700 900101'),
      regular('ruby', 'Sarah Evans', 'Mother', 'Sarah Evans', '07700 900104'),
      { ...regular('ruby', 'Raj Patel', 'Grandparent', 'Sarah Evans', '07700 900105'), note: 'No smartphone: uses the daily code.' },
    ],
    checks: [],
    handovers: [],
    notices: [],
    audit: [{ at: 7 * 60, who: MANAGER, what: 'Opened the day: 6 regular collectors on file' }],
  }
}

export function status(c: Collector, now: number): Result {
  if (c.revokedAt !== null) return 'revoked'
  if (c.usedAt !== null) return 'already_used'
  if (now < c.from) return 'not_yet_valid'
  if (c.until !== null && now > c.until) return 'expired'
  return 'valid'
}

export function releasedToday(world: World, childId: string): Handover | undefined {
  return [...world.handovers].reverse().find((h) => h.childId === childId && h.released)
}

// ---------------------------------------------------------------- signing
//
// A pass is CP1.<payload>.<signature>, HMAC-SHA256. The key is the same in
// every browser, so the sample collectors' passes scan from one device to
// another; a pass altered by a byte is still refused, exactly as the live app
// refuses one from another nursery. It is a demo key and protects nothing.

const KEY = crypto.subtle.importKey(
  'raw',
  new TextEncoder().encode('entraccess-uk-collector-prototype-demo-key'),
  { name: 'HMAC', hash: 'SHA-256' },
  false,
  ['sign', 'verify'],
)
const enc = new TextEncoder()
const b64 = (bytes: ArrayBuffer | Uint8Array) =>
  btoa(String.fromCharCode(...new Uint8Array(bytes))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
const unb64 = (text: string) => Uint8Array.from(atob(text.replace(/-/g, '+').replace(/_/g, '/')), (c) => c.charCodeAt(0))

export async function passFor(c: Collector): Promise<string> {
  const payload = b64(enc.encode(JSON.stringify({ a: c.id, v: c.version })))
  const sig = await crypto.subtle.sign('HMAC', await KEY, enc.encode(`CP1.${payload}`))
  return `CP1.${payload}.${b64(sig).slice(0, 22)}`
}

/** Today's code for a collector: six digits, changing every day and on reissue. */
export async function codeFor(c: Collector): Promise<string> {
  const day = new Date().toISOString().slice(0, 10)
  const sig = new Uint8Array(await crypto.subtle.sign('HMAC', await KEY, enc.encode(`${c.id}:${c.version}:${day}`)))
  const n = ((sig[0] << 24) | (sig[1] << 16) | (sig[2] << 8) | sig[3]) >>> 0
  return String(n % 1_000_000).padStart(6, '0')
}

async function readPass(token: string): Promise<{ id: string; version: number } | null> {
  const parts = token.trim().split('.')
  if (parts.length !== 3 || parts[0] !== 'CP1') return null
  const expected = await crypto.subtle.sign('HMAC', await KEY, enc.encode(`CP1.${parts[1]}`))
  if (b64(expected).slice(0, 22) !== parts[2]) return null
  try {
    const body = JSON.parse(new TextDecoder().decode(unb64(parts[1])))
    return { id: String(body.a), version: Number(body.v) }
  } catch {
    return null
  }
}

/** Change one character of a pass, the way a forged or edited copy would be. */
export function tamper(token: string): string {
  const parts = token.split('.')
  if (parts.length !== 3) return token + 'x'
  const body = parts[1]
  const i = Math.floor(body.length / 2)
  const swapped = body[i] === 'A' ? 'B' : 'A'
  return `${parts[0]}.${body.slice(0, i)}${swapped}${body.slice(i + 1)}.${parts[2]}`
}

// ---------------------------------------------------------------- the door

function record(world: World, check: Omit<DoorCheck, 'id' | 'at' | 'staff'>): DoorCheck {
  const full = { ...check, id: uid('k'), at: world.clock, staff: STAFF }
  world.checks.push(full)
  return full
}

function unlessCollected(world: World, c: Collector, result: Result): Result {
  if (result !== 'valid') return result
  return releasedToday(world, c.childId) ? 'already_collected' : result
}

export async function checkPass(world: World, token: string): Promise<DoorCheck> {
  if (!token.trim().startsWith('CP1.')) {
    return record(world, { method: 'pass', result: 'unreadable', childId: null, collectorId: null })
  }
  const read = await readPass(token)
  if (!read) return record(world, { method: 'pass', result: 'wrong_nursery', childId: null, collectorId: null })
  const c = world.collectors.find((x) => x.id === read.id)
  if (!c) return record(world, { method: 'pass', result: 'wrong_nursery', childId: null, collectorId: null })
  if (read.version !== c.version) {
    return record(world, { method: 'pass', result: 'reissued', childId: c.childId, collectorId: c.id })
  }
  const result = unlessCollected(world, c, status(c, world.clock))
  return record(world, { method: 'pass', result, childId: c.childId, collectorId: c.id })
}

export async function checkCode(world: World, childId: string, code: string): Promise<DoorCheck> {
  const recent = world.checks.filter(
    (k) =>
      k.childId === childId &&
      k.method === 'code' &&
      (k.result === 'wrong_code' || k.result === 'locked') &&
      world.clock - k.at < CODE_WINDOW_MINUTES,
  ).length
  if (recent >= CODE_LIMIT) return record(world, { method: 'code', result: 'locked', childId, collectorId: null })
  for (const c of world.collectors.filter((x) => x.childId === childId)) {
    if ((await codeFor(c)) === code.replace(/\D/g, '')) {
      const result = unlessCollected(world, c, status(c, world.clock))
      return record(world, { method: 'code', result, childId, collectorId: c.id })
    }
  }
  return record(world, { method: 'code', result: 'wrong_code', childId, collectorId: null })
}

export class Refused extends Error {}

export function decide(world: World, check: DoorCheck, release: boolean, idChecked: boolean, reason: string): Handover {
  if (check.result !== 'valid' || !check.collectorId || !check.childId) {
    throw new Refused('Only an authorised check can lead to a handover.')
  }
  if (world.handovers.some((h) => h.checkId === check.id)) throw new Refused('This check has already been decided.')
  if (world.clock - check.at > DECISION_MINUTES) throw new Refused('This check is too old. Check the collector again.')
  const c = world.collectors.find((x) => x.id === check.collectorId)!
  const child = world.children.find((x) => x.id === check.childId)!
  if (release) {
    if (status(c, world.clock) !== 'valid') {
      throw new Refused('This collector stopped being authorised after the check. Do not release the child.')
    }
    const earlier = releasedToday(world, child.id)
    if (earlier) {
      throw new Refused(`${child.name} was already collected at ${hhmm(earlier.at)} by ${earlier.collector}. Do not release.`)
    }
    if (!idChecked) throw new Refused('Tick the ID check first: photo ID seen, or the collector is known to you.')
  } else if (!reason.trim()) {
    throw new Refused('Say why the child was not released.')
  }
  const handover: Handover = {
    id: uid('h'),
    at: world.clock,
    checkId: check.id,
    childId: child.id,
    collectorId: c.id,
    collector: c.name,
    relationship: c.relationship,
    authorisedBy: c.authorisedBy,
    staff: STAFF,
    released: release,
    reason: release ? null : reason.trim(),
    idChecked,
  }
  world.handovers.push(handover)
  if (release && c.kind === 'one_off') c.usedAt = world.clock
  // Every parent linked to the child hears, not only the one who authorised.
  for (const p of world.parents.filter((x) => x.childIds.includes(child.id))) {
    world.notices.push({
      at: world.clock,
      to: p.name,
      text: release
        ? `${child.name} was collected at ${hhmm(world.clock)} by ${c.name} (${c.relationship}), authorised by ${c.authorisedBy}.`
        : `${c.name} came to collect ${child.name} at ${hhmm(world.clock)} and was not released: ${reason.trim()}. ${child.name} is safe at the nursery.`,
    })
  }
  world.audit.push({
    at: world.clock,
    who: STAFF,
    what: release
      ? `Released ${child.name} to ${c.name} (${c.relationship})${idChecked ? ', ID checked' : ''}`
      : `Refused ${c.name} for ${child.name}: ${reason.trim()}`,
  })
  return handover
}

export function csv(world: World): string {
  const rows = [['time', 'child', 'outcome', 'collector', 'relationship', 'authorised by', 'staff', 'reason']]
  for (const h of world.handovers) {
    const child = world.children.find((x) => x.id === h.childId)
    rows.push([hhmm(h.at), child?.name ?? '', h.released ? 'released' : 'refused', h.collector, h.relationship, h.authorisedBy, h.staff, h.reason ?? ''])
  }
  return rows.map((r) => r.map((v) => `"${v.replace(/"/g, '""')}"`).join(',')).join('\n')
}
