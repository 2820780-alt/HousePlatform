"""Typed project inputs for foundation geometry, without engineering defaults."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping


@dataclass(frozen=True)
class GeometryField:
    key: str
    label: str
    unit: str
    required: bool = False
    allow_zero: bool = False


@dataclass(frozen=True)
class GeometryDefault:
    value: str
    unit: str
    source: str
    status: str


@dataclass(frozen=True)
class ResolvedGeometry:
    values: dict[str, tuple[Decimal, str]]
    provenance: dict[str, str]
    missing: tuple[str, ...]
    warnings: tuple[str, ...]
    default_sources: dict[str, str]


def field(key: str, label: str, unit: str, required: bool = False, allow_zero: bool = False) -> GeometryField:
    return GeometryField(key, label, unit, required, allow_zero)


STRIP = (field("geometry.length", "Суммарная длина участков", "m", True),
         field("geometry.width", "Ширина ленты", "m", True),
         field("geometry.height", "Высота ленты", "m", True),
         field("strip.overlap_volume", "Объём пересечений", "m3", True, True))
SLAB = (field("geometry.net_area", "Площадь плиты с учётом вырезов", "m2", True),
        field("geometry.slab_thickness", "Толщина плиты", "m", True))
RIBS = (field("geometry.rib_length", "Суммарная длина рёбер", "m", True),
        field("geometry.rib_width", "Ширина ребра", "m", True),
        field("geometry.rib_height", "Высота ребра вне плиты", "m", True),
        field("geometry.rib_overlap_volume", "Объём пересечений рёбер", "m3", True, True))
PILE_CYLINDER = (field("pile.diameter", "Диаметр сваи", "m", True),
                 field("pile.length", "Длина сваи", "m", True),
                 field("pile.count", "Количество свай", "piece", True))
PILE_COUNT = (field("pile.count", "Количество свай", "piece", True),)
SCREW_PILE = PILE_COUNT + (field("pile.head_count", "Количество оголовков", "piece", True, True),)
PIER = (field("element.length", "Длина опоры", "m", True),
        field("element.width", "Ширина опоры", "m", True),
        field("element.height", "Высота опоры", "m", True),
        field("element.count", "Количество опор", "piece", True))
WALL = (field("geometry.wall_length", "Суммарная длина стен", "m", True),
        field("geometry.wall_height", "Высота стен", "m", True),
        field("geometry.wall_thickness", "Толщина стен", "m", True),
        field("geometry.opening_area", "Площадь проёмов", "m2", True, True),
        field("geometry.wall_overlap_volume", "Объём пересечений стен", "m3", True, True))
SURFACE = (field("geometry.area", "Площадь поверхности", "m2", True),)
PRECAST = (field("layout.fbs_main", "Количество ФБС основной марки", "piece", True, True),
           field("layout.fbs_short", "Количество коротких ФБС", "piece", True, True),
           field("layout.fbs_shorter", "Количество доборных ФБС", "piece", True, True),
           field("layout.fl", "Количество плит ФЛ", "piece", True, True))
ZONES = (field("geometry.wall_area", "Площадь утепления стен", "m2", False, True),
         field("geometry.slab_area", "Площадь утепления под плитой", "m2", False, True),
         field("geometry.edge_area", "Площадь утепления торцов", "m2", False, True))

FOUNDATION_FIELDS = {
    "FND_STRIP_MONOLITHIC_RC": STRIP,
    "FND_STRIP_PRECAST_FBS_FL": PRECAST,
    "FND_SLAB_MONOLITHIC_RC": SLAB,
    "FND_SLAB_RIBBED_RC": SLAB + RIBS,
    "FND_SLAB_USHP": SLAB + RIBS + ZONES,
    "FND_UFF": STRIP + SLAB + ZONES,
    "FND_PILE_BORED_RC": PILE_CYLINDER,
    "FND_PILE_DRIVEN_RC": PILE_COUNT,
    "FND_PILE_SCREW": SCREW_PILE,
    "FND_PILE_GRILLAGE": STRIP + PILE_COUNT,
    "FND_COLUMN_CONCRETE_RC": PIER,
    "FND_BASEMENT_WALL_MONOLITHIC": WALL,
    "FND_SUBSTRUCTURE_WATERPROOFING_COATING": SURFACE,
    "FND_SUBSTRUCTURE_WATERPROOFING_MEMBRANE": SURFACE,
    "FND_SUBSTRUCTURE_INSULATION_XPS": ZONES,
}


def _value(value: object, spec: GeometryField) -> Decimal:
    if isinstance(value, (bool, float)) or value is None:
        raise ValueError(f"{spec.key}: an exact number is required")
    try:
        number = Decimal(str(value).strip().replace(",", "."))
    except (InvalidOperation, ValueError):
        raise ValueError(f"{spec.key}: an exact number is required") from None
    if (not number.is_finite() or number < 0 or (number == 0 and not spec.allow_zero) or
            number.adjusted() > 9 or number.as_tuple().exponent < -6):
        raise ValueError(f"{spec.key}: number is outside the permitted range")
    if spec.unit == "piece" and number != number.to_integral_value():
        raise ValueError(f"{spec.key}: count must be an integer")
    return number


def resolve_foundation_geometry(
    technology_code: str, *, user_values: Mapping[str, object], project_values: Mapping[str, object],
    defaults: Mapping[str, GeometryDefault] | None = None, allow_preliminary: bool = False,
) -> ResolvedGeometry:
    """Resolve explicit override > project > sourced M2 default; never infer a value."""
    specs = FOUNDATION_FIELDS.get(technology_code)
    if specs is None:
        raise ValueError("unsupported foundation technology")
    defaults = defaults or {}
    allowed = {spec.key for spec in specs}
    if (set(user_values) | set(project_values) | set(defaults)) - allowed:
        raise ValueError("unknown geometry parameter")
    values, provenance, missing, warnings, default_sources = {}, {}, [], [], {}
    for spec in specs:
        default = defaults.get(spec.key)
        if spec.key in user_values and user_values[spec.key] is not None:
            value, source = user_values[spec.key], "USER_OVERRIDE"
        elif spec.key in project_values and project_values[spec.key] is not None:
            value, source = project_values[spec.key], "PROJECT_VALUE"
        elif default is not None:
            if (not isinstance(default, GeometryDefault) or default.unit != spec.unit or not default.source.strip() or
                    default.status not in {"VERIFIED", "PRELIMINARY"}):
                raise ValueError(f"{spec.key}: invalid M2 default")
            if default.status == "PRELIMINARY" and not allow_preliminary:
                if spec.required:
                    missing.append(spec.key)
                continue
            value, source = default.value, "M2_DEFAULT"
            default_sources[spec.key] = default.source.strip()
            if default.status == "PRELIMINARY":
                warnings.append(spec.key)
        else:
            if spec.required:
                missing.append(spec.key)
            continue
        values[spec.key] = (_value(value, spec), spec.unit)
        provenance[spec.key] = source
    if technology_code == "FND_SUBSTRUCTURE_INSULATION_XPS" and not any(
            values.get(key, (Decimal(0), "m2"))[0] > 0
            for key in ("geometry.wall_area", "geometry.slab_area", "geometry.edge_area")):
        missing.append("geometry.insulation_zone")
    if technology_code == "FND_STRIP_PRECAST_FBS_FL" and not any(
            values.get(key, (Decimal(0), "piece"))[0] > 0
            for key in ("layout.fbs_main", "layout.fbs_short", "layout.fbs_shorter", "layout.fl")):
        missing.append("layout.items")
    return ResolvedGeometry(values, provenance, tuple(missing), tuple(warnings), default_sources)
