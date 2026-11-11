import math
import pytest
from routing.domain.risk import (Risk, apply_load_override, assess_checkpoint,
                                 classify_rain, classify_snow, classify_wind)

L, M, H, S, N = Risk.LOW, Risk.MODERATE, Risk.HIGH, Risk.SEVERE, Risk.NO_TRAVEL


@pytest.mark.parametrize("v,exp", [(0, L), (24.99, L), (25, M), (34.99, M), (35, H), (44.99, H),
                                   (45, S), (54.99, S), (55, N), (80, N)])
def test_wind(v, exp):
    assert classify_wind(v) == exp


@pytest.mark.parametrize("v,exp", [(0, L), (0.0999, L), (0.10, M), (0.2499, M), (0.25, H), (0.4999, H),
                                   (0.50, S), (1.00, S), (1.000001, N), (3, N)])
def test_rain(v, exp):
    assert classify_rain(v) == exp


@pytest.mark.parametrize("v,exp", [(0, L), (0.499, L), (0.5, M), (0.999, M), (1.0, H), (1.999, H),
                                   (2.0, S), (3.0, S), (3.000001, N), (9, N)])
def test_snow(v, exp):
    assert classify_snow(v) == exp


def test_float_noise_does_not_cross_boundary():
    assert classify_rain(0.25000000000000006) == H and classify_rain(0.1 + 1e-12) == M
    assert classify_rain(1.0000000000000002) == S


def test_missing_is_unknown_not_low():
    assert classify_wind(None) is None and classify_rain(math.nan) is None and classify_snow(None) is None


def test_negative_rejected():
    with pytest.raises(ValueError):
        classify_wind(-1)


@pytest.mark.parametrize("wind,load,exp", [
    (55, 0, N), (60, 1, N),
    (45, 30_000, S), (45, 30_001, N), (54.9, 30_001, N), (54.9, 30_000, S),
    (35, 40_000, H), (35, 40_001, S), (44.9, 40_001, S), (44.9, 40_000, H),
    (44.9, 35_000, H), (34.9, 80_000, M), (24, 80_000, L),
])
def test_load_overrides(wind, load, exp):
    assert assess_checkpoint(wind, 0, 0, load).final == exp


def test_override_never_lowers_risk():
    assert apply_load_override(40, 50_000, N) == N
    r = assess_checkpoint(40, 0.6, 0, 50_000)  # rain severe, override severe
    assert r.final == S


def test_combined_takes_worst():
    r = assess_checkpoint(10, 0.3, 2.5, 10_000)
    assert (r.wind, r.rain, r.snow, r.final) == (L, H, S, S) and r.complete
    assert assess_checkpoint(10, 1.5, 0, 0).final == N


def test_override_flag():
    assert assess_checkpoint(40, 0, 0, 45_000).load_override_applied
    assert not assess_checkpoint(40, 0, 0, 10_000).load_override_applied


def test_partial_and_total_missing():
    r = assess_checkpoint(30, None, 0, 0)
    assert r.final == M and not r.complete
    assert assess_checkpoint(None, None, None, 0).final is None
    # Override still applies from known wind when other values are missing
    assert assess_checkpoint(50, None, None, 31_000).final == N


@pytest.mark.parametrize("load", [-1, math.nan, math.inf, None])
def test_bad_load(load):
    with pytest.raises(ValueError):
        assess_checkpoint(1, 0, 0, load)
