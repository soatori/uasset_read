"""Type-aware projection registry and deterministic family dispatch (R3).

Registry ``project_document()`` means all objects of the supplied
PackageDocument. It is not the bounded ``uasset_read.projection.project_document``
response API. Generic object identity/properties stay in PackageDocument.objects
and are never copied into a generic ``object`` projection.
"""

from __future__ import annotations

from typing import Any

from uasset_read.models.diagnostics import make_diagnostic
from uasset_read.models.document import PackageDocument
from uasset_read.models.object_model import ObjectRecord
from uasset_read.projections.cpp_render import CppProjection, render_cpp
from uasset_read.projections.data_exports import (
    CurveTableProjector,
    DataTableProjector,
    MaterialInstanceProjector,
    UserDefinedEnumProjector,
    UserDefinedStructProjector,
)
from uasset_read.projections.material_builder import MaterialEditorBuilderProjector
from uasset_read.projections.records import (
    ProjectionRecord,
    dependency_ids,
    matches_family,
    semantic_dict,
    unavailable_records,
)

# Capability matrix published on the canonical document (R3 initial matrix).
CAPABILITY_MATRIX: tuple[dict[str, Any], ...] = (
    {
        "family": "blueprint_family",
        "asset_kinds": ["blueprint", "anim_blueprint", "blueprint_function_library", "blueprint_interface"],
        "kinds": ["cpp_declaration", "cpp_migration"],
        "rule": "from R2 render_cpp; full trace remains in objects[].semantic",
    },
    {
        "family": "material",
        "asset_kinds": ["material"],
        "kinds": ["material_editor_builder"],
        "rule": "represented when editor graph exists, else unavailable + diagnostic",
    },
    {
        "family": "material_instance",
        "asset_kinds": ["material_instance"],
        "kinds": ["material_instance", "material_parameters"],
        "rule": "parent/overrides resolved or explicit unresolved",
    },
    {
        "family": "data_table",
        "asset_kinds": ["data_table"],
        "kinds": ["data_table", "data_table_csv", "data_table_json"],
        "rule": "row struct + values decoded, else opaque/unavailable",
    },
    {
        "family": "curve_table",
        "asset_kinds": ["curve_table"],
        "kinds": ["curve_table", "curve_table_csv", "curve_table_json"],
        "rule": "keys/interp explicit; compressed-only unavailable unless decoded",
    },
    {
        "family": "user_defined_struct_enum",
        "asset_kinds": ["user_defined_struct", "user_defined_enum"],
        "kinds": ["cpp_declaration", "defaults_json"],
        "rule": "fields/enumerators + defaults when reflected data exists",
    },
    {
        "family": "other_graph_assets",
        "asset_kinds": ["graph_asset"],
        "kinds": ["graph", "asset_builder_cpp"],
        "rule": "no generic fake C++ body",
    },
    {
        "family": "physical_binary_assets",
        "asset_kinds": ["physical_asset"],
        "kinds": ["asset_metadata", "payload_reference"],
        "rule": "metadata/payload references unless evidenced projector exists",
    },
)

_BLUEPRINT_KINDS = (
    "blueprint",
    "anim_blueprint",
    "blueprint_function_library",
    "blueprint_interface",
)
_BLUEPRINT_PAIRS = (
    ("cpp_declaration", "text/x-c++hdr"),
    ("cpp_migration", "text/x-c++src"),
)
_PHYSICAL_PAIRS = (
    ("asset_metadata", "application/json"),
    ("payload_reference", "application/json"),
)
_GRAPH_PAIRS = (
    ("graph", "application/json"),
    ("asset_builder_cpp", "text/x-c++src"),
)


def _status_from_stats(stats: dict[str, int], *, mode: str) -> str:
    declarations = int(stats.get("declarations") or 0)
    seen = int(stats.get("instructions_seen") or 0)
    translated = int(stats.get("translated") or 0)
    represented = int(stats.get("represented") or 0)
    untranslated = int(stats.get("untranslated") or 0)
    unavailable = int(stats.get("unavailable") or 0)
    if mode == "declaration":
        return "translated" if declarations > 0 else "unavailable"
    if seen <= 0:
        return "translated" if declarations > 0 else "unavailable"
    if untranslated > 0 or unavailable > 0:
        return "represented" if (translated + represented) > 0 else "untranslated"
    if translated > 0:
        return "translated"
    if represented > 0:
        return "represented"
    return "unavailable"


def _completeness(stats: dict[str, int], *, mode: str) -> float | None:
    declarations = int(stats.get("declarations") or 0)
    seen = int(stats.get("instructions_seen") or 0)
    if mode == "declaration":
        return 1.0 if declarations > 0 else None
    if seen <= 0:
        return None
    mapped = int(stats.get("translated") or 0) + int(stats.get("represented") or 0)
    return mapped / seen


def _unavailable_blueprint_projections(
    document: PackageDocument,
    object_id: str,
    reason: str,
) -> list[ProjectionRecord]:
    return unavailable_records(
        object_id,
        _BLUEPRINT_PAIRS,
        code=reason,
        message="Blueprint semantic input is unavailable",
        stage="projection.blueprint",
        dependencies=dependency_ids(document, object_id),
    )


def _projection_record_from_cpp(
    *,
    kind: str,
    object_id: str,
    media_type: str,
    mode: str,
    result: CppProjection,
    dependencies: list[str],
) -> ProjectionRecord:
    return ProjectionRecord(
        kind=kind,
        source_object_id=object_id,
        media_type=media_type,
        content=result.header_text if mode == "declaration" else result.source_text,
        embedded=True,
        status=_status_from_stats(result.translation_stats, mode=mode),
        completeness=_completeness(result.translation_stats, mode=mode),
        dependencies=dependencies,
        diagnostics=list(result.diagnostics),
    )


class BlueprintCppProjector:
    """Blueprint family: cpp_declaration + cpp_migration via R2 render_cpp."""

    asset_kinds = _BLUEPRINT_KINDS

    _CLASS_NAMES = frozenset(
        {
            "Blueprint",
            "AnimBlueprint",
            "BlueprintGeneratedClass",
            "AnimBlueprintGeneratedClass",
            "BlueprintFunctionLibrary",
            "BlueprintInterface",
        }
    )

    def can_project(self, obj: ObjectRecord) -> bool:
        return matches_family(obj, self.asset_kinds, self._CLASS_NAMES)

    def project(self, document: PackageDocument, obj: ObjectRecord) -> list[ProjectionRecord]:
        semantic = obj.semantic
        dependencies = dependency_ids(document, obj.id)
        # Unproven family kinds without a projected semantic stay explicit unavailable.
        if (obj.class_name or "") in ("BlueprintFunctionLibrary", "BlueprintInterface") and (
            not isinstance(semantic, dict)
            or not (isinstance(semantic.get("kind"), str) and semantic.get("kind"))
        ):
            return _unavailable_blueprint_projections(
                document, obj.id, "blueprint_family_semantic_unavailable"
            )
        if not isinstance(semantic, dict) or semantic.get("kind") not in self.asset_kinds:
            return _unavailable_blueprint_projections(
                document, obj.id, "blueprint_semantic_unavailable"
            )
        try:
            decl = render_cpp(semantic, mode="declaration")
            mig = render_cpp(semantic, mode="migration")
        except Exception:
            return unavailable_records(
                obj.id,
                _BLUEPRINT_PAIRS,
                code="blueprint_render_failed",
                message="Blueprint C++ projection failed for projected semantic dict",
                stage="projection.blueprint",
                dependencies=dependencies,
            )
        return [
            _projection_record_from_cpp(
                kind="cpp_declaration",
                object_id=obj.id,
                media_type="text/x-c++hdr",
                mode="declaration",
                result=decl,
                dependencies=dependencies,
            ),
            _projection_record_from_cpp(
                kind="cpp_migration",
                object_id=obj.id,
                media_type="text/x-c++src",
                mode="migration",
                result=mig,
                dependencies=dependencies,
            ),
        ]


class PhysicalAssetProjector:
    """Physical/binary assets: metadata + payload references only (no invented payloads)."""

    # Includes handler semantic kinds so kind-first dispatch stays single-owner.
    asset_kinds = (
        "physical_asset",
        "texture",
        "texture_mip",
        "sound",
        "mesh",
        "skeleton",
        "physics_asset",
        "physical_material",
    )
    _CLASS_NAMES = frozenset(
        {
            "Texture2D",
            "TextureCube",
            "StaticMesh",
            "SkeletalMesh",
            "SoundWave",
        }
    )

    def can_project(self, obj: ObjectRecord) -> bool:
        return matches_family(obj, self.asset_kinds, self._CLASS_NAMES)

    def project(self, document: PackageDocument, obj: ObjectRecord) -> list[ProjectionRecord]:
        dependencies = dependency_ids(document, obj.id)
        semantic = semantic_dict(obj)
        metadata = {
            "kind": "asset_metadata",
            "object_id": obj.id,
            "name": obj.name,
            "class_name": obj.class_name,
            "roles": list(obj.roles),
            "semantic_kind": semantic.get("kind"),
        }
        payload_ref = None
        if obj.serial_region is not None and obj.serial_region.payload_ref:
            payload_ref = obj.serial_region.payload_ref
        records = [
            ProjectionRecord(
                kind="asset_metadata",
                source_object_id=obj.id,
                media_type="application/json",
                content=metadata,
                embedded=True,
                status="represented",
                completeness=None,
                dependencies=dependencies,
                diagnostics=[],
            )
        ]
        if payload_ref is None:
            records.extend(
                unavailable_records(
                    obj.id,
                    (("payload_reference", "application/json"),),
                    code="payload_reference_unavailable",
                    message="No evidenced payload descriptor on the export serial region",
                    stage="projection.physical_asset",
                    dependencies=dependencies,
                )
            )
        else:
            records.append(
                ProjectionRecord(
                    kind="payload_reference",
                    source_object_id=obj.id,
                    media_type="application/json",
                    content={"kind": "payload_reference", "payload_ref": payload_ref},
                    embedded=True,
                    status="represented",
                    completeness=None,
                    dependencies=dependencies,
                    diagnostics=[],
                )
            )
        return records


class GraphAssetProjector:
    """Other registered graph assets: graph summary only; never a fake C++ body."""

    asset_kinds = (
        "graph_asset",
        "niagara",
        "material_function",
        "material_parameter_collection",
        "anim_blend_space",
        "anim_composite",
        "anim_layer_interface",
    )
    _CLASS_NAMES = frozenset(
        {
            "NiagaraSystem",
            "NiagaraEmitter",
            "MaterialFunction",
            "MaterialParameterCollection",
            "AnimComposite",
            "BlendSpace",
        }
    )

    def can_project(self, obj: ObjectRecord) -> bool:
        return matches_family(obj, self.asset_kinds, self._CLASS_NAMES)

    def project(self, document: PackageDocument, obj: ObjectRecord) -> list[ProjectionRecord]:
        dependencies = dependency_ids(document, obj.id)
        semantic = semantic_dict(obj)
        graphs = semantic.get("graphs") or semantic.get("expressions")
        if not graphs:
            return unavailable_records(
                obj.id,
                _GRAPH_PAIRS,
                code="graph_semantic_unavailable",
                message="Graph-asset semantic graph data is unavailable",
                stage="projection.graph_asset",
                dependencies=dependencies,
            )
        content = {
            "kind": "graph",
            "object_id": obj.id,
            "name": obj.name,
            "semantic_kind": semantic.get("kind"),
            "entry_count": len(graphs),
        }
        return [
            ProjectionRecord(
                kind="graph",
                source_object_id=obj.id,
                media_type="application/json",
                content=content,
                embedded=True,
                status="represented",
                completeness=None,
                dependencies=dependencies,
                diagnostics=[],
            ),
            ProjectionRecord(
                kind="asset_builder_cpp",
                source_object_id=obj.id,
                media_type="text/x-c++src",
                content=None,
                embedded=True,
                status="unavailable",
                completeness=None,
                dependencies=dependencies,
                diagnostics=[
                    make_diagnostic(
                        "asset_builder_cpp_unavailable",
                        "No evidenced asset-builder C++ projector for this graph asset family",
                        "projection.graph_asset",
                        object_id=obj.id,
                    )
                ],
            ),
        ]


class ProjectorRegistry:
    """Deterministic type-aware projector dispatch."""

    def __init__(self) -> None:
        self._entries: list[Any] = []

    @classmethod
    def default(cls) -> "ProjectorRegistry":
        registry = cls()
        registry.register(BlueprintCppProjector())
        registry.register(MaterialEditorBuilderProjector())
        registry.register(MaterialInstanceProjector())
        registry.register(DataTableProjector())
        registry.register(CurveTableProjector())
        registry.register(UserDefinedStructProjector())
        registry.register(UserDefinedEnumProjector())
        registry.register(PhysicalAssetProjector())
        registry.register(GraphAssetProjector())
        return registry

    def register(self, projector: Any) -> None:
        self._entries.append(projector)

    def _owners(self, obj: ObjectRecord) -> list[Any]:
        matches = [projector for projector in self._entries if projector.can_project(obj)]
        if len(matches) > 1:
            names = sorted(type(projector).__name__ for projector in matches)
            raise ValueError(f"ambiguous projector ownership for {obj.id}: {names}")
        return matches

    def project_object(self, document: PackageDocument, object_id: str) -> list[ProjectionRecord]:
        obj = next((item for item in document.objects if item.id == object_id), None)
        if obj is None:
            return []
        records: list[ProjectionRecord] = []
        for projector in self._owners(obj):
            records.extend(projector.project(document, obj))
        records.sort(key=lambda item: (item.source_object_id, item.kind, item.media_type))
        return records

    def project_document(self, document: PackageDocument) -> list[ProjectionRecord]:
        records: list[ProjectionRecord] = []
        for obj in document.objects:
            records.extend(self.project_object(document, obj.id))
        records.sort(key=lambda item: (item.source_object_id, item.kind, item.media_type))
        return records


__all__ = [
    "CAPABILITY_MATRIX",
    "BlueprintCppProjector",
    "GraphAssetProjector",
    "PhysicalAssetProjector",
    "ProjectorRegistry",
]
