from __future__ import annotations

from pathlib import Path

from .loader import RefPackageLoader
from .models import IssueSeverity, ProjectionIssue, ProjectionSummary


class ProjectionValidator:
    """Validator skeleton for inactive REF projection packages."""

    def __init__(self, reference_root: str | Path) -> None:
        self.reference_root = Path(reference_root)

    def validate(self) -> ProjectionSummary:
        summary = RefPackageLoader(self.reference_root).load()
        issues = list(summary.issues)

        for source in summary.sources:
            if source.integration_allowed is True:
                issues.append(
                    ProjectionIssue(
                        code="REF_RUNTIME_INTEGRATION_ALLOWED",
                        severity=IssueSeverity.WARNING,
                        message="REF package is marked integration_allowed=true; projection tooling must keep it inactive.",
                        source_path=source.path,
                        package_id=source.package_id,
                    )
                )

        return ProjectionSummary(
            sources=summary.sources,
            entities=summary.entities,
            issues=tuple(sorted(issues, key=lambda item: (item.code, item.package_id or "", item.message))),
        )
