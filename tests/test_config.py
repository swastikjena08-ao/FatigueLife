import json

import pytest

from fatiguelife.config import ConfigError, load_config


def test_baseline_yaml_loads():
    cfg = load_config("configs/baseline.yaml")
    assert cfg.geometry.length_m == pytest.approx(0.1)
    assert cfg.loading.alternating_load_n == 30
    assert cfg.material.name == "Illustrative Aluminium Alloy"
    assert cfg.fatigue.notch_factor == 1.5
    assert cfg.optimization is not None and cfg.optimization.grid_points == 60


def _base_dict():
    return {
        "project": {"title": "x"},
        "geometry": {"length_mm": 100, "width_mm": 20, "thickness_mm": 5},
        "loading": {"alternating_load_n": 30, "mean_load_n": 0, "frequency_hz": 10},
        "material": {"preset": "illustrative_aluminium"},
        "fatigue": {"notch_factor": 1.5, "target_life_cycles": 1e6,
                    "minimum_yield_safety_factor": 1.5},
    }


def test_unknown_key_raises_clear_error(tmp_path):
    bad = _base_dict()
    bad["geometry"]["depth_mm"] = 3
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad))
    with pytest.raises(ConfigError, match="depth_mm"):
        load_config(p)


def test_missing_required_key_raises(tmp_path):
    bad = _base_dict()
    del bad["geometry"]["thickness_mm"]
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad))
    with pytest.raises(ConfigError, match="thickness_mm"):
        load_config(p)


def test_json_config_works_without_yaml(tmp_path):
    good = _base_dict()
    good["project"]["title"] = "json run"
    p = tmp_path / "run.json"
    p.write_text(json.dumps(good))
    assert load_config(p).title == "json run"


def test_unknown_preset_lists_available(tmp_path):
    bad = _base_dict()
    bad["material"] = {"preset": "unobtainium"}
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad))
    with pytest.raises(ConfigError, match="illustrative_aluminium"):
        load_config(p)


def test_all_shipped_configs_load():
    for name in ("baseline", "aluminium_bracket", "steel_bracket",
                 "high_mean_load", "optimization"):
        load_config(f"configs/{name}.yaml")
