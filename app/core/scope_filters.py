from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence

from sqlalchemy import false, or_, true

from app.core.access_scopes import AccessScope
from app.core.permission_guard import require_permission


OWN_FIELD_CONTEXT_KEYS: dict[str, tuple[str, ...]] = {
    "owner_user_id": ("userId",),
    "owner_id": ("userId",),
    "user_id": ("userId",),
    "created_by": ("userId",),
    "created_by_user_id": ("userId",),
    "uploaded_by_user_id": ("userId",),
    "workspace_id": ("workspaceIds",),
    "supplier_id": ("supplierIds",),
    "contractor_id": ("contractorIds",),
    "customer_id": ("customerIds",),
    "project_id": ("projectIds",),
    "organization_id": ("organizationIds",),
}

RELEVANT_FIELD_CONTEXT_KEYS: dict[str, tuple[str, ...]] = {
    "workspace_id": ("relevantWorkspaceIds", "workspaceIds"),
    "supplier_id": ("relevantSupplierIds", "supplierIds"),
    "contractor_id": ("relevantContractorIds", "contractorIds"),
    "customer_id": ("relevantCustomerIds", "customerIds"),
    "project_id": ("relevantProjectIds", "projectIds"),
    "organization_id": ("relevantOrganizationIds", "organizationIds"),
}

LIMITED_DEFAULT_FIELDS: tuple[str, ...] = ("id", "title", "name", "status", "updated_at")


@dataclass(frozen=True)
class OwnerScopeContext:
    userId: str | None = None
    workspaceIds: tuple[str, ...] = ()
    supplierIds: tuple[str, ...] = ()
    contractorIds: tuple[str, ...] = ()
    customerIds: tuple[str, ...] = ()
    projectIds: tuple[str, ...] = ()
    organizationIds: tuple[str, ...] = ()
    relevantWorkspaceIds: tuple[str, ...] = ()
    relevantSupplierIds: tuple[str, ...] = ()
    relevantContractorIds: tuple[str, ...] = ()
    relevantCustomerIds: tuple[str, ...] = ()
    relevantProjectIds: tuple[str, ...] = ()
    relevantOrganizationIds: tuple[str, ...] = ()
    limitedFields: tuple[str, ...] = ()


def get_owner_scope_context(user: Any | None) -> OwnerScopeContext:
    if user is None:
        return OwnerScopeContext()

    user_id = _first_value(user, ("userId", "user_id", "id"))
    workspace_ids = _values_for(user, "workspaceIds", "workspace_id", "workspaceId")
    supplier_ids = _values_for(user, "supplierIds", "supplier_id", "supplierId")
    contractor_ids = _values_for(user, "contractorIds", "contractor_id", "contractorId")
    customer_ids = _values_for(user, "customerIds", "customer_id", "customerId")
    project_ids = _values_for(user, "projectIds", "project_id", "projectId")
    organization_ids = _values_for(user, "organizationIds", "organization_id", "organizationId")

    workspace_ids += _related_values(user, "workspace_members", "workspace_id")
    supplier_ids += _related_values(user, "supplier_accounts", "supplier_id")

    return OwnerScopeContext(
        userId=_string_or_none(user_id),
        workspaceIds=_unique_strings(workspace_ids),
        supplierIds=_unique_strings(supplier_ids),
        contractorIds=_unique_strings(contractor_ids),
        customerIds=_unique_strings(customer_ids),
        projectIds=_unique_strings(project_ids),
        organizationIds=_unique_strings(organization_ids),
        relevantWorkspaceIds=_unique_strings(_values_for(user, "relevantWorkspaceIds", "relevant_workspace_ids")),
        relevantSupplierIds=_unique_strings(_values_for(user, "relevantSupplierIds", "relevant_supplier_ids")),
        relevantContractorIds=_unique_strings(_values_for(user, "relevantContractorIds", "relevant_contractor_ids")),
        relevantCustomerIds=_unique_strings(_values_for(user, "relevantCustomerIds", "relevant_customer_ids")),
        relevantProjectIds=_unique_strings(_values_for(user, "relevantProjectIds", "relevant_project_ids")),
        relevantOrganizationIds=_unique_strings(_values_for(user, "relevantOrganizationIds", "relevant_organization_ids")),
        limitedFields=_unique_strings(_values_for(user, "limitedFields", "limited_fields")),
    )


def build_scope_condition(
    model: Any,
    user: Any | None,
    scope: str = AccessScope.GLOBAL,
    *,
    relevant_rules: Mapping[str, str | Sequence[str]] | None = None,
):
    scope_value = _enum_value(scope)
    if scope_value == AccessScope.GLOBAL:
        return true()
    if scope_value == AccessScope.NONE:
        return false()
    if scope_value == AccessScope.OWN:
        return _condition_for_field_context_map(model, get_owner_scope_context(user), OWN_FIELD_CONTEXT_KEYS)
    if scope_value == AccessScope.RELEVANT:
        if relevant_rules:
            return _condition_for_relevant_rules(model, get_owner_scope_context(user), relevant_rules)
        return _condition_for_field_context_map(model, get_owner_scope_context(user), RELEVANT_FIELD_CONTEXT_KEYS)
    if scope_value == AccessScope.LIMITED:
        return true()
    return false()


def apply_scope_filter(
    statement: Any,
    model: Any,
    user: Any | None,
    scope: str = AccessScope.GLOBAL,
    *,
    relevant_rules: Mapping[str, str | Sequence[str]] | None = None,
) -> Any:
    condition = build_scope_condition(model, user, scope, relevant_rules=relevant_rules)
    return statement.where(condition)


def apply_permission_scope_filter(
    statement: Any,
    model: Any,
    user: Any | None,
    moduleCode: str,
    actionCode: str,
    scope: str = AccessScope.GLOBAL,
    *,
    relevant_rules: Mapping[str, str | Sequence[str]] | None = None,
) -> Any:
    require_permission(user, moduleCode, actionCode, scope)
    return apply_scope_filter(statement, model, user, scope, relevant_rules=relevant_rules)


def resource_matches_scope(
    resource: Any,
    user: Any | None,
    scope: str = AccessScope.GLOBAL,
    *,
    relevant_rules: Mapping[str, str | Sequence[str]] | None = None,
) -> bool:
    scope_value = _enum_value(scope)
    if scope_value == AccessScope.GLOBAL:
        return True
    if scope_value == AccessScope.NONE:
        return False
    if scope_value == AccessScope.OWN:
        return _resource_matches_field_context_map(resource, get_owner_scope_context(user), OWN_FIELD_CONTEXT_KEYS)
    if scope_value == AccessScope.RELEVANT:
        context = get_owner_scope_context(user)
        if relevant_rules:
            return _resource_matches_relevant_rules(resource, context, relevant_rules)
        return _resource_matches_field_context_map(resource, context, RELEVANT_FIELD_CONTEXT_KEYS)
    if scope_value == AccessScope.LIMITED:
        return True
    return False


def filter_resources_by_scope(
    resources: Iterable[Any],
    user: Any | None,
    scope: str = AccessScope.GLOBAL,
    *,
    relevant_rules: Mapping[str, str | Sequence[str]] | None = None,
) -> list[Any]:
    return [
        resource
        for resource in resources
        if resource_matches_scope(resource, user, scope, relevant_rules=relevant_rules)
    ]


def project_limited_fields(
    data: Mapping[str, Any] | Any,
    allowed_fields: Sequence[str] | None = None,
    *,
    default_fields: Sequence[str] = LIMITED_DEFAULT_FIELDS,
) -> dict[str, Any]:
    fields = tuple(allowed_fields or ())
    if not fields:
        fields = tuple(field for field in default_fields if _get_value(data, field) is not None)
    return {field: _get_value(data, field) for field in fields if _get_value(data, field) is not None}


def applyScopeFilter(*args: Any, **kwargs: Any) -> Any:
    return apply_scope_filter(*args, **kwargs)


def applyPermissionScopeFilter(*args: Any, **kwargs: Any) -> Any:
    return apply_permission_scope_filter(*args, **kwargs)


def _condition_for_field_context_map(
    model: Any,
    context: OwnerScopeContext,
    field_context_map: Mapping[str, tuple[str, ...]],
):
    conditions = []
    for field_name, context_fields in field_context_map.items():
        column = getattr(model, field_name, None)
        values = _context_values(context, context_fields)
        if column is not None and values:
            conditions.append(column.in_(values))
    return or_(*conditions) if conditions else false()


def _condition_for_relevant_rules(
    model: Any,
    context: OwnerScopeContext,
    relevant_rules: Mapping[str, str | Sequence[str]],
):
    conditions = []
    for field_name, context_field_names in relevant_rules.items():
        column = getattr(model, field_name, None)
        values = _context_values(context, _as_tuple(context_field_names))
        if column is not None and values:
            conditions.append(column.in_(values))
    return or_(*conditions) if conditions else false()


def _resource_matches_field_context_map(
    resource: Any,
    context: OwnerScopeContext,
    field_context_map: Mapping[str, tuple[str, ...]],
) -> bool:
    checked_any_field = False
    for field_name, context_fields in field_context_map.items():
        resource_value = _get_value(resource, field_name)
        values = _context_values(context, context_fields)
        if resource_value is not None:
            checked_any_field = True
        if resource_value is not None and str(resource_value) in values:
            return True
    return False if checked_any_field else False


def _resource_matches_relevant_rules(
    resource: Any,
    context: OwnerScopeContext,
    relevant_rules: Mapping[str, str | Sequence[str]],
) -> bool:
    for field_name, context_field_names in relevant_rules.items():
        resource_value = _get_value(resource, field_name)
        values = _context_values(context, _as_tuple(context_field_names))
        if resource_value is not None and str(resource_value) in values:
            return True
    return False


def _context_values(context: OwnerScopeContext, field_names: Sequence[str]) -> tuple[str, ...]:
    values: list[str] = []
    for field_name in field_names:
        value = getattr(context, field_name, None)
        if isinstance(value, tuple):
            values.extend(value)
        elif value is not None:
            values.append(str(value))
    return _unique_strings(values)


def _values_for(source: Any, *field_names: str) -> list[Any]:
    values: list[Any] = []
    for field_name in field_names:
        value = _get_value(source, field_name)
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            values.extend(value)
        else:
            values.append(value)
    return values


def _related_values(source: Any, relationship_name: str, field_name: str) -> list[Any]:
    values: list[Any] = []
    for item in _safe_iterable(_get_value(source, relationship_name)):
        value = _get_value(item, field_name)
        if value is not None:
            values.append(value)
    return values


def _first_value(source: Any, field_names: Sequence[str]) -> Any:
    for field_name in field_names:
        value = _get_value(source, field_name)
        if value is not None:
            return value
    return None


def _get_value(source: Any, field_name: str) -> Any:
    if source is None:
        return None
    if isinstance(source, Mapping):
        return source.get(field_name)
    return getattr(source, field_name, None)


def _safe_iterable(value: Any) -> list[Any]:
    if not value:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return []


def _unique_strings(values: Iterable[Any]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value is None:
            continue
        string_value = str(value)
        if string_value and string_value not in seen:
            result.append(string_value)
            seen.add(string_value)
    return tuple(result)


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _as_tuple(value: str | Sequence[str]) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    return tuple(value)


def _enum_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)
