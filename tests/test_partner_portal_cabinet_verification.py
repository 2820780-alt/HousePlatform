import pytest

from app.models import CabinetModerationLog, CabinetVerification
from app.models.partner_portal import MODULE_08_PARTNER_PORTAL
from app.services.partner_portal_cabinet_verification import (
    CABINET_VERIFICATION_LEVELS,
    CABINET_VERIFICATION_STATUSES,
    build_cabinet_moderation_log,
    build_cabinet_verification,
)


def test_cabinet_verification_and_moderation_models_are_module8_entities():
    verification_columns = set(CabinetVerification.__table__.columns.keys())
    log_columns = set(CabinetModerationLog.__table__.columns.keys())

    assert CabinetVerification.__tablename__ == "module08_cabinet_verifications"
    assert CabinetModerationLog.__tablename__ == "module08_cabinet_moderation_logs"
    assert CabinetVerification.__table__.columns["module_code"].default.arg == MODULE_08_PARTNER_PORTAL
    assert CabinetModerationLog.__table__.columns["module_code"].default.arg == MODULE_08_PARTNER_PORTAL
    for column in (
        "cabinet_id",
        "cabinet_type",
        "verification_status",
        "verification_level",
        "reviewed_by_user_id",
        "reviewed_at",
        "next_review_at",
        "reason",
    ):
        assert column in verification_columns
    for column in (
        "cabinet_id",
        "moderation_event",
        "previous_status",
        "new_status",
        "previous_level",
        "new_level",
        "actor_user_id",
        "reason",
        "comment",
    ):
        assert column in log_columns


def test_cabinet_verification_supports_requested_statuses_and_levels():
    assert CABINET_VERIFICATION_STATUSES == (
        "DRAFT",
        "PENDING_REVIEW",
        "VERIFIED",
        "NEEDS_CLARIFICATION",
        "REJECTED",
        "RESTRICTED",
        "BLOCKED",
        "ARCHIVED",
    )
    assert CABINET_VERIFICATION_LEVELS == (
        "NOT_VERIFIED",
        "BASIC_CHECKED",
        "DOCUMENTS_CHECKED",
        "COMPANY_VERIFIED",
        "TRUSTED_PARTNER",
    )


def test_build_cabinet_verification_normalizes_status_and_level_without_granting_permissions():
    verification = build_cabinet_verification(
        {
            "cabinetId": "cabinet-company-1",
            "cabinetType": "CONSTRUCTION_COMPANY",
            "verificationStatus": "verified",
            "verificationLevel": "trusted_partner",
            "reviewedByUserId": "moderator-1",
            "reason": "Documents checked.",
        }
    ).to_dict()

    assert verification["cabinetId"] == "cabinet-company-1"
    assert verification["verificationStatus"] == "VERIFIED"
    assert verification["verificationLevel"] == "TRUSTED_PARTNER"
    assert verification["sourceModuleCode"] == MODULE_08_PARTNER_PORTAL
    assert verification["targetModuleCode"] == MODULE_08_PARTNER_PORTAL
    assert "permissionCode" not in verification
    assert "accessLevel" not in verification


def test_build_cabinet_moderation_log_records_history_not_audit_or_rbac():
    log = build_cabinet_moderation_log(
        {
            "cabinetId": "cabinet-supplier-1",
            "moderationEvent": "clarification_requested",
            "previousStatus": "pending_review",
            "newStatus": "needs_clarification",
            "previousLevel": "basic_checked",
            "newLevel": "basic_checked",
            "actorUserId": "moderator-1",
            "comment": "Need updated company document.",
        }
    ).to_dict()

    assert log["moderationEvent"] == "CLARIFICATION_REQUESTED"
    assert log["previousStatus"] == "PENDING_REVIEW"
    assert log["newStatus"] == "NEEDS_CLARIFICATION"
    assert log["previousLevel"] == "BASIC_CHECKED"
    assert log["newLevel"] == "BASIC_CHECKED"
    assert log["sourceModuleCode"] == MODULE_08_PARTNER_PORTAL
    assert "AuditLog" not in log
    assert "Permission" not in log


def test_cabinet_verification_rejects_unknown_status_or_level():
    with pytest.raises(ValueError):
        build_cabinet_verification({"verificationStatus": "ACTIVE"})
    with pytest.raises(ValueError):
        build_cabinet_verification({"verificationLevel": "GOLD"})
