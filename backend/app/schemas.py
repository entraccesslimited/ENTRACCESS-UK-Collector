"""What the API accepts and returns."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import CheckMethod, CheckResult, CollectorKind, HandoverOutcome, Role


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SignIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class Me(Out):
    id: uuid.UUID
    email: str
    full_name: str
    role: Role
    nursery_name: str


class ChildOut(Out):
    id: uuid.UUID
    full_name: str
    room: str | None
    active: bool


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


class PassOut(BaseModel):
    """What a parent shares with the collector."""

    authorisation_id: uuid.UUID
    token: str
    code_today: str = Field(description="Six digits, good today only, in the nursery's time.")
    share_url: str
    status: CheckResult


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


class DecisionIn(BaseModel):
    release: bool
    reason: str | None = Field(default=None, max_length=500)


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
    occurred_at: datetime


class DoorCheckOut(BaseModel):
    id: uuid.UUID
    checked_at: datetime
    method: CheckMethod
    result: CheckResult
    child_name: str | None
    collector_name: str | None
    staff_name: str
    distance_m: float | None = None


class TodayOut(BaseModel):
    released: int
    refused: int
    exceptions: int
    active_collectors: int


class ChildIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    room: str | None = Field(default=None, max_length=80)


class PersonIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=200)
    phone: str | None = Field(default=None, max_length=40)
    role: Role
    password: str = Field(min_length=10, max_length=200)


class PersonOut(Out):
    id: uuid.UUID
    email: str
    full_name: str
    phone: str | None
    role: Role
    active: bool


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
