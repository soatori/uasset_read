"""Projection — view/depth/selection/pagination on PackageDocument.

Transforms a PackageDocument into different views without mutating it.
"""

from __future__ import annotations

import json
from typing import Any

from .document import PackageDocument
from .object_model import Dependency, ObjectRecord


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


def paginate(
    items: list[Any],
    *,
    offset: int = 0,
    limit: int | None = None,
) -> tuple[list[Any], int | None, dict[str, int]]:
    """Paginate a list, returning (page, next_offset, truncation_info).

    If limit is None, all items are returned.
    Returns (items, next_offset_or_None, truncation_info).
    """
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
    def _size() -> int:
        return len(json.dumps(response, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    items = response[list_key]
    while _size() > max_bytes and items:
        items.pop()
        n = len(items)
        response["returned"] = n
        response["next_offset"] = response["offset"] + n
    if not items:
        response.pop("next_offset", None)  # a cursor that doesn't advance ends nothing
    size = _size()  # one encode serves both the test and the message
    if size > max_bytes:
        raise ValueError(f"Response budget {max_bytes} bytes too small for minimal envelope ({size} bytes)")
    if items and response["offset"] + len(items) >= response[total_key]:
        response.pop("next_offset", None)  # a cursor past the real end is a lie
    return response


_VALID_DEPTHS = {"package", "object", "asset", "decode"}
_DEPTH_ORDER = {"package": 0, "object": 1, "asset": 2, "decode": 3}

# Top-level scoped sections that ``project_document(sections=...)`` may drop.
_VALID_SECTIONS = {"relations", "dependencies"}


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
    fields: list[str] | None = None,
    sections: list[str] | None = None,
    offset: int = 0,
    limit: int | None = None,
    max_bytes: int | None = None,
    response_extras: dict | None = None,
) -> dict[str, Any]:
    """Project a PackageDocument to a specific view/depth/selection/pagination.

    Views:
      - semantic (default): object identity, roles, status, coverage
      - raw: adds flags, serial offsets, header details
      - debug: raw + parse statistics, recovery info, offset evidence
    ``sections`` is an allowlist of the scoped envelope sections to include
    (valid names: "relations", "dependencies"); excluded sections are dropped
    from the response before ``max_bytes`` accounting, so their bytes go to
    the object page instead. Default None keeps both (unchanged behavior).
    ``response_extras`` entries are merged with ``dict.update()`` (same-named
    projection keys are overwritten by the extras) before ``max_bytes``
    trimming runs, so extras count against the byte budget like any envelope key.
    """
    _VALID_VIEWS = {"semantic", "raw", "debug"}
    if view not in _VALID_VIEWS:
        raise ValueError(f"Invalid view: {view!r}. Expected one of {_VALID_VIEWS}")
    if depth not in _VALID_DEPTHS:
        raise ValueError(f"Invalid depth: {depth!r}. Expected one of {_VALID_DEPTHS}")
    if sections is not None:
        unknown = set(sections) - _VALID_SECTIONS
        if unknown:
            raise ValueError(f"Invalid sections: {sorted(unknown)}. Expected from {_VALID_SECTIONS}")
    if offset < 0:
        raise ValueError("offset must be non-negative")
    if limit is not None and limit < 0:
        raise ValueError("limit must be non-negative")
    if max_bytes is not None and max_bytes < 0:
        raise ValueError("max_bytes must be non-negative")
    if _DEPTH_ORDER[depth] > _DEPTH_ORDER[doc.depth]:
        raise ValueError(
            f"cannot project at depth {depth!r}: document was parsed at depth {doc.depth!r}"
        )

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

    # Select objects
    selected = select_objects(doc, object_ids=object_ids, roles=roles, classes=classes)

    # Paginate
    page, next_offset, truncation_info = paginate(
        selected,
        offset=offset,
        limit=limit,
    )

    # Scope relations and diagnostics to the returned page
    # IMPORTANT: compute page_ids BEFORE fields filter, since fields converts to dicts
    page_ids = {o.id for o in page if isinstance(o, ObjectRecord)}
    if not page_ids and page and isinstance(page[0], dict):
        page_ids = {o["id"] for o in page if "id" in o}

    # Filter fields if requested
    if fields:
        field_set = set(fields)
        filtered = []
        for obj in page:
            d = _emit(obj)
            filtered.append({k: v for k, v in d.items() if k in field_set or k in ("id", "name")})
        page = filtered

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

    # Build result
    result: dict[str, Any] = {
        "format": "uasset_read.package",
        "format_version": "2.0",
        "view": view,
        "depth": depth,
        "source": {"kind": doc.source.kind, "name": doc.source.name, "size": doc.source.size},
        "package": _package_to_dict(doc, view=view),
        "objects": page
        if (fields and page and isinstance(page[0], dict))
        else [_emit(o) for o in page],
        "relations": relations,
        "dependencies": filtered_dependencies,
        # Payloads stay deferred (issue #621); the key is schema-required.
        "payloads": [],
        "diagnostics": [d.to_dict() for d in page_diagnostics],
        "summary": {
            "object_count": doc.summary.object_count,
            "asset_object_ids": list(doc.summary.asset_object_ids),
            "total_imports": doc.summary.total_imports,
            "total_exports": doc.summary.total_exports,
        },
    }

    # Drop opted-out scoped sections BEFORE max_bytes accounting (#631).
    if sections is not None:
        for dropped in _VALID_SECTIONS - set(sections):
            result.pop(dropped)

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

    # max_bytes enforcement — measure AFTER adding TRUNCATED diagnostic
    if max_bytes is not None:

        def _encoded() -> int:
            return len(json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

        if _encoded() > max_bytes:
            trunc_diag = {
                "severity": "warning",
                "code": "TRUNCATED",
                "message": f"Output truncated to fit {max_bytes}-byte budget",
                "stage": "projection",
                "recoverable": True,
            }
            result["diagnostics"].append(trunc_diag)
            # Attach the truncation block BEFORE measuring, so the byte cap
            # accounts for the block itself.
            result["truncation"] = {
                "reason": "max_bytes",
                "budget": max_bytes,
                "actual": _encoded(),
                "objects_dropped": 0,
            }
            result["next_offset"] = offset + len(result["objects"])
            while len(result["objects"]) > 0 and _encoded() > max_bytes:
                result["objects"].pop()
                result["next_offset"] = offset + len(result["objects"])
                remaining_ids = {o["id"] for o in result["objects"] if isinstance(o, dict) and "id" in o}
                rels, diags, deps = _scope_to_page(remaining_ids)
                if "relations" in result:
                    result["relations"] = rels
                if "dependencies" in result:
                    result["dependencies"] = deps
                result["diagnostics"] = [d.to_dict() for d in diags] + [trunc_diag]
            page_total = max(0, len(selected) - offset)
            if limit is not None:
                page_total = min(limit, page_total)
            if page_total == 0:
                # Out-of-range empty page: never a cursor, never over budget.
                result.pop("next_offset", None)
                result["truncation"]["actual"] = _encoded()
                if _encoded() > max_bytes:
                    raise ValueError(f"Output budget {max_bytes} bytes too small for minimal envelope ({_encoded()} bytes)")
                return result
            if len(result["objects"]) == 0:
                # Nothing fit. A budget that cannot even hold the bare
                # envelope (no objects, no truncation metadata) is a hard
                # error; otherwise return an explicit retry contract: no
                # cursor, page-relative dropped count, BUDGET_EXHAUSTED diag.
                skeleton = {k: v for k, v in result.items() if k not in ("truncation", "next_offset")}
                skeleton["diagnostics"] = [d for d in skeleton["diagnostics"] if d.get("code") != "TRUNCATED"]
                minimal = len(json.dumps(skeleton, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
                if minimal > max_bytes:
                    raise ValueError(f"Output budget {max_bytes} bytes too small for minimal envelope ({minimal} bytes)")
                result.pop("next_offset", None)
                result["truncation"] = {
                    "reason": "max_bytes",
                    "budget": max_bytes,
                    "actual": _encoded(),
                    "objects_dropped": page_total,
                }
                result["diagnostics"].append({
                    "severity": "warning",
                    "code": "BUDGET_EXHAUSTED",
                    "message": f"Budget {max_bytes} fits 0 of {page_total} page objects; retry offset {offset} with a larger max_bytes",
                    "stage": "projection",
                    "recoverable": True,
                })
                return result
            objects_dropped = page_total - len(result["objects"])
            actual = _encoded()
            result["truncation"] = {
                "reason": "max_bytes",
                "budget": max_bytes,
                "actual": actual,
                "objects_dropped": objects_dropped,
            }

    return result


def _package_to_dict(doc: PackageDocument, *, view: str = "semantic") -> dict[str, Any]:
    """Convert PackageInfo to dict, with extra fields for raw/debug views."""
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
            if isinstance(inner, dict) and inner.get("kind") in ("struct", "struct_fallback"):
                return {"kind": "value", "type": val.get("type"), "value": _summary_value(inner)}
        return val
    if isinstance(val, list):
        return {"kind": "array", "length": len(val)}
    return val


def _property_summary(bag: dict[str, Any]) -> dict[str, Any]:
    """Bounded compact view of a property bag for the semantic view (#636).

    Names + scalars only; containers keep kind and length, never elements or
    raw bytes. Truncation is explicit via ``property_count``; the full bag
    stays available in the raw/debug views.
    """
    items = list(bag.items())[:_SUMMARY_MAX_NAMES]
    return {
        "properties": {name: _summary_value(v) for name, v in items},
        "property_count": len(bag),
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
            {"offset": obj.serial_region.offset, "size": obj.serial_region.size} if obj.serial_region else None
        )
        if obj.properties is not None:
            d["properties"] = obj.properties
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
