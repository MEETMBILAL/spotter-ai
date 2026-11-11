"""Checkpoint ETAs from provider durations. No traffic, HOS, rest stops or truck speeds."""
from __future__ import annotations

from bisect import bisect_right
from datetime import datetime, timedelta
from typing import Optional, Sequence


def time_profile(cum_miles: Sequence[float], total_duration_s: float,
                 segment_durations_s: Optional[Sequence[float]] = None) -> tuple[list[float], str]:
    """Cumulative seconds at each vertex, plus method: 'segment' or 'proportional'.
    Segment durations (Mapbox annotations) are rescaled so they sum to the route duration."""
    if total_duration_s <= 0:
        raise ValueError("Route duration must be positive")
    n = len(cum_miles) - 1
    if segment_durations_s is not None and len(segment_durations_s) == n \
            and all(s >= 0 for s in segment_durations_s) and sum(segment_durations_s) > 0:
        k = total_duration_s / sum(segment_durations_s)
        t = [0.0]
        for s in segment_durations_s:
            t.append(t[-1] + s * k)
        return t, "segment"
    total = cum_miles[-1]
    return [c / total * total_duration_s for c in cum_miles], "proportional"


def seconds_at_distance(cum_miles: Sequence[float], times_s: Sequence[float], d: float) -> float:
    d = min(max(d, 0.0), cum_miles[-1])
    i = min(bisect_right(cum_miles, d) - 1, len(cum_miles) - 2)
    seg = cum_miles[i + 1] - cum_miles[i]
    f = 0.0 if seg <= 0 else (d - cum_miles[i]) / seg
    return times_s[i] + f * (times_s[i + 1] - times_s[i])


def arrival_time(departure: datetime, cum_miles, times_s, d: float) -> datetime:
    if departure.tzinfo is None:
        raise ValueError("departure must be timezone-aware")
    return departure + timedelta(seconds=seconds_at_distance(cum_miles, times_s, d))
