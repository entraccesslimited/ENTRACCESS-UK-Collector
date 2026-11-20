import { Alert, PageTitle, Stat } from '@/components/ui'
import { clock, STATUS_LABEL, when } from '@/lib/format'
import { useLoad } from '@/lib/useLoad'
import type { DoorCheck, Today } from '@/lib/types'

export function AdminToday() {
  const today = useLoad<Today>('/admin/today')
  const exceptions = useLoad<DoorCheck[]>('/admin/checks?exceptions_only=true')
  return (
    <>
      <PageTitle title="Today" sub="Handovers and exceptions at the door, in the nursery’s time." />
      {today.error && <Alert>{today.error}</Alert>}
      {today.data && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat label="Released" value={today.data.released} tone="green" />
          <Stat label="Refused" value={today.data.refused} tone="red" />
          <Stat label="Exceptions at the door" value={today.data.exceptions} tone="amber" />
          <Stat label="Active collectors" value={today.data.active_collectors} />
        </div>
      )}
      {today.data && (
        <section className="card mt-6">
          <h2 className="mb-1 font-semibold">Register</h2>
          <p className="text-sm text-slate-600">
            <b>{today.data.arrived}</b> marked in of <b>{today.data.expected}</b> booked in today
            {today.data.absent > 0 ? `, ${today.data.absent} off with an absence given` : ''}.
          </p>
          {today.data.not_arrived.length > 0 && (
            <p className="mt-2 text-sm">
              <span className="font-semibold text-amber-800">Not in yet:</span> {today.data.not_arrived.join(', ')}
            </p>
          )}
          <p className="mt-2 text-xs text-slate-500">
            {today.data.alert_run
              ? today.data.alert_run.suppressed_reason
                ? `Non-arrival check at ${clock(today.data.alert_run.ran_at)}: ${today.data.alert_run.suppressed_reason}`
                : `Non-arrival check at ${clock(today.data.alert_run.ran_at)}: parents of ${today.data.alert_run.alerted} child${today.data.alert_run.alerted === 1 ? '' : 'ren'} emailed.`
              : today.data.arrival_alert_at
                ? `Parents are told at ${today.data.arrival_alert_at.slice(0, 5)} if a child booked in has not arrived.`
                : 'Non-arrival alerts are off. Turn them on in Settings.'}
          </p>
        </section>
      )}
      <section className="card mt-6 overflow-x-auto">
        <h2 className="mb-3 font-semibold">Exceptions in the last 30 days</h2>
        <p className="mb-3 text-sm text-slate-600">
          Every check that did not come back valid: removed or replaced passes, wrong codes, passes from elsewhere.
        </p>
        {exceptions.data?.length === 0 && <p className="text-sm text-slate-500">None. Every check came back valid.</p>}
        {exceptions.data && exceptions.data.length > 0 && (
          <table className="w-full">
            <thead>
              <tr>
                <th>When</th>
                <th>Result</th>
                <th>Child</th>
                <th>Collector</th>
                <th>Checked by</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {exceptions.data.map((c) => (
                <tr key={c.id}>
                  <td>{when(c.checked_at)}</td>
                  <td className="font-medium text-red-700">
                    {STATUS_LABEL[c.result]}
                    {c.result === 'outside_geofence' && c.distance_m !== null && (
                      <span className="block text-xs font-normal text-slate-500">
                        {c.distance_m >= 1000 ? `${(c.distance_m / 1000).toFixed(1)} km` : `${Math.round(c.distance_m)} m`} away
                      </span>
                    )}
                  </td>
                  <td>{c.child_name ?? '—'}</td>
                  <td>{c.collector_name ?? '—'}</td>
                  <td>{c.staff_name}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  )
}
