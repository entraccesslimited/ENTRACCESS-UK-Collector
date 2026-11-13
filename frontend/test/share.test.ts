import assert from 'node:assert/strict'
import { test } from 'node:test'

import { href, international, message } from '../src/lib/share.ts'

const pass = {
  collectorName: 'Grace Hughes',
  childFirstName: 'Maya',
  nurseryName: 'Little Acorns',
  shareUrl: 'https://example.test/pass/CP1.abc',
  code: '123456',
  regular: true,
}

test('UK numbers become international for WhatsApp', () => {
  assert.equal(international('07700 900123'), '447700900123')
  assert.equal(international('+44 7700 900123'), '447700900123')
  assert.equal(international('0044 7700 900123'), '447700900123')
  assert.equal(international('+353 87 123 4567'), '353871234567')
})

test('the link message carries the pass and asks for photo ID', () => {
  const text = message(pass, 'link')
  assert.match(text, /^Hi Grace, here is your pass to collect Maya from Little Acorns: https:\/\/example\.test\/pass\/CP1\.abc/)
  assert.match(text, /photo ID/)
})

test('the code message says it is for today only', () => {
  const text = message(pass, 'code')
  assert.match(text, /today is 123 456/)
  assert.match(text, /changes every day/)
  assert.doesNotMatch(message({ ...pass, regular: false }, 'code'), /changes every day/)
})

test('each channel opens the right app with the text', () => {
  assert.equal(href('whatsapp', '07700 900123', 'Hi there', 's'), 'https://wa.me/447700900123?text=Hi%20there')
  assert.equal(href('sms', '07700 900123', 'Hi there', 's'), 'sms:07700900123?&body=Hi%20there')
  assert.equal(href('email', '07700 900123', 'Hi', 'Collecting Maya'), 'mailto:?subject=Collecting%20Maya&body=Hi')
})
