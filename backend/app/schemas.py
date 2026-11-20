"""What the API accepts and returns."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import (
    AbsenceReason,
    CheckMethod,
    CheckResult,
    CollectorKind,
    CollectorSource,
    HandoverOutcome,
    IdCheckMethod,
    RestrictionReason,
    Role,
)


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SignIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class ForgotPassword(BaseModel):
    email: EmailStr


class SetPassword(BaseModel):
    token: str = Field(min_length=10, max_length=2000)
    password: str = Field(min_length=1, max_length=200)


class PasswordLinkInfo(BaseModel):
    """Who a link is for, so the page can greet them before they type."""

    full_name: str
    email: str
    first_time: bool


class Me(Out):
    id: uuid.UUID
    email: str
    full_name: str
    role: Literal["admin", "staff", "parent", "operator"]
    nursery_name: str = Field(description="The nursery's name, or the company's for an operator.")


class ChildOut(Out):
    id: uuid.UUID
    full_name: str
    room: str | None
    active: bool
    session_days: str = "12345"


class AuthorisationIn(BaseModel):
    collector_name: str = Field(min_length=2, max_length=200)
    collector_relationship: str = Field(min_length=1, max_length=60, examples=["Grandparent"])
    collector_phone: str = Field(min_length=7, max_length=40, examples=["07700 900123"])
    kind: CollectorKind
    note_for_staff: str | None = Field(default=None, max_length=300)
    on_date: date | None = None
    from_time: time | None = None
    until_time: time | None = None
    start_date: date | None = None
    end_date: date | None = None


class AuthorisationOut(Out):
    id: uuid.UUID
    child_id: uuid.UUID
    collector_name: str
    collector_relationship: str
    collector_phone: str
    note_for_staff: str | None
    kind: CollectorKind
    valid_from: datetime
    valid_until: datetime | None
    created_at: datetime
    revoked_at: datetime | None
    used_at: datetime | None
    status: CheckResult
    authorised_by_name: str
    source: CollectorSource = CollectorSource.PARENT
    has_photo: bool = False


class PassOut(BaseModel):
    """What a parent shares with the collector."""

    authorisation_id: uuid.UUID
    token: str
    code_today: str = Field(description="Six digits, good today only, in the nursery's time.")
    share_url: str
    status: CheckResult
    nursery_name: str = ""
    child_first_name: str = ""


class PublicPassOut(BaseModel):
    """What the collector sees when they open the shared link.

    The child's first name only, and nothing about the family: anyone who is
    forwarded the link learns as little as possible.
    """

    nursery_name: str
    collector_name: str
    child_first_name: str
    kind: CollectorKind
    valid_from: datetime
    valid_until: datetime | None
    status: CheckResult
    token: str


class PositionIn(BaseModel):
    """Where the checking phone says it is, from the browser's Geolocation API."""

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_m: float = Field(default=0, ge=0, le=1_000_000)


class CodeCheckIn(BaseModel):
    child_id: uuid.UUID
    code: str = Field(min_length=6, max_length=12)
    position: PositionIn | None = None


class PassCheckIn(BaseModel):
    token: str = Field(min_length=3, max_length=400)
    position: PositionIn | None = None


class GeofenceIn(BaseModel):
    latitude: float = Field(ge=-90, le=90, examples=[53.3811])
    longitude: float = Field(ge=-180, le=180, examples=[-1.4701])
    radius_m: int = Field(ge=50, le=5000, examples=[150])


class GeofenceOut(BaseModel):
    enabled: bool
    latitude: float | None = None
    longitude: float | None = None
    radius_m: int | None = None
    min_radius_m: int = 50
    max_radius_m: int = 5000


class RestrictionAtDoor(BaseModel):
    """Who must not be given this child. Shown to staff with every check for the child."""

    person_name: str
    reason: RestrictionReason


class CheckOut(BaseModel):
    """The answer at the door."""

    check_id: uuid.UUID
    result: CheckResult
    method: CheckMethod
    message: str
    can_release: bool
    child_id: uuid.UUID | None = None
    child_name: str | None = None
    room: str | None = None
    collector_name: str | None = None
    collector_relationship: str | None = None
    collector_phone: str | None = None
    note_for_staff: str | None = None
    authorised_by_name: str | None = None
    kind: CollectorKind | None = None
    valid_until: datetime | None = None
    restrictions: list[RestrictionAtDoor] = Field(default_factory=list)
    # A photo of the collector, from GET /door/checks/{check_id}/photo.
    has_photo: bool = False


class DecisionIn(BaseModel):
    release: bool
    reason: str | None = Field(default=None, max_length=500)
    # How staff checked the person is the named collector. Required to release.
    id_check_method: IdCheckMethod | None = None


class HandoverOut(Out):
    id: uuid.UUID
    child_id: uuid.UUID
    child_name: str
    collector_name: str
    collector_relationship: str
    authorised_by_name: str
    staff_name: str
    outcome: HandoverOutcome
    refusal_reason: str | None
    id_checked: bool
    id_check_method: IdCheckMethod | None = None
    occurred_at: datetime


class ActivityOut(BaseModel):
    at: datetime
    who: str
    what: str
    kind: str


class DoorCheckOut(BaseModel):
    id: uuid.UUID
    checked_at: datetime
    method: CheckMethod
    result: CheckResult
    child_name: str | None
    collector_name: str | None
    staff_name: str
    distance_m: float | None = None


class NonArrivalRunOut(Out):
    day: date
    ran_at: datetime
    expected: int
    missing: int
    alerted: int
    suppressed_reason: str | None


class TodayOut(BaseModel):
    released: int
    refused: int
    exceptions: int
    active_collectors: int
    # The arrival register for today.
    expected: int = 0
    arrived: int = 0
    absent: int = 0
    not_arrived: list[str] = Field(default_factory=list)
    arrival_alert_at: time | None = None
    alert_run: NonArrivalRunOut | None = None


class PhotoIn(BaseModel):
    """A photo as a `data:` URL, already shrunk on the phone."""

    data_url: str = Field(min_length=20, max_length=420_000)


class ChildUpdateIn(BaseModel):
    room: str | None = Field(default=None, max_length=80)
    # ISO weekday numbers, Monday 1 to Sunday 7: "12345" is Monday to Friday.
    session_days: str | None = Field(default=None, min_length=1, max_length=7)


class AbsenceIn(BaseModel):
    day: date
    reason: AbsenceReason
    note: str | None = Field(default=None, max_length=300)


class AbsenceOut(Out):
    id: uuid.UUID
    child_id: uuid.UUID
    day: date
    reason: AbsenceReason
    note: str | None
    created_at: datetime


class StaffAbsenceIn(AbsenceIn):
    child_id: uuid.UUID


class RegisterChildOut(BaseModel):
    child_id: uuid.UUID
    full_name: str
    room: str | None
    expected: bool
    arrived_at: datetime | None = None
    arrived_offline: bool = False
    absence_reason: AbsenceReason | None = None
    absence_note: str | None = None
    collected_at: datetime | None = None
    collected_by: str | None = None


class RegisterOut(BaseModel):
    day: date
    children: list[RegisterChildOut]
    arrival_alert_at: time | None = None


class ArrivalIn(BaseModel):
    child_id: uuid.UUID
    # Set by a phone sending a mark it made without signal: when it was made.
    occurred_at: datetime | None = None
    client_id: str | None = Field(default=None, min_length=8, max_length=64)


class RegisterSyncIn(BaseModel):
    marks: list[ArrivalIn] = Field(max_length=500)


class RegisterSyncResult(BaseModel):
    client_id: str | None
    child_id: uuid.UUID
    # recorded, duplicate (sent before), already (marked in by someone else), rejected
    status: Literal["recorded", "duplicate", "already", "rejected"]
    message: str | None = None


class RegisterSyncOut(BaseModel):
    results: list[RegisterSyncResult]


class AlertSettingsIn(BaseModel):
    # Unset turns the morning non-arrival alert off.
    arrival_alert_at: time | None = None


class AlertSettingsOut(BaseModel):
    arrival_alert_at: time | None


class ChildIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    room: str | None = Field(default=None, max_length=80)


class PersonIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=200)
    phone: str | None = Field(default=None, max_length=40)
    role: Role
    # Left out, they are emailed a link to choose their own — nobody else then
    # knows it. Given, it is a first password the manager hands over in person.
    password: str | None = Field(default=None, min_length=10, max_length=200)


class PersonOut(Out):
    id: uuid.UUID
    email: str
    full_name: str
    phone: str | None
    role: Role
    active: bool
    # Invited by email and has not chosen a password yet, so cannot sign in.
    invitation_pending: bool = False


class LinkIn(BaseModel):
    parent_id: uuid.UUID
    child_id: uuid.UUID
    relationship_label: str = Field(default="Parent", max_length=60)


class LinkOut(BaseModel):
    parent_id: uuid.UUID
    parent_name: str
    child_id: uuid.UUID
    child_name: str
    relationship_label: str


class NurseryRow(BaseModel):
    """One nursery as the company portal sees it: settings and counts only."""

    id: uuid.UUID
    name: str
    slug: str
    active: bool
    created_at: datetime
    geofence_on: bool
    children: int
    parents: int
    room_leaders: int
    managers: int
    active_collectors: int
    collections_30d: int
    exceptions_30d: int


class CompanyOverview(BaseModel):
    nurseries: int
    active_nurseries: int
    children: int
    active_collectors: int
    collections_30d: int
    exceptions_30d: int


class NewNursery(BaseModel):
    name: str = Field(min_length=2, max_length=200, examples=["Little Acorns Nursery, Sheffield"])
    slug: str = Field(min_length=3, max_length=50, examples=["little-acorns-sheffield"])
    manager_name: str = Field(min_length=2, max_length=200)
    manager_email: EmailStr
    # Left out, the manager is emailed a link to choose their own password,
    # so the company never knows it.
    manager_password: str | None = Field(default=None, min_length=10, max_length=200)


UK_REGIONS: tuple[str, ...] = (
    "North East",
    "North West",
    "Yorkshire and the Humber",
    "East Midlands",
    "West Midlands",
    "East of England",
    "London",
    "South East",
    "South West",
    "Wales",
    "Scotland",
    "Northern Ireland",
)
INTERESTS: tuple[str, ...] = ("demo", "pilot", "core", "safeguard_pro", "group", "question")


class EnquiryIn(BaseModel):
    contact_name: str = Field(min_length=2, max_length=120)
    nursery_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=40)
    region: str | None = Field(default=None, max_length=60)
    children: str | None = Field(default=None, max_length=40, examples=["About 60"])
    interest: str | None = Field(default=None, max_length=40)
    message: str | None = Field(default=None, max_length=2000)
    # Never shown to a person: a bot that fills every field gives itself away.
    website: str | None = Field(default=None, max_length=200)


class EnquiryOut(Out):
    id: uuid.UUID
    contact_name: str
    nursery_name: str
    email: str
    phone: str | None
    region: str | None
    children: str | None
    interest: str | None
    message: str | None
    created_at: datetime
    handled_at: datetime | None
    handled_by: str | None


class RestrictionIn(BaseModel):
    person_name: str = Field(min_length=3, max_length=200)
    reason: RestrictionReason
    reference: str | None = Field(default=None, max_length=120, examples=["Court order ZW26P00123"])
    detail: str | None = Field(default=None, max_length=500)


class RestrictionOut(Out):
    id: uuid.UUID
    child_id: uuid.UUID
    person_name: str
    reason: RestrictionReason
    reference: str | None
    detail: str | None
    created_at: datetime
    created_by_name: str
    ended_at: datetime | None
    removed_collectors: list[str] = Field(default_factory=list)


class SignOutImportIn(BaseModel):
    day: date
    csv: str = Field(min_length=1, max_length=1_000_000)
    source: str = Field(default="CSV", max_length=200, examples=["famly-sign-outs.csv"])


class SignOutImportOut(BaseModel):
    id: uuid.UUID
    day: date
    source: str
    rows: int
    imported_at: datetime
    imported_by_name: str | None


class ReconciliationLineOut(BaseModel):
    child_name: str
    child_id: uuid.UUID | None
    signed_out_at: datetime | None
    register_collected_by: str | None
    released_at: datetime | None
    collector_name: str | None
    collector_relationship: str | None
    staff_name: str | None
    id_check_method: IdCheckMethod | None
    refusals: list[str]
    flags: list[str]


class ReconciliationOut(BaseModel):
    day: date
    register_import: SignOutImportOut | None
    lines: list[ReconciliationLineOut]
    flagged: int
    matched: int


class ContactIn(BaseModel):
    """A collector from the child's registration form, added by the nursery."""

    collector_name: str = Field(min_length=3, max_length=200)
    collector_relationship: str = Field(min_length=1, max_length=60, examples=["Grandparent"])
    collector_phone: str = Field(min_length=7, max_length=40, examples=["07700 900123"])
    note_for_staff: str | None = Field(default=None, max_length=300)
    start_date: date | None = None
    end_date: date | None = None


class ContactImportIn(BaseModel):
    csv: str = Field(min_length=1, max_length=500_000)


class ContactImportOut(BaseModel):
    added: int
    skipped: int
    collectors: list[str]


class SharedIn(BaseModel):
    """How the pass went to the collector. Sent from the sharer's own phone."""

    channel: Literal["whatsapp", "sms", "email", "share", "copy"]
    what: Literal["link", "code"]


class KpisOut(BaseModel):
    start: date
    end: date
    releases: int
    refusals: int
    refusal_reasons: list[tuple[str, int]]
    blocked_checks: int
    blocked_by_result: dict[str, int]
    id_checks: dict[str, int]
    collectors_added_by_parents: int
    one_off_collectors: int
    contacts_added_by_nursery: int
    collectors_removed: int
    passes_shared: int
    restrictions_added: int
    restrictions_in_force: int
    days_with_releases: int
    registers_imported: int
    days_without_register: int
    reconciliation_flags: dict[str, int]


class EvidenceCollectorOut(BaseModel):
    child_name: str
    collector_name: str
    collector_relationship: str
    kind: CollectorKind
    source: CollectorSource
    authorised_by_name: str
    created_at: datetime
    valid_until: datetime | None
    revoked_at: datetime | None
    used_at: datetime | None


class EvidenceRestrictionOut(BaseModel):
    child_name: str
    person_name: str
    reason: RestrictionReason
    reference: str | None
    created_at: datetime
    created_by_name: str
    ended_at: datetime | None


class EvidenceEventOut(BaseModel):
    at: datetime
    kind: str
    child: str
    detail: str
    who: str


class EvidenceFlagOut(BaseModel):
    day: date
    child_name: str
    flags: list[str]
    signed_out_at: datetime | None
    register_collected_by: str | None
    released_at: datetime | None
    collector_name: str | None


class EvidenceOut(BaseModel):
    nursery_name: str
    start: date
    end: date
    child_name: str | None
    generated_at: datetime
    generated_by: str
    kpis: KpisOut
    collectors: list[EvidenceCollectorOut]
    restrictions: list[EvidenceRestrictionOut]
    events: list[EvidenceEventOut]
    flagged: list[EvidenceFlagOut]
    registers: list[date]
