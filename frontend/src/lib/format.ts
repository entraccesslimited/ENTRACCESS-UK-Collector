import type { Authorisation, CheckResult } from './types'

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
  revoked: 'Removed',
  reissued: 'Replaced',
  not_yet_valid: 'Starts later',
  expired: 'Ended',
  already_used: 'Used',
  wrong_code: 'Wrong code',
  locked: 'Paused',
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

function timeOf(value: string): string {
  return new Date(value).toLocaleTimeString('en-GB', { timeZone: LONDON, hour: '2-digit', minute: '2-digit' })
}

export function code(value: string): string {
  return `${value.slice(0, 3)} ${value.slice(3)}`
}
