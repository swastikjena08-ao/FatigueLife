"""Unit conversions and display formatting.

All physics modules work in SI units (m, N, Pa, kg, cycles); these helpers
convert to and from the friendly display units (mm, MPa, g) and format values
for reports.
"""


def mm_to_m(value_mm: float) -> float:
    return value_mm / 1000.0


def m_to_mm(value_m: float) -> float:
    return value_m * 1000.0


def pa_to_mpa(value_pa: float) -> float:
    return value_pa / 1.0e6


def mpa_to_pa(value_mpa: float) -> float:
    return value_mpa * 1.0e6


def kg_to_g(value_kg: float) -> float:
    return value_kg * 1000.0


def format_cycles(n_cycles: float) -> str:
    """Cycles as scientific notation at or above 1e5, plain integer below."""
    if n_cycles >= 1.0e5:
        return f"{n_cycles:.2e}"
    return f"{n_cycles:.0f}"


def format_stress_mpa(value_pa: float) -> str:
    return f"{pa_to_mpa(value_pa):.1f} MPa"
