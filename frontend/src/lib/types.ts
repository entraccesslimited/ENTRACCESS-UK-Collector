export type Role = 'admin' | 'staff' | 'parent' | 'operator'
export type Kind = 'regular' | 'one_off'
export type CheckResult =
  | 'valid'
  | 'unreadable'
  | 'wrong_nursery'
  | 'unknown'
  | 'revoked'
  | 'reissued'
  | 'not_yet_valid'
  | 'expired'
  | 'already_used'
  | 'wrong_code'
  | 'locked'
  | 'outside_geofence'
  | 'no_location'

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
}

export interface PassInfo {
  authorisation_id: string
  token: string
  code_today: string
  share_url: string
  status: CheckResult
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
  occurred_at: string
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
