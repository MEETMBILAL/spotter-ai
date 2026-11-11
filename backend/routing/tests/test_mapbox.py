import logging
import pytest
import requests
import responses
from routing.providers.errors import (NoRouteError, ProviderConfigError, ProviderTimeout, ProviderUnavailable)
from routing.providers.mapbox import DIRECTIONS_URL, GEOCODE_URL, MapboxClient
from .helpers import line_route

DIR = DIRECTIONS_URL.format(coords="-100.000000,40.000000;-96.000000,40.000000")
O, D = (-100.0, 40.0), (-96.0, 40.0)


def client(token="tok"):
    return MapboxClient(token)


@responses.activate
def test_geocode_parse_skips_malformed_and_caches():
    responses.add(responses.GET, GEOCODE_URL, json={"features": [
        {"geometry": {"coordinates": [-87.6, 41.8]}, "properties": {"mapbox_id": "x", "name": "Chicago",
                                                                    "full_address": "Chicago, Illinois, United States"}},
        {"geometry": {}, "properties": {}}]})
    c = client()
    r = c.geocode("Chicago")
    assert len(r) == 1 and r[0].lon == -87.6 and r[0].label.startswith("Chicago")
    c.geocode("chicago")
    assert len(responses.calls) == 1
    assert responses.calls[0].request.params["access_token"] == "tok"


@responses.activate
def test_three_genuine_routes_and_geometry_preserved():
    routes = [line_route(5, 200, 14400), line_route(6, 210, 15000), line_route(7, 230, 16000)]
    responses.add(responses.GET, DIR, json={"code": "Ok", "routes": routes})
    out = client().get_routes(O, D)
    assert len(out) == 3 and len(out[1].coords) == 6 and out[0].coords[0] == (-100.0, 40.0)
    assert out[0].segment_durations_s == (3600.0,) * 4
    p = responses.calls[0].request.params
    assert p["alternatives"] == "true" and p["geometries"] == "geojson" and p["overview"] == "full"


@responses.activate
def test_duplicate_alternatives_dropped_never_fabricated():
    responses.add(responses.GET, DIR, json={"code": "Ok", "routes": [line_route(), line_route()]})
    assert len(client().get_routes(O, D)) == 1


@responses.activate
def test_routes_cached():
    responses.add(responses.GET, DIR, json={"code": "Ok", "routes": [line_route()]})
    c = client()
    c.get_routes(O, D), c.get_routes(O, D)
    assert len(responses.calls) == 1


@responses.activate
def test_no_route_and_errors():
    responses.add(responses.GET, DIR, json={"code": "NoRoute", "routes": []})
    with pytest.raises(NoRouteError):
        client().get_routes(O, D)
    responses.replace(responses.GET, DIR, json={"code": "Ok", "routes": []})
    with pytest.raises(NoRouteError):
        client().get_routes((-100.0, 40.0), (-96.0, 40.0))
    responses.replace(responses.GET, DIR, status=401, json={"message": "Not Authorized"})
    with pytest.raises(ProviderConfigError):
        client().get_routes(O, D)
    responses.replace(responses.GET, DIR, status=429, json={})
    with pytest.raises(ProviderUnavailable):
        client().get_routes(O, D)
    responses.replace(responses.GET, DIR, body=requests.Timeout())
    with pytest.raises(ProviderTimeout):
        client().get_routes(O, D)


def test_missing_token():
    with pytest.raises(ProviderConfigError):
        client("").geocode("abc")


@responses.activate
def test_token_never_logged(caplog):
    responses.add(responses.GET, GEOCODE_URL, body=requests.ConnectionError("failed https://x?access_token=SECRET123"))
    with caplog.at_level(logging.DEBUG), pytest.raises(ProviderUnavailable) as e:
        client("SECRET123").geocode("zzz")
    assert "SECRET123" not in caplog.text and "SECRET123" not in str(e.value)
