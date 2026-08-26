import dataclasses

import pytest

from fatiguelife.config import load_config
from fatiguelife.loading import Loading
from fatiguelife.sensitivity import run_sensitivity
from fatiguelife.sweep import SWEEPABLE, run_sweep

CFG = load_config("configs/baseline.yaml")


def test_sweep_returns_requested_points_and_monotone_life():
    pts = run_sweep(CFG, "alternating_load_n", points=5)
    assert len(pts) == 5
    lives = [p.fatigue_life_cycles for p in pts if p.fatigue_life_cycles]
    assert lives == sorted(lives, reverse=True)  # more load -> less life


def test_sweep_range_is_centred_on_current_value():
    pts = run_sweep(CFG, "thickness_mm", points=9)
    values = [p.value for p in pts]
    assert values[0] == pytest.approx(5.0 / 4.0)
    assert values[-1] == pytest.approx(5.0 * 4.0)
    assert min(values) < 5.0 < max(values)


def test_all_sweepable_parameters_run():
    for parameter in SWEEPABLE:
        pts = run_sweep(CFG, parameter, points=3)
        assert len(pts) == 3


def test_unknown_parameter_rejected():
    with pytest.raises(ValueError, match="alternating_load_n"):
        run_sweep(CFG, "density")


def test_sensitivity_signs_and_ranking():
    results = {r.parameter: r for r in run_sensitivity(CFG)}
    assert results["alternating_load_n"].value < 0  # more load, less life
    assert results["thickness_mm"].value > 0        # thicker, more life
    assert results["notch_factor"].value < 0
    vals = [abs(r.value) for r in run_sensitivity(CFG) if r.value is not None]
    assert vals == sorted(vals, reverse=True)


def test_sensitivity_handles_zero_mean_load():
    cfg0 = dataclasses.replace(CFG, loading=Loading(30.0, 0.0, 10.0))
    r = {x.parameter: x for x in run_sensitivity(cfg0)}["mean_load_n"]
    assert r.kind == "absolute"
