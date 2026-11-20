import type { AbsenceReason, Authorisation, CheckResult, IdCheckMethod, ReconciliationFlag, RestrictionReason } from './types'

const LONDON = 'Europe/London'

export function when(value: string): string {
  return new Date(value).toLocaleString('en-GB', {
    timeZone: LONDON,
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function day(value: string): string {
  return new Date(value).toLocaleDateString('en-GB', {
    timeZone: LONDON,
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  })
}

export function todayIso(): string {
  // The nursery's date, not the browser's: en-CA formats as YYYY-MM-DD.
  return new Date().toLocaleDateString('en-CA', { timeZone: LONDON })
}

export const STATUS_LABEL: Record<CheckResult, string> = {
  valid: 'Active',
  unreadable: 'Not a pass',
  wrong_nursery: 'Another nursery',
  unknown: 'Unknown',
  restricted: 'Never release',
  revoked: 'Removed',
  reissued: 'Replaced',
  not_yet_valid: 'Starts later',
  expired: 'Ended',
  already_used: 'Used',
  already_collected: 'Already collected',
  wrong_code: 'Wrong code',
  locked: 'Paused',
  outside_geofence: 'Off site',
  no_location: 'No location',
}

export function validity(auth: Pick<Authorisation, 'kind' | 'valid_from' | 'valid_until'>): string {
  if (auth.kind === 'one_off') {
    return auth.valid_until
      ? `Once, ${day(auth.valid_from)} ${timeOf(auth.valid_from)}–${timeOf(auth.valid_until)}`
      : `Once, from ${when(auth.valid_from)}`
  }
  return auth.valid_until
    ? `Any day, ${day(auth.valid_from)} to ${day(auth.valid_until)}`
    : `Any day from ${day(auth.valid_from)}`
}

export const ID_CHECK_LABEL: Record<IdCheckMethod, string> = {
  photo_id: 'ID document',
  known_to_staff: 'Known to staff',
  password: 'Password',
}

export const RESTRICTION_LABEL: Record<RestrictionReason, string> = {
  court_order: 'Court order',
  safeguarding: 'Safeguarding',
  parent_request: 'Parent’s request',
  other: 'Other',
}

export const FLAG_LABEL: Record<ReconciliationFlag, string> = {
  no_handover: 'Signed out, not released at the door',
  no_sign_out: 'Released, not signed out',
  collector_mismatch: 'Register names someone else',
  time_gap: 'Times over 15 minutes apart',
  unknown_child: 'Child not found here',
  signed_out_twice: 'Signed out twice',
}

/** A time of day in the nursery's zone, or a dash. */
export function clock(value: string | null): string {
  return value ? timeOf(value) : '—'
}

function timeOf(value: string): string {
  return new Date(value).toLocaleTimeString('en-GB', { timeZone: LONDON, hour: '2-digit', minute: '2-digit' })
}

export function code(value: string): string {
  return `${value.slice(0, 3)} ${value.slice(3)}`
}

export const ABSENCE_LABEL: Record<AbsenceReason, string> = {
  ill: 'Ill',
  appointment: 'Appointment',
  holiday: 'Holiday',
  other: 'Other',
}

/** ISO weekday numbers as the nursery reads them. */
export const WEEKDAYS: { value: string; short: string }[] = [
  { value: '1', short: 'Mon' },
  { value: '2', short: 'Tue' },
  { value: '3', short: 'Wed' },
  { value: '4', short: 'Thu' },
  { value: '5', short: 'Fri' },
  { value: '6', short: 'Sat' },
  { value: '7', short: 'Sun' },
]

export function sessionDays(days: string): string {
  if (days === '12345') return 'Mon–Fri'
  if (days === '1234567') return 'Every day'
  return WEEKDAYS.filter((d) => days.includes(d.value)).map((d) => d.short).join(', ') || 'No days'
}
