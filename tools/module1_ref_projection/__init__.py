"""Inactive Module 1 REF projection tooling.

This package is intentionally isolated from production runtime code. It can read
prepared REF source packages only when called explicitly by tests or CLI.
"""

from .loader import DEFAULT_PACKAGE_FILES, RefPackageLoader
from .models import (
    CompatibilityClassification,
    ProjectedCharacteristicField,
    ProjectedCharacteristicProfile,
    ProjectedMaterialGroup,
    ProjectedMaterialType,
    ProjectedProfileAssignment,
    ProjectionEntity,
    ProjectionIssue,
    ProjectionSource,
    ProjectionSummary,
)
from .ref1 import Ref1ProjectionResult, project_ref1_taxonomy, write_ref1_projection_outputs
from .ref2 import Ref2ProjectionResult, project_ref2_characteristics, write_ref2_projection_outputs
from .validator import ProjectionValidator

__all__ = [
    "CompatibilityClassification",
    "DEFAULT_PACKAGE_FILES",
    "ProjectedCharacteristicField",
    "ProjectedCharacteristicProfile",
    "ProjectedMaterialGroup",
    "ProjectedMaterialType",
    "ProjectedProfileAssignment",
    "ProjectionEntity",
    "ProjectionIssue",
    "ProjectionSource",
    "ProjectionSummary",
    "ProjectionValidator",
    "Ref1ProjectionResult",
    "Ref2ProjectionResult",
    "RefPackageLoader",
    "project_ref1_taxonomy",
    "project_ref2_characteristics",
    "write_ref1_projection_outputs",
    "write_ref2_projection_outputs",
]
