"""Local sensitivity of predicted fatigue life to each input parameter.

Uses central log-log elasticities d ln(Nf) / d ln(x) where the parameter is
strictly positive, and an absolute finite-difference sensitivity for a mean
load that currently sits at zero.
"""
import math
from dataclasses import dataclass

from fatiguelife.config import Config
from fatiguelife.sweep import PARAM_SPECS, simulate_config

ELASTICITY_PARAMS = ("alternating_load_n", "thickness_mm", "width_mm",
                     "length_mm", "notch_factor")


@dataclass
class SensitivityResult:
    parameter: str
    kind: str  # "elasticity" or "absolute"
    value: float | None
    interpretation: str


def _life(cfg: Config) -> float | None:
    return simulate_config(cfg).fatigue_life_cycles


def _elasticity(cfg: Config, parameter: str) -> float | None:
    spec = PARAM_SPECS[parameter]
    x = spec.getter(cfg)
    if x <= 0.0:
        return None
    life_hi = _life(spec.apply(cfg, 1.05 * x))
    life_lo = _life(spec.apply(cfg, 0.95 * x))
    if not life_hi or not life_lo:
        return None
    return (math.log(life_hi) - math.log(life_lo)) / (math.log(1.05 * x) - math.log(0.95 * x))


def _absolute_mean_load(cfg: Config) -> float | None:
    spec = PARAM_SPECS["mean_load_n"]
    delta = 0.05 * max(cfg.loading.alternating_load_n, 1.0)
    life_hi = _life(spec.apply(cfg, cfg.loading.mean_load_n + delta))
    life_lo = _life(spec.apply(cfg, cfg.loading.mean_load_n - delta))
    if not life_hi or not life_lo:
        return None
    return (life_hi - life_lo) / (2.0 * delta)


def run_sensitivity(cfg: Config) -> list[SensitivityResult]:
    """Rank parameters by how strongly they move the predicted life."""
    results: list[SensitivityResult] = []

    for parameter in ELASTICITY_PARAMS:
        value = _elasticity(cfg, parameter)
        label = PARAM_SPECS[parameter].label
        if value is None:
            text = (f"{label}: sensitivity unavailable (a perturbed run produced "
                    "no valid fatigue prediction).")
        else:
            text = (f"A 1% increase in {label} changes predicted life by about "
                    f"{value:+.1f}%.")
        results.append(SensitivityResult(parameter, "elasticity", value, text))

    pm = cfg.loading.mean_load_n
    label = PARAM_SPECS["mean_load_n"].label
    if pm != 0.0:
        value = _elasticity(cfg, "mean_load_n") if pm > 0 else None
        if value is None:
            value = _absolute_mean_load(cfg)
            kind = "absolute"
            text = (f"{label}: adding 1 N of mean load changes predicted life by "
                    f"about {value:.3g} cycles." if value is not None else
                    f"{label}: sensitivity unavailable near this operating point.")
        else:
            kind = "elasticity"
            text = (f"A 1% increase in {label} changes predicted life by about "
                    f"{value:+.1f}%.")
    else:
        kind = "absolute"
        value = _absolute_mean_load(cfg)
        text = (f"{label} is currently zero; adding 1 N of mean load changes "
                f"predicted life by about {value:.3g} cycles." if value is not None
                else f"{label}: sensitivity unavailable near this operating point.")
    results.append(SensitivityResult("mean_load_n", kind, value, text))

    results.sort(key=lambda r: (r.value is None, -abs(r.value) if r.value is not None else 0.0))
    return results
