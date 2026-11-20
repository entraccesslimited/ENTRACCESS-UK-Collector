import assert from 'node:assert/strict'
import { test } from 'node:test'

import { addMark, load, pendingFor, removeMark, save, settle, type PendingMark } from '../src/lib/offlineRegister.ts'

const morning = new Date('2026-11-23T08:40:00Z')

test('a mark keeps the moment it was made and an id of its own', () => {
  const queue = addMark([], 'child-1', morning, 'id-1')
  assert.deepEqual(queue, [{ client_id: 'id-1', child_id: 'child-1', occurred_at: '2026-11-23T08:40:00.000Z' }])
})

test('tapping a child twice the same day queues one mark', () => {
  const once = addMark([], 'child-1', morning, 'id-1')
  const twice = addMark(once, 'child-1', new Date('2026-11-23T08:45:00Z'), 'id-2')
  assert.equal(twice.length, 1)
  assert.equal(pendingFor(twice, 'child-1')?.client_id, 'id-1')
})

test('a mark can be taken back before it is sent', () => {
  const queue = addMark(addMark([], 'child-1', morning, 'a'), 'child-2', morning, 'b')
  assert.deepEqual(removeMark(queue, 'child-1').map((m) => m.child_id), ['child-2'])
})

test('every answered mark leaves the queue, and refusals are reported', () => {
  const queue: PendingMark[] = [
    { client_id: 'a', child_id: 'c1', occurred_at: morning.toISOString() },
    { client_id: 'b', child_id: 'c2', occurred_at: morning.toISOString() },
    { client_id: 'c', child_id: 'c3', occurred_at: morning.toISOString() },
  ]
  const { queue: left, refused } = settle(queue, [
    { client_id: 'a', child_id: 'c1', status: 'recorded', message: null },
    { client_id: 'b', child_id: 'c2', status: 'rejected', message: 'That mark is too old to record.' },
  ])
  assert.deepEqual(left.map((m) => m.client_id), ['c'])
  assert.deepEqual(refused, ['That mark is too old to record.'])
})

test('the queue survives a reload, and a damaged store reads as empty', () => {
  const store = new Map<string, string>()
  const storage = { getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => void store.set(k, v) }
  const queue = addMark([], 'child-1', morning, 'id-1')
  save(queue, storage)
  assert.deepEqual(load(storage), queue)
  store.set('collector.register.pending.v1', '{not json')
  assert.deepEqual(load(storage), [])
  store.set('collector.register.pending.v1', JSON.stringify([{ client_id: 1 }, ...queue]))
  assert.deepEqual(load(storage), queue)
})
