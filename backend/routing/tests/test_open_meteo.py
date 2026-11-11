from datetime import date
import pytest
import requests
import responses
from routing.providers.errors import ProviderResponseError, ProviderTimeout, ProviderUnavailable
from routing.providers.open_meteo import URL, OpenMeteoClient, parse_location
from .helpers import hourly_payload

D = date(2026, 11, 12)
T0 = 1_800_000_000 - 1_800_000_000 % 3600


def test_parse_units_and_rain_includes_showers():
    s = parse_location(hourly_payload(T0, 3, wind=30, rain=0.1, showers=0.05, snow=0.4))
    assert s.wind_mph[0] == 30 and s.rain_in[0] == pytest.approx(0.15) and s.snow_in[0] == 0.4 and not s.notes


def test_unit_conversion_when_response_units_differ():
    units = {"wind_speed_10m": "km/h", "rain": "mm", "showers": "mm", "snowfall": "cm"}
    s = parse_location(hourly_payload(T0, 2, wind=100, rain=25.4, showers=0, snow=2.54, units=units))
    assert s.wind_mph[0] == pytest.approx(62.1371) and s.rain_in[0] == pytest.approx(1.0) and s.snow_in[0] == pytest.approx(1.0)


def test_unknown_unit_rejected():
    with pytest.raises(ProviderResponseError):
        parse_location(hourly_payload(T0, 2, units={"wind_speed_10m": "furlongs", "rain": "inch", "snowfall": "inch"}))


def test_non_hourly_step_makes_rain_snow_unavailable_not_zero():
    s = parse_location(hourly_payload(T0, 4, step=3 * 3600, rain=0.3, snow=1.0))
    assert all(v is None for v in s.rain_in + s.snow_in) and s.wind_mph[0] == 10 and s.notes


def test_missing_or_invalid_values_are_none():
    p = hourly_payload(T0, 3)
    p["hourly"]["snowfall"] = [None, -1, float("nan")]
    s = parse_location(p)
    assert s.snow_in == (None, None, None)


def test_showers_absent_falls_back_with_note():
    s = parse_location(hourly_payload(T0, 2, showers=None, rain=0.2))
    assert s.rain_in[0] == 0.2 and any("showers" in n for n in s.notes)


def test_bad_structure():
    with pytest.raises(ProviderResponseError):
        parse_location({"hourly": {"time": [T0]}})
    p = hourly_payload(T0, 3)
    p["hourly"]["rain"] = [0.0]
    with pytest.raises(ProviderResponseError):
        parse_location(p)


@responses.activate
def test_single_vs_list_response_batching_and_cache():
    pts = [(40.0 + i * 0.1, -100.0) for i in range(60)]   # 60 unique -> 2 requests (50 + 10)

    def cb(request):
        n = len(request.params["latitude"].split(","))
        import json
        return 200, {}, json.dumps([hourly_payload(T0, 5)] * n)

    responses.add_callback(responses.GET, URL, callback=cb)
    c = OpenMeteoClient()
    out = c.get_hourly(pts, D, D)
    assert len(out) == 60 and len(responses.calls) == 2
    q = responses.calls[0].request.params
    assert q["wind_speed_unit"] == "mph" and q["precipitation_unit"] == "inch" and q["timeformat"] == "unixtime"
    assert {"wind_speed_10m", "rain", "showers", "snowfall"} <= set(q["hourly"].split(","))
    c.get_hourly(pts, D, D)
    assert len(responses.calls) == 2                      # fully cached


@responses.activate
def test_dedupes_nearby_points_and_single_dict_response():
    responses.add(responses.GET, URL, json=hourly_payload(T0, 3))
    out = OpenMeteoClient().get_hourly([(40.001, -100.001), (40.002, -100.002)], D, D)
    assert len(responses.calls) == 1 and out[0] is out[1]
    assert responses.calls[0].request.params["latitude"] == "40.0"


@responses.activate
def test_failures_map_to_provider_errors():
    c = OpenMeteoClient()
    responses.add(responses.GET, URL, body=requests.Timeout())
    with pytest.raises(ProviderTimeout):
        c.get_hourly([(1, 1)], D, D)
    responses.replace(responses.GET, URL, body=requests.ConnectionError("boom"))
    with pytest.raises(ProviderUnavailable):
        c.get_hourly([(1, 1)], D, D)
    responses.replace(responses.GET, URL, status=400, json={"error": True, "reason": "date out of range"})
    with pytest.raises(ProviderUnavailable, match="date out of range"):
        c.get_hourly([(1, 1)], D, D)
    responses.replace(responses.GET, URL, body="<html>", status=200)
    with pytest.raises(ProviderResponseError):
        c.get_hourly([(1, 1)], D, D)
    responses.replace(responses.GET, URL, json=[hourly_payload(T0, 2)] * 2)   # wrong count
    with pytest.raises(ProviderResponseError):
        c.get_hourly([(1, 1)], D, D)
