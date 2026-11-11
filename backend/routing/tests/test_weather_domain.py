import pytest
from routing.domain.weather import HourlySeries, sample_at

T0 = 1_800_000_000 - 1_800_000_000 % 3600


def series(wind=(10, 20, 30), rain=(0.1, 0.2, 0.3), snow=(0, 1, 2)):
    t = tuple(T0 + i * 3600 for i in range(len(wind)))
    return HourlySeries(t, tuple(wind), tuple(rain), tuple(snow))


def test_exact_hour():
    s = sample_at(series(), T0 + 3600)
    assert (s.wind_mph, s.rain_in_hr, s.snow_in_hr, s.status) == (20, 0.2, 1, "ok")


def test_wind_interpolated_rain_snow_use_hour_ending_at_or_after():
    s = sample_at(series(), T0 + 1800)       # halfway between hour 0 and 1
    assert s.wind_mph == pytest.approx(15)   # instantaneous -> interpolate
    assert s.rain_in_hr == 0.2 and s.snow_in_hr == 1  # preceding-hour sums -> hour ending at T0+1h, no interpolation


def test_not_covered_is_unavailable_not_low():
    assert sample_at(series(), T0 - 1).status == "unavailable"
    s = sample_at(series(), T0 + 3 * 3600)
    assert s.status == "unavailable" and s.reason == "forecast_not_covered" and s.wind_mph is None
    assert sample_at(None, T0).reason == "no_forecast_data"


def test_missing_values():
    s = sample_at(series(wind=(10, None, 30)), T0 + 1800)
    assert s.wind_mph is None and s.status == "partial"
    s = sample_at(series(wind=(None,) * 3, rain=(None,) * 3, snow=(None,) * 3), T0)
    assert s.status == "unavailable" and s.reason == "values_missing"
