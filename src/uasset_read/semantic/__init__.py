"""Semantic JSON -- common infrastructure for UAsset semantic output."""
from uasset_read.semantic.models import (
    SemanticIR, AssetMeta, AssetStatus, CoverageInfo,
    DiagnosticEntry, EvidenceEntry, ReferenceEntry,
)
from uasset_read.semantic.builder import build_semantic_ir
from uasset_read.semantic.projection import project_semantic
from uasset_read.semantic.validator import validate_semantic_document
from uasset_read.semantic.render import render_semantic_json

# Domain extractors migrated to #554-#557 (stubs in graph_domain, structured_domain, resource_domain)
import uasset_read.semantic.blueprint  # noqa: F401  (registers #554 extractors)
import uasset_read.semantic.anim_blueprint  # noqa: F401  (registers #555 extractors)
import uasset_read.semantic.material  # noqa: F401  (registers #556 extractors)
import uasset_read.semantic.data_table  # noqa: F401  (registers #557 DataTable extractors)
import uasset_read.semantic.skeleton  # noqa: F401  (registers #557 Skeleton extractors)
import uasset_read.semantic.mesh  # noqa: F401  (registers #557a Mesh extractors)
import uasset_read.semantic.texture  # noqa: F401  (registers #557b Texture extractors)
import uasset_read.semantic.sound  # noqa: F401  (registers #557c Sound extractors)
import uasset_read.semantic.anim  # noqa: F401  (registers #557f Animation extractors)
import uasset_read.semantic.curve_table  # noqa: F401  (registers #557d CurveTable extractors)
import uasset_read.semantic.user_defined  # noqa: F401  (registers #557g UserDefined extractors)
import uasset_read.semantic.standalone  # noqa: F401  (registers #557h Standalone extractors)
import uasset_read.semantic.niagara  # noqa: F401  (registers #557e Niagara extractors)

__all__ = [
    "SemanticIR", "AssetMeta", "AssetStatus", "CoverageInfo",
    "DiagnosticEntry", "EvidenceEntry", "ReferenceEntry",
    "build_semantic_ir", "project_semantic",
    "validate_semantic_document", "render_semantic_json",
]
