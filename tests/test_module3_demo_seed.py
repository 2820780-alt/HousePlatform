import json

import pytest

from app.cli import module3_demo_seed as module3_demo_seed_cli
from app.models.enums import UserStatus
from app.services.module3_demo_seed import (
    MODULE3_DEMO_METADATA_KEY,
    MODULE3_DEMO_SEED_CODE,
    Module3DemoSeedResult,
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
    templates = {item.userTypeCode: item for item in plan.accessTemplates}

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
    assert {"CUSTOMER", "SUPPLIER", "CONSTRUCTION_COMPANY", "SPECIALIST", "SYSTEM_USER"} == set(templates)
    assert "MODULE_05_ESTIMATE_ENGINE" in {item.moduleCode for item in templates["CUSTOMER"].moduleAccess}
    assert "MODULE_01_MATERIAL_HUB" in {item.moduleCode for item in templates["SUPPLIER"].moduleAccess}
    assert "MODULE_03_USERS_ROLES" in templates["SUPPLIER"].deniedModuleCodes
    assert "price-dynamics" in {item.widgetCode for item in templates["CONSTRUCTION_COMPANY"].widgetAccess}
    assert "MODULE_03_USERS_ROLES" in {item.moduleCode for item in templates["SYSTEM_USER"].moduleAccess}

    overrides = {item.scenarioCode: item for item in plan.accessOverrides}
    assert overrides["MODULE3_USER_INDIVIDUAL_MODULE_ALLOW"].moduleCode == "MODULE_01_MATERIAL_HUB"
    assert overrides["MODULE3_USER_INDIVIDUAL_WIDGET_ALLOW"].widgetCode == "materials-kpi"
    assert overrides["MODULE3_USER_INDIVIDUAL_WIDGET_DENY"].accessLevel == "NO_ACCESS"
    assert overrides["MODULE3_BLOCKED_USER_ACCESS_DISABLED"].sourceLabel == "Системное правило"

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
    override_keys = [(item.user_email, item.moduleCode, item.widgetCode, item.scenarioCode) for item in plan.accessOverrides]

    assert len(emails) == len(set(emails))
    assert len(slugs) == len(set(slugs))
    assert len(membership_keys) == len(set(membership_keys))
    assert len(override_keys) == len(set(override_keys))
    assert all(email.endswith("@atom.local") for email in emails)
    assert all(slug.startswith("demo-") for slug in slugs)
    assert build_module3_demo_seed_plan("development").to_dict() == plan.to_dict()


def test_module3_demo_seed_cli_declares_local_control_commands():
    parser = module3_demo_seed_cli.build_parser()

    create_args = parser.parse_args(["create", "--environment", "development", "--enable"])
    reset_args = parser.parse_args(["reset", "--environment", "development", "--enable", "--dry-run"])
    recreate_args = parser.parse_args(["recreate", "--environment", "demo", "--enable"])

    assert create_args.command == "create"
    assert create_args.enable is True
    assert reset_args.command == "reset"
    assert reset_args.dry_run is True
    assert recreate_args.command == "recreate"
    assert recreate_args.environment == "demo"


def test_module3_demo_seed_cli_rejects_dry_run_for_create():
    with pytest.raises(SystemExit):
        module3_demo_seed_cli.main(["create", "--environment", "development", "--enable", "--dry-run"])


def test_module3_demo_seed_cli_plan_runs_without_server(capsys):
    exit_code = module3_demo_seed_cli.main(["plan", "--environment", "development", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["seedCode"] == MODULE3_DEMO_SEED_CODE
    assert payload["metadata"]["isDemo"] is True
    assert payload["users"]
    assert payload["companies"]


def test_module3_demo_seed_result_reports_reset_counts():
    result = Module3DemoSeedResult(
        seedCode=MODULE3_DEMO_SEED_CODE,
        environment="development",
        usersDeleted=2,
        companiesDeleted=1,
        membershipsDeleted=3,
        rolesDeleted=4,
        preferencesDeleted=2,
        moduleAccessDeleted=1,
        functionAccessDeleted=1,
        moduleAccessUpserted=2,
        functionAccessUpserted=3,
        dryRun=True,
    )

    assert result.to_dict()["dryRun"] is True
    assert result.to_dict()["usersDeleted"] == 2
    assert result.to_dict()["companiesDeleted"] == 1
    assert result.to_dict()["moduleAccessUpserted"] == 2
    assert result.to_dict()["functionAccessUpserted"] == 3
