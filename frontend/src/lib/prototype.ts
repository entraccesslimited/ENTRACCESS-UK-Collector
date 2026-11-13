/**
 * The Collector's rules, run in the browser for the public prototype.
 *
 * Mirrors app/collection.py closely enough that what a visitor sees here is
 * what a nursery would see live: signed passes, daily six-digit codes checked
 * against one child, one-off collectors who can be used once, instant removal,
 * a pause after five wrong codes, a child released once a day, a never-release
 * list, the way staff checked identity, contacts from registration forms, and
 * the end-of-day comparison with the sign-out register. Nothing is stored or
 * sent anywhere; a reload starts again.
 */

export type Kind = 'regular' | 'one_off'

export type Result =
  | 'valid'
  | 'unreadable'
  | 'wrong_nursery'
  | 'restricted'
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
  restricted: "This person is on the child's never-release list. Do not release the child. Keep the child inside and tell the manager now.",
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
  restricted: 'Never release',
  revoked: 'Removed',
  reissued: 'Replaced',
  not_yet_valid: 'Starts later',
  expired: 'Ended',
  already_used: 'Used',
  already_collected: 'Already collected',
  wrong_code: 'Wrong code',
  locked: 'Paused',
}

/** How staff satisfied themselves the person at the door is the named collector. */
export type IdMethod = 'photo_id' | 'known_to_staff' | 'password'
export const ID_LABEL: Record<IdMethod, string> = {
  photo_id: 'Photo ID',
  known_to_staff: 'Known to staff',
  password: 'Password',
}

export type RestrictionReason = 'court_order' | 'safeguarding' | 'parent_request' | 'other'
export const REASON_LABEL: Record<RestrictionReason, string> = {
  court_order: 'Court order',
  safeguarding: 'Safeguarding',
  parent_request: 'Parent’s request',
  other: 'Other',
}

export interface Restriction {
  id: string
  childId: string
  person: string
  reason: RestrictionReason
  reference: string
  at: number
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
  /** Named by a parent, or held by the nursery from the registration form. */
  source: 'parent' | 'setting'
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
  idMethod: IdMethod | null
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
  restrictions: Restriction[]
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
    source: 'parent',
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
      // From Maya's registration form, added by the manager.
      { ...regular('maya', 'Grace Hughes', 'Grandmother', 'Amira Khan', '07700 900106'), source: 'setting', note: 'Password: bluebell' },
      regular('ruby', 'Sarah Evans', 'Mother', 'Sarah Evans', '07700 900104'),
      { ...regular('ruby', 'Raj Patel', 'Grandparent', 'Sarah Evans', '07700 900105'), note: 'No smartphone: uses the daily code.' },
    ],
    checks: [],
    handovers: [],
    notices: [],
    restrictions: [
      { id: 'r-maya-rob', childId: 'maya', person: 'Rob Shah', reason: 'court_order', reference: 'ZW26P00123', at: 7 * 60 },
    ],
    audit: [
      { at: 7 * 60, who: MANAGER, what: 'Opened the day: 7 regular collectors on file, 1 from a registration form' },
      { at: 7 * 60, who: MANAGER, what: 'Never-release list for Maya Shah: Rob Shah (court order)' },
    ],
  }
}

export function status(c: Collector, now: number): Result {
  if (c.revokedAt !== null) return 'revoked'
  if (c.usedAt !== null) return 'already_used'
  if (now < c.from) return 'not_yet_valid'
  if (c.until !== null && now > c.until) return 'expired'
  return 'valid'
}

// ---------------------------------------------------------------- names
//
// As app/names.py: the same person is "Grace Smith", "smith, grace" or
// "Grace A. Smith", but a first name alone never matches.

export function words(name: string): Set<string> {
  const plain = name
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/['\u2019]/g, '')
    .replace(/[^a-z\s]/g, ' ')
  return new Set(plain.split(/\s+/).filter((w) => w.length > 1))
}

export function samePerson(a: string, b: string): boolean {
  const [x, y] = [words(a), words(b)]
  if (x.size === 0 || y.size === 0) return false
  const [small, big] = x.size <= y.size ? [x, y] : [y, x]
  const inside = [...small].every((w) => big.has(w))
  return inside && (small.size === big.size || small.size >= 2)
}

export function restrictionFor(world: World, childId: string, person: string): Restriction | undefined {
  return world.restrictions.find((r) => r.childId === childId && samePerson(r.person, person))
}

/** Put someone on a child's never-release list; any collector of that name stops at once. */
export function restrict(world: World, childId: string, person: string, reason: RestrictionReason, reference: string): Collector[] {
  const name = person.trim().replace(/\s+/g, ' ')
  if (words(name).size < 2) throw new Refused('Give the person’s full name, as on the order or record.')
  const child = world.children.find((c) => c.id === childId)!
  if (restrictionFor(world, childId, name)) throw new Refused(`${name} is already on ${child.name}’s never-release list.`)
  world.restrictions.push({ id: uid('r'), childId, person: name, reason, reference: reference.trim(), at: world.clock })
  world.audit.push({ at: world.clock, who: MANAGER, what: `Never-release list for ${child.name}: ${name} (${REASON_LABEL[reason].toLowerCase()})` })
  const removed = world.collectors.filter((c) => c.childId === childId && c.revokedAt === null && samePerson(c.name, name))
  for (const c of removed) {
    c.revokedAt = world.clock
    world.audit.push({ at: world.clock, who: MANAGER, what: `Removed ${c.name} as a collector for ${child.name}` })
  }
  return removed
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
  if (restrictionFor(world, c.childId, c.name)) return 'restricted'
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

export function decide(world: World, check: DoorCheck, release: boolean, idMethod: IdMethod | null, reason: string): Handover {
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
    if (restrictionFor(world, child.id, c.name)) {
      throw new Refused(`${c.name} is on ${child.name}’s never-release list. Do not release the child. Tell the manager.`)
    }
    if (!idMethod) throw new Refused('Say how you checked who the collector is: photo ID, known to you, or the password.')
    if (idMethod === 'password' && !c.note.trim()) {
      throw new Refused('The parent did not set a password for this collector. Check photo ID instead.')
    }
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
    idChecked: release,
    idMethod: release ? idMethod : null,
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
      ? `Released ${child.name} to ${c.name} (${c.relationship}), ID checked: ${ID_LABEL[idMethod!].toLowerCase()}`
      : `Refused ${c.name} for ${child.name}: ${reason.trim()}`,
  })
  return handover
}

export function csv(world: World): string {
  const rows = [['time', 'child', 'outcome', 'collector', 'relationship', 'authorised by', 'staff', 'id check', 'reason']]
  for (const h of world.handovers) {
    const child = world.children.find((x) => x.id === h.childId)
    rows.push([hhmm(h.at), child?.name ?? '', h.released ? 'released' : 'refused', h.collector, h.relationship, h.authorisedBy, h.staff, h.idMethod ? ID_LABEL[h.idMethod] : '', h.reason ?? ''])
  }
  return rows.map((r) => r.map((v) => `"${v.replace(/"/g, '""')}"`).join(',')).join('\n')
}

// ---------------------------------------------------------------- the register
//
// As app/reconcile.py: the nursery's own sign-out register, compared child by
// child with the door.

export type Flag = 'no_handover' | 'no_sign_out' | 'collector_mismatch' | 'time_gap' | 'unknown_child' | 'signed_out_twice'
export const FLAG_LABEL: Record<Flag, string> = {
  no_handover: 'Signed out, not released at the door',
  no_sign_out: 'Released, not signed out',
  collector_mismatch: 'Register names someone else',
  time_gap: 'Times over 15 minutes apart',
  unknown_child: 'Child not found here',
  signed_out_twice: 'Signed out twice',
}
export const TIME_GAP_MINUTES = 15

export interface RegisterLine {
  child: string
  childId: string | null
  signedOut: number | null
  collectedBy: string
  released: Handover | null
  flags: Flag[]
}

/** A sample of what the nursery system would export for today, so far. */
export function sampleRegister(world: World): string {
  const lines = ['Child,Signed out,Collected by']
  for (const h of world.handovers.filter((x) => x.released)) {
    const child = world.children.find((c) => c.id === h.childId)!
    lines.push(`${child.name},${hhmm(h.at + 3)},${h.collector}`)
  }
  // Someone the register says left, with nobody checked at the door.
  if (!releasedToday(world, 'ruby')) lines.push(`Ruby Evans,${hhmm(Math.max(world.clock - 20, 15 * 60))},Sarah Evans`)
  return lines.join('\n')
}

const clockOf = (text: string): number | null => {
  const m = text.trim().match(/^(\d{1,2})[:.](\d{2})$/)
  if (!m) return null
  const [h, mm] = [Number(m[1]), Number(m[2])]
  return h < 24 && mm < 60 ? h * 60 + mm : null
}

export function reconcile(world: World, text: string): RegisterLine[] {
  const rows = text.split(/\r?\n/).map((r) => r.split(',').map((c) => c.trim())).filter((r) => r.some(Boolean))
  if (rows.length === 0) throw new Refused('The register is empty.')
  const header = rows[0].map((h) => h.toLowerCase())
  const iChild = header.findIndex((h) => h.startsWith('child'))
  const iTime = header.findIndex((h) => h.includes('signed out') || h.includes('time'))
  const iWho = header.findIndex((h) => h.includes('collected'))
  if (iChild < 0 || iTime < 0) throw new Refused('The first line needs “Child” and “Signed out” columns.')
  const out: RegisterLine[] = []
  const byChild = new Map<string, RegisterLine>()
  for (const [n, row] of rows.slice(1).entries()) {
    const name = row[iChild] ?? ''
    const time = clockOf(row[iTime] ?? '')
    if (!name || time === null) throw new Refused(`Line ${n + 2}: give a child and a time like 15:42.`)
    const child = world.children.find((c) => samePerson(c.name, name) && words(c.name).size === words(name).size)
    if (!child) {
      out.push({ child: name, childId: null, signedOut: time, collectedBy: row[iWho] ?? '', released: null, flags: ['unknown_child'] })
      continue
    }
    const seen = byChild.get(child.id)
    if (seen) {
      if (!seen.flags.includes('signed_out_twice')) seen.flags.push('signed_out_twice')
      continue
    }
    const line: RegisterLine = { child: child.name, childId: child.id, signedOut: time, collectedBy: row[iWho] ?? '', released: releasedToday(world, child.id) ?? null, flags: [] }
    byChild.set(child.id, line)
    out.push(line)
  }
  for (const child of world.children) {
    const h = releasedToday(world, child.id)
    if (h && !byChild.has(child.id)) out.push({ child: child.name, childId: child.id, signedOut: null, collectedBy: '', released: h, flags: [] })
  }
  for (const line of out) {
    if (line.childId === null) continue
    const h = line.released
    if (line.signedOut !== null && !h) line.flags.unshift('no_handover')
    if (h && line.signedOut === null) line.flags.unshift('no_sign_out')
    if (h && line.signedOut !== null) {
      const said = words(line.collectedBy)
      const first = h.collector.split(' ')[0].toLowerCase()
      const named =
        !line.collectedBy.trim() ||
        samePerson(line.collectedBy, h.collector) ||
        (said.size === 1 && [...said].every((w) => w === first || words(h.relationship).has(w)))
      if (!named) line.flags.push('collector_mismatch')
      if (Math.abs(line.signedOut - h.at) > TIME_GAP_MINUTES) line.flags.push('time_gap')
    }
  }
  world.audit.push({ at: world.clock, who: MANAGER, what: `Compared the sign-out register with the door: ${out.filter((l) => l.flags.length).length} to look at` })
  return out.sort((a, b) => Number(b.flags.length > 0) - Number(a.flags.length > 0))
}
