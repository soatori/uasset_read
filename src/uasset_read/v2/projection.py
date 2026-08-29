"""Projection — view/depth/selection/pagination on PackageDocument.

Transforms a PackageDocument into different views without mutating it.
"""

from __future__ import annotations

from typing import Any

from .document import PackageDocument
from .object_model import ObjectRecord


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


_VALID_DEPTHS = {"package", "object", "asset", "decode"}


def project_document(
    doc: PackageDocument,
    *,
    view: str = "semantic",
    depth: str = "asset",
    object_ids: list[str] | None = None,
    roles: list[str] | None = None,
    classes: list[str] | None = None,
    fields: list[str] | None = None,
    offset: int = 0,
    limit: int | None = None,
    max_bytes: int | None = None,
) -> dict[str, Any]:
    """Project a PackageDocument to a specific view/depth/selection/pagination.

    Views:
      - semantic (default): object identity, roles, status, coverage
      - raw: adds flags, serial offsets, header details
      - debug: raw + parse statistics, recovery info, offset evidence
    """
    import json as _json

    _VALID_VIEWS = {"semantic", "raw", "debug"}
    if view not in _VALID_VIEWS:
        raise ValueError(f"Invalid view: {view!r}. Expected one of {_VALID_VIEWS}")
    if depth not in _VALID_DEPTHS:
        raise ValueError(f"Invalid depth: {depth!r}. Expected one of {_VALID_DEPTHS}")
    if offset < 0:
        raise ValueError("offset must be non-negative")
    if limit is not None and limit < 0:
        raise ValueError("limit must be non-negative")
    if max_bytes is not None and max_bytes < 0:
        raise ValueError("max_bytes must be non-negative")

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
            d = obj_to_dict(obj, view=view)
            filtered.append({k: v for k, v in d.items() if k in field_set or k in ("id", "name")})
        page = filtered
    relations = [{"kind": r.kind, "from": r.from_id, "to": r.to_id} for r in doc.relations if r.from_id in page_ids]
    page_diagnostics = [
        d for d in doc.diagnostics if getattr(d, "object_id", None) is None or getattr(d, "object_id", None) in page_ids
    ]

    # Find all objects reachable from the page through relations
    reachable_ids = set(page_ids)
    frontier = set(page_ids)
    while frontier:
        next_frontier = set()
        for r in doc.relations:
            if r.from_id in frontier and r.to_id not in reachable_ids:
                next_frontier.add(r.to_id)
            if r.to_id in frontier and r.from_id not in reachable_ids:
                next_frontier.add(r.from_id)
        frontier = next_frontier
        reachable_ids.update(frontier)

    # Filter dependencies to only those reachable from the page
    reachable_imports = {idx for idx, imp in enumerate(doc.dependencies) if f"import:{imp.index}" in reachable_ids}
    filtered_dependencies = [
        {"index": d.index, "class": d.class_name, "object_name": d.object_name}
        for i, d in enumerate(doc.dependencies)
        if i in reachable_imports
    ]

    # Filter payloads to only those owned by objects in the page
    filtered_payloads = [
        {
            "id": p.id,
            "owner": p.owner_id,
            "kind": p.kind,
            "source_region": p.source_region,
            "offset": p.offset,
            "stored_size": p.stored_size,
            "status": p.status,
        }
        for p in doc.payloads
        if p.owner_id in page_ids
    ]

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
        else [obj_to_dict(o, view=view) for o in page],
        "relations": relations,
        "dependencies": filtered_dependencies,
        "payloads": filtered_payloads,
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
            "object_diagnostics": sum(len(o.diagnostics) for o in doc.objects),
        }

    # max_bytes enforcement — measure AFTER adding TRUNCATED diagnostic
    if max_bytes is not None:

        def _encoded() -> int:
            return len(_json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

        if _encoded() > max_bytes:
            trunc_diag = {
                "severity": "warning",
                "code": "TRUNCATED",
                "message": f"Output truncated to fit {max_bytes}-byte budget",
                "stage": "projection",
                "recoverable": True,
            }
            result["diagnostics"].append(trunc_diag)
            while len(result["objects"]) > 0 and _encoded() > max_bytes:
                result["objects"].pop()
            # Add truncation metadata, then re-check: the metadata itself adds bytes
            objects_dropped = len(selected) - len(result["objects"])
            result["truncation"] = {
                "reason": "max_bytes",
                "budget": max_bytes,
                "objects_dropped": objects_dropped,
            }
            result["next_offset"] = offset + len(result["objects"])
            # Re-measure after adding truncation metadata; pop more objects if needed
            while len(result["objects"]) > 0 and _encoded() > max_bytes:
                result["objects"].pop()
                result["truncation"]["objects_dropped"] += 1
                result["next_offset"] = offset + len(result["objects"])
            actual = _encoded()
            if actual > max_bytes:
                raise ValueError(f"Output budget {max_bytes} bytes too small for minimal envelope ({actual} bytes)")
            result["truncation"]["actual"] = actual

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


def obj_to_dict(obj: ObjectRecord, *, view: str = "semantic") -> dict[str, Any]:
    """Convert an ObjectRecord to a dict for JSON serialization.

    Views:
      - semantic: identity, roles, status, coverage
      - raw: adds flags, serial_region details
      - debug: raw + all diagnostics with full detail
    """
    d: dict[str, Any] = {
        "id": obj.id,
        "table_index": obj.table_index,
        "name": obj.name,
        "class": obj.class_name,
        "roles": list(obj.roles),
        "serial_region": (
            {"offset": obj.serial_region.offset, "size": obj.serial_region.size} if obj.serial_region else None
        ),
        "status": {"parse": obj.status.parse, "semantic": obj.status.semantic},
    }
    if view in ("raw", "debug"):
        d["flags"] = obj.flags
    if obj.properties is not None:
        d["properties"] = obj.properties
    if obj.semantic is not None:
        d["semantic"] = obj.semantic
    if obj.coverage:
        d["coverage"] = [
            {"feature": c.feature, "status": c.status, **({"detail": c.detail} if c.detail else {})}
            for c in obj.coverage
        ]
    if obj.diagnostics:
        d["diagnostics"] = [diag.to_dict() for diag in obj.diagnostics]
    return d
