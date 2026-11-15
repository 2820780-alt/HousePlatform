"""Conservative, idempotent calculation blocks for the strip-foundation draft."""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select, text

from app.models.module2_calculation_block import TechnologyCalculationBlock
from app.models.module2_technology import Technology, TechnologyMaterialRequirement, TechnologyWorkStep
from app.services.module2_calculation_blocks import add_block, encode_definition
from app.services.module2_calculation_graph import BlockParameter, CalculationBlock, CalculationNode

TECHNOLOGY_CODE = "FND_STRIP_MONOLITHIC_RC"
CONCRETE_WORK = "foundations_concrete_betonirovanie_konstrukciy"
FORMWORK_WORK = "foundations_concrete_montazh_opalubki_fundamenta"
REINFORCEMENT_WORK = "reinforcement_armirovanie_fundamenta"


def _id(technology_id: uuid.UUID, *parts: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "/".join(("atom", "fnd3", str(technology_id), *parts))))


def _parameter(key: str, label: str, unit: str, *, minimum: str = "0") -> BlockParameter:
    return BlockParameter(key, label, unit, minimum=Decimal(minimum))


def _strip_blocks(technology_id: uuid.UUID, roles: dict, steps: dict) -> tuple[CalculationBlock, ...]:
    def make(key, name, nodes, outputs, parameters, material_role=None, work_code=None,
             material_output=None, work_output=None):
        role = roles.get(material_role) if material_role else None
        step = steps.get(work_code) if work_code else None
        return CalculationBlock(
            id=_id(technology_id, key), name=name, nodes=tuple(nodes), outputs=tuple(outputs),
            parameters=tuple(parameters), material_id=str(role.canonical_material_id) if role else None,
            material_requirement_id=str(role.id) if role else None,
            work_code=work_code, work_step_id=str(step.id) if step else None,
            material_output_id=material_output, work_output_id=work_output,
        )

    def node(block, key, operation, unit, **kw):
        return CalculationNode(_id(technology_id, block, key), operation, unit, **kw)

    k = "concrete"
    length = node(k, "length", "INPUT", "m", input_key="geometry.length")
    width = node(k, "width", "INPUT", "m", input_key="geometry.width")
    height = node(k, "height", "INPUT", "m", input_key="geometry.height")
    overlaps = node(k, "overlaps", "INPUT", "m3", input_key="strip.overlap_volume")
    gross = node(k, "gross", "PRISM_VOLUME", "m3", inputs=(length.id, width.id, height.id))
    net = node(k, "net", "SUBTRACT", "m3", inputs=(gross.id, overlaps.id))
    blocks = [make(k, "Бетон ленты", (length, width, height, overlaps, gross, net), (net.id,),
                   (_parameter("geometry.length", "Суммарная длина участков", "m"),
                    _parameter("geometry.width", "Ширина ленты", "m"),
                    _parameter("geometry.height", "Высота ленты", "m"),
                    _parameter("strip.overlap_volume", "Объём пересечений участков", "m3")),
                   "FND2_BT_02", CONCRETE_WORK, net.id, net.id)]

    for code, title in (("REBAR_TOP", "Верхняя продольная арматура"),
                        ("REBAR_BOTTOM", "Нижняя продольная арматура"),
                        ("STIRRUPS", "Поперечная арматура и хомуты")):
        k = code.lower()
        unit_length = node(k, "length", "INPUT", "m", input_key=f"{k}.length")
        count = node(k, "count", "INPUT", "piece", input_key=f"{k}.count")
        lap = node(k, "lap", "INPUT", "m", input_key=f"{k}.lap_length")
        joints = node(k, "joints", "INPUT", "piece", input_key=f"{k}.lap_count")
        mass_per_m = node(k, "mass_per_m", "INPUT", "kg_per_m", input_key=f"{k}.mass_per_m")
        bars = node(k, "bars", "MULTIPLY", "m", inputs=(unit_length.id, count.id))
        lap_total = node(k, "lap_total", "MULTIPLY", "m", inputs=(lap.id, joints.id))
        total = node(k, "total", "ADD", "m", inputs=(bars.id, lap_total.id))
        mass = node(k, "mass", "MULTIPLY", "kg", inputs=(total.id, mass_per_m.id))
        blocks.append(make(k, title, (unit_length, count, lap, joints, mass_per_m, bars, lap_total, total, mass),
                           (total.id, mass.id),
                           (_parameter(f"{k}.length", "Длина одного элемента", "m"),
                            _parameter(f"{k}.count", "Количество элементов", "piece"),
                            _parameter(f"{k}.lap_length", "Длина одного нахлёста", "m"),
                            _parameter(f"{k}.lap_count", "Общее число нахлёстов", "piece"),
                            _parameter(f"{k}.mass_per_m", "Масса погонного метра", "kg_per_m", minimum="0.000001")),
                           code, REINFORCEMENT_WORK, total.id, mass.id))

    k = "formwork"
    panels = node(k, "panels", "INPUT", "m2", input_key="formwork.material_area")
    work = node(k, "work", "INPUT", "m2", input_key="formwork.installation_area")
    blocks.append(make(k, "Опалубка", (panels, work), (panels.id, work.id),
                       (_parameter("formwork.material_area", "Площадь приобретаемой фанеры", "m2"),
                        _parameter("formwork.installation_area", "Площадь монтажа опалубки", "m2")),
                       "FND2_FORM_01", FORMWORK_WORK, panels.id, work.id))
    return tuple(blocks)


async def add_strip_blocks(db, *, actor: object) -> dict:
    """Add missing draft blocks without overwriting previously edited blocks."""
    if db.bind.dialect.name != "postgresql":
        raise ValueError("Strip setup requires PostgreSQL transaction locking")
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('atom.fnd3.strip.blocks'))"))
    technologies = (await db.scalars(select(Technology).where(
        Technology.technology_code == TECHNOLOGY_CODE, Technology.status == "DRAFT").with_for_update())).all()
    if len(technologies) != 1:
        raise ValueError("Expected one strip-foundation draft")
    technology = technologies[0]
    role_codes = ("FND2_BT_02", "REBAR_TOP", "REBAR_BOTTOM", "STIRRUPS", "FND2_FORM_01")
    roles = {row.code: row for row in (await db.scalars(select(TechnologyMaterialRequirement).where(
        TechnologyMaterialRequirement.technology_id == technology.id,
        TechnologyMaterialRequirement.code.in_(role_codes)))).all()}
    if set(roles) != set(role_codes) or any(role.canonical_material_id is None for role in roles.values()):
        raise ValueError("Strip material roles need explicit M1 selections")
    work_codes = (CONCRETE_WORK, FORMWORK_WORK, REINFORCEMENT_WORK)
    work_rows = (await db.scalars(select(TechnologyWorkStep).where(
        TechnologyWorkStep.technology_id == technology.id,
        TechnologyWorkStep.work_code.in_(work_codes)))).all()
    steps = {row.work_code: row for row in work_rows}
    if len(work_rows) != len(work_codes) or set(steps) != set(work_codes):
        raise ValueError("Strip work steps are missing or ambiguous")
    blocks = _strip_blocks(technology.id, roles, steps)
    existing = {str(row.id): row for row in (await db.scalars(select(TechnologyCalculationBlock).where(
        TechnologyCalculationBlock.technology_id == technology.id))).all()}
    created, reused, edited = 0, 0, []
    for block in blocks:
        row = existing.get(block.id)
        if row:
            if (row.definition != encode_definition(block) or row.name != block.name or
                    str(row.material_id or "") != (block.material_id or "") or row.work_code != block.work_code):
                edited.append(block.name)
            else:
                reused += 1
            continue
        await add_block(db, technology_id=technology.id, block=block, actor=actor,
                        actor_id=getattr(actor, "id", None))
        created += 1
    return {"technology_id": str(technology.id), "created": created, "reused": reused, "edited": edited}
