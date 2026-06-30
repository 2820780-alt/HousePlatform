import pytest

from app.models import SupplierCabinetLink
from app.models.partner_portal import MODULE_08_PARTNER_PORTAL
from app.services.partner_portal_supplier_link import (
    MODULE_01_MATERIAL_HUB,
    build_supplier_cabinet_link,
)


def test_supplier_cabinet_link_model_connects_material_hub_supplier_to_module8_cabinet():
    columns = set(SupplierCabinetLink.__table__.columns.keys())

    assert SupplierCabinetLink.__tablename__ == "module08_supplier_cabinet_links"
    assert SupplierCabinetLink.__table__.columns["module_code"].default.arg == MODULE_08_PARTNER_PORTAL
    assert SupplierCabinetLink.__table__.columns["source_module_code"].default.arg == MODULE_01_MATERIAL_HUB
    assert SupplierCabinetLink.__table__.columns["target_module_code"].default.arg == MODULE_08_PARTNER_PORTAL
    for column in (
        "supplier_id",
        "cabinet_id",
        "link_status",
        "verification_status",
        "source_module_code",
        "target_module_code",
    ):
        assert column in columns


def test_build_supplier_cabinet_link_keeps_supplier_data_owned_by_module1():
    link = build_supplier_cabinet_link(
        {
            "supplierId": "supplier-1",
            "cabinetId": "cabinet-supplier-1",
            "linkStatus": "active",
            "verificationStatus": "verified",
        }
    ).to_dict()

    assert link["supplierId"] == "supplier-1"
    assert link["cabinetId"] == "cabinet-supplier-1"
    assert link["linkStatus"] == "ACTIVE"
    assert link["verificationStatus"] == "VERIFIED"
    assert link["sourceModuleCode"] == MODULE_01_MATERIAL_HUB
    assert link["targetModuleCode"] == MODULE_08_PARTNER_PORTAL
    for forbidden_key in (
        "materialId",
        "canonicalMaterialId",
        "priceId",
        "priceListId",
        "supplierPrice",
        "Material",
    ):
        assert forbidden_key not in link


def test_supplier_cabinet_link_requires_supplier_id():
    with pytest.raises(ValueError):
        build_supplier_cabinet_link({"cabinetId": "cabinet-supplier-1"})
