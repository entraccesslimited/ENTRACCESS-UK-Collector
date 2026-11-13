import { useState } from 'react'

import { api } from '@/lib/api'
import { href, message, type Channel, type What } from '@/lib/share'
import type { Authorisation, PassInfo } from '@/lib/types'

/** Send the pass, or today's code, the way the sender chooses. The message
 *  opens in their own app; we only note which way it went. */
export function SharePass({ auth, pass, logPath }: { auth: Authorisation; pass: PassInfo; logPath: string }) {
  const [what, setWhat] = useState<What>('link')
  const [note, setNote] = useState<string | null>(null)
  const text = message(
    {
      collectorName: auth.collector_name,
      childFirstName: pass.child_first_name,
      nurseryName: pass.nursery_name,
      shareUrl: pass.share_url,
      code: pass.code_today,
      regular: auth.kind === 'regular',
    },
    what,
  )
  const subject = `Collecting ${pass.child_first_name} from ${pass.nursery_name}`
  const first = auth.collector_name.split(' ')[0]

  const log = (channel: Channel | 'share' | 'copy') => {
    void api(logPath, { method: 'POST', json: { channel, what } }).catch(() => undefined)
  }

  const more = async () => {
    try {
      if (navigator.share) {
        await navigator.share({ title: subject, text })
        log('share')
      } else {
        await navigator.clipboard.writeText(text)
        log('copy')
        setNote('Message copied. Paste it into any app.')
      }
    } catch {
      /* the share sheet was closed */
    }
  }

  const channels: { channel: Channel; label: string; target?: string }[] = [
    { channel: 'whatsapp', label: 'WhatsApp', target: '_blank' },
    { channel: 'sms', label: 'Text' },
    { channel: 'email', label: 'Email' },
  ]

  return (
    <div className="space-y-3 rounded-lg border border-slate-200 p-3">
      <p className="text-sm font-semibold">Send to {first}</p>
      <div className="grid grid-cols-2 gap-2 text-sm" role="radiogroup" aria-label="What to send">
        {(['link', 'code'] as What[]).map((w) => (
          <button
            key={w}
            type="button"
            role="radio"
            aria-checked={what === w}
            onClick={() => setWhat(w)}
            className={`rounded-lg border p-2 text-left ${what === w ? 'border-brand-500 bg-brand-50' : 'border-slate-300'}`}
          >
            <span className="block font-semibold">{w === 'link' ? 'QR pass link' : 'Today’s code'}</span>
            <span className="text-xs text-slate-600">{w === 'link' ? 'They show the QR at the door.' : 'For a phone without internet.'}</span>
          </button>
        ))}
      </div>
      <p className="rounded bg-slate-50 p-2 text-xs text-slate-700">{text}</p>
      <div className="grid grid-cols-4 gap-2">
        {channels.map((c) => (
          <a
            key={c.channel}
            className="btn btn-secondary px-2 text-center"
            href={href(c.channel, auth.collector_phone, text, subject)}
            target={c.target}
            rel={c.target ? 'noopener noreferrer' : undefined}
            onClick={() => log(c.channel)}
          >
            {c.label}
          </a>
        ))}
        <button type="button" className="btn btn-secondary px-2" onClick={more}>
          More
        </button>
      </div>
      {note && <p className="text-xs text-emerald-700">{note}</p>}
      <p className="text-xs text-slate-500">
        Opens your own app with the message ready to {auth.collector_phone}. Nothing is sent until you press send there.
      </p>
    </div>
  )
}
