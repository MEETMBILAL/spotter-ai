# Assumptions & Approximations (Batch 1: domain core)

## Risk engine (`routing/domain/risk.py`)
- Thresholds exactly as specified; intervals are contiguous. Rain 1.00 and snow 3.0 are inclusive Severe.
- Values are rounded to 6 decimals before comparison so unit-conversion float noise cannot flip a boundary.
- Missing/NaN weather is **unknown** (`None`), never Low. A checkpoint with partial data takes the worst *known*
  component and is flagged `complete=False`. Load overrides apply whenever wind is known.
- Load comparisons are strict `>`; overrides can only raise risk, never lower it.

## Checkpoints & mileage ownership
- Checkpoints: mile 0 (origin), every N miles along the actual polyline, destination last (never duplicated).
  Including the origin is a design choice (weather at departure matters).
- Polyline length is rescaled to the provider-reported distance so totals match the routing API.
- A checkpoint's weather is assumed to represent the stretch nearest to it: its segment runs from the midpoint with
  the previous checkpoint to the midpoint with the next (first starts at 0, last ends at the destination).
  Every mile is owned by exactly one segment. This is a sampling approximation, not continuous coverage.

## Average risk
Mile-weighted mean of Low=0, Moderate=1, High=2, Severe=3, No Travel=4 over miles with known weather
(Low and Moderate included). Unknown miles are excluded and reported separately.

## ETA
Segment durations (Mapbox annotations) when available, rescaled to the route total; otherwise proportional
interpolation by distance. No traffic, truck speeds, rest breaks or hours-of-service.

## Ranking
Lexicographic: severe miles, high miles, average risk, duration. Any No Travel mileage => ineligible (gate, not weight).
**Decision for your review:** routes with *missing* weather for part of the route are sorted *after* routes with
complete data (a data-quality tier placed before the four specified keys), because otherwise a route with no forecast
would look like 0 severe/high miles and win. A recommended route with gaps is labelled `recommended_partial_data`.
A route with zero known weather miles is ineligible.

## Not yet implemented
Mapbox/Open-Meteo providers, API endpoints, heatmap, frontend (see PROJECT_STATE.md).

---
# Batch 2-3 additions

## Weather variables (Open-Meteo `/v1/forecast`, hourly) - verified against Open-Meteo docs
- `wind_speed_10m`: INSTANTANEOUS at the stamped hour (requested in mph). Interpolated linearly to the arrival instant.
- `rain`, `showers`, `snowfall`: PRECEDING-HOUR SUMS (requested in inches). At a verified 3600 s step, sum over 1 h = in/hr.
  Not interpolated: an arrival in (T-1h, T] uses the value stamped T (the hour that contains it).
- Rain intensity = rain + showers. If the model returns no showers series, rain only is used and a warning is shown.
- Snow intensity is derived ONLY if consecutive timestamps are exactly 3600 s apart; otherwise rain/snow are "unavailable" (never 0).
- Response `hourly_units` are checked and converted (km/h, m/s, kn, mm, cm supported); unknown units reject the response.
- Timestamps requested as unix epoch (UTC): no timezone ambiguity. Wind gusts are not used (spec says wind speed).
- Coordinates are rounded to 0.01 deg (~1.1 km) for requests/caching; up to 50 locations per request; 30-min cache.
- Forecast horizon capped at 15 days; arrivals beyond coverage are "unavailable", not guessed.

## Routing
Mapbox `driving` profile with `alternatives=true` (max 3 routes). Exact duplicates dropped; nothing is synthesised.
NOT truck-specific: ignores height/weight/axle/hazmat restrictions. ETAs exclude traffic, rest breaks, hours-of-service.
Segment durations (annotations) are used when counts match the geometry; else proportional by distance.

## Unknown weather
Unknown is distinct from Low. A provider failure yields Unknown checkpoints and status `insufficient_data` (never "safe").
Statuses: recommended | recommended_partial_data | no_safe_route | insufficient_data.

## Heatmap
Corridor points every ~20 mi along the route at lateral offsets -15/0/+15 mi, deduped on a 0.05 deg grid, max 99.
Colours show weather-only risk from the same backend risk engine with no load rules; checkpoint risk (load-aware) is separate.
Intensity scaling in the UI (value / No-Travel threshold) is visual only. Points with no data are omitted, not drawn as calm.
Heatmap re-requests directions via the 15-min cache, so route_index is stable within that window.

## Limits
Max 300 checkpoints per route (use a larger interval for very long trips). Rate limiting is per-process (locmem cache).
