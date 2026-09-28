"""Projection — the sole v4 package-output producer.

``project_document()`` turns a full ``depth="decode"`` PackageDocument into the
``uasset_read.package`` / ``format_version "4.0"`` envelope in exactly one of
the modes ``normal`` or ``debug``. ``debug`` is ``normal`` plus the evidence
block; stripping it and normalizing ``mode`` reproduces ``normal`` exactly.
"""

from __future__ import annotations

from typing import Any, Literal

from .models.byte_ranges import project_region
from .models.diagnostics import Diagnostic, diagnostic_detail, diagnostic_summary
from .models.document import PackageDocument
from .models.object_model import Dependency, ObjectRecord

# Envelope schema major for project_document() output. Deliberately lives on
# the projection layer: PackageDocument stays a package-level aggregate with
# no presentation-version state (v4 contract freeze).
FORMAT_VERSION = "4.0"

_VALID_MODES = ("normal", "debug")

# Contract-banned evidence keys (SemanticValue.propertyNames): physical
# evidence never rides common semantic output in either mode. Removed
# region-shaped values are re-emitted as debug.semantic_source_ranges; other
# evidence values (e.g. raw_data) are dropped here — property tag/value regions
# and raw fallback bytes live in debug.property_evidence instead.
_BANNED_SEMANTIC_EVIDENCE_KEYS = frozenset(
    {"source_range", "script_source_range", "raw_region", "tag_range", "value_range", "raw_data"}
)


def _pointer_token(key: str) -> str:
    """JSON Pointer escape for one path token (RFC 6901)."""
    return key.replace("~", "~0").replace("/", "~1")


def _sanitize_semantic(
    value: Any,
    object_id: str,
    pointer: str,
    entries: list[dict[str, Any]],
) -> Any:
    """Copy one semantic value without banned evidence keys.

    ``pointer`` is relative to the object's semantic value. A region-shaped
    dict under a banned key becomes a ``debug.semantic_source_ranges`` entry
    at that pointer; any other value under a banned key is dropped.
    """
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            child = f"{pointer}/{_pointer_token(str(key))}"
            if key in _BANNED_SEMANTIC_EVIDENCE_KEYS:
                if isinstance(item, dict):
                    entries.append({"object_id": object_id, "json_pointer": child, "region": item})
                continue
            out[key] = _sanitize_semantic(item, object_id, child, entries)
        return out
    if isinstance(value, list):
        return [
            _sanitize_semantic(item, object_id, f"{pointer}/{index}", entries) for index, item in enumerate(value)
        ]
    return value


def build_projection_records(
    document: PackageDocument,
    *,
    registry: Any | None = None,
) -> list[Any]:
    """Create embedded type-aware projection records for a PackageDocument.

    Sole API that produces type-specific embedded content. Unknown families
    emit no records.
    """
    from uasset_read.projections.registry import ProjectorRegistry

    active = registry if registry is not None else ProjectorRegistry.default()
    return active.project_document(document)


def dependency_to_dict(dep: Dependency) -> dict[str, Any]:
    """Serialize one import-dependency entry (#632).

    Shared by the projection envelope and the agent tools so no caller drops
    ``package_name``, which the model carries since the import map.
    """
    return {
        "index": dep.index,
        "class": dep.class_name,
        "object_name": dep.object_name,
        "package_name": dep.package_name,
    }


def _require_full_decode(document: PackageDocument) -> None:
    """v4 precondition: a decode document containing all exports."""
    if document.depth != "decode":
        raise ValueError(
            f"v4 output requires a full depth='decode' document; got depth={document.depth!r}"
        )
    missing = [obj.id for obj in document.objects if obj.properties is None]
    if missing:
        raise ValueError(
            f"v4 output requires all exports to be decoded; {len(missing)} export(s) have no properties "
            f"(first: {missing[0]})"
        )


def _property_entries(obj: ObjectRecord) -> list[dict[str, Any]]:
    """Ordered property occurrences with per-name occurrence numbers."""
    from uasset_read.models.properties import project_property_bag

    if obj.properties is None:
        return []
    return project_property_bag(obj.properties)


# Raw fallback bytes stay debug evidence only, capped so evidence stays bounded.
_RAW_EVIDENCE_CAP = 256


def _raw_evidence(data: bytes) -> dict[str, Any]:
    truncated = len(data) > _RAW_EVIDENCE_CAP
    return {
        "encoding": "hex",
        "data": data[:_RAW_EVIDENCE_CAP].hex(),
        "total_size": len(data),
        "truncated": truncated,
    }


def _entry_raw_bytes(value: Any) -> bytes | None:
    """Top-level raw bytes a property entry still carries, if any."""
    from uasset_read.models.fallback import PropertyFallback, StructFallback
    from uasset_read.models.properties import PropertyValue

    if isinstance(value, PropertyValue) and not isinstance(value, PropertyFallback):
        value = value.value
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if isinstance(value, StructFallback) and value.raw_bytes:
        return bytes(value.raw_bytes)
    return None


def _property_evidence(document: PackageDocument) -> list[dict[str, Any]]:
    """Debug-only per-property evidence; every region goes through project_region()."""
    out: list[dict[str, Any]] = []
    for obj in document.objects:
        if obj.properties is None:
            continue
        for index, entry in enumerate(obj.properties.entries):
            item: dict[str, Any] = {"object_id": obj.id, "property_index": index}
            has_evidence = False
            if entry.tag_region is not None:
                item["tag_region"] = project_region(entry.tag_region)
                has_evidence = True
            if entry.value_region is not None:
                item["value_region"] = project_region(entry.value_region)
                has_evidence = True
            raw = _entry_raw_bytes(entry.value)
            if raw is not None:
                item["raw"] = _raw_evidence(raw)
                has_evidence = True
            if has_evidence:
                out.append(item)
    return out


def obj_to_dict(obj: ObjectRecord, evidence_out: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Serialize one ObjectRecord to the v4 ObjectEntry shape.

    The semantic copy never carries contract-banned evidence keys; when
    ``evidence_out`` is given, removed region values are appended to it as
    ``debug.semantic_source_ranges`` candidates.
    """
    d: dict[str, Any] = {
        "id": obj.id,
        "table_index": obj.table_index,
        "name": obj.name,
        "class": obj.class_name,
        "roles": list(obj.roles),
        "status": {"parse": obj.status.parse, "semantic": obj.status.semantic},
        "properties": _property_entries(obj),
    }
    if obj.semantic is not None:
        entries: list[dict[str, Any]] = []
        d["semantic"] = _sanitize_semantic(obj.semantic, obj.id, "", entries)
        if evidence_out is not None:
            evidence_out.extend(entries)
    if obj.coverage:
        d["coverage"] = [
            {"feature": c.feature, "status": c.status, **({"detail": c.detail} if c.detail else {})}
            for c in obj.coverage
        ]
    return d


def _package_to_dict(doc: PackageDocument) -> dict[str, Any]:
    assert doc.package is not None
    package = doc.package
    out: dict[str, Any] = {
        "name": package.name,
        "layout": package.layout,
        "package_flags": package.package_flags,
    }
    if package.engine_version is not None:
        out["engine_version"] = package.engine_version
    if package.compatible_engine_version is not None:
        out["compatible_engine_version"] = package.compatible_engine_version
    if package.total_header_size is not None:
        out["total_header_size"] = package.total_header_size
    if package.export_count is not None:
        out["export_count"] = package.export_count
    if package.import_count is not None:
        out["import_count"] = package.import_count
    if package.name_count is not None:
        out["name_count"] = package.name_count
    return out


def _all_diagnostics(doc: PackageDocument) -> list[Diagnostic]:
    return list(doc.diagnostics) + list(doc.reader_diagnostics)


def _payload_descriptors(document: PackageDocument) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Common payload descriptors plus their debug source evidence.

    Payload bytes stay referenced; ``source_region``/``offset`` are debug
    evidence only.
    """
    payloads: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    for obj in document.objects:
        if not obj.id.startswith("export:"):
            continue
        region = obj.serial_region
        if region is None or region.size <= 0 or not region.source_slices:
            continue
        physical = region.source_slices[0]
        payload_id = region.payload_ref or f"payload:{obj.id}"
        payloads.append(
            {
                "id": payload_id,
                "owner": obj.id,
                "kind": "other",
                "stored_size": physical.size,
                "status": "available",
            }
        )
        sources.append(
            {
                "payload_id": payload_id,
                "source_region": project_region(region),
                "offset": physical.source_start,
            }
        )
    return payloads, sources


def _byte_accounting(document: PackageDocument) -> list[dict[str, Any]]:
    """Debug evidence: per-export window tiled by its decoded leaves."""
    objects_by_id = {obj.id: obj for obj in document.objects}
    scopes: list[dict[str, Any]] = []
    for scope_id, scope in document.byte_accounting.scopes.items():
        if not scope.leaves:
            continue
        obj = objects_by_id.get(scope_id)
        if obj is not None and obj.serial_region is not None:
            window = project_region(obj.serial_region)
        else:
            window = project_region(scope.leaves[0])
        scopes.append(
            {
                "object_id": scope_id,
                "window": window,
                "leaves": [project_region(leaf) for leaf in scope.leaves],
            }
        )
    return scopes


def _object_regions(document: PackageDocument) -> list[dict[str, Any]]:
    return [
        {"object_id": obj.id, "region": project_region(obj.serial_region)}
        for obj in document.objects
        if obj.serial_region is not None
    ]


def project_document(
    document: PackageDocument,
    *,
    mode: Literal["normal", "debug"] = "normal",
) -> dict[str, Any]:
    """Project a full decode PackageDocument to the v4 envelope.

    ``normal`` carries decoded values and static semantics only. ``debug``
    adds the evidence block (``debug``); stripping it and normalizing ``mode``
    reproduces ``normal`` exactly.
    """
    if mode not in _VALID_MODES:
        raise ValueError(f"Invalid mode: {mode!r}. Expected one of {_VALID_MODES}")
    _require_full_decode(document)

    source = document.source
    assert source is not None
    diagnostics = _all_diagnostics(document)
    payloads, payload_sources = _payload_descriptors(document)

    # Display names for relation targets (peer-borrowed readability):
    # exports -> object name, imports -> "package.object" path. Ids stay
    # canonical; duplicate names are fine here (display convenience only).
    target_display = {obj.id: obj.name for obj in document.objects}
    for dep in document.dependencies:
        target_display[f"import:{dep.index}"] = f"{dep.package_name}.{dep.object_name}" if dep.package_name else dep.object_name

    from uasset_read.projections.records import projection_to_dict

    semantic_evidence: list[dict[str, Any]] = []
    result: dict[str, Any] = {
        "format": "uasset_read.package",
        "format_version": FORMAT_VERSION,
        "mode": mode,
        "source": {"kind": source.kind, "name": source.name, "size": source.size},
        "package": _package_to_dict(document),
        "summary": {
            "object_count": document.summary.object_count,
            "asset_object_ids": list(document.summary.asset_object_ids),
            "total_imports": document.summary.total_imports,
            "total_exports": document.summary.total_exports,
        },
        "objects": [obj_to_dict(obj, semantic_evidence) for obj in document.objects],
        "relations": [
            {
                "kind": rel.kind,
                "from": rel.from_id,
                "to": rel.to_id,
                **({"target_path": target_display[rel.to_id]} if rel.to_id in target_display else {}),
            }
            for rel in document.relations
        ],
        "dependencies": [dependency_to_dict(dep) for dep in document.dependencies],
        "projections": [projection_to_dict(item) for item in build_projection_records(document)],
        "payloads": payloads,
        "sidecars": [],
        "diagnostics": [diagnostic_summary(d) for d in diagnostics],
    }

    if mode == "debug":
        result["debug"] = {
            "object_regions": _object_regions(document),
            "property_evidence": _property_evidence(document),
            "semantic_source_ranges": sorted(
                semantic_evidence,
                key=lambda entry: (entry["json_pointer"], entry["object_id"]),
            ),
            "payload_sources": payload_sources,
            "sidecar_sources": [],
            "diagnostic_details": [diagnostic_detail(d, i) for i, d in enumerate(diagnostics)],
            "byte_accounting": _byte_accounting(document),
        }
    return result
