"""Keeping the door check at the nursery.

A nursery can ask for collectors to be checked only on its premises: the
phone doing the check sends its position, and a check from outside the
fence, or with no position at all, is refused and recorded.

**This is an operational control, not a security one.** The position comes
from the browser's Geolocation API, so it comes from the device, and a device
can lie. What it stops is the ordinary case: a check made from home, or from a
phone carried off-site with the door screen still open. It should never be
described to a nursery as a guarantee.

Two decisions:

* **The benefit of the doubt goes to the person at the door.** Phone GPS indoors
  is often ±50 metres or worse, so a check passes when the device's own
  uncertainty circle reaches the fence, not only when the reported point does.
* **No position is a refusal, when a fence is set.** Otherwise declining the
  browser's location prompt would bypass the fence.

Distances use the haversine formula; at the scale of a nursery the error is
centimetres, far below the precision of any input.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

EARTH_RADIUS_M = 6_371_008.8

# Tighter than 50 m rejects people standing inside it, given phone GPS error;
# wider than 5 km is not a nursery.
MIN_RADIUS_M = 50
MAX_RADIUS_M = 5_000
DEFAULT_RADIUS_M = 150

# A fix this vague is a cell-tower guess that would satisfy any fence.
MAX_USABLE_ACCURACY_M = 10_000


class Verdict(StrEnum):
    INSIDE = "inside"
    OUTSIDE = "outside"
    UNKNOWN = "unknown"
    NOT_FENCED = "not_fenced"


@dataclass(frozen=True)
class Fence:
    latitude: float
    longitude: float
    radius_m: int


@dataclass(frozen=True)
class Position:
    latitude: float
    longitude: float
    accuracy_m: float = 0.0


@dataclass(frozen=True)
class Result:
    verdict: Verdict
    distance_m: float | None = None

    @property
    def allowed(self) -> bool:
        return self.verdict in (Verdict.INSIDE, Verdict.NOT_FENCED)


def distance_m(a: Position | Fence, b: Position | Fence) -> float:
    lat1, lon1 = math.radians(a.latitude), math.radians(a.longitude)
    lat2, lon2 = math.radians(b.latitude), math.radians(b.longitude)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(min(1.0, h)))


def check(fence: Fence | None, position: Position | None) -> Result:
    if fence is None:
        return Result(Verdict.NOT_FENCED)
    if position is None or position.accuracy_m > MAX_USABLE_ACCURACY_M:
        return Result(Verdict.UNKNOWN)
    measured = distance_m(fence, position)
    nearest_possible = measured - max(position.accuracy_m, 0.0)
    verdict = Verdict.INSIDE if nearest_possible <= fence.radius_m else Verdict.OUTSIDE
    return Result(verdict, distance_m=measured)


def valid_coordinates(latitude: float, longitude: float) -> bool:
    """Real coordinates, and not 0,0, which a device with no fix sometimes sends."""
    if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
        return False
    return not (abs(latitude) < 1e-7 and abs(longitude) < 1e-7)
