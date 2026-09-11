from __future__ import annotations

import ast
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from app.services.module1_alternatives_analogs import build_alternative_readiness_report
from app.services.module1_compatibility_matrix import build_compatibility_readiness_report
from app.services.module1_data_quality_dashboard import build_material_quality_snapshot
from app.services.module1_documents_evidence import (
    build_document_evidence_from_raw_link,
    build_document_package,
)
from app.services.module1_export_packages import (
    build_material_export_bundle,
    build_module11_analytics_signal_package,
    build_module2_technology_input_package,
    build_module5_estimate_input_hint_package,
    validate_export_package,
)
from app.services.module1_extraction_workbench import (
    build_extraction_workbench_report,
    build_workbench_input,
)
from app.services.module1_golden_materials import build_golden_canonical_view
from app.services.module1_matching_dedup import build_match_candidate
from app.services.module1_material_normalizer import normalize_raw_ingestion_item
from app.services.module1_material_roles import build_material_role_readiness_report
from app.services.module1_moderation_core import (
    MaterialModerationDecision,
    build_decision_plan,
    build_moderation_queue_item,
)
from app.services.module1_participants_directory import build_participant_directory_package
from app.services.module1_price_work_observations import build_price_observation_package
from app.services.module1_raw_ingestion_pipeline import (
    build_raw_ingestion_item_from_source_task_result,
    validate_raw_ingestion_item,
)
from app.services.module1_technical_profile_packaging import build_material_technical_profile
from app.services.module1_ui_view_models import (
    build_material_detail_view,
    build_module1_ui_preview_context,
)


def _gas_block_raw_payload() -> dict:
    return {
        "sourceCode": "YUFO_VKBLOCK",
        "sourceUrl": "https://vkblock.ru/product/gazoblok-d500",
        "title": "Газоблок D500 B2.5 600x300x200",
        "category": "Газобетон",
        "price": "4200",
        "unit": "м3",
        "manufacturer": "VKBlock",
        "region": "Краснодарский край",
        "characteristics": {
            "length_mm": 600,
            "width_mm": 300,
            "height_mm": 200,
            "density_class": "D500",
            "strength_class": "B2.5",
            "frost_resistance": "F35",
            "thermal_conductivity": "0.12",
            "pieces_per_m3": "27.8",
            "volume_per_piece_m3": "0.036",
        },
        "documentLinks": ["https://vkblock.ru/cert.pdf"],
    }


def test_golden_gas_block_full_module1_path_is_preview_only_and_serializable() -> None:
    view = build_golden_canonical_view("golden_aerated_concrete_block_d500")
    technical_profile = build_material_technical_profile(view)
    role_report = build_material_role_readiness_report(technical_profile)
    alternative_report = build_alternative_readiness_report(technical_profile)
    compatibility_report = build_compatibility_readiness_report(technical_profile)
    documents = build_document_package(view)
    participants = build_participant_directory_package(view)
    prices = build_price_observation_package(view)
    quality = build_material_quality_snapshot(view)
    export_bundle = build_material_export_bundle(view)

    assert view.material_id == "golden_aerated_concrete_block_d500"
    assert technical_profile.readiness.ready_for_module2 is True
    assert role_report.roles_found is True
    assert alternative_report.message.endswith("without automatic material replacement.")
    assert compatibility_report.message.endswith("without technology, quantity or cost calculations.")
    assert documents.material_id == view.material_id
    assert participants.participants
    assert prices.observations
    assert quality.overall_quality_score > 0
    assert export_bundle.no_side_effects is True
    assert validate_export_package(export_bundle).is_valid is True
    assert export_bundle.module2_package.no_calculation_result is True
    assert export_bundle.module5_package.no_estimate_total is True
    assert export_bundle.module11_signals.no_charts is True


def test_raw_ingestion_to_moderation_preview_does_not_create_or_merge_materials() -> None:
    result = SimpleNamespace(
        entity_type="catalog_product",
        source_id="source-task-source",
        created_at=datetime(2026, 7, 2, 9, 0),
        new_value={**_gas_block_raw_payload(), "adapterVersion": "qa-adapter-v1"},
    )
    raw_item = build_raw_ingestion_item_from_source_task_result(result)
    validation = validate_raw_ingestion_item(raw_item)
    normalized = normalize_raw_ingestion_item(raw_item)
    existing = {
        "id": "mat-gas-001",
        "canonical_name": "Газоблок D500 B2.5 600x300x200",
        "group_code": "aerated_concrete_block",
        "normalized_characteristics": {
            "length_mm": Decimal("600"),
            "width_mm": Decimal("300"),
            "height_mm": Decimal("200"),
            "density_class": "D500",
            "strength_class": "B2.5",
        },
        "unit": "m3",
    }
    match = build_match_candidate(normalized, [existing])
    queue_item = build_moderation_queue_item(match)
    decision = MaterialModerationDecision(
        decision_type="accept_match",
        moderator_id="qa-moderator",
        comment="Final QA preview only.",
        confirmed=True,
    )
    plan = build_decision_plan(queue_item, decision)

    assert validation.is_valid is True
    assert raw_item.raw_payload["legacy_entity"] == "SourceTaskResult"
    assert normalized.suggested_group_code == "aerated_concrete_block"
    assert match.matched_material_reference["id"] == "mat-gas-001"
    assert any("No automatic merge" in item for item in match.explanation)
    assert queue_item.allowed_decisions
    assert plan.no_side_effects is True
    assert any("No database write" in warning for warning in plan.warnings)
    assert any("Do not create aliases automatically" in operation for operation in plan.operations_preview)


def test_extraction_workbench_full_preview_has_no_http_parsing_ocr_or_side_effects() -> None:
    workbench_input = build_workbench_input(
        _gas_block_raw_payload(),
        source_profile_code="YUFO_VKBLOCK",
        extraction_profile_code="yufo_vkblock_extraction_profile",
        material_group="aerated_concrete_block",
    )
    report = build_extraction_workbench_report(
        workbench_input,
        canonical_material_view=build_golden_canonical_view("golden_aerated_concrete_block_d500"),
    )

    assert report.no_side_effects is True
    assert report.pipeline_preview.no_side_effects is True
    assert report.pipeline_preview.raw_ingestion_preview["rawDataIsCanonical"] is False
    assert report.pipeline_preview.matching_preview["mergesDuplicate"] is False
    assert report.pipeline_preview.moderation_preview["decisionApplied"] is False
    assert all(hint.safe_to_auto_apply is False for hint in report.action_hints)


def test_metal_tile_keeps_fastening_pattern_as_hint_not_fastener_consumption() -> None:
    metal_tile = build_golden_canonical_view("golden_metal_tile_classic")
    profile = build_material_technical_profile(metal_tile)
    module2_package = build_module2_technology_input_package(metal_tile)
    raw_item = build_raw_ingestion_item_from_source_task_result(
        SimpleNamespace(
            entity_type="catalog_product",
            source_id="source-metal-tile",
            created_at=datetime(2026, 7, 2, 9, 0),
            new_value={
                "sourceCode": "YUFO_SPK_KRASNODAR",
                "title": "Металлочерепица Classic 0.5 мм покрытие Satin",
                "category": "Кровля",
                "unit": "м2",
                "characteristics": {
                    "profile_name": "Classic",
                    "metal_thickness_mm": "0.5",
                    "coating": "Satin",
                    "fastening_pattern_code": "standard_roof",
                    "screw_consumption": "8",
                },
            },
        )
    )
    normalized = normalize_raw_ingestion_item(raw_item)

    assert "fastening_pattern_code" in profile.technical_characteristics
    assert "fastening_pattern_code" in profile.module2_required_fields
    assert module2_package.no_calculation_result is True
    assert "screw_consumption" not in profile.technical_characteristics
    assert "screws_per_m2" not in profile.technical_characteristics
    assert "screw_consumption" not in normalized.normalized_characteristics
    assert "screws_per_m2" not in normalized.normalized_characteristics


def test_price_documents_participants_and_export_layers_stay_non_operational() -> None:
    view = build_golden_canonical_view("golden_aerated_concrete_block_d500")
    price_package = build_price_observation_package(view)
    document_evidence = build_document_evidence_from_raw_link(
        {"title": "Product card", "url": "https://example.test/catalog/aerated-concrete-d500"},
        material_id=view.material_id,
        material_group="aerated_concrete_block",
    )
    participants = build_participant_directory_package(view)
    module5_package = build_module5_estimate_input_hint_package(view)
    module11_signals = build_module11_analytics_signal_package(view)

    assert price_package.observations
    assert price_package.readiness.status in {"ready", "ready_with_warnings", "has_observations", "needs_review"}
    assert "without estimates" in price_package.readiness.message
    assert document_evidence.raw_link is not None
    assert document_evidence.raw_link.is_document is False
    assert document_evidence.document is None
    assert participants.participants
    assert all(getattr(item, "participant_type", None) != "user" for item in participants.participants)
    assert module5_package.price_observation_refs
    assert module5_package.no_estimate_total is True
    assert module5_package.no_selected_best_price is True
    assert module11_signals.no_charts is True
    assert module11_signals.no_dynamic_analytics is True


def test_ui_view_model_is_human_readable_and_hides_dto_names_and_raw_payloads() -> None:
    view = build_golden_canonical_view("golden_aerated_concrete_block_d500")
    detail = build_material_detail_view(view)
    context = build_module1_ui_preview_context(golden_limit=2)
    rendered_preview = str({"detail": detail, "context": context})

    assert detail["mainInfo"]["name"] == "Газоблок D500 600x300x200"
    assert detail["quality"]["module2Readiness"]["calculationPerformed"] is False
    assert context["readOnly"] is True
    assert context["noDatabaseWrites"] is True
    assert context["workbench"]["noHttp"] is True
    assert context["workbench"]["noOcr"] is True
    assert "CleanMaterialPackage" not in rendered_preview
    assert "Module2TechnologyInputPackage" not in rendered_preview
    assert "raw_payload" not in rendered_preview
    assert "debug" not in rendered_preview.lower()


READ_ONLY_SERVICES = frozenset(
    {
        "module1_alternatives_analogs.py",
        "module1_characteristic_schema_registry.py",
        "module1_compatibility_matrix.py",
        "module1_data_quality_dashboard.py",
        "module1_documents_evidence.py",
        "module1_extraction_blueprint_registry.py",
        "module1_golden_materials.py",
        "module1_legacy_compatibility.py",
        "module1_material_roles.py",
        "module1_material_seed_registry.py",
        "module1_participants_directory.py",
        "module1_price_work_observations.py",
        "module1_ref1_read_policy.py",
        "module1_ref2_read_policy.py",
        "module1_ref3_read_policy.py",
        "module1_ref3_read_projection.py",
        "module1_ref4_normalization_policy.py",
        "module1_ref5_compatibility_policy.py",
        "module1_ref6_work_material_policy.py",
        "module1_ref_artifact_portability.py",
        "module1_ref_dual_read.py",
        "module1_ref_runtime_artifacts.py",
        "module1_source_profile_registry.py",
        "module1_ui_view_models.py",
        "module1_unit_conversion_registry.py",
        "module1_work_catalog.py",
    }
)

EXPORT_PACKAGE_SERVICES = frozenset(
    {
        "module1_export_packages.py",
        "module1_technical_profile_packaging.py",
        "module1_work_cost_export_contract.py",
    }
)

# These pipeline services currently build plans/DTOs only. Any future database
# write must be classified explicitly instead of silently inheriting permission.
INGESTION_CANONICAL_PIPELINE_SERVICES = frozenset(
    {
        "module1_canonical_material_store.py",
        "module1_extraction_workbench.py",
        "module1_matching_dedup.py",
        "module1_material_normalizer.py",
        "module1_moderation_core.py",
        "module1_raw_ingestion_pipeline.py",
    }
)

PERSISTENCE_SERVICE_BOUNDARIES = {
    "module1_provider_work_cost_offers.py": {
        "allowed_session_methods": frozenset({"add", "flush"}),
        "allowed_add_targets": frozenset({"offer"}),
        "allowed_mutation_roots": frozenset({"offer"}),
        "allowed_models": frozenset({"ProviderWorkCostOffer"}),
        "reason": "Module 1 owns provider work cost offers; owner and RBAC are enforced server-side.",
    },
    "module1_operational_widgets.py": {
        "allowed_session_methods": frozenset({"add", "flush"}),
        "allowed_add_targets": frozenset({"layout"}),
        "allowed_mutation_roots": frozenset({"layout"}),
        "allowed_models": frozenset({"UserDashboardLayout"}),
        # FUTURE_CLEANUP_CANDIDATE: layout persistence could move to a dedicated
        # settings service, but it remains a legitimate user-scoped write today.
        "reason": "Module 1 may persist its widget instances in the current user's dashboard layout.",
    },
}

SESSION_WRITE_METHODS = frozenset(
    {
        "add",
        "add_all",
        "bulk_insert_mappings",
        "bulk_save_objects",
        "bulk_update_mappings",
        "commit",
        "delete",
        "flush",
        "merge",
    }
)
SQLALCHEMY_DML_BUILDERS = frozenset({"delete", "insert", "update"})
FORBIDDEN_RUNTIME_IMPORT_PREFIXES = (
    "httpx",
    "requests",
    "urllib",
    "app.api.v1.admin_cabinet",
    "app.services.module2",
    "app.services.module3",
    "app.services.module5",
    "app.services.module9",
    "app.services.module11",
)
FORBIDDEN_PERSISTENCE_MODEL_PREFIXES = (
    "app.models.knowledge_",
    "app.models.estimate",
    "app.models.procurement",
    "app.models.tender",
    "app.models.analytics",
    "app.models.market_index",
)
MATERIAL_PRICE_MODELS = frozenset(
    {"CatalogProduct", "Material", "MaterialMatchCandidate", "PriceHistory", "SupplierPrice"}
)


def _service_path(file_name: str) -> Path:
    return Path("app/services") / file_name


def _service_tree(file_name: str) -> ast.Module:
    path = _service_path(file_name)
    return ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))


def _imported_modules(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
            modules.update(f"{node.module}.{alias.name}" for alias in node.names)
    return modules


def _session_names(tree: ast.AST) -> set[str]:
    names = {"db", "session"}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for argument in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
            annotation = ast.unparse(argument.annotation) if argument.annotation is not None else ""
            if "Session" in annotation:
                names.add(argument.arg)
    return names


def _receiver_is_session(receiver: ast.AST, session_names: set[str]) -> bool:
    if isinstance(receiver, ast.Name):
        return receiver.id in session_names
    return isinstance(receiver, ast.Attribute) and receiver.attr in session_names


def _session_write_calls(tree: ast.AST) -> list[tuple[str, int, ast.Call]]:
    session_names = _session_names(tree)
    calls: list[tuple[str, int, ast.Call]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if _receiver_is_session(node.func.value, session_names) and node.func.attr in SESSION_WRITE_METHODS:
            calls.append((node.func.attr, node.lineno, node))
    return calls


def _sqlalchemy_dml_aliases(tree: ast.AST) -> tuple[set[str], set[str]]:
    function_names: set[str] = set()
    module_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "sqlalchemy":
                    module_names.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("sqlalchemy"):
            for alias in node.names:
                if alias.name in SQLALCHEMY_DML_BUILDERS:
                    function_names.add(alias.asname or alias.name)
    return function_names, module_names


def _dml_builder_calls(tree: ast.AST) -> list[tuple[str, int]]:
    function_names, module_names = _sqlalchemy_dml_aliases(tree)
    calls: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id in function_names:
            calls.append((node.func.id, node.lineno))
        elif (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in SQLALCHEMY_DML_BUILDERS
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in module_names
        ):
            calls.append((node.func.attr, node.lineno))
    return calls


def _raw_sql_writes(tree: ast.AST) -> list[tuple[str, int]]:
    writes: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        sql = node.value.lstrip().upper()
        if sql.startswith(("DELETE ", "INSERT ", "UPDATE ")):
            writes.append((sql.split(maxsplit=1)[0], node.lineno))
    return writes


def _constructor_assignments(tree: ast.AST) -> dict[str, set[str]]:
    assignments: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        value = node.value
        if not isinstance(value, ast.Call) or not isinstance(value.func, ast.Name):
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                assignments.setdefault(target.id, set()).add(value.func.id)
    return assignments


def _add_targets(tree: ast.AST) -> set[str]:
    targets: set[str] = set()
    for method, _line, call in _session_write_calls(tree):
        if method != "add" or not call.args:
            continue
        argument = call.args[0]
        targets.add(argument.id if isinstance(argument, ast.Name) else ast.unparse(argument))
    return targets


def _attribute_assignment_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute) or not isinstance(node.ctx, ast.Store):
            continue
        value = node.value
        while isinstance(value, ast.Attribute):
            value = value.value
        if isinstance(value, ast.Name):
            roots.add(value.id)
    return roots


def test_module1_service_boundary_classification_is_complete() -> None:
    actual = {path.name for path in Path("app/services").glob("module1_*.py")}
    classified = (
        READ_ONLY_SERVICES
        | EXPORT_PACKAGE_SERVICES
        | INGESTION_CANONICAL_PIPELINE_SERVICES
        | set(PERSISTENCE_SERVICE_BOUNDARIES)
    )
    assert actual == classified


def test_read_only_export_and_pipeline_services_have_no_database_writes() -> None:
    guarded = READ_ONLY_SERVICES | EXPORT_PACKAGE_SERVICES | INGESTION_CANONICAL_PIPELINE_SERVICES
    for file_name in sorted(guarded):
        tree = _service_tree(file_name)
        assert not _session_write_calls(tree), f"{file_name} performs an unclassified session write"
        assert not _dml_builder_calls(tree), f"{file_name} builds direct SQLAlchemy DML"
        assert not _raw_sql_writes(tree), f"{file_name} contains direct write SQL"


def test_persistence_services_stay_inside_their_explicit_write_boundaries() -> None:
    for file_name, boundary in PERSISTENCE_SERVICE_BOUNDARIES.items():
        tree = _service_tree(file_name)
        calls = _session_write_calls(tree)
        methods = {method for method, _line, _call in calls}
        assert boundary["reason"]
        assert methods
        assert methods <= boundary["allowed_session_methods"], (
            f"{file_name} uses unapproved session methods: "
            f"{sorted(methods - boundary['allowed_session_methods'])}"
        )
        add_targets = _add_targets(tree)
        assert add_targets <= boundary["allowed_add_targets"], (
            f"{file_name} adds an unapproved object: "
            f"{sorted(add_targets - boundary['allowed_add_targets'])}"
        )
        assert _attribute_assignment_roots(tree) <= boundary["allowed_mutation_roots"], (
            f"{file_name} mutates an unapproved object root"
        )
        constructors = _constructor_assignments(tree)
        persisted_models = {
            model
            for target in boundary["allowed_add_targets"]
            for model in constructors.get(target, set())
        }
        assert persisted_models <= boundary["allowed_models"], (
            f"{file_name} constructs an unapproved persisted model: {sorted(persisted_models)}"
        )
        assert not _dml_builder_calls(tree), f"{file_name} bypasses the ORM allowlist with direct DML"
        assert not _raw_sql_writes(tree), f"{file_name} bypasses the ORM allowlist with write SQL"
        imported_modules = _imported_modules(tree)
        assert not any(
            module.startswith(prefix)
            for module in imported_modules
            for prefix in FORBIDDEN_PERSISTENCE_MODEL_PREFIXES
        ), f"{file_name} imports a foreign business-module persistence model"


def test_module1_services_do_not_import_external_operational_business_layers() -> None:
    for path in Path("app/services").glob("module1_*.py"):
        imported_modules = _imported_modules(_service_tree(path.name))
        violations = {
            module
            for module in imported_modules
            if any(
                module == prefix or module.startswith(f"{prefix}.")
                for prefix in FORBIDDEN_RUNTIME_IMPORT_PREFIXES
            )
        }
        assert not violations, f"{path.name} imports forbidden operational layers: {sorted(violations)}"


def test_provider_work_cost_and_widget_layout_writes_remain_separate_and_owned() -> None:
    provider_tree = _service_tree("module1_provider_work_cost_offers.py")
    widget_tree = _service_tree("module1_operational_widgets.py")

    provider_models = {
        model
        for target in PERSISTENCE_SERVICE_BOUNDARIES["module1_provider_work_cost_offers.py"]["allowed_add_targets"]
        for model in _constructor_assignments(provider_tree).get(target, set())
    }
    widget_models = {
        model
        for target in PERSISTENCE_SERVICE_BOUNDARIES["module1_operational_widgets.py"]["allowed_add_targets"]
        for model in _constructor_assignments(widget_tree).get(target, set())
    }

    assert provider_models == {"ProviderWorkCostOffer"}
    assert provider_models.isdisjoint(MATERIAL_PRICE_MODELS)
    assert widget_models == {"UserDashboardLayout"}
