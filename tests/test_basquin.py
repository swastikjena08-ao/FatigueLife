import math

import pytest

from fatiguelife.basquin import life_cycles, stress_at_life_pa


def test_life_hand_calculation():
    # (62/620)^(1/-0.15) = 0.1^(-1/0.15) = 10^(1/0.15)
    assert life_cycles(62.0e6, 620.0e6, -0.15) == pytest.approx(10.0 ** (1.0 / 0.15))


def test_loglog_slope_equals_exponent():
    a, b = 620.0e6, -0.12
    n1, n2 = 1.0e4, 1.0e6
    s1, s2 = stress_at_life_pa(n1, a, b), stress_at_life_pa(n2, a, b)
    slope = (math.log(s2) - math.log(s1)) / (math.log(n2) - math.log(n1))
    assert slope == pytest.approx(b)


def test_higher_stress_means_shorter_life():
    assert life_cycles(120.0e6, 620.0e6, -0.12) < life_cycles(60.0e6, 620.0e6, -0.12)


def test_nonnegative_exponent_rejected():
    with pytest.raises(ValueError):
        life_cycles(100.0e6, 620.0e6, 0.1)
