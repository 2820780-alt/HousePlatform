"""Inactive Module 1 REF projection tooling.

This package is intentionally isolated from production runtime code. It can read
prepared REF source packages only when called explicitly by tests or CLI.
"""

from .combined import CombinedProjectionResult, project_combined_ref_validation, write_combined_projection_outputs
from .loader import DEFAULT_PACKAGE_FILES, RefPackageLoader
from .models import (
    CompatibilityClassification,
    ProjectedCharacteristicField,
    ProjectedCharacteristicProfile,
    ProjectedConsumptionRule,
    ProjectedConversion,
    ProjectedCoverageRule,
    ProjectedGeometryRule,
    ProjectedMaterialGroup,
    ProjectedMaterialType,
    ProjectedPackagingRule,
    ProjectedProfileAssignment,
    ProjectedUnit,
    ProjectedYieldRule,
    ProjectionEntity,
    ProjectionIssue,
    ProjectionSource,
    ProjectionSummary,
)
from .ref1 import Ref1ProjectionResult, project_ref1_taxonomy, write_ref1_projection_outputs
from .ref2 import Ref2ProjectionResult, project_ref2_characteristics, write_ref2_projection_outputs
from .ref3_extended import Ref3ExtendedProjectionResult, project_ref3_extended, write_ref3_extended_projection_outputs
from .ref3_units import Ref3UnitProjectionResult, project_ref3_units, write_ref3_unit_projection_outputs
from .runtime_artifacts import (
    RuntimeArtifactBuildError,
    RuntimeArtifactBuildResult,
    build_runtime_artifact_package,
    derive_artifact_set_id,
)
from .validator import ProjectionValidator

__all__ = [
    "CompatibilityClassification",
    "CombinedProjectionResult",
    "DEFAULT_PACKAGE_FILES",
    "ProjectedCharacteristicField",
    "ProjectedCharacteristicProfile",
    "ProjectedConsumptionRule",
    "ProjectedConversion",
    "ProjectedCoverageRule",
    "ProjectedGeometryRule",
    "ProjectedMaterialGroup",
    "ProjectedMaterialType",
    "ProjectedPackagingRule",
    "ProjectedProfileAssignment",
    "ProjectedUnit",
    "ProjectedYieldRule",
    "ProjectionEntity",
    "ProjectionIssue",
    "ProjectionSource",
    "ProjectionSummary",
    "ProjectionValidator",
    "Ref1ProjectionResult",
    "Ref2ProjectionResult",
    "Ref3ExtendedProjectionResult",
    "Ref3UnitProjectionResult",
    "RefPackageLoader",
    "RuntimeArtifactBuildError",
    "RuntimeArtifactBuildResult",
    "build_runtime_artifact_package",
    "derive_artifact_set_id",
    "project_combined_ref_validation",
    "project_ref1_taxonomy",
    "project_ref2_characteristics",
    "project_ref3_extended",
    "project_ref3_units",
    "write_combined_projection_outputs",
    "write_ref1_projection_outputs",
    "write_ref2_projection_outputs",
    "write_ref3_extended_projection_outputs",
    "write_ref3_unit_projection_outputs",
]
