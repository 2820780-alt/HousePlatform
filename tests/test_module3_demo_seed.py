import pytest

from app.models.enums import UserStatus
from app.services.module3_demo_seed import (
    MODULE3_DEMO_METADATA_KEY,
    MODULE3_DEMO_SEED_CODE,
    Module3DemoSeedGuardError,
    build_module3_demo_seed_plan,
    module3_demo_seed_is_allowed,
    require_module3_demo_seed_allowed,
)


def test_module3_demo_seed_is_guarded_by_environment_and_flag():
    assert module3_demo_seed_is_allowed(app_env="development", node_env="", enabled=True)
    assert module3_demo_seed_is_allowed(app_env="demo", node_env="", enabled=True)
    assert module3_demo_seed_is_allowed(app_env="staging", node_env="", enabled=True)
    assert not module3_demo_seed_is_allowed(app_env="development", node_env="", enabled=False)
    assert not module3_demo_seed_is_allowed(app_env="production", node_env="", enabled=True)
    assert not module3_demo_seed_is_allowed(app_env="development", node_env="production", enabled=True)

    with pytest.raises(Module3DemoSeedGuardError):
        require_module3_demo_seed_allowed(app_env="production", node_env="", enabled=True)


def test_module3_demo_seed_plan_contains_required_users_companies_and_metadata():
    plan = build_module3_demo_seed_plan("development")
    users = {item.code: item for item in plan.users}
    companies = {item.code: item for item in plan.companies}

    assert plan.seedCode == MODULE3_DEMO_SEED_CODE
    assert plan.metadata == {
        "isDemo": True,
        "isSeed": True,
        "demoScenarioCode": MODULE3_DEMO_SEED_CODE,
        "environment": "development",
        "sourceModuleCode": "MODULE_03_USERS_ROLES",
    }
    assert MODULE3_DEMO_METADATA_KEY == "module3_demo_seed_metadata"

    required_user_codes = {
        "customer_active",
        "customer_blocked",
        "supplier_active",
        "supplier_moderation",
        "supplier_blocked",
        "construction_company_active",
        "construction_company_moderation",
        "construction_company_blocked",
        "independent_engineer_active",
        "independent_engineer_limited",
        "super_admin",
        "moderator",
        "support_admin",
        "platform_admin",
    }
    assert required_user_codes.issubset(users)
    assert users["customer_blocked"].status == UserStatus.BLOCKED
    assert users["supplier_moderation"].status == UserStatus.INACTIVE
    assert users["independent_engineer_limited"].accessProfile == "limited"
    assert users["super_admin"].isSystemUser is True
    assert users["moderator"].isSystemUser is True
    assert users["support_admin"].isSystemUser is True

    required_company_codes = {
        "spug_active",
        "kuban_materials_active",
        "betonpostavka_moderation",
        "monolit_blocked",
    }
    assert required_company_codes == set(companies)
    assert companies["spug_active"].name == "ООО «СтройПроект Юг»"
    assert companies["kuban_materials_active"].workspace_type == "SUPPLIER"
    assert companies["betonpostavka_moderation"].status == "PENDING_REVIEW"
    assert companies["monolit_blocked"].status == "BLOCKED"

    employees = [item for item in plan.employees if item.company_slug == "demo-stroyproekt-yug"]
    assert [item.role_key for item in employees] == [
        "COMPANY_LEAD",
        "ENGINEER",
        "BUYER",
        "PROJECT_MANAGER",
        "ESTIMATOR",
    ]

    for collection in (plan.users, plan.companies, plan.employees):
        for item in collection:
            metadata = item.metadata.to_dict()
            assert metadata["isDemo"] is True
            assert metadata["isSeed"] is True
            assert metadata["environment"] == "development"
            assert metadata["sourceModuleCode"] == "MODULE_03_USERS_ROLES"


def test_module3_demo_seed_plan_is_idempotent_by_natural_keys():
    plan = build_module3_demo_seed_plan("development")
    emails = [item.email for item in plan.users]
    slugs = [item.slug for item in plan.companies]
    membership_keys = [(item.user_email, item.company_slug) for item in plan.employees]

    assert len(emails) == len(set(emails))
    assert len(slugs) == len(set(slugs))
    assert len(membership_keys) == len(set(membership_keys))
    assert all(email.endswith("@atom.local") for email in emails)
    assert all(slug.startswith("demo-") for slug in slugs)
    assert build_module3_demo_seed_plan("development").to_dict() == plan.to_dict()
