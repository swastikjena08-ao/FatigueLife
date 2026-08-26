import pytest

from fatiguelife.notch import local_stress_pa
from fatiguelife.goodman import GoodmanInvalidError, equivalent_fully_reversed_pa


def test_kf_scales_local_stress():
    assert local_stress_pa(100.0e6, 1.5) == pytest.approx(150.0e6)
    assert local_stress_pa(100.0e6, 2.0) > local_stress_pa(100.0e6, 1.5)


def test_kf_below_one_rejected():
    with pytest.raises(ValueError):
        local_stress_pa(100.0e6, 0.9)


def test_tensile_mean_stress_raises_equivalent_stress():
    zero_mean = equivalent_fully_reversed_pa(100.0e6, 0.0, 400.0e6)
    tensile = equivalent_fully_reversed_pa(100.0e6, 100.0e6, 400.0e6)
    assert zero_mean == pytest.approx(100.0e6)
    assert tensile == pytest.approx(100.0e6 / 0.75)
    assert tensile > zero_mean


def test_compressive_mean_gets_no_credit():
    compressive = equivalent_fully_reversed_pa(100.0e6, -50.0e6, 400.0e6)
    assert compressive == pytest.approx(100.0e6)


def test_mean_at_or_above_sut_is_invalid():
    with pytest.raises(GoodmanInvalidError):
        equivalent_fully_reversed_pa(100.0e6, 400.0e6, 400.0e6)
