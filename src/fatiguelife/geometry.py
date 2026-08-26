"""Rectangular cantilever beam geometry (SI units internally)."""
from dataclasses import dataclass

from fatiguelife.units import m_to_mm


@dataclass(frozen=True)
class Geometry:
    """Rectangular cantilever: length L, width b, thickness h (metres)."""

    length_m: float
    width_m: float
    thickness_m: float

    def validation_errors(self) -> list[str]:
        """Return human-readable errors for non-positive dimensions."""
        errors: list[str] = []
        for name, value in (
            ("length", self.length_m),
            ("width", self.width_m),
            ("thickness", self.thickness_m),
        ):
            if value <= 0.0:
                errors.append(
                    f"Beam {name} must be positive; got {m_to_mm(value):.3g} mm."
                )
        return errors

    def second_moment_m4(self) -> float:
        """Second moment of area I = b*h^3/12 for a rectangular section."""
        return self.width_m * self.thickness_m**3 / 12.0

    def mass_kg(self, density_kg_m3: float) -> float:
        """Beam mass = rho * L * b * h."""
        return density_kg_m3 * self.length_m * self.width_m * self.thickness_m
