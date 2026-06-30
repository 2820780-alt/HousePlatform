from app.services.partner_portal_active_cabinet_context import (
    COMPACT_SELECTOR,
    FULL_SELECTOR,
    getActiveCabinetContext,
    get_active_cabinet_context,
)


def test_active_cabinet_context_selects_active_cabinet_from_multiple_cabinets():
    context = get_active_cabinet_context(
        {
            "userId": "user-1",
            "activeRegionCode": "KRASNODAR_KRAI",
            "availableCabinets": [
                {
                    "cabinetId": "cabinet-customer",
                    "cabinetType": "CUSTOMER",
                    "title": "Кабинет заказчика",
                    "businessRole": "CUSTOMER",
                    "workspaceId": "workspace-customer",
                },
                {
                    "cabinetId": "cabinet-supplier",
                    "cabinetType": "MATERIAL_SUPPLIER",
                    "title": "Поставщик материалов",
                    "businessRole": "SUPPLIER",
                    "workspaceId": "workspace-supplier",
                },
            ],
        },
        access_context={
            "userId": "user-1",
            "workspaceId": "workspace-supplier",
            "activeRegionCode": "KRASNODAR_KRAI",
            "allowedModuleCodes": ["MODULE_01_MATERIAL_HUB", "MODULE_07_DIGITAL_HOUSE"],
            "allowedFeatureCodes": ["HOUSE_PROFILE"],
        },
        active_cabinet_id="cabinet-supplier",
    ).to_dict()

    assert context["sourceModuleCode"] == "MODULE_08_PARTNER_PORTAL"
    assert context["activeCabinetId"] == "cabinet-supplier"
    assert context["activeCabinetType"] == "MATERIAL_SUPPLIER"
    assert context["activeCabinetTitle"] == "Поставщик материалов"
    assert context["activeBusinessRole"] == "SUPPLIER"
    assert context["workspaceId"] == "workspace-supplier"
    assert context["cabinetSelectorMode"] == FULL_SELECTOR
    assert [item["isActive"] for item in context["availableCabinets"]] == [False, True]


def test_single_cabinet_uses_compact_selector_mode_not_main_selector():
    context = getActiveCabinetContext(
        {
            "userId": "supplier-user",
            "activeRegionCode": "KRASNODAR_KRAI",
            "workspaces": [
                {
                    "workspaceId": "workspace-supplier",
                    "workspaceTitle": "Бауснаб",
                    "workspaceType": "SUPPLIER",
                    "roleCode": "SUPPLIER",
                }
            ],
        }
    ).to_dict()

    assert context["activeCabinetId"] == "module8-preview:workspace-supplier:SUPPLIER"
    assert context["activeCabinetType"] == "MATERIAL_SUPPLIER"
    assert context["cabinetSelectorMode"] == COMPACT_SELECTOR
    assert len(context["availableCabinets"]) == 1


def test_active_cabinet_context_filters_objects_by_visibility_and_permissions():
    context = get_active_cabinet_context(
        {
            "userId": "customer-user",
            "workspaceId": "workspace-customer",
            "activeRegionCode": "KRASNODAR_KRAI",
            "availableCabinets": [
                {
                    "cabinetId": "cabinet-customer",
                    "cabinetType": "CUSTOMER",
                    "title": "Заказчик",
                    "businessRole": "CUSTOMER",
                    "workspaceId": "workspace-customer",
                    "isActive": True,
                }
            ],
            "availableObjects": [
                {
                    "objectId": "house-visible",
                    "title": "Дом 120 м2",
                    "visibilityScope": "WORKSPACE",
                    "workspaceId": "workspace-customer",
                    "requiredModuleCode": "MODULE_07_DIGITAL_HOUSE",
                    "requiredFeatureCode": "HOUSE_PROFILE",
                },
                {
                    "objectId": "house-wrong-workspace",
                    "title": "Чужой объект",
                    "visibilityScope": "WORKSPACE",
                    "workspaceId": "workspace-other",
                    "requiredModuleCode": "MODULE_07_DIGITAL_HOUSE",
                },
                {
                    "objectId": "house-no-module-access",
                    "title": "Нет доступа к модулю",
                    "visibilityScope": "PUBLIC",
                    "requiredModuleCode": "MODULE_09_PROCUREMENT",
                },
                {
                    "objectId": "house-no-feature-access",
                    "title": "Нет доступа к feature",
                    "visibilityScope": "PUBLIC",
                    "requiredModuleCode": "MODULE_07_DIGITAL_HOUSE",
                    "requiredFeatureCode": "HOUSE_STORAGE",
                },
                {
                    "objectId": "house-private",
                    "title": "Приватный объект",
                    "visibilityScope": "PRIVATE",
                    "ownerUserId": "other-user",
                },
            ],
        },
        access_context={
            "userId": "customer-user",
            "workspaceId": "workspace-customer",
            "activeRegionCode": "KRASNODAR_KRAI",
            "allowedModuleCodes": ["MODULE_07_DIGITAL_HOUSE"],
            "allowedFeatureCodes": ["HOUSE_PROFILE"],
        },
        active_object_id="house-visible",
    ).to_dict()

    assert context["activeObjectId"] == "house-visible"
    assert context["activeObjectTitle"] == "Дом 120 м2"
    assert context["objectSelectorMode"] == COMPACT_SELECTOR
    assert [item["activeObjectId"] for item in context["availableObjects"]] == ["house-visible"]


def test_active_cabinet_context_allows_selecting_between_multiple_visible_objects():
    context = get_active_cabinet_context(
        {
            "userId": "customer-user",
            "workspaceId": "workspace-customer",
            "activeRegionCode": "KRASNODAR_KRAI",
            "availableCabinets": [
                {
                    "cabinetId": "cabinet-customer",
                    "cabinetType": "CUSTOMER",
                    "title": "Заказчик",
                    "businessRole": "CUSTOMER",
                    "workspaceId": "workspace-customer",
                    "isActive": True,
                }
            ],
            "availableObjects": [
                {
                    "objectId": "house-1",
                    "title": "Дом",
                    "visibilityScope": "WORKSPACE",
                    "workspaceId": "workspace-customer",
                    "requiredModuleCode": "MODULE_07_DIGITAL_HOUSE",
                },
                {
                    "objectId": "flat-1",
                    "title": "Квартира",
                    "visibilityScope": "WORKSPACE",
                    "workspaceId": "workspace-customer",
                    "requiredModuleCode": "MODULE_07_DIGITAL_HOUSE",
                },
            ],
        },
        access_context={"allowedModuleCodes": ["MODULE_07_DIGITAL_HOUSE"]},
        active_object_id="flat-1",
    ).to_dict()

    assert context["activeObjectId"] == "flat-1"
    assert context["objectSelectorMode"] == FULL_SELECTOR
    assert [item["isActive"] for item in context["availableObjects"]] == [False, True]
