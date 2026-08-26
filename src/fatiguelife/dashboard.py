"""Serve the local dashboard and its JSON API."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources

import numpy as np

from fatiguelife import MATERIAL_NOTICE, SCOPE_STATEMENT
from fatiguelife.basquin import stress_at_life_pa
from fatiguelife.config import Config, ConfigError, config_from_dict
from fatiguelife.design import run_sizing
from fatiguelife.io_data import summary_dict
from fatiguelife.materials import MaterialError, PRESETS
from fatiguelife.sensitivity import run_sensitivity
from fatiguelife.simulate import ASSUMPTIONS
from fatiguelife.sweep import SWEEPABLE, run_sweep, simulate_config
from fatiguelife.units import m_to_mm, pa_to_mpa

BUILTIN_DEFAULTS = {
    "project": {"title": "Interactive fatigue study"},
    "geometry": {"length_mm": 100, "width_mm": 20, "thickness_mm": 5},
    "loading": {"alternating_load_n": 30, "mean_load_n": 20, "frequency_hz": 10},
    "material": {"preset": "illustrative_aluminium"},
    "fatigue": {"notch_factor": 1.5, "target_life_cycles": 1e6,
                "minimum_yield_safety_factor": 1.5},
    "optimization": {"width_min_mm": 5, "width_max_mm": 50, "thickness_min_mm": 1,
                     "thickness_max_mm": 20, "grid_points": 60},
}


def request_to_config(payload: dict) -> Config:
    """Translate a dashboard request body into a validated Config.

    Reuses the strict config path so unknown keys and vague materials fail
    with readable messages, never a server error.
    """
    if not isinstance(payload, dict):
        raise ConfigError("Request body must be a JSON object.")
    data = {
        "project": {"title": "dashboard request"},
        "geometry": payload.get("geometry", {}),
        "loading": payload.get("loading", {}),
        "material": payload.get("material", {}),
        "fatigue": payload.get("fatigue", {}),
    }
    if "optimization" in payload:
        data["optimization"] = payload["optimization"]
    from pathlib import Path

    return config_from_dict(data, base_dir=Path.cwd())


def _chart_data(cfg: Config, result_summary: dict) -> dict:
    """S-N curve samples and Goodman diagram values for the SVG charts."""
    material = cfg.material
    cycles = np.geomspace(material.life_range_min_cycles,
                          material.life_range_max_cycles, 60)
    stresses = [pa_to_mpa(stress_at_life_pa(float(n), material.basquin_coefficient_pa,
                                            material.basquin_exponent))
                for n in cycles]
    results = result_summary["results"]
    eq = results["goodman_equivalent_stress_mpa"]
    life = results["fatigue_life_cycles"]
    mean = results["local_mean_stress_mpa"]
    alt = results["local_alternating_stress_mpa"]
    sut = pa_to_mpa(material.ultimate_strength_pa)
    safe = None
    if mean is not None and alt is not None:
        margin = alt / pa_to_mpa(material.basquin_coefficient_pa)
        # Safe on the Goodman screening line anchored at the target-life strength:
        target_strength = pa_to_mpa(stress_at_life_pa(
            cfg.fatigue.target_life_cycles, material.basquin_coefficient_pa,
            material.basquin_exponent))
        safe = (mean < sut) and (alt <= target_strength * (1.0 - max(mean, 0.0) / sut))
    return {
        "sn_curve": {"cycles": [float(n) for n in cycles],
                     "stress_mpa": stresses},
        "operating_point": {"cycles": life, "stress_mpa": eq},
        "goodman": {
            "sut_mpa": sut,
            "sy_mpa": pa_to_mpa(material.yield_strength_pa),
            "target_life_strength_mpa": pa_to_mpa(stress_at_life_pa(
                cfg.fatigue.target_life_cycles, material.basquin_coefficient_pa,
                material.basquin_exponent)),
            "mean_mpa": mean, "alt_mpa": alt, "eq_mpa": eq, "safe": safe,
        },
    }


def _api_simulate(payload: dict) -> dict:
    cfg = request_to_config(payload)
    result = simulate_config(cfg)
    body = summary_dict(cfg, result)
    body.update(_chart_data(cfg, body))
    return body


def _api_sweep(payload: dict) -> dict:
    parameter = payload.pop("parameter", None)
    points = payload.pop("points", None)
    span = payload.pop("span_factor", None)
    if parameter not in SWEEPABLE:
        raise ConfigError(f"Unknown sweep parameter {parameter!r}; choose one of {list(SWEEPABLE)}.")
    cfg = request_to_config(payload)
    sweep_points = run_sweep(cfg, parameter,
                             points=int(points) if points else None,
                             span_factor=float(span) if span else None)
    return {
        "parameter": parameter,
        "points": [{
            "value": p.value,
            "life": p.fatigue_life_cycles,
            "ny": p.yield_safety_factor,
            "badge": p.status_badge,
            "warnings": p.warnings,
        } for p in sweep_points],
    }


def _api_sensitivity(payload: dict) -> dict:
    cfg = request_to_config(payload)
    return {"results": [{
        "parameter": r.parameter, "kind": r.kind, "value": r.value,
        "interpretation": r.interpretation,
    } for r in run_sensitivity(cfg)]}


def _api_optimize(payload: dict) -> dict:
    cfg = request_to_config(payload)
    if cfg.optimization is None:
        raise ConfigError("The optimize request needs an 'optimization' block.")
    res = run_sizing(cfg)

    def cand(c):
        return None if c is None else {
            "width_mm": c.width_mm, "thickness_mm": c.thickness_mm,
            "mass_kg": c.mass_kg, "life": c.fatigue_life_cycles,
            "ny": c.yield_safety_factor, "warnings": c.warnings,
        }

    return {"best": cand(res.best), "top": [cand(c) for c in res.top],
            "evaluated": res.evaluated, "feasible_count": res.feasible_count,
            "note": res.note}


def _api_materials(_payload: dict | None = None) -> dict:
    return {"presets": {key: m.as_display_dict() for key, m in PRESETS.items()},
            "notice": MATERIAL_NOTICE}


def _defaults_body(cfg: Config | None) -> dict:
    if cfg is None:
        raw = dict(BUILTIN_DEFAULTS)
    else:
        raw = cfg.raw
    body = json.loads(json.dumps(raw))  # deep copy, JSON-safe
    body.setdefault("optimization", BUILTIN_DEFAULTS["optimization"])
    return {
        **{k: body[k] for k in ("geometry", "loading", "material", "fatigue",
                                "optimization")},
        "title": body.get("project", {}).get("title", "Interactive fatigue study"),
        "assumptions": ASSUMPTIONS,
        "scope_statement": SCOPE_STATEMENT,
        "material_notice": MATERIAL_NOTICE,
        "sweepable": list(SWEEPABLE),
    }


def create_server(cfg: Config | None, port: int) -> ThreadingHTTPServer:
    """Build the dashboard server bound to 127.0.0.1 (port 0 = ephemeral)."""
    page = resources.files("fatiguelife").joinpath("dashboard.html").read_text(
        encoding="utf-8"
    )
    defaults = _defaults_body(cfg)
    post_routes = {
        "/api/simulate": _api_simulate,
        "/api/sweep": _api_sweep,
        "/api/sensitivity": _api_sensitivity,
        "/api/optimize": _api_optimize,
    }

    class ApiHandler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep test output quiet
            pass

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, status: int, data: dict) -> None:
            self._send(status, json.dumps(data).encode(), "application/json")

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self._send(200, page.encode(), "text/html; charset=utf-8")
            elif self.path == "/api/materials":
                self._send_json(200, _api_materials())
            elif self.path == "/api/defaults":
                self._send_json(200, defaults)
            elif self.path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
            else:
                self._send_json(404, {"error": f"Unknown path {self.path}"})

        def do_POST(self):
            handler = post_routes.get(self.path)
            if handler is None:
                self._send_json(404, {"error": f"Unknown API path {self.path}"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length) or b"{}")
                self._send_json(200, handler(payload))
            except (ConfigError, MaterialError, ValueError) as exc:
                self._send_json(400, {"error": str(exc)})
            except Exception as exc:  # pragma: no cover - defensive
                self._send_json(500, {"error": f"Internal error: {exc}"})

    return ThreadingHTTPServer(("127.0.0.1", port), ApiHandler)


def serve(cfg: Config | None, port: int) -> None:
    """Run the dashboard until interrupted."""
    server = create_server(cfg, port)
    host, actual_port = server.server_address
    print(f"Serving FatigueLife dashboard at http://{host}:{actual_port} "
          "- Ctrl+C to stop.")
    print(f"SCOPE: {SCOPE_STATEMENT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
