"""Semantic IR builder — the single semantic-projection boundary.

Orchestrates: main-asset selection, reference normalization, coverage/diagnostics.
Does NOT perform standard/debug projection (that is project_semantic's job).
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import TYPE_CHECKING

from uasset_read.semantic.models import (
    SemanticIR,
    AssetMeta,
    AssetStatus,
    EvidenceEntry,
)
from uasset_read.semantic.references import collect_references
from uasset_read.semantic.coverage import CoverageModel
from uasset_read.semantic.diagnostics import DiagnosticAggregator
from uasset_read.semantic.extensions import get_extractor, get_domain_format

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR, ExportIR


_TYPE_MAP: dict[str, str] = {
    # Material
    "Material": "material",
    "MaterialInstance": "material",
    "MaterialInstanceConstant": "material",
    "MaterialInstanceDynamic": "material",
    "MaterialFunction": "material_function",
    "MaterialParameterCollection": "material_parameter_collection",
    # Sound
    "SoundCue": "sound_cue",
    "SoundWave": "sound_wave",
    "SoundAttenuation": "sound_attenuation",
    "SoundConcurrency": "sound_concurrency",
    "ReverbEffect": "reverb_effect",
    "DialogueWave": "dialogue_wave",
    "DialogueVoice": "dialogue_voice",
    # Niagara
    "NiagaraSystem": "niagara_system",
    "NiagaraEmitter": "niagara_emitter",
    "NiagaraScript": "niagara_script",
    # Mesh
    "StaticMesh": "static_mesh",
    "SkeletalMesh": "skeletal_mesh",
    "Skeleton": "skeleton",
    "SkeletalMeshLODSettings": "skeletal_mesh_lod_settings",
    # Animation
    "AnimSequence": "anim_sequence",
    "AnimMontage": "anim_montage",
    "PoseAsset": "pose_asset",
    "AnimCurveCompressionSettings": "anim_curve_compression_settings",
    "AnimCurveCompressionCodec": "anim_curve_compression_codec",
    "AnimBoneCompressionSettings": "anim_bone_compression_settings",
    "AnimationDataModel": "anim_data_model",
    "AnimComposite": "anim_composite",
    "AnimBlendSpace": "anim_blend_space",
    "AnimBlendSpace1D": "anim_blend_space",
    "AimOffsetBlendSpace": "anim_blend_space",
    "AimOffsetBlendSpace1D": "anim_blend_space",
    # Data
    "DataTable": "data_table",
    "CurveTable": "curve_table",
    "StringTable": "string_table",
    # Texture
    "Texture2D": "texture",
    "TextureCube": "texture",
    "TextureRenderTarget2D": "texture",
    "TextureRenderTargetCube": "texture",
    # Blueprint
    "BlueprintGeneratedClass": "blueprint",
    "AnimBlueprintGeneratedClass": "anim_blueprint",
    "Blueprint": "blueprint",
    "AnimBlueprint": "anim_blueprint",
    # User-defined data types
    "UserDefinedEnum": "enum",
    "UserDefinedStruct": "struct",
    # Rendering configuration
    "SubsurfaceProfile": "subsurface_profile",
    # Curves
    "CurveFloat": "curve",
    "CurveLinearColor": "curve",
    "CurveVector": "curve",
    # Foliage
    "FoliageType_InstancedStaticMesh": "foliage_type",
    "FoliageType": "foliage_type",
    # Builder
    "CubeBuilder": "cube_builder",
    # Physics
    "PhysicsAsset": "physics_asset",
    "PhysicalMaterial": "physical_material",
    # Animation (extended)
    "AnimLayerInterface": "anim_layer_interface",
    # Sound (extended)
    "SoundMix": "sound_mix",
    "SoundClass": "sound_class",
    "SoundSubmix": "sound_submix",
    # AI
    "BehaviorTree": "behavior_tree",
    "BlackboardData": "blackboard_data",
    # Data assets
    "DataAsset": "data_asset",
    "PrimaryDataAsset": "primary_data_asset",
    # Landscape
    "Landscape": "landscape",
    "LandscapeGrassType": "landscape_grass_type",
    "LandscapeLayerInfoObject": "landscape_layer_info",
    # World
    "World": "world",
    "Level": "level",
    # Particles
    "ParticleSystem": "particle_system",
    # UI
    "WidgetBlueprintGeneratedClass": "widget_blueprint",
    "WidgetBlueprint": "widget_blueprint",
    # Texture (extended)
    "Texture2DArray": "texture",
    "VolumeTexture": "texture",
    # Media
    "MediaPlayer": "media_player",
    "MediaTexture": "media_texture",
    "MediaSource": "media_source",
    # Cloth and Hair
    "ClothAsset": "cloth_asset",
    "GroomAsset": "groom_asset",
    # Sparse Volume Texture
    "SparseVolumeTexture": "sparse_volume_texture",
    # Movie / Sequencer
    "MovieScene": "movie_scene",
    "LevelSequence": "level_sequence",
    "MovieSceneControlRigParameterTrack": "movie_scene",
    "MovieSceneControlRigParameterSection": "movie_scene",
}


def resolve_asset_type(export_class: str) -> str:
    """Resolve a UE class name to a normalized semantic type string."""
    if not export_class:
        return "unknown"
    return _TYPE_MAP.get(export_class, "unknown")


_PARSE_RANK = {"complete": 0, "partial": 1, "failed": 2}


def _worst_parse(a: str, b: str) -> str:
    """Return the more severe parse status (failed > partial > complete)."""
    return a if _PARSE_RANK.get(a, 1) >= _PARSE_RANK.get(b, 1) else b


def _extractor_accepts_mode(extractor) -> bool:
    """Check if a domain extractor function accepts a 'mode' keyword parameter."""
    if extractor is None:
        return False
    try:
        sig = inspect.signature(extractor)
        return "mode" in sig.parameters
    except (ValueError, TypeError):
        return False


def _combine_package_status(export_parse: str, diagnostics_data) -> str:
    """Combine export-level and package-level parse status.

    Priority: failed > partial > complete. Package-level errors or a
    non-success package status must never be reported as "complete", even
    when the primary export itself parsed successfully.
    """
    if export_parse == "failed":
        return "failed"
    if diagnostics_data is None:
        return export_parse
    pkg_status = diagnostics_data.status or "success"
    if pkg_status == "failed":
        return "failed"
    if pkg_status != "success" or diagnostics_data.errors:
        return _worst_parse(export_parse, "partial")
    return export_parse


def _resolve_package_name(package_ir: PackageIR, source_path: str | None) -> str:
    """Resolve a non-empty asset package path.

    Prefers the parsed package name. When it is missing, derives one from the
    source file so fallback documents remain schema-valid (``asset.package``
    requires minLength 1); otherwise falls back to a stable sentinel.
    """
    name = package_ir.header.package_name or ""
    if name:
        return name
    if source_path:
        stem = Path(source_path).stem
        if stem:
            return "/" + stem
    return "/Unknown"


def _select_primary_export(package_ir: PackageIR) -> tuple[ExportIR | None, str]:
    """Select the primary export using deterministic rules.

    Returns ``(export, rule)`` where ``rule`` is ``"b_is_asset"``,
    ``"basename_match"``, or ``"none"`` (export is None).

    1. Prefer the single export marked with ``b_is_asset``.
    2. Fallback: single top-level export whose name matches package basename.
    3. Otherwise: ``(None, "none")`` (opaque/partial).

    Do NOT guess when there are multiple candidates, no candidates,
    or insufficient evidence.  Nested exports (those with a non-None
    ``outer_index_resolved``) are never considered primary.
    """
    # Rule 1: b_is_asset (only top-level)
    candidates = [
        e
        for e in package_ir.exports
        if getattr(e, "b_is_asset", False) and not getattr(e, "outer_index_resolved", None)
    ]
    if len(candidates) == 1:
        return candidates[0], "b_is_asset"

    # Rule 2: name matches package basename (only top-level)
    basename = package_ir.header.package_name.rsplit("/", 1)[-1] if package_ir.header.package_name else ""
    if basename:
        name_matches = [
            e for e in package_ir.exports if e.object_name == basename and not getattr(e, "outer_index_resolved", None)
        ]
        if len(name_matches) == 1:
            return name_matches[0], "basename_match"

    return None, "none"


def build_semantic_ir(package_ir: PackageIR, source_path: str | None = None, *, mode: str = "standard") -> SemanticIR:
    """Build a mode-independent SemanticIR from PackageIR.

    This is the single semantic-projection boundary. It does NOT perform
    standard/debug pruning — use ``project_semantic()`` for that.
    The returned IR always has ``mode="standard"`` as a placeholder;
    ``project_semantic()`` stamps the actual target mode.

    Args:
        package_ir: PackageIR from ir_builder
        source_path: Optional path of the parsed file, used to derive a stable
            package identity when the header has none.
        mode: Build mode — "standard" or "debug". Passed to domain extractors
            that accept it, enabling debug evidence generation before projection.

    Returns:
        SemanticIR ready for projection and rendering
    """
    diag = DiagnosticAggregator()
    if package_ir.diagnostics_data:
        diag.from_ir(package_ir.diagnostics_data)

    primary, selection_rule = _select_primary_export(package_ir)

    if primary is None:
        diag.add("warning", "NO_EXPORTS", "No suitable primary export found")
        return SemanticIR(
            format="uasset_read.asset_semantic",
            format_version="1.0",
            mode="",
            asset_type="unknown",
            asset=AssetMeta(package=_resolve_package_name(package_ir, source_path), name="unknown"),
            status=AssetStatus(parse="failed", representation="opaque"),
            references=collect_references(package_ir.imports, package_ir.exports),
            diagnostics=diag.build(),
            evidence=(EvidenceEntry(key="primary_selection_rule", value="none"),),
        )

    # Resolve asset type
    asset_type = resolve_asset_type(primary.object_class or "")

    # Build status (export-level mapping, then package-level combination)
    parse_status = primary.parse_status or "success"
    parse_map = {
        "success": "complete",
        "partial": "partial",
        "partial_metadata": "partial",
        "failed": "failed",
        "opaque": "partial",
    }
    representation_map = {
        "success": "full",
        "partial": "partial",
        "partial_metadata": "partial",
        "failed": "opaque",
        "opaque": "opaque",
    }
    export_parse = parse_map.get(parse_status, "partial")
    parse = _combine_package_status(export_parse, package_ir.diagnostics_data)

    # Common-layer evidence contract: explain primary selection and parse outcome.
    # Standard projection strips it; debug keeps it.
    evidence: list = [
        EvidenceEntry(key="primary_export_index", value=primary.index),
        EvidenceEntry(key="primary_selection_rule", value=selection_rule),
        EvidenceEntry(key="original_class", value=primary.object_class or ""),
        EvidenceEntry(key="export_parse_status", value=primary.parse_status or "success"),
    ]
    if primary.fallback_reason:
        evidence.append(EvidenceEntry(key="fallback_reason", value=primary.fallback_reason))

    # Unknown type -> opaque representation + evidence with raw class
    if asset_type == "unknown":
        representation = "opaque"
        diag.add("info", "UNKNOWN_TYPE", f"Unresolved asset type for class '{primary.object_class}'")
        # Preserve exact UE class in evidence when normalized type is insufficient
        evidence.append(EvidenceEntry(key="asset_class", value=primary.object_class or ""))
    else:
        representation = representation_map.get(parse_status, "opaque")

    extractor = get_extractor(primary.object_class or "")
    domain_format = get_domain_format(primary.object_class or "")

    # Known type but no registered extractor -> opaque (not full)
    if asset_type != "unknown" and extractor is None:
        representation = "opaque"
        diag.add("info", "NO_EXTRACTOR", f"No semantic extractor registered for class '{primary.object_class}'")

    status = AssetStatus(parse=parse, representation=representation)

    if status.parse == "partial" and not any(d.code == "PARTIAL_PARSE" for d in diag.build()):
        diag.add("warning", "PARTIAL_PARSE", f"Asset '{primary.object_name}' was only partially parsed")
    elif status.parse == "failed" and not any(d.code == "PARSE_FAILED" for d in diag.build()):
        diag.add("error", "PARSE_FAILED", f"Asset '{primary.object_name}' failed to parse")

    cov = CoverageModel()
    content: dict = {}
    evidence_list: list = list(evidence)

    # Check if extractor accepts 'mode' parameter
    _pass_mode = _extractor_accepts_mode(extractor)

    _extractor_ran = False
    if extractor is not None and status.representation != "opaque":
        if _pass_mode:
            content = extractor(package_ir, primary, cov, evidence_list, mode=mode)
        else:
            content = extractor(package_ir, primary, cov, evidence_list)
        _extractor_ran = True
    elif extractor is not None and asset_type == "material" and getattr(package_ir, "material", None) is not None:
        # Material data is built by _build_material_ir in ir_builder, not from export parsing
        # Call the extractor even when the export is opaque
        content = extractor(package_ir, primary, cov, evidence_list)
        _extractor_ran = True
        # Override representation to full since we have material data
        representation = "full"
        status = AssetStatus(parse=parse, representation="full")
    elif extractor is None:
        # No extractor registered — domain_content is genuinely unavailable
        cov.track("domain_content", False)
    # When _extractor_ran but content is empty, the extractor had nothing to
    # contribute.  Do NOT track domain_content as unavailable (it was never
    # available) to avoid a coverage/representation mismatch.
    _domain_content_empty = not content

    # Domain formats own coverage inside content; references and diagnostics
    # are always provided by the envelope so domain extractors need not
    # hardcode empty values.
    owns_envelope_sections = (
        domain_format is not None and status.representation != "opaque" and not _domain_content_empty
    )
    if owns_envelope_sections and content.get("coverage"):
        # Any reported coverage entry means some scope is not complete:
        # representation cannot be "full" (honest status contract).
        representation = "partial"
        status = AssetStatus(parse=parse, representation="partial")
    coverage = None if owns_envelope_sections else cov.build()
    # Merge domain extractor diagnostics into the envelope diagnostics
    for d in content.get("diagnostics", []):
        if isinstance(d, dict):
            diag.add(d.get("severity", "warning"), d.get("code", "UNKNOWN"), d.get("message", ""))
        else:
            diag.add(getattr(d, "severity", "warning"), getattr(d, "code", "UNKNOWN"), getattr(d, "message", ""))
    diagnostics = diag.build()
    references = collect_references(package_ir.imports, package_ir.exports)

    fmt, fmt_version = "uasset_read.asset_semantic", "1.0"
    if owns_envelope_sections:
        fmt, fmt_version = domain_format
    elif _extractor_ran and _domain_content_empty and domain_format is not None:
        # Extractor ran but produced nothing — downgrade to partial
        representation = "partial"
        status = AssetStatus(parse=parse, representation="partial")

    return SemanticIR(
        format=fmt,
        format_version=fmt_version,
        mode="",
        asset_type=asset_type,
        asset=AssetMeta(
            package=_resolve_package_name(package_ir, source_path),
            name=primary.object_name or "unknown",
            generated_class=primary.object_class if asset_type == "unknown" else None,
        ),
        status=status,
        references=references,
        content=content,
        coverage=coverage,
        diagnostics=diagnostics,
        evidence=tuple(evidence_list),
    )
