# FatigueLife — Design Specification

**Date:** 2026-08-26
**Status:** Approved design, pre-implementation
**Location:** `/home/adith/swastik/fatiguelife` (plain directory, no dedicated git repo)

## Title

FatigueLife: A Computational Framework for Fatigue-Life Estimation and
Lightweight Design of Cyclically Loaded Cantilever Brackets

## Purpose and scope

A local-first Python research tool that estimates how long a simple
rectangular metal cantilever bracket may survive under repeated bending, and
compares how material choice, geometry, cyclic load, mean load, and notch
severity influence predicted high-cycle fatigue life and minimum-mass design.

**Research question:** How do cyclic load amplitude, mean stress, beam
geometry, material properties, and notch severity affect predicted high-cycle
fatigue life and minimum-mass design of a cantilever bracket?

**Scope statement (must appear in dashboard, CLI, README):**
"This is an educational comparative model. It uses simplified beam theory,
Basquin S–N fatigue curves, Modified Goodman mean-stress correction, and a
simplified notch factor. It does not provide certified component-life
predictions or replace experimental fatigue testing."

## Physical model

Rectangular cantilever beam, fixed at one end, cyclic transverse load
P(t) = Pm + Pa·sin(ωt) at the free end. Frequency is displayed but does not
affect constant-amplitude stress-life results.

SI units internally (m, N, Pa, kg, cycles); display in mm, MPa, g/kg, cycles
(scientific notation where appropriate).

Equations:

- Second moment of area: `I = b·h³ / 12`
- Nominal alternating bending stress: `σ_a = 6·Pa·L / (b·h²)`
- Nominal mean bending stress: `σ_m = 6·Pm·L / (b·h²)`
- Local stresses: `σ_a_local = Kf·σ_a`, `σ_m_local = Kf·σ_m`
- Modified Goodman equivalent fully reversed stress:
  `σ_a_eq = σ_a_local / (1 − σ_m_local/Sut)`
  - **Compressive mean edge case (decision 6):** for σ_m_local < 0 the
    denominator is capped at 1 — no beneficial credit for compressive mean
    stress. Noted in the assumptions section.
- Basquin: `σ_a_eq = A·Nf^b`  →  `Nf = (σ_a_eq/A)^(1/b)`
- Max local stress: `σ_max_local = Kf·(σ_m + σ_a)`
- Yield safety factor: `n_y = Sy / σ_max_local`
- Mass: `mass = ρ·L·b·h`

## Validity checks (results must never mislead)

Prominent invalid/warning states when:

- any geometry dimension ≤ 0
- Pa < 0
- Kf < 1
- Basquin exponent b ≥ 0
- Sy ≤ 0 or Sut ≤ 0
- σ_m_local ≥ Sut (Goodman invalid)
- σ_max_local ≥ Sy (static yield likely → warning)
- Basquin life outside the dataset's configured applicable range
  (**decision 4:** each material dataset carries explicit
  `life_range_min_cycles` / `life_range_max_cycles`; presets use 1e3–1e8)
- vague material name (no specific dataset)
- required material metadata missing

Result labels: "Valid within selected model assumptions" /
"Warning: illustrative data" / "Warning: incomplete material-condition match" /
"Invalid: no fatigue prediction available".

## Material system

**A. Illustrative presets:** Illustrative Aluminium Alloy, Illustrative Mild
Steel, Illustrative Stainless Steel. Each has name, ρ, E, Sy, Sut, Basquin A
and b, life range, condition note, confidence = illustrative.

**B. Custom Material Assistant.** Required metadata: exact designation/alloy,
product form, heat treatment/condition, surface condition, environment,
R-ratio, ρ, E, Sy, Sut, Basquin A+b OR S–N points, source citation,
confidence label (high/moderate/low/illustrative), notes.

Rules:
- **Vague-name rejection (decision 5):** blocklist of generic names
  ("steel", "aluminium", "aluminum", "stainless", "metal", "alloy",
  "titanium", "iron", case-insensitive) rejected when the name carries no
  specific designation, with message: "Please specify an exact grade/alloy
  and fatigue dataset conditions."
- Never silently substitute a similar material; never scrape the internet.
- Import of user-reviewed YAML/JSON datasets supported.
- Source metadata shown in dashboard, CLI, CSV and JSON exports.
- Visible notice: "Fatigue properties are condition-specific. Results depend
  on the selected dataset and may not apply to a real component."

## Dashboard

**Architecture (decision 3):** single-page `dashboard.html` (semantic
HTML/CSS/vanilla JS, SVG charts, zero external libraries) served by a stdlib
`http.server` in `dashboard.py`. All physics runs server-side in the core
modules; the page calls JSON endpoints: `/api/simulate`, `/api/sweep`,
`/api/sensitivity`, `/api/optimize`, `/api/materials`. Calculations fully
separated from presentation.

Eleven sections, exactly per user spec:
1. Header — title, research question, scope warning, status badge
2. Model inputs — L, b, h, Pa, Pm, frequency, Kf, target life, required n_y;
   beam diagram with force direction and cyclic-load equation
3. Material Assistant — preset dropdown, custom-material flow, metadata
   panel, citation/condition/confidence fields, property display
4. Key results cards — life, mass, nominal/local alternating stress, mean
   stress, Goodman equivalent, max local stress, n_y, status + warnings
5. S–N curve — SVG log-log, Basquin line, operating point, MPa axis,
   material metadata below
6. Goodman diagram — σ_m vs σ_a, limit line, operating point, safe/unsafe,
   "simplified screening criterion" note
7. Parameter studies — tabs for Pa, Pm, h, b, L, Kf; current-value-centred
   range; life and n_y graphs; point table; CSV export per study
8. Sensitivity — ranked bar chart of d ln(Nf)/d ln(x) for Pa, h, b, L, Kf;
   absolute finite difference for Pm when Pm = 0; plain-language reading
9. Lightweight design study — grid search over (b, h) with target life, min
   n_y, bounds, grid points; min-mass design + top-10 feasible table +
   "grid-based preliminary sizing, not full shape optimization" warning
10. Assumptions and limitations — full list per user spec (incl. no FEA,
    no crack growth, no Miner's rule, no environment effects, no
    experimental validation, comparative not certified)
11. Export and reproducibility — CSV/JSON summary, sweep CSV, sizing CSV,
    config display, copy-config button, SVG chart export if practical

## CLI

Launcher `./fatiguelife` with commands: `serve [config]`, `run config
--outdir`, `sweep config --outdir`, `sensitivity config`, `optimize config
--outdir`, `info config`, `test`. Readable results, all warnings, material
metadata shown. Strict YAML/JSON validation: unknown keys rejected, no silent
defaults on invalid keys, helpful unit-related error messages.

## Configs

`configs/`: baseline.yaml, aluminium_bracket.yaml, steel_bracket.yaml,
high_mean_load.yaml, optimization.yaml. `configs/materials/`:
illustrative_aluminium.yaml, illustrative_mild_steel.yaml,
illustrative_stainless_steel.yaml, custom_material_template.yaml.
Structure per user spec (project / geometry / loading / material / fatigue /
study / optimization blocks; `_mm`, `_n`, `_hz` unit-suffixed keys).

## File structure

```
src/fatiguelife/
  __init__.py units.py materials.py geometry.py loading.py stress.py
  notch.py goodman.py basquin.py design.py sweep.py sensitivity.py
  config.py simulate.py io_data.py dashboard.py dashboard.html cli.py
tests/
  test_geometry.py test_stress.py test_goodman.py test_basquin.py
  test_materials.py test_sweeps.py test_design.py test_config.py
  test_dashboard.py
configs/  assets/  README.md  pyproject.toml  .gitignore
```

## Tooling (decision 2)

`uv` + `pyproject.toml`. Python ≥ 3.10. Runtime
dependency: numpy only. `pyyaml` as optional extra `fatiguelife[yaml]`
(JSON configs work without it). pytest as dev dependency. No external APIs,
no scraping.

## Testing / verification

Twenty required pytest cases per user spec: analytical identities (I,
hand-calculated bending stress), proportionality trends (Pa, L, b, h
scalings), Kf/mean-stress/life monotonicity, yield and Goodman-invalid
triggers, S–N slope = b, optimizer feasibility, strict-config errors,
vague-material rejection, custom-material metadata requirements, export
provenance fields, dashboard smoke test. Described as "Code verification
through analytical relationships, unit tests, and expected physical trends"
— never as experimental validation.

## README

Portfolio-quality: title, description, research question, plain-language
explanation, scope warning, main equations, dashboard capabilities, quick
start, sample config, material data policy, assumptions/limitations,
testing/verification, project structure, screenshot placeholder
(`assets/dashboard-preview.png`), suggested application description (verbatim
from user spec).

## Development order

1. Skeleton + package setup → 2. units + dataclasses → 3. geometry + stress →
4. materials + validation → 5. Goodman + Basquin → 6. simulate + warnings →
7. CLI + config → 8. unit tests + trend checks → 9. sweeps + sensitivity →
10. sizing optimisation → 11. dashboard + SVG charts → 12. exports →
13. README + example configs → 14. full test run, honest status report.

## Non-negotiable rules (verbatim intent)

Python 3.10+; numpy only required runtime dep; PyYAML optional; pytest
dev-only; no external APIs; no scraping; never claim "most accurate" data;
never claim certified/experimentally validated life; illustrative presets
clearly distinguished from source-backed datasets; calculations separated
from dashboard; dataclasses, type hints, docstrings, robust errors, strict
config validation; every run reproducible from a config file; clean
GitHub-ready quality.
