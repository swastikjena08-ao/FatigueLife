# FatigueLife Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `fatiguelife`, a local-first Python tool (CLI + stdlib-served dashboard) that estimates high-cycle fatigue life of a rectangular cantilever bracket and supports parameter studies, sensitivity analysis, and minimum-mass sizing.

**Architecture:** Pure-Python physics core (dataclasses, one module per concern: geometry → stress → notch → Goodman → Basquin → simulate) consumed by three thin frontends: a strict config loader, an argparse CLI, and a stdlib `http.server` dashboard whose vanilla-JS page calls JSON endpoints. Calculations never live in frontend code.

**Tech Stack:** Python ≥ 3.10, numpy (only runtime dep), PyYAML (optional extra), pytest (dev only), stdlib `http.server` + vanilla HTML/CSS/JS/SVG.

**Spec:** `docs/superpowers/specs/2026-08-26-fatiguelife-design.md` (read it first; it carries the full validity rules, dashboard sections, and non-negotiables).

## Global Constraints

- Project root: `/home/adith/swastik/fatiguelife`. **No git repo** (user decision) — skip all commit steps; instead end every task by running the full test suite: `uv run pytest tests/ -q`.
- Python ≥ 3.10; `numpy` is the ONLY required runtime dependency; `pyyaml` optional extra `[yaml]`; JSON configs must work without PyYAML.
- SI units internally (m, N, Pa, kg, cycles); display units mm / MPa / g-kg / cycles (scientific notation ≥ 1e5).
- No external APIs, no scraping, no external JS/CSS libraries.
- Never claim data is "most accurate" or results certified/validated; the scope statement string must appear in dashboard, CLI output, and README:
  `"This is an educational comparative model. It uses simplified beam theory, Basquin S–N fatigue curves, Modified Goodman mean-stress correction, and a simplified notch factor. It does not provide certified component-life predictions or replace experimental fatigue testing."`
- Material-condition notice string (dashboard + CLI + README):
  `"Fatigue properties are condition-specific. Results depend on the selected dataset and may not apply to a real component."`
- Strict config validation: unknown keys are errors, never silently defaulted.
- Dataclasses, type hints, docstrings everywhere. Physics modules must not import dashboard/CLI modules.
- Compressive mean stress: Goodman denominator capped at 1 (no compressive credit) — documented in assumptions.
- All commands below run from the project root with `uv`.

---

### Task 1: Project skeleton, packaging, units module

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `src/fatiguelife/__init__.py`, `src/fatiguelife/units.py`, `tests/test_units.py`, `assets/.gitkeep`, `configs/.gitkeep`, `configs/materials/.gitkeep`

**Interfaces:**
- Produces: `units.mm_to_m(x)`, `units.m_to_mm(x)`, `units.pa_to_mpa(x)`, `units.mpa_to_pa(x)`, `units.kg_to_g(x)`, `units.format_cycles(n: float) -> str` (e.g. `"5.10e+06"` for n ≥ 1e5, `"12345"` below), `units.format_stress_mpa(pa: float) -> str` (e.g. `"36.0 MPa"`).

- [x] **Step 1: Create skeleton and pyproject**

```toml
# pyproject.toml
[project]
name = "fatiguelife"
version = "0.1.0"
description = "Educational computational framework for fatigue-life estimation of cyclically loaded cantilever brackets"
requires-python = ">=3.10"
dependencies = ["numpy>=1.24"]

[project.optional-dependencies]
yaml = ["pyyaml>=6.0"]

[dependency-groups]
dev = ["pytest>=8.0", "pyyaml>=6.0"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/fatiguelife"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`.gitignore`: `__pycache__/`, `.venv/`, `*.pyc`, `.pytest_cache/`, `out/`, `uv.lock` NOT ignored.
`src/fatiguelife/__init__.py`: `__version__ = "0.1.0"` plus the scope-statement constant `SCOPE_STATEMENT = "This is an educational comparative model. ..."` (full string from Global Constraints) and `MATERIAL_NOTICE = "Fatigue properties are condition-specific. ..."` (full string).

Run `uv sync --all-extras` in the project root to create the venv.

- [x] **Step 2: Write failing tests for units**

```python
# tests/test_units.py
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
```

- [x] **Step 3: Run tests, verify they fail** — `uv run pytest tests/test_units.py -q`, expected: import error / failures.

- [x] **Step 4: Implement `units.py`**

```python
"""Unit conversions and display formatting. SI internally; friendly units for display."""

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
    if n_cycles >= 1.0e5:
        return f"{n_cycles:.2e}"
    return f"{n_cycles:.0f}"

def format_stress_mpa(value_pa: float) -> str:
    return f"{pa_to_mpa(value_pa):.1f} MPa"
```

- [x] **Step 5: Run full suite, verify pass** — `uv run pytest tests/ -q`.

---

### Task 2: Geometry, loading, and stress modules

**Files:**
- Create: `src/fatiguelife/geometry.py`, `src/fatiguelife/loading.py`, `src/fatiguelife/stress.py`, `tests/test_geometry.py`, `tests/test_stress.py`

**Interfaces:**
- Produces:
  - `geometry.Geometry(length_m: float, width_m: float, thickness_m: float)` frozen dataclass with `.second_moment_m4() -> float`, `.mass_kg(density_kg_m3: float) -> float`, `.validation_errors() -> list[str]` (empty when valid; messages name the offending dimension and mention mm units).
  - `loading.Loading(alternating_load_n: float, mean_load_n: float, frequency_hz: float)` frozen dataclass with `.validation_errors() -> list[str]` (Pa < 0 is an error; frequency informational only).
  - `stress.bending_stress_pa(load_n: float, geom: Geometry) -> float` implementing `6·P·L/(b·h²)`.

- [x] **Step 1: Write failing tests** (spec-required tests 1–6)

```python
# tests/test_geometry.py
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
```

```python
# tests/test_stress.py
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
```

- [x] **Step 2: Run, verify fail** — `uv run pytest tests/test_geometry.py tests/test_stress.py -q`.

- [x] **Step 3: Implement**

```python
# src/fatiguelife/geometry.py
"""Rectangular cantilever beam geometry (SI units)."""
from dataclasses import dataclass
from fatiguelife.units import m_to_mm

@dataclass(frozen=True)
class Geometry:
    length_m: float
    width_m: float
    thickness_m: float

    def validation_errors(self) -> list[str]:
        errors: list[str] = []
        for name, value in (("length", self.length_m), ("width", self.width_m),
                            ("thickness", self.thickness_m)):
            if value <= 0.0:
                errors.append(
                    f"Beam {name} must be positive; got {m_to_mm(value):.3g} mm."
                )
        return errors

    def second_moment_m4(self) -> float:
        """I = b*h^3/12 for a rectangular section."""
        return self.width_m * self.thickness_m**3 / 12.0

    def mass_kg(self, density_kg_m3: float) -> float:
        return density_kg_m3 * self.length_m * self.width_m * self.thickness_m
```

```python
# src/fatiguelife/loading.py
"""Cyclic end load P(t) = Pm + Pa*sin(omega*t). Frequency is display-only."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Loading:
    alternating_load_n: float
    mean_load_n: float
    frequency_hz: float = 0.0

    def validation_errors(self) -> list[str]:
        errors: list[str] = []
        if self.alternating_load_n < 0.0:
            errors.append(
                f"Alternating load Pa must be non-negative; got {self.alternating_load_n:.3g} N."
            )
        return errors
```

```python
# src/fatiguelife/stress.py
"""Nominal bending stress at the fixed end of a rectangular cantilever."""
from fatiguelife.geometry import Geometry

def bending_stress_pa(load_n: float, geom: Geometry) -> float:
    """sigma = 6*P*L / (b*h^2). Sign follows the sign of the load."""
    return 6.0 * load_n * geom.length_m / (geom.width_m * geom.thickness_m**2)
```

- [x] **Step 4: Run full suite, verify pass** — `uv run pytest tests/ -q`.

---

### Task 3: Material system — presets, custom validation, vague-name rejection

**Files:**
- Create: `src/fatiguelife/materials.py`, `tests/test_materials.py`

**Interfaces:**
- Produces:
  - `materials.Material` frozen dataclass, fields (all typed): `name: str`, `density_kg_m3: float`, `youngs_modulus_pa: float`, `yield_strength_pa: float`, `ultimate_strength_pa: float`, `basquin_coefficient_pa: float`, `basquin_exponent: float`, `life_range_min_cycles: float`, `life_range_max_cycles: float`, `product_form: str`, `heat_treatment: str`, `surface_condition: str`, `environment: str`, `stress_ratio_r: float`, `source: str`, `confidence: str` (one of `"high"|"moderate"|"low"|"illustrative"`), `condition_note: str = ""`, `notes: str = ""`.
  - `Material.validation_errors() -> list[str]` (Sy/Sut/A ≤ 0, b ≥ 0, bad confidence label).
  - `Material.is_condition_complete() -> bool` — False if any of product_form/heat_treatment/surface_condition/environment is empty or `"unspecified"`.
  - `materials.MaterialError(ValueError)`.
  - `materials.is_vague_name(name: str) -> bool`.
  - `materials.PRESETS: dict[str, Material]` with keys `"illustrative_aluminium"`, `"illustrative_mild_steel"`, `"illustrative_stainless_steel"`.
  - `materials.material_from_dict(data: dict) -> Material` — strict: unknown keys raise, missing required keys raise listing ALL missing, vague names raise with the exact message `"Please specify an exact grade/alloy and fatigue dataset conditions."`; accepts friendly-unit keys (below) and converts to SI; accepts either `basquin_coefficient_mpa` + `basquin_exponent` OR `sn_points_mpa_cycles` (list of `[stress_mpa, cycles]`, ≥ 2 points) fitted to A, b by least squares in log-log space (numpy).

Custom-material dict keys (friendly units): `name, product_form, heat_treatment, surface_condition, environment, stress_ratio_r, density_kg_m3, youngs_modulus_gpa, yield_strength_mpa, ultimate_strength_mpa, basquin_coefficient_mpa, basquin_exponent, sn_points_mpa_cycles, life_range_min_cycles, life_range_max_cycles, source, confidence, condition_note, notes`. Required (must be present, non-empty): name, product_form, heat_treatment, surface_condition, environment, stress_ratio_r, density_kg_m3, youngs_modulus_gpa, yield_strength_mpa, ultimate_strength_mpa, source, confidence, life range, and (A+b or sn_points).

Preset values (illustrative only — label them so):

| preset | ρ kg/m³ | E GPa | Sy MPa | Sut MPa | A MPa | b | life range |
|---|---|---|---|---|---|---|---|
| illustrative_aluminium | 2700 | 70 | 240 | 310 | 620 | −0.15 | 1e3–1e8 |
| illustrative_mild_steel | 7850 | 200 | 250 | 420 | 900 | −0.11 | 1e4–1e8 |
| illustrative_stainless_steel | 8000 | 193 | 290 | 620 | 1100 | −0.12 | 1e4–1e8 |

Every preset: `confidence="illustrative"`, `source="Illustrative textbook-style values for educational comparison only; not a measured dataset."`, condition fields `"illustrative"`, `stress_ratio_r=-1.0`, `condition_note` explaining intended illustrative condition.

Vague-name rule: lowercase the name, strip; reject if it matches (whole string, after removing spaces/hyphens) any of `{"steel","mild steel","stainless","stainless steel","aluminium","aluminum","alloy","metal","iron","titanium","aluminium alloy","aluminum alloy","steel alloy"}` OR contains no digit AND is a single generic word from `{"steel","aluminium","aluminum","stainless","metal","alloy","iron","titanium","brass","copper"}`. (Presets bypass this check — they are explicitly labelled illustrative.)

- [x] **Step 1: Write failing tests** (spec-required tests 17, 18 live here)

```python
# tests/test_materials.py
import pytest
from fatiguelife import materials
from fatiguelife.materials import MaterialError, PRESETS, material_from_dict, is_vague_name

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
    assert set(PRESETS) == {"illustrative_aluminium", "illustrative_mild_steel",
                            "illustrative_stainless_steel"}
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
    pts = [[620.0 * n ** -0.12, n] for n in (1e4, 1e5, 1e6, 1e7)]
    data = {k: v for k, v in GOOD_CUSTOM.items()
            if k not in ("basquin_coefficient_mpa", "basquin_exponent")}
    data["sn_points_mpa_cycles"] = pts
    m = material_from_dict(data)
    assert m.basquin_coefficient_pa == pytest.approx(620.0e6, rel=1e-6)
    assert m.basquin_exponent == pytest.approx(-0.12, rel=1e-6)
```

- [x] **Step 2: Run, verify fail** — `uv run pytest tests/test_materials.py -q`.

- [x] **Step 3: Implement `materials.py`**

Key implementation notes (write full docstrings):

```python
VAGUE_EXACT = {"steel", "mild steel", "stainless", "stainless steel", "aluminium",
               "aluminum", "alloy", "metal", "iron", "titanium",
               "aluminium alloy", "aluminum alloy", "steel alloy"}
GENERIC_WORDS = {"steel", "aluminium", "aluminum", "stainless", "metal", "alloy",
                 "iron", "titanium", "brass", "copper"}
VAGUE_MESSAGE = "Please specify an exact grade/alloy and fatigue dataset conditions."

def is_vague_name(name: str) -> bool:
    n = " ".join(name.lower().split())
    if n in VAGUE_EXACT:
        return True
    words = n.replace("-", " ").split()
    has_digit = any(ch.isdigit() for ch in n)
    return (not has_digit) and len(words) == 1 and words[0] in GENERIC_WORDS
```

`material_from_dict`: (1) reject unknown keys → `MaterialError(f"Unknown material key(s): {sorted(extra)}. Allowed: {sorted(ALLOWED)}")`; (2) collect ALL missing required keys and raise once naming each; (3) `is_vague_name(name)` → `MaterialError(VAGUE_MESSAGE)`; (4) require exactly one of (A+b) / sn_points; fit sn_points with `numpy.polyfit(log(N), log(S), 1)` → `b = slope`, `A = exp(intercept)`; (5) convert GPa→Pa (×1e9), MPa→Pa (×1e6); (6) validate confidence label ∈ {high, moderate, low, illustrative}; (7) return `Material`, then raise if `material.validation_errors()` non-empty.

`PRESETS`: build from the table above with `mpa*1e6`, `gpa*1e9`.

- [x] **Step 4: Run full suite, verify pass** — `uv run pytest tests/ -q`.

---

### Task 4: Notch, Goodman, Basquin

**Files:**
- Create: `src/fatiguelife/notch.py`, `src/fatiguelife/goodman.py`, `src/fatiguelife/basquin.py`, `tests/test_goodman.py`, `tests/test_basquin.py`

**Interfaces:**
- Produces:
  - `notch.local_stress_pa(nominal_pa: float, kf: float) -> float` (`kf * nominal`; raises `ValueError` if `kf < 1`).
  - `goodman.GoodmanInvalidError(ValueError)`.
  - `goodman.equivalent_fully_reversed_pa(sigma_a_local_pa, sigma_m_local_pa, sut_pa) -> float` — raises `GoodmanInvalidError` when `sigma_m_local_pa >= sut_pa`; for compressive mean (`< 0`) uses denominator 1.0 (capped, no compressive credit).
  - `basquin.life_cycles(sigma_a_eq_pa, coefficient_a_pa, exponent_b) -> float` = `(sigma/A)**(1/b)`; raises `ValueError` if `b >= 0` or `sigma <= 0` or `A <= 0`.
  - `basquin.stress_at_life_pa(n_cycles, coefficient_a_pa, exponent_b) -> float` = `A * n**b`.

- [x] **Step 1: Write failing tests** (spec tests 7, 8, 14)

```python
# tests/test_goodman.py
import pytest
from fatiguelife.notch import local_stress_pa
from fatiguelife.goodman import equivalent_fully_reversed_pa, GoodmanInvalidError

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
```

```python
# tests/test_basquin.py
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
```

- [x] **Step 2: Run, verify fail.**

- [x] **Step 3: Implement** the three modules exactly per the Interfaces block (each ~15 lines with docstrings; Goodman docstring must state the compressive cap and that Modified Goodman is a simplified screening criterion).

- [x] **Step 4: Run full suite, verify pass** — `uv run pytest tests/ -q`.

---

### Task 5: Single-run simulation with warnings and status

**Files:**
- Create: `src/fatiguelife/simulate.py`, `tests/test_simulate.py`

**Interfaces:**
- Consumes: everything from Tasks 2–4.
- Produces:
  - `simulate.FatigueParams(notch_factor: float, target_life_cycles: float, minimum_yield_safety_factor: float)` frozen dataclass.
  - `simulate.ResultStatus` (`enum.Enum`) with `.label: str` values exactly: `VALID` → `"Valid within selected model assumptions"`, `WARNING_ILLUSTRATIVE` → `"Warning: illustrative data"`, `WARNING_INCOMPLETE` → `"Warning: incomplete material-condition match"`, `INVALID` → `"Invalid: no fatigue prediction available"`.
  - `simulate.SimulationResult` dataclass: `status: ResultStatus`, `warnings: list[str]`, `errors: list[str]`, `nominal_alternating_stress_pa`, `nominal_mean_stress_pa`, `local_alternating_stress_pa`, `local_mean_stress_pa`, `goodman_equivalent_stress_pa`, `max_local_stress_pa`, `yield_safety_factor` (all `float | None`), `fatigue_life_cycles: float | None`, `mass_kg: float`, `meets_target_life: bool | None`, `meets_yield_requirement: bool | None`, `material: Material`, plus `.badge() -> str` returning `"Valid" | "Warning" | "Invalid"` (Warning when status is a warning OR warnings list non-empty).
  - `simulate.run(geom: Geometry, load: Loading, material: Material, params: FatigueParams) -> SimulationResult`.

Logic (order matters):
1. Collect `errors` from `geom.validation_errors()`, `load.validation_errors()`, `material.validation_errors()`, and `params.notch_factor < 1` → `"Notch factor Kf must be >= 1; got ..."`. Any errors → status INVALID, numeric fields None (mass still computed if geometry valid, else 0.0), return.
2. Compute σ_a, σ_m (stress.py), local values (notch.py), σ_max_local = Kf·(σ_m + σ_a), n_y = Sy/σ_max_local (None if σ_max_local ≤ 0 → set n_y = float("inf") when σ_max_local <= 0).
3. Goodman: catch `GoodmanInvalidError` → status INVALID, error `"Mean local stress ... >= Sut ...: Modified Goodman correction is invalid; no fatigue prediction available."`, life None, return.
4. Basquin life; warnings appended when: σ_max_local ≥ Sy (`"Static yield likely: maximum local stress ... >= yield strength ..."`); life outside `[material.life_range_min_cycles, material.life_range_max_cycles]` (`"Predicted life ... is outside the dataset's applicable range ...; treat the number as extrapolation, not prediction."`); `material.confidence == "illustrative"` (append MATERIAL_NOTICE-style warning `"Illustrative material data: results are for comparison only."`); `not material.is_condition_complete()` or `material.confidence == "low"` (`"Material condition metadata is incomplete or low-confidence; the dataset may not match the modelled component."`).
5. Status: INVALID handled above; else `WARNING_ILLUSTRATIVE` if confidence illustrative; else `WARNING_INCOMPLETE` if condition incomplete or confidence low; else `VALID`. (`badge()` still says "Warning" for a VALID status with yield/range warnings.)
6. `meets_target_life = life >= params.target_life_cycles`, `meets_yield_requirement = n_y >= params.minimum_yield_safety_factor`.

- [x] **Step 1: Write failing tests** (spec tests 9–13)

```python
# tests/test_simulate.py
import dataclasses
import pytest
from fatiguelife.geometry import Geometry
from fatiguelife.loading import Loading
from fatiguelife.materials import PRESETS
from fatiguelife.simulate import FatigueParams, ResultStatus, run

GEOM = Geometry(0.1, 0.02, 0.005)
LOAD = Loading(alternating_load_n=30.0, mean_load_n=20.0, frequency_hz=10.0)
MAT = PRESETS["illustrative_aluminium"]
PARAMS = FatigueParams(notch_factor=1.5, target_life_cycles=1.0e6,
                       minimum_yield_safety_factor=1.5)

def test_baseline_runs_and_is_labelled_illustrative():
    r = run(GEOM, LOAD, MAT, PARAMS)
    assert r.status is ResultStatus.WARNING_ILLUSTRATIVE
    assert r.fatigue_life_cycles is not None and r.fatigue_life_cycles > 0
    assert r.badge() == "Warning"

def test_increasing_pa_reduces_life():
    hi = run(GEOM, Loading(60.0, 20.0, 10.0), MAT, PARAMS)
    lo = run(GEOM, LOAD, MAT, PARAMS)
    assert hi.fatigue_life_cycles < lo.fatigue_life_cycles

def test_increasing_thickness_increases_life():
    thick = run(Geometry(0.1, 0.02, 0.010), LOAD, MAT, PARAMS)
    thin = run(GEOM, LOAD, MAT, PARAMS)
    assert thick.fatigue_life_cycles > thin.fatigue_life_cycles

def test_increasing_kf_reduces_life():
    sharp = run(GEOM, LOAD, MAT, dataclasses.replace(PARAMS, notch_factor=2.5))
    mild = run(GEOM, LOAD, MAT, PARAMS)
    assert sharp.fatigue_life_cycles < mild.fatigue_life_cycles

def test_yield_risk_triggers_warning():
    # Huge load -> sigma_max_local >= Sy but sigma_m_local < Sut
    r = run(GEOM, Loading(400.0, 0.0, 10.0), MAT, PARAMS)
    assert any("yield" in w.lower() for w in r.warnings)
    assert r.badge() == "Warning"

def test_mean_local_stress_at_sut_is_invalid():
    r = run(GEOM, Loading(10.0, 900.0, 10.0), MAT, PARAMS)
    assert r.status is ResultStatus.INVALID
    assert r.fatigue_life_cycles is None

def test_bad_geometry_is_invalid():
    r = run(Geometry(0.1, -0.02, 0.005), LOAD, MAT, PARAMS)
    assert r.status is ResultStatus.INVALID
```

(Sanity for the invalid-mean case: σ_m nominal = 6·900·0.1/(0.02·2.5e-5) = 1.08e9 Pa; ×1.5 ≫ Sut 310 MPa. Yield case: σ_a = 400/30·3.6e7 = 4.8e8; ×1.5 = 720 MPa ≥ Sy 240 MPa but σ_m_local = 0 < Sut. However σ_max_local ≥ Sut... only σ_m matters for Goodman, so still computable.)

- [x] **Step 2: Run, verify fail.**
- [x] **Step 3: Implement `simulate.py`** per the logic block above.
- [x] **Step 4: Run full suite, verify pass** — `uv run pytest tests/ -q`.

---

### Task 6: Strict config loading + example config files

**Files:**
- Create: `src/fatiguelife/config.py`, `tests/test_config.py`, `configs/baseline.yaml`, `configs/aluminium_bracket.yaml`, `configs/steel_bracket.yaml`, `configs/high_mean_load.yaml`, `configs/optimization.yaml`, `configs/materials/illustrative_aluminium.yaml`, `configs/materials/illustrative_mild_steel.yaml`, `configs/materials/illustrative_stainless_steel.yaml`, `configs/materials/custom_material_template.yaml`

**Interfaces:**
- Consumes: `Geometry`, `Loading`, `FatigueParams`, `materials.material_from_dict`, `materials.PRESETS`.
- Produces:
  - `config.ConfigError(ValueError)`.
  - `config.StudyParams(sweep_points: int = 9, sweep_span_factor: float = 4.0)`.
  - `config.OptimizationParams(width_min_m, width_max_m, thickness_min_m, thickness_max_m, grid_points: int)` (converted from `_mm` keys).
  - `config.Config` dataclass: `title: str`, `geometry: Geometry`, `loading: Loading`, `material: Material`, `fatigue: FatigueParams`, `study: StudyParams`, `optimization: OptimizationParams | None`, `raw: dict` (the parsed input, for reproducibility display/export).
  - `config.load_config(path: str | Path) -> Config` — `.yaml`/`.yml` via PyYAML (raise `ConfigError("PyYAML is required for YAML configs. Install with: pip install 'fatiguelife[yaml]' — or use a JSON config.")` when missing), `.json` via stdlib.
  - `config.config_from_dict(data: dict, base_dir: Path) -> Config`.

Schema (sections and allowed keys — anything else raises `ConfigError` naming the unknown key, its section, and the allowed keys):
- `project`: `title` (str, required)
- `geometry`: `length_mm`, `width_mm`, `thickness_mm` (numbers, required) — error messages must mention mm, e.g. `"geometry.width_mm must be a positive number in millimetres"`
- `loading`: `alternating_load_n` (required), `mean_load_n` (default 0.0 is NOT applied silently — required), `frequency_hz` (required)
- `material`: exactly one of `preset` (str key into PRESETS; unknown preset → error listing available), `custom` (inline dict → `material_from_dict`), `file` (path relative to config file → parsed YAML/JSON dict → `material_from_dict`)
- `fatigue`: `notch_factor`, `target_life_cycles`, `minimum_yield_safety_factor` (all required)
- `study`: `sweep_points`, `sweep_span_factor` (optional section; defaults 9 / 4.0 only when the whole section or key is absent)
- `optimization`: `width_min_mm`, `width_max_mm`, `thickness_min_mm`, `thickness_max_mm`, `grid_points` (optional section, but required for the optimize command)

Config file contents — write these exactly:

```yaml
# configs/baseline.yaml
project:
  title: "Illustrative aluminium cantilever fatigue study"
geometry:
  length_mm: 100
  width_mm: 20
  thickness_mm: 5
loading:
  alternating_load_n: 30
  mean_load_n: 20
  frequency_hz: 10
material:
  preset: illustrative_aluminium
fatigue:
  notch_factor: 1.5
  target_life_cycles: 1000000
  minimum_yield_safety_factor: 1.5
study:
  sweep_points: 9
  sweep_span_factor: 4
optimization:
  width_min_mm: 5
  width_max_mm: 50
  thickness_min_mm: 1
  thickness_max_mm: 20
  grid_points: 60
```

`aluminium_bracket.yaml`: same structure, L=150, b=25, h=6, Pa=40, Pm=0, Kf=1.8, title "Aluminium bracket, fully reversed loading".
`steel_bracket.yaml`: preset illustrative_mild_steel, L=120, b=20, h=4, Pa=60, Pm=30, Kf=1.6.
`high_mean_load.yaml`: preset illustrative_mild_steel, L=100, b=20, h=5, Pa=25, Pm=120, Kf=1.5, title "High mean load Goodman stress study".
`optimization.yaml`: baseline values + title "Minimum-mass sizing study", optimization grid_points: 80.
`configs/materials/illustrative_*.yaml`: full custom-material-format dumps of each preset (so users see the schema populated), with a comment header `# Illustrative dataset — educational comparison only.`
`custom_material_template.yaml`: every custom key with placeholder values and comments explaining each field, `confidence: low`, and a comment block: `# Fatigue properties are condition-specific. Results depend on the selected dataset and may not apply to a real component.`

- [x] **Step 1: Write failing tests** (spec test 16)

```python
# tests/test_config.py
import json
import pytest
from fatiguelife.config import ConfigError, load_config

def test_baseline_yaml_loads(tmp_path):
    cfg = load_config("configs/baseline.yaml")
    assert cfg.geometry.length_m == pytest.approx(0.1)
    assert cfg.loading.alternating_load_n == 30
    assert cfg.material.name == "Illustrative Aluminium Alloy"
    assert cfg.fatigue.notch_factor == 1.5
    assert cfg.optimization is not None and cfg.optimization.grid_points == 60

def test_unknown_key_raises_clear_error(tmp_path):
    bad = {"project": {"title": "x"},
           "geometry": {"length_mm": 100, "width_mm": 20, "thickness_mm": 5,
                        "depth_mm": 3},
           "loading": {"alternating_load_n": 30, "mean_load_n": 0, "frequency_hz": 10},
           "material": {"preset": "illustrative_aluminium"},
           "fatigue": {"notch_factor": 1.5, "target_life_cycles": 1e6,
                        "minimum_yield_safety_factor": 1.5}}
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad))
    with pytest.raises(ConfigError, match="depth_mm"):
        load_config(p)

def test_missing_required_key_raises(tmp_path):
    bad = {"project": {"title": "x"},
           "geometry": {"length_mm": 100, "width_mm": 20},
           "loading": {"alternating_load_n": 30, "mean_load_n": 0, "frequency_hz": 10},
           "material": {"preset": "illustrative_aluminium"},
           "fatigue": {"notch_factor": 1.5, "target_life_cycles": 1e6,
                        "minimum_yield_safety_factor": 1.5}}
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad))
    with pytest.raises(ConfigError, match="thickness_mm"):
        load_config(p)

def test_json_config_works_without_yaml(tmp_path):
    good = {"project": {"title": "json run"},
            "geometry": {"length_mm": 100, "width_mm": 20, "thickness_mm": 5},
            "loading": {"alternating_load_n": 30, "mean_load_n": 20, "frequency_hz": 10},
            "material": {"preset": "illustrative_aluminium"},
            "fatigue": {"notch_factor": 1.5, "target_life_cycles": 1e6,
                         "minimum_yield_safety_factor": 1.5}}
    p = tmp_path / "run.json"
    p.write_text(json.dumps(good))
    assert load_config(p).title == "json run"

def test_unknown_preset_lists_available(tmp_path):
    bad = {"project": {"title": "x"},
           "geometry": {"length_mm": 100, "width_mm": 20, "thickness_mm": 5},
           "loading": {"alternating_load_n": 30, "mean_load_n": 0, "frequency_hz": 10},
           "material": {"preset": "unobtainium"},
           "fatigue": {"notch_factor": 1.5, "target_life_cycles": 1e6,
                        "minimum_yield_safety_factor": 1.5}}
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad))
    with pytest.raises(ConfigError, match="illustrative_aluminium"):
        load_config(p)

def test_all_shipped_configs_load():
    for name in ("baseline", "aluminium_bracket", "steel_bracket",
                 "high_mean_load", "optimization"):
        load_config(f"configs/{name}.yaml")
```

- [x] **Step 2: Run, verify fail.**
- [x] **Step 3: Implement `config.py`** (a `_check_section(data, section, allowed, required)` helper keeps it DRY) **and write all 9 config files.**
- [x] **Step 4: Run full suite, verify pass** — `uv run pytest tests/ -q`. (Tests that read `configs/` run from project root per pytest.ini testpaths.)

---

### Task 7: Sweeps and sensitivity

**Files:**
- Create: `src/fatiguelife/sweep.py`, `src/fatiguelife/sensitivity.py`, `tests/test_sweeps.py`

**Interfaces:**
- Consumes: `Config`, `simulate.run`, dataclasses from earlier tasks.
- Produces:
  - `sweep.SWEEPABLE: tuple[str, ...] = ("alternating_load_n", "mean_load_n", "thickness_mm", "width_mm", "length_mm", "notch_factor")`.
  - `sweep.SweepPoint` dataclass: `value: float` (in the parameter's display unit: N, mm, or unitless Kf), `fatigue_life_cycles: float | None`, `yield_safety_factor: float | None`, `status_badge: str`, `warnings: list[str]`.
  - `sweep.run_sweep(cfg: Config, parameter: str, points: int | None = None, span_factor: float | None = None) -> list[SweepPoint]` — raises `ValueError` for unknown parameter naming SWEEPABLE. Range: current-value-centred geometric range `numpy.geomspace(x/span, x*span, points)` when current x > 0; when x == 0 (only physically possible for `mean_load_n`), linear `numpy.linspace(0, max(1.0, cfg.loading.alternating_load_n), points)`. Each point rebuilds the varied dataclass with `dataclasses.replace` and calls `simulate.run`.
  - `sensitivity.SensitivityResult` dataclass: `parameter: str`, `kind: str` (`"elasticity"` or `"absolute"`), `value: float | None`, `interpretation: str` (plain-language, e.g. `"A 1% increase in thickness changes predicted life by about +X%."`).
  - `sensitivity.run_sensitivity(cfg: Config) -> list[SensitivityResult]` — for each of Pa, h, b, L, Kf: central log-log elasticity `(ln Nf(1.05x) − ln Nf(0.95x)) / (ln 1.05x − ln 0.95x)`; for Pm: same elasticity if `Pm != 0`, else `kind="absolute"` with finite difference `(Nf(+δ) − Nf(−δ)) / (2δ)`, `δ = 0.05 * Pa` (clamped so Pm−δ stays valid); `value=None` with explanatory interpretation when either perturbed run yields no life (invalid). Results sorted by `abs(value)` descending (None last).

- [x] **Step 1: Write failing tests**

```python
# tests/test_sweeps.py
import pytest
from fatiguelife.config import load_config
from fatiguelife.sweep import run_sweep, SWEEPABLE
from fatiguelife.sensitivity import run_sensitivity

CFG = load_config("configs/baseline.yaml")

def test_sweep_returns_requested_points_and_monotone_life():
    pts = run_sweep(CFG, "alternating_load_n", points=5)
    assert len(pts) == 5
    lives = [p.fatigue_life_cycles for p in pts if p.fatigue_life_cycles]
    assert lives == sorted(lives, reverse=True)  # more load -> less life

def test_sweep_range_is_centred_on_current_value():
    pts = run_sweep(CFG, "thickness_mm", points=9)
    values = [p.value for p in pts]
    assert values[0] == pytest.approx(5.0 / 4.0)
    assert values[-1] == pytest.approx(5.0 * 4.0)
    assert min(values) < 5.0 < max(values)

def test_unknown_parameter_rejected():
    with pytest.raises(ValueError, match="alternating_load_n"):
        run_sweep(CFG, "density")

def test_sensitivity_signs_and_ranking():
    results = {r.parameter: r for r in run_sensitivity(CFG)}
    assert results["alternating_load_n"].value < 0        # more load, less life
    assert results["thickness_mm"].value > 0              # thicker, more life
    assert results["notch_factor"].value < 0
    # thickness elasticity magnitude ~ 2/|b| > load elasticity ~ 1/|b|... both large;
    # just require |h| elasticity > |L| is false (equal-ish) — instead check ordering is by magnitude:
    vals = [abs(r.value) for r in run_sensitivity(CFG) if r.value is not None]
    assert vals == sorted(vals, reverse=True)

def test_sensitivity_handles_zero_mean_load():
    import dataclasses
    from fatiguelife.loading import Loading
    cfg0 = dataclasses.replace(CFG, loading=Loading(30.0, 0.0, 10.0))
    r = {x.parameter: x for x in run_sensitivity(cfg0)}["mean_load_n"]
    assert r.kind == "absolute"
```

- [x] **Step 2: Run, verify fail.**
- [x] **Step 3: Implement both modules.** Note for `run_sweep`: map parameter name → which dataclass field it replaces and its unit conversion (`thickness_mm` → `Geometry.thickness_m` via `mm_to_m`, `notch_factor` → `FatigueParams.notch_factor`, loads direct). Keep a module-level dict `PARAM_SPECS: dict[str, ParamSpec]` (`ParamSpec` = small dataclass with `label`, `unit`, `getter(cfg) -> float`, `apply(cfg, value) -> tuple[Geometry, Loading, FatigueParams]`) shared by sweep and sensitivity — DRY.
- [x] **Step 4: Run full suite, verify pass** — `uv run pytest tests/ -q`.

---

### Task 8: Lightweight design (grid sizing)

**Files:**
- Create: `src/fatiguelife/design.py`, `tests/test_design.py`

**Interfaces:**
- Consumes: `Config` (must have `optimization`), `simulate.run`, `PARAM_SPECS` idea not needed here.
- Produces:
  - `design.DesignCandidate` dataclass: `width_mm: float`, `thickness_mm: float`, `mass_kg: float`, `fatigue_life_cycles: float | None`, `yield_safety_factor: float | None`, `feasible: bool`, `warnings: list[str]`.
  - `design.SizingResult` dataclass: `best: DesignCandidate | None`, `top: list[DesignCandidate]` (≤ 10, lowest mass first, feasible only), `evaluated: int`, `feasible_count: int`, `note: str` = `"This is a grid-based preliminary sizing study, not full shape optimization."`.
  - `design.run_sizing(cfg: Config) -> SizingResult` — raises `ConfigError` if `cfg.optimization is None`. Grid: `numpy.linspace` over width and thickness bounds with `grid_points` per axis. Feasible ⇔ result not INVALID AND `fatigue_life_cycles >= fatigue.target_life_cycles` AND `yield_safety_factor >= fatigue.minimum_yield_safety_factor`.

- [x] **Step 1: Write failing tests** (spec test 15)

```python
# tests/test_design.py
from fatiguelife.config import load_config
from fatiguelife.design import run_sizing

CFG = load_config("configs/optimization.yaml")

def test_all_returned_designs_are_feasible():
    res = run_sizing(CFG)
    assert res.best is not None
    for c in [res.best, *res.top]:
        assert c.feasible
        assert c.fatigue_life_cycles >= CFG.fatigue.target_life_cycles
        assert c.yield_safety_factor >= CFG.fatigue.minimum_yield_safety_factor

def test_best_is_minimum_mass_and_top_sorted():
    res = run_sizing(CFG)
    masses = [c.mass_kg for c in res.top]
    assert masses == sorted(masses)
    assert res.best.mass_kg == masses[0]

def test_note_is_present():
    assert "not full shape optimization" in run_sizing(CFG).note

def test_infeasible_problem_returns_none_best():
    import dataclasses
    cfg = dataclasses.replace(
        CFG, fatigue=dataclasses.replace(CFG.fatigue, target_life_cycles=1e30))
    res = run_sizing(cfg)
    assert res.best is None and res.top == [] and res.feasible_count == 0
```

- [x] **Step 2: Run, verify fail.**
- [x] **Step 3: Implement `design.py`.** (Note 80×80 = 6400 simulate calls — pure Python is fine, each call is microseconds.)
- [x] **Step 4: Run full suite, verify pass** — `uv run pytest tests/ -q`.

---

### Task 9: Exports (CSV/JSON) — io_data

**Files:**
- Create: `src/fatiguelife/io_data.py`, `tests/test_io_data.py`

**Interfaces:**
- Consumes: `SimulationResult`, `SweepPoint`, `SensitivityResult`, `SizingResult`, `Config`.
- Produces (all writers take an explicit path and return it; all include provenance):
  - `io_data.summary_dict(cfg: Config, result: SimulationResult) -> dict` — nested dict with `scope_statement`, `config` (the `cfg.raw` echo), `material` block containing `name`, `source`, `confidence`, all condition fields, `results` block with display-unit values AND SI values, `status`, `badge`, `warnings`.
  - `io_data.write_summary_json(cfg, result, path) -> Path` (json.dump of summary_dict, indent=2).
  - `io_data.write_summary_csv(cfg, result, path) -> Path` — two-column `key,value` rows flattened from summary_dict (`material.source`, `material.confidence` keys must appear).
  - `io_data.write_sweep_csv(parameter: str, points: list[SweepPoint], material: Material, path) -> Path` — header comment rows `# material: ...`, `# source: ...`, `# confidence: ...` then columns `value,fatigue_life_cycles,yield_safety_factor,status,warnings`.
  - `io_data.write_sizing_csv(res: SizingResult, material: Material, path) -> Path` — same provenance header; columns `width_mm,thickness_mm,mass_kg,fatigue_life_cycles,yield_safety_factor,feasible`.

- [x] **Step 1: Write failing tests** (spec test 19)

```python
# tests/test_io_data.py
import json
from fatiguelife.config import load_config
from fatiguelife.simulate import run
from fatiguelife import io_data

CFG = load_config("configs/baseline.yaml")
RESULT = run(CFG.geometry, CFG.loading, CFG.material, CFG.fatigue)

def test_summary_json_includes_provenance(tmp_path):
    p = io_data.write_summary_json(CFG, RESULT, tmp_path / "s.json")
    data = json.loads(p.read_text())
    assert data["material"]["source"]
    assert data["material"]["confidence"] == "illustrative"
    assert "educational comparative model" in data["scope_statement"]

def test_summary_csv_includes_provenance(tmp_path):
    p = io_data.write_summary_csv(CFG, RESULT, tmp_path / "s.csv")
    text = p.read_text()
    assert "material.source" in text and "material.confidence" in text

def test_sweep_csv_has_provenance_header(tmp_path):
    from fatiguelife.sweep import run_sweep
    pts = run_sweep(CFG, "alternating_load_n", points=3)
    p = io_data.write_sweep_csv("alternating_load_n", pts, CFG.material, tmp_path / "sw.csv")
    text = p.read_text()
    assert text.startswith("# material:") and "# confidence: illustrative" in text
```

- [x] **Step 2: Run, verify fail.**
- [x] **Step 3: Implement `io_data.py`** (stdlib `csv` + `json`; a `_flatten(d, prefix)` helper for the CSV).
- [x] **Step 4: Run full suite, verify pass** — `uv run pytest tests/ -q`.

---

### Task 10: CLI and launcher

**Files:**
- Create: `src/fatiguelife/cli.py`, `fatiguelife` (executable launcher script at project root), `tests/test_cli.py`

**Interfaces:**
- Consumes: everything.
- Produces: `cli.main(argv: list[str] | None = None) -> int`. Subcommands:
  - `run CONFIG --outdir OUT` — simulate; print human-readable report (title, scope statement, material name/source/confidence + condition notice, inputs in display units, all result cards from spec Section 4, status label, every warning prefixed `WARNING:`, errors prefixed `INVALID:`); write `summary.json` + `summary.csv` into outdir.
  - `sweep CONFIG --outdir OUT [--parameter P]` — default: all six SWEEPABLE parameters; one CSV each (`sweep_<parameter>.csv`); prints compact table per sweep.
  - `sensitivity CONFIG` — prints ranked table + interpretations.
  - `optimize CONFIG --outdir OUT` — sizing study; prints best + top-10 table + the grid-study note; writes `sizing.csv`.
  - `info CONFIG` — prints parsed config, material metadata block, assumption list, no simulation.
  - `serve [CONFIG] [--port 8765]` — implemented in Task 11; until then registers and raises `SystemExit("serve is implemented in a later task")` — replace in Task 11.
  - `test` — `subprocess.run([sys.executable, "-m", "pytest", "tests/", "-q"], cwd=<project root>)`, returns its returncode.
  - All config/material errors are caught and printed as `error: <message>` to stderr, exit code 2 (argparse-style); never a traceback for user errors.

Launcher (`fatiguelife`, `chmod +x`):

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
exec uv run python -m fatiguelife.cli "$@"
```

Also add to `cli.py`: `if __name__ == "__main__": raise SystemExit(main())` and create `src/fatiguelife/__main__.py` calling the same (so `python -m fatiguelife` works too).

- [x] **Step 1: Write failing tests**

```python
# tests/test_cli.py
from fatiguelife.cli import main

def test_run_command_prints_report_and_exports(tmp_path, capsys):
    rc = main(["run", "configs/baseline.yaml", "--outdir", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Illustrative Aluminium Alloy" in out
    assert "educational comparative model" in out
    assert "confidence" in out.lower()
    assert (tmp_path / "summary.json").exists()
    assert (tmp_path / "summary.csv").exists()

def test_run_reports_warnings(tmp_path, capsys):
    main(["run", "configs/baseline.yaml", "--outdir", str(tmp_path)])
    out = capsys.readouterr().out
    assert "WARNING" in out  # illustrative-data warning at minimum

def test_info_command(capsys):
    rc = main(["info", "configs/baseline.yaml"])
    out = capsys.readouterr().out
    assert rc == 0 and "Assumptions" in out

def test_invalid_config_is_friendly(tmp_path, capsys):
    p = tmp_path / "bad.json"
    p.write_text('{"project": {"title": "x"}, "geometry": {"length_mm": 100}}')
    rc = main(["run", str(p), "--outdir", str(tmp_path)])
    err = capsys.readouterr().err
    assert rc == 2 and "error:" in err and "Traceback" not in err

def test_sweep_and_optimize_commands(tmp_path, capsys):
    assert main(["sweep", "configs/baseline.yaml", "--outdir", str(tmp_path),
                 "--parameter", "alternating_load_n"]) == 0
    assert (tmp_path / "sweep_alternating_load_n.csv").exists()
    assert main(["optimize", "configs/optimization.yaml", "--outdir", str(tmp_path)]) == 0
    assert (tmp_path / "sizing.csv").exists()
    out = capsys.readouterr().out
    assert "not full shape optimization" in out

def test_sensitivity_command(capsys):
    assert main(["sensitivity", "configs/baseline.yaml"]) == 0
    assert "alternating_load_n" in capsys.readouterr().out
```

- [x] **Step 2: Run, verify fail.**
- [x] **Step 3: Implement `cli.py`, `__main__.py`, launcher; `chmod +x fatiguelife`.** Keep printing helpers (`_print_report(cfg, result)`, `_print_material(material)`, `ASSUMPTIONS: list[str]` — the full Section-10 list from the spec, reused by dashboard later) in `cli.py`; move `ASSUMPTIONS` into `simulate.py` so dashboard can import it without importing the CLI.
- [x] **Step 4: Run full suite, verify pass; also smoke-run `./fatiguelife run configs/baseline.yaml --outdir /tmp/claude-1000/-home-adith-swastik/82d9d2ad-b2f5-4dec-b7c6-6e613b97f4a3/scratchpad/flout` manually and read the report.**

---### Task 11: Dashboard — stdlib server + single-page UI with SVG charts

**Files:**
- Create: `src/fatiguelife/dashboard.py`, `src/fatiguelife/dashboard.html`, `tests/test_dashboard.py`
- Modify: `src/fatiguelife/cli.py` (real `serve` command)

**Interfaces:**
- Consumes: `Config`, `simulate.run`, `run_sweep`, `run_sensitivity`, `run_sizing`, `io_data.summary_dict`, `materials.PRESETS`, `materials.material_from_dict`, `simulate.ASSUMPTIONS`.
- Produces:
  - `dashboard.create_server(cfg: Config | None, port: int) -> http.server.ThreadingHTTPServer` and `dashboard.serve(cfg, port)` (blocking; prints URL).
  - `dashboard.ApiHandler(http.server.BaseHTTPRequestHandler)`:
    - `GET /` → `dashboard.html` (read via `importlib.resources`), `GET /favicon.ico` → 204.
    - `GET /api/materials` → `{"presets": {key: material_dict...}, "notice": MATERIAL_NOTICE}`.
    - `GET /api/defaults` → the loaded config as a friendly-units dict (or built-in baseline defaults when server started without a config).
    - `POST /api/simulate` body `{geometry:{length_mm,width_mm,thickness_mm}, loading:{...}, material:{preset|custom}, fatigue:{...}}` → full `summary_dict` + arrays for charts: `sn_curve: {cycles: [...], stress_mpa: [...]}` (60 log-spaced points across the material life range), `operating_point: {cycles, stress_mpa}`, `goodman: {sut_mpa, sy_mpa, mean_mpa, alt_mpa, eq_mpa, safe: bool}`.
    - `POST /api/sweep` body `{..same inputs.., parameter, points, span_factor}` → `{parameter, points: [{value, life, ny, badge, warnings}]}`.
    - `POST /api/sensitivity` → list of `{parameter, kind, value, interpretation}`.
    - `POST /api/optimize` body includes `{optimization: {width_min_mm, ...}}` → `{best, top, evaluated, feasible_count, note}`.
    - All handlers: parse JSON, translate `ConfigError`/`MaterialError`/`ValueError` into `{"error": msg}` with HTTP 400; any material/config problem must surface as readable text in the UI, never a 500.
  - Request→dataclass translation lives in a pure function `dashboard.request_to_model(payload: dict) -> tuple[Config-like parts]` reusing `config._check_section`-style strictness (unknown keys → 400).

`dashboard.html` — one file, semantic HTML + `<style>` + `<script>`, **zero external resources**. Required structure (ids fixed so tests and JS agree):

1. `<header>`: `<h1>FatigueLife</h1>`, research question paragraph, scope-statement `<p class="scope-warning">`, status badge `<span id="status-badge">` (classes `badge-valid|badge-warning|badge-invalid`).
2. `<section id="inputs">`: numeric inputs `#in-length, #in-width, #in-thickness, #in-pa, #in-pm, #in-frequency, #in-kf, #in-target-life, #in-min-ny` (labels with units); right side: inline SVG cantilever diagram (fixed-end hatching, beam rectangle, downward arrow labelled `P(t)`, equation text `P(t) = Pm + Pa·sin(ωt)`).
3. `<section id="material">`: `<select id="material-preset">` (options from /api/materials, each labelled `"... (illustrative)"`), button `#btn-custom-material` toggling `#custom-material-panel` (all custom fields incl. `#mat-source`, condition fields, `#mat-confidence` select), the condition-specific notice paragraph, and `<dl id="material-props">` showing all active material properties + source + confidence.
4. `<section id="results">`: cards grid — `#card-life, #card-mass, #card-sigma-a, #card-sigma-a-local, #card-sigma-m, #card-goodman-eq, #card-sigma-max, #card-ny, #card-status` — plus `<ul id="warnings">`.
5. `<section id="sn-chart">`: `<h2>S–N Curve</h2>`, `<svg id="svg-sn">` log-log Basquin line + operating point; `<p id="sn-meta">` material/condition metadata.
6. `<section id="goodman-chart">`: Goodman diagram SVG `#svg-goodman` (limit line Sut→Sy axes per simplified screening), operating point, `#goodman-verdict` safe/unsafe, explanatory note.
7. `<section id="studies">`: parameter buttons (one per SWEEPABLE), `#svg-study-life`, `#svg-study-ny`, `<table id="study-table">`, button `#btn-study-csv` (client-side CSV via `Blob` + object URL from the already-fetched JSON).
8. `<section id="sensitivity">`: `#svg-sensitivity` ranked horizontal bar chart, `#sensitivity-text` plain-language interpretation list.
9. `<section id="sizing">`: inputs `#opt-*` (bounds, grid points), run button, best-design card, `<table id="sizing-table">` top 10, the grid-note paragraph, `#btn-sizing-csv`.
10. `<section id="assumptions">`: `<h2>Assumptions and Limitations</h2>`, `<ul>` rendered from `/api/defaults`-shipped `assumptions` list (server injects `simulate.ASSUMPTIONS`).
11. `<section id="export">`: buttons `#btn-json` / `#btn-csv` (download current summary via Blob), `<pre id="config-echo">` showing the friendly-units config, `#btn-copy-config` (`navigator.clipboard.writeText`), per-chart "Download SVG" links (serialize `outerHTML` to Blob).

JS architecture (~400 lines, keep it boring): a single `state` object; `readInputs()` → payload; `async recalc()` on any input `change` (debounced 250 ms) → `POST /api/simulate` → `renderAll(data)`; chart helpers `logTicks(min,max)`, `linScale/logScale(domain,range)`, `polyline(points)` building SVG strings; every render function ≤ 40 lines. Error responses render into `#warnings` and set the badge to Invalid. No frameworks, no fetch to anywhere but same-origin `/api/*`.

CSS: system font stack, max-width 1100 px, card grid `display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr))`, badge colors (valid #2e7d32, warning #b26a00, invalid #b71c1c), print-friendly.

- [x] **Step 1: Write failing tests** (spec test 20)

```python
# tests/test_dashboard.py
import json
import threading
import urllib.request
import pytest
from fatiguelife.config import load_config
from fatiguelife.dashboard import create_server

@pytest.fixture()
def server_url():
    cfg = load_config("configs/baseline.yaml")
    srv = create_server(cfg, port=0)  # ephemeral port
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()

def _get(url):
    with urllib.request.urlopen(url, timeout=5) as r:
        return r.status, r.read().decode()

def _post(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status, json.loads(r.read())

def test_page_serves_with_headings(server_url):
    status, html = _get(server_url + "/")
    assert status == 200
    for text in ("FatigueLife", "S–N Curve", "Goodman", "Assumptions and Limitations",
                 "educational comparative model"):
        assert text in html

def test_api_simulate_baseline(server_url):
    payload = {
        "geometry": {"length_mm": 100, "width_mm": 20, "thickness_mm": 5},
        "loading": {"alternating_load_n": 30, "mean_load_n": 20, "frequency_hz": 10},
        "material": {"preset": "illustrative_aluminium"},
        "fatigue": {"notch_factor": 1.5, "target_life_cycles": 1e6,
                     "minimum_yield_safety_factor": 1.5},
    }
    status, data = _post(server_url + "/api/simulate", payload)
    assert status == 200
    assert data["results"]["fatigue_life_cycles"] > 0
    assert data["material"]["confidence"] == "illustrative"
    assert len(data["sn_curve"]["cycles"]) >= 10

def test_api_materials_lists_presets(server_url):
    status, body = _get(server_url + "/api/materials")
    assert status == 200 and "illustrative_aluminium" in body

def test_api_rejects_vague_custom_material(server_url):
    payload = {
        "geometry": {"length_mm": 100, "width_mm": 20, "thickness_mm": 5},
        "loading": {"alternating_load_n": 30, "mean_load_n": 0, "frequency_hz": 10},
        "material": {"custom": {"name": "steel"}},
        "fatigue": {"notch_factor": 1.5, "target_life_cycles": 1e6,
                     "minimum_yield_safety_factor": 1.5},
    }
    import urllib.error
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(server_url + "/api/simulate", payload)
    assert exc.value.code == 400
    body = json.loads(exc.value.read())
    assert "exact grade/alloy" in body["error"] or "Missing" in body["error"]
```

- [x] **Step 2: Run, verify fail.**
- [x] **Step 3: Implement `dashboard.py`** (handler + `create_server` with `("127.0.0.1", port)`, port 0 → ephemeral; include `hatch` build note: add `[tool.hatch.build.targets.wheel].force-include` not needed — `dashboard.html` sits inside the package dir so it ships; read it with `importlib.resources.files("fatiguelife").joinpath("dashboard.html").read_text()`).
- [x] **Step 4: Implement `dashboard.html`** per the structure block. Verify by running `./fatiguelife serve configs/baseline.yaml` and fetching `/` + one `/api/simulate` with curl.
- [x] **Step 5: Wire `serve` subcommand in `cli.py`** (default port 8765, optional config arg, prints `Serving FatigueLife dashboard at http://127.0.0.1:8765 — Ctrl+C to stop.`).
- [x] **Step 6: Run full suite, verify pass** — `uv run pytest tests/ -q`.

---

### Task 12: README, final verification, honest status report

**Files:**
- Create: `README.md`, `assets/dashboard-preview.png` placeholder note (create `assets/README.txt` saying "Place dashboard screenshot here as dashboard-preview.png").
- Modify: none.

**Interfaces:** none — documentation.

- [x] **Step 1: Write README.md** with exactly these sections (portfolio quality, concise):
  1. `# FatigueLife` + one-line description
  2. Badges-free intro paragraph + **scope warning blockquote** (the scope statement verbatim)
  3. Research question
  4. What it does (plain language, 5–6 bullets)
  5. Main equations (the eight equations from the spec, in a code block or LaTeX-ish inline)
  6. Dashboard capabilities (Sections 1–11 summarized, screenshot placeholder `![Dashboard](assets/dashboard-preview.png)`)
  7. Quick start:
     ```bash
     uv sync --all-extras
     ./fatiguelife serve configs/baseline.yaml   # dashboard
     ./fatiguelife run configs/baseline.yaml --outdir out/
     ./fatiguelife test
     ```
  8. Sample configuration (baseline.yaml verbatim)
  9. Material data policy — illustrative presets vs source-backed custom datasets, required metadata list, the condition-specific notice verbatim, "never scrapes the internet, never substitutes materials silently"
  10. Assumptions and limitations (full spec list)
  11. Testing / code verification — describe as "Code verification through analytical relationships, unit tests, and expected physical trends." Explicitly: NOT experimental validation.
  12. Project structure tree
  13. "Describing this project in an application" — the suggested paragraph from the spec, verbatim.
- [x] **Step 2: Full verification run** — `uv run pytest tests/ -q` (all pass), `./fatiguelife run configs/high_mean_load.yaml --outdir <scratchpad>/hml` (expect Goodman-related warnings or invalid status printed honestly), `./fatiguelife info configs/steel_bracket.yaml`, `./fatiguelife serve` smoke check.
- [x] **Step 3: Report final status honestly** — exact test counts, anything skipped or deferred, known rough edges. No success claims without the pytest output to back them.

