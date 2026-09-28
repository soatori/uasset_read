"""Type-aware projection registry and deterministic family dispatch (R3).

Registry ``project_document()`` means all objects of the supplied
PackageDocument. It is not the ``uasset_read.projection.project_document``
envelope API. Generic object identity/properties stay in PackageDocument.objects
and are never copied into a generic ``object`` projection.

Blueprint and material families emit no embedded records: their IR/CFG and
static semantics live under ``objects[].semantic`` (v4). Families with no
registered projector likewise emit nothing.
"""

from __future__ import annotations

from typing import Any

from uasset_read.models.document import PackageDocument
from uasset_read.models.object_model import ObjectRecord
from uasset_read.projections.data_exports import (
    CurveTableProjector,
    DataTableProjector,
    MaterialInstanceProjector,
    UserDefinedEnumProjector,
    UserDefinedStructProjector,
)
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
        "kinds": [],
        "rule": "no embedded projections; IR/CFG/static semantics stay in objects[].semantic",
    },
    {
        "family": "material",
        "asset_kinds": ["material"],
        "kinds": [],
        "rule": "no embedded projections; material graph semantics stay in objects[].semantic",
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
        "kinds": ["defaults_json"],
        "rule": "fields/enumerators + defaults when reflected data exists",
    },
    {
        "family": "other_graph_assets",
        "asset_kinds": ["graph_asset"],
        "kinds": ["graph"],
        "rule": "graph summary only; never a generated source body",
    },
    {
        "family": "physical_binary_assets",
        "asset_kinds": ["physical_asset"],
        "kinds": ["asset_metadata", "payload_reference"],
        "rule": "metadata/payload references unless evidenced projector exists",
    },
)

_GRAPH_PAIRS = (("graph", "application/json"),)


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
    """Other registered graph assets: graph summary only."""

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
        ]


class ProjectorRegistry:
    """Deterministic type-aware projector dispatch."""

    def __init__(self) -> None:
        self._entries: list[Any] = []

    @classmethod
    def default(cls) -> "ProjectorRegistry":
        registry = cls()
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
    "GraphAssetProjector",
    "PhysicalAssetProjector",
    "ProjectorRegistry",
]
