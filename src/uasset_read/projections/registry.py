"""Type-aware projection dispatch and deterministic family list (R3).

``project_records()`` runs the whole supplied PackageDocument;
``project_records_with()`` runs one explicit projector tuple. Neither is the
``uasset_read.projection.project_document`` envelope API. Generic object
identity/properties stay in PackageDocument.objects and are never copied into
a generic ``object`` projection.

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
#
# Phase 0 complete contract (plan-asset-semantics.md Appendix A, finalized
# 2026-10-06): ``complete`` = the family's published promised field set is
# fully decoded AND at least one real sample asserts every promised field;
# anything beyond the promised set is disclosed by coverage / projection
# completeness. ``status`` stays tier-honest (#629) while ``completeness``
# carries semantic amount — the two are orthogonal. ``promised_fields`` is
# that declaration, keyed by semantic kind (dotted paths mark nested keys;
# present-only keys are promised when present). Declaration only: it changes
# no output and no behavior.
CAPABILITY_MATRIX: tuple[dict[str, Any], ...] = (
    {
        "family": "blueprint_family",
        "asset_kinds": ["blueprint", "anim_blueprint", "blueprint_function_library", "blueprint_interface"],
        "kinds": [],
        "rule": "no embedded projections; IR/CFG/static semantics stay in objects[].semantic",
        # Placeholder: Topic 1's contract holds this family's promised set.
        "promised_fields": None,
    },
    {
        "family": "material",
        "asset_kinds": ["material"],
        "kinds": [],
        "rule": "no embedded projections; material graph semantics stay in objects[].semantic",
        "promised_fields": {
            # Flags/Editor keys exist only when present; the decode-layer graph
            # keys are asserted only from Phase 2 (decode assertions pending).
            "material": (
                "kind",
                "name",
                "bUsedWithStaticLighting",
                "bUsedWithNanite",
                "bCanMaskedBeAssumedOpaque",
                "EditorX",
                "EditorY",
                "expression_count",
                "material_graph.capability",  # in {complete, partial}
            ),
        },
    },
    {
        "family": "material_instance",
        "asset_kinds": ["material_instance"],
        "kinds": ["material_instance", "material_parameters"],
        "rule": "parent/overrides resolved or explicit unresolved",
        "promised_fields": {
            "material_instance": ("kind", "name", "has_parent", "scalar_param_count", "vector_param_count"),
        },
    },
    {
        "family": "data_table",
        "asset_kinds": ["data_table"],
        "kinds": ["data_table", "data_table_csv", "data_table_json"],
        "rule": "row struct + values decoded, else opaque/unavailable",
        # rows/values are pinned by the projection assertions, not re-listed.
        "promised_fields": {"data_table": ("kind", "row_count", "row_names")},
    },
    {
        "family": "curve_table",
        "asset_kinds": ["curve_table"],
        "kinds": ["curve_table", "curve_table_csv", "curve_table_json"],
        "rule": "keys/interp explicit; compressed-only unavailable unless decoded",
        "promised_fields": {"curve_table": ("kind", "curve_table_mode", "row_count", "row_names")},
    },
    {
        "family": "user_defined_struct_enum",
        "asset_kinds": ["user_defined_struct", "user_defined_enum"],
        "kinds": ["defaults_json"],
        "rule": "fields/enumerators + defaults when reflected data exists",
        # Remaining fields are disclosed via coverage.
        "promised_fields": {
            "user_defined_enum": ("kind", "enum_name"),
            "user_defined_struct": ("kind", "struct_name"),
        },
    },
    {
        "family": "other_graph_assets",
        "asset_kinds": ["graph_asset"],
        "kinds": ["graph"],
        "rule": "graph summary only; never a generated source body",
        "promised_fields": {
            "niagara": ("kind", "niagara_type", "name"),
            "material_function": (
                "kind",
                "name",
                "input_names",
                "output_names",
                "input_count",
                "output_count",
                "expression_count",
                "function_call_count",
            ),
            "material_parameter_collection": (
                "kind",
                "name",
                "scalar_params",
                "scalar_param_count",
                "vector_params",
                "vector_param_count",
            ),
            "anim_blend_space": ("kind", "blend_space_type", "name", "axes", "dimension", "sample_count", "samples"),
            "anim_composite": ("kind", "name", "segment_count", "segments"),
            "anim_layer_interface": ("kind", "name", "function_count", "functions"),
        },
    },
    {
        "family": "physical_binary_assets",
        "asset_kinds": ["physical_asset"],
        "kinds": ["asset_metadata", "payload_reference"],
        "rule": "metadata/payload references unless evidenced projector exists",
        "promised_fields": {
            "texture": ("kind", "texture_type", "srgb", "compression_settings"),
            "texture_mip": ("kind", "source_region", "width", "height"),
            "sound": ("kind", "sound_type"),
            "mesh": ("kind", "mesh_type", "name", "lods", "lod_count"),
            "skeleton": ("kind", "name", "bone_source", "bone_count", "bones", "virtual_bone_count", "socket_count"),
            "physics_asset": ("kind", "name", "body_count", "constraint_count", "bodies"),
            # Float defaults omitted by the editor surface as coverage missing.
            "physical_material": (
                "kind",
                "name",
                "friction",
                "static_friction",
                "restitution",
                "density",
                "surface_type",
            ),
        },
    },
    {
        "family": "string_table",
        "asset_kinds": ["string_table"],
        "kinds": [],
        "rule": "no embedded projections; string-table semantics stay in objects[].semantic",
        "promised_fields": {"string_table": ("kind", "table_type", "namespace", "entry_count", "entries")},
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
        # Graph summary counts only — the other_graph_assets matrix rule is
        # "graph summary only; never a generated source body". Expression-
        # shaped entries (material_function) carry no node counts and stay
        # out of this block (#664).
        if all(isinstance(g, dict) and "node_count" in g for g in graphs):
            content["node_count"] = sum(int(g.get("node_count") or 0) for g in graphs)
            content["pin_count"] = sum(int(g.get("pin_count") or 0) for g in graphs)
            content["edge_count"] = sum(int(g.get("edge_count") or 0) for g in graphs)
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


PROJECTORS: tuple[Any, ...] = (
    MaterialInstanceProjector(),
    DataTableProjector(),
    CurveTableProjector(),
    UserDefinedStructProjector(),
    UserDefinedEnumProjector(),
    PhysicalAssetProjector(),
    GraphAssetProjector(),
)


def project_records_with(
    projectors: tuple[Any, ...], document: PackageDocument, obj: ObjectRecord
) -> list[ProjectionRecord]:
    matches = [projector for projector in projectors if projector.can_project(obj)]
    if len(matches) > 1:
        names = sorted(type(projector).__name__ for projector in matches)
        raise ValueError(f"ambiguous projector ownership for {obj.id}: {names}")
    return [record for projector in matches for record in projector.project(document, obj)]


def project_records(document: PackageDocument) -> list[ProjectionRecord]:
    records = [record for obj in document.objects for record in project_records_with(PROJECTORS, document, obj)]
    return sorted(records, key=lambda item: (item.source_object_id, item.kind, item.media_type))


__all__ = [
    "CAPABILITY_MATRIX",
    "GraphAssetProjector",
    "PhysicalAssetProjector",
    "PROJECTORS",
    "project_records",
    "project_records_with",
]
