"""Material data, illustrative presets, and custom-dataset validation."""
from dataclasses import dataclass

import numpy as np


class MaterialError(ValueError):
    """Raised when a material dataset is vague, incomplete, or inconsistent."""


VAGUE_MESSAGE = "Please specify an exact grade/alloy and fatigue dataset conditions."

VAGUE_EXACT = {
    "steel", "mild steel", "stainless", "stainless steel", "aluminium",
    "aluminum", "alloy", "metal", "iron", "titanium",
    "aluminium alloy", "aluminum alloy", "steel alloy",
}
GENERIC_WORDS = {
    "steel", "aluminium", "aluminum", "stainless", "metal", "alloy",
    "iron", "titanium", "brass", "copper",
}

CONFIDENCE_LABELS = ("high", "moderate", "low", "illustrative")


def is_vague_name(name: str) -> bool:
    """True when a material name is too generic to identify a fatigue dataset."""
    n = " ".join(name.lower().split())
    if n in VAGUE_EXACT:
        return True
    words = n.replace("-", " ").split()
    has_digit = any(ch.isdigit() for ch in n)
    return (not has_digit) and len(words) == 1 and words[0] in GENERIC_WORDS


@dataclass(frozen=True)
class Material:
    """A fatigue material dataset with full provenance metadata (SI units)."""

    name: str
    density_kg_m3: float
    youngs_modulus_pa: float
    yield_strength_pa: float
    ultimate_strength_pa: float
    basquin_coefficient_pa: float
    basquin_exponent: float
    life_range_min_cycles: float
    life_range_max_cycles: float
    product_form: str
    heat_treatment: str
    surface_condition: str
    environment: str
    stress_ratio_r: float
    source: str
    confidence: str
    condition_note: str = ""
    notes: str = ""

    def validation_errors(self) -> list[str]:
        errors: list[str] = []
        if self.density_kg_m3 <= 0.0:
            errors.append(f"Density must be positive; got {self.density_kg_m3:.3g} kg/m^3.")
        if self.yield_strength_pa <= 0.0:
            errors.append("Yield strength Sy must be positive.")
        if self.ultimate_strength_pa <= 0.0:
            errors.append("Ultimate strength Sut must be positive.")
        if self.basquin_coefficient_pa <= 0.0:
            errors.append("Basquin coefficient A must be positive.")
        if self.basquin_exponent >= 0.0:
            errors.append(
                f"Basquin exponent b must be negative; got {self.basquin_exponent:.3g}."
            )
        if self.life_range_min_cycles <= 0.0 or self.life_range_max_cycles <= self.life_range_min_cycles:
            errors.append("Applicable life range must satisfy 0 < min < max cycles.")
        if self.confidence not in CONFIDENCE_LABELS:
            errors.append(
                f"Confidence label must be one of {CONFIDENCE_LABELS}; got {self.confidence!r}."
            )
        return errors

    def is_condition_complete(self) -> bool:
        """False when any condition field is empty or 'unspecified'."""
        fields = (self.product_form, self.heat_treatment,
                  self.surface_condition, self.environment)
        return all(f and f.strip().lower() != "unspecified" for f in fields)

    def as_display_dict(self) -> dict:
        """Friendly-units dict for reports, exports, and the dashboard."""
        return {
            "name": self.name,
            "density_kg_m3": self.density_kg_m3,
            "youngs_modulus_gpa": self.youngs_modulus_pa / 1e9,
            "yield_strength_mpa": self.yield_strength_pa / 1e6,
            "ultimate_strength_mpa": self.ultimate_strength_pa / 1e6,
            "basquin_coefficient_mpa": self.basquin_coefficient_pa / 1e6,
            "basquin_exponent": self.basquin_exponent,
            "life_range_min_cycles": self.life_range_min_cycles,
            "life_range_max_cycles": self.life_range_max_cycles,
            "product_form": self.product_form,
            "heat_treatment": self.heat_treatment,
            "surface_condition": self.surface_condition,
            "environment": self.environment,
            "stress_ratio_r": self.stress_ratio_r,
            "source": self.source,
            "confidence": self.confidence,
            "condition_note": self.condition_note,
            "notes": self.notes,
        }


_ILLUSTRATIVE_SOURCE = (
    "Illustrative textbook-style values for educational comparison only; "
    "not a measured dataset."
)


def _preset(name: str, rho: float, e_gpa: float, sy_mpa: float, sut_mpa: float,
            a_mpa: float, b: float, n_min: float, n_max: float, note: str) -> Material:
    return Material(
        name=name,
        density_kg_m3=rho,
        youngs_modulus_pa=e_gpa * 1e9,
        yield_strength_pa=sy_mpa * 1e6,
        ultimate_strength_pa=sut_mpa * 1e6,
        basquin_coefficient_pa=a_mpa * 1e6,
        basquin_exponent=b,
        life_range_min_cycles=n_min,
        life_range_max_cycles=n_max,
        product_form="illustrative",
        heat_treatment="illustrative",
        surface_condition="illustrative",
        environment="illustrative",
        stress_ratio_r=-1.0,
        source=_ILLUSTRATIVE_SOURCE,
        confidence="illustrative",
        condition_note=note,
    )


PRESETS: dict[str, Material] = {
    "illustrative_aluminium": _preset(
        "Illustrative Aluminium Alloy", 2700.0, 70.0, 240.0, 310.0, 620.0, -0.15,
        1e3, 1e8,
        "Order-of-magnitude values loosely representative of a wrought aluminium "
        "alloy in laboratory air; for comparative studies only.",
    ),
    "illustrative_mild_steel": _preset(
        "Illustrative Mild Steel", 7850.0, 200.0, 250.0, 420.0, 900.0, -0.11,
        1e4, 1e8,
        "Order-of-magnitude values loosely representative of a low-carbon "
        "structural steel in laboratory air; for comparative studies only.",
    ),
    "illustrative_stainless_steel": _preset(
        "Illustrative Stainless Steel", 8000.0, 193.0, 290.0, 620.0, 1100.0, -0.12,
        1e4, 1e8,
        "Order-of-magnitude values loosely representative of an austenitic "
        "stainless steel in laboratory air; for comparative studies only.",
    ),
}


_REQUIRED_KEYS = (
    "name", "product_form", "heat_treatment", "surface_condition", "environment",
    "stress_ratio_r", "density_kg_m3", "youngs_modulus_gpa", "yield_strength_mpa",
    "ultimate_strength_mpa", "life_range_min_cycles", "life_range_max_cycles",
    "source", "confidence",
)
_OPTIONAL_KEYS = (
    "basquin_coefficient_mpa", "basquin_exponent", "sn_points_mpa_cycles",
    "condition_note", "notes",
)
ALLOWED_KEYS = frozenset(_REQUIRED_KEYS) | frozenset(_OPTIONAL_KEYS)


def _fit_basquin_mpa(points: list) -> tuple[float, float]:
    """Least-squares fit of log(S) = log(A) + b*log(N) to [stress_mpa, cycles] pairs."""
    if not isinstance(points, list) or len(points) < 2:
        raise MaterialError("sn_points_mpa_cycles needs at least 2 [stress_mpa, cycles] points.")
    stresses = np.array([p[0] for p in points], dtype=float)
    cycles = np.array([p[1] for p in points], dtype=float)
    if np.any(stresses <= 0) or np.any(cycles <= 0):
        raise MaterialError("S-N points must have positive stress (MPa) and cycles.")
    slope, intercept = np.polyfit(np.log(cycles), np.log(stresses), 1)
    return float(np.exp(intercept)), float(slope)


def material_from_dict(data: dict) -> Material:
    """Build a Material from a user-supplied dict (friendly units), strictly.

    Rejects unknown keys, missing required metadata (all reported at once),
    and vague material names. Requires either Basquin A + b or S-N points.
    """
    extra = sorted(set(data) - ALLOWED_KEYS)
    if extra:
        raise MaterialError(
            f"Unknown material key(s): {extra}. Allowed keys: {sorted(ALLOWED_KEYS)}."
        )

    missing = [k for k in _REQUIRED_KEYS if k not in data or data[k] in (None, "")]
    if missing:
        raise MaterialError(
            "Missing required material metadata: " + ", ".join(missing) + ". "
            "Custom fatigue datasets require full condition metadata and a source citation."
        )

    name = str(data["name"])
    if is_vague_name(name):
        raise MaterialError(VAGUE_MESSAGE)

    has_ab = "basquin_coefficient_mpa" in data and "basquin_exponent" in data
    has_pts = "sn_points_mpa_cycles" in data
    if has_ab and has_pts:
        raise MaterialError(
            "Provide either basquin_coefficient_mpa + basquin_exponent OR "
            "sn_points_mpa_cycles, not both."
        )
    if has_ab:
        a_mpa = float(data["basquin_coefficient_mpa"])
        b = float(data["basquin_exponent"])
    elif has_pts:
        a_mpa, b = _fit_basquin_mpa(data["sn_points_mpa_cycles"])
    else:
        raise MaterialError(
            "Provide fatigue data: basquin_coefficient_mpa + basquin_exponent, "
            "or sn_points_mpa_cycles."
        )

    confidence = str(data["confidence"]).strip().lower()

    try:
        material = Material(
            name=name,
            density_kg_m3=float(data["density_kg_m3"]),
            youngs_modulus_pa=float(data["youngs_modulus_gpa"]) * 1e9,
            yield_strength_pa=float(data["yield_strength_mpa"]) * 1e6,
            ultimate_strength_pa=float(data["ultimate_strength_mpa"]) * 1e6,
            basquin_coefficient_pa=a_mpa * 1e6,
            basquin_exponent=b,
            life_range_min_cycles=float(data["life_range_min_cycles"]),
            life_range_max_cycles=float(data["life_range_max_cycles"]),
            product_form=str(data["product_form"]),
            heat_treatment=str(data["heat_treatment"]),
            surface_condition=str(data["surface_condition"]),
            environment=str(data["environment"]),
            stress_ratio_r=float(data["stress_ratio_r"]),
            source=str(data["source"]),
            confidence=confidence,
            condition_note=str(data.get("condition_note", "")),
            notes=str(data.get("notes", "")),
        )
    except (TypeError, ValueError) as exc:
        raise MaterialError(f"Material field has wrong type: {exc}") from exc

    errors = material.validation_errors()
    if errors:
        raise MaterialError("Invalid material dataset: " + " ".join(errors))
    return material
