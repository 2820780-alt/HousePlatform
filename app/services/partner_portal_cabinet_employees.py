from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.models.partner_portal import MODULE_08_PARTNER_PORTAL
from app.services.partner_portal_cabinet_types import (
    CONSTRUCTION_COMPANY,
    CUSTOMER,
    MATERIAL_SUPPLIER,
    SPECIALIST,
    normalize_cabinet_type,
)


EMPLOYEE_STATUS_ACTIVE = "ACTIVE"
MEMBERSHIP_STATUS_ACTIVE = "ACTIVE"

BUSINESS_ROLE_CATALOG: tuple[dict[str, Any], ...] = (
    {"roleCode": "CUSTOMER_OWNER", "cabinetType": CUSTOMER, "title": "Владелец объекта", "isDefault": True},
    {"roleCode": "SUPPLIER_OWNER", "cabinetType": MATERIAL_SUPPLIER, "title": "Директор / владелец", "isDefault": True},
    {"roleCode": "SUPPLIER_ADMIN", "cabinetType": MATERIAL_SUPPLIER, "title": "Администратор", "isDefault": False},
    {"roleCode": "SALES_MANAGER", "cabinetType": MATERIAL_SUPPLIER, "title": "Менеджер продаж", "isDefault": False},
    {"roleCode": "COMPANY_OWNER", "cabinetType": CONSTRUCTION_COMPANY, "title": "Директор / владелец", "isDefault": True},
    {"roleCode": "COMPANY_ADMIN", "cabinetType": CONSTRUCTION_COMPANY, "title": "Администратор", "isDefault": False},
    {"roleCode": "FOREMAN", "cabinetType": CONSTRUCTION_COMPANY, "title": "Прораб", "isDefault": False},
    {"roleCode": "PROCUREMENT_ENGINEER", "cabinetType": CONSTRUCTION_COMPANY, "title": "Инженер снабжения", "isDefault": False},
    {"roleCode": "ESTIMATOR", "cabinetType": CONSTRUCTION_COMPANY, "title": "Сметчик", "isDefault": False},
    {"roleCode": "PROJECT_SALES_MANAGER", "cabinetType": CONSTRUCTION_COMPANY, "title": "Менеджер проекта / продаж", "isDefault": False},
    {"roleCode": "PTO_ENGINEER", "cabinetType": CONSTRUCTION_COMPANY, "title": "Инженер ПТО", "isDefault": False},
    {"roleCode": "STOREKEEPER", "cabinetType": CONSTRUCTION_COMPANY, "title": "Кладовщик", "isDefault": False},
    {"roleCode": "FOREMAN", "cabinetType": SPECIALIST, "title": "Прораб", "isDefault": False},
    {"roleCode": "PROCUREMENT_ENGINEER", "cabinetType": SPECIALIST, "title": "Инженер снабжения", "isDefault": False},
    {"roleCode": "ESTIMATOR", "cabinetType": SPECIALIST, "title": "Сметчик", "isDefault": False},
    {"roleCode": "PTO_ENGINEER", "cabinetType": SPECIALIST, "title": "Инженер ПТО", "isDefault": False},
    {"roleCode": "DESIGNER", "cabinetType": SPECIALIST, "title": "Проектировщик", "isDefault": False},
)


@dataclass(frozen=True)
class CabinetEmployeeRoleDTO:
    roleCode: str
    cabinetType: str
    title: str
    isDefault: bool = False
    sourceModuleCode: str = MODULE_08_PARTNER_PORTAL
    permissionSourceModuleCode: str = "MODULE_03_USERS_ROLES"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CabinetEmployeeDTO:
    employeeId: str | None = None
    cabinetId: str | None = None
    userId: str | None = None
    displayName: str | None = None
    email: str | None = None
    phone: str | None = None
    positionTitle: str | None = None
    businessRoleCode: str | None = None
    status: str = EMPLOYEE_STATUS_ACTIVE
    sourceModuleCode: str = MODULE_08_PARTNER_PORTAL

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CabinetMembershipDTO:
    membershipId: str | None = None
    cabinetId: str | None = None
    employeeId: str | None = None
    userId: str | None = None
    businessRoleCode: str | None = None
    membershipStatus: str = MEMBERSHIP_STATUS_ACTIVE
    isOwner: bool = False
    joinedAt: str | None = field(default_factory=lambda: datetime.now(UTC).isoformat())
    sourceModuleCode: str = MODULE_08_PARTNER_PORTAL
    permissionSourceModuleCode: str = "MODULE_03_USERS_ROLES"
    boundaryNote: str = (
        "Module 08 stores cabinet business role and membership context only. "
        "Permissions, access level and scope stay in Module 03."
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def get_cabinet_employee_roles(cabinet_type: str | None = None) -> list[CabinetEmployeeRoleDTO]:
    normalized_type = normalize_cabinet_type(cabinet_type)
    roles: list[CabinetEmployeeRoleDTO] = []
    for item in BUSINESS_ROLE_CATALOG:
        if normalized_type and item["cabinetType"] != normalized_type:
            continue
        roles.append(
            CabinetEmployeeRoleDTO(
                roleCode=str(item["roleCode"]),
                cabinetType=str(item["cabinetType"]),
                title=str(item["title"]),
                isDefault=bool(item["isDefault"]),
            )
        )
    return roles


def build_cabinet_membership(
    employee: Any,
    *,
    cabinet_id: str | None = None,
    business_role_code: str | None = None,
    is_owner: bool = False,
) -> CabinetMembershipDTO:
    employee_data = _dict_value(employee)
    return CabinetMembershipDTO(
        cabinetId=cabinet_id or _string_or_none(employee_data.get("cabinetId")),
        employeeId=_string_or_none(employee_data.get("employeeId") or employee_data.get("id")),
        userId=_string_or_none(employee_data.get("userId")),
        businessRoleCode=business_role_code or _string_or_none(employee_data.get("businessRoleCode")),
        isOwner=is_owner,
    )


def build_cabinet_employee(
    employee: Any,
    *,
    cabinet_id: str | None = None,
    business_role_code: str | None = None,
) -> CabinetEmployeeDTO:
    data = _dict_value(employee)
    return CabinetEmployeeDTO(
        employeeId=_string_or_none(data.get("employeeId") or data.get("id")),
        cabinetId=cabinet_id or _string_or_none(data.get("cabinetId")),
        userId=_string_or_none(data.get("userId")),
        displayName=_string_or_none(data.get("displayName") or data.get("name")),
        email=_string_or_none(data.get("email")),
        phone=_string_or_none(data.get("phone")),
        positionTitle=_string_or_none(data.get("positionTitle")),
        businessRoleCode=business_role_code or _string_or_none(data.get("businessRoleCode")),
    )


def getCabinetEmployeeRoles(cabinetType: str | None = None) -> list[CabinetEmployeeRoleDTO]:
    return get_cabinet_employee_roles(cabinetType)


def buildCabinetMembership(
    employee: Any,
    *,
    cabinet_id: str | None = None,
    business_role_code: str | None = None,
    is_owner: bool = False,
) -> CabinetMembershipDTO:
    return build_cabinet_membership(
        employee,
        cabinet_id=cabinet_id,
        business_role_code=business_role_code,
        is_owner=is_owner,
    )


def buildCabinetEmployee(
    employee: Any,
    *,
    cabinet_id: str | None = None,
    business_role_code: str | None = None,
) -> CabinetEmployeeDTO:
    return build_cabinet_employee(
        employee,
        cabinet_id=cabinet_id,
        business_role_code=business_role_code,
    )


def _dict_value(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return {}


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


__all__ = [
    "EMPLOYEE_STATUS_ACTIVE",
    "MEMBERSHIP_STATUS_ACTIVE",
    "BUSINESS_ROLE_CATALOG",
    "CabinetEmployeeRoleDTO",
    "CabinetEmployeeDTO",
    "CabinetMembershipDTO",
    "get_cabinet_employee_roles",
    "build_cabinet_membership",
    "build_cabinet_employee",
    "getCabinetEmployeeRoles",
    "buildCabinetMembership",
    "buildCabinetEmployee",
]
