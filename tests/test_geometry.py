import pytest

from fatiguelife.geometry import Geometry


def test_second_moment_matches_bh3_over_12():
    g = Geometry(length_m=0.1, width_m=0.02, thickness_m=0.005)
    assert g.second_moment_m4() == pytest.approx(0.02 * 0.005**3 / 12.0)


def test_mass():
    g = Geometry(length_m=0.1, width_m=0.02, thickness_m=0.005)
    assert g.mass_kg(2700.0) == pytest.approx(2700.0 * 0.1 * 0.02 * 0.005)


def test_nonpositive_dimension_reports_error():
    g = Geometry(length_m=0.1, width_m=0.0, thickness_m=0.005)
    errs = g.validation_errors()
    assert errs and "width" in errs[0].lower()
