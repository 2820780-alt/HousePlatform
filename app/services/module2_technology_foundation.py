from __future__ import annotations

import uuid
from copy import deepcopy
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.access_levels import AccessLevel
from app.core.permission_guard import LEGACY_ROLE_ALIASES
from app.core.role_access_matrix import STARTER_ROLE_MODULE_ACCESS
from app.models.module2_technology import (
    MODULE2_OWNER_CODE,
    Technology,
    TechnologyEvidenceReference,
    TechnologyLayer,
    TechnologyMaterialRequirement,
    TechnologyNode,
    TechnologyWorkStep,
)
from app.schemas.module2_technology import (
    MaterialRequirementSelector,
    Module2InputAcceptance,
    TechnologyDraftInput,
    TechnologyDraftUpdate,
    TechnologyLifecycle,
    TechnologyMaterialRequirementInput,
)
from app.services.module1_export_packages import Module2TechnologyInputPackage
from app.services.module1_work_catalog import get_work_item


_ACCESS_RANK = {
    AccessLevel.NO_ACCESS: 0,
    AccessLevel.VIEW: 1,
    AccessLevel.CREATE: 2,
    AccessLevel.EDIT: 3,
    AccessLevel.APPROVE: 4,
    AccessLevel.ADMIN: 5,
}
_ALLOWED_TRANSITIONS = {
    TechnologyLifecycle.DRAFT: {TechnologyLifecycle.REVIEW},
    TechnologyLifecycle.REVIEW: {TechnologyLifecycle.DRAFT, TechnologyLifecycle.ACTIVE},
    TechnologyLifecycle.ACTIVE: {TechnologyLifecycle.ARCHIVED},
    TechnologyLifecycle.ARCHIVED: set(),
}


class Module2TechnologyError(ValueError):
    pass


class Module2TechnologyPermissionError(PermissionError):
    pass


def accept_module1_input(
    package: Module2TechnologyInputPackage,
) -> Module2InputAcceptance:
    if package.no_side_effects is not True:
        raise Module2TechnologyError("M1 package must declare no_side_effects")
    if package.no_calculation_result is not True:
        raise Module2TechnologyError("M1 package must not contain a calculation result")

    raw_material_id = package.clean_material.material_id
    canonical_material_id = None
    blockers = list(package.blockers)
    if raw_material_id:
        try:
            canonical_material_id = uuid.UUID(str(raw_material_id))
        except ValueError:
            blockers.append("invalid_canonical_material_id")
    else:
        blockers.append("missing_identity")

    missing_fields = _unique(package.missing_fields)
    normalized_blockers = _unique(blockers)
    return Module2InputAcceptance(
        canonical_material_id=canonical_material_id,
        missing_fields=missing_fields,
        blockers=normalized_blockers,
        accepted_for_active_technology=bool(
            canonical_material_id and not missing_fields and not normalized_blockers
        ),
    )


def material_requirement_from_module1(
    package: Module2TechnologyInputPackage,
    *,
    code: str,
    material_role_code: str,
    notes: str | None = None,
) -> TechnologyMaterialRequirementInput:
    acceptance = accept_module1_input(package)
    if acceptance.canonical_material_id is None:
        raise Module2TechnologyError("M1 package does not identify a canonical material")
    return TechnologyMaterialRequirementInput(
        code=code,
        selector_kind=MaterialRequirementSelector.CANONICAL_MATERIAL,
        canonical_material_id=acceptance.canonical_material_id,
        material_role_code=material_role_code,
        notes=notes,
    )


def build_draft_technology(
    data: TechnologyDraftInput | dict,
    *,
    actor_role_code: str,
    input_package: Module2TechnologyInputPackage | None = None,
    created_by_user_id: uuid.UUID | None = None,
) -> Technology:
    require_module2_access(actor_role_code, AccessLevel.EDIT)
    command = data if isinstance(data, TechnologyDraftInput) else TechnologyDraftInput.model_validate(data)
    acceptance = accept_module1_input(input_package) if input_package else Module2InputAcceptance()

    technology = Technology(
        id=uuid.uuid4(),
        technology_code=command.technology_code,
        revision=1,
        name=command.name,
        description=command.description,
        system_code=command.system_code,
        status=TechnologyLifecycle.DRAFT.value,
        owner_module_code=MODULE2_OWNER_CODE,
        source_kind=command.source_kind,
        input_missing_fields=list(acceptance.missing_fields),
        input_blockers=list(acceptance.blockers),
        created_by_user_id=created_by_user_id,
    )

    requirements = {
        item.code: TechnologyMaterialRequirement(
            id=uuid.uuid4(),
            code=item.code,
            selector_kind=item.selector_kind.value,
            material_role_code=item.material_role_code,
            canonical_material_id=item.canonical_material_id,
            material_category_id=item.material_category_id,
            material_type_id=item.material_type_id,
            technical_constraints=deepcopy(item.technical_constraints),
            notes=item.notes,
        )
        for item in command.requirements
    }
    technology.requirements.extend(requirements.values())

    for item in sorted(command.layers, key=lambda value: value.position):
        technology.layers.append(
            TechnologyLayer(
                id=uuid.uuid4(),
                position=item.position,
                functional_role=item.functional_role,
                material_requirement=requirements.get(item.requirement_code),
                thickness_expression=item.thickness_expression,
                is_mandatory=item.is_mandatory,
                notes=item.notes,
                restrictions=deepcopy(item.restrictions),
            )
        )

    for item in command.nodes:
        technology.nodes.append(
            TechnologyNode(
                id=uuid.uuid4(),
                code=item.code,
                node_type=item.node_type,
                name=item.name,
                description=item.description,
                conditions=deepcopy(item.conditions),
            )
        )

    for item in sorted(command.work_steps, key=lambda value: value.position):
        if get_work_item(item.work_code) is None:
            raise Module2TechnologyError(
                f"unknown Module1 Work Catalog code: {item.work_code}"
            )
        technology.work_steps.append(
            TechnologyWorkStep(
                id=uuid.uuid4(),
                position=item.position,
                work_code=item.work_code,
                applicability_expression=item.applicability_expression,
                dependency_step_codes=list(item.dependency_step_codes),
                instructions=item.instructions,
            )
        )

    for item in command.evidence_references:
        technology.evidence_references.append(
            TechnologyEvidenceReference(
                id=uuid.uuid4(),
                document_id=item.document_id,
                knowledge_resource_id=item.knowledge_resource_id,
                target_kind=item.target_kind,
                target_reference=item.target_reference,
                interpretation=item.interpretation,
            )
        )
    return technology


def update_draft_technology(
    technology: Technology,
    data: TechnologyDraftUpdate | dict,
    *,
    actor_role_code: str,
) -> Technology:
    require_module2_access(actor_role_code, AccessLevel.EDIT)
    if technology.status != TechnologyLifecycle.DRAFT.value:
        raise Module2TechnologyError("only a DRAFT technology can be updated in place")
    command = data if isinstance(data, TechnologyDraftUpdate) else TechnologyDraftUpdate.model_validate(data)
    for field_name in command.model_fields_set:
        setattr(technology, field_name, getattr(command, field_name))
    return technology


def transition_technology(
    technology: Technology,
    target: TechnologyLifecycle | str,
    *,
    actor_role_code: str,
) -> Technology:
    current = TechnologyLifecycle(technology.status)
    target_status = target if isinstance(target, TechnologyLifecycle) else TechnologyLifecycle(target)
    if target_status not in _ALLOWED_TRANSITIONS[current]:
        raise Module2TechnologyError(
            f"unsupported technology lifecycle transition: {current.value} -> {target_status.value}"
        )

    required_access = AccessLevel.EDIT
    if target_status == TechnologyLifecycle.ACTIVE or target_status == TechnologyLifecycle.DRAFT:
        required_access = AccessLevel.APPROVE
    elif target_status == TechnologyLifecycle.ARCHIVED:
        required_access = AccessLevel.ADMIN
    require_module2_access(actor_role_code, required_access)

    if target_status == TechnologyLifecycle.ACTIVE:
        blockers = validate_technology_activation(technology)
        if technology.input_missing_fields or technology.input_blockers:
            raise Module2TechnologyError("incomplete M1 input cannot activate a technology")
        if "missing_layer" in blockers:
            raise Module2TechnologyError("technology requires at least one layer before activation")

    technology.status = target_status.value
    return technology


def validate_technology_activation(technology: Technology) -> tuple[str, ...]:
    blockers = [
        *(f"missing_m1_field:{item}" for item in technology.input_missing_fields or ()),
        *(f"m1_blocker:{item}" for item in technology.input_blockers or ()),
    ]
    if not technology.layers:
        blockers.append("missing_layer")
    return _unique(blockers)


def create_next_revision(
    technology: Technology,
    *,
    actor_role_code: str,
    created_by_user_id: uuid.UUID | None = None,
) -> Technology:
    require_module2_access(actor_role_code, AccessLevel.EDIT)
    if technology.status != TechnologyLifecycle.ACTIVE.value:
        raise Module2TechnologyError("a new revision can only supersede ACTIVE technology")

    revised = Technology(
        id=uuid.uuid4(),
        technology_code=technology.technology_code,
        revision=technology.revision + 1,
        name=technology.name,
        description=technology.description,
        system_code=technology.system_code,
        status=TechnologyLifecycle.DRAFT.value,
        owner_module_code=MODULE2_OWNER_CODE,
        source_kind=technology.source_kind,
        input_missing_fields=deepcopy(technology.input_missing_fields),
        input_blockers=deepcopy(technology.input_blockers),
        supersedes=technology,
        created_by_user_id=created_by_user_id,
    )

    requirements: dict[uuid.UUID, TechnologyMaterialRequirement] = {}
    for item in technology.requirements:
        copied = TechnologyMaterialRequirement(
            id=uuid.uuid4(),
            code=item.code,
            selector_kind=item.selector_kind,
            material_role_code=item.material_role_code,
            canonical_material_id=item.canonical_material_id,
            material_category_id=item.material_category_id,
            material_type_id=item.material_type_id,
            technical_constraints=deepcopy(item.technical_constraints),
            notes=item.notes,
        )
        revised.requirements.append(copied)
        requirements[item.id] = copied

    for item in technology.layers:
        source_requirement_id = (
            item.material_requirement.id if item.material_requirement else item.material_requirement_id
        )
        revised.layers.append(
            TechnologyLayer(
                id=uuid.uuid4(),
                position=item.position,
                functional_role=item.functional_role,
                material_requirement=requirements.get(source_requirement_id),
                thickness_expression=item.thickness_expression,
                is_mandatory=item.is_mandatory,
                notes=item.notes,
                restrictions=deepcopy(item.restrictions),
            )
        )

    for item in technology.nodes:
        revised.nodes.append(
            TechnologyNode(
                id=uuid.uuid4(),
                code=item.code,
                node_type=item.node_type,
                name=item.name,
                description=item.description,
                conditions=deepcopy(item.conditions),
            )
        )

    for item in technology.work_steps:
        revised.work_steps.append(
            TechnologyWorkStep(
                id=uuid.uuid4(),
                position=item.position,
                work_code=item.work_code,
                applicability_expression=item.applicability_expression,
                dependency_step_codes=deepcopy(item.dependency_step_codes),
                instructions=item.instructions,
            )
        )

    for item in technology.evidence_references:
        revised.evidence_references.append(
            TechnologyEvidenceReference(
                id=uuid.uuid4(),
                document_id=item.document_id,
                knowledge_resource_id=item.knowledge_resource_id,
                target_kind=item.target_kind,
                target_reference=item.target_reference,
                interpretation=item.interpretation,
            )
        )
    return revised


async def persist_technology_draft(
    db: AsyncSession,
    technology: Technology,
) -> Technology:
    if technology.status != TechnologyLifecycle.DRAFT.value:
        raise Module2TechnologyError("only DRAFT technology may enter through draft persistence")
    db.add(technology)
    await db.flush()
    return technology


async def read_technology(
    db: AsyncSession,
    technology_id: uuid.UUID,
) -> Technology | None:
    result = await db.execute(
        select(Technology)
        .where(Technology.id == technology_id)
        .options(
            selectinload(Technology.requirements),
            selectinload(Technology.layers),
            selectinload(Technology.nodes),
            selectinload(Technology.work_steps),
            selectinload(Technology.evidence_references),
            selectinload(Technology.consumption_norms),
            selectinload(Technology.compatibility_rules),
            selectinload(Technology.knowledge_rules),
        )
    )
    return result.scalar_one_or_none()


async def list_technologies(
    db: AsyncSession,
    *,
    status: TechnologyLifecycle | None = None,
) -> tuple[Technology, ...]:
    statement = select(Technology).order_by(
        Technology.technology_code,
        Technology.revision.desc(),
    )
    if status is not None:
        statement = statement.where(Technology.status == status.value)
    result = await db.execute(statement)
    return tuple(result.scalars().all())


def require_module2_access(role_code: str, required: AccessLevel) -> None:
    actual = _module2_access_level(role_code)
    if _ACCESS_RANK[actual] < _ACCESS_RANK[required]:
        raise Module2TechnologyPermissionError(
            f"{role_code} requires {required.value} access to {MODULE2_OWNER_CODE}"
        )


def _module2_access_level(role_code: str) -> AccessLevel:
    raw_role_code = str(role_code).upper()
    normalized = LEGACY_ROLE_ALIASES.get(raw_role_code, raw_role_code)
    levels = [
        AccessLevel(rule.accessLevel)
        for rule in STARTER_ROLE_MODULE_ACCESS
        if rule.roleCode == normalized and rule.moduleCode == MODULE2_OWNER_CODE
    ]
    return max(levels, key=_ACCESS_RANK.get, default=AccessLevel.NO_ACCESS)


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if value))
