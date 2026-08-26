import dataclasses

from fatiguelife.config import load_config
from fatiguelife.design import run_sizing

CFG = load_config("configs/optimization.yaml")


def test_all_returned_designs_are_feasible():
    res = run_sizing(CFG)
    assert res.best is not None
    for c in [res.best, *res.top]:
        assert c.feasible
        assert c.fatigue_life_cycles >= CFG.fatigue.target_life_cycles
        assert c.yield_safety_factor >= CFG.fatigue.minimum_yield_safety_factor


def test_best_is_minimum_mass_and_top_sorted():
    res = run_sizing(CFG)
    masses = [c.mass_kg for c in res.top]
    assert masses == sorted(masses)
    assert res.best.mass_kg == masses[0]
    assert len(res.top) <= 10


def test_note_is_present():
    assert "not full shape optimization" in run_sizing(CFG).note


def test_infeasible_problem_returns_none_best():
    cfg = dataclasses.replace(
        CFG, fatigue=dataclasses.replace(CFG.fatigue, target_life_cycles=1e30)
    )
    res = run_sizing(cfg)
    assert res.best is None and res.top == [] and res.feasible_count == 0
