"""Unit tests for the pure domain layer: risk, geo, eta, segments, weather, ranking."""
import math
import pytest
from datetime import datetime, timezone, timedelta
from routing.domain.risk import (
    Risk, classify_wind, classify_rain, classify_snow,
    apply_load_override, assess_checkpoint,
)
from routing.domain.geo import (
    haversine_miles, cumulative_miles, checkpoint_distances,
    build_checkpoints, point_at_distance, corridor_points,
)
from routing.domain.eta import time_profile, seconds_at_distance, arrival_time
from routing.domain.segments import build_segments, summarize, RouteRiskSummary, RiskSegment
from routing.domain.weather import HourlySeries, sample_at
from routing.domain.ranking import rank_routes, RouteCandidate


# ===============================================================
# RISK ENGINE
# ===============================================================

class TestWindClassification:
    def test_calm_is_low(self):
        assert classify_wind(0) == Risk.LOW
    def test_boundary_25_is_moderate(self):
        assert classify_wind(25) == Risk.MODERATE
    def test_just_below_25_is_low(self):
        assert classify_wind(24.9) == Risk.LOW
    def test_35_is_high(self):
        assert classify_wind(35) == Risk.HIGH
    def test_45_is_severe(self):
        assert classify_wind(45) == Risk.SEVERE
    def test_55_is_no_travel(self):
        assert classify_wind(55) == Risk.NO_TRAVEL
    def test_none_is_none(self):
        assert classify_wind(None) is None
    def test_nan_is_none(self):
        assert classify_wind(float("nan")) is None


class TestRainClassification:
    def test_no_rain_is_low(self):
        assert classify_rain(0) == Risk.LOW
    def test_heavy_rain_is_no_travel(self):
        assert classify_rain(1.5) == Risk.NO_TRAVEL
    def test_exactly_1_in_hr_is_severe(self):
        assert classify_rain(1.0) == Risk.SEVERE
    def test_none_is_none(self):
        assert classify_rain(None) is None


class TestSnowClassification:
    def test_trace_snow_is_low(self):
        assert classify_snow(0.1) == Risk.LOW
    def test_heavy_snow_is_no_travel(self):
        assert classify_snow(5.0) == Risk.NO_TRAVEL
    def test_none_is_none(self):
        assert classify_snow(None) is None


class TestLoadOverride:
    def test_55mph_always_no_travel(self):
        result = apply_load_override(55, 0, Risk.LOW)
        assert result == Risk.NO_TRAVEL
    def test_45mph_heavy_load_no_travel(self):
        result = apply_load_override(46, 35000, Risk.HIGH)
        assert result == Risk.NO_TRAVEL
    def test_45mph_light_load_unchanged(self):
        result = apply_load_override(46, 20000, Risk.HIGH)
        assert result == Risk.HIGH
    def test_35mph_very_heavy_load_raises_to_severe(self):
        result = apply_load_override(36, 45000, Risk.MODERATE)
        assert result == Risk.SEVERE
    def test_no_wind_data_unchanged(self):
        result = apply_load_override(None, 80000, Risk.LOW)
        assert result == Risk.LOW


class TestAssessCheckpoint:
    def test_all_low_no_override(self):
        r = assess_checkpoint(10, 0.05, 0.1, 35000)
        assert r.final == Risk.LOW
        assert r.complete is True
        assert r.load_override_applied is False
    def test_max_component_wins(self):
        r = assess_checkpoint(10, 0.05, 5.0, 35000)  # snow is No Travel
        assert r.final == Risk.NO_TRAVEL
    def test_no_data_returns_none_final(self):
        r = assess_checkpoint(None, None, None, 35000)
        assert r.final is None
        assert r.complete is False
    def test_partial_data_complete_false(self):
        r = assess_checkpoint(10, None, 0.1, 35000)
        assert r.complete is False
    def test_load_override_applied_flag(self):
        r = assess_checkpoint(46, 0, 0, 35000)  # 46mph wind + 35k lb -> NO_TRAVEL
        assert r.load_override_applied is True
    def test_negative_load_raises(self):
        with pytest.raises(ValueError):
            assess_checkpoint(10, 0, 0, -1)


# ===============================================================
# GEO
# ===============================================================

class TestHaversine:
    def test_same_point_is_zero(self):
        assert haversine_miles((-87.6, 41.8), (-87.6, 41.8)) == pytest.approx(0, abs=1e-6)
    def test_known_distance(self):
        # Chicago to NYC ~ 711 miles
        d = haversine_miles((-87.6298, 41.8781), (-74.0060, 40.7128))
        assert 700 < d < 730
    def test_symmetric(self):
        a, b = (-100, 40), (-96, 40)
        assert haversine_miles(a, b) == pytest.approx(haversine_miles(b, a))


class TestCumulativeMiles:
    def test_basic_accumulation(self):
        coords = [(-100, 40), (-99, 40), (-98, 40)]
        cum = cumulative_miles(coords)
        assert cum[0] == 0
        assert cum[-1] > 0
        assert cum[1] < cum[2]
    def test_scaled_to_target(self):
        coords = [(-100, 40), (-96, 40)]
        cum = cumulative_miles(coords, target_total_miles=250)
        assert cum[-1] == pytest.approx(250, abs=1e-9)
    def test_single_coord_raises(self):
        with pytest.raises(ValueError):
            cumulative_miles([(-100, 40)])


class TestCheckpointDistances:
    def test_200_mile_route_at_50(self):
        d = checkpoint_distances(200, 50)
        assert d == [0, 50, 100, 150, 200]
    def test_always_starts_at_zero_ends_at_total(self):
        d = checkpoint_distances(175, 25)
        assert d[0] == 0
        assert d[-1] == 175
    def test_invalid_interval_raises(self):
        with pytest.raises(ValueError):
            checkpoint_distances(100, 30)


# ===============================================================
# ETA
# ===============================================================

class TestTimeProfile:
    def test_proportional_fallback(self):
        cum = [0, 50, 100, 200]
        t, method = time_profile(cum, 7200)
        assert method == "proportional"
        assert t[0] == 0
        assert t[-1] == pytest.approx(7200)
    def test_segment_method_used_when_annotations_match(self):
        cum = [0, 100, 200]
        segs = [3600.0, 3600.0]
        t, method = time_profile(cum, 7200, segs)
        assert method == "segment"
        assert t[-1] == pytest.approx(7200)
    def test_zero_duration_raises(self):
        with pytest.raises(ValueError):
            time_profile([0, 100], 0)


class TestArrivalTime:
    def test_departure_at_origin(self):
        dep = datetime(2026, 11, 12, 8, 0, tzinfo=timezone.utc)
        result = arrival_time(dep, [0, 100], [0, 7200], 0)
        assert result == dep
    def test_destination_adds_duration(self):
        dep = datetime(2026, 11, 12, 8, 0, tzinfo=timezone.utc)
        result = arrival_time(dep, [0, 100], [0, 7200], 100)
        assert result == dep + timedelta(hours=2)
    def test_naive_departure_raises(self):
        with pytest.raises(ValueError):
            arrival_time(datetime(2026, 11, 12, 8, 0), [0, 100], [0, 7200], 50)


# ===============================================================
# SEGMENTS
# ===============================================================

class TestBuildSegments:
    def test_tiles_cover_full_route(self):
        distances = [0, 50, 100, 200]
        risks = [Risk.LOW, Risk.HIGH, Risk.SEVERE, Risk.NO_TRAVEL]
        segs = build_segments(distances, risks, 200)
        assert segs[0].start_mi == 0
        assert segs[-1].end_mi == pytest.approx(200)
        total = sum(s.miles for s in segs)
        assert total == pytest.approx(200)
    def test_no_gaps_or_overlaps(self):
        distances = [0, 100, 200]
        risks = [Risk.LOW, Risk.MODERATE]
        segs = build_segments(distances, risks, 200)
        for a, b in zip(segs, segs[1:]):
            assert a.end_mi == pytest.approx(b.start_mi)
    def test_mismatched_lengths_raises(self):
        with pytest.raises(ValueError):
            build_segments([0, 100], [Risk.LOW, Risk.HIGH, Risk.SEVERE], 100)


class TestSummarize:
    def test_all_low(self):
        segs = [RiskSegment(0, 0, 100, Risk.LOW), RiskSegment(1, 100, 200, Risk.LOW)]
        s = summarize(segs)
        assert s.total_miles == pytest.approx(200)
        assert s.unknown_miles == 0
        assert s.average_risk == pytest.approx(0)
    def test_mixed_risks(self):
        segs = [RiskSegment(0, 0, 100, Risk.LOW), RiskSegment(1, 100, 200, Risk.SEVERE)]
        s = summarize(segs)
        # average: (0*100 + 3*100) / 200 = 1.5
        assert s.average_risk == pytest.approx(1.5)
    def test_unknown_miles_excluded_from_average(self):
        segs = [RiskSegment(0, 0, 100, Risk.HIGH), RiskSegment(1, 100, 200, None)]
        s = summarize(segs)
        assert s.unknown_miles == pytest.approx(100)
        assert s.average_risk == pytest.approx(2.0)  # only 100 known miles, risk=2


class TestRoundedMiles:
    def test_sums_to_total(self):
        segs = [RiskSegment(0, 0, 33.33, Risk.LOW), RiskSegment(1, 33.33, 66.67, Risk.HIGH), RiskSegment(2, 66.67, 100, Risk.SEVERE)]
        s = summarize(segs)
        rounded = s.rounded_miles(1)
        assert sum(rounded.values()) == pytest.approx(round(s.total_miles, 1), abs=0.11)


# ===============================================================
# WEATHER SAMPLING
# ===============================================================

T0 = 1700000000

def _series(hours=5, wind=10.0, rain=0.1, snow=0.0):
    times = tuple(T0 + i * 3600 for i in range(hours))
    return HourlySeries(
        times=times,
        wind_mph=tuple(wind for _ in range(hours)),
        rain_in=tuple(rain for _ in range(hours)),
        snow_in=tuple(snow for _ in range(hours)),
    )

class TestSampleAt:
    def test_exact_hour_hit(self):
        s = sample_at(_series(), T0)
        assert s.status == "ok"
        assert s.wind_mph == pytest.approx(10.0)
    def test_between_hours_interpolates_wind(self):
        times = (T0, T0 + 3600)
        series = HourlySeries(times=times, wind_mph=(0.0, 36.0), rain_in=(0.1, 0.1), snow_in=(0.0, 0.0))
        s = sample_at(series, T0 + 1800)  # halfway
        assert s.wind_mph == pytest.approx(18.0)
    def test_before_forecast_is_unavailable(self):
        s = sample_at(_series(), T0 - 1)
        assert s.status == "unavailable"
        assert s.reason == "forecast_not_covered"
    def test_after_forecast_is_unavailable(self):
        s = sample_at(_series(hours=3), T0 + 4 * 3600)
        assert s.status == "unavailable"
    def test_none_series_is_unavailable(self):
        s = sample_at(None, T0)
        assert s.status == "unavailable"
    def test_partial_none_values_give_partial_status(self):
        times = (T0,)
        series = HourlySeries(times=times, wind_mph=(None,), rain_in=(0.1,), snow_in=(0.0,))
        s = sample_at(series, T0)
        assert s.status == "partial"


# ===============================================================
# RANKING
# ===============================================================

def _candidate(route_id, severe=0, high=0, avg=0.5, duration=14400, complete=True, no_travel=0):
    miles_by_risk = {r: 0.0 for r in Risk}
    miles_by_risk[Risk.SEVERE] = severe
    miles_by_risk[Risk.HIGH] = high
    miles_by_risk[Risk.NO_TRAVEL] = no_travel
    miles_by_risk[Risk.LOW] = max(0, 200 - severe - high - no_travel)
    unknown = 0.0 if complete else 50.0
    total = 200.0
    summary = RouteRiskSummary(total_miles=total, miles_by_risk=miles_by_risk, unknown_miles=unknown)
    return RouteCandidate(route_id=route_id, duration_s=duration, summary=summary)

class TestRanking:
    def test_fewer_severe_miles_wins(self):
        a = _candidate("route-1", severe=10)
        b = _candidate("route-2", severe=0)
        result = rank_routes([a, b])
        assert result.recommended_id == "route-2"
    def test_no_travel_route_is_ineligible(self):
        a = _candidate("route-1", no_travel=50)
        b = _candidate("route-2")
        result = rank_routes([a, b])
        assert result.recommended_id == "route-2"
        ineligible = next(r for r in result.ranked if r.route_id == "route-1")
        assert not ineligible.eligible
    def test_all_no_travel_is_no_safe_route(self):
        candidates = [_candidate("r1", no_travel=100), _candidate("r2", no_travel=50)]
        result = rank_routes(candidates)
        assert result.status == "no_safe_route"
        assert result.recommended_id is None
    def test_complete_data_beats_partial(self):
        complete = _candidate("route-1", complete=True)
        partial = _candidate("route-2", complete=False)
        result = rank_routes([partial, complete])
        assert result.recommended_id == "route-1"
    def test_tie_broken_by_duration(self):
        fast = _candidate("route-1", duration=10000)
        slow = _candidate("route-2", duration=20000)
        result = rank_routes([slow, fast])
        assert result.recommended_id == "route-1"
    def test_single_route_recommended(self):
        result = rank_routes([_candidate("route-1")])
        assert result.recommended_id == "route-1"
        assert result.status == "recommended"
