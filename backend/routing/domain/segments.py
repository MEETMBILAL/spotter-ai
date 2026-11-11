"""Mileage ownership: every route mile belongs to exactly one segment / risk category.

Sampling assumption: a checkpoint's weather represents the stretch of route nearest to it,
i.e. its segment spans from the midpoint with the previous checkpoint to the midpoint with
the next one (first starts at mile 0, last ends at the destination). Segments therefore
tile [0, total] with no gaps or overlaps. This is an approximation, not continuous coverage.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from .risk import Risk


@dataclass(frozen=True)
class RiskSegment:
    checkpoint_index: int
    start_mi: float
    end_mi: float
    risk: Optional[Risk]  # None = weather unavailable

    @property
    def miles(self) -> float:
        return self.end_mi - self.start_mi


def build_segments(distances: Sequence[float], risks: Sequence[Optional[Risk]], total_miles: float) -> list[RiskSegment]:
    if len(distances) != len(risks) or not distances:
        raise ValueError("distances and risks must be equal-length and non-empty")
    if any(b <= a for a, b in zip(distances, distances[1:])):
        raise ValueError("checkpoint distances must be strictly increasing")
    if distances[0] < 0 or distances[-1] > total_miles + 1e-6:
        raise ValueError("checkpoint distances must lie within the route")
    bounds = [0.0] + [(a + b) / 2 for a, b in zip(distances, distances[1:])] + [float(total_miles)]
    return [RiskSegment(i, bounds[i], bounds[i + 1], r) for i, r in enumerate(risks)]


@dataclass(frozen=True)
class RouteRiskSummary:
    total_miles: float
    miles_by_risk: dict[Risk, float]
    unknown_miles: float

    @property
    def known_miles(self) -> float:
        return self.total_miles - self.unknown_miles

    @property
    def severe_miles(self) -> float:
        return self.miles_by_risk[Risk.SEVERE]

    @property
    def high_miles(self) -> float:
        return self.miles_by_risk[Risk.HIGH]

    @property
    def no_travel_miles(self) -> float:
        return self.miles_by_risk[Risk.NO_TRAVEL]

    @property
    def complete(self) -> bool:
        return self.unknown_miles <= 1e-9

    @property
    def average_risk(self) -> Optional[float]:
        """Mile-weighted mean of numeric risk (Low=0, Moderate=1, High=2, Severe=3, No Travel=4)
        over miles with known weather. Low and Moderate miles ARE included. Unknown miles are
        excluded (and reported separately). None if no mile has known weather."""
        if self.known_miles <= 1e-9:
            return None
        return sum(int(r) * m for r, m in self.miles_by_risk.items()) / self.known_miles

    def rounded_miles(self, decimals: int = 1) -> dict[str, float]:
        """Display rounding by largest remainder so the parts always sum to the rounded total."""
        scale = 10 ** decimals
        parts = {r.label: m for r, m in self.miles_by_risk.items()}
        parts["Unknown"] = self.unknown_miles
        target = round(self.total_miles * scale)
        floors = {k: int(v * scale) for k, v in parts.items()}
        short = target - sum(floors.values())
        order = sorted(parts, key=lambda k: parts[k] * scale - floors[k], reverse=True)
        for k in order[: max(short, 0)]:
            floors[k] += 1
        return {k: v / scale for k, v in floors.items()}


def summarize(segments: Sequence[RiskSegment]) -> RouteRiskSummary:
    by = {r: 0.0 for r in Risk}
    unknown = 0.0
    for s in segments:
        if s.risk is None:
            unknown += s.miles
        else:
            by[s.risk] += s.miles
    return RouteRiskSummary(sum(s.miles for s in segments), by, unknown)
