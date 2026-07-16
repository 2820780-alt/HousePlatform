"""Inactive Module 1 REF projection tooling.

This package is intentionally isolated from production runtime code. It can read
prepared REF source packages only when called explicitly by tests or CLI.
"""

from .loader import DEFAULT_PACKAGE_FILES, RefPackageLoader
from .models import (
    CompatibilityClassification,
    ProjectionEntity,
    ProjectionIssue,
    ProjectionSource,
    ProjectionSummary,
)
from .validator import ProjectionValidator

__all__ = [
    "CompatibilityClassification",
    "DEFAULT_PACKAGE_FILES",
    "ProjectionEntity",
    "ProjectionIssue",
    "ProjectionSource",
    "ProjectionSummary",
    "ProjectionValidator",
    "RefPackageLoader",
]
