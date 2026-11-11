"""Trip analysis orchestration. Business logic only - no Django views here."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from ..domain import ranking as rk
from ..domain.eta import arrival_time, time_profile
from ..domain.geo import (METERS_PER_MILE, build_checkpoints, corridor_points, cumulative_miles)
from ..domain.risk import Risk, assess_checkpoint
from ..domain.segments import build_segments, summarize
from ..domain.weather import sample_at
from ..providers.errors import NoRouteError, ProviderError

MAX_CHECKPOINTS_PER_ROUTE = 300
FORECAST_DAYS = 15  # Open-Meteo forecast horizon used (max 16 days incl. today)
NOT_TRUCK_WARNING = ("Routes are standard driving directions, not truck-specific: they do not account for "
                     "height, weight, axle or hazmat restrictions. ETAs exclude traffic, rest breaks and hours-of-service.")
REASON_TEXT = {
    "severe_miles": "it has the fewest Severe-risk miles",
    "high_miles": "it has the fewest High-risk miles",
    "average_risk": "it has the lowest average risk",
    "duration": "it has the shortest travel time",
    "data_completeness": "it has complete weather coverage",
    "tie": "it is tied on every criterion and was listed first by the routing provider",
}


class AnalysisInputError(ValueError):
    pass


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def risk_obj(r: Optional[Risk]) -> dict:
    return {"level": None if r is None else int(r), "label": "Unknown" if r is None else r.label}


def _r(v, n=3):
    return None if v is None else round(v, n)


def fetch_weather(weather, points, t_min: float, t_max: float, warnings: list, now: datetime):
    """Returns HourlySeries per point, or None entries (with a warning) - never fabricated data."""
    n = len(points)
    start = datetime.fromtimestamp(t_min, timezone.utc).date()
    end = datetime.fromtimestamp(t_max + 3600, timezone.utc).date()
    limit = (now + timedelta(days=FORECAST_DAYS)).date()
    if start > limit:
        warnings.append(f"Forecast data is only available about {FORECAST_DAYS} days ahead; "
                        "weather could not be assessed for this departure.")
        return [None] * n
    if end > limit:
        warnings.append(f"Part of the trip is beyond the {FORECAST_DAYS}-day forecast horizon; "
                        "those checkpoints have no weather data.")
        end = limit
    try:
        series = weather.get_hourly(points, start, end)
    except ProviderError as exc:
        warnings.append(f"Weather data unavailable: {exc.message}")
        return [None] * n
    for note in dict.fromkeys(n_ for s in series if s for n_ in s.notes):
        warnings.append(note)
    return series


def analyze_trip(*, origin: dict, destination: dict, departure: datetime, load_lb: float, interval: int,
                 directions, weather, now: Optional[datetime] = None) -> dict:
    now = now or datetime.now(timezone.utc)
    options = directions.get_routes((origin["lon"], origin["lat"]), (destination["lon"], destination["lat"]))
    if not options:
        raise NoRouteError("No drivable route was found between these locations")

    prepared = []
    for opt in options:
        miles = opt.distance_m / METERS_PER_MILE
        cum = cumulative_miles(opt.coords, miles)
        cps = build_checkpoints(opt.coords, cum, interval)
        if len(cps) > MAX_CHECKPOINTS_PER_ROUTE:
            raise AnalysisInputError("This route is too long for the selected interval; choose a larger interval.")
        times, method = time_profile(cum, opt.duration_s, opt.segment_durations_s)
        etas = [arrival_time(departure, cum, times, c.distance_miles) for c in cps]
        prepared.append((opt, miles, cps, etas, method))

    flat = [(c, e) for _, _, cps, etas, _ in prepared for c, e in zip(cps, etas)]
    warnings: list = [NOT_TRUCK_WARNING]
    if len(options) < 3:
        warnings.append(f"The routing provider returned {len(options)} route(s) for this trip, not 3. "
                        "Only genuine provider routes are shown; no alternatives were fabricated.")
    series = fetch_weather(weather, [(c.lat, c.lon) for c, _ in flat],
                           min(e.timestamp() for _, e in flat), max(e.timestamp() for _, e in flat), warnings, now)

    routes, candidates, pos = [], [], 0
    for i, (opt, miles, cps, etas, method) in enumerate(prepared):
        rid = f"route-{i + 1}"
        cp_out, risks = [], []
        for c, eta in zip(cps, etas):
            s = sample_at(series[pos], eta.timestamp())
            pos += 1
            a = assess_checkpoint(s.wind_mph, s.rain_in_hr, s.snow_in_hr, load_lb)
            risks.append(a.final)
            cp_out.append({
                "index": c.index, "distance_miles": round(c.distance_miles, 2),
                "lon": round(c.lon, 5), "lat": round(c.lat, 5), "eta": iso(eta),
                "is_origin": c.is_origin, "is_destination": c.is_destination,
                "weather": {"status": s.status, "reason": s.reason, "wind_mph": _r(s.wind_mph, 1),
                            "rain_in_hr": _r(s.rain_in_hr), "snow_in_hr": _r(s.snow_in_hr)},
                "risk": {"wind": risk_obj(a.wind), "rain": risk_obj(a.rain), "snow": risk_obj(a.snow),
                         "final": risk_obj(a.final), "complete": a.complete,
                         "load_override_applied": a.load_override_applied},
            })
        segs = build_segments([c.distance_miles for c in cps], risks, cps[-1].distance_miles)
        summ = summarize(segs)
        candidates.append(rk.RouteCandidate(rid, opt.duration_s, summ))
        rounded = summ.rounded_miles(1)
        routes.append({
            "id": rid, "name": f"Route {i + 1}", "distance_miles": round(miles, 2),
            "duration_s": round(opt.duration_s), "eta_method": method,
            "geometry": {"type": "LineString", "coordinates": [[round(x, 5), round(y, 5)] for x, y in opt.coords]},
            "checkpoints": cp_out,
            "segments": [{"checkpoint_index": s.checkpoint_index, "start_mi": round(s.start_mi, 2),
                          "end_mi": round(s.end_mi, 2), "risk": risk_obj(s.risk)} for s in segs],
            "summary": {
                "total_miles": round(summ.total_miles, 2), "miles_by_risk": rounded,
                "unknown_miles": round(summ.unknown_miles, 2),
                "average_risk": None if summ.average_risk is None else round(summ.average_risk, 3),
                "has_no_travel": summ.no_travel_miles > 1e-9, "data_complete": summ.complete,
            },
        })

    result = rk.rank_routes(candidates)
    by_id = {x.route_id: x for x in result.ranked}
    for r in routes:
        x = by_id[r["id"]]
        r["ranking"] = {"rank": x.rank, "eligible": x.eligible, "ineligible_reason": x.ineligible_reason,
                        "decided_by": x.decided_by, "recommended": r["id"] == result.recommended_id}
        if any(c["weather"]["status"] != "ok" for c in r["checkpoints"]):
            n = sum(c["weather"]["status"] != "ok" for c in r["checkpoints"])
            warnings.append(f"{r['name']}: {n} checkpoint(s) have incomplete weather data.")

    reasons = []
    if result.recommended_id:
        top = next(x for x in result.ranked if x.rank == 1)
        reasons.append("Selected because " + REASON_TEXT.get(top.decided_by, "it is the only eligible route")
                       if top.decided_by else "It is the only eligible route (others contain No Travel conditions or lack data).")
    rec = {"status": result.status, "message": result.message, "route_id": result.recommended_id,
           "reasons": reasons, "warnings": result.warnings}
    return {
        "trip": {"origin": origin, "destination": destination, "departure_time": iso(departure),
                 "load_lb": load_lb, "checkpoint_interval_miles": interval},
        "routes": routes, "recommendation": rec, "warnings": list(dict.fromkeys(warnings)),
        "meta": {"routes_returned": len(routes), "routes_requested": 3, "truck_specific_routing": False,
                 "routing_provider": "mapbox", "weather_provider": "open-meteo",
                 "units": {"wind": "mph", "rain": "in/hr", "snow": "in/hr", "distance": "mi", "duration": "s"}},
    }


HEATMAP_HOURS = 48


def build_heatmap(*, route, route_id: str, departure: datetime, weather, now: Optional[datetime] = None) -> dict:
    now = now or datetime.now(timezone.utc)
    miles = route.distance_m / METERS_PER_MILE
    cum = cumulative_miles(route.coords, miles)
    pts = corridor_points(route.coords, cum)
    t0 = departure.timestamp()
    warnings: list = []
    series = fetch_weather(weather, [(lat, lon) for lon, lat in pts], t0, t0 + HEATMAP_HOURS * 3600, warnings, now)
    frames = []
    for h in range(HEATMAP_HOURS + 1):
        t = t0 + h * 3600
        samples = [sample_at(s, t) for s in series]
        risks = [assess_checkpoint(s.wind_mph, s.rain_in_hr, s.snow_in_hr, 0).final for s in samples]
        frames.append({
            "hour": h, "time": iso(departure + timedelta(hours=h)),
            "wind_mph": [_r(s.wind_mph, 1) for s in samples], "rain_in_hr": [_r(s.rain_in_hr) for s in samples],
            "snow_in_hr": [_r(s.snow_in_hr) for s in samples],
            "risk": [None if r is None else int(r) for r in risks],
            "available": any(r is not None for r in risks),
        })
    return {"route_id": route_id, "departure_time": iso(departure),
            "points": [[round(x, 4), round(y, 4)] for x, y in pts], "frames": frames,
            "unavailable_hours": [f["hour"] for f in frames if not f["available"]],
            "warnings": warnings,
            "note": "Regional weather around the route corridor (no truck-load rules). "
                    "Checkpoint risk shown on routes is calculated separately for your load."}
