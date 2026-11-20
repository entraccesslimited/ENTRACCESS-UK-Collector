/** Register marks made without signal, kept on the phone until they are sent.
 *
 *  A mark is the child, the moment staff tapped it, and an id of its own, so
 *  the server records it once at the time it was made however often it is
 *  sent. Nothing here decides whether a child may go home: the door check is
 *  never done offline, because only the server knows if a pass was revoked.
 */

import type { SyncResult } from './types'

export interface PendingMark {
  client_id: string
  child_id: string
  occurred_at: string
}

export const QUEUE_KEY = 'collector.register.pending.v1'

export function newId(): string {
  const c = globalThis.crypto
  if (c && 'randomUUID' in c) return c.randomUUID()
  return `m-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}

/** Add a mark, unless this child already has one waiting from today. */
export function addMark(queue: PendingMark[], childId: string, now: Date, id: string = newId()): PendingMark[] {
  const today = now.toDateString()
  if (queue.some((m) => m.child_id === childId && new Date(m.occurred_at).toDateString() === today)) return queue
  return [...queue, { client_id: id, child_id: childId, occurred_at: now.toISOString() }]
}

/** Take a child's waiting mark back, before it was ever sent. */
export function removeMark(queue: PendingMark[], childId: string): PendingMark[] {
  return queue.filter((m) => m.child_id !== childId)
}

/** Drop every mark the server answered, and say which it refused and why. */
export function settle(queue: PendingMark[], results: SyncResult[]): { queue: PendingMark[]; refused: string[] } {
  const answered = new Set(results.map((r) => r.client_id))
  return {
    queue: queue.filter((m) => !answered.has(m.client_id)),
    refused: results.filter((r) => r.status === 'rejected').map((r) => r.message ?? 'A mark was refused.'),
  }
}

export function pendingFor(queue: PendingMark[], childId: string): PendingMark | undefined {
  return queue.find((m) => m.child_id === childId)
}

export function load(storage: Pick<Storage, 'getItem'> | undefined = globalThis.localStorage): PendingMark[] {
  try {
    const raw = storage?.getItem(QUEUE_KEY)
    const parsed: unknown = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed)
      ? parsed.filter(
          (m): m is PendingMark =>
            m && typeof m.client_id === 'string' && typeof m.child_id === 'string' && typeof m.occurred_at === 'string',
        )
      : []
  } catch {
    return []
  }
}

export function save(queue: PendingMark[], storage: Pick<Storage, 'setItem'> | undefined = globalThis.localStorage): void {
  try {
    storage?.setItem(QUEUE_KEY, JSON.stringify(queue))
  } catch {
    // Private browsing or a full store: the marks stay in memory for this visit.
  }
}

/** A failed request that never reached the server, as opposed to one it refused. */
export function isOffline(err: unknown): boolean {
  return err instanceof TypeError || (typeof navigator !== 'undefined' && navigator.onLine === false)
}
