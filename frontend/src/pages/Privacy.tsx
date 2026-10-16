import { SiteLayout } from '@/components/SiteLayout'

const HELD = [
  ['Children', 'Name and room', 'To know which child a collection is for'],
  ['Parents', 'Name, email, phone, and which children they are linked to', 'To let them authorise collectors and tell them about every collection'],
  ['Collectors', 'Name, relationship, phone, and any note the parent leaves for staff', 'So staff can check the right adult and ring them if needed'],
  ['Staff', 'Name, work email and role', 'To sign in, and to record who checked and who released each child'],
  ['Door checks', 'When, by whom, the result, and, only if the nursery uses a geofence, where the checking phone was', 'So any check can be looked at afterwards'],
  ['Handovers', 'Child, collector, who authorised it, who released or refused, when, and any reason given', 'The record a nursery needs if a collection is ever questioned'],
]

export function Privacy() {
  return (
    <SiteLayout>
      <article className="mx-auto max-w-3xl px-4 py-12 text-slate-700">
        <h1 className="text-3xl font-bold text-ink">Privacy and data protection</h1>
        <p className="mt-3">
          ENTRACCESS UK LTD builds Collector, a way for nurseries to record who may collect each child. That means we hold
          records about children and families. This page says what we hold, why, who can see it and how long it stays.
        </p>

        <div className="card mt-6">
          <dl className="grid gap-3 text-sm sm:grid-cols-2">
            <div><dt className="text-slate-500">Company</dt><dd>ENTRACCESS UK LTD, registered in England and Wales ([COMPANY NUMBER])</dd></div>
            <div><dt className="text-slate-500">ICO registration</dt><dd>[ICO REGISTRATION NUMBER]</dd></div>
            <div><dt className="text-slate-500">Law</dt><dd>UK GDPR and the Data Protection Act 2018</dd></div>
            <div><dt className="text-slate-500">Our role</dt><dd>Processor for each nursery; controller for our own records</dd></div>
          </dl>
        </div>

        <h2 className="mt-8 text-xl font-semibold text-ink">Who is responsible for what</h2>
        <p className="mt-2">
          <b>Each nursery is the data controller</b> for its children’s and families’ records: it decides who is enrolled,
          who is linked as a parent, and who on its staff may see what. <b>ENTRACCESS UK is the data processor</b>, acting on
          the nursery’s instructions. A parent asking about their own child should ask the nursery first.
        </p>

        <h2 className="mt-8 text-xl font-semibold text-ink">What we hold</h2>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr><th>About</th><th>What is held</th><th>Why</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {HELD.map(([about, what, why]) => (
                <tr key={about}><td className="font-medium">{about}</td><td>{what}</td><td>{why}</td></tr>
              ))}
            </tbody>
          </table>
        </div>

        <h2 className="mt-8 text-xl font-semibold text-ink">What we deliberately do not do</h2>
        <ul className="mt-2 list-disc space-y-1 pl-5">
          <li>No photos of children, no facial recognition, no fingerprints.</li>
          <li>A collector’s pass carries no name, child or date: only a signed identifier that means nothing outside its nursery.</li>
          <li>Location is used only for door checks, only when a nursery turns its geofence on, and only from the checking phone.</li>
          <li>We do not sell data or advertise. Our company portal shows each nursery’s counts and never names a child or family.</li>
          <li>One session cookie to keep you signed in, and nothing that tracks you across the internet.</li>
        </ul>

        <h2 className="mt-8 text-xl font-semibold text-ink">How long it stays</h2>
        <p className="mt-2">
          Retention is agreed with each nursery in its pilot or service agreement, and set out in its data protection impact
          assessment. Handover records are kept unaltered for that period, because they are what answers a question about a
          collection. When a nursery leaves, its records are returned or deleted as the agreement says.
        </p>

        <h2 className="mt-8 text-xl font-semibold text-ink">If you send us an enquiry</h2>
        <p className="mt-2">
          The details you send through the website are used only to reply to you, seen only by the people at ENTRACCESS UK
          who handle enquiries, and deleted within 12 months if you do not become a customer.
        </p>

        <h2 className="mt-8 text-xl font-semibold text-ink">Your rights</h2>
        <p className="mt-2">
          You may ask what is held about you, ask for a correction or erasure, or object to processing. Parents: ask your
          nursery first; they hold the record and can act on it at once. If you are not satisfied, you can complain to the{' '}
          <a className="text-brand-700 underline" href="https://ico.org.uk/make-a-complaint/">Information Commissioner’s Office</a>.
        </p>

        <h2 className="mt-8 text-xl font-semibold text-ink">If something goes wrong</h2>
        <p className="mt-2">
          We tell affected nurseries without delay: what happened, what was involved, what we have done and what they should
          do, and we report to the ICO within 72 hours where UK GDPR requires it.
        </p>
        <p className="mt-8 text-xs text-slate-500">Last reviewed 16 October 2026. Before any pilot, each nursery completes a data protection impact assessment with us.</p>
      </article>
    </SiteLayout>
  )
}
