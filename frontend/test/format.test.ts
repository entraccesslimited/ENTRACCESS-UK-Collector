import assert from 'node:assert/strict'
import { test } from 'node:test'

import { code, STATUS_LABEL, validity } from '../src/lib/format.ts'

test('a code reads in two groups of three', () => {
  assert.equal(code('123456'), '123 456')
})

test('every door result has a label staff can read', () => {
  for (const label of Object.values(STATUS_LABEL)) assert.ok(label.length > 0)
  assert.equal(STATUS_LABEL.revoked, 'Removed')
})

test('a one-off collection says it is once', () => {
  const text = validity({ kind: 'one_off', valid_from: '2026-10-20T08:00:00Z', valid_until: '2026-10-20T17:00:00Z' })
  assert.match(text, /^Once,/)
  assert.match(text, /09:00–18:00/)
})

test('a regular collector with no end says from', () => {
  assert.match(validity({ kind: 'regular', valid_from: '2026-10-20T00:00:00Z', valid_until: null }), /^Any day from/)
})

test('every reconciliation flag and ID check reads in plain words', async () => {
  const { FLAG_LABEL, ID_CHECK_LABEL, RESTRICTION_LABEL } = await import('../src/lib/format.ts')
  for (const labels of [FLAG_LABEL, ID_CHECK_LABEL, RESTRICTION_LABEL]) {
    for (const label of Object.values(labels)) assert.ok(label.length > 0)
  }
  assert.equal(STATUS_LABEL.restricted, 'Never release')
})
