from __future__ import annotations

from pathlib import Path

from app.services.module1_golden_materials import build_golden_canonical_view
from app.services.module1_ui_view_models import (
    build_golden_materials_view,
    build_material_detail_view,
    build_material_export_preview_view,
    build_material_list_item_view,
    build_material_quality_view,
    build_module1_ui_preview_context,
    build_workbench_preview_view,
    translate_module1_issue,
    translate_module1_readiness,
    translate_module1_status,
)


def _golden_gas_block():
    return build_golden_canonical_view("golden_aerated_concrete_block_d500")


def test_material_list_item_view_is_human_readable_and_readiness_focused() -> None:
    item = build_material_list_item_view(_golden_gas_block())

    assert item["title"] == "Газоблок D500 600x300x200"
    assert item["category"]
    assert item["status"] == "Эталон"
    assert isinstance(item["qualityScore"], int)
    assert item["readyForModule2"] is True
    assert isinstance(item["readyForModule5"], bool)


def test_material_detail_view_contains_expected_human_sections() -> None:
    detail = build_material_detail_view(_golden_gas_block())

    assert detail["mainInfo"]["name"] == "Газоблок D500 600x300x200"
    assert detail["characteristics"]
    assert detail["technicalProfile"]["readyForModule2"] is True
    assert "documents" in detail
    assert "participants" in detail
    assert "priceObservations" in detail
    assert "quality" in detail
    assert "exportPreview" in detail


def test_quality_view_translates_issues_and_does_not_auto_fix() -> None:
    quality = build_material_quality_view(_golden_gas_block())

    assert quality["score"] > 0
    assert quality["module2Readiness"]["calculationPerformed"] is False
    assert quality["module5Readiness"]["estimateCalculated"] is False
    assert quality["exportReadiness"]["autoFixApplied"] is False
    assert translate_module1_status("needs_review") == "Требует проверки"
    assert translate_module1_readiness("ready_for_module2") == "Готовность к расчетам"
    assert translate_module1_issue({"issue_type": "missing_price", "severity": "medium", "dimension": "price_observations"})["title"] == "Нет наблюдения цены"


def test_workbench_preview_is_dry_run_and_hides_raw_payload() -> None:
    preview = build_workbench_preview_view(canonical_material_view=_golden_gas_block())

    assert preview["title"] == "Лаборатория извлечения"
    assert preview["noHttp"] is True
    assert preview["noParsing"] is True
    assert preview["noOcr"] is True
    assert preview["noSideEffects"] is True
    assert preview["matching"]["mergesDuplicate"] is False
    assert preview["moderation"]["decisionApplied"] is False
    assert "raw_payload" not in str(preview)
    assert "Сопоставлено" in {trace["status"] for trace in preview["fieldTrace"]} or "Не используется" in {
        trace["status"] for trace in preview["fieldTrace"]
    }


def test_golden_materials_and_export_preview_are_read_only() -> None:
    golden = build_golden_materials_view(limit=3)
    export_preview = build_material_export_preview_view(_golden_gas_block())

    assert golden["readOnly"] is True
    assert golden["noDatabaseWrites"] is True
    assert golden["items"]
    assert export_preview["noFileGeneration"] is True
    assert export_preview["noSideEffects"] is True
    assert all("Package" not in package["title"] for package in export_preview["packages"])


def test_module1_ui_preview_context_groups_materials_quality_workbench_and_exports() -> None:
    context = build_module1_ui_preview_context(golden_limit=2)

    assert "Материалы" in context["sections"]
    assert "Качество данных" in context["sections"]
    assert "Лаборатория извлечения" in context["sections"]
    assert "Эталонные материалы" in context["sections"]
    assert "Экспортные пакеты" in context["sections"]
    assert len(context["materials"]) == 2
    assert context["selectedMaterial"]["mainInfo"]["name"]
    assert context["quality"]["autoFixApplied"] is False
    assert context["workbench"]["noSideEffects"] is True
    assert context["exportPreview"]["noFileGeneration"] is True
    assert context["readOnly"] is True
    assert context["noDatabaseWrites"] is True


def test_module1_ui_view_models_do_not_import_orm_network_or_file_export_layers() -> None:
    source = Path("app/services/module1_ui_view_models.py").read_text(encoding="utf-8")

    assert "app.models" not in source
    assert "__tablename__" not in source
    assert ".commit(" not in source
    assert "db.add(" not in source
    assert "Material(" not in source
    assert "CanonicalMaterial(" not in source
    assert "requests" not in source
    assert "httpx" not in source
    assert ".to_csv(" not in source
    assert ".to_excel(" not in source
