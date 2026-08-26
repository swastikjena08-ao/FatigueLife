"""Run one bracket fatigue estimate and collect its warnings."""
import enum
from dataclasses import dataclass

from fatiguelife.basquin import life_cycles
from fatiguelife.geometry import Geometry
from fatiguelife.goodman import GoodmanInvalidError, equivalent_fully_reversed_pa
from fatiguelife.loading import Loading
from fatiguelife.materials import Material
from fatiguelife.notch import local_stress_pa
from fatiguelife.stress import bending_stress_pa
from fatiguelife.units import format_cycles, format_stress_mpa

ASSUMPTIONS: list[str] = [
    "Linear-elastic cantilever-beam theory (slender rectangular beam).",
    "Constant-amplitude uniaxial bending only.",
    "High-cycle stress-life (S-N) focus; low-cycle strain-life is out of scope.",
    "Basquin S-N model with a single coefficient A and exponent b.",
    "Modified Goodman mean-stress correction (simplified screening criterion); "
    "compressive mean stress is given no beneficial credit.",
    "Simplified notch treatment via a single user-supplied factor Kf; "
    "no FEA and no local notch-geometry calculation.",
    "Crack-initiation life only; no crack-growth (fracture mechanics) life.",
    "No Miner's rule or variable-amplitude loading in Version 1.",
    "No corrosion, temperature, residual stress, surface-finish correction, "
    "manufacturing defects, welding, or multiaxial load effects.",
    "No experimental validation: results are comparative, not certified predictions.",
]


class ResultStatus(enum.Enum):
    VALID = "Valid within selected model assumptions"
    WARNING_ILLUSTRATIVE = "Warning: illustrative data"
    WARNING_INCOMPLETE = "Warning: incomplete material-condition match"
    INVALID = "Invalid: no fatigue prediction available"

    @property
    def label(self) -> str:
        return self.value


@dataclass(frozen=True)
class FatigueParams:
    notch_factor: float
    target_life_cycles: float
    minimum_yield_safety_factor: float


@dataclass
class SimulationResult:
    status: ResultStatus
    warnings: list[str]
    errors: list[str]
    material: Material
    mass_kg: float
    nominal_alternating_stress_pa: float | None = None
    nominal_mean_stress_pa: float | None = None
    local_alternating_stress_pa: float | None = None
    local_mean_stress_pa: float | None = None
    goodman_equivalent_stress_pa: float | None = None
    max_local_stress_pa: float | None = None
    yield_safety_factor: float | None = None
    fatigue_life_cycles: float | None = None
    meets_target_life: bool | None = None
    meets_yield_requirement: bool | None = None

    def badge(self) -> str:
        """Coarse Valid / Warning / Invalid label for the dashboard badge."""
        if self.status is ResultStatus.INVALID:
            return "Invalid"
        if self.status is not ResultStatus.VALID or self.warnings:
            return "Warning"
        return "Valid"


def run(geom: Geometry, load: Loading, material: Material,
        params: FatigueParams) -> SimulationResult:
    """Run one fatigue estimate; never raises for user-input problems."""
    errors: list[str] = []
    errors += geom.validation_errors()
    errors += load.validation_errors()
    errors += material.validation_errors()
    if params.notch_factor < 1.0:
        errors.append(f"Notch factor Kf must be >= 1; got {params.notch_factor:.3g}.")

    geometry_ok = not geom.validation_errors()
    mass = geom.mass_kg(material.density_kg_m3) if geometry_ok else 0.0

    if errors:
        return SimulationResult(
            status=ResultStatus.INVALID, warnings=[], errors=errors,
            material=material, mass_kg=mass,
        )

    sigma_a = bending_stress_pa(load.alternating_load_n, geom)
    sigma_m = bending_stress_pa(load.mean_load_n, geom)
    kf = params.notch_factor
    sigma_a_local = local_stress_pa(sigma_a, kf)
    sigma_m_local = local_stress_pa(sigma_m, kf)
    sigma_max_local = kf * (sigma_m + sigma_a)
    if sigma_max_local > 0.0:
        n_y = material.yield_strength_pa / sigma_max_local
    else:
        n_y = float("inf")

    result = SimulationResult(
        status=ResultStatus.VALID, warnings=[], errors=[],
        material=material, mass_kg=mass,
        nominal_alternating_stress_pa=sigma_a,
        nominal_mean_stress_pa=sigma_m,
        local_alternating_stress_pa=sigma_a_local,
        local_mean_stress_pa=sigma_m_local,
        max_local_stress_pa=sigma_max_local,
        yield_safety_factor=n_y,
    )

    try:
        sigma_a_eq = equivalent_fully_reversed_pa(
            sigma_a_local, sigma_m_local, material.ultimate_strength_pa
        )
    except GoodmanInvalidError:
        result.status = ResultStatus.INVALID
        result.errors.append(
            f"Mean local stress {format_stress_mpa(sigma_m_local)} is at or above "
            f"Sut {format_stress_mpa(material.ultimate_strength_pa)}: the Modified "
            "Goodman correction is invalid; no fatigue prediction available."
        )
        return result

    result.goodman_equivalent_stress_pa = sigma_a_eq

    if sigma_a_eq <= 0.0:
        result.status = ResultStatus.INVALID
        result.errors.append(
            "Equivalent alternating stress is zero or negative; no fatigue "
            "prediction available (is the alternating load zero?)."
        )
        return result

    life = life_cycles(sigma_a_eq, material.basquin_coefficient_pa,
                       material.basquin_exponent)
    result.fatigue_life_cycles = life
    result.meets_target_life = life >= params.target_life_cycles
    result.meets_yield_requirement = n_y >= params.minimum_yield_safety_factor

    if sigma_max_local >= material.yield_strength_pa:
        result.warnings.append(
            f"Static yield likely: maximum local stress "
            f"{format_stress_mpa(sigma_max_local)} is at or above the yield "
            f"strength {format_stress_mpa(material.yield_strength_pa)}."
        )
    if not (material.life_range_min_cycles <= life <= material.life_range_max_cycles):
        result.warnings.append(
            f"Predicted life {format_cycles(life)} cycles is outside the dataset's "
            f"applicable range ({format_cycles(material.life_range_min_cycles)} to "
            f"{format_cycles(material.life_range_max_cycles)} cycles); treat the "
            "number as extrapolation, not prediction."
        )
    if material.confidence == "illustrative":
        result.warnings.append(
            "Illustrative material data: results are for comparison only."
        )
        result.status = ResultStatus.WARNING_ILLUSTRATIVE
    elif not material.is_condition_complete() or material.confidence == "low":
        result.warnings.append(
            "Material condition metadata is incomplete or low-confidence; the "
            "dataset may not match the modelled component."
        )
        result.status = ResultStatus.WARNING_INCOMPLETE

    return result
