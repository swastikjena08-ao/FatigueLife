"""Nominal bending stress at the fixed end of a rectangular cantilever."""
from fatiguelife.geometry import Geometry


def bending_stress_pa(load_n: float, geom: Geometry) -> float:
    """sigma = 6*P*L / (b*h^2). Sign follows the sign of the load."""
    return 6.0 * load_n * geom.length_m / (geom.width_m * geom.thickness_m**2)
