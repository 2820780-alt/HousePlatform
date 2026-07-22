from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from .models import IssueSeverity, ProjectionIssue, ProjectionSource, ProjectionSummary
from .portability import PortabilityValidationError, strict_json_file


DEFAULT_PACKAGE_FILES: Mapping[str, str] = {
    "REF-1": "ATOM_REF1_Material_Taxonomy_v2_PRELIMINARY_APPROVED.json",
    "REF-2A": "ATOM_REF2_Field_Dictionary_v1_DRAFT.json",
    "REF-2B": "ATOM_REF2_Material_Characteristic_Profiles_v1_DRAFT.json",
    "REF-3A": "ATOM_REF3_Unit_Dictionary_v1_DRAFT.json",
    "REF-3B": "ATOM_REF3_Packaging_Quantity_Profiles_v1_DRAFT.json",
    "REF-3C": "ATOM_REF3_Geometry_Coverage_Consumption_Rules_v1_DRAFT.json",
    "REF-3-MANIFEST": "ATOM_REF3_Package_Manifest_v1_DRAFT.json",
}

SUPPORTED_VERSIONS = {
    "0.3-preliminary-approved",
    "0.1-draft",
    "0.2-draft",
    "0.3-draft",
}


class RefPackageLoader:
    """Read-only loader for inactive Module 1 REF source packages."""

    def __init__(
        self,
        reference_root: str | Path,
        package_files: Mapping[str, str] | None = None,
    ) -> None:
        self.reference_root = Path(reference_root)
        self.package_files = dict(package_files or DEFAULT_PACKAGE_FILES)

    def load(self) -> ProjectionSummary:
        sources: list[ProjectionSource] = []
        issues: list[ProjectionIssue] = []

        for expected_package_id, filename in sorted(self.package_files.items()):
            path = self.reference_root / filename
            if not path.exists():
                issues.append(
                    ProjectionIssue(
                        code="REF_MISSING_FILE",
                        severity=IssueSeverity.BLOCKER,
                        message=f"Missing REF package file: {filename}",
                        source_path=path,
                        package_id=expected_package_id,
                    )
                )
                continue

            payload = self._read_json(path, expected_package_id, issues)
            if payload is None:
                continue

            metadata = self._extract_metadata(payload)
            package_id = str(metadata.get("package_id") or expected_package_id)
            version = str(metadata.get("version") or "UNKNOWN")
            status = str(metadata.get("status") or "UNKNOWN")
            integration_allowed = self._extract_integration_allowed(payload)

            if version not in SUPPORTED_VERSIONS:
                issues.append(
                    ProjectionIssue(
                        code="REF_UNSUPPORTED_VERSION",
                        severity=IssueSeverity.WARNING,
                        message=f"Unsupported REF package version: {version}",
                        source_path=path,
                        package_id=package_id,
                    )
                )

            issues.extend(self._duplicate_id_issues(payload, path, package_id))
            sources.append(
                ProjectionSource(
                    package_id=package_id,
                    version=version,
                    status=status,
                    path=path,
                    integration_allowed=integration_allowed,
                    metadata=metadata,
                )
            )

        return ProjectionSummary(
            sources=tuple(sorted(sources, key=lambda item: item.package_id)),
            entities=tuple(),
            issues=tuple(sorted(issues, key=lambda item: (item.code, item.package_id or "", item.message))),
        )

    def _read_json(
        self,
        path: Path,
        package_id: str,
        issues: list[ProjectionIssue],
    ) -> dict[str, Any] | None:
        try:
            payload = strict_json_file(path)
            if not isinstance(payload, dict):
                raise PortabilityValidationError("invalid_json", "JSON root must be an object")
            return payload
        except PortabilityValidationError as exc:
            issue_code = "REF_MALFORMED_JSON" if exc.status == "invalid_json" else f"REF_{exc.status.upper()}"
            issues.append(
                ProjectionIssue(
                    code=issue_code,
                    severity=IssueSeverity.BLOCKER,
                    message=f"REF source validation failed: {exc.status}",
                    source_path=path,
                    package_id=package_id,
                )
            )
        return None

    def _extract_metadata(self, payload: dict[str, Any]) -> dict[str, Any]:
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        package_id = payload.get("package_id") or metadata.get("package_id") or payload.get("id")
        version = payload.get("version") or payload.get("package_version") or metadata.get("version")
        status = payload.get("status") or metadata.get("status")
        return {
            "package_id": package_id,
            "version": version,
            "status": status,
        }

    def _extract_integration_allowed(self, payload: dict[str, Any]) -> bool | None:
        if isinstance(payload.get("integration_allowed"), bool):
            return payload["integration_allowed"]
        approval = payload.get("approval")
        if isinstance(approval, dict) and isinstance(approval.get("integration_allowed"), bool):
            return approval["integration_allowed"]
        return None

    def _duplicate_id_issues(
        self,
        payload: dict[str, Any],
        path: Path,
        package_id: str,
    ) -> list[ProjectionIssue]:
        issues: list[ProjectionIssue] = []
        for collection_name, value in payload.items():
            if not isinstance(value, list):
                continue
            if collection_name == "review_queue":
                continue
            identifiers = [
                self._entity_identifier(collection_name, item)
                for item in value
                if isinstance(item, dict)
            ]
            identifiers = [item for item in identifiers if item]
            for identifier, count in Counter(identifiers).items():
                if count > 1:
                    issues.append(
                        ProjectionIssue(
                            code="REF_DUPLICATE_ID",
                            severity=IssueSeverity.BLOCKER,
                            message=f"Duplicate identifier {identifier!r} in {collection_name}",
                            source_path=path,
                            package_id=package_id,
                            entity_id=identifier,
                        )
                    )
        return issues

    def _entity_identifier(self, collection_name: str, item: dict[str, Any]) -> str | None:
        collection_keys = {
            "groups": ("group_id", "id"),
            "material_types": ("material_type_id", "id"),
            "fields": ("field_code", "id"),
            "profiles": ("profile_id", "id"),
            "units": ("unit_code", "id"),
            "geometry_rules": ("rule_id", "id"),
            "coverage_consumption_rules": ("rule_id", "id"),
            "packaging_profiles": ("profile_id", "id"),
            "material_type_assignments": ("material_type_id", "id"),
        }
        for key in collection_keys.get(
            collection_name,
            ("id", "material_type_id", "field_code", "profile_id", "unit_code", "rule_id", "package_id"),
        ):
            value = item.get(key)
            if isinstance(value, str) and value:
                return value
        return None
