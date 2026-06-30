from app.models import CabinetEmployee, CabinetEmployeeRole, CabinetMembership
from app.models.partner_portal import MODULE_08_PARTNER_PORTAL
from app.services.partner_portal_cabinet_employees import (
    build_cabinet_employee,
    build_cabinet_membership,
    get_cabinet_employee_roles,
)


def test_cabinet_employee_models_are_module8_entities():
    assert CabinetEmployee.__tablename__ == "module08_cabinet_employees"
    assert CabinetEmployeeRole.__tablename__ == "module08_cabinet_employee_roles"
    assert CabinetMembership.__tablename__ == "module08_cabinet_memberships"
    assert CabinetEmployee.__table__.columns["module_code"].default.arg == MODULE_08_PARTNER_PORTAL
    assert CabinetEmployeeRole.__table__.columns["module_code"].default.arg == MODULE_08_PARTNER_PORTAL
    assert CabinetMembership.__table__.columns["module_code"].default.arg == MODULE_08_PARTNER_PORTAL


def test_cabinet_employee_models_store_business_role_not_permissions():
    employee_columns = set(CabinetEmployee.__table__.columns.keys())
    role_columns = set(CabinetEmployeeRole.__table__.columns.keys())
    membership_columns = set(CabinetMembership.__table__.columns.keys())

    assert "business_role_code" in employee_columns
    assert "business_role_code" in membership_columns
    assert "role_code" in role_columns
    for forbidden in ("permission_code", "access_level", "access_scope", "scope"):
        assert forbidden not in employee_columns
        assert forbidden not in role_columns
        assert forbidden not in membership_columns


def test_get_cabinet_employee_roles_returns_business_roles_by_cabinet_type():
    roles = [role.to_dict() for role in get_cabinet_employee_roles("CONSTRUCTION_COMPANY")]
    role_codes = [role["roleCode"] for role in roles]

    assert "COMPANY_OWNER" in role_codes
    assert "FOREMAN" in role_codes
    assert "PROCUREMENT_ENGINEER" in role_codes
    assert all(role["cabinetType"] == "CONSTRUCTION_COMPANY" for role in roles)
    assert all(role["sourceModuleCode"] == MODULE_08_PARTNER_PORTAL for role in roles)
    assert all(role["permissionSourceModuleCode"] == "MODULE_03_USERS_ROLES" for role in roles)
    assert "accessLevel" not in roles[0]


def test_build_employee_and_membership_keep_module8_as_business_context_only():
    employee = build_cabinet_employee(
        {
            "employeeId": "employee-1",
            "userId": "user-1",
            "displayName": "Иван Прораб",
            "email": "foreman@example.test",
            "positionTitle": "Прораб",
        },
        cabinet_id="cabinet-company-1",
        business_role_code="FOREMAN",
    ).to_dict()
    membership = build_cabinet_membership(
        employee,
        cabinet_id="cabinet-company-1",
        business_role_code="FOREMAN",
        is_owner=False,
    ).to_dict()

    assert employee["businessRoleCode"] == "FOREMAN"
    assert employee["sourceModuleCode"] == MODULE_08_PARTNER_PORTAL
    assert membership["businessRoleCode"] == "FOREMAN"
    assert membership["permissionSourceModuleCode"] == "MODULE_03_USERS_ROLES"
    assert "Permission" not in employee
    assert "accessScope" not in membership
