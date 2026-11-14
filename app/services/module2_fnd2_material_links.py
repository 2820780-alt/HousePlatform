"""Explicit preliminary material choices for the fifteen FND-2 drafts."""
from __future__ import annotations

import uuid

from sqlalchemy import select, text

from app.models.enums import MaterialStatus
from app.models.material import Material
from app.models.module2_technology import Technology, TechnologyMaterialRequirement
from app.services.audit_service import log_event


# Each entry is a selectable candidate, not an instruction to consume every
# alternative. Existing roles and their project-specific choices are retained.
MATERIAL_LINKS = {
    "FND_STRIP_MONOLITHIC_RC": ("BT-02", "RA-04", "RA-10", "ARM-AUX-01", "ARM-AUX-05", "FORM-01", "BASE-01", "BASE-02", "BASE-04", "WPR-01"),
    "FND_STRIP_PRECAST_FBS_FL": ("FBS-02", "FBS-05", "FBS-09", "FL-12", "RM-01", "BASE-01", "BASE-02", "WPR-01"),
    "FND_SLAB_MONOLITHIC_RC": ("BT-02", "RA-04", "ARM-AUX-01", "ARM-AUX-05", "FORM-01", "BASE-01", "BASE-02", "BASE-04", "WPR-01", "XPS-06"),
    "FND_SLAB_RIBBED_RC": ("BT-02", "RA-04", "RA-10", "ARM-AUX-01", "ARM-AUX-05", "FORM-01", "BASE-01", "BASE-02", "WPR-01", "XPS-06"),
    "FND_SLAB_USHP": ("BT-02", "RA-04", "XPS-06", "XPS-04", "BASE-01", "BASE-02", "BASE-04", "PEN-01", "PEN-02"),
    "FND_UFF": ("BT-02", "BT-01", "RA-04", "XPS-06", "BASE-01", "BASE-02", "BASE-04", "PEN-01", "PEN-02", "WPR-01"),
    "FND_PILE_BORED_RC": ("BT-03", "RA-04", "RA-10", "ARM-AUX-01", "ARM-AUX-05"),
    "FND_PILE_DRIVEN_RC": ("PILE-RC-01", "PILE-RC-02"),
    "FND_PILE_SCREW": ("PILE-S-01", "PILE-S-02", "PILE-S-03", "PILE-S-04", "PILE-S-05"),
    "FND_PILE_GRILLAGE": ("PILE-RC-01", "PILE-RC-02", "PILE-S-01", "PILE-S-02", "PILE-S-03", "BT-02", "RA-04", "RA-10", "ARM-AUX-01", "FORM-01"),
    "FND_COLUMN_CONCRETE_RC": ("BT-02", "RA-04", "RA-10", "ARM-AUX-01", "FORM-01"),
    "FND_BASEMENT_WALL_MONOLITHIC": ("BT-03", "RA-04", "FORM-01", "WPR-01", "WPR-03", "WPR-04", "XPS-03", "PEN-01", "PEN-02"),
    "FND_SUBSTRUCTURE_WATERPROOFING_COATING": ("WPR-02", "WPR-01", "WPR-05", "XPS-03"),
    "FND_SUBSTRUCTURE_WATERPROOFING_MEMBRANE": ("WPR-03", "WPR-02", "WPR-04", "WPR-05", "XPS-03"),
    "FND_SUBSTRUCTURE_INSULATION_XPS": ("XPS-03", "XPS-06", "XPS-02", "XPS-04", "XPS-08", "XPS-09", "XPS-10"),
}

MONOLITHIC = (
    "FND_STRIP_MONOLITHIC_RC", "FND_SLAB_MONOLITHIC_RC", "FND_SLAB_RIBBED_RC", "FND_SLAB_USHP",
    "FND_UFF", "FND_PILE_GRILLAGE", "FND_COLUMN_CONCRETE_RC", "FND_BASEMENT_WALL_MONOLITHIC",
)
for _code in MONOLITHIC:
    MATERIAL_LINKS[_code] += ("ARM-AUX-02", "ARM-AUX-03", "ARM-AUX-04", "ARM-AUX-06",
                              "FORM-02", "FORM-03", "FORM-04", "FORM-05", "FORM-06", "FORM-07", "FORM-10")
MATERIAL_LINKS["FND_BASEMENT_WALL_MONOLITHIC"] += (
    "BASE-03", "BASE-05", "DRN-01", "DRN-02", "DRN-03-DN110", "DRN-03-DN160",
    "DRN-04-DN110", "DRN-04-DN160", "DRN-05-DN110", "DRN-05-DN160",
)
UNDERGROUND = ("FND_STRIP_MONOLITHIC_RC", "FND_STRIP_PRECAST_FBS_FL", "FND_BASEMENT_WALL_MONOLITHIC")
WATERPROOFING = ("FND_SUBSTRUCTURE_WATERPROOFING_COATING", "FND_SUBSTRUCTURE_WATERPROOFING_MEMBRANE")
CONDITIONAL_ROLES = {
    "FORM-08": MONOLITHIC,
    "FORM-09": MONOLITHIC,
    "ARM-AUX-07": ("FND_SLAB_MONOLITHIC_RC", "FND_SLAB_RIBBED_RC", "FND_SLAB_USHP"),
    "WPR-06": UNDERGROUND + ("FND_SLAB_MONOLITHIC_RC",),
    "WPR-07": UNDERGROUND + ("FND_SLAB_MONOLITHIC_RC",),
    "WPR-08": UNDERGROUND + WATERPROOFING,
    "WPR-09": ("FND_BASEMENT_WALL_MONOLITHIC", "FND_SLAB_USHP", "FND_UFF"),
    "WPR-10": WATERPROOFING + ("FND_BASEMENT_WALL_MONOLITHIC",),
    "DRN-06": ("FND_BASEMENT_WALL_MONOLITHIC",),
    "DRN-07": ("FND_BASEMENT_WALL_MONOLITHIC",),
    "PEN-03": ("FND_BASEMENT_WALL_MONOLITHIC", "FND_SLAB_USHP", "FND_UFF"),
    "PEN-04": ("FND_BASEMENT_WALL_MONOLITHIC", "FND_SLAB_USHP", "FND_UFF"),
    "PILE-S-06": ("FND_PILE_SCREW", "FND_PILE_GRILLAGE"),
}


async def link_material_choices(db, *, material_ids: dict[str, str]) -> dict:
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('atom.fnd2.technology.materials'))"))
    technologies = list((await db.scalars(select(Technology).where(
        Technology.status == "DRAFT", Technology.technology_code.in_(MATERIAL_LINKS)).with_for_update())).all())
    by_code = {tech.technology_code: tech for tech in technologies}
    if len(technologies) != 15 or len(by_code) != 15:
        raise ValueError("Expected exactly one DRAFT for each of 15 foundation technologies")
    wanted = {key for keys in MATERIAL_LINKS.values() for key in keys}
    if wanted - set(material_ids):
        raise ValueError("Required material candidates have not been resolved")
    ids = {key: uuid.UUID(material_ids[key]) for key in wanted}
    available = set((await db.scalars(select(Material.id).where(
        Material.id.in_(ids.values()), Material.status.not_in((MaterialStatus.ARCHIVED, MaterialStatus.REJECTED))))).all())
    if set(ids.values()) - available:
        raise ValueError("A referenced material is missing or archived")
    results = {}
    for code, keys in MATERIAL_LINKS.items():
        technology = by_code[code]
        rows = list((await db.scalars(select(TechnologyMaterialRequirement).where(
            TechnologyMaterialRequirement.technology_id == technology.id))).all())
        by_requirement = {row.code: row for row in rows}
        linked = {row.canonical_material_id for row in rows if row.canonical_material_id}
        created = reused = 0
        for key in keys:
            requirement_code = "FND2_" + key.replace("-", "_")
            material_id = ids[key]
            previous = by_requirement.get(requirement_code)
            if previous:
                if previous.canonical_material_id != material_id:
                    raise ValueError(f"Existing FND-2 role changed: {code}/{key}")
                reused += 1
            elif material_id in linked:
                reused += 1
            else:
                requirement = TechnologyMaterialRequirement(
                    id=uuid.uuid5(uuid.NAMESPACE_URL, f"atom/fnd2/{technology.id}/{key}"),
                    technology_id=technology.id, code=requirement_code,
                    selector_kind="CANONICAL_MATERIAL", material_role_code=requirement_code,
                    canonical_material_id=material_id,
                    technical_constraints={"fnd2_selection": "project_confirmation_required"},
                    notes="Предварительный вариант; применение, совместимость и количество определяются проектом. Альтернативы не суммировать.")
                db.add(requirement)
                linked.add(material_id)
                created += 1
        await log_event(db, "M2_FND2_MATERIAL_CHOICES", "Technology", technology.id, None,
                        {"created": created, "reused": reused})
        results[code] = {"created": created, "reused": reused}
    await db.flush()
    return results


async def link_unresolved_roles(db, *, rows: list[list[str]]) -> dict:
    """Keep unspecified executions as conditional M2 roles, never fake M1 products."""
    source = {row[0]: row for row in rows if len(row) == 6 and all(row[i] for i in (0, 1, 4, 5))}
    if len(rows) != 13 or set(source) != set(CONDITIONAL_ROLES):
        raise ValueError("Expected the thirteen reviewed conditional roles")
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('atom.fnd2.technology.materials'))"))
    techs = list((await db.scalars(select(Technology).where(
        Technology.status == "DRAFT", Technology.technology_code.in_(MATERIAL_LINKS)).with_for_update())).all())
    by_code = {tech.technology_code: tech for tech in techs}
    if len(techs) != 15 or len(by_code) != 15:
        raise ValueError("Expected exactly one DRAFT for each of 15 foundation technologies")
    existing = {(item.technology_id, item.code): item for item in (await db.scalars(
        select(TechnologyMaterialRequirement).where(
            TechnologyMaterialRequirement.technology_id.in_([tech.id for tech in techs])))).all()}
    result = {"created": 0, "reused": 0, "source_roles": len(source)}
    for key, destinations in CONDITIONAL_ROLES.items():
        _, name, _group, unit_hint, decision, required = source[key]
        role_code = "FND2_ROLE_" + key.replace("-", "_")
        for code in destinations:
            tech = by_code[code]
            previous = existing.get((tech.id, role_code))
            if previous:
                if previous.selector_kind != "ROLE" or previous.canonical_material_id is not None:
                    raise ValueError(f"Conditional role changed: {code}/{key}")
                result["reused"] += 1
                continue
            db.add(TechnologyMaterialRequirement(
                id=uuid.uuid5(uuid.NAMESPACE_URL, f"atom/fnd2/{tech.id}/role/{key}"),
                technology_id=tech.id, code=role_code, selector_kind="ROLE", material_role_code=role_code,
                technical_constraints={"conditional": True, "selection_required": True,
                                       "source_unit_hint": unit_hint, "source_unit_unconfirmed": True},
                notes=f"{name}. {decision}. {required}. Применять только по проекту; исполнение не выбрано."))
            result["created"] += 1
    await db.flush()
    return result
