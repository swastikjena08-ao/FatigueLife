import pytest

from fatiguelife.geometry import Geometry
from fatiguelife.stress import bending_stress_pa

BASE = Geometry(length_m=0.1, width_m=0.02, thickness_m=0.005)


def test_hand_calculated_bending_stress():
    # sigma = 6*30*0.1 / (0.02*0.005^2) = 3.6e7 Pa = 36 MPa
    assert bending_stress_pa(30.0, BASE) == pytest.approx(3.6e7)


def test_doubling_load_doubles_stress():
    assert bending_stress_pa(60.0, BASE) == pytest.approx(2 * bending_stress_pa(30.0, BASE))


def test_doubling_length_doubles_stress():
    g2 = Geometry(length_m=0.2, width_m=0.02, thickness_m=0.005)
    assert bending_stress_pa(30.0, g2) == pytest.approx(2 * bending_stress_pa(30.0, BASE))


def test_doubling_width_halves_stress():
    g2 = Geometry(length_m=0.1, width_m=0.04, thickness_m=0.005)
    assert bending_stress_pa(30.0, g2) == pytest.approx(0.5 * bending_stress_pa(30.0, BASE))


def test_doubling_thickness_quarters_stress():
    g2 = Geometry(length_m=0.1, width_m=0.02, thickness_m=0.01)
    assert bending_stress_pa(30.0, g2) == pytest.approx(0.25 * bending_stress_pa(30.0, BASE))
