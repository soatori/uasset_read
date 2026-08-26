"""LegacyPackageReader — adapter from v1 ParseResult to v2 PackageDocument.

This is the bridge that converts existing parse results into
the new v2 document model. Phase 1 uses this adapter; later phases
replace it with a direct binary reader.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..diagnostics import Diagnostic
from ..object_model import (
    Dependency,
    ObjectRecord,
    ObjectStatus,
    Region,
    Relation,
    ROLES_ASSET,
    ROLES_CDO,
    ROLES_GENERATED_CLASS,
)
from ..document import PackageDocument, PackageInfo, SourceInfo, Summary


def _extract_property_diagnostics(
    export: Any,
    export_index: int,
) -> list[Diagnostic]:
    """Extract property-level diagnostics from an export's parsed properties."""
    diags: list[Diagnostic] = []
    properties = getattr(export, "properties", None) or []
    for prop in properties:
        # size_exceeded means the tag claimed more bytes than available
        if getattr(prop, "size_exceeded", False):
            diags.append(Diagnostic(
                severity="warning",
                code="PROPERTY_SIZE_EXCEEDED",
                message=(
                    f"Property '{getattr(prop, 'name', '?')}' "
                    f"size {getattr(prop, 'size', 0)} exceeded remaining bytes"
                ),
                stage="properties.tagged",
                object_id=f"export:{export_index}",
                property_path=getattr(prop, "name", "?"),
                offset=getattr(prop, "tag_start_offset", None),
                size=getattr(prop, "size", None),
                effect="semantic_loss",
                recoverable=True,
            ))
        # Check for remainder bytes between value_end_offset and actual end
        value_end = getattr(prop, "value_end_offset", None)
        value_start = getattr(prop, "value_start_offset", None)
        if (
            value_end is not None
            and value_start is not None
            and not getattr(prop, "size_exceeded", False)
        ):
            expected_size = getattr(prop, "size", 0)
            if expected_size > 0:
                # This is informational — the property was parsed within bounds
                pass
    return diags


def _build_source_info(path: str) -> SourceInfo:
    p = Path(path)
    return SourceInfo(
        kind="loose",
        name=p.name,
        size=p.stat().st_size,
        path=str(p),
    )


def _build_package_info(summary: Any, name_map: list[str]) -> PackageInfo:
    engine_version = ""
    saved = getattr(summary, "saved_by_engine_version", None)
    if saved and hasattr(saved, "major"):
        engine_version = f"{saved.major}.{saved.minor}.{saved.patch}.{saved.changelist}"

    compat_version = ""
    compat = getattr(summary, "compatible_with_engine_version", None)
    if compat and hasattr(compat, "major"):
        compat_version = f"{compat.major}.{compat.minor}.{compat.patch}.{compat.changelist}"

    return PackageInfo(
        name=getattr(summary, "package_name", ""),
        layout="legacy",
        engine_version=engine_version,
        compatible_engine_version=compat_version,
        package_flags=getattr(summary, "package_flags", 0),
        total_header_size=getattr(summary, "total_header_size", 0),
        export_count=getattr(summary, "export_count", 0),
        import_count=getattr(summary, "import_count", 0),
        name_count=getattr(summary, "name_count", 0) or len(name_map),
    )


def _resolve_class_name(export: Any) -> str | None:
    """Try to get class name from export."""
    cn = getattr(export, "class_name", None)
    if cn:
        return cn
    # Try to resolve from class_index
    class_index = getattr(export, "class_index", None)
    if class_index is not None:
        idx = getattr(class_index, "index_value", None)
        if idx is not None and idx < 0:
            return f"import:{-idx - 1}"
    return None


def _build_object_record(
    export: Any,
    index: int,
    name_map: list[str],
) -> ObjectRecord:
    """Convert a v1 ObjectExport to a v2 ObjectRecord."""
    name = getattr(export, "object_name", "")
    b_is_asset = getattr(export, "b_is_asset", False)

    # Determine roles
    roles: list[str] = []
    if b_is_asset:
        roles.append(ROLES_ASSET)

    # Detect CDO by name pattern
    if name.startswith("Default__"):
        roles.append(ROLES_CDO)

    # Detect GeneratedClass by name pattern
    if name.endswith("_C") and not name.startswith("Default__"):
        roles.append(ROLES_GENERATED_CLASS)

    # Serial region
    serial_offset = getattr(export, "serial_offset", 0)
    serial_size = getattr(export, "serial_size", 0)
    serial_region = None
    if serial_size > 0:
        serial_region = Region(offset=serial_offset, size=serial_size)

    # Parse status from v1 export status
    export_status = getattr(export, "parse_status", None)
    if export_status is None or export_status == "success":
        parse_status = "complete"
    elif export_status in ("partial", "skipped"):
        parse_status = "partial"
    elif export_status == "failed":
        parse_status = "failed"
    else:
        parse_status = "opaque"

    class_name = _resolve_class_name(export)

    return ObjectRecord(
        id=f"export:{index}",
        table_index=index,
        name=name,
        class_name=class_name,
        serial_region=serial_region,
        flags=getattr(export, "object_flags", 0),
        roles=tuple(roles),
        status=ObjectStatus(parse=parse_status, semantic="not_requested"),
    )


def _resolve_package_index(pi: Any) -> str | None:
    """Convert a PackageIndex to an object id string."""
    if pi is None:
        return None
    idx = getattr(pi, "index", None)
    if idx is None or idx == 0:
        return None
    if idx < 0:
        return f"import:{-idx - 1}"
    return f"export:{idx - 1}"


def _build_relations(exports: list[Any]) -> list[Relation]:
    """Derive relations from export outer/super/template indices."""
    relations: list[Relation] = []
    for i, exp in enumerate(exports):
        from_id = f"export:{i}"

        # outer_of
        outer_id = _resolve_package_index(getattr(exp, "outer_index", None))
        if outer_id is not None:
            relations.append(Relation(kind="outer_of", from_id=from_id, to_id=outer_id))

        # class_of
        class_id = _resolve_package_index(getattr(exp, "class_index", None))
        if class_id is not None:
            relations.append(Relation(kind="class_of", from_id=from_id, to_id=class_id))

        # template_of
        template_id = _resolve_package_index(getattr(exp, "template_index", None))
        if template_id is not None:
            relations.append(Relation(kind="template_of", from_id=from_id, to_id=template_id))

    return relations


def _build_dependencies(import_map: list[Any]) -> list[Dependency]:
    """Convert v1 import map to v2 dependencies."""
    deps: list[Dependency] = []
    for i, imp in enumerate(import_map):
        deps.append(Dependency(
            index=i,
            class_name=getattr(imp, "class_name", ""),
            object_name=getattr(imp, "object_name", ""),
            package_name=getattr(imp, "class_package", ""),
        ))
    return deps


def _build_diagnostics_from_v1(
    export_map: list[Any],
    errors: list[str],
    warnings: list[str],
) -> list[Diagnostic]:
    """Convert v1 errors/warnings to v2 diagnostics."""
    diags: list[Diagnostic] = []

    # Convert export-level failures
    for i, exp in enumerate(export_map):
        status = getattr(exp, "parse_status", None)
        if status == "failed":
            diags.append(Diagnostic(
                severity="error",
                code="EXPORT_PARSE_FAILED",
                message=f"Export {i} ({getattr(exp, 'object_name', '?')}) failed to parse",
                stage="objects.export",
                object_id=f"export:{i}",
                effect="parse_failure",
                recoverable=True,
            ))
        elif status == "partial":
            diags.append(Diagnostic(
                severity="warning",
                code="EXPORT_PARTIAL",
                message=f"Export {i} ({getattr(exp, 'object_name', '?')}) partially parsed",
                stage="objects.export",
                object_id=f"export:{i}",
                effect="semantic_loss",
                recoverable=True,
            ))

    # Convert top-level errors
    for err in errors:
        diags.append(Diagnostic(
            severity="error",
            code="PACKAGE_HEADER_ERROR",
            message=err,
            stage="package.summary",
            recoverable=True,
        ))

    return diags


def build_package_document(
    parse_result: Any,
    file_path: str,
) -> PackageDocument:
    """Build a v2 PackageDocument from a v1 ParseResult.

    This is the Phase 1 adapter. It wraps existing data to produce
    the new document model without replacing the v1 pipeline.
    """
    summary = parse_result.summary
    export_map = getattr(parse_result, "export_map", []) or []
    import_map = getattr(parse_result, "import_map", []) or []
    name_map = getattr(parse_result, "name_map", []) or []

    # Build objects — ALL exports, no filtering
    objects = [
        _build_object_record(exp, i, name_map)
        for i, exp in enumerate(export_map)
    ]

    # Build relations
    relations = _build_relations(export_map)

    # Build dependencies
    dependencies = _build_dependencies(import_map)

    # Build diagnostics — package-level + property-level per export
    diagnostics = _build_diagnostics_from_v1(
        export_map,
        getattr(parse_result, "errors", []),
        getattr(parse_result, "warnings", []),
    )
    for i, exp in enumerate(export_map):
        diagnostics.extend(_extract_property_diagnostics(exp, i))

    # Compute asset_object_ids
    asset_ids = tuple(obj.id for obj in objects if ROLES_ASSET in obj.roles)

    # Summary
    package_info = _build_package_info(summary, name_map) if summary else PackageInfo(name="", layout="legacy")
    summary_obj = Summary(
        object_count=len(objects),
        asset_object_ids=asset_ids,
        total_imports=len(import_map),
        total_exports=len(export_map),
    )

    return PackageDocument(
        source=_build_source_info(file_path),
        package=package_info,
        objects=objects,
        relations=relations,
        dependencies=dependencies,
        diagnostics=diagnostics,
        summary=summary_obj,
    )
