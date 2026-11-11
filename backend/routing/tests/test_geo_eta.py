from datetime import datetime, timedelta, timezone
import pytest
from routing.domain.geo import (build_checkpoints, checkpoint_distances, cumulative_miles,
                                haversine_miles, point_at_distance)
from routing.domain.eta import arrival_time, seconds_at_distance, time_profile

LINE = [(-100.0, 40.0), (-99.0, 40.0), (-98.0, 40.0), (-97.0, 40.0)]


def test_haversine_one_degree_latitude():
    assert haversine_miles((0, 0), (0, 1)) == pytest.approx(69.09, abs=0.05)


def test_distances_include_origin_and_destination_once():
    assert checkpoint_distances(100, 25) == [0, 25, 50, 75, 100]  # destination not duplicated
    assert checkpoint_distances(101, 25) == [0, 25, 50, 75, 100, 101]
    assert checkpoint_distances(7, 10) == [0, 7]
    d = checkpoint_distances(333.3, 10)
    assert d[-1] == 333.3 and all(b > a for a, b in zip(d, d[1:]))


@pytest.mark.parametrize("bad", [0, 5, 20, 100])
def test_bad_interval(bad):
    with pytest.raises(ValueError):
        checkpoint_distances(100, bad)


def test_cumulative_scaling_matches_provider_distance():
    cum = cumulative_miles(LINE, target_total_miles=200.0)
    assert cum[-1] == pytest.approx(200.0) and cum[0] == 0


def test_checkpoints_lie_on_route_and_are_ordered():
    cum = cumulative_miles(LINE)
    cps = build_checkpoints(LINE, cum, 50)
    assert cps[0].is_origin and cps[-1].is_destination and not any(c.is_destination for c in cps[:-1])
    assert (cps[0].lon, cps[0].lat) == LINE[0]
    assert cps[-1].lon == pytest.approx(-97.0) and cps[-1].lat == pytest.approx(40.0)
    assert all(b.distance_miles > a.distance_miles for a, b in zip(cps, cps[1:]))
    assert all(c.lat == pytest.approx(40.0) and -100 <= c.lon <= -97 for c in cps)


def test_point_at_distance_midpoint():
    cum = [0, 10, 20]
    assert point_at_distance([(0, 0), (1, 0), (2, 0)], cum, 15) == (1.5, 0)
    assert point_at_distance([(0, 0), (1, 0), (2, 0)], cum, 99) == (2, 0)


def test_too_short_geometry():
    with pytest.raises(ValueError):
        cumulative_miles([(0, 0)])


def test_proportional_eta():
    cum = [0, 50, 100]
    times, method = time_profile(cum, 7200)
    assert method == "proportional" and seconds_at_distance(cum, times, 25) == 1800


def test_segment_eta_uses_segment_durations_and_rescales():
    cum = [0, 50, 100]
    times, method = time_profile(cum, 7200, [1000, 3000])  # slow second half
    assert method == "segment" and times[-1] == pytest.approx(7200)
    assert seconds_at_distance(cum, times, 50) == pytest.approx(1800)
    assert seconds_at_distance(cum, times, 75) == pytest.approx(1800 + 2700)


def test_segment_length_mismatch_falls_back():
    assert time_profile([0, 50, 100], 100, [1, 2, 3])[1] == "proportional"


def test_arrival_time_requires_tz_and_adds_offset():
    cum = [0, 100]
    times, _ = time_profile(cum, 3600)
    dep = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    assert arrival_time(dep, cum, times, 100) == dep + timedelta(hours=1)
    with pytest.raises(ValueError):
        arrival_time(datetime(2026, 1, 1), cum, times, 0)
