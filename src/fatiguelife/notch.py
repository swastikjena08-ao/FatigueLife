"""Simplified notch treatment: local stress = Kf * nominal stress.

Kf is a user-supplied fatigue stress-concentration factor. No local notch
geometry or FEA is performed.
"""


def local_stress_pa(nominal_pa: float, kf: float) -> float:
    """Scale a nominal stress by the fatigue notch factor Kf (>= 1)."""
    if kf < 1.0:
        raise ValueError(f"Notch factor Kf must be >= 1; got {kf:.3g}.")
    return kf * nominal_pa
