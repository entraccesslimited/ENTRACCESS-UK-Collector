export type Role = 'admin' | 'staff' | 'parent' | 'operator'
export type Kind = 'regular' | 'one_off'
export type CheckResult =
  | 'valid'
  | 'unreadable'
  | 'wrong_nursery'
  | 'unknown'
  | 'restricted'
  | 'revoked'
  | 'reissued'
  | 'not_yet_valid'
  | 'expired'
  | 'already_used'
  | 'already_collected'
  | 'wrong_code'
  | 'locked'
  | 'outside_geofence'
  | 'no_location'

export type IdCheckMethod = 'photo_id' | 'known_to_staff' | 'password'
export type RestrictionReason = 'court_order' | 'safeguarding' | 'parent_request' | 'other'

export interface Me {
  id: string
  email: string
  full_name: string
  role: Role
  nursery_name: string
}

export interface Child {
  id: string
  full_name: string
  room: string | null
  active: boolean
}

export interface Authorisation {
  id: string
  child_id: string
  collector_name: string
  collector_relationship: string
  collector_phone: string
  note_for_staff: string | null
  kind: Kind
  valid_from: string
  valid_until: string | null
  created_at: string
  revoked_at: string | null
  used_at: string | null
  status: CheckResult
  authorised_by_name: string
  source: 'parent' | 'setting'
}

export interface PassInfo {
  authorisation_id: string
  token: string
  code_today: string
  share_url: string
  status: CheckResult
  nursery_name: string
  child_first_name: string
}

export interface PublicPass {
  nursery_name: string
  collector_name: string
  child_first_name: string
  kind: Kind
  valid_from: string
  valid_until: string | null
  status: CheckResult
  token: string
}

export interface Check {
  check_id: string
  result: CheckResult
  method: 'pass' | 'code'
  message: string
  can_release: boolean
  child_id: string | null
  child_name: string | null
  room: string | null
  collector_name: string | null
  collector_relationship: string | null
  collector_phone: string | null
  note_for_staff: string | null
  authorised_by_name: string | null
  kind: Kind | null
  valid_until: string | null
  restrictions: { person_name: string; reason: RestrictionReason }[]
}

export interface Handover {
  id: string
  child_id: string
  child_name: string
  collector_name: string
  collector_relationship: string
  authorised_by_name: string
  staff_name: string
  outcome: 'released' | 'refused'
  refusal_reason: string | null
  id_checked: boolean
  id_check_method: IdCheckMethod | null
  occurred_at: string
}

export interface Activity {
  at: string
  who: string
  what: string
  kind: string
}

export interface DoorCheck {
  id: string
  checked_at: string
  method: 'pass' | 'code'
  result: CheckResult
  child_name: string | null
  collector_name: string | null
  staff_name: string
  distance_m: number | null
}

export interface Today {
  released: number
  refused: number
  exceptions: number
  active_collectors: number
}

export interface Person {
  id: string
  email: string
  full_name: string
  phone: string | null
  role: Role
  active: boolean
  /** Invited by email and has not chosen a password yet, so cannot sign in. */
  invitation_pending?: boolean
}

export interface Link {
  parent_id: string
  parent_name: string
  child_id: string
  child_name: string
  relationship_label: string
}

export interface NurseryRow {
  id: string
  name: string
  slug: string
  active: boolean
  created_at: string
  geofence_on: boolean
  children: number
  parents: number
  room_leaders: number
  managers: number
  active_collectors: number
  collections_30d: number
  exceptions_30d: number
}

export interface CompanyOverview {
  nurseries: number
  active_nurseries: number
  children: number
  active_collectors: number
  collections_30d: number
  exceptions_30d: number
}

export interface Restriction {
  id: string
  child_id: string
  person_name: string
  reason: RestrictionReason
  reference: string | null
  detail: string | null
  created_at: string
  created_by_name: string
  ended_at: string | null
  removed_collectors: string[]
}

export type ReconciliationFlag =
  | 'no_handover'
  | 'no_sign_out'
  | 'collector_mismatch'
  | 'time_gap'
  | 'unknown_child'
  | 'signed_out_twice'

export interface SignOutImport {
  id: string
  day: string
  source: string
  rows: number
  imported_at: string
  imported_by_name: string | null
}

export interface ReconciliationLine {
  child_name: string
  child_id: string | null
  signed_out_at: string | null
  register_collected_by: string | null
  released_at: string | null
  collector_name: string | null
  collector_relationship: string | null
  staff_name: string | null
  id_check_method: IdCheckMethod | null
  refusals: string[]
  flags: ReconciliationFlag[]
}

export interface Reconciliation {
  day: string
  register_import: SignOutImport | null
  lines: ReconciliationLine[]
  flagged: number
  matched: number
}

export interface Kpis {
  start: string
  end: string
  releases: number
  refusals: number
  refusal_reasons: [string, number][]
  blocked_checks: number
  blocked_by_result: Partial<Record<CheckResult, number>>
  id_checks: Partial<Record<IdCheckMethod | 'not_recorded', number>>
  collectors_added_by_parents: number
  one_off_collectors: number
  contacts_added_by_nursery: number
  collectors_removed: number
  passes_shared: number
  restrictions_added: number
  restrictions_in_force: number
  days_with_releases: number
  registers_imported: number
  days_without_register: number
  reconciliation_flags: Partial<Record<ReconciliationFlag, number>>
}

export interface Evidence {
  nursery_name: string
  start: string
  end: string
  child_name: string | null
  generated_at: string
  generated_by: string
  kpis: Kpis
  collectors: {
    child_name: string
    collector_name: string
    collector_relationship: string
    kind: Kind
    source: 'parent' | 'setting'
    authorised_by_name: string
    created_at: string
    valid_until: string | null
    revoked_at: string | null
    used_at: string | null
  }[]
  restrictions: {
    child_name: string
    person_name: string
    reason: RestrictionReason
    reference: string | null
    created_at: string
    created_by_name: string
    ended_at: string | null
  }[]
  events: { at: string; kind: string; child: string; detail: string; who: string }[]
  flagged: {
    day: string
    child_name: string
    flags: ReconciliationFlag[]
    signed_out_at: string | null
    register_collected_by: string | null
    released_at: string | null
    collector_name: string | null
  }[]
  registers: string[]
}
