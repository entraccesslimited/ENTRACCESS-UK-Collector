import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { SUPPORT_EMAIL } from '@/lib/contact'

import { SiteLayout } from '@/components/SiteLayout'
import { Alert } from '@/components/ui'
import { api } from '@/lib/api'

const REGIONS = [
  'North East',
  'North West',
  'Yorkshire and the Humber',
  'East Midlands',
  'West Midlands',
  'East of England',
  'London',
  'South East',
  'South West',
  'Wales',
  'Scotland',
  'Northern Ireland',
]

const STEPS = [
  {
    who: 'Parent',
    title: 'Authorises the collector',
    text: 'From their phone, a parent names who is collecting: once, on a set day, or regularly. They can remove anyone instantly.',
  },
  {
    who: 'Collector',
    title: 'Gets a pass',
    text: 'The collector is sent a link with a QR pass. Without a phone, the parent reads them a six-digit code that changes every day.',
  },
  {
    who: 'Staff',
    title: 'Check it at the door',
    text: 'Staff scan the pass or type the code against the child, see who authorised it, check photo ID, then release or refuse.',
  },
  {
    who: 'Nursery or school',
    title: 'Keeps the record',
    text: 'Every check and every handover is recorded and cannot be edited. Both parents are told at once who their child left with.',
  },
]

const SAFEGUARDS = [
  ['One-off means once', 'A one-off pass stops working the moment the child is released. It cannot be used twice.'],
  ['Removal is instant', 'A parent or manager removes a collector and the pass and code stop at once, even mid-check at the door.'],
  ['Passes prove nothing about a family', 'A pass carries no name, child or date, and is signed for one nursery or school only. A lost one tells the finder nothing.'],
  ['Codes cannot be guessed', 'Codes are checked against one child, never the whole setting, and entry pauses after five wrong tries.'],
  ['On site only, if you want it', 'An optional geofence refuses door checks from phones off the premises, and records how far away they were.'],
  ['A record nobody can rewrite', 'Checks and handovers are append-only, with the names copied in, so the record reads the same years later.'],
]

const FAQ = [
  ['Does it work for primary schools as well as nurseries?', 'Yes. The same checks work at a classroom door at home time, at the school gate, and for breakfast and after-school clubs: a parent authorises the collector, and a member of staff checks them before the child leaves.'],
  ['Does it replace our nursery management system or school MIS?', 'No. It works alongside the system you already use. It does not replace your registers, learning journals or your staff’s judgement.'],
  ['Do parents need to download an app?', 'No. Parents use a web page on their phone, and collectors open a link. Nothing to install.'],
  ['What if the collector has no smartphone?', 'The parent reads them the six-digit code for the day, and the member of staff types it in against the child.'],
  ['We are a secondary school. Is this for us?', 'Secondary students mostly come and go on their own, so our sister product, ENTRACCESS UK, is built for you: QR attendance at the gate, sign-in and sign-out, and alerts for parents. See entraccess.co.uk.'],
  ['Do you take photos of children?', 'No. There are no photos of children, no facial recognition and no fingerprints, ever.'],
  ['Where is the data kept?', 'Live deployments are hosted in the UK or European Economic Area, and data is encrypted in transit. Each nursery’s or school’s data is kept separate from every other’s.'],
  ['How does a pilot work?', 'Six to eight weeks in one room or class. First alongside your current process, then live once your safeguarding and data-protection review signs it off.'],
]

export function Website() {
  return (
    <SiteLayout>
      <section className="hero-grid border-b border-slate-200">
        <div className="mx-auto grid max-w-6xl items-center gap-10 px-4 py-16 md:grid-cols-2 md:py-24">
          <div>
            <p className="inline-block rounded-full bg-brand-50 px-3 py-1 text-xs font-bold tracking-widest text-brand-700">
              SAFE COLLECTION FOR UK NURSERIES AND PRIMARY SCHOOLS
            </p>
            <h1 className="mt-4 text-4xl leading-[1.05] text-ink md:text-6xl">Every handover, authorised.</h1>
            <p className="mt-5 text-lg text-slate-600">
              Parents authorise who collects their child. Staff check that authorisation at the door. The nursery or school keeps
              a clear record of every handover.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <a href="#contact" className="btn btn-primary px-6 py-3 text-base">
                Book a demo
              </a>
              <Link to="/prototype" className="btn btn-secondary border-slate-300 px-6 py-3 text-base hover:border-brand-500 hover:bg-surface hover:text-brand-700">
                Try the prototype
              </Link>
              <a href="#pricing" className="btn btn-secondary border-slate-300 px-6 py-3 text-base hover:border-brand-500 hover:bg-surface hover:text-brand-700">
                See pricing
              </a>
            </div>
            <p className="mt-4 text-sm text-slate-500">
              A secondary school? <a href="https://entraccess.co.uk" className="font-semibold text-brand-700 underline underline-offset-2">ENTRACCESS UK</a> is built for you.
            </p>
          </div>
          <div className="rounded-3xl bg-[#111a2e] p-6 text-white shadow-[0_30px_70px_-28px_rgb(29_78_216/0.55)] ring-1 ring-brand-500/25">
            <p className="text-sm text-[#cbd5e1]">4.15pm. A parent rings: “My mum’s picking up today. She’s not on the list.”</p>
            <ol className="mt-4 space-y-3 text-sm">
              <li className="rounded-xl border border-brand-500/30 bg-brand-500/15 p-3">✓ Mum is authorised from the parent’s phone, for today only</li>
              <li className="rounded-xl border border-brand-500/30 bg-brand-500/15 p-3">✓ She shows her pass at the door; a member of staff checks her ID</li>
              <li className="rounded-xl border border-brand-500/30 bg-brand-500/15 p-3">✓ Released at 17:42, recorded, and both parents are told</li>
            </ol>
            <p className="mt-4 text-xs text-[#94a3b8]">Afterwards, anyone can see who authorised it, who checked it and who released the child.</p>
          </div>
        </div>
      </section>

      <section id="how" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-16">
        <h2 className="text-3xl text-ink md:text-4xl">How it works</h2>
        <p className="mt-2 max-w-2xl text-slate-600">
          Most nursery and primary teams handle changed collections well, by phone, password and experience. The hard part is showing
          afterwards exactly what happened. Collector makes good practice easy to evidence.
        </p>
        <div className="mt-8 grid gap-4 md:grid-cols-4">
          {STEPS.map((step, i) => (
            <div key={step.title} className="card">
              <div className="flex items-center gap-3">
                <span className="grid size-9 place-items-center rounded-full bg-brand-600 font-display text-sm font-extrabold text-white">
                  {i + 1}
                </span>
                <span className="text-xs font-bold tracking-widest text-brand-600">{step.who.toUpperCase()}</span>
              </div>
              <h3 className="mt-1 font-semibold text-ink">{step.title}</h3>
              <p className="mt-2 text-sm text-slate-600">{step.text}</p>
            </div>
          ))}
        </div>
        <div className="mt-8 grid gap-4 md:grid-cols-3">
          {[
            ['For parents', 'Authorise a grandparent for today, a childminder every Tuesday, or a neighbour in an emergency. Remove anyone in a tap. See every collection.'],
            ['For staff at the door', 'Room leaders and class teachers get one screen: scan or type, see who the parent authorised and any note they left, release or refuse with a reason.'],
            ['For managers', 'Today’s releases, refusals and exceptions at a glance. The full record by date, exported to a spreadsheet for an inspection or a review.'],
          ].map(([title, text]) => (
            <div key={title} className="rounded-2xl border-t-4 border-brand-600 bg-mist p-5">
              <h3 className="font-semibold text-ink">{title}</h3>
              <p className="mt-2 text-sm text-slate-600">{text}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="safeguards" className="scroll-mt-20 bg-mist">
        <div className="mx-auto max-w-6xl px-4 py-16">
          <h2 className="text-3xl text-ink md:text-4xl">Safeguards built in</h2>
          <p className="mt-2 max-w-2xl text-slate-600">
            Designed with privacy first: only what is needed to authorise a collection, no photos of children, and each
            setting’s data kept separate.
          </p>
          <div className="mt-8 grid gap-4 md:grid-cols-3">
            {SAFEGUARDS.map(([title, text]) => (
              <div key={title} className="card">
                <span className="arch-mark" aria-hidden="true" />
                <h3 className="mt-3 font-semibold text-ink">{title}</h3>
                <p className="mt-2 text-sm text-slate-600">{text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="pricing" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-16">
        <h2 className="text-3xl text-ink md:text-4xl">Priced for a single setting, ready for a group or trust</h2>
        <p className="mt-2 max-w-2xl text-slate-600">
          Per nursery or school, per month: adding a child never changes the price. Most start with a paid pilot in one room or class,
          and nobody is asked to pay before the scope is agreed.
        </p>
        <div className="mt-8 grid gap-4 md:grid-cols-4">
          <Price name="Paid pilot" price="£750–£1,500" unit="per setting · 6–8 weeks" items={['Setup and import of your children', 'Staff training', 'Alongside your current process, then live', 'End-of-pilot validation report']} />
          <Price name="Core" price="£99" unit="per setting / month" items={['Everything on this page', 'One-off and regular collectors', 'Signed passes and daily codes', 'Instant removal', 'Door checks and the full handover record', 'Optional geofence']} />
          <Price name="Safeguard Pro" price="£179" unit="per setting / month" featured items={['Everything in Core', 'Sign-out reconciliation against your own register', 'Live exception dashboard', 'Audit exports and a KPI summary']} />
          <Price name="Groups" price="from £129" unit="per site / month" items={['Multi-site rollout', 'Group-level reporting', 'Start with one pilot setting', 'Volume terms']} />
        </div>
        <p className="mt-4 text-sm text-slate-500">Paid pilots are invoiced only after the pilot scope has been agreed in writing.</p>
      </section>

      <section id="faq" className="scroll-mt-20 bg-mist">
        <div className="mx-auto max-w-4xl px-4 py-16">
          <h2 className="text-3xl text-ink md:text-4xl">Questions</h2>
          <div className="mt-6 divide-y divide-slate-200 rounded-2xl border border-slate-200 bg-surface">
            {FAQ.map(([q, a]) => (
              <details key={q} className="group p-5">
                <summary className="cursor-pointer list-none font-semibold text-ink">
                  {q} <span className="float-right text-slate-400 group-open:rotate-45">+</span>
                </summary>
                <p className="mt-2 text-sm text-slate-600">{a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      <section id="contact" className="mx-auto max-w-5xl scroll-mt-20 px-4 py-16">
        <div className="blue-panel rounded-3xl px-5 py-10 shadow-[0_40px_80px_-40px_rgb(29_78_216/0.6)] sm:px-10">
        <p className="text-xs font-bold tracking-widest text-blue-200">BOOK A DEMO</p>
        <h2 className="mt-2 text-3xl text-white">Talk to us</h2>
        <p className="mt-2 max-w-2xl text-blue-100">
          Tell us about your nursery or school. We will reply within two working days, and can show you a demo first. We
          never ask for children’s or families’ details by email.
        </p>
        <p className="mt-2 text-blue-100">
          Or email us at{' '}
          <a className="font-semibold text-white underline underline-offset-2" href={`mailto:${SUPPORT_EMAIL}`}>
            {SUPPORT_EMAIL}
          </a>
          .
        </p>
        <Enquiry />
        </div>
      </section>
    </SiteLayout>
  )
}

function Price({ name, price, unit, items, featured }: { name: string; price: string; unit: string; items: string[]; featured?: boolean }) {
  return (
    <div className={`card flex flex-col ${featured ? 'border-brand-600 shadow-[0_30px_60px_-30px_rgb(37_99_235/0.45)] ring-2 ring-brand-600' : ''}`}>
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-ink">{name}</h3>
        {featured && <span className="rounded-full bg-gradient-to-r from-brand-600 to-brand-500 px-2.5 py-0.5 text-xs font-bold uppercase tracking-wide text-white">Most complete</span>}
      </div>
      <p className="mt-3 text-3xl font-bold text-ink">{price}</p>
      <p className="text-xs text-slate-500">{unit}</p>
      <ul className="mt-4 space-y-2 text-sm text-slate-600">
        {items.map((item) => (
          <li key={item}><span className="font-bold text-brand-600">✓</span> {item}</li>
        ))}
      </ul>
    </div>
  )
}

function Enquiry() {
  const blank = { contact_name: '', nursery_name: '', email: '', phone: '', region: '', children: '', interest: 'demo', message: '', website: '' }
  const [form, setForm] = useState(blank)
  const [sent, setSent] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const set = (key: keyof typeof form) => (event: { target: { value: string } }) => setForm({ ...form, [key]: event.target.value })

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const result = await api<{ message: string }>('/public/enquiries', {
        method: 'POST',
        json: { ...form, phone: form.phone || null, region: form.region || null, children: form.children || null, message: form.message || null },
      })
      setSent(result.message)
      setForm(blank)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not send. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  if (sent) return <div className="mt-6"><Alert tone="ok">{sent}</Alert></div>

  return (
    <form onSubmit={submit} className="card mt-6 grid gap-4 sm:grid-cols-2">
      {error && <div className="sm:col-span-2"><Alert>{error}</Alert></div>}
      <label>
        <span className="label">Your name</span>
        <input className="input" value={form.contact_name} onChange={set('contact_name')} required minLength={2} autoComplete="name" />
      </label>
      <label>
        <span className="label">Nursery or school</span>
        <input className="input" value={form.nursery_name} onChange={set('nursery_name')} required minLength={2} autoComplete="organization" />
      </label>
      <label>
        <span className="label">Email</span>
        <input className="input" type="email" value={form.email} onChange={set('email')} required autoComplete="email" />
      </label>
      <label>
        <span className="label">Phone (optional)</span>
        <input className="input" type="tel" value={form.phone} onChange={set('phone')} autoComplete="tel" placeholder="07700 900123" />
      </label>
      <label>
        <span className="label">Region</span>
        <select className="input" value={form.region} onChange={set('region')}>
          <option value="">Choose a region…</option>
          {REGIONS.map((r) => (
            <option key={r}>{r}</option>
          ))}
        </select>
      </label>
      <label>
        <span className="label">How many children (roughly)</span>
        <input className="input" value={form.children} onChange={set('children')} placeholder="About 60" />
      </label>
      <label className="sm:col-span-2">
        <span className="label">Interested in</span>
        <select className="input" value={form.interest} onChange={set('interest')}>
          <option value="demo">A demo</option>
          <option value="pilot">A paid pilot</option>
          <option value="core">Core</option>
          <option value="safeguard_pro">Safeguard Pro</option>
          <option value="group">A group of nurseries or a trust</option>
          <option value="question">Just a question</option>
        </select>
      </label>
      <label className="sm:col-span-2">
        <span className="label">Anything else (optional)</span>
        <textarea className="input min-h-28" value={form.message} onChange={set('message')} maxLength={2000} />
      </label>
      {/* Hidden from people; a bot that fills every field fills this one too. */}
      <label className="hidden" aria-hidden="true">
        Website
        <input tabIndex={-1} autoComplete="off" value={form.website} onChange={set('website')} />
      </label>
      <div className="sm:col-span-2">
        <button className="btn btn-primary" disabled={busy}>
          {busy ? 'Sending…' : 'Send enquiry'}
        </button>
        <p className="mt-2 text-xs text-slate-500">
          We use these details only to reply to you. See <Link to="/privacy" className="underline">privacy</Link>.
        </p>
      </div>
    </form>
  )
}
