import json

from fatiguelife import io_data
from fatiguelife.config import load_config
from fatiguelife.simulate import run

CFG = load_config("configs/baseline.yaml")
RESULT = run(CFG.geometry, CFG.loading, CFG.material, CFG.fatigue)


def test_summary_json_includes_provenance(tmp_path):
    p = io_data.write_summary_json(CFG, RESULT, tmp_path / "s.json")
    data = json.loads(p.read_text())
    assert data["material"]["source"]
    assert data["material"]["confidence"] == "illustrative"
    assert "educational comparative model" in data["scope_statement"]


def test_summary_csv_includes_provenance(tmp_path):
    p = io_data.write_summary_csv(CFG, RESULT, tmp_path / "s.csv")
    text = p.read_text()
    assert "material.source" in text and "material.confidence" in text


def test_sweep_csv_has_provenance_header(tmp_path):
    from fatiguelife.sweep import run_sweep

    pts = run_sweep(CFG, "alternating_load_n", points=3)
    p = io_data.write_sweep_csv("alternating_load_n", pts, CFG.material, tmp_path / "sw.csv")
    text = p.read_text()
    assert text.startswith("# material:") and "# confidence: illustrative" in text


def test_sizing_csv_has_provenance_header(tmp_path):
    from fatiguelife.design import run_sizing

    res = run_sizing(load_config("configs/optimization.yaml"))
    p = io_data.write_sizing_csv(res, CFG.material, tmp_path / "sz.csv")
    text = p.read_text()
    assert text.startswith("# material:") and "width_mm" in text
