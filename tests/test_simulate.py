import dataclasses

import pytest

from fatiguelife.geometry import Geometry
from fatiguelife.loading import Loading
from fatiguelife.materials import PRESETS
from fatiguelife.simulate import FatigueParams, ResultStatus, run

GEOM = Geometry(0.1, 0.02, 0.005)
LOAD = Loading(alternating_load_n=30.0, mean_load_n=20.0, frequency_hz=10.0)
MAT = PRESETS["illustrative_aluminium"]
PARAMS = FatigueParams(
    notch_factor=1.5, target_life_cycles=1.0e6, minimum_yield_safety_factor=1.5
)


def test_baseline_runs_and_is_labelled_illustrative():
    r = run(GEOM, LOAD, MAT, PARAMS)
    assert r.status is ResultStatus.WARNING_ILLUSTRATIVE
    assert r.fatigue_life_cycles is not None and r.fatigue_life_cycles > 0
    assert r.badge() == "Warning"


def test_increasing_pa_reduces_life():
    hi = run(GEOM, Loading(60.0, 20.0, 10.0), MAT, PARAMS)
    lo = run(GEOM, LOAD, MAT, PARAMS)
    assert hi.fatigue_life_cycles < lo.fatigue_life_cycles


def test_increasing_thickness_increases_life():
    thick = run(Geometry(0.1, 0.02, 0.010), LOAD, MAT, PARAMS)
    thin = run(GEOM, LOAD, MAT, PARAMS)
    assert thick.fatigue_life_cycles > thin.fatigue_life_cycles


def test_increasing_kf_reduces_life():
    sharp = run(GEOM, LOAD, MAT, dataclasses.replace(PARAMS, notch_factor=2.5))
    mild = run(GEOM, LOAD, MAT, PARAMS)
    assert sharp.fatigue_life_cycles < mild.fatigue_life_cycles


def test_yield_risk_triggers_warning():
    # Large load -> sigma_max_local >= Sy while sigma_m_local stays below Sut
    r = run(GEOM, Loading(400.0, 0.0, 10.0), MAT, PARAMS)
    assert any("yield" in w.lower() for w in r.warnings)
    assert r.badge() == "Warning"


def test_mean_local_stress_at_sut_is_invalid():
    r = run(GEOM, Loading(10.0, 900.0, 10.0), MAT, PARAMS)
    assert r.status is ResultStatus.INVALID
    assert r.fatigue_life_cycles is None


def test_bad_geometry_is_invalid():
    r = run(Geometry(0.1, -0.02, 0.005), LOAD, MAT, PARAMS)
    assert r.status is ResultStatus.INVALID
