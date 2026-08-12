"""Semantic JSON -- common infrastructure for UAsset semantic output."""
from uasset_read.semantic.models import (
    SemanticIR, AssetMeta, AssetStatus, CoverageInfo,
    DiagnosticEntry, EvidenceEntry, ReferenceEntry,
)
from uasset_read.semantic.builder import build_semantic_ir
from uasset_read.semantic.projection import project_semantic
from uasset_read.semantic.validator import validate_semantic_document
from uasset_read.semantic.render import render_semantic_json

# Register domain extractors
from uasset_read.semantic.extensions import register_extension
from uasset_read.semantic.graph_domain import extract_graph
from uasset_read.semantic.structured_domain import extract_structured
from uasset_read.semantic.resource_domain import extract_resource

# Graph domain: Material, SoundCue, Niagara
for _cls in ("Material", "MaterialInstance", "MaterialInstanceConstant",
             "MaterialInstanceDynamic", "SoundCue",
             "NiagaraSystem", "NiagaraEmitter", "NiagaraScript"):
    register_extension(_cls, extract_graph)

# Structured domain: StaticMesh, SkeletalMesh, Skeleton, Animation, DataTable
for _cls in ("StaticMesh", "SkeletalMesh", "Skeleton",
             "AnimSequence", "AnimMontage",
             "DataTable", "CurveTable"):
    register_extension(_cls, extract_structured)

# Resource domain: Texture, SoundWave
for _cls in ("Texture2D", "TextureCube", "SoundWave"):
    register_extension(_cls, extract_resource)

__all__ = [
    "SemanticIR", "AssetMeta", "AssetStatus", "CoverageInfo",
    "DiagnosticEntry", "EvidenceEntry", "ReferenceEntry",
    "build_semantic_ir", "project_semantic",
    "validate_semantic_document", "render_semantic_json",
]
