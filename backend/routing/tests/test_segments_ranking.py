import pytest
from routing.domain.ranking import NO_SAFE_ROUTE_MESSAGE, RouteCandidate, rank_routes
from routing.domain.risk import Risk
from routing.domain.segments import build_segments, summarize

L, M, H, S, N = Risk.LOW, Risk.MODERATE, Risk.HIGH, Risk.SEVERE, Risk.NO_TRAVEL


def test_segments_tile_route_exactly():
    segs = build_segments([0, 25, 50, 75, 100], [L, M, H, S, N], 100)
    assert segs[0].start_mi == 0 and segs[-1].end_mi == 100
    assert all(a.end_mi == b.start_mi for a, b in zip(segs, segs[1:]))  # no gaps/overlaps
    assert [s.miles for s in segs] == [12.5, 25, 25, 25, 12.5]
    assert sum(s.miles for s in segs) == 100


def test_uneven_final_checkpoint():
    segs = build_segments([0, 10, 20, 23], [L, L, L, H], 23)
    assert sum(s.miles for s in segs) == pytest.approx(23) and segs[-1].end_mi == 23


def test_checkpoint_count_times_interval_is_not_used():
    segs = build_segments([0, 50, 60], [L, L, S], 60)  # 3 checkpoints, 60 mi (not 150)
    assert summarize(segs).total_miles == 60


def test_validation():
    with pytest.raises(ValueError):
        build_segments([0, 10, 10], [L, L, L], 10)
    with pytest.raises(ValueError):
        build_segments([0, 20], [L, L], 10)


def test_summary_aggregation_and_average():
    s = summarize(build_segments([0, 25, 50, 75, 100], [L, M, H, S, S], 100))
    assert s.total_miles == 100 and s.complete
    assert sum(s.miles_by_risk.values()) == pytest.approx(100)
    assert s.severe_miles == pytest.approx(37.5) and s.high_miles == pytest.approx(25)
    # (0*12.5 + 1*25 + 2*25 + 3*37.5)/100 = 1.875
    assert s.average_risk == pytest.approx(1.875)


def test_unknown_miles_excluded_from_average_and_reported():
    s = summarize(build_segments([0, 50, 100], [L, None, None], 100))
    assert s.unknown_miles == pytest.approx(75) and not s.complete
    assert s.average_risk == 0 and s.known_miles == pytest.approx(25)
    assert summarize(build_segments([0, 100], [None, None], 100)).average_risk is None


def test_rounded_miles_sum_to_total():
    s = summarize(build_segments([0, 33, 66, 99], [L, M, H, S], 99.07))
    r = s.rounded_miles(1)
    assert sum(r.values()) == pytest.approx(round(99.07, 1))


def cand(rid, dur, risks, dists=None, total=100):
    dists = dists or [i * total / (len(risks) - 1) if len(risks) > 1 else 0 for i in range(len(risks))]
    return RouteCandidate(rid, dur, summarize(build_segments(dists, risks, total)))


def test_lexicographic_severe_beats_everything():
    a = cand("fast", 1000, [L, S, L, L, L])      # severe miles, fastest
    b = cand("slow", 9000, [H, H, H, H, H])      # no severe, many high, slowest
    r = rank_routes([a, b])
    assert r.recommended_id == "slow" and r.ranked[0].decided_by == "severe_miles"


def test_high_then_average_then_duration():
    assert rank_routes([cand("a", 1, [H, L, L, L, L]), cand("b", 9, [L] * 5)]).recommended_id == "b"
    r = rank_routes([cand("a", 1, [M, M, M, M, M]), cand("b", 9, [L] * 5)])
    assert r.recommended_id == "b" and r.ranked[0].decided_by == "average_risk"
    r = rank_routes([cand("a", 500, [L] * 5), cand("b", 100, [L] * 5)])
    assert r.recommended_id == "b" and r.ranked[0].decided_by == "duration"


def test_no_travel_is_gate_not_weight():
    blocked = cand("blocked", 1, [L, L, N, L, L])
    ok = cand("ok", 99999, [S, S, S, S, S])  # terrible but eligible
    r = rank_routes([blocked, ok])
    assert r.recommended_id == "ok"
    by = {x.route_id: x for x in r.ranked}
    assert not by["blocked"].eligible and by["blocked"].rank is None and "No Travel" in by["blocked"].ineligible_reason


def test_all_blocked():
    r = rank_routes([cand("a", 1, [N, L, L, L, L]), cand("b", 2, [L, L, L, L, N])])
    assert r.recommended_id is None and r.status == "no_safe_route" and r.message == NO_SAFE_ROUTE_MESSAGE
    assert all(not x.eligible for x in r.ranked) and len(r.ranked) == 2  # still displayed


def test_empty_candidates():
    assert rank_routes([]).status == "no_safe_route"


def test_partial_data_is_flagged_and_complete_routes_preferred():
    partial = cand("partial", 1, [L, None, None, None, None])
    full = cand("full", 9999, [M] * 5)
    r = rank_routes([partial, full])
    assert r.recommended_id == "full" and r.status == "recommended"
    r2 = rank_routes([partial])
    assert r2.status == "recommended_partial_data" and r2.warnings


def test_all_unknown_route_not_recommended():
    r = rank_routes([cand("x", 1, [None] * 5)])
    assert r.recommended_id is None and r.status == "insufficient_data"  # not "no safe route"
    mixed = rank_routes([cand("x", 1, [None] * 5), cand("n", 1, [N] * 5)])
    assert mixed.status == "no_safe_route"


def test_tie_is_stable():
    r = rank_routes([cand("first", 100, [L] * 5), cand("second", 100, [L] * 5)])
    assert r.recommended_id == "first" and r.ranked[0].decided_by == "tie"
