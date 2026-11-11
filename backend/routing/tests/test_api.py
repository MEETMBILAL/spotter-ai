import json
from datetime import datetime, timedelta, timezone
import pytest
import requests
import responses
from routing.providers.mapbox import DIRECTIONS_URL, GEOCODE_URL
from routing.providers.open_meteo import URL as OM
from .helpers import H, TRIP, future_start, hourly_payload, line_route

DIR = DIRECTIONS_URL.format(coords="-100.000000,40.000000;-96.000000,40.000000")


def body(dep=None, **kw):
    dep = dep or future_start(1)
    return {**TRIP, "departure_time": dep.isoformat(), **kw}


def post(client, path, data):
    return client.post(path, data=json.dumps(data), content_type="application/json")


def mock_routes(*routes):
    responses.add(responses.GET, DIR, json={"code": "Ok", "routes": list(routes or [line_route()])})


def mock_weather(**kw):
    start = int(future_start(0).timestamp()) - 6 * H

    def cb(request):
        n = len(request.params["latitude"].split(","))
        p = hourly_payload(start, 24 * 5, **kw)
        return 200, {}, json.dumps([p] * n if n > 1 else p)
    responses.add_callback(responses.GET, OM, callback=cb)


@responses.activate
def test_analyze_end_to_end_structure_and_mileage(client):
    mock_routes(line_route(5, 200, 14400), line_route(6, 215, 15000), line_route(7, 240, 17000))
    mock_weather(wind=10, rain=0.0, snow=0.0)
    r = post(client, "/api/analyze", body())
    assert r.status_code == 200, r.content
    d = r.json()
    assert len(d["routes"]) == 3 and d["meta"]["truck_specific_routing"] is False
    for route in d["routes"]:
        assert sum(s["end_mi"] - s["start_mi"] for s in route["segments"]) == pytest.approx(route["distance_miles"], abs=0.05)
        assert sum(route["summary"]["miles_by_risk"].values()) == pytest.approx(route["distance_miles"], abs=0.05)
        cps = route["checkpoints"]
        assert cps[0]["is_origin"] and cps[-1]["is_destination"]
        assert cps[-1]["distance_miles"] == pytest.approx(route["distance_miles"], abs=0.01)
        assert all(b["distance_miles"] > a["distance_miles"] for a, b in zip(cps, cps[1:]))
        assert all(c["risk"]["final"]["label"] == "Low" and c["weather"]["status"] == "ok" for c in cps)
        assert route["eta_method"] == "segment"
    assert d["recommendation"]["status"] == "recommended" and d["recommendation"]["route_id"] == "route-1"  # shortest
    etas = [c["eta"] for c in d["routes"][0]["checkpoints"]]
    assert etas == sorted(etas) and etas[0] == d["trip"]["departure_time"]


@responses.activate
def test_fewer_than_three_routes_is_disclosed(client):
    mock_routes(line_route())
    mock_weather()
    d = post(client, "/api/analyze", body()).json()
    assert len(d["routes"]) == 1 and any("not 3" in w and "fabricated" in w for w in d["warnings"])


@responses.activate
def test_all_routes_no_travel(client):
    mock_routes(line_route(5, 200, 14400), line_route(6, 215, 15000))
    mock_weather(wind=60)
    d = post(client, "/api/analyze", body()).json()
    assert d["recommendation"]["status"] == "no_safe_route" and d["recommendation"]["message"] == "No Safe Route Available"
    assert d["recommendation"]["route_id"] is None and len(d["routes"]) == 2
    assert all(r["summary"]["has_no_travel"] and not r["ranking"]["eligible"] for r in d["routes"])


@responses.activate
def test_load_override_changes_risk(client):
    mock_routes()
    mock_weather(wind=40)
    heavy = post(client, "/api/analyze", body(load_lb=45000)).json()["routes"][0]["checkpoints"][0]["risk"]
    light = post(client, "/api/analyze", body(load_lb=20000)).json()["routes"][0]["checkpoints"][0]["risk"]
    assert heavy["final"]["label"] == "Severe" and heavy["load_override_applied"]
    assert light["final"]["label"] == "High" and not light["load_override_applied"]


@responses.activate
def test_weather_provider_failure_is_never_low(client):
    mock_routes()
    responses.add(responses.GET, OM, body=requests.Timeout())
    d = post(client, "/api/analyze", body()).json()
    cps = d["routes"][0]["checkpoints"]
    assert all(c["risk"]["final"]["level"] is None and c["risk"]["final"]["label"] == "Unknown" for c in cps)
    assert d["recommendation"]["status"] == "insufficient_data" and d["recommendation"]["route_id"] is None
    assert any("Weather data unavailable" in w for w in d["warnings"])
    assert d["routes"][0]["summary"]["unknown_miles"] == pytest.approx(d["routes"][0]["distance_miles"], abs=0.05)


@responses.activate
def test_forecast_not_covering_arrival_is_marked(client):
    mock_routes()
    start = int(future_start(1).timestamp())  # forecast ends 3h after departure; trip takes 4h

    def cb(request):
        n = len(request.params["latitude"].split(","))
        return 200, {}, json.dumps([hourly_payload(start, 4)] * n if n > 1 else hourly_payload(start, 4))
    responses.add_callback(responses.GET, OM, callback=cb)
    d = post(client, "/api/analyze", body(dep=datetime.fromtimestamp(start, timezone.utc))).json()
    cps = d["routes"][0]["checkpoints"]
    assert cps[-1]["weather"]["reason"] == "forecast_not_covered" and cps[-1]["risk"]["final"]["level"] is None
    assert d["routes"][0]["summary"]["unknown_miles"] > 0
    assert d["recommendation"]["status"] == "recommended_partial_data" and d["recommendation"]["warnings"]


@responses.activate
def test_mapbox_errors_surface_cleanly(client):
    responses.add(responses.GET, DIR, json={"code": "NoRoute"})
    r = post(client, "/api/analyze", body())
    assert r.status_code == 404 and r.json()["error"]["code"] == "no_route"


def test_missing_token_is_503(client, settings):
    settings.MAPBOX_SERVER_TOKEN = ""
    r = post(client, "/api/analyze", body())
    assert r.status_code == 503 and r.json()["error"]["code"] == "provider_not_configured"


@pytest.mark.parametrize("patch", [
    {"load_lb": -1}, {"load_lb": 10**9}, {"load_lb": "abc"}, {"checkpoint_interval_miles": 30},
    {"origin": {"lon": 999, "lat": 0}}, {"departure_time": "tomorrow"}, {"departure_time": "2026-11-12T08:00:00"},
    {"departure_time": (datetime.now(timezone.utc) + timedelta(days=40)).isoformat()},
    {"destination": {"label": "same", "lon": -100.0, "lat": 40.0}},
])
def test_validation_errors(client, patch):
    r = post(client, "/api/analyze", {**body(), **patch})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_request"


def test_malformed_and_oversized_bodies(client):
    assert client.post("/api/analyze", data="{not json", content_type="application/json").status_code == 400
    assert client.post("/api/analyze", data="x" * 70_000, content_type="application/json").status_code == 413


@responses.activate
def test_heatmap_49_frames(client):
    mock_routes(line_route(5, 200, 14400))
    mock_weather(wind=lambda i: i % 60)
    r = post(client, "/api/heatmap", body(route_index=0))
    assert r.status_code == 200, r.content
    d = r.json()
    n = len(d["points"])
    assert 2 <= n <= 99 and [f["hour"] for f in d["frames"]] == list(range(49))
    assert all(len(f["wind_mph"]) == n == len(f["risk"]) for f in d["frames"])
    assert d["frames"][0]["time"] == d["departure_time"] and d["unavailable_hours"] == []
    assert len({tuple(p) for p in d["points"]}) == n
    # series starts 6h before "now"; departure is +24h => hour h reads series index 30+h
    assert d["frames"][5]["wind_mph"][0] == 35          # real series value, not decorative
    assert "truck" in d["note"].lower()


@responses.activate
def test_heatmap_reuses_cached_directions_and_rejects_bad_route(client):
    mock_routes(line_route())
    mock_weather()
    post(client, "/api/analyze", body())
    post(client, "/api/heatmap", body(route_index=0))
    assert sum(1 for c in responses.calls if c.request.url.startswith("https://api.mapbox.com")) == 1
    r = post(client, "/api/heatmap", body(route_index=2))
    assert r.status_code == 404


@responses.activate
def test_heatmap_hours_beyond_forecast_flagged(client):
    mock_routes()
    start = int(future_start(1).timestamp())
    def cb(request):
        n = len(request.params["latitude"].split(","))
        return 200, {}, json.dumps([hourly_payload(start, 10)] * n if n > 1 else hourly_payload(start, 10))
    responses.add_callback(responses.GET, OM, callback=cb)
    d = post(client, "/api/heatmap", body(dep=datetime.fromtimestamp(start, timezone.utc))).json()
    assert d["unavailable_hours"] == list(range(10, 49))
    assert all(r is None for r in d["frames"][20]["risk"])


@responses.activate
def test_geocode(client):
    responses.add(responses.GET, GEOCODE_URL, json={"features": [{"geometry": {"coordinates": [-87.6, 41.8]},
                  "properties": {"mapbox_id": "a", "name": "Chicago", "full_address": "Chicago, IL"}}]})
    r = client.get("/api/geocode", {"q": "Chic"})
    assert r.status_code == 200 and r.json()["results"][0]["lon"] == -87.6
    assert client.get("/api/geocode", {"q": "a"}).status_code == 400
    assert client.get("/api/geocode").status_code == 400


def test_rate_limiting(client):
    codes = [client.post("/api/analyze", data="{}", content_type="application/json").status_code for _ in range(12)]
    assert 429 in codes and codes[0] == 400


def test_no_stack_trace_leak(client, monkeypatch):
    import routing.api.views as v
    monkeypatch.setattr(v, "get_directions", lambda: (_ for _ in ()).throw(RuntimeError("secret internals")))
    r = post(client, "/api/analyze", body())
    assert r.status_code == 500 and "secret internals" not in r.content.decode()
    assert r.json()["error"]["code"] == "internal_error"


# ---------------------------------------------------------------------------
# Security tests added as part of production hardening
# ---------------------------------------------------------------------------

def test_health_no_provider_details(client):
    """Health endpoint must not leak provider configuration details."""
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert "mapbox_configured" not in data
    assert "token" not in str(r.content)


def test_health_minimal(client):
    """Health endpoint must return exactly {"status": "ok"}."""
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_wrong_method_analyze(client):
    """GET on /api/analyze must be rejected with 405."""
    r = client.get("/api/analyze")
    assert r.status_code == 405


def test_wrong_method_heatmap(client):
    """GET on /api/heatmap must be rejected with 405."""
    r = client.get("/api/heatmap")
    assert r.status_code == 405


def test_wrong_method_geocode_post(client):
    """POST on /api/geocode must be rejected with 405."""
    r = client.post("/api/geocode", data="{}", content_type="application/json")
    assert r.status_code == 405


def test_rate_limit_has_retry_after(client):
    """429 responses from DRF throttling must carry a Retry-After header."""
    # Exhaust the analyze throttle (limit is 10/min; send 12 to be sure)
    for _ in range(12):
        client.post("/api/analyze", data="{}", content_type="application/json")
    # Collect further responses and check for 429s
    extra = [client.post("/api/analyze", data="{}", content_type="application/json")
             for _ in range(5)]
    throttled = [r for r in extra if r.status_code == 429]
    assert throttled, "Expected at least one 429 response after exhausting throttle"
    for r in throttled:
        # Retry-After must be present (DRF sets wait; our errors.py forwards it)
        assert "Retry-After" in r, f"Missing Retry-After header in 429 response: {dict(r.items())}"


def test_geocode_short_query_rejected(client):
    """Single-character geocode queries must be rejected without leaking internals."""
    r = client.get("/api/geocode", {"q": "a"})
    assert r.status_code == 400
    body = r.content.decode()
    assert "token" not in body.lower()
    assert "traceback" not in body.lower()


def test_error_no_internal_info(client):
    """Error responses must not contain Django internals, tracebacks, or tokens."""
    r = client.post("/api/analyze", data='{"load_lb": -1}', content_type="application/json")
    body = r.content.decode()
    assert r.status_code == 400
    assert "django" not in body.lower()
    assert "traceback" not in body.lower()
    assert "/home/" not in body
    assert "test-token" not in body


def test_deeply_nested_payload_rejected(client):
    """A payload with a structurally invalid field type must return 400."""
    import json as _json
    payload = {
        "origin": {"lon": -100, "lat": 40, "label": "A"},
        "destination": {"lon": -96, "lat": 40, "label": "B"},
        "departure_time": "2026-11-12T08:00:00Z",
        "load_lb": {"nested": {"deeply": "nested_object"}},
        "checkpoint_interval_miles": 25,
    }
    r = client.post("/api/analyze", data=_json.dumps(payload), content_type="application/json")
    assert r.status_code == 400


def test_wrong_content_type_analyze(client):
    """Form-encoded bodies to /api/analyze must be rejected (400 or 415)."""
    r = client.post("/api/analyze", data="load_lb=1000",
                    content_type="application/x-www-form-urlencoded")
    assert r.status_code in (400, 415)


# ── AbuseGuardMiddleware tests ──────────────────────────────────────────────

def test_abuse_guard_blocks_burst(client, settings):
    """When ABUSE_BURST_LIMIT is exceeded, middleware returns 429 with Retry-After."""
    settings.ABUSE_BURST_LIMIT = 3
    settings.ABUSE_WINDOW_S = 60
    settings.ABUSE_BLOCK_S = 30
    from django.core.cache import cache
    cache.clear()
    responses_list = [
        client.post("/api/analyze", data="{}", content_type="application/json")
        for _ in range(6)
    ]
    blocked = [r for r in responses_list if r.status_code == 429]
    assert blocked, "Expected middleware to block after burst limit"
    assert "Retry-After" in blocked[0]


def test_abuse_guard_does_not_affect_geocode(client, settings):
    """Geocode endpoint is not guarded by AbuseGuardMiddleware."""
    settings.ABUSE_BURST_LIMIT = 1
    settings.ABUSE_WINDOW_S = 60
    settings.ABUSE_BLOCK_S = 30
    from django.core.cache import cache
    cache.clear()
    r1 = client.get("/api/geocode", {"q": "test"})
    assert r1.status_code != 429 or r1.json().get("error", {}).get("message") != "Too many requests. Please try again later."
