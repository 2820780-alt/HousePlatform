from datetime import date
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DBSession
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.enums import (
    SourceActionType,
    SourceType,
    TaskStatus,
    UploadFileType,
    UploadStatus,
    UserRole,
)
from app.models.source import Source
from app.models.source_task import SourceTask
from app.models.supplier_account import SupplierAccount
from app.models.supplier_upload import SupplierUpload
from app.processing.file_validator import validate_file
from app.schemas.common import PaginatedResponse
from app.schemas.material_hub import SupplierUploadRead
from app.services.audit_service import log_event
from app.services.upload_storage import save_uploaded_file

router = APIRouter(prefix="/supplier", tags=["supplier-upload"])


async def _get_my_supplier_id(db, user) -> UUID:
    if user.role != UserRole.SUPPLIER:
        raise ForbiddenError()
    result = await db.execute(
        select(SupplierAccount.supplier_id).where(SupplierAccount.user_id == user.id)
    )
    supplier_id = result.scalar_one_or_none()
    if not supplier_id:
        raise NotFoundError("No supplier linked")
    return supplier_id


async def _get_or_create_manual_source(db, supplier_id: UUID) -> Source:
    result = await db.execute(
        select(Source).where(
            Source.source_type == SourceType.MANUAL_UPLOAD,
            Source.name == f"supplier:{supplier_id}:manual-upload",
        )
    )
    source = result.scalar_one_or_none()
    if source:
        return source

    source = Source(
        name=f"supplier:{supplier_id}:manual-upload",
        source_type=SourceType.MANUAL_UPLOAD,
        priority=100,
    )
    db.add(source)
    await db.flush()
    await db.refresh(source)
    return source


@router.post("/upload", response_model=SupplierUploadRead, status_code=201)
async def upload_document(
    db: DBSession,
    user: CurrentUser,
    file: UploadFile = File(...),
    city: str | None = Form(None),
    region: str | None = Form(None),
    price_date: date | None = Form(None),
):
    supplier_id = await _get_my_supplier_id(db, user)
    content = await file.read()

    validation = validate_file(
        filename=file.filename or "",
        content_type=file.content_type,
        file_size_bytes=len(content),
    )
    if not validation.valid:
        raise HTTPException(status_code=422, detail=validation.error)

    source = await _get_or_create_manual_source(db, supplier_id)

    upload = SupplierUpload(
        supplier_id=supplier_id,
        uploaded_by_user_id=user.id,
        source_id=source.id,
        file_name=file.filename or "upload",
        file_type=UploadFileType(validation.file_type.value.upper()),
        status=UploadStatus.UPLOADED,
    )
    db.add(upload)
    await db.flush()
    upload.file_url = save_uploaded_file(content, upload.file_name, upload.id)
    db.add(upload)
    await db.flush()
    await db.refresh(upload)

    task = SourceTask(
        source_id=source.id,
        action_type=SourceActionType.UPLOAD_SUPPLIER_FILE,
        status=TaskStatus.PENDING,
        created_by=user.id,
        result_summary={
            "supplier_upload_id": str(upload.id),
            "supplier_id": str(supplier_id),
            "filename": file.filename,
            "file_url": upload.file_url,
            "file_type": validation.file_type.value,
            "size_bytes": len(content),
            "city": city,
            "region": region,
            "price_date": price_date.isoformat() if price_date else None,
        },
    )
    db.add(task)
    await db.flush()

    await log_event(db, "supplier_upload_created", "SupplierUpload", upload.id, user.id, {
        "source_task_id": str(task.id),
        "source_id": str(source.id),
    })

    return upload


@router.get("/uploads", response_model=PaginatedResponse[SupplierUploadRead])
async def list_uploads(
    db: DBSession,
    user: CurrentUser,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    supplier_id = await _get_my_supplier_id(db, user)
    total_q = await db.execute(
        select(func.count(SupplierUpload.id)).where(SupplierUpload.supplier_id == supplier_id)
    )
    total = total_q.scalar()
    result = await db.execute(
        select(SupplierUpload)
        .where(SupplierUpload.supplier_id == supplier_id)
        .order_by(SupplierUpload.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return PaginatedResponse(items=result.scalars().all(), total=total, offset=offset, limit=limit)


@router.get("/uploads/{upload_id}", response_model=SupplierUploadRead)
async def get_upload(upload_id: UUID, db: DBSession, user: CurrentUser):
    supplier_id = await _get_my_supplier_id(db, user)
    result = await db.execute(
        select(SupplierUpload).where(
            SupplierUpload.id == upload_id,
            SupplierUpload.supplier_id == supplier_id,
        )
    )
    upload = result.scalar_one_or_none()
    if not upload:
        raise NotFoundError("Upload not found")
    return upload


@router.get("/upload/formats")
async def get_supported_formats():
    return {
        "supported_formats": [
            {"extension": ".xlsx", "description": "Excel 2007+ (XLSX)"},
            {"extension": ".csv", "description": "CSV"},
        ],
        "not_supported": [
            "PDF, invoices and commercial offers are future formats",
            "Images and scans",
            "Word and OpenDocument files",
            "Archives",
        ],
        "max_size_mb": 50,
        "note": "Module 01 MVP accepts only CSV and XLSX.",
    }
