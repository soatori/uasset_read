"""Projection — view/depth/selection/pagination on PackageDocument.

Transforms a PackageDocument into different views without mutating it.
"""

from __future__ import annotations

from typing import Any

from .models.document import PackageDocument
from .models.object_model import Dependency, ObjectRecord


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

    Negative offset/limit are rejected here rather than per caller.
    """
    if offset < 0:
        raise ValueError(f"offset must be >= 0, got {offset}")
    if limit is not None and limit < 0:
        raise ValueError(f"limit must be >= 0 or None, got {limit}")

    total = len(items)
    page = items[offset:]
    if limit is not None:
        page = page[:limit]

    next_offset = offset + len(page) if offset + len(page) < total else None
    truncation_info = {
        "total": total,
        "offset": offset,
        "limit": limit if limit is not None else total,
        "returned": len(page),
    }
    return page, next_offset, truncation_info


def project_document(
    doc: PackageDocument,
    *,
    depth: str = "asset",
    object_ids: list[str] | None = None,
    roles: list[str] | None = None,
    classes: list[str] | None = None,
    offset: int = 0,
    limit: int | None = None,
) -> dict[str, Any]:
    """Project a PackageDocument to a view dict for JSON serialization."""
    objects = select_objects(doc, object_ids=object_ids, roles=roles, classes=classes)
    page, next_offset, truncation_info = paginate(objects, offset=offset, limit=limit)

    return {
        "source": {
            "kind": doc.source.kind,
            "name": doc.source.name,
            "size": doc.source.size,
            "path": doc.source.path,
        },
        "package": {
            "name": doc.package.name,
            "layout": doc.package.layout,
            "engine_version": doc.package.engine_version,
            "compatible_engine_version": doc.package.compatible_engine_version,
            "package_flags": doc.package.package_flags,
            "total_header_size": doc.package.total_header_size,
            "export_count": doc.package.export_count,
            "import_count": doc.package.import_count,
            "name_count": doc.package.name_count,
        },
        "objects": [_object_to_dict(obj) for obj in page],
        "relations": [_relation_to_dict(r) for r in doc.relations],
        "dependencies": [_dependency_to_dict(d) for d in doc.dependencies],
        "diagnostics": [d.to_dict() for d in doc.diagnostics],
        "summary": {
            "object_count": doc.summary.object_count,
            "asset_object_ids": list(doc.summary.asset_object_ids),
            "total_imports": doc.summary.total_imports,
            "total_exports": doc.summary.total_exports,
        },
        "depth": doc.depth,
        "pagination": {
            "offset": offset,
            "limit": limit,
            "next_offset": next_offset,
            "truncation": truncation_info,
        },
    }


def _object_to_dict(obj: ObjectRecord) -> dict[str, Any]:
    """Convert ObjectRecord to dict for JSON serialization."""
    d: dict[str, Any] = {
        "id": obj.id,
        "table_index": obj.table_index,
        "name": obj.name,
    }
    if obj.class_name is not None:
        d["class_name"] = obj.class_name
    if obj.class_ref is not None:
        d["class_ref"] = str(obj.class_ref)
    if obj.outer_ref is not None:
        d["outer_ref"] = str(obj.outer_ref)
    if obj.super_ref is not None:
        d["super_ref"] = str(obj.super_ref)
    if obj.template_ref is not None:
        d["template_ref"] = str(obj.template_ref)
    if obj.flags:
        d["flags"] = obj.flags
    if obj.roles:
        d["roles"] = list(obj.roles)
    if obj.serial_region is not None:
        d["serial_region"] = {
            "offset": obj.serial_region.offset,
            "size": obj.serial_region.size,
        }
    d["status"] = {
        "parse": obj.status.parse,
        "semantic": obj.status.semantic,
    }
    if obj.properties is not None:
        d["properties"] = obj.properties
    if obj.semantic is not None:
        d["semantic"] = obj.semantic
    if obj.coverage:
        d["coverage"] = [
            {"feature": c.feature, "status": c.status, "detail": c.detail}
            for c in obj.coverage
        ]
    return d


def _relation_to_dict(rel: Any) -> dict[str, Any]:
    """Convert Relation to dict for JSON serialization."""
    return {
        "kind": rel.kind,
        "from_id": rel.from_id,
        "to_id": rel.to_id,
    }


def _dependency_to_dict(dep: Dependency) -> dict[str, Any]:
    """Convert Dependency to dict for JSON serialization."""
    return {
        "index": dep.index,
        "class_name": dep.class_name,
        "object_name": dep.object_name,
        "package_name": dep.package_name,
    }
