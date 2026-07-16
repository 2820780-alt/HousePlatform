from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class CompatibilityClassification(str, Enum):
    EXACT_MATCH = "EXACT_MATCH"
    ALIAS_MATCH = "ALIAS_MATCH"
    RUNTIME_ONLY = "RUNTIME_ONLY"
    REF_ONLY = "REF_ONLY"
    AMBIGUOUS = "AMBIGUOUS"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    STRUCTURE_MISMATCH = "STRUCTURE_MISMATCH"
    INVALID_REFERENCE = "INVALID_REFERENCE"
    UNSUPPORTED = "UNSUPPORTED"
    INCOMPATIBLE_TYPE = "INCOMPATIBLE_TYPE"
    INCOMPATIBLE_UNIT = "INCOMPATIBLE_UNIT"


class IssueSeverity(str, Enum):
    BLOCKER = "BLOCKER"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass(frozen=True)
class ProjectionSource:
    package_id: str
    version: str
    status: str
    path: Path
    integration_allowed: bool | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "package_id": self.package_id,
            "version": self.version,
            "status": self.status,
            "path": str(self.path),
            "integration_allowed": self.integration_allowed,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class ProjectionEntity:
    entity_id: str
    entity_type: str
    source_package_id: str
    classification: CompatibilityClassification
    payload: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "source_package_id": self.source_package_id,
            "classification": self.classification.value,
            "payload": self.payload,
        }


@dataclass(frozen=True)
class ProjectedMaterialGroup:
    source: ProjectionSource
    source_code: str
    normalized_code: str
    title: str
    aliases: tuple[str, ...] = tuple()
    status: str = "UNKNOWN"
    issues: tuple[str, ...] = tuple()
    source_pointer: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.as_dict(),
            "source_code": self.source_code,
            "normalized_code": self.normalized_code,
            "title": self.title,
            "aliases": list(self.aliases),
            "status": self.status,
            "issues": list(self.issues),
            "source_pointer": self.source_pointer,
        }


@dataclass(frozen=True)
class ProjectedMaterialType:
    source: ProjectionSource
    source_code: str
    normalized_code: str
    title: str
    group_code: str | None
    normalized_group_code: str | None
    aliases: tuple[str, ...] = tuple()
    status: str = "UNKNOWN"
    issues: tuple[str, ...] = tuple()
    source_pointer: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.as_dict(),
            "source_code": self.source_code,
            "normalized_code": self.normalized_code,
            "title": self.title,
            "group_code": self.group_code,
            "normalized_group_code": self.normalized_group_code,
            "aliases": list(self.aliases),
            "status": self.status,
            "issues": list(self.issues),
            "source_pointer": self.source_pointer,
        }


@dataclass(frozen=True)
class ProjectedCharacteristicField:
    source: ProjectionSource
    source_code: str
    normalized_code: str
    title: str
    data_type: str | None = None
    unit_code: str | None = None
    aliases: tuple[str, ...] = tuple()
    allowed_values: tuple[str, ...] = tuple()
    status: str = "UNKNOWN"
    issues: tuple[str, ...] = tuple()
    source_pointer: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.as_dict(),
            "source_code": self.source_code,
            "normalized_code": self.normalized_code,
            "title": self.title,
            "data_type": self.data_type,
            "unit_code": self.unit_code,
            "aliases": list(self.aliases),
            "allowed_values": list(self.allowed_values),
            "status": self.status,
            "issues": list(self.issues),
            "source_pointer": self.source_pointer,
        }


@dataclass(frozen=True)
class ProjectedCharacteristicProfile:
    source: ProjectionSource
    source_code: str
    normalized_code: str
    title: str
    field_codes: tuple[str, ...] = tuple()
    required: tuple[str, ...] = tuple()
    module2_required: tuple[str, ...] = tuple()
    recommended: tuple[str, ...] = tuple()
    conditional: tuple[str, ...] = tuple()
    status: str = "UNKNOWN"
    auto_activatable: bool = False
    issues: tuple[str, ...] = tuple()
    source_pointer: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.as_dict(),
            "source_code": self.source_code,
            "normalized_code": self.normalized_code,
            "title": self.title,
            "field_codes": list(self.field_codes),
            "required": list(self.required),
            "module2_required": list(self.module2_required),
            "recommended": list(self.recommended),
            "conditional": list(self.conditional),
            "status": self.status,
            "auto_activatable": self.auto_activatable,
            "issues": list(self.issues),
            "source_pointer": self.source_pointer,
        }


@dataclass(frozen=True)
class ProjectedProfileAssignment:
    source: ProjectionSource
    source_code: str
    normalized_code: str
    material_type_id: str
    group_code: str | None
    profile_id: str
    field_codes: tuple[str, ...] = tuple()
    review_required: bool = True
    auto_activatable: bool = False
    issues: tuple[str, ...] = tuple()
    source_pointer: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.as_dict(),
            "source_code": self.source_code,
            "normalized_code": self.normalized_code,
            "material_type_id": self.material_type_id,
            "group_code": self.group_code,
            "profile_id": self.profile_id,
            "field_codes": list(self.field_codes),
            "review_required": self.review_required,
            "auto_activatable": self.auto_activatable,
            "issues": list(self.issues),
            "source_pointer": self.source_pointer,
        }


@dataclass(frozen=True)
class ProjectionIssue:
    code: str
    severity: IssueSeverity
    message: str
    source_path: Path | None = None
    package_id: str | None = None
    entity_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
            "source_path": str(self.source_path) if self.source_path else None,
            "package_id": self.package_id,
            "entity_id": self.entity_id,
        }


@dataclass(frozen=True)
class ProjectionSummary:
    sources: tuple[ProjectionSource, ...]
    entities: tuple[ProjectionEntity, ...]
    issues: tuple[ProjectionIssue, ...]

    @property
    def blocker_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity is IssueSeverity.BLOCKER)

    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity is IssueSeverity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity is IssueSeverity.INFO)

    def as_dict(self) -> dict[str, Any]:
        return {
            "sources": [source.as_dict() for source in self.sources],
            "entities": [entity.as_dict() for entity in self.entities],
            "issues": [issue.as_dict() for issue in self.issues],
            "counts": {
                "sources": len(self.sources),
                "entities": len(self.entities),
                "blockers": self.blocker_count,
                "warnings": self.warning_count,
                "info": self.info_count,
            },
        }
