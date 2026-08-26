"""Load YAML or JSON configs and turn them into validated model objects."""
import json
from dataclasses import dataclass
from pathlib import Path

from fatiguelife.geometry import Geometry
from fatiguelife.loading import Loading
from fatiguelife.materials import Material, MaterialError, PRESETS, material_from_dict
from fatiguelife.simulate import FatigueParams
from fatiguelife.units import mm_to_m


class ConfigError(ValueError):
    """Raised for any malformed, unknown, or missing configuration content."""


@dataclass(frozen=True)
class StudyParams:
    sweep_points: int = 9
    sweep_span_factor: float = 4.0


@dataclass(frozen=True)
class OptimizationParams:
    width_min_m: float
    width_max_m: float
    thickness_min_m: float
    thickness_max_m: float
    grid_points: int


@dataclass(frozen=True)
class Config:
    title: str
    geometry: Geometry
    loading: Loading
    material: Material
    fatigue: FatigueParams
    study: StudyParams
    optimization: OptimizationParams | None
    raw: dict


_SCHEMA: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    # section: (required keys, optional keys)
    "project": (("title",), ()),
    "geometry": (("length_mm", "width_mm", "thickness_mm"), ()),
    "loading": (("alternating_load_n", "mean_load_n", "frequency_hz"), ()),
    "material": ((), ("preset", "custom", "file")),
    "fatigue": (("notch_factor", "target_life_cycles",
                 "minimum_yield_safety_factor"), ()),
    "study": ((), ("sweep_points", "sweep_span_factor")),
    "optimization": (("width_min_mm", "width_max_mm", "thickness_min_mm",
                      "thickness_max_mm", "grid_points"), ()),
}
_REQUIRED_SECTIONS = ("project", "geometry", "loading", "material", "fatigue")


def _check_section(data: dict, section: str) -> dict:
    """Validate one section against the schema; return the section dict."""
    content = data[section]
    if not isinstance(content, dict):
        raise ConfigError(f"Section '{section}' must be a mapping of keys to values.")
    required, optional = _SCHEMA[section]
    allowed = set(required) | set(optional)
    unknown = sorted(set(content) - allowed)
    if unknown:
        raise ConfigError(
            f"Unknown key(s) {unknown} in section '{section}'. "
            f"Allowed keys: {sorted(allowed)}."
        )
    missing = sorted(set(required) - set(content))
    if missing:
        raise ConfigError(
            f"Missing required key(s) {missing} in section '{section}'."
        )
    return content


def _positive_number(section: str, key: str, value, unit_hint: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ConfigError(f"{section}.{key} must be a number ({unit_hint}); got {value!r}.")
    if value <= 0:
        raise ConfigError(
            f"{section}.{key} must be a positive number ({unit_hint}); got {value}."
        )
    return float(value)


def _number(section: str, key: str, value, unit_hint: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ConfigError(f"{section}.{key} must be a number ({unit_hint}); got {value!r}.")
    return float(value)


def _load_material(spec: dict, base_dir: Path) -> Material:
    keys = [k for k in ("preset", "custom", "file") if k in spec]
    if len(keys) != 1:
        raise ConfigError(
            "Section 'material' must contain exactly one of: 'preset', 'custom', "
            f"or 'file'; got {sorted(spec) or 'nothing'}."
        )
    kind = keys[0]
    if kind == "preset":
        name = spec["preset"]
        if name not in PRESETS:
            raise ConfigError(
                f"Unknown material preset {name!r}. Available presets: "
                f"{sorted(PRESETS)}."
            )
        return PRESETS[name]
    if kind == "custom":
        if not isinstance(spec["custom"], dict):
            raise ConfigError("material.custom must be a mapping of material fields.")
        try:
            return material_from_dict(spec["custom"])
        except MaterialError as exc:
            raise ConfigError(f"Invalid custom material: {exc}") from exc
    # kind == "file"
    path = (base_dir / str(spec["file"])).resolve()
    data = _parse_file(path)
    if not isinstance(data, dict):
        raise ConfigError(f"Material file {path} must contain a mapping of fields.")
    try:
        return material_from_dict(data)
    except MaterialError as exc:
        raise ConfigError(f"Invalid material file {path}: {exc}") from exc


def _parse_file(path: Path) -> dict:
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    text = path.read_text()
    suffix = path.suffix.lower()
    if suffix == ".json":
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"Invalid JSON in {path}: {exc}") from exc
    if suffix in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError as exc:
            raise ConfigError(
                "PyYAML is required for YAML configs. Install with: "
                "pip install 'fatiguelife[yaml]' -- or use a JSON config."
            ) from exc
        try:
            return yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc
    raise ConfigError(
        f"Unsupported config extension {path.suffix!r}; use .yaml, .yml, or .json."
    )


def config_from_dict(data: dict, base_dir: Path) -> Config:
    """Build a validated Config from a parsed dict (strict, SI-converted)."""
    if not isinstance(data, dict):
        raise ConfigError("Top-level config must be a mapping of sections.")
    unknown = sorted(set(data) - set(_SCHEMA))
    if unknown:
        raise ConfigError(
            f"Unknown top-level section(s) {unknown}. "
            f"Allowed sections: {sorted(_SCHEMA)}."
        )
    missing = sorted(set(_REQUIRED_SECTIONS) - set(data))
    if missing:
        raise ConfigError(f"Missing required section(s): {missing}.")

    project = _check_section(data, "project")
    geo = _check_section(data, "geometry")
    load = _check_section(data, "loading")
    mat = _check_section(data, "material")
    fat = _check_section(data, "fatigue")

    geometry = Geometry(
        length_m=mm_to_m(_positive_number("geometry", "length_mm", geo["length_mm"], "millimetres")),
        width_m=mm_to_m(_positive_number("geometry", "width_mm", geo["width_mm"], "millimetres")),
        thickness_m=mm_to_m(_positive_number("geometry", "thickness_mm", geo["thickness_mm"], "millimetres")),
    )
    loading = Loading(
        alternating_load_n=_number("loading", "alternating_load_n", load["alternating_load_n"], "newtons"),
        mean_load_n=_number("loading", "mean_load_n", load["mean_load_n"], "newtons"),
        frequency_hz=_number("loading", "frequency_hz", load["frequency_hz"], "hertz"),
    )
    material = _load_material(mat, base_dir)
    fatigue = FatigueParams(
        notch_factor=_positive_number("fatigue", "notch_factor", fat["notch_factor"], "dimensionless, >= 1"),
        target_life_cycles=_positive_number("fatigue", "target_life_cycles", fat["target_life_cycles"], "cycles"),
        minimum_yield_safety_factor=_positive_number(
            "fatigue", "minimum_yield_safety_factor", fat["minimum_yield_safety_factor"], "dimensionless"),
    )

    study = StudyParams()
    if "study" in data:
        st = _check_section(data, "study")
        study = StudyParams(
            sweep_points=int(_positive_number("study", "sweep_points", st.get("sweep_points", 9), "count")),
            sweep_span_factor=_positive_number("study", "sweep_span_factor", st.get("sweep_span_factor", 4.0), "factor"),
        )

    optimization = None
    if "optimization" in data:
        op = _check_section(data, "optimization")
        optimization = OptimizationParams(
            width_min_m=mm_to_m(_positive_number("optimization", "width_min_mm", op["width_min_mm"], "millimetres")),
            width_max_m=mm_to_m(_positive_number("optimization", "width_max_mm", op["width_max_mm"], "millimetres")),
            thickness_min_m=mm_to_m(_positive_number("optimization", "thickness_min_mm", op["thickness_min_mm"], "millimetres")),
            thickness_max_m=mm_to_m(_positive_number("optimization", "thickness_max_mm", op["thickness_max_mm"], "millimetres")),
            grid_points=int(_positive_number("optimization", "grid_points", op["grid_points"], "count")),
        )
        if optimization.width_min_m >= optimization.width_max_m:
            raise ConfigError("optimization.width_min_mm must be less than width_max_mm.")
        if optimization.thickness_min_m >= optimization.thickness_max_m:
            raise ConfigError("optimization.thickness_min_mm must be less than thickness_max_mm.")

    title = project["title"]
    if not isinstance(title, str) or not title.strip():
        raise ConfigError("project.title must be a non-empty string.")

    return Config(
        title=title, geometry=geometry, loading=loading, material=material,
        fatigue=fatigue, study=study, optimization=optimization, raw=data,
    )


def load_config(path: str | Path) -> Config:
    """Load and strictly validate a YAML or JSON config file."""
    path = Path(path)
    data = _parse_file(path)
    return config_from_dict(data, base_dir=path.parent)
