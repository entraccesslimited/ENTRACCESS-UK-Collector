/** Building the message a parent sends to a collector, from their own phone.
 *  Nothing is sent by ENTRACCESS UK: these open WhatsApp, Messages or the
 *  email app with the text filled in, and the parent presses send. */

export type Channel = 'whatsapp' | 'sms' | 'email'
export type What = 'link' | 'code'

export interface ShareInput {
  collectorName: string
  childFirstName: string
  nurseryName: string
  shareUrl: string
  code: string
  regular: boolean
}

/** A UK mobile in the international form WhatsApp wants: 07700 900123 → 447700900123. */
export function international(phone: string): string {
  const digits = phone.replace(/\D/g, '')
  if (phone.trim().startsWith('+')) return digits
  if (digits.startsWith('00')) return digits.slice(2)
  if (digits.startsWith('0')) return `44${digits.slice(1)}`
  return digits
}

export function message(input: ShareInput, what: What): string {
  const first = input.collectorName.trim().split(/\s+/)[0]
  if (what === 'code') {
    const spaced = `${input.code.slice(0, 3)} ${input.code.slice(3)}`
    return (
      `Hi ${first}, your code to collect ${input.childFirstName} from ${input.nurseryName} today is ${spaced}. ` +
      `Give it at the door and bring photo ID.` +
      (input.regular ? ' The code changes every day, so ask me for a new one next time.' : '')
    )
  }
  return (
    `Hi ${first}, here is your pass to collect ${input.childFirstName} from ${input.nurseryName}: ${input.shareUrl} ` +
    `Show the QR code at the door and bring photo ID. Please do not forward it.`
  )
}

export function href(channel: Channel, phone: string, text: string, subject: string): string {
  const body = encodeURIComponent(text)
  if (channel === 'whatsapp') return `https://wa.me/${international(phone)}?text=${body}`
  // "?&body=" is read by both iOS and Android Messages.
  if (channel === 'sms') return `sms:${phone.replace(/[^\d+]/g, '')}?&body=${body}`
  return `mailto:?subject=${encodeURIComponent(subject)}&body=${body}`
}
