"""Matching hourly forecast series to arbitrary arrival instants (pure, provider-agnostic).

Series semantics (Open-Meteo hourly, verified against its docs):
  * wind_mph : INSTANTANEOUS value at the stamped hour  -> linearly interpolated between hours.
  * rain_in / snow_in : SUM OVER THE PRECEDING HOUR (inches). At a 1-hour step this equals in/hr.
    For an instant t in (T-1h, T] the applicable interval is the one ending at T -> value at T,
    NOT interpolated (interpolating an interval total would be meaningless).
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from typing import Optional, Sequence


@dataclass(frozen=True)
class HourlySeries:
    times: tuple          # epoch seconds (UTC), ascending
    wind_mph: tuple       # Optional[float] per time
    rain_in: tuple        # Optional[float] per time (preceding-hour sum == in/hr), None if not valid
    snow_in: tuple
    notes: tuple = ()     # data-quality notes surfaced to the user


@dataclass(frozen=True)
class WeatherSample:
    status: str           # "ok" | "partial" | "unavailable"
    wind_mph: Optional[float]
    rain_in_hr: Optional[float]
    snow_in_hr: Optional[float]
    reason: Optional[str] = None


_UNAVAILABLE = lambda reason: WeatherSample("unavailable", None, None, None, reason)  # noqa: E731


def sample_at(series: Optional[HourlySeries], t: float) -> WeatherSample:
    if series is None or not series.times:
        return _UNAVAILABLE("no_forecast_data")
    times = series.times
    if t < times[0] or t > times[-1]:
        return _UNAVAILABLE("forecast_not_covered")
    lo = bisect_right(times, t) - 1
    hi = bisect_left(times, t)
    if times[lo] == t:
        wind = series.wind_mph[lo]
    else:
        a, b = series.wind_mph[lo], series.wind_mph[hi]
        wind = None if a is None or b is None else a + (b - a) * (t - times[lo]) / (times[hi] - times[lo])
    rain, snow = series.rain_in[hi], series.snow_in[hi]
    got = sum(v is not None for v in (wind, rain, snow))
    if got == 3:
        return WeatherSample("ok", wind, rain, snow)
    if got == 0:
        return _UNAVAILABLE("values_missing")
    return WeatherSample("partial", wind, rain, snow, "some_values_missing")
