"""Open-Meteo hourly forecast provider.

Requested variables: wind_speed_10m (instant), rain + showers + snowfall (preceding-hour sums).
Units are requested as mph / inch and the response's `hourly_units` are VERIFIED and converted if
they differ. Rain/snow are only treated as in/hr when consecutive timestamps are exactly 3600 s apart;
otherwise they are reported unavailable (never guessed, never zero).
"""
from __future__ import annotations

import logging
import math
from datetime import date
from typing import Optional, Sequence

import requests
from django.core.cache import cache as default_cache

from ..domain.weather import HourlySeries
from .errors import ProviderResponseError, ProviderTimeout, ProviderUnavailable

log = logging.getLogger(__name__)
URL = "https://api.open-meteo.com/v1/forecast"
CHUNK = 50
TTL_S = 1800
WIND_TO_MPH = {"mp/h": 1.0, "mph": 1.0, "km/h": 0.621371, "m/s": 2.236936, "kn": 1.150779}
PRECIP_TO_IN = {"inch": 1.0, "in": 1.0, "mm": 1 / 25.4, "cm": 1 / 2.54}


def _factor(table: dict, unit: Optional[str], var: str) -> float:
    if unit not in table:
        raise ProviderResponseError(f"Open-Meteo returned an unknown unit {unit!r} for {var}")
    return table[unit]


def _convert(values: Sequence, factor: float, n: int, var: str) -> list:
    if not isinstance(values, list) or len(values) != n:
        raise ProviderResponseError(f"Open-Meteo series {var} has the wrong length")
    out = []
    for v in values:
        ok = isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0
        out.append(v * factor if ok else None)
    return out


def parse_location(loc: dict) -> HourlySeries:
    try:
        h, units = loc["hourly"], loc.get("hourly_units", {})
        times = h["time"]
        if not isinstance(times, list) or not times or not all(isinstance(t, int) for t in times):
            raise ProviderResponseError("Open-Meteo timestamps are not epoch seconds")
        if any(b <= a for a, b in zip(times, times[1:])):
            raise ProviderResponseError("Open-Meteo timestamps are not ascending")
        n, notes = len(times), []
        wind = _convert(h["wind_speed_10m"], _factor(WIND_TO_MPH, units.get("wind_speed_10m"), "wind"), n, "wind")
        rain = _convert(h["rain"], _factor(PRECIP_TO_IN, units.get("rain"), "rain"), n, "rain")
        snow = _convert(h["snowfall"], _factor(PRECIP_TO_IN, units.get("snowfall"), "snowfall"), n, "snowfall")
        showers_raw = h.get("showers")
        if isinstance(showers_raw, list) and any(v is not None for v in showers_raw):
            sh = _convert(showers_raw, _factor(PRECIP_TO_IN, units.get("showers"), "showers"), n, "showers")
            rain = [None if a is None or b is None else a + b for a, b in zip(rain, sh)]
        else:
            notes.append("Model provides no showers variable; rain intensity excludes convective showers.")
        if any(b - a != 3600 for a, b in zip(times, times[1:])):
            notes.append("Forecast is not hourly; rain/snow intensity cannot be derived and is unavailable.")
            rain, snow = [None] * n, [None] * n
        return HourlySeries(tuple(times), tuple(wind), tuple(rain), tuple(snow), tuple(notes))
    except KeyError as exc:
        raise ProviderResponseError(f"Open-Meteo response is missing {exc}") from None


class OpenMeteoClient:
    def __init__(self, timeout: float = 10.0, session=None, cache=None):
        self.timeout = timeout
        self.session = session or requests.Session()
        self.cache = cache or default_cache

    @staticmethod
    def round_point(lat: float, lon: float) -> tuple:
        return (round(lat, 2), round(lon, 2))  # ~1.1 km; far finer than model grids, enables cache hits

    def get_hourly(self, points: Sequence[tuple], start: date, end: date) -> list:
        """points: [(lat, lon)]. Returns HourlySeries aligned with `points`."""
        keys = [self.round_point(*p) for p in points]
        found: dict = {}
        missing = []
        for k in dict.fromkeys(keys):
            hit = self.cache.get(f"om:v1:{k[0]}:{k[1]}:{start}:{end}")
            if hit is not None:
                found[k] = hit
            else:
                missing.append(k)
        for i in range(0, len(missing), CHUNK):
            chunk = missing[i:i + CHUNK]
            for k, series in zip(chunk, self._fetch(chunk, start, end)):
                found[k] = series
                self.cache.set(f"om:v1:{k[0]}:{k[1]}:{start}:{end}", series, TTL_S)
        return [found[k] for k in keys]

    def _fetch(self, chunk: list, start: date, end: date) -> list:
        params = {
            "latitude": ",".join(str(k[0]) for k in chunk),
            "longitude": ",".join(str(k[1]) for k in chunk),
            "hourly": "wind_speed_10m,rain,showers,snowfall",
            "wind_speed_unit": "mph", "precipitation_unit": "inch",
            "timeformat": "unixtime", "timezone": "GMT",
            "start_date": start.isoformat(), "end_date": end.isoformat(),
        }
        try:
            r = self.session.get(URL, params=params, timeout=self.timeout)
        except requests.Timeout:
            raise ProviderTimeout("Open-Meteo request timed out") from None
        except requests.RequestException as exc:
            log.warning("Open-Meteo request failed: %s", type(exc).__name__)
            raise ProviderUnavailable("Could not reach Open-Meteo") from None
        try:
            data = r.json()
        except ValueError:
            raise ProviderResponseError("Open-Meteo returned invalid JSON") from None
        if r.status_code >= 400:
            reason = data.get("reason") if isinstance(data, dict) else None
            raise ProviderUnavailable(f"Open-Meteo rejected the request: {reason or r.status_code}")
        results = data if isinstance(data, list) else [data]
        if len(results) != len(chunk):
            raise ProviderResponseError("Open-Meteo returned an unexpected number of locations")
        return [parse_location(x) for x in results]
