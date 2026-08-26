import pytest

from fatiguelife.materials import MaterialError, PRESETS, is_vague_name, material_from_dict

GOOD_CUSTOM = {
    "name": "AA6061-T6",
    "product_form": "extruded bar",
    "heat_treatment": "T6",
    "surface_condition": "machined",
    "environment": "lab air, room temperature",
    "stress_ratio_r": -1.0,
    "density_kg_m3": 2700.0,
    "youngs_modulus_gpa": 68.9,
    "yield_strength_mpa": 276.0,
    "ultimate_strength_mpa": 310.0,
    "basquin_coefficient_mpa": 620.0,
    "basquin_exponent": -0.12,
    "life_range_min_cycles": 1.0e3,
    "life_range_max_cycles": 1.0e8,
    "source": "Example datasheet reference, user-reviewed",
    "confidence": "moderate",
}


def test_presets_exist_and_are_illustrative():
    assert set(PRESETS) == {
        "illustrative_aluminium",
        "illustrative_mild_steel",
        "illustrative_stainless_steel",
    }
    for m in PRESETS.values():
        assert m.confidence == "illustrative"
        assert m.validation_errors() == []


def test_vague_names_detected():
    for name in ("steel", "Aluminium", "stainless steel", "metal", "alloy"):
        assert is_vague_name(name)
    assert not is_vague_name("AA6061-T6")
    assert not is_vague_name("AISI 4340, quenched and tempered")


def test_vague_custom_material_rejected():
    data = dict(GOOD_CUSTOM, name="steel")
    with pytest.raises(MaterialError, match="exact grade/alloy"):
        material_from_dict(data)


def test_missing_citation_rejected():
    data = {k: v for k, v in GOOD_CUSTOM.items() if k != "source"}
    with pytest.raises(MaterialError, match="source"):
        material_from_dict(data)


def test_missing_condition_metadata_rejected():
    data = {k: v for k, v in GOOD_CUSTOM.items() if k != "heat_treatment"}
    with pytest.raises(MaterialError, match="heat_treatment"):
        material_from_dict(data)


def test_unknown_key_rejected():
    data = dict(GOOD_CUSTOM, hardness_hb=95)
    with pytest.raises(MaterialError, match="hardness_hb"):
        material_from_dict(data)


def test_valid_custom_material_converts_units():
    m = material_from_dict(GOOD_CUSTOM)
    assert m.yield_strength_pa == pytest.approx(276.0e6)
    assert m.basquin_coefficient_pa == pytest.approx(620.0e6)


def test_sn_points_fit_recovers_basquin():
    # Points generated from A=620 MPa, b=-0.12 must fit back to the same values.
    pts = [[620.0 * n**-0.12, n] for n in (1e4, 1e5, 1e6, 1e7)]
    data = {
        k: v
        for k, v in GOOD_CUSTOM.items()
        if k not in ("basquin_coefficient_mpa", "basquin_exponent")
    }
    data["sn_points_mpa_cycles"] = pts
    m = material_from_dict(data)
    assert m.basquin_coefficient_pa == pytest.approx(620.0e6, rel=1e-6)
    assert m.basquin_exponent == pytest.approx(-0.12, rel=1e-6)
