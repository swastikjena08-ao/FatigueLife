"""Basquin stress-life relation: sigma_a_eq = A * Nf^b (b < 0)."""


def _check(coefficient_a_pa: float, exponent_b: float) -> None:
    if coefficient_a_pa <= 0.0:
        raise ValueError(f"Basquin coefficient A must be positive; got {coefficient_a_pa:.3g}.")
    if exponent_b >= 0.0:
        raise ValueError(f"Basquin exponent b must be negative; got {exponent_b:.3g}.")


def life_cycles(sigma_a_eq_pa: float, coefficient_a_pa: float, exponent_b: float) -> float:
    """Predicted fatigue initiation life Nf = (sigma_a_eq / A)^(1/b)."""
    _check(coefficient_a_pa, exponent_b)
    if sigma_a_eq_pa <= 0.0:
        raise ValueError(f"Equivalent stress must be positive; got {sigma_a_eq_pa:.3g} Pa.")
    return (sigma_a_eq_pa / coefficient_a_pa) ** (1.0 / exponent_b)


def stress_at_life_pa(n_cycles: float, coefficient_a_pa: float, exponent_b: float) -> float:
    """Alternating stress amplitude on the Basquin curve at a given life."""
    _check(coefficient_a_pa, exponent_b)
    if n_cycles <= 0.0:
        raise ValueError(f"Life must be positive; got {n_cycles:.3g} cycles.")
    return coefficient_a_pa * n_cycles**exponent_b
