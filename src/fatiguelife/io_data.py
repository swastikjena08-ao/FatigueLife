"""Write simulation, sweep, and sizing results as CSV or JSON."""
import csv
import json
from pathlib import Path

from fatiguelife import SCOPE_STATEMENT
from fatiguelife.config import Config
from fatiguelife.design import SizingResult
from fatiguelife.materials import Material
from fatiguelife.simulate import SimulationResult
from fatiguelife.sweep import SweepPoint
from fatiguelife.units import kg_to_g, pa_to_mpa


def summary_dict(cfg: Config, result: SimulationResult) -> dict:
    """Full single-run summary: config echo, material provenance, results."""
    def mpa(value_pa: float | None) -> float | None:
        return pa_to_mpa(value_pa) if value_pa is not None else None

    return {
        "scope_statement": SCOPE_STATEMENT,
        "title": cfg.title,
        "config": cfg.raw,
        "material": result.material.as_display_dict(),
        "results": {
            "status": result.status.label,
            "badge": result.badge(),
            "fatigue_life_cycles": result.fatigue_life_cycles,
            "meets_target_life": result.meets_target_life,
            "mass_kg": result.mass_kg,
            "mass_g": kg_to_g(result.mass_kg),
            "nominal_alternating_stress_mpa": mpa(result.nominal_alternating_stress_pa),
            "nominal_mean_stress_mpa": mpa(result.nominal_mean_stress_pa),
            "local_alternating_stress_mpa": mpa(result.local_alternating_stress_pa),
            "local_mean_stress_mpa": mpa(result.local_mean_stress_pa),
            "goodman_equivalent_stress_mpa": mpa(result.goodman_equivalent_stress_pa),
            "max_local_stress_mpa": mpa(result.max_local_stress_pa),
            "yield_safety_factor": result.yield_safety_factor,
            "meets_yield_requirement": result.meets_yield_requirement,
        },
        "warnings": list(result.warnings),
        "errors": list(result.errors),
    }


def _flatten(data: dict, prefix: str = "") -> list[tuple[str, object]]:
    rows: list[tuple[str, object]] = []
    for key, value in data.items():
        name = f"{prefix}{key}"
        if isinstance(value, dict):
            rows.extend(_flatten(value, name + "."))
        elif isinstance(value, list):
            rows.append((name, "; ".join(str(v) for v in value)))
        else:
            rows.append((name, value))
    return rows


def write_summary_json(cfg: Config, result: SimulationResult, path: str | Path) -> Path:
    path = Path(path)
    path.write_text(json.dumps(summary_dict(cfg, result), indent=2) + "\n")
    return path


def write_summary_csv(cfg: Config, result: SimulationResult, path: str | Path) -> Path:
    path = Path(path)
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["key", "value"])
        for key, value in _flatten(summary_dict(cfg, result)):
            writer.writerow([key, value])
    return path


def _provenance_header(material: Material) -> str:
    return (
        f"# material: {material.name}\n"
        f"# source: {material.source}\n"
        f"# confidence: {material.confidence}\n"
        f"# scope: {SCOPE_STATEMENT}\n"
    )


def write_sweep_csv(parameter: str, points: list[SweepPoint], material: Material,
                    path: str | Path) -> Path:
    path = Path(path)
    with path.open("w", newline="") as handle:
        handle.write(_provenance_header(material))
        handle.write(f"# parameter: {parameter}\n")
        writer = csv.writer(handle)
        writer.writerow(["value", "fatigue_life_cycles", "yield_safety_factor",
                         "status", "warnings"])
        for point in points:
            writer.writerow([
                point.value, point.fatigue_life_cycles, point.yield_safety_factor,
                point.status_badge, "; ".join(point.warnings),
            ])
    return path


def write_sizing_csv(result: SizingResult, material: Material, path: str | Path) -> Path:
    path = Path(path)
    with path.open("w", newline="") as handle:
        handle.write(_provenance_header(material))
        handle.write(f"# note: {result.note}\n")
        writer = csv.writer(handle)
        writer.writerow(["width_mm", "thickness_mm", "mass_kg",
                         "fatigue_life_cycles", "yield_safety_factor", "feasible"])
        for candidate in result.top:
            writer.writerow([
                candidate.width_mm, candidate.thickness_mm, candidate.mass_kg,
                candidate.fatigue_life_cycles, candidate.yield_safety_factor,
                candidate.feasible,
            ])
    return path
