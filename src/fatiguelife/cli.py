"""Command-line entry points for FatigueLife."""
import argparse
import subprocess
import sys
from pathlib import Path

from fatiguelife import MATERIAL_NOTICE, SCOPE_STATEMENT
from fatiguelife import io_data
from fatiguelife.config import Config, ConfigError, load_config
from fatiguelife.design import run_sizing
from fatiguelife.materials import Material, MaterialError
from fatiguelife.sensitivity import run_sensitivity
from fatiguelife.simulate import ASSUMPTIONS, SimulationResult
from fatiguelife.sweep import SWEEPABLE, run_sweep, simulate_config
from fatiguelife.units import format_cycles, format_stress_mpa, kg_to_g, m_to_mm

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _print_material(material: Material) -> None:
    print("Material")
    print(f"  name:        {material.name}")
    print(f"  confidence:  {material.confidence}")
    print(f"  source:      {material.source}")
    print(f"  condition:   form={material.product_form}; "
          f"heat treatment={material.heat_treatment}; "
          f"surface={material.surface_condition}; "
          f"environment={material.environment}; R={material.stress_ratio_r:g}")
    print(f"  Sy = {format_stress_mpa(material.yield_strength_pa)}, "
          f"Sut = {format_stress_mpa(material.ultimate_strength_pa)}, "
          f"A = {format_stress_mpa(material.basquin_coefficient_pa)}, "
          f"b = {material.basquin_exponent:g}")
    print(f"  applicable life range: {format_cycles(material.life_range_min_cycles)} "
          f"to {format_cycles(material.life_range_max_cycles)} cycles")
    if material.condition_note:
        print(f"  note:        {material.condition_note}")
    print(f"  NOTICE: {MATERIAL_NOTICE}")


def _print_inputs(cfg: Config) -> None:
    g, load, fatigue = cfg.geometry, cfg.loading, cfg.fatigue
    print("Inputs")
    print(f"  L = {m_to_mm(g.length_m):g} mm, b = {m_to_mm(g.width_m):g} mm, "
          f"h = {m_to_mm(g.thickness_m):g} mm")
    print(f"  Pa = {load.alternating_load_n:g} N, Pm = {load.mean_load_n:g} N, "
          f"f = {load.frequency_hz:g} Hz (display only)")
    print(f"  Kf = {fatigue.notch_factor:g}, target life = "
          f"{format_cycles(fatigue.target_life_cycles)} cycles, "
          f"required n_y = {fatigue.minimum_yield_safety_factor:g}")


def _print_report(cfg: Config, result: SimulationResult) -> None:
    print(f"== {cfg.title} ==")
    print(f"SCOPE: {SCOPE_STATEMENT}")
    print()
    _print_inputs(cfg)
    print()
    _print_material(result.material)
    print()
    print(f"Status: {result.status.label}  [{result.badge()}]")

    def stress(value_pa: float | None) -> str:
        return format_stress_mpa(value_pa) if value_pa is not None else "n/a"

    print("Results")
    life = (format_cycles(result.fatigue_life_cycles) + " cycles"
            if result.fatigue_life_cycles is not None else "no prediction")
    print(f"  predicted fatigue life:    {life}")
    print(f"  beam mass:                 {kg_to_g(result.mass_kg):.1f} g")
    print(f"  nominal alternating:       {stress(result.nominal_alternating_stress_pa)}")
    print(f"  local alternating:         {stress(result.local_alternating_stress_pa)}")
    print(f"  nominal mean:              {stress(result.nominal_mean_stress_pa)}")
    print(f"  Goodman equivalent:        {stress(result.goodman_equivalent_stress_pa)}")
    print(f"  maximum local stress:      {stress(result.max_local_stress_pa)}")
    ny = result.yield_safety_factor
    print(f"  yield safety factor:       {ny:.2f}" if ny is not None
          else "  yield safety factor:       n/a")
    if result.meets_target_life is not None:
        print(f"  meets target life:         {result.meets_target_life}")
    if result.meets_yield_requirement is not None:
        print(f"  meets yield requirement:   {result.meets_yield_requirement}")
    for warning in result.warnings:
        print(f"  WARNING: {warning}")
    for error in result.errors:
        print(f"  INVALID: {error}")


def _cmd_run(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    result = simulate_config(cfg)
    _print_report(cfg, result)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    json_path = io_data.write_summary_json(cfg, result, outdir / "summary.json")
    csv_path = io_data.write_summary_csv(cfg, result, outdir / "summary.csv")
    print()
    print(f"Exported: {json_path} and {csv_path}")
    return 0


def _cmd_sweep(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    parameters = [args.parameter] if args.parameter else list(SWEEPABLE)
    print(f"== Parameter sweeps: {cfg.title} ==")
    print(f"SCOPE: {SCOPE_STATEMENT}")
    for parameter in parameters:
        points = run_sweep(cfg, parameter)
        path = io_data.write_sweep_csv(parameter, points, cfg.material,
                                       outdir / f"sweep_{parameter}.csv")
        print(f"\n{parameter}  (exported to {path})")
        print(f"  {'value':>12}  {'life (cycles)':>14}  {'n_y':>8}  status")
        for point in points:
            life = (format_cycles(point.fatigue_life_cycles)
                    if point.fatigue_life_cycles is not None else "n/a")
            ny = f"{point.yield_safety_factor:.2f}" if point.yield_safety_factor is not None else "n/a"
            print(f"  {point.value:>12.4g}  {life:>14}  {ny:>8}  {point.status_badge}")
    return 0


def _cmd_sensitivity(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    print(f"== Sensitivity of predicted life: {cfg.title} ==")
    print(f"SCOPE: {SCOPE_STATEMENT}\n")
    for res in run_sensitivity(cfg):
        value = f"{res.value:+.2f}" if res.value is not None else "n/a"
        print(f"  {res.parameter:<20} {res.kind:<11} {value:>8}   {res.interpretation}")
    return 0


def _cmd_optimize(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    result = run_sizing(cfg)
    print(f"== Lightweight design study: {cfg.title} ==")
    print(f"SCOPE: {SCOPE_STATEMENT}")
    print(f"NOTE: {result.note}")
    print(f"Evaluated {result.evaluated} designs; {result.feasible_count} feasible.")
    if result.best is None:
        print("No feasible design in the given bounds.")
    else:
        best = result.best
        print(f"\nMinimum-mass feasible design: b = {best.width_mm:.2f} mm, "
              f"h = {best.thickness_mm:.2f} mm, mass = {kg_to_g(best.mass_kg):.1f} g, "
              f"life = {format_cycles(best.fatigue_life_cycles)} cycles, "
              f"n_y = {best.yield_safety_factor:.2f}")
        print("\nTop feasible designs by lowest mass:")
        print(f"  {'b (mm)':>8}  {'h (mm)':>8}  {'mass (g)':>9}  {'life (cycles)':>14}  {'n_y':>6}")
        for c in result.top:
            print(f"  {c.width_mm:>8.2f}  {c.thickness_mm:>8.2f}  "
                  f"{kg_to_g(c.mass_kg):>9.1f}  {format_cycles(c.fatigue_life_cycles):>14}  "
                  f"{c.yield_safety_factor:>6.2f}")
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    path = io_data.write_sizing_csv(result, cfg.material, outdir / "sizing.csv")
    print(f"\nExported: {path}")
    return 0


def _cmd_info(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    print(f"== {cfg.title} ==")
    print(f"SCOPE: {SCOPE_STATEMENT}\n")
    _print_inputs(cfg)
    print()
    _print_material(cfg.material)
    print("\nAssumptions and limitations:")
    for assumption in ASSUMPTIONS:
        print(f"  - {assumption}")
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    from fatiguelife.dashboard import serve

    cfg = load_config(args.config) if args.config else None
    serve(cfg, args.port)
    return 0


def _cmd_test(args: argparse.Namespace) -> int:
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q"], cwd=PROJECT_ROOT
    )
    return completed.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fatiguelife",
        description="Educational fatigue-life estimation for cantilever brackets. "
                    + SCOPE_STATEMENT,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="single simulation with report and exports")
    p_run.add_argument("config")
    p_run.add_argument("--outdir", default="out")
    p_run.set_defaults(func=_cmd_run)

    p_sweep = sub.add_parser("sweep", help="parameter sweeps with CSV export")
    p_sweep.add_argument("config")
    p_sweep.add_argument("--outdir", default="out")
    p_sweep.add_argument("--parameter", choices=list(SWEEPABLE))
    p_sweep.set_defaults(func=_cmd_sweep)

    p_sens = sub.add_parser("sensitivity", help="ranked life sensitivities")
    p_sens.add_argument("config")
    p_sens.set_defaults(func=_cmd_sensitivity)

    p_opt = sub.add_parser("optimize", help="grid-based minimum-mass sizing study")
    p_opt.add_argument("config")
    p_opt.add_argument("--outdir", default="out")
    p_opt.set_defaults(func=_cmd_optimize)

    p_info = sub.add_parser("info", help="show parsed config, material, assumptions")
    p_info.add_argument("config")
    p_info.set_defaults(func=_cmd_info)

    p_serve = sub.add_parser("serve", help="launch the local dashboard")
    p_serve.add_argument("config", nargs="?")
    p_serve.add_argument("--port", type=int, default=8765)
    p_serve.set_defaults(func=_cmd_serve)

    p_test = sub.add_parser("test", help="run the test suite")
    p_test.set_defaults(func=_cmd_test)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ConfigError, MaterialError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
