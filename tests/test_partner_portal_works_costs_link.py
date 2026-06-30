import pytest

from app.models import WorksCostsCabinetLink
from app.models.partner_portal import MODULE_08_PARTNER_PORTAL
from app.services.partner_portal_works_costs_link import (
    MODULE_04_WORKS_COSTS,
    build_works_costs_cabinet_link,
)


def test_works_costs_cabinet_link_model_connects_module4_references_to_module8_cabinet():
    columns = set(WorksCostsCabinetLink.__table__.columns.keys())

    assert WorksCostsCabinetLink.__tablename__ == "module08_works_costs_cabinet_links"
    assert WorksCostsCabinetLink.__table__.columns["module_code"].default.arg == MODULE_08_PARTNER_PORTAL
    assert WorksCostsCabinetLink.__table__.columns["source_module_code"].default.arg == MODULE_04_WORKS_COSTS
    assert WorksCostsCabinetLink.__table__.columns["target_module_code"].default.arg == MODULE_08_PARTNER_PORTAL
    for column in (
        "cabinet_id",
        "work_rate_source_id",
        "contractor_profile_ref",
        "work_producer_ref",
        "link_status",
        "source_module_code",
        "target_module_code",
    ):
        assert column in columns


def test_build_works_costs_cabinet_link_keeps_work_rates_owned_by_module4():
    link = build_works_costs_cabinet_link(
        {
            "cabinetId": "cabinet-company-1",
            "workRateSourceId": "work-rate-source-1",
            "contractorProfileRef": "contractor-profile-1",
            "workProducerRef": "work-producer-1",
            "linkStatus": "active",
        }
    ).to_dict()

    assert link["cabinetId"] == "cabinet-company-1"
    assert link["workRateSourceId"] == "work-rate-source-1"
    assert link["contractorProfileRef"] == "contractor-profile-1"
    assert link["workProducerRef"] == "work-producer-1"
    assert link["linkStatus"] == "ACTIVE"
    assert link["sourceModuleCode"] == MODULE_04_WORKS_COSTS
    assert link["targetModuleCode"] == MODULE_08_PARTNER_PORTAL
    for forbidden_key in (
        "workRateId",
        "approvedRateId",
        "rateObservationId",
        "workCatalogId",
        "WorkRate",
    ):
        assert forbidden_key not in link


def test_works_costs_cabinet_link_requires_module4_reference():
    with pytest.raises(ValueError):
        build_works_costs_cabinet_link({"cabinetId": "cabinet-company-1"})
