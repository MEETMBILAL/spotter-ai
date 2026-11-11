"""Geometry along the real route polyline. Coordinates are GeoJSON order: (lon, lat)."""
from __future__ import annotations

import math
from bisect import bisect_right
from dataclasses import dataclass
from typing import Sequence

EARTH_RADIUS_MI = 3958.7613
METERS_PER_MILE = 1609.344
ALLOWED_INTERVALS = (10, 25, 50)
_EPS = 1e-6

Coord = tuple[float, float]


def haversine_miles(a: Coord, b: Coord) -> float:
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_MI * math.asin(min(1.0, math.sqrt(h)))


def cumulative_miles(coords: Sequence[Coord], target_total_miles: float | None = None) -> list[float]:
    """Cumulative distance at each vertex. If target_total_miles is given, distances are
    scaled so the polyline length equals the provider-reported route distance."""
    if len(coords) < 2:
        raise ValueError("Route geometry needs at least 2 coordinates")
    cum = [0.0]
    for a, b in zip(coords, coords[1:]):
        cum.append(cum[-1] + haversine_miles(a, b))
    if cum[-1] <= 0:
        raise ValueError("Route geometry has zero length")
    if target_total_miles is not None:
        if target_total_miles <= 0:
            raise ValueError("Route distance must be positive")
        k = target_total_miles / cum[-1]
        cum = [c * k for c in cum]
    return cum


def point_at_distance(coords: Sequence[Coord], cum: Sequence[float], d: float) -> Coord:
    d = min(max(d, 0.0), cum[-1])
    i = min(bisect_right(cum, d) - 1, len(coords) - 2)
    seg = cum[i + 1] - cum[i]
    t = 0.0 if seg <= 0 else (d - cum[i]) / seg
    return (coords[i][0] + t * (coords[i + 1][0] - coords[i][0]),
            coords[i][1] + t * (coords[i + 1][1] - coords[i][1]))


def checkpoint_distances(total_miles: float, interval: int) -> list[float]:
    """[0, interval, 2*interval, ..., total]. Destination is always last, never duplicated."""
    if interval not in ALLOWED_INTERVALS:
        raise ValueError(f"interval must be one of {ALLOWED_INTERVALS}")
    if total_miles <= 0:
        raise ValueError("total_miles must be positive")
    out = [0.0]
    k = 1
    while k * interval < total_miles - _EPS:
        out.append(float(k * interval))
        k += 1
    out.append(float(total_miles))
    return out


@dataclass(frozen=True)
class Checkpoint:
    index: int
    distance_miles: float
    lon: float
    lat: float
    is_origin: bool
    is_destination: bool


def build_checkpoints(coords: Sequence[Coord], cum: Sequence[float], interval: int) -> list[Checkpoint]:
    dists = checkpoint_distances(cum[-1], interval)
    last = len(dists) - 1
    cps = []
    for i, d in enumerate(dists):
        lon, lat = point_at_distance(coords, cum, d)
        cps.append(Checkpoint(i, d, lon, lat, i == 0, i == last))
    return cps


def bearing_deg(a: Coord, b: Coord) -> float:
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    y = math.sin(lon2 - lon1) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lon2 - lon1)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def offset_point(p: Coord, bearing: float, miles: float) -> Coord:
    lon1, lat1, brg = math.radians(p[0]), math.radians(p[1]), math.radians(bearing)
    ang = miles / EARTH_RADIUS_MI
    lat2 = math.asin(math.sin(lat1) * math.cos(ang) + math.cos(lat1) * math.sin(ang) * math.cos(brg))
    lon2 = lon1 + math.atan2(math.sin(brg) * math.sin(ang) * math.cos(lat1),
                             math.cos(ang) - math.sin(lat1) * math.sin(lat2))
    return (((math.degrees(lon2) + 540) % 360) - 180, math.degrees(lat2))


def corridor_points(coords: Sequence[Coord], cum: Sequence[float],
                    offsets_miles: Sequence[float] = (-15.0, 0.0, 15.0),
                    max_points: int = 99, grid_deg: float = 0.05) -> list[Coord]:
    """Weather sample points along the route plus lateral offsets (perpendicular to travel).
    Near-duplicates (same grid cell) are dropped; the count never exceeds max_points."""
    total = cum[-1]
    n_along = max(2, min(max_points // len(offsets_miles), math.ceil(total / 20) + 1))
    seen, out = set(), []
    delta = min(1.0, total / 100)
    for i in range(n_along):
        d = total * i / (n_along - 1)
        p = point_at_distance(coords, cum, d)
        brg = bearing_deg(point_at_distance(coords, cum, d - delta), point_at_distance(coords, cum, d + delta))
        for off in offsets_miles:
            q = p if off == 0 else offset_point(p, brg + (90 if off > 0 else -90), abs(off))
            if not (-90 <= q[1] <= 90):
                continue
            key = (round(q[1] / grid_deg), round(q[0] / grid_deg))
            if key not in seen:
                seen.add(key)
                out.append(q)
    return out[:max_points]
