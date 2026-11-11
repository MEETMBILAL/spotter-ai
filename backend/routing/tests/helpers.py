"""Deterministic fixtures: mocked provider payloads (NOT real API data)."""
from datetime import datetime, timedelta, timezone

H = 3600


def hourly_payload(t0, hours=72, wind=10.0, rain=0.0, showers=0.0, snow=0.0, units=None, step=H):
    times = [t0 + i * step for i in range(hours)]
    f = (lambda v: v(i) if callable(v) else v)
    return {
        "hourly_units": units or {"wind_speed_10m": "mp/h", "rain": "inch", "showers": "inch", "snowfall": "inch"},
        "hourly": {
            "time": times,
            "wind_speed_10m": [wind(i) if callable(wind) else wind for i in range(hours)],
            "rain": [rain(i) if callable(rain) else rain for i in range(hours)],
            "showers": [showers] * hours if showers is not None else [None] * hours,
            "snowfall": [snow(i) if callable(snow) else snow for i in range(hours)],
        },
    }


def future_start(days=1):
    d = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) + timedelta(days=days)
    return d


def line_route(n=5, dist_mi=200, dur_s=14400, lat=40.0, lon0=-100.0, dlon=1.0):
    """A straight east-west route as a Mapbox-shaped route dict."""
    coords = [[lon0 + i * dlon, lat] for i in range(n)]
    return {"distance": dist_mi * 1609.344, "duration": dur_s, "geometry": {"coordinates": coords},
            "legs": [{"annotation": {"duration": [dur_s / (n - 1)] * (n - 1)}}]}


TRIP = {"origin": {"label": "A", "lon": -100.0, "lat": 40.0}, "destination": {"label": "B", "lon": -96.0, "lat": 40.0},
        "load_lb": 35000, "checkpoint_interval_miles": 50}
