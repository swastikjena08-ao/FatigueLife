"""Search a width-by-thickness grid for a light feasible design."""
import dataclasses
from dataclasses import dataclass

import numpy as np

from fatiguelife.config import Config, ConfigError
from fatiguelife.sweep import simulate_config
from fatiguelife.units import m_to_mm

GRID_NOTE = "This is a grid-based preliminary sizing study, not full shape optimization."


@dataclass
class DesignCandidate:
    width_mm: float
    thickness_mm: float
    mass_kg: float
    fatigue_life_cycles: float | None
    yield_safety_factor: float | None
    feasible: bool
    warnings: list[str]


@dataclass
class SizingResult:
    best: DesignCandidate | None
    top: list[DesignCandidate]
    evaluated: int
    feasible_count: int
    note: str = GRID_NOTE


def run_sizing(cfg: Config) -> SizingResult:
    """Evaluate the (width, thickness) grid and return the lightest feasible designs."""
    if cfg.optimization is None:
        raise ConfigError(
            "The sizing study needs an 'optimization' section in the config "
            "(width/thickness bounds and grid_points)."
        )
    opt = cfg.optimization
    widths = np.linspace(opt.width_min_m, opt.width_max_m, opt.grid_points)
    thicknesses = np.linspace(opt.thickness_min_m, opt.thickness_max_m, opt.grid_points)

    feasible: list[DesignCandidate] = []
    evaluated = 0
    for width_m in widths:
        for thickness_m in thicknesses:
            candidate_cfg = dataclasses.replace(
                cfg,
                geometry=dataclasses.replace(
                    cfg.geometry, width_m=float(width_m), thickness_m=float(thickness_m)
                ),
            )
            res = simulate_config(candidate_cfg)
            evaluated += 1
            ok = (
                res.fatigue_life_cycles is not None
                and res.yield_safety_factor is not None
                and res.fatigue_life_cycles >= cfg.fatigue.target_life_cycles
                and res.yield_safety_factor >= cfg.fatigue.minimum_yield_safety_factor
            )
            if ok:
                feasible.append(DesignCandidate(
                    width_mm=m_to_mm(float(width_m)),
                    thickness_mm=m_to_mm(float(thickness_m)),
                    mass_kg=res.mass_kg,
                    fatigue_life_cycles=res.fatigue_life_cycles,
                    yield_safety_factor=res.yield_safety_factor,
                    feasible=True,
                    warnings=list(res.warnings),
                ))

    feasible.sort(key=lambda c: c.mass_kg)
    top = feasible[:10]
    return SizingResult(
        best=top[0] if top else None,
        top=top,
        evaluated=evaluated,
        feasible_count=len(feasible),
    )
