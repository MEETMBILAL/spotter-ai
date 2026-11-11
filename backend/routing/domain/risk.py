"""Centralised, pure risk engine. The ONLY place threshold logic lives."""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import IntEnum
from typing import Optional


class Risk(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4

    @property
    def label(self) -> str:
        return {0: "Low", 1: "Moderate", 2: "High", 3: "Severe", 4: "No Travel"}[int(self)]


# Upper bounds for LOW, MODERATE, HIGH, SEVERE as (limit, inclusive).
# Anything above the last bound is NO_TRAVEL. Intervals are contiguous by construction.
WIND_BOUNDS = ((25, False), (35, False), (45, False), (55, False))          # mph
RAIN_BOUNDS = ((0.10, False), (0.25, False), (0.50, False), (1.00, True))   # in/hr
SNOW_BOUNDS = ((0.5, False), (1.0, False), (2.0, False), (3.0, True))       # in/hr

_LEVELS = (Risk.LOW, Risk.MODERATE, Risk.HIGH, Risk.SEVERE)
_PRECISION = 6  # absorbs unit-conversion float noise (e.g. 0.25000000000000006)


def _clean(value: Optional[float]) -> Optional[float]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if value < 0:
        raise ValueError(f"Weather intensity cannot be negative: {value}")
    return round(float(value), _PRECISION)


def _classify(value: Optional[float], bounds) -> Optional[Risk]:
    v = _clean(value)
    if v is None:
        return None  # unavailable is NOT low
    for level, (limit, inclusive) in zip(_LEVELS, bounds):
        if v < limit or (inclusive and v == limit):
            return level
    return Risk.NO_TRAVEL


def classify_wind(mph: Optional[float]) -> Optional[Risk]:
    return _classify(mph, WIND_BOUNDS)


def classify_rain(in_per_hr: Optional[float]) -> Optional[Risk]:
    return _classify(in_per_hr, RAIN_BOUNDS)


def classify_snow(in_per_hr: Optional[float]) -> Optional[Risk]:
    return _classify(in_per_hr, SNOW_BOUNDS)


def apply_load_override(wind_mph: Optional[float], load_lb: float, current: Risk) -> Risk:
    """Truck-load overrides. Load comparisons are strictly greater-than."""
    w = _clean(wind_mph)
    if w is None:
        return current
    if w >= 55:
        return Risk.NO_TRAVEL
    if w >= 45 and load_lb > 30_000:
        return Risk.NO_TRAVEL
    if w >= 35 and load_lb > 40_000:
        return max(current, Risk.SEVERE)
    return current


@dataclass(frozen=True)
class CheckpointRisk:
    wind: Optional[Risk]
    rain: Optional[Risk]
    snow: Optional[Risk]
    final: Optional[Risk]          # None => no weather data at all
    complete: bool                 # False if any component was unavailable
    load_override_applied: bool


def assess_checkpoint(
    wind_mph: Optional[float],
    rain_in_hr: Optional[float],
    snow_in_hr: Optional[float],
    load_lb: float,
) -> CheckpointRisk:
    if load_lb is None or not math.isfinite(load_lb) or load_lb < 0:
        raise ValueError("load_lb must be a finite, non-negative number")
    wind, rain, snow = classify_wind(wind_mph), classify_rain(rain_in_hr), classify_snow(snow_in_hr)
    known = [r for r in (wind, rain, snow) if r is not None]
    if not known:
        return CheckpointRisk(wind, rain, snow, None, False, False)
    base = max(known)
    final = apply_load_override(wind_mph, load_lb, base)
    return CheckpointRisk(wind, rain, snow, final, len(known) == 3, final != base)
