import json
import threading
import urllib.error
import urllib.request

import pytest

from fatiguelife.config import load_config
from fatiguelife.dashboard import create_server


@pytest.fixture()
def server_url():
    cfg = load_config("configs/baseline.yaml")
    srv = create_server(cfg, port=0)  # ephemeral port
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _get(url):
    with urllib.request.urlopen(url, timeout=5) as r:
        return r.status, r.read().decode()


def _post(url, payload):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status, json.loads(r.read())


def _payload():
    return {
        "geometry": {"length_mm": 100, "width_mm": 20, "thickness_mm": 5},
        "loading": {"alternating_load_n": 30, "mean_load_n": 20, "frequency_hz": 10},
        "material": {"preset": "illustrative_aluminium"},
        "fatigue": {"notch_factor": 1.5, "target_life_cycles": 1e6,
                    "minimum_yield_safety_factor": 1.5},
    }


def test_page_serves_with_headings(server_url):
    status, html = _get(server_url + "/")
    assert status == 200
    for text in ("FatigueLife", "S–N Curve", "Goodman", "Assumptions and Limitations",
                 "educational comparative model"):
        assert text in html


def test_api_simulate_baseline(server_url):
    status, data = _post(server_url + "/api/simulate", _payload())
    assert status == 200
    assert data["results"]["fatigue_life_cycles"] > 0
    assert data["material"]["confidence"] == "illustrative"
    assert len(data["sn_curve"]["cycles"]) >= 10
    assert data["goodman"]["sut_mpa"] == pytest.approx(310.0)


def test_api_materials_lists_presets(server_url):
    status, body = _get(server_url + "/api/materials")
    assert status == 200 and "illustrative_aluminium" in body


def test_api_sweep_and_sensitivity_and_optimize(server_url):
    payload = _payload()
    payload["parameter"] = "thickness_mm"
    payload["points"] = 5
    payload["span_factor"] = 4
    status, data = _post(server_url + "/api/sweep", payload)
    assert status == 200 and len(data["points"]) == 5

    status, data = _post(server_url + "/api/sensitivity", _payload())
    assert status == 200 and any(r["parameter"] == "thickness_mm" for r in data["results"])

    payload = _payload()
    payload["optimization"] = {"width_min_mm": 5, "width_max_mm": 50,
                               "thickness_min_mm": 1, "thickness_max_mm": 20,
                               "grid_points": 20}
    status, data = _post(server_url + "/api/optimize", payload)
    assert status == 200 and data["best"] is not None
    assert "not full shape optimization" in data["note"]


def test_api_rejects_vague_custom_material(server_url):
    payload = _payload()
    payload["material"] = {"custom": {"name": "steel"}}
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(server_url + "/api/simulate", payload)
    assert exc.value.code == 400
    body = json.loads(exc.value.read())
    assert "exact grade/alloy" in body["error"] or "Missing" in body["error"]


def test_api_defaults_reflects_config(server_url):
    status, body = _get(server_url + "/api/defaults")
    assert status == 200
    data = json.loads(body)
    assert data["geometry"]["length_mm"] == 100
    assert data["assumptions"]
