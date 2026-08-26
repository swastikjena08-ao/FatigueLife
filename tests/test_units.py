from fatiguelife import units


def test_mm_m_roundtrip():
    assert units.mm_to_m(100.0) == 0.1
    assert units.m_to_mm(0.1) == 100.0


def test_stress_conversion():
    assert units.pa_to_mpa(3.6e7) == 36.0
    assert units.mpa_to_pa(36.0) == 3.6e7


def test_mass_conversion():
    assert units.kg_to_g(0.027) == 27.0


def test_format_cycles_scientific_above_1e5():
    assert units.format_cycles(5.1e6) == "5.10e+06"
    assert units.format_cycles(1234.0) == "1234"


def test_format_stress():
    assert units.format_stress_mpa(3.6e7) == "36.0 MPa"
