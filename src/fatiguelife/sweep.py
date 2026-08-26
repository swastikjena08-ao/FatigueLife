"""Vary one input at a time and record life and yield safety factor."""
import dataclasses
from dataclasses import dataclass
from typing import Callable

import numpy as np

from fatiguelife.config import Config
from fatiguelife.simulate import SimulationResult, run
from fatiguelife.units import mm_to_m


@dataclass(frozen=True)
class ParamSpec:
    """How one sweepable parameter is read from and applied to a Config."""

    label: str
    unit: str
    getter: Callable[[Config], float]
    apply: Callable[[Config, float], Config]


def _set_geometry(cfg: Config, **kwargs) -> Config:
    return dataclasses.replace(cfg, geometry=dataclasses.replace(cfg.geometry, **kwargs))


def _set_loading(cfg: Config, **kwargs) -> Config:
    return dataclasses.replace(cfg, loading=dataclasses.replace(cfg.loading, **kwargs))


PARAM_SPECS: dict[str, ParamSpec] = {
    "alternating_load_n": ParamSpec(
        "Alternating load Pa", "N",
        lambda c: c.loading.alternating_load_n,
        lambda c, v: _set_loading(c, alternating_load_n=v),
    ),
    "mean_load_n": ParamSpec(
        "Mean load Pm", "N",
        lambda c: c.loading.mean_load_n,
        lambda c, v: _set_loading(c, mean_load_n=v),
    ),
    "thickness_mm": ParamSpec(
        "Thickness h", "mm",
        lambda c: c.geometry.thickness_m * 1000.0,
        lambda c, v: _set_geometry(c, thickness_m=mm_to_m(v)),
    ),
    "width_mm": ParamSpec(
        "Width b", "mm",
        lambda c: c.geometry.width_m * 1000.0,
        lambda c, v: _set_geometry(c, width_m=mm_to_m(v)),
    ),
    "length_mm": ParamSpec(
        "Length L", "mm",
        lambda c: c.geometry.length_m * 1000.0,
        lambda c, v: _set_geometry(c, length_m=mm_to_m(v)),
    ),
    "notch_factor": ParamSpec(
        "Notch factor Kf", "-",
        lambda c: c.fatigue.notch_factor,
        lambda c, v: dataclasses.replace(
            c, fatigue=dataclasses.replace(c.fatigue, notch_factor=max(v, 1.0))
        ),
    ),
}

SWEEPABLE: tuple[str, ...] = tuple(PARAM_SPECS)


@dataclass
class SweepPoint:
    value: float
    fatigue_life_cycles: float | None
    yield_safety_factor: float | None
    status_badge: str
    warnings: list[str]


def simulate_config(cfg: Config) -> SimulationResult:
    """Run the single-point simulation for a Config."""
    return run(cfg.geometry, cfg.loading, cfg.material, cfg.fatigue)


def run_sweep(cfg: Config, parameter: str, points: int | None = None,
              span_factor: float | None = None) -> list[SweepPoint]:
    """Sweep one parameter over a current-value-centred range."""
    if parameter not in PARAM_SPECS:
        raise ValueError(
            f"Unknown sweep parameter {parameter!r}. Choose one of: {list(SWEEPABLE)}."
        )
    spec = PARAM_SPECS[parameter]
    n = points if points is not None else cfg.study.sweep_points
    span = span_factor if span_factor is not None else cfg.study.sweep_span_factor
    current = spec.getter(cfg)
    if current > 0.0:
        values = np.geomspace(current / span, current * span, n)
    else:
        # Only mean load can meaningfully sit at zero; sweep it linearly up to Pa.
        upper = max(1.0, cfg.loading.alternating_load_n)
        values = np.linspace(0.0, upper, n)

    result_points: list[SweepPoint] = []
    for value in values:
        res = simulate_config(spec.apply(cfg, float(value)))
        result_points.append(SweepPoint(
            value=float(value),
            fatigue_life_cycles=res.fatigue_life_cycles,
            yield_safety_factor=res.yield_safety_factor,
            status_badge=res.badge(),
            warnings=list(res.warnings) + list(res.errors),
        ))
    return result_points
