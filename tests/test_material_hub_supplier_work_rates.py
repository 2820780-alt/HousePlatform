from app.api.v1.admin_suppliers import _supplier_model_payload
from app.schemas.material_hub_contracts import (
    AccountLinkStatus,
    AccountSyncStatus,
    SupplierContract,
    WorkRateObservation,
)


def test_supplier_future_fields_do_not_write_directly_to_supplier_orm():
    payload = {
        "name": "Поставщик Юг",
        "site": "https://example.test",
        "supplier_account_id": "00000000-0000-0000-0000-000000000001",
        "account_link_status": "LINKED",
        "delivery_zone_ids": ["00000000-0000-0000-0000-000000000002"],
        "bank_details": {"bik": "000000000"},
    }

    orm_payload = _supplier_model_payload(payload)

    assert orm_payload == {"name": "Поставщик Юг", "site": "https://example.test"}


def test_supplier_contract_prepares_module8_link_metadata_without_module8_entity():
    supplier = SupplierContract(
        name="Поставщик Юг",
        supplier_account_id="00000000-0000-0000-0000-000000000001",
        account_link_status=AccountLinkStatus.LINK_REQUESTED,
        sync_status=AccountSyncStatus.PENDING_REVIEW,
        delivery_zone_ids=["00000000-0000-0000-0000-000000000002"],
        pickup_available=True,
        delivery_available=True,
    )

    assert supplier.source_module_code == "MODULE_01_MATERIAL_HUB"
    assert supplier.supplier_account_id is not None
    assert supplier.account_link_status == AccountLinkStatus.LINK_REQUESTED
    assert supplier.sync_status == AccountSyncStatus.PENDING_REVIEW


def test_work_rate_observation_is_separate_from_material_price():
    observation = WorkRateObservation(
        work_name="Монтаж стропильной системы",
        raw_unit="м2",
        normalized_unit="м²",
        raw_price="1250.00",
        work_region_id="00000000-0000-0000-0000-000000000010",
        source_region_id="00000000-0000-0000-0000-000000000010",
        linked_material_ids=["00000000-0000-0000-0000-000000000020"],
        work_producer_account_id="00000000-0000-0000-0000-000000000030",
    )

    assert observation.source_module_code == "MODULE_01_MATERIAL_HUB"
    assert observation.target_module_code == "MODULE_04_WORKS_COSTS"
    assert observation.raw_price is not None
    assert observation.work_region_id is not None
    assert observation.linked_material_ids
    assert observation.account_link_status == AccountLinkStatus.NOT_LINKED
