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
    max_bytes: int | None = None,
    item_byte_estimate: Any = None,
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

    Returns a dict matching the v2 JSON contract.
    """
    # Select objects
    selected = select_objects(doc, object_ids=object_ids, roles=roles, classes=classes)

    # Paginate
    page, next_offset, truncation_info = paginate(
        selected,
        offset=offset,
        limit=limit,
        max_bytes=max_bytes,
    )

    # Filter fields if requested
    if fields:
        field_set = set(fields)
        page_dicts = []
        for obj in page:
            d = obj_to_dict(obj)
            page_dicts = page_dicts  # keep full for now, filter later
        # Field filtering on full objects
        filtered = []
        for obj in page:
            d = obj_to_dict(obj)
            filtered.append({k: v for k, v in d.items() if k in field_set or k in ("id", "name")})
        page = filtered

    # Build result
    result: dict[str, Any] = {
        "format": "uasset_read.package",
        "format_version": "2.0",
        "view": view,
        "depth": depth,
        "source": {"kind": doc.source.kind, "name": doc.source.name, "size": doc.source.size},
        "package": {
            "name": doc.package.name,
            "layout": doc.package.layout,
            "engine_version": doc.package.engine_version,
            "package_flags": doc.package.package_flags,
            "export_count": doc.package.export_count,
            "import_count": doc.package.import_count,
            "name_count": doc.package.name_count,
        },
        "objects": [obj_to_dict(o) for o in page],
        "relations": [{"kind": r.kind, "from": r.from_id, "to": r.to_id} for r in doc.relations],
        "dependencies": [
            {"index": d.index, "class": d.class_name, "object_name": d.object_name} for d in doc.dependencies
        ],
        "payloads": [],
        "diagnostics": [d.to_dict() for d in doc.diagnostics],
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

    return result


def obj_to_dict(obj: ObjectRecord) -> dict[str, Any]:
    """Convert an ObjectRecord to a dict for JSON serialization."""
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
