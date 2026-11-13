import assert from 'node:assert/strict'
import { test } from 'node:test'

import { checkPass, decide, passFor, reconcile, Refused, restrict, samePerson, sampleRegister, startingWorld } from '../src/lib/prototype.ts'

test('names match the way the live app matches them', () => {
  assert.ok(samePerson('Grace Smith', 'smith, GRACE'))
  assert.ok(samePerson('Grace Smith', 'Grace A. Smith'))
  assert.ok(samePerson("Zoë O'Brien", 'Zoe OBrien'))
  assert.ok(!samePerson('Grace', 'Grace Smith'))
  assert.ok(!samePerson('Grace Smith', 'Grace Jones'))
})

async function released(world = startingWorld(), id = 'leo-lucy', method: 'photo_id' | 'password' | null = 'photo_id') {
  const c = world.collectors.find((x) => x.id === id)!
  const check = await checkPass(world, await passFor(c))
  return { world, check, handover: decide(world, check, true, method, '') }
}

test('a release records how identity was checked', async () => {
  const { handover } = await released()
  assert.equal(handover.idMethod, 'photo_id')
  assert.equal(handover.idChecked, true)
})

test('a release needs a method, and the password needs one from the parent', async () => {
  const world = startingWorld()
  const lucy = world.collectors.find((x) => x.id === 'leo-dev')!
  const check = await checkPass(world, await passFor(lucy))
  assert.throws(() => decide(world, check, true, null, ''), Refused)
  assert.throws(() => decide(world, check, true, 'password', ''), /did not set a password/)
  // Grace's registration form has a password.
  assert.equal((await released(startingWorld(), 'maya-grace', 'password')).handover.idMethod, 'password')
})

test('Maya starts with a court order, shown with every check for her', async () => {
  const world = startingWorld()
  assert.deepEqual(world.restrictions.map((r) => [r.childId, r.person]), [['maya', 'Rob Shah']])
})

test('adding someone to the list removes them as a collector at once', async () => {
  const world = startingWorld()
  const dev = world.collectors.find((x) => x.id === 'leo-dev')!
  const token = await passFor(dev)
  const removed = restrict(world, 'leo', 'dev shah', 'court_order', '')
  assert.deepEqual(removed.map((c) => c.name), ['Dev Shah'])
  assert.equal((await checkPass(world, token)).result, 'revoked')
  // Dev is still Maya's collector: the list is per child.
  assert.equal(world.collectors.find((x) => x.id === 'maya-priya')!.revokedAt, null)
  assert.throws(() => restrict(world, 'leo', 'Dev', 'other', ''), /full name/)
})

test('a collector who slipped onto the list is still refused at the door', async () => {
  const world = startingWorld()
  world.restrictions.push({ id: 'x', childId: 'leo', person: 'Lucy Shah', reason: 'safeguarding', reference: '', at: 0 })
  const lucy = world.collectors.find((x) => x.id === 'leo-lucy')!
  assert.equal((await checkPass(world, await passFor(lucy))).result, 'restricted')
})

test('the register is compared with the door, child by child', async () => {
  const { world } = await released()
  const sample = sampleRegister(world)
  assert.match(sample, /^Child,Signed out,Collected by\nLeo Shah,14:33,Lucy Shah\nRuby Evans,15:00,Sarah Evans$/)
  const lines = reconcile(world, sample)
  const flags = Object.fromEntries(lines.map((l) => [l.child, l.flags]))
  assert.deepEqual(flags, { 'Ruby Evans': ['no_handover'], 'Leo Shah': [] })

  const edited = reconcile(world, 'Child,Signed out,Collected by\nLeo Shah,15:40,Dev Shah\nNobody Here,15:00,\nLeo Shah,15:41,\n')
  const byChild = Object.fromEntries(edited.map((l) => [l.child, l.flags]))
  assert.deepEqual(byChild['Leo Shah'], ['signed_out_twice', 'collector_mismatch', 'time_gap'])
  assert.deepEqual(byChild['Nobody Here'], ['unknown_child'])
  assert.throws(() => reconcile(world, 'Child,Signed out\nLeo Shah,teatime\n'), /Line 2/)
})
