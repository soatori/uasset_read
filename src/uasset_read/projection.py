"""Projection — view/depth/selection/pagination on PackageDocument.

Transforms a PackageDocument into different views without mutating it.
"""

from __future__ import annotations

import json
from typing import Any

from .models.document import PackageDocument
from .models.object_model import Dependency, ObjectRecord

# Envelope schema major for project_document() output. Deliberately lives on
# the projection layer: PackageDocument stays a package-level aggregate with
# no presentation-version state (v3 contract freeze, Task 1).
FORMAT_VERSION = "3.0"


def build_projection_records(
    document: PackageDocument,
    *,
    object_ids: list[str] | None = None,
    registry: Any | None = None,
) -> list[Any]:
    """Create embedded type-aware projection records for a PackageDocument.

    Sole API that produces type-specific embedded content. ``object_ids``
    limits records to those sources. Unknown families emit no records.
    """
    from uasset_read.projections.records import ProjectionRecord
    from uasset_read.projections.registry import ProjectorRegistry

    active = registry if registry is not None else ProjectorRegistry.default()
    if object_ids is None:
        records: list[ProjectionRecord] = active.project_document(document)
    else:
        records = []
        for object_id in object_ids:
            records.extend(active.project_object(document, object_id))
        records.sort(key=lambda item: (item.source_object_id, item.kind, item.media_type))
    return records


def select_objects(
    doc: PackageDocument,
    *,
    object_ids: list[str] | None = None,
    roles: list[str] | None = None,
    classes: list[str] | None = None,
) -> list[ObjectRecord]:
    """Filter objects by id, role, or class. All filters are AND-combined."""
    result = doc.objects
    if object_ids:
        id_set = set(object_ids)
        result = [o for o in result if o.id in id_set]
    if roles:
        role_set = set(roles)
        result = [o for o in result if any(r in role_set for r in o.roles)]
    if classes:
        class_set = set(classes)
        result = [o for o in result if o.class_name in class_set]
    return result


def json_byte_size(payload: Any) -> int:
    """Compact-JSON UTF-8 byte length — the single measure every byte-budget trim shares."""
    return len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def paginate(
    items: list[Any],
    *,
    offset: int = 0,
    limit: int | None = None,
) -> tuple[list[Any], int | None, dict[str, int]]:
    """Paginate a list, returning (page, next_offset, truncation_info).

    If limit is None, all items are returned.
    Returns (items, next_offset_or_None, truncation_info).

    Negative ``offset``/``limit`` are rejected here rather than per caller:
    Python slicing happily accepts them (#644), and ``offset=-1`` silently
    returned the last page with a cursor that walked backwards. Zero is legal.
    """
    if offset < 0:
        raise ValueError("offset must be non-negative")
    if limit is not None and limit < 0:
        raise ValueError("limit must be non-negative")
    total = len(items)
    page = items[offset:]
    truncated = False

    if limit is not None and len(page) > limit:
        page = page[:limit]
        truncated = True

    next_offset = offset + len(page) if truncated or (offset + len(page) < total) else None
    truncation_info = {
        "total": total,
        "offset": offset,
        "returned": len(page),
        "truncated": 1 if truncated else 0,
    }
    return page, next_offset, truncation_info


def fit_list_response(response: dict, max_bytes: int, *, list_key: str, total_key: str = "total") -> dict:
    """Drop trailing items from response[list_key] until the compact encoding fits max_bytes.

    Mutates ``response`` in place; it must carry {list_key (a list), "offset",
    "returned", total_key}. Raises ValueError when max_bytes cannot hold even
    the empty-list envelope.
    """
    items = response[list_key]
    while json_byte_size(response) > max_bytes and items:
        items.pop()
        n = len(items)
        response["returned"] = n
        response["next_offset"] = response["offset"] + n
    if not items:
        response.pop("next_offset", None)  # a cursor that doesn't advance ends nothing
    size = json_byte_size(response)  # one measure serves both the test and the message
    if size > max_bytes:
        raise ValueError(f"Response budget {max_bytes} bytes too small for minimal envelope ({size} bytes)")
    if items and response["offset"] + len(items) >= response[total_key]:
        response.pop("next_offset", None)  # a cursor past the real end is a lie
    return response


_VALID_VIEWS = {"semantic", "raw", "debug"}
_VALID_DEPTHS = {"package", "object", "asset", "decode"}
_DEPTH_ORDER = {"package": 0, "object": 1, "asset": 2, "decode": 3}

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


def project_document(
    doc: PackageDocument,
    *,
    view: str = "semantic",
    depth: str = "asset",
    object_ids: list[str] | None = None,
    roles: list[str] | None = None,
    classes: list[str] | None = None,
    offset: int = 0,
    limit: int | None = None,
    max_bytes: int | None = None,
    response_extras: dict | None = None,
) -> dict[str, Any]:
    """Project a PackageDocument to a specific view/depth/selection/pagination.

    Layer split (G4): this function validates, selects and paginates;
    ``_project_envelope`` performs structure conversion (never truncates) and
    ``_enforce_budget`` performs byte-budget truncation (never touches the
    document). Serialization stays with the caller — CLI and Agent each dump once.

    Views:
      - semantic (default): object identity, roles, status, coverage
      - raw: adds flags, serial offsets, header details
      - debug: raw + parse statistics, recovery info, offset evidence
    ``offset``/``limit`` are validated by ``paginate`` (#644), the single
    guard every paging caller routes through.
    ``response_extras`` entries are merged with ``dict.update()`` (same-named
    projection keys are overwritten by the extras) before ``max_bytes``
    trimming runs, so extras count against the byte budget like any envelope key.
    """
    if view not in _VALID_VIEWS:
        raise ValueError(f"Invalid view: {view!r}. Expected one of {_VALID_VIEWS}")
    if depth not in _VALID_DEPTHS:
        raise ValueError(f"Invalid depth: {depth!r}. Expected one of {_VALID_DEPTHS}")
    if max_bytes is not None and max_bytes < 0:
        raise ValueError("max_bytes must be non-negative")
    if _DEPTH_ORDER[depth] > _DEPTH_ORDER[doc.depth]:
        raise ValueError(f"cannot project at depth {depth!r}: document was parsed at depth {doc.depth!r}")

    selected = select_objects(doc, object_ids=object_ids, roles=roles, classes=classes)
    page, next_offset, truncation_info = paginate(
        selected,
        offset=offset,
        limit=limit,
    )
    envelope = _project_envelope(
        doc,
        view=view,
        depth=depth,
        page=page,
        next_offset=next_offset,
        truncation_info=truncation_info,
        response_extras=response_extras,
    )
    if max_bytes is not None:
        page_total = max(0, len(selected) - offset)
        if limit is not None:
            page_total = min(limit, page_total)
        envelope = _enforce_budget(envelope, max_bytes, offset=offset, page_total=page_total)
    return envelope


def _project_envelope(
    doc: PackageDocument,
    *,
    view: str,
    depth: str,
    page: list[ObjectRecord],
    next_offset: int | None,
    truncation_info: dict[str, int],
    response_extras: dict | None = None,
) -> dict[str, Any]:
    """Layer 1 (G4): structure conversion only — selection and pagination are
    already applied; this layer never truncates.
    """

    def _emit(o: ObjectRecord) -> dict[str, Any]:
        """Serialize one object, stripping fields the projection depth can't back."""
        d = obj_to_dict(o, view=view)
        if _DEPTH_ORDER[depth] < _DEPTH_ORDER["asset"]:
            d.pop("semantic", None)
            d.pop("coverage", None)
        if _DEPTH_ORDER[depth] < _DEPTH_ORDER["object"]:
            d.pop("properties", None)
            d.pop("properties_summary", None)
        return d

    # Scope relations and diagnostics to the returned page
    page_ids = {o.id for o in page}

    # Display names for relation targets (peer-borrowed readability):
    # exports -> object name, imports -> "package.object" path (UE class-path
    # style, matching the f"{package}.{asset}" join in serializers). Ids stay
    # canonical; duplicate names are fine here (display convenience only).
    target_display = {o.id: o.name for o in doc.objects}
    for d in doc.dependencies:
        target_display[f"import:{d.index}"] = f"{d.package_name}.{d.object_name}" if d.package_name else d.object_name

    def _scope_to_page(ids: set[str]) -> tuple[list, list, list]:
        """Scope relations, diagnostics, dependencies to page ids."""
        relations = []
        for r in doc.relations:
            if r.from_id not in ids:
                continue
            rel: dict[str, Any] = {"kind": r.kind, "from": r.from_id, "to": r.to_id}
            if r.to_id in target_display:
                rel["target_path"] = target_display[r.to_id]
            relations.append(rel)
        page_diagnostics = [
            d for d in doc.diagnostics if getattr(d, "object_id", None) is None or getattr(d, "object_id", None) in ids
        ]

        # Keep only imports that appear as relation targets of page objects —
        # one hop, matching the edges the response actually shows. A
        # multi-hop closure here retained imports the page could not account
        # for (reachable only through relations of dropped objects).
        visible_ids = ids | {r["to"] for r in relations}
        reachable_imports = {idx for idx, imp in enumerate(doc.dependencies) if f"import:{imp.index}" in visible_ids}
        filtered_dependencies = [
            dependency_to_dict(d) for i, d in enumerate(doc.dependencies) if i in reachable_imports
        ]
        return relations, page_diagnostics, filtered_dependencies

    relations, page_diagnostics, filtered_dependencies = _scope_to_page(page_ids)

    # Type-aware projections for the returned page only. Canonical file
    # materialization stays on build_canonical_document/write_projected_document;
    # this bounded response API embeds the same registry records.
    from uasset_read.projections.records import projection_to_dict

    page_projection_records = build_projection_records(doc, object_ids=[o.id for o in page])
    page_projections = [projection_to_dict(item) for item in page_projection_records]

    # Build result
    assert doc.source is not None
    result: dict[str, Any] = {
        "format": "uasset_read.package",
        "format_version": FORMAT_VERSION,
        "projections": page_projections,
        "sidecars": [],
        "view": view,
        "depth": depth,
        "source": {"kind": doc.source.kind, "name": doc.source.name, "size": doc.source.size},
        "package": _package_to_dict(doc, view=view),
        "objects": [_emit(o) for o in page],
        "relations": relations,
        "dependencies": filtered_dependencies,
        # Payloads stay deferred; per-export BulkData mapping requires
        # cooked fixtures (#627).  The key is schema-required.
        "payloads": [],
        "diagnostics": [d.to_dict() for d in page_diagnostics],
        "summary": {
            "object_count": doc.summary.object_count,
            "asset_object_ids": list(doc.summary.asset_object_ids),
            "total_imports": doc.summary.total_imports,
            "total_exports": doc.summary.total_exports,
        },
    }

    if next_offset is not None:
        result["next_offset"] = next_offset
        result["truncation"] = truncation_info

    # Debug view adds parse statistics
    if view == "debug":
        result["debug"] = {
            "total_objects": len(doc.objects),
            "total_relations": len(doc.relations),
            "total_diagnostics": len(doc.diagnostics),
        }

    # Merge agent-tool response keys BEFORE measuring, so the trim
    # machinery below accounts for them like any other envelope bytes.
    if response_extras:
        result.update(response_extras)

    return result


def _enforce_budget(envelope: dict[str, Any], max_bytes: int, *, offset: int, page_total: int) -> dict[str, Any]:
    """Layer 2 (G4): drop trailing page objects until the compact encoding fits.

    Depends only on the already-projected dict, never on ``PackageDocument``,
    so truncation decisions are unit-testable from a hand-built envelope.
    Re-scoping after a drop filters the page-scoped lists captured on entry —
    the same subsets ``_project_envelope`` would have produced for the
    surviving ids. Measure AFTER adding the TRUNCATED diagnostic: the cap
    must account for every byte the caller will serialize.
    """
    if json_byte_size(envelope) <= max_bytes:
        return envelope

    # Captured once: the binary search probes prefixes in arbitrary order, so
    # each probe must re-derive from the page-scoped originals, not from the
    # previous probe's residue.
    base_relations = list(envelope.get("relations", []))
    base_dependencies = list(envelope.get("dependencies", []))
    base_projections = list(envelope.get("projections", []))
    base_diagnostics = list(envelope["diagnostics"])

    trunc_diag = {
        "severity": "warning",
        "code": "TRUNCATED",
        "message": f"Output truncated to fit {max_bytes}-byte budget",
        "stage": "projection",
        "recoverable": True,
    }
    envelope["diagnostics"].append(trunc_diag)
    # Attach the truncation block BEFORE measuring, so the byte cap
    # accounts for the block itself.
    envelope["truncation"] = {
        "reason": "max_bytes",
        "budget": max_bytes,
        "actual": json_byte_size(envelope),
        "objects_dropped": 0,
    }
    envelope["next_offset"] = offset + len(envelope["objects"])
    objects_snapshot = list(envelope["objects"])

    def _apply_prefix(keep: int) -> None:
        envelope["objects"] = objects_snapshot[:keep]
        envelope["next_offset"] = offset + keep
        remaining_ids = {o["id"] for o in envelope["objects"] if isinstance(o, dict) and "id" in o}
        kept_relations = [r for r in base_relations if isinstance(r, dict) and r.get("from") in remaining_ids]
        if "relations" in envelope:
            envelope["relations"] = kept_relations
        # Visible imports stay one hop out: the surviving objects plus whatever
        # their surviving relations point at.
        visible_ids = remaining_ids | {r["to"] for r in kept_relations}
        if "dependencies" in envelope:
            envelope["dependencies"] = [
                d for d in base_dependencies if isinstance(d, dict) and f"import:{d.get('index')}" in visible_ids
            ]
        # Projection records follow the surviving page objects.
        envelope["projections"] = [
            item for item in base_projections if item.get("source_object_id") in remaining_ids
        ]
        envelope["diagnostics"] = [
            d for d in base_diagnostics if isinstance(d, dict) and (d.get("object_id") is None or d["object_id"] in remaining_ids)
        ] + [trunc_diag]

    # Binary search the longest prefix that fits. Linear pop+re-encode
    # is O(n) full dumps and stalls AnimBlueprint decode pages (~4MB).
    lo, hi = 0, len(objects_snapshot)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        _apply_prefix(mid)
        if json_byte_size(envelope) <= max_bytes:
            lo = mid
        else:
            hi = mid - 1
    _apply_prefix(lo)

    if page_total == 0:
        # Out-of-range empty page: never a cursor, never over budget.
        envelope.pop("next_offset", None)
        envelope["truncation"]["actual"] = json_byte_size(envelope)
        if json_byte_size(envelope) > max_bytes:
            raise ValueError(
                f"Output budget {max_bytes} bytes too small for minimal envelope ({json_byte_size(envelope)} bytes)"
            )
        return envelope
    if len(envelope["objects"]) == 0:
        # Nothing fit: return the complete retry contract only if
        # its diagnostics and truncation metadata fit the budget.
        envelope.pop("next_offset", None)
        envelope["truncation"] = {
            "reason": "max_bytes",
            "budget": max_bytes,
            "actual": json_byte_size(envelope),
            "objects_dropped": page_total,
        }
        envelope["diagnostics"].append(
            {
                "severity": "warning",
                "code": "BUDGET_EXHAUSTED",
                "message": f"Budget {max_bytes} fits 0 of {page_total} page objects; retry offset {offset} with a larger max_bytes",
                "stage": "projection",
                "recoverable": True,
            }
        )
        # The byte count includes its own digits, so stabilize it
        # after all metadata has been added before checking the cap.
        actual = json_byte_size(envelope)
        while envelope["truncation"]["actual"] != actual:
            envelope["truncation"]["actual"] = actual
            actual = json_byte_size(envelope)
        if actual > max_bytes:
            raise ValueError(f"Output budget {max_bytes} bytes too small for minimal envelope ({actual} bytes)")
        return envelope
    objects_dropped = page_total - len(envelope["objects"])
    envelope["truncation"] = {
        "reason": "max_bytes",
        "budget": max_bytes,
        "actual": 0,
        "objects_dropped": objects_dropped,
    }
    actual = json_byte_size(envelope)
    while envelope["truncation"]["actual"] != actual:
        envelope["truncation"]["actual"] = actual
        actual = json_byte_size(envelope)

    return envelope


def _package_to_dict(doc: PackageDocument, *, view: str = "semantic") -> dict[str, Any]:
    """Convert PackageInfo to dict, with extra fields for raw/debug views."""
    assert doc.package is not None
    d: dict[str, Any] = {
        "name": doc.package.name,
        "layout": doc.package.layout,
        "engine_version": doc.package.engine_version,
        "compatible_engine_version": doc.package.compatible_engine_version,
        "package_flags": doc.package.package_flags,
        "export_count": doc.package.export_count,
        "import_count": doc.package.import_count,
        "name_count": doc.package.name_count,
    }
    if view in ("raw", "debug"):
        d["total_header_size"] = doc.package.total_header_size
    return d


_SUMMARY_MAX_NAMES = 100


def _summary_value(val: Any) -> Any:
    """Compact one property value: scalars pass, containers are length-elided.

    ``normalize_property_bag`` descriptors that are already length-bounded
    (bytes, opaque) pass through untouched; struct-shaped values (including
    fallbacks, which may carry raw bytes) collapse to a length-only form.
    """
    if isinstance(val, dict):
        kind = val.get("kind")
        if kind == "struct":
            return {"kind": "struct", "struct_type": val.get("struct_type"), "length": len(val.get("fields", {}))}
        if kind == "struct_fallback":
            return {
                "kind": "struct_fallback",
                "struct_type": val.get("struct_type"),
                "size": val.get("size"),
                "length": len(val.get("fields", {})),
            }
        if kind == "value":
            inner = val.get("value")
            if isinstance(inner, list):
                return {"kind": "value", "type": val.get("type"), "length": len(inner)}
            if isinstance(inner, dict):
                return {"kind": "value", "type": val.get("type"), "value": _summary_value(inner)}
            return val
        if kind == "map":
            return {
                "kind": "map",
                "key_type": val.get("key_type"),
                "value_type": val.get("value_type"),
                "length": len(val.get("entries") or []),
            }
        if kind == "set":
            return {"kind": "set", "element_type": val.get("element_type"), "length": len(val.get("elements") or [])}
        if kind in {"struct_property", "material_input", "binary_or_native_property"}:
            # Bounded native headers stay; never expand nested raw blobs here.
            keys = {
                k: v
                for k, v in val.items()
                if k in {"kind", "struct_type", "type", "size", "expression_ref", "output_index", "input_name"}
                and not isinstance(v, (bytes, dict, list))
            }
            return keys or {"kind": kind}
        return val
    if isinstance(val, list):
        return {"kind": "array", "length": len(val)}
    return val


def _property_summary(bag: Any) -> dict[str, Any]:
    """Bounded compact view of a property bag for the semantic view (#636).

    Names + scalars only; containers keep kind and length, never elements or
    raw bytes. Truncation is explicit via ``property_count``; the full bag
    stays available in the raw/debug views.
    """
    from uasset_read.models.properties import project_property_value

    items = [(entry.name, project_property_value(entry.value)) for entry in bag.entries]
    count = len(bag.entries)
    items = items[:_SUMMARY_MAX_NAMES]
    return {
        "properties": {name: _summary_value(v) for name, v in items},
        "property_count": count,
    }


def obj_to_dict(obj: ObjectRecord, *, view: str = "semantic") -> dict[str, Any]:
    """Convert an ObjectRecord to a dict for JSON serialization.

    Views:
      - semantic: identity, roles, status, coverage, bounded properties_summary
      - raw: adds flags, serial_region details, the full property bag
      - debug: raw + all diagnostics with full detail
    """
    d: dict[str, Any] = {
        "id": obj.id,
        "table_index": obj.table_index,
        "name": obj.name,
        "class": obj.class_name,
        "roles": list(obj.roles),
        "status": {"parse": obj.status.parse, "semantic": obj.status.semantic},
    }
    if view in ("raw", "debug"):
        d["flags"] = obj.flags
        d["serial_region"] = (
            {"offset": obj.serial_region.start, "size": obj.serial_region.size} if obj.serial_region else None
        )
        if obj.properties is not None:
            from uasset_read.models.properties import project_property_bag

            d["properties"] = project_property_bag(obj.properties)
    elif view == "semantic" and obj.properties is not None:
        d["properties_summary"] = _property_summary(obj.properties)
    if obj.semantic is not None:
        d["semantic"] = obj.semantic
    if obj.coverage:
        d["coverage"] = [
            {"feature": c.feature, "status": c.status, **({"detail": c.detail} if c.detail else {})}
            for c in obj.coverage
        ]
    return d
