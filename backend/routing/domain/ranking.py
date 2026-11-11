"""Route ranking. Lexicographic: severe miles, high miles, average risk, duration.
No weighted score. No Travel mileage is an eligibility gate, not a ranking input."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence

from .segments import RouteRiskSummary

NO_SAFE_ROUTE_MESSAGE = "No Safe Route Available"
INSUFFICIENT_DATA_MESSAGE = "Weather data unavailable - route safety cannot be assessed"
_FIELDS = ("data_completeness", "severe_miles", "high_miles", "average_risk", "duration")


@dataclass(frozen=True)
class RouteCandidate:
    route_id: str
    duration_s: float
    summary: RouteRiskSummary


@dataclass(frozen=True)
class RankedRoute:
    route_id: str
    rank: Optional[int]            # None for ineligible routes
    eligible: bool
    ineligible_reason: Optional[str]
    decided_by: Optional[str] = None  # which key separated this route from the next-ranked one


@dataclass(frozen=True)
class RankingResult:
    ranked: list[RankedRoute]
    recommended_id: Optional[str]
    status: str                    # recommended | recommended_partial_data | no_safe_route | insufficient_data
    message: str
    warnings: list[str] = field(default_factory=list)


def _key(c: RouteCandidate) -> tuple:
    s = c.summary
    avg = s.average_risk
    return (
        0 if s.complete else 1,                 # data-quality tier (see ASSUMPTIONS.md)
        round(s.severe_miles, 3),
        round(s.high_miles, 3),
        round(avg, 6) if avg is not None else float("inf"),
        round(c.duration_s, 3),
    )


def _ineligible_reason(c: RouteCandidate) -> Optional[str]:
    if c.summary.no_travel_miles > 1e-9:
        return f"Contains {c.summary.no_travel_miles:.1f} No Travel miles"
    if c.summary.known_miles <= 1e-9:
        return "No weather data available for this route"
    return None


def rank_routes(candidates: Sequence[RouteCandidate]) -> RankingResult:
    eligible = sorted((c for c in candidates if _ineligible_reason(c) is None), key=_key)  # stable
    blocked = sorted((c for c in candidates if _ineligible_reason(c) is not None),
                     key=lambda c: (c.summary.no_travel_miles, *_key(c)))

    ranked: list[RankedRoute] = []
    for i, c in enumerate(eligible):
        decided = None
        if i + 1 < len(eligible):
            a, b = _key(c), _key(eligible[i + 1])
            decided = next((f for f, x, y in zip(_FIELDS, a, b) if x != y), "tie")
        ranked.append(RankedRoute(c.route_id, i + 1, True, None, decided))
    ranked += [RankedRoute(c.route_id, None, False, _ineligible_reason(c)) for c in blocked]

    if not eligible:
        if candidates and all(c.summary.no_travel_miles <= 1e-9 for c in candidates):
            # Nothing is blocked; we simply have no weather. Do not claim "no safe route".
            return RankingResult(ranked, None, "insufficient_data", INSUFFICIENT_DATA_MESSAGE)
        return RankingResult(ranked, None, "no_safe_route", NO_SAFE_ROUTE_MESSAGE)

    best = eligible[0]
    warnings = []
    if not best.summary.complete:
        warnings.append(f"{best.summary.unknown_miles:.1f} mi of this route has no weather forecast; "
                        "it cannot be confirmed fully safe.")
    status = "recommended" if best.summary.complete else "recommended_partial_data"
    return RankingResult(ranked, best.route_id, status, "Safest eligible route", warnings)
