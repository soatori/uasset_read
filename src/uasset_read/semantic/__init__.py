"""Semantic JSON -- common infrastructure for UAsset semantic output."""
from uasset_read.semantic.models import (
    SemanticIR, AssetMeta, AssetStatus, CoverageInfo,
    DiagnosticEntry, EvidenceEntry, ReferenceEntry,
)
from uasset_read.semantic.builder import build_semantic_ir
from uasset_read.semantic.projection import project_semantic
from uasset_read.semantic.validator import validate_semantic_document
from uasset_read.semantic.render import render_semantic_json

__all__ = [
    "SemanticIR", "AssetMeta", "AssetStatus", "CoverageInfo",
    "DiagnosticEntry", "EvidenceEntry", "ReferenceEntry",
    "build_semantic_ir", "project_semantic",
    "validate_semantic_document", "render_semantic_json",
]
