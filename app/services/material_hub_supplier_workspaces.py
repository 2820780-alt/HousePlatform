from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.material_document import MaterialDocument
from app.models.enums import SourceType
from app.models.source import Source
from app.models.supplier import Supplier
from app.models.supplier_branch import SupplierBranch
from app.models.supplier_price import SupplierPrice
from app.models.supplier_upload import SupplierUpload
from app.schemas.material_hub_contracts import (
    AccountLinkStatus,
    AccountSyncStatus,
    SupplierBranchContract,
    SupplierCard,
    SupplierContract,
)


async def load_supplier_cards(db: AsyncSession, *, limit: int = 6) -> list[SupplierCard]:
    result = await db.execute(select(Supplier).order_by(Supplier.updated_at.desc()).limit(limit))
    suppliers = list(result.scalars().all())
    cards: list[SupplierCard] = []
    for supplier in suppliers:
        cards.append(
            SupplierCard(
                supplier=_supplier_contract(supplier),
                branches=await _supplier_branches(db, supplier),
                material_count=await _count_supplier_materials(db, supplier),
                document_count=await _count_supplier_documents(db, supplier),
                source_count=await _count_supplier_sources(db, supplier),
                upload_count=await _count_supplier_uploads(db, supplier),
                parsing_error_count=await _count_supplier_parsing_errors(db, supplier),
            )
        )
    return cards


async def load_supplier_workspace_summary(db: AsyncSession) -> dict:
    return {
        "suppliers_total": await _count_model(db, Supplier),
        "branches_total": await _count_model(db, SupplierBranch),
        "uploads_total": await _count_model(db, SupplierUpload),
        "parsing_errors_total": await _sum_supplier_upload_errors(db),
        "future_module8_link": {
            "source_module_code": "MODULE_01_MATERIAL_HUB",
            "target_module_code": "MODULE_08_PARTNER_PORTAL",
            "fields": [
                "supplier_account_id",
                "account_link_status",
                "verified_account",
                "linked_at",
                "sync_status",
                "last_synced_at",
            ],
            "note": "Module 01 prepares link metadata only; Module 08 remains source of truth for cabinets.",
        },
        "archive_policy": "Suppliers and sources must be archived or blocked instead of deleted when linked data exists.",
    }


async def load_work_rates_workspace_summary(db: AsyncSession) -> dict:
    open_source_count = await _count_where(
        db,
        Source,
        Source.source_type.in_([SourceType.MANUFACTURER, SourceType.RETAIL, SourceType.SUPPLIER]),
    )
    return {
        "source_module_code": "MODULE_01_MATERIAL_HUB",
        "target_module_code": "MODULE_04_WORKS_COSTS",
        "observation_contract": "WorkRateObservation",
        "open_sources_available": open_source_count,
        "supported_inputs": [
            "open_source",
            "manual_moderator_entry",
            "file_source",
            "future_work_producer_cabinet",
            "platform_internal_source",
        ],
        "regional_fields": [
            "work_region_id",
            "work_city_id",
            "work_zone_id",
            "source_region_id",
            "region_status",
        ],
        "account_link_fields": [
            "work_producer_account_id",
            "account_link_status",
            "verified_account",
            "sync_status",
            "last_synced_at",
        ],
        "note": "Module 01 stores primary work-rate observations only; approved business logic remains future Module 04.",
    }


def _supplier_contract(supplier: Supplier) -> SupplierContract:
    return SupplierContract(
        id=supplier.id,
        name=supplier.name,
        inn=supplier.inn,
        site=supplier.site,
        email=supplier.email,
        phone=supplier.phone,
        address=supplier.address,
        contacts={
            "email": supplier.email,
            "phone": supplier.phone,
            "city": supplier.city,
            "region": supplier.region,
        },
        manager_contacts=[],
        bank_details={},
        profile={"description": supplier.description, "country": supplier.country},
        account_link_status=AccountLinkStatus.NOT_LINKED,
        verified_account=False,
        sync_status=AccountSyncStatus.NOT_SYNCED,
        pickup_available=None,
        delivery_available=None,
        status=supplier.status,
        created_at=supplier.created_at,
        updated_at=supplier.updated_at,
    )


async def _supplier_branches(db: AsyncSession, supplier: Supplier) -> list[SupplierBranchContract]:
    result = await db.execute(
        select(SupplierBranch)
        .where(SupplierBranch.supplier_id == supplier.id)
        .order_by(SupplierBranch.created_at.desc())
        .limit(10)
    )
    return [
        SupplierBranchContract(
            id=branch.id,
            supplier_id=branch.supplier_id,
            name=branch.name,
            address=branch.address,
            contacts=branch.contacts,
            manager_contacts=[],
            pickup_available=None,
            delivery_available=None,
            is_main=branch.is_main,
            created_at=branch.created_at,
        )
        for branch in result.scalars().all()
    ]


async def _count_model(db: AsyncSession, model) -> int:
    result = await db.execute(select(func.count(model.id)))
    return result.scalar() or 0


async def _count_where(db: AsyncSession, model, condition) -> int:
    result = await db.execute(select(func.count(model.id)).where(condition))
    return result.scalar() or 0


async def _count_supplier_materials(db: AsyncSession, supplier: Supplier) -> int:
    result = await db.execute(
        select(func.count(func.distinct(SupplierPrice.material_id))).where(SupplierPrice.supplier_id == supplier.id)
    )
    return result.scalar() or 0


async def _count_supplier_documents(db: AsyncSession, supplier: Supplier) -> int:
    result = await db.execute(
        select(func.count(MaterialDocument.id)).where(MaterialDocument.source_id.in_(
            select(Source.id).where(Source.name == supplier.name)
        ))
    )
    return result.scalar() or 0


async def _count_supplier_sources(db: AsyncSession, supplier: Supplier) -> int:
    return await _count_where(db, Source, Source.name == supplier.name)


async def _count_supplier_uploads(db: AsyncSession, supplier: Supplier) -> int:
    return await _count_where(db, SupplierUpload, SupplierUpload.supplier_id == supplier.id)


async def _count_supplier_parsing_errors(db: AsyncSession, supplier: Supplier) -> int:
    result = await db.execute(
        select(func.coalesce(func.sum(SupplierUpload.rows_errors), 0)).where(SupplierUpload.supplier_id == supplier.id)
    )
    return result.scalar() or 0


async def _sum_supplier_upload_errors(db: AsyncSession) -> int:
    result = await db.execute(select(func.coalesce(func.sum(SupplierUpload.rows_errors), 0)))
    return result.scalar() or 0
