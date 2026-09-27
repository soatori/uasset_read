"""LegacyPackageReader — direct binary reader for legacy .uasset packages.

Reads package summary, name table, import/export maps, depends, and
preload dependencies directly from binary, building a PackageDocument
without going through the v1 pipeline.
"""

from __future__ import annotations

import contextlib
import struct
from pathlib import Path
from collections.abc import Sequence
from typing import Any, Literal, get_args

from ..archive import ByteArchive, SourceInfo
from ..constants import PKG_Cooked, PKG_FilterEditorOnly, PKG_UnversionedProperties
from ..exceptions import ParseError, ExportBoundsExceeded

from ..package import PackageArchive
from ..serializers.property_tags import read_property_tag
from ..serializers.object_resources import (
    ObjectExport,
    ObjectImport,
    PackageIndex,
    read_export_map,
    read_import_map,
    resolve_class_name,
    script_property_region,
)
from ..serializers.package_summary import (
    PackageFileSummary,
    read_depends_map,
    read_name_table,
    read_package_summary,
    read_preload_dependencies,
)
from ..models.diagnostics import (
    Diagnostic,
    TrailingContext,
    classify_trailing_reason,
    make_diagnostic as _diag,
)
from .asset_types import handlers_impl as _handlers_side_effect  # noqa: F401  — registration
from .asset_types.registry import run_handlers
from ..models.document import PackageDocument, PackageInfo, Summary
from ..models.object_model import (
    Dependency,
    ObjectRecord,
    ObjectRef,
    ObjectStatus,
    Relation,
)
from ..models.properties import PropertyBag
from ..versioning import FORTNITE_GUID, get_custom_version


def _package_index_to_ref(pi: PackageIndex) -> ObjectRef | None:
    """Convert a PackageIndex to an ObjectRef."""
    if pi.is_null:
        return None
    if pi.is_import:
        return ObjectRef(table="import", index=pi.to_import_index())
    return ObjectRef(table="export", index=pi.to_export_index())


def _package_index_to_id(pi: PackageIndex) -> str | None:
    """Convert a PackageIndex to an object id string."""
    if pi.is_null:
        return None
    if pi.is_import:
        return f"import:{pi.to_import_index()}"
    return f"export:{pi.to_export_index()}"


def _resolve_outer_name(
    obj: ObjectRecord,
    objects: list[ObjectRecord],
    import_map: list[ObjectImport],
) -> str | None:
    """Resolve an object's Outer to its display name; None when absent or out of range."""
    ref = obj.outer_ref
    if ref is None:
        return None
    if ref.table == "export":
        if 0 <= ref.index < len(objects):
            return objects[ref.index].name
        return None
    if 0 <= ref.index < len(import_map):
        return import_map[ref.index].object_name
    return None


def _build_preload_relations(
    preload_deps: Sequence[int],
    export_map: Sequence[ObjectExport],
) -> tuple[list[Relation], list[Diagnostic]]:
    """Derive preload_of relations from per-export preload dependency spans.

    UE legacy format: each FObjectExport's FirstExportDependency plus the
    four category counts index into the summary's flat PreloadDependencyValues
    array; the export's span is
    [FirstExportDependency, FirstExportDependency + total) (LinkerSave.cpp).
    """
    relations: list[Relation] = []
    diagnostics: list[Diagnostic] = []
    for i, exp in enumerate(export_map):
        if exp.first_export_dependency < 0:
            continue
        total = (
            exp.serialization_before_serialization_dependencies
            + exp.create_before_serialization_dependencies
            + exp.serialization_before_create_dependencies
            + exp.create_before_create_dependencies
        )
        if total <= 0:
            continue
        start = exp.first_export_dependency
        end = start + total
        if end > len(preload_deps):
            diagnostics.append(
                _diag(
                    "PRELOAD_DEPENDENCY_RANGE_INVALID",
                    f"Export {i} preload span [{start},{end}) exceeds preload array size {len(preload_deps)}",
                    "package.preload",
                    object_id=f"export:{i}",
                    effect=None,
                )
            )
            continue
        for raw in preload_deps[start:end]:
            to_id = _package_index_to_id(PackageIndex(raw))
            if to_id is not None:
                relations.append(Relation(kind="preload_of", from_id=f"export:{i}", to_id=to_id))
    return relations, diagnostics


def _validate_relation_targets(
    relations: Sequence[Relation],
    *,
    export_count: int,
    import_count: int,
) -> tuple[list[Relation], list[Diagnostic]]:
    """Drop relations whose target exceeds its table size, with diagnostics.

    Out-of-range table references are corrupt data at a binary trust boundary;
    they surface as structured, recoverable diagnostics instead of dangling edges.
    """
    kept: list[Relation] = []
    diagnostics: list[Diagnostic] = []
    for rel in relations:
        table, _, raw_idx = rel.to_id.partition(":")
        try:
            idx = int(raw_idx)
        except ValueError:
            diagnostics.append(
                _diag(
                    "RELATION_TARGET_INVALID",
                    f"{rel.kind} target {rel.to_id} from {rel.from_id} has unparseable index",
                    "package.relations",
                    object_id=rel.from_id,
                    effect=None,
                )
            )
            continue
        limit = export_count if table == "export" else import_count
        if table not in ("export", "import") or idx >= limit:
            diagnostics.append(
                _diag(
                    "RELATION_TARGET_OUT_OF_RANGE",
                    f"{rel.kind} target {rel.to_id} from {rel.from_id} exceeds {table} table size {limit}",
                    "package.relations",
                    object_id=rel.from_id,
                    effect=None,
                )
            )
            continue
        kept.append(rel)
    return kept, diagnostics


# NAME_None reaches us as the literal table entry "None" (index 0), and as
# Python None when the version gate skipped the field entirely.
_NAME_NONE = frozenset({None, "", "None"})


def _import_owner(
    import_map: Sequence[ObjectImport],
    start: int,
    resolved: dict[int, tuple[str, str]],
) -> tuple[str, str]:
    """Resolve the package import ``start`` belongs to, as (package, reason).

    Empty package always comes with a reason. Every node stepped over on the way
    inherits that same answer, so caching them keeps the whole table linear;
    ``MAX_IMPORT_COUNT`` is 1,000,000, and re-walking each chain from its own
    start would turn a crafted outer list into quadratic work. ``seen`` makes a
    cyclic chain terminate without needing a depth cap.
    """
    chain: list[int] = []
    seen: set[int] = {start}
    cur_i = start
    while True:
        cached = resolved.get(cur_i)
        if cached is not None:
            answer = cached
            break
        chain.append(cur_i)
        cur = import_map[cur_i]
        owner = cur.package_name
        if isinstance(owner, str) and owner not in _NAME_NONE:
            answer = (owner, "")
            break
        outer = cur.outer_index.index
        if outer == 0:
            # Null OuterIndex marks the top-level UPackage itself; its
            # ObjectName is the package path (see resolve_import_dependencies).
            if cur.class_name != "Package":
                answer = ("", "outer chain ends on a non-Package entry")
            elif cur.object_name in _NAME_NONE:
                answer = ("", "Package entry carries no name")
            else:
                answer = (cur.object_name, "")
            break
        if outer > 0:
            answer = ("", "outer references an export")
            break
        idx = -outer - 1
        if not 0 <= idx < len(import_map):
            answer = ("", f"outer import index {idx} is out of range")
            break
        if idx in seen:
            answer = ("", "outer chain cycles")
            break
        seen.add(idx)
        cur_i = idx
    for node in chain:
        resolved[node] = answer
    return answer


def resolve_import_dependencies(
    import_map: Sequence[ObjectImport],
) -> tuple[list[Dependency], list[Diagnostic]]:
    """Build the import dependency set keyed on each import's *owning* package.

    ``FObjectImport.ClassPackage`` is the package holding the object's class, so
    reading it as the owner made every engine-classed asset claim
    ``/Script/Engine`` (#645). UE separates the two facts: the owner is
    ``PackageName`` when set, otherwise the outer chain is followed "until a set
    PackageName is found or until OuterIndex is null" (ObjectResource.h:457-460)
    and that terminal entry, a null-outer ``Package`` resource, carries the
    package path in its ``ObjectName`` (ObjectResource.h:199-203,
    LinkerLoad.cpp:2402).

    Unresolvable owners stay empty with a diagnostic; a path is never guessed.
    """
    dependencies: list[Dependency] = []
    diagnostics: list[Diagnostic] = []
    resolved: dict[int, tuple[str, str]] = {}
    for i, imp in enumerate(import_map):
        owner, reason = _import_owner(import_map, i, resolved)
        dependencies.append(
            Dependency(
                index=i,
                class_name=imp.class_name,
                object_name=imp.object_name,
                package_name=owner,
            )
        )
        if not owner:
            diagnostics.append(
                _diag(
                    "IMPORT_PACKAGE_UNRESOLVED",
                    f"Import {i} ({imp.class_name} {imp.object_name}) has no owning package: {reason}",
                    "package.import_map",
                    object_id=f"import:{i}",
                )
            )
    return dependencies, diagnostics


def _build_object_record_direct(
    export: ObjectExport,
    index: int,
    import_map: list[ObjectImport],
    export_map: list[ObjectExport],
    main_path: str = "",
) -> ObjectRecord:
    """Convert an ObjectExport to an ObjectRecord using direct binary data."""
    name = export.object_name
    b_is_asset = export.b_is_asset

    # Determine roles
    roles: list[str] = []
    if b_is_asset:
        roles.append("asset")
    if name.startswith("Default__"):
        roles.append("class_default_object")
    if name.endswith("_C") and not name.startswith("Default__"):
        roles.append("generated_class")

    # Serial region — package-virtual ByteRegion with physical source mapping.
    serial_region = None
    if export.serial_size > 0:
        from ..models.byte_ranges import ByteRegion, region_from_source
        from ..sources import CompositeSource, FileSource

        if main_path:
            try:
                source = CompositeSource.from_package(Path(main_path))
                serial_region = region_from_source(
                    source,
                    export.serial_offset,
                    export.serial_size,
                    status="decoded",
                    feature="serial",
                )
            except Exception:
                source = FileSource(Path(main_path))
                serial_region = region_from_source(
                    source,
                    export.serial_offset,
                    export.serial_size,
                    status="decoded",
                    feature="serial",
                )
        else:
            serial_region = ByteRegion(
                start=export.serial_offset,
                size=export.serial_size,
                status="decoded",
                source_id="package",
                source_start=export.serial_offset,
                feature="serial",
            )

    # Class name resolution
    class_name = resolve_class_name(export.class_index, import_map, export_map)

    # ObjectRef fields
    outer_ref = _package_index_to_ref(export.outer_index)
    super_ref = _package_index_to_ref(export.super_index)
    class_ref = _package_index_to_ref(export.class_index)
    template_ref = _package_index_to_ref(export.template_index)

    return ObjectRecord(
        id=f"export:{index}",
        table_index=index,
        name=name,
        class_name=class_name,
        outer_ref=outer_ref,
        super_ref=super_ref,
        class_ref=class_ref,
        template_ref=template_ref,
        flags=export.object_flags,
        roles=tuple(roles),
        serial_region=serial_region,
        status=ObjectStatus(parse="complete", semantic="not_requested"),
    )


def _merge_archive_recoveries(
    archive: PackageArchive,
    objects: Sequence[ObjectRecord],
    diagnostics: list[Diagnostic],
) -> None:
    """Merge FArchive structured diagnostics into the document.

    A diagnostic whose fallback rescued the read surfaces as
    effect="recovery" and downgrades the attributed object's parse status
    to at least partial. A "stop_table" fallback (e.g.
    EXPORT_TABLE_TRUNCATED) aborted the read instead — data past the stop
    point is lost, so it is labeled effect="data_loss", recoverable=False.
    """
    objects_by_id = {obj.id: obj for obj in objects}
    for sd in archive.get_structured_diagnostics():
        obj = objects_by_id.get(sd.object_id)
        if obj is not None and obj.status.parse == "complete":
            obj.status = ObjectStatus(parse="partial", semantic=obj.status.semantic)
        sev = sd.severity if sd.severity in ("info", "warning", "error", "critical") else "warning"
        # Effect heuristic: "stop_table" fallback means data loss
        recovered = getattr(sd, "fallback", None) != "stop_table"
        diagnostics.append(
            Diagnostic(
                severity=sev,
                code=sd.code,
                message=sd.message,
                stage=sd.stage,
                object_id=sd.object_id or None,
                offset=sd.offset,
                effect="recovery" if recovered else "data_loss",
                recoverable=recovered,
                fallback=getattr(sd, "fallback", None),
                reason=getattr(sd, "reason", None),
            )
        )


def _build_source_info(path: str) -> SourceInfo:
    p = Path(path)
    return SourceInfo(
        kind="loose",
        name=p.name,
        size=p.stat().st_size,
        path=str(p),
    )


def _build_package_info_from_summary(
    summary: PackageFileSummary,
    name_map: list[str],
    source_path: str = "",
) -> PackageInfo:
    engine_version = ""
    saved = summary.saved_by_engine_version
    if saved and hasattr(saved, "major"):
        engine_version = f"{saved.major}.{saved.minor}.{saved.patch}.{saved.changelist}"

    compat_version = ""
    compat = summary.compatible_with_engine_version
    if compat and hasattr(compat, "major"):
        compat_version = f"{compat.major}.{compat.minor}.{compat.patch}.{compat.changelist}"

    # Derive package name from file path when summary.package_name is empty
    package_name = summary.package_name
    if not package_name and source_path:
        path_obj = Path(source_path)
        content_dir = next(
            (parent for parent in path_obj.parents if parent.name.lower() == "content"),
            None,
        )
        if content_dir is not None:
            relative = path_obj.relative_to(content_dir).with_suffix("").as_posix()
            plugin_root = content_dir.parent
            descriptor = plugin_root / f"{plugin_root.name}.uplugin"
            mount_root = f"/{plugin_root.name}" if descriptor.is_file() else "/Game"
            package_name = f"{mount_root}/{relative}"
        else:
            package_name = f"/Game/{path_obj.stem}"

    return PackageInfo(
        name=package_name,
        layout="legacy",
        engine_version=engine_version,
        compatible_engine_version=compat_version,
        package_flags=summary.package_flags,
        total_header_size=summary.total_header_size,
        export_count=summary.export_count,
        import_count=summary.import_count,
        name_count=summary.name_count or len(name_map),
    )


def normalize_property_bag(
    properties: Sequence[Any],
    *,
    package_source: Any | None = None,
    object_id: str = "",
) -> "PropertyBag":
    """Convert every parsed occurrence into a lossless ordered PropertyBag.

    Never keys the result by name. Presentation maps are built later by
    ``project_property_bag``. Missing/invalid ranges become diagnostics on
    the bag's entries via opaque regions rather than silent skips.
    """
    from ..models.byte_ranges import opaque_region
    from ..models.fallback import PropertyFallback
    from ..models.properties import (
        PropertyBag,
        PropertyEntry,
        StructValue,
        PropertyValue,
        project_property_value,
    )

    bag = PropertyBag()
    range_diags: list[Diagnostic] = []
    for prop in properties:
        name = getattr(prop, "name", None)
        if name is None:
            continue

        array_index: int | None = getattr(prop, "array_index", None)
        if isinstance(array_index, int) and array_index < 0:
            array_index = None
        type_name = getattr(prop, "type", "") or ""

        tag_start = getattr(prop, "tag_start_offset", None)
        value_start = getattr(prop, "value_start_offset", None)
        value_end = getattr(prop, "value_end_offset", None)

        if isinstance(prop, PropertyFallback):
            size = int(getattr(prop, "size", 0) or 0)
            if value_start is not None and value_end is not None and value_end > value_start:
                value_region = opaque_region(
                    int(value_start),
                    int(value_end - value_start),
                    getattr(prop.reason, "value", str(prop.reason)),
                    feature="property_fallback",
                )
            elif size > 0 and value_start is not None:
                value_region = opaque_region(
                    int(value_start),
                    size,
                    getattr(prop.reason, "value", str(prop.reason)),
                    feature="property_fallback",
                )
            else:
                value_region = None
            bag.entries.append(
                PropertyEntry(
                    name=str(name),
                    type_name=type_name,
                    value={
                        "kind": "opaque",
                        "type": prop.type,
                        "size": prop.size,
                        "reason": prop.reason.value,
                    },
                    array_index=array_index,
                    tag_region=None,
                    value_region=value_region,
                )
            )
            continue

        if isinstance(prop, StructValue):
            entry_value: Any = {
                "kind": "struct",
                "struct_type": prop.struct_type,
                "fields": {k: project_property_value(v) for k, v in prop.fields.items()},
            }
        elif isinstance(prop, PropertyValue):
            inner = prop.value
            if isinstance(inner, dict) and (
                "expression_ref" in inner
                or "expression_index" in inner
                or (inner.get("kind") in {"struct_property", "material_input", "struct_binary_decoded"})
            ):
                entry_value = _normalize_structured_dict(inner)
            elif isinstance(inner, StructValue):
                entry_value = {
                    "kind": "struct",
                    "struct_type": inner.struct_type,
                    "fields": {k: project_property_value(v) for k, v in inner.fields.items()},
                }
            else:
                entry_value = {
                    "kind": "value",
                    "type": prop.type,
                    "value": project_property_value(inner),
                }
        elif isinstance(prop, dict):
            entry_value = _normalize_structured_dict(prop)
        else:
            entry_value = project_property_value(prop)

        tag_region = None
        value_region = None
        if (
            package_source is not None
            and tag_start is not None
            and value_start is not None
            and value_start >= tag_start
        ):
            from ..models.byte_ranges import region_from_source

            try:
                tag_region = region_from_source(
                    package_source,
                    int(tag_start),
                    int(value_start - tag_start),
                    status="decoded",
                    feature="property_tag",
                )
                if value_end is not None and value_end > value_start:
                    value_region = region_from_source(
                        package_source,
                        int(value_start),
                        int(value_end - value_start),
                        status="decoded",
                        feature="property_value",
                    )
            except Exception as exc:
                tag_region = None
                value_region = None
                range_diags.append(
                    Diagnostic(
                        severity="warning",
                        code="PROPERTY_RANGE_INVALID",
                        message=f"invalid tag/value range for {name!r}: {exc}",
                        stage="properties.normalize",
                        object_id=object_id,
                        offset=int(tag_start) if tag_start is not None else None,
                        size=None,
                        effect="semantic_loss",
                        reason="recovered_corruption",
                    )
                )

        bag.entries.append(
            PropertyEntry(
                name=name,
                type_name=type_name,
                value=entry_value,
                array_index=array_index,
                tag_region=tag_region,
                value_region=value_region,
            )
        )
    # Attach range diagnostics onto the bag for projector visibility.
    if range_diags:
        bag.diagnostics.extend(range_diags)
    return bag


def _normalize_structured_dict(inner: dict[str, Any]) -> dict[str, Any]:
    """Flatten known native structs so consumers see expression_ref/output_index."""
    out = dict(inner)
    fields = out.get("fields")
    if isinstance(fields, dict):
        for key, value in fields.items():
            out.setdefault(key, value)
        if "fields" in out and out.get("kind") in {"struct_property", "struct_binary_decoded"}:
            # Keep structured fields at top level for lossless consumers.
            merged = {k: v for k, v in out.items() if k != "fields"}
            merged.update(fields)
            out = merged
    if "expression_index" in out and "expression_ref" not in out:
        out["expression_ref"] = out["expression_index"]
    if "Expression" in out and "expression_ref" not in out:
        out["expression_ref"] = out["Expression"]
    if "OutputIndex" in out and "output_index" not in out:
        out["output_index"] = out["OutputIndex"]
    if "InputName" in out and "input_name" not in out:
        out["input_name"] = out["InputName"]
    return out


def _serialize_value(value: Any) -> Any:
    """Recursively serialize a property value to JSON-safe form."""
    from ..models.fallback import PropertyFallback, StructFallback
    from ..models.properties import (
        StructValue,
        SetValue,
        MapValue,
        TextValue,
    )

    if value is None or isinstance(value, (bool, int, float, str, bytes)):
        if isinstance(value, bytes):
            return {"kind": "bytes", "length": len(value)}
        return value
    if isinstance(value, PropertyFallback):
        return {
            "kind": "opaque",
            "type": value.type,
            "size": value.size,
            "reason": value.reason.value,
        }
    if isinstance(value, StructValue):
        inner: dict[str, Any] = {}
        for k, v in value.fields.items():
            inner[k] = _serialize_value(v)
        return {"kind": "struct", "struct_type": value.struct_type, "fields": inner}
    if isinstance(value, StructFallback):
        return value.to_dict()
    if isinstance(value, TextValue):
        return {
            "kind": "text",
            "namespace": value.namespace,
            "key": value.key,
            "source_string": value.source_string,
            "property_type": value.property_type,
        }
    if isinstance(value, SetValue):
        return [_serialize_value(elem) for elem in value.elements]
    if isinstance(value, MapValue):
        return [
            {"key": _serialize_value(e.get("key")), "value": _serialize_value(e.get("value"))} for e in value.entries
        ]
    if isinstance(value, list):
        return [_serialize_value(elem) for elem in value]
    if isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}
    # ObjectRef, other objects — repr as string
    return str(value)


class LegacyPackageReader:
    """Direct binary reader for legacy .uasset packages.

    Reads the binary format using existing serializers and builds
    a PackageDocument without going through the v1 pipeline.
    """

    def __init__(
        self,
        *,
        tolerant: bool = True,
        mappings_path: str | None = None,
        game: str | None = None,
    ) -> None:
        self._tolerant = tolerant
        self._mappings_path = mappings_path
        self._game = game
        # Resolved from the required read(main_path=...) argument; every
        # consumer needs the path for SourceInfo/PackageInfo.
        self._main_path: str = ""
        self._package_source: Any = None

    def read(
        self,
        *,
        depth: Literal["package", "object", "asset", "decode"] = "package",
        object_ids: Sequence[str] | None = None,
        archive: PackageArchive,
        main_path: str,
    ) -> PackageDocument:
        """Read the package and return a PackageDocument.

        At depth="package", only the package structure is read (no object properties).

        The caller owns *archive* and is responsible for closing it; this reader
        never closes an archive it did not open. *main_path* supplies the file
        path carried by SourceInfo/PackageInfo.
        """
        self._main_path = main_path
        diagnostics: list[Diagnostic] = []
        try:
            from ..sources import CompositeSource

            self._package_source = CompositeSource.from_package(Path(main_path))
        except Exception:
            self._package_source = None

        try:
            # 0. Load the mappings provider once per document (mirrors v1
            # _init_parse_env); None + diagnostic when unloadable.
            total_decompressed = 0
            mappings_provider, total_decompressed = self._load_mappings(diagnostics, total_decompressed)

            # 1. Read summary
            summary, total_decompressed = read_package_summary(archive, total_decompressed=total_decompressed)

            # 1a. .uexp address-space guard.
            # UE source (independent reviewer verdict, 2026-09-08):
            #   FilePackageWriterUtil.cpp:164-212 — the cook writer splits ONE
            #   combined buffer at Summary.TotalHeaderSize into .uasset + .uexp
            #   and rebases FFileRegion.Offset -= HeaderSize.
            #   SavePackage2.cpp:3762-3775 — Export.SerialOffset +=
            #   Linker.Summary.TotalHeaderSize (so SerialOffset indexes the
            #   combined stream, and .uexp content begins at TotalHeaderSize).
            #   AsyncLoading.cpp:605-611,894-918 — the engine's own split-file
            #   trigger is .uasset file size == Summary.TotalHeaderSize.
            # Concatenate .uexp ONLY when main_size == TotalHeaderSize AND a
            # .uexp exists; otherwise the spliced address space is wrong and
            # every SerialOffset silently misresolves.
            if archive.has_uexp and archive.main_size != summary.total_header_size:
                archive.reject_uexp_region()
                diagnostics.append(
                    _diag(
                        "UEXP_SPLIT_GUARD_FAILED",
                        (
                            f"main file size {archive.main_size} != "
                            f"Summary.TotalHeaderSize {summary.total_header_size}; "
                            f".uexp not concatenated — SerialOffset would misresolve"
                        ),
                        "package.uexp_guard",
                        effect=None,
                    )
                )

            # Property tag format is version-gated; set the gates the same
            # way pipeline/stages.py does so UE5.0-5.2 tags don't fall into
            # the UE5.3+ FPropertyTypeName path (mirrors v1 behavior).
            archive.set_property_version_gates(summary.file_version_ue4, summary.file_version_ue5)

            # 2. Validate name table
            if summary.name_count <= 0:
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        code="EMPTY_NAME_TABLE",
                        message=f"name_count={summary.name_count}, UE package must have non-empty name table",
                        stage="package.name_table",
                        recoverable=False,
                    )
                )
                return self._build_minimal_document(summary, diagnostics)

            # 3. Read name table
            name_map = read_name_table(archive, summary)
            archive.set_name_map(name_map)

            # 4. Read import map
            import_map = read_import_map(archive, summary, name_map)

            # 5. Read export map
            export_map = read_export_map(archive, summary, name_map)

            # Truncation is reported once by read_export_map's archive-level
            # EXPORT_TABLE_TRUNCATED diagnostic, merged in step 12 below.

            # 5a. Missing-sidecar diagnostic.
            # UE's split writer (FilePackageWriterUtil.cpp:164-176) moves every
            # export body into .uexp at Summary.TotalHeaderSize (SavePackage2.cpp:3767).
            # When size(.uasset) == TotalHeaderSize but no .uexp is spliced in,
            # the export serial ranges address bytes outside the archive.  Report
            # that once as its own diagnostic rather than letting each export fail
            # with a bounds error.
            if not archive.has_uexp and archive.main_size == summary.total_header_size and export_map:
                max_end = max((e.serial_offset + e.serial_size for e in export_map), default=0)
                if max_end > archive.total_size():
                    diagnostics.append(
                        _diag(
                            "PACKAGE_SIDECAR_MISSING",
                            (
                                f"main file is header-only ({archive.main_size} bytes) "
                                f"but no .uexp was found; exports referencing offsets "
                                f">= {summary.total_header_size} cannot be read"
                            ),
                            "package.bundle",
                            severity="error",
                            effect="data_loss",
                        )
                    )

            # 6. Read depends map
            depends_map = read_depends_map(archive, summary, total_decompressed=total_decompressed)

            # 7. Read preload dependencies
            preload_deps = read_preload_dependencies(archive, summary)

            # 8. Build ObjectRecords — ALL exports, no filtering
            objects = [
                _build_object_record_direct(exp, i, import_map, export_map, self._main_path)
                for i, exp in enumerate(export_map)
            ]

            # 10. Build relations from export indices
            relations: list[Relation] = []
            for i, exp in enumerate(export_map):
                from_id = f"export:{i}"
                outer_id = _package_index_to_id(exp.outer_index)
                if outer_id is not None:
                    relations.append(Relation(kind="outer_of", from_id=from_id, to_id=outer_id))
                class_id = _package_index_to_id(exp.class_index)
                if class_id is not None:
                    relations.append(Relation(kind="class_of", from_id=from_id, to_id=class_id))
                template_id = _package_index_to_id(exp.template_index)
                if template_id is not None:
                    relations.append(Relation(kind="template_of", from_id=from_id, to_id=template_id))
                super_id = _package_index_to_id(exp.super_index)
                if super_id is not None:
                    relations.append(Relation(kind="super_of", from_id=from_id, to_id=super_id))

            # 10a. Blueprint family edges — derived from the export table only.
            # UE basis: FObjectExport::ClassIndex is "the class this object
            # belongs to" (ObjectResource.h), and a CDO is an instance of its
            # class, so a "Default__X" export's ClassIndex resolves to the X
            # export itself (UClass::CreateDefaultObject, Class.cpp). The
            # generated class of a blueprint asset is "<AssetName>_C" in the
            # same Outer (UBlueprint::GetBlueprintClassName, Blueprint.cpp);
            # the class gate below keeps this name convention from pairing
            # arbitrary *_C exports.
            for i, exp in enumerate(export_map):
                name = exp.object_name
                if name.startswith("Default__"):
                    cls_id = _package_index_to_id(exp.class_index)
                    if cls_id is not None and cls_id.startswith("export:"):
                        relations.append(Relation(kind="default_object_of", from_id=f"export:{i}", to_id=cls_id))

            asset_by_outer_name: dict[tuple[str, str], int] = {}
            for i, exp in enumerate(export_map):
                if exp.b_is_asset:
                    key = (_package_index_to_id(exp.outer_index) or "", exp.object_name)
                    asset_by_outer_name[key] = i
            for i, exp in enumerate(export_map):
                name = exp.object_name
                if not name.endswith("_C") or name.startswith("Default__"):
                    continue
                cls_name = resolve_class_name(exp.class_index, import_map, export_map) or ""
                if not cls_name.endswith("BlueprintGeneratedClass"):
                    continue
                key = (_package_index_to_id(exp.outer_index) or "", name[:-2])
                bp_idx = asset_by_outer_name.get(key)
                if bp_idx is not None:
                    relations.append(
                        Relation(kind="generated_class_of", from_id=f"export:{i}", to_id=f"export:{bp_idx}")
                    )

            # 10b. Build depends_on relations from depends_map
            # UE FPackageIndex: positive -> export, negative -> import
            # (ObjectResource.h FPackageIndex::IsExport/IsImport)
            for i, deps in enumerate(depends_map):
                from_id = f"export:{i}"
                for pkg_index in deps:
                    to_id = _package_index_to_id(PackageIndex(pkg_index))
                    if to_id is not None:
                        relations.append(Relation(kind="depends_on", from_id=from_id, to_id=to_id))

            # 10c. Build preload_of relations from per-export preload spans
            preload_relations, preload_diags = _build_preload_relations(preload_deps, export_map)
            relations.extend(preload_relations)
            diagnostics.extend(preload_diags)

            # 10d. Drop relation targets that exceed their table size
            relations, target_diags = _validate_relation_targets(
                relations,
                export_count=len(export_map),
                import_count=len(import_map),
            )
            diagnostics.extend(target_diags)

            # 11. Build dependencies from import map. The owning package comes
            # from PackageName/outer chain, never from ClassPackage (#645).
            dependencies, import_package_diags = resolve_import_dependencies(import_map)
            diagnostics.extend(import_package_diags)

            # 12. FArchive structured recoveries are merged in step 17c, after
            # property parsing has attributed them to their objects.

            # 13. Compute asset_object_ids
            asset_ids = tuple(obj.id for obj in objects if "asset" in obj.roles)

            # 14. Build PackageInfo
            package_info = _build_package_info_from_summary(summary, name_map, source_path=self._main_path)

            # 15. Build Summary
            summary_obj = Summary(
                object_count=len(objects),
                asset_object_ids=asset_ids,
                total_imports=len(import_map),
                total_exports=len(export_map),
            )

            # 16. Parse properties for requested objects at depth >= object
            extras: dict[str, dict[str, Any]] = {}
            if depth in ("object", "asset", "decode"):
                extras = self._parse_requested_object_properties(
                    archive=archive,
                    objects=objects,
                    export_map=export_map,
                    import_map=import_map,
                    name_map=name_map,
                    summary=summary,
                    object_ids=object_ids,
                    diagnostics=diagnostics,
                    mappings=mappings_provider,
                    depth=depth,
                )
                byte_accounting = self._attach_byte_accounting(objects, diagnostics)
            else:
                from ..models.byte_ranges import ByteAccounting

                byte_accounting = ByteAccounting()

            # 16b. Blueprint deep-decode graph pass at depth="decode".
            # Editor saves do not export pins — they live in each node export's
            # serial region after the property stream. The shared
            # serializers/graph* readers decode them; results travel to the
            # handlers through extras under the owning export id.
            if depth == "decode" and not (summary.package_flags & PKG_Cooked):
                _attach_blueprint_graph_extras(
                    archive=archive,
                    summary=summary,
                    name_map=name_map,
                    import_map=import_map,
                    export_map=export_map,
                    objects=objects,
                    extras=extras,
                    diagnostics=diagnostics,
                    object_ids=object_ids,
                )

            # 16c. Kismet bytecode for Function/UFunction exports at asset+decode
            # (Gate K: expression summaries at asset; full tree at decode).
            if depth in ("asset", "decode") and not (summary.package_flags & PKG_Cooked):
                _attach_kismet_extras(
                    archive=archive,
                    summary=summary,
                    name_map=name_map,
                    import_map=import_map,
                    export_map=export_map,
                    objects=objects,
                    extras=extras,
                    diagnostics=diagnostics,
                    object_ids=object_ids,
                    include_ir=depth == "decode",
                )

            # 16d. Assemble the package envelope BEFORE the handler phase so
            # Blueprint correlation consumes the same PackageDocument instance
            # that read() finalizes and returns (plan Task 8 Step 4).
            source_info = _build_source_info(self._main_path)
            document = PackageDocument(
                source=source_info,
                package=package_info,
                objects=objects,
                relations=relations,
                dependencies=dependencies,
                diagnostics=diagnostics,
                summary=summary_obj,
                depth=depth,
                byte_accounting=byte_accounting,
            )

            # 16e. Per-owner typed analysis contexts: convert the decoded raw
            # graph dicts to typed IR exactly once (BlueprintGraphDecoder) and
            # pair them with the typed Kismet function IR built at attach time.
            from ..models.analysis import BlueprintAnalysisContext, BlueprintAnalysisEnvelope

            contexts: dict[str, BlueprintAnalysisContext] = {}
            if depth == "decode":
                from .blueprint.graph import BlueprintGraphDecoder

                decoder = BlueprintGraphDecoder()
                for obj in objects:
                    if (obj.class_name or "") not in _BLUEPRINT_FAMILY_CLASSES:
                        continue
                    entry = extras.get(obj.id) or {}
                    graphs_raw = entry.get("graphs") or []
                    if graphs_raw and obj.semantic is None:
                        # Decoder channel: BlueprintGraphDecoder reads raw
                        # graphs off the object; correlation re-reads them for
                        # node_data/kind enrichment while the seed is live.
                        obj.semantic = {
                            "graphs": graphs_raw,
                            "interfaces": entry.get("interfaces") or [],
                        }
                    typed_graphs = decoder.decode(obj, document, source=None)
                    functions = list(entry.get("kismet_ir") or [])
                    contexts[obj.id] = BlueprintAnalysisContext(
                        owner_object_id=obj.id,
                        graphs=typed_graphs,
                        functions=functions,
                    )
            envelope = BlueprintAnalysisEnvelope(document=document, contexts=contexts)

            # 17. Run asset handlers at depth >= asset
            if depth in ("asset", "decode"):
                for obj in objects:
                    try:
                        handler_result = run_handlers(
                            obj, depth, objects, (export_map, name_map, extras, envelope)
                        )
                        semantic = handler_result.semantic
                        if semantic is not None:
                            obj.semantic = semantic
                        elif obj.id in contexts:
                            # Handler produced nothing: drop the decoder seed so
                            # a partial seed never ships as the final semantic.
                            obj.semantic = None
                        obj.coverage.extend(handler_result.coverage)
                        diagnostics.extend(handler_result.diagnostics)
                    except Exception as exc:
                        diagnostics.append(
                            _diag(
                                "HANDLER_FAILURE",
                                f"Handler error for {obj.id}: {exc}",
                                "semantic.handler",
                                object_id=obj.id,
                                effect=None,
                            )
                        )

            # 17b. Payload descriptors are populated by the caller
            # (parse_package_document) after read() returns, using the
            # bundle's discovered sidecar files.

            # 17c. Merge FArchive structured recoveries (header maps +
            # property parsing) once every read has had its object context.
            _merge_archive_recoveries(archive, objects, diagnostics)

            # 18. The envelope assembled at 16d is the returned document; the
            # handler/correlation phases mutate the same object records and
            # diagnostic list in place.
            return document

        except ParseError as e:
            diagnostics.append(_diag("PACKAGE_READ_FAILED", str(e), "package.read", severity="error", effect=None))
            return self._build_minimal_document(None, diagnostics)

    def _load_mappings(self, diagnostics: list[Diagnostic], total_decompressed: int = 0) -> tuple[Any | None, int]:
        """Build the mappings provider once per document (mirrors v1 _init_parse_env).

        The property decoder expects a loaded provider object, never a raw
        path string. On any load failure (missing file, bad magic, missing
        optional codec) returns None and records a MAPPINGS_LOAD_FAILED
        diagnostic; the parse continues and unversioned exports stay opaque.
        """
        if not self._mappings_path:
            return None, total_decompressed
        try:
            # Lazy import mirrors v1 (pipeline/core.py, pipeline/stages.py):
            # the mappings module and its optional codecs must not become a
            # core-import dependency.
            from ..mappings import UsmapParser

            parser = UsmapParser(self._mappings_path, total_decompressed=total_decompressed)
            return parser.mappings, parser.total_decompressed
        except Exception as exc:
            diagnostics.append(
                _diag(
                    "MAPPINGS_LOAD_FAILED",
                    f"Failed to load mappings '{self._mappings_path}': {type(exc).__name__}: {exc}",
                    "package.mappings",
                )
            )
            return None, total_decompressed

    def _expand_blueprint_prerequisite_closure(
        self,
        target_indices: set[int],
        *,
        objects: list[ObjectRecord],
        export_map: list[ObjectExport],
        max_exports: int = 256,
    ) -> set[int]:
        """Add graph-container/node/CDO prerequisites for selected Blueprint-family owners.

        ``object_ids`` remains an output filter: the returned document still
        exposes only requested objects; this set only widens which exports
        receive property/byte accounting so graph decode is selection-stable.

        Expansion covers direct graph-like children of the family seed, every
        node export under those graphs (K2 identity lives on the node property
        bag), and matching Default__ CDOs. ``max_exports`` keeps large
        AnimBlueprint selections bounded instead of parsing the whole package
        graph tree per selection.
        """
        if not target_indices or len(target_indices) >= len(export_map):
            return target_indices

        family = {
            i
            for i, obj in enumerate(objects)
            if i in target_indices and (obj.class_name or "") in _BLUEPRINT_FAMILY_CLASSES
        }
        if not family:
            return target_indices

        selected = set(target_indices)

        def _is_graph_like(class_name: str) -> bool:
            name = class_name or ""
            return name.endswith("Graph") or name in {
                "EdGraph",
                "UEdGraph",
                "AnimationBlueprint",
            }

        # One hop: direct outer=seed graph containers (and their direct graph children).
        added = 0
        graph_containers: set[int] = set()
        for i, exp in enumerate(export_map):
            if added >= max_exports:
                break
            if i in selected:
                continue
            outer = exp.outer_index
            outer_idx = getattr(outer, "index", 0) if outer is not None else 0
            if outer_idx <= 0:
                continue
            parent = outer_idx - 1
            if parent in family or parent in selected:
                obj = objects[i] if i < len(objects) else None
                class_name = (obj.class_name if obj else "") or ""
                if parent in family or _is_graph_like(class_name):
                    selected.add(i)
                    added += 1
                    if _is_graph_like(class_name):
                        graph_containers.add(i)

        # Second hop: every export whose outer is a selected graph container —
        # node exports (K2Node_*) carry FunctionReference/EventReference bags
        # that K2 metadata enrichment needs for selected-vs-full parity.
        for i, exp in enumerate(export_map):
            if added >= max_exports:
                break
            if i in selected or i in family:
                continue
            outer = exp.outer_index
            outer_idx = getattr(outer, "index", 0) if outer is not None else 0
            if outer_idx <= 0:
                continue
            parent = outer_idx - 1
            if parent in graph_containers or (
                parent in selected and _is_graph_like((objects[parent].class_name if parent < len(objects) else "") or "")
            ):
                selected.add(i)
                added += 1

        # Export-table CDO: Default__X whose class is a selected generated class.
        selected_ids = {f"export:{i}" for i in selected}
        for i, exp in enumerate(export_map):
            if i in selected or added >= max_exports:
                break
            if not exp.object_name.startswith("Default__"):
                continue
            cls = _package_index_to_id(exp.class_index)
            if cls in selected_ids:
                selected.add(i)
                added += 1
        return selected

    def _parse_requested_object_properties(
        self,
        archive: PackageArchive,
        objects: list[ObjectRecord],
        export_map: list[ObjectExport],
        import_map: list[ObjectImport],
        name_map: list[str],
        summary: PackageFileSummary,
        object_ids: Sequence[str] | None,
        diagnostics: list[Diagnostic],
        mappings: Any | None = None,
        depth: Literal["package", "object", "asset", "decode"] = "object",
    ) -> dict[str, dict[str, Any]]:
        """Parse properties for requested objects at depth >= object.

        No v1 class-handler dispatch happens here: v2 handlers consume the
        normalized property bag plus the bounded extras this method slices
        out itself.

        Returns ``extras``: maps object id to per-class bounded data
        (currently ``table_rows`` for DataTable/CurveTable/StringTable).

        If object_ids is None, parses ALL objects.
        Each export's serial region is bounded via _read_range enforced inside PackageArchive reads.
        Caught property-parse errors (bounded exception set) on one export do
        not prevent parsing of others; unexpected exception types propagate.
        """
        from .properties.tagged import TaggedPropertyReader

        # Determine which exports to parse
        target_indices: set[int] | None = None
        if object_ids is not None:
            target_indices = set()
            for oid in object_ids:
                if oid.startswith("export:"):
                    with contextlib.suppress(ValueError, IndexError):
                        target_indices.add(int(oid.split(":")[1]))
            # Bounded prerequisite closure only when graphs/bytecode will be
            # decoded: object/asset depth must keep `object_ids` as the exact
            # property-parse set (plan Task 6 / audit). Decode expands graph
            # containers, node exports, and generated-class/CDO references
            # needed for selection-stable graph results.
            if depth == "decode":
                target_indices = self._expand_blueprint_prerequisite_closure(
                    target_indices,
                    objects=objects,
                    export_map=export_map,
                )
            # Material dependency closure: selecting a Material export must also
            # parse its MaterialExpression* / MaterialEditorOnlyData bags so the
            # expression graph is available without selecting every export.
            material_roots = {
                i
                for i in target_indices
                if i < len(objects) and (objects[i].class_name or "") == "Material"
            }
            if material_roots:
                for j, child in enumerate(objects):
                    if j in target_indices:
                        continue
                    cn = child.class_name or ""
                    if cn != "MaterialEditorOnlyData" and not cn.startswith("MaterialExpression"):
                        continue
                    outer = child.outer_ref
                    if outer is not None and outer.table == "export" and outer.index in material_roots:
                        target_indices.add(j)

        extras: dict[str, dict[str, Any]] = {}
        tagged_reader = TaggedPropertyReader()

        for i, obj in enumerate(objects):
            if target_indices is not None and i not in target_indices:
                continue
            if not obj.serial_region or obj.serial_region.size <= 0:
                obj.properties = PropertyBag()
                continue

            exp = export_map[i]
            serial_end = exp.serial_offset + exp.serial_size
            script_start, script_end, script_known = script_property_region(exp)
            prop_range_end = script_end if script_known else serial_end
            prev_range = archive.set_read_range((script_start, prop_range_end))
            archive._current_object_id = obj.id
            try:
                # Sole public tagged entry: TaggedPropertyReader owns the
                # export-level stream; value dispatch stays in property_parser.
                raw_props = tagged_reader.read_export(
                    export=exp,
                    archive=archive,
                    summary=summary,
                    name_map=name_map,
                    export_map=export_map,
                    import_map=import_map,
                    mappings=mappings,
                    game=self._game,
                    tolerant=self._tolerant,
                )
                overrun = archive.tell() - prop_range_end
                obj.properties = normalize_property_bag(
                    raw_props,
                    package_source=self._package_source,
                    object_id=obj.id,
                )
                cn = obj.class_name or ""
                uses_unversioned = bool(getattr(summary, "package_flags", 0) & PKG_UnversionedProperties)
                # The export map pins the tagged stream; trust it over however far the
                # walk happened to get, then step over the GUID field that follows it so
                # the class-native payload is read at its real start.
                payload_start = archive.tell()
                if overrun <= 0 and not uses_unversioned:
                    # The optional-Guid field follows the tagged stream for every versioned
                    # save, so it is stepped over even when the export map records no script
                    # region (UE 5.3 and earlier).
                    if script_known:
                        archive.set_read_range((script_end, serial_end))
                        archive.seek(script_end)
                    payload_start = _skip_optional_object_guid(archive, serial_end)
                    archive.set_read_range((payload_start, serial_end))
                if overrun <= 0 and cn in _TABLE_CLASSES:
                    extras[obj.id] = {
                        "table_rows": _read_table_rows(
                            archive,
                            serial_end,
                            name_map,
                            obj.id,
                            diagnostics,
                            curve_table=cn == "CurveTable",
                        )
                    }
                elif overrun <= 0 and cn == "StringTable":
                    extras[obj.id] = {
                        "string_table": _read_string_table(
                            archive, obj.id, diagnostics, _string_table_has_dev_notes(summary)
                        )
                    }
                elif overrun <= 0 and cn not in _TABLE_CLASSES and cn != "StringTable" and archive.tell() < serial_end:
                    # Properties ended early but the export still has bytes: a
                    # class raw trailer (e.g. UPhysicsAsset::Serialize writes
                    # CollisionDisableTable after the tagged properties) we do
                    # not decode yet. Preserve them and say so -- never silently
                    # skip and claim coverage (#638). Exports may also carry a
                    # short all-zero alignment pad at their end; that is not a
                    # trailer worth reporting.
                    remaining = serial_end - archive.tell()
                    padded = remaining <= 16 and not any(archive.read(remaining))
                    if not padded:
                        diagnostics.append(
                            _diag(
                                "EXPORT_TRAILING_BYTES_UNCONSUMED",
                                (
                                    f"Export {i} ({obj.name}) leaves {remaining} undecoded "
                                    f"bytes after the tagged properties (class {cn})"
                                ),
                                "objects.export",
                                object_id=obj.id,
                                size=remaining,
                                reason=classify_trailing_reason(
                                    TrailingContext(
                                        class_name=cn,
                                        object_name=obj.name,
                                        outer_name=_resolve_outer_name(obj, objects, import_map),
                                    )
                                ),
                            )
                        )
                if overrun > 0:
                    obj.status = ObjectStatus(parse="partial", semantic=obj.status.semantic)
                    diagnostics.append(
                        _diag(
                            "EXPORT_PROPERTY_BOUNDS_EXCEEDED",
                            (
                                f"Export {i} ({obj.name}) property parse ran "
                                f"{overrun} bytes past serial_end {serial_end}"
                            ),
                            "properties.tagged",
                            object_id=obj.id,
                        )
                    )

            except ExportBoundsExceeded as e:
                obj.properties = PropertyBag()
                obj.status = ObjectStatus(parse="partial", semantic=obj.status.semantic)
                diagnostics.append(
                    _diag(
                        "EXPORT_PROPERTY_BOUNDS_EXCEEDED",
                        f"Export {i} ({obj.name}) read exceeded serial bound: {e}",
                        "properties.tagged",
                        object_id=obj.id,
                    )
                )
            except (ParseError, EOFError, struct.error, ValueError, UnicodeError) as e:
                obj.properties = PropertyBag()
                obj.status = ObjectStatus(parse="partial", semantic=obj.status.semantic)
                diagnostics.append(
                    _diag(
                        "EXPORT_PROPERTY_PARSE_FAILED",
                        f"Export {i} ({obj.name}) property parse failed: {type(e).__name__}: {e}",
                        "properties.tagged",
                        object_id=obj.id,
                    )
                )
            finally:
                archive._current_object_id = ""
                archive.set_read_range(prev_range)

        return extras

    def _attach_byte_accounting(self, objects: Sequence[ObjectRecord], diagnostics: list[Diagnostic]) -> Any:
        """Tile every requested export serial range with non-overlapping leaves."""
        from ..models.byte_ranges import ByteAccounting, tile_export_scope

        accounting = ByteAccounting()
        source = self._package_source
        for obj in objects:
            if not obj.serial_region or obj.serial_region.size <= 0:
                continue
            decoded = []
            if obj.properties:
                for entry in obj.properties.entries:
                    for region in (entry.tag_region, entry.value_region):
                        if region is not None and region.size > 0:
                            decoded.append(region)
            active_source = source
            if active_source is None:
                # Per-export virtual tiling — never reuse another export's source_id.
                source_id = obj.serial_region.source_id or "package"

                class _Identity:
                    def __init__(self, sid: str) -> None:
                        self._sid = sid

                    def map_range(self, offset: int, size: int, _sid: str | None = None):
                        return [(_sid or self._sid, offset, size)]

                active_source = _Identity(source_id)
            try:
                scope = tile_export_scope(
                    obj.id,
                    obj.serial_region.start,
                    obj.serial_region.size,
                    decoded,
                    active_source,
                )
                accounting.scopes[obj.id] = scope
            except ValueError as exc:
                diagnostics.append(
                    _diag(
                        "BYTE_ACCOUNTING_INVALID",
                        str(exc),
                        "objects.export",
                        object_id=obj.id,
                        effect="semantic_loss",
                        reason="unexpected",
                    )
                )
        return accounting

    def _build_minimal_document(
        self,
        summary: PackageFileSummary | None,
        diagnostics: list[Diagnostic],
    ) -> PackageDocument:
        """Build a minimal PackageDocument when parsing fails early."""
        from ..models.byte_ranges import ByteAccounting

        package_info = PackageInfo(name="", layout="legacy")
        if summary:
            package_info = _build_package_info_from_summary(summary, [], source_path=self._main_path)

        return PackageDocument(
            source=_build_source_info(self._main_path),
            package=package_info,
            diagnostics=diagnostics,
            byte_accounting=ByteAccounting(),
        )


# DataTable-family rows are serialized after the tagged properties as
# NumRows(i32) + per-row FName(Index,Number) + row value (tagged property
# stream terminated by the None tag, no int32 size prefix).
# UE source: Engine/Source/Runtime/Engine/Private/DataTable.cpp LoadStructData.
# StringTable is NOT this layout — it uses the FStringTable trailer below (#615).
_TABLE_CLASSES = ("DataTable", "CurveTable")

# ECurveTableMode (Engine/Source/Runtime/Engine/Classes/Engine/CurveTable.h).
_CURVE_TABLE_MODES = {0: "Empty", 1: "SimpleCurves", 2: "RichCurves"}


def _skip_optional_object_guid(archive: PackageArchive, serial_end: int) -> int:
    """Step over the optional ``Guid`` field UE writes after the tagged properties.

    ``UObject::Serialize`` calls ``FLazyObjectPtr::PossiblySerializeObjectGuid`` after
    ``MarkScriptSerializationEnd`` (``Obj.cpp:1886`` vs ``:2113``). That enters an optional
    structured-archive field through ``FBinaryArchiveFormatter::TryEnterField``, which writes
    its condition as an archive bool -- 4 bytes -- and only then the 16-byte
    ``FUniqueObjectGuid`` when set (``LazyObjectPtr.cpp:116-133``,
    ``Formatters/BinaryArchiveFormatter.h:113-121``).

    Class-native payloads start after it, so reading a DataTable/CurveTable row block at the
    script-region end lands 4 bytes early. Returns the payload start.
    """
    pos = archive.tell()
    if serial_end - pos < 4:
        return pos
    flag = archive.read_i32()
    if flag > 1:
        # An archive bool is 0 or 1. Anything else means we are not on the field
        # boundary, so refuse to consume it rather than shift the payload by 4 bytes.
        archive.seek(pos)
        return pos
    if flag and serial_end - archive.tell() >= 16:
        archive.read(16)
    return archive.tell()


_MAX_TABLE_BLOB = 64 * 1024 * 1024  # bounded read; larger tables report partial
_MAX_TABLE_ROWS = 100000  # garbage row counts are rejected, not trusted


_BLUEPRINT_FAMILY_CLASSES = frozenset(
    {"Blueprint", "AnimBlueprint", "BlueprintGeneratedClass", "AnimBlueprintGeneratedClass"}
)

# Hard safety cap on graph-owner outer-chain traversal. The export-table size
# bounds real chains; this named limit stops malformed data even on huge tables.
MAX_GRAPH_OWNER_HOPS = 256


def _resolve_graph_owner(export_idx: int, export_map: list[ObjectExport], objects: list[ObjectRecord]) -> str | None:
    """Walk a graph export's outer chain to its Blueprint-family owner.

    Graph exports' outer is the UBlueprint asset object (verified on the
    tracked fixtures: StackOBot EventGraph export:4 outer=export:0,
    ABP_RifleAnimLayers EventGraph export:3 outer=export:1). Walks the raw
    ``outer_index`` chain (FPackageIndex: positive = export index + 1,
    negative = import) with a visited-export set so cycles terminate, bounded
    by ``min(len(export_map), MAX_GRAPH_OWNER_HOPS)``. ALS chains of nine hops
    must resolve; a partial chain never guesses an owner. Returns None when no
    family export is on the chain, an index is invalid, a cycle repeats, or
    the bound is reached.
    """
    by_index = {o.table_index: o for o in objects}
    idx = export_idx
    visited: set[int] = set()
    bound = min(len(export_map), MAX_GRAPH_OWNER_HOPS) if export_map else MAX_GRAPH_OWNER_HOPS
    for _ in range(bound):
        if idx in visited:
            return None  # cyclic outer chain — never resolve through a loop
        visited.add(idx)
        rec = by_index.get(idx)
        if rec is None:
            return None
        if (rec.class_name or "") in _BLUEPRINT_FAMILY_CLASSES:
            return rec.id
        if idx >= len(export_map):
            return None
        outer = export_map[idx].outer_index
        value = outer.index if outer is not None else 0
        if value > 0:  # export ref (1-based)
            idx = value - 1
        else:
            return None  # import or null outer cannot own a package graph
    return None


def _attach_blueprint_graph_extras(
    archive,
    summary,
    name_map,
    import_map,
    export_map,
    objects,
    extras,
    diagnostics,
    *,
    object_ids: Sequence[str] | None,
) -> None:
    """Parse all graphs at decode depth and route them to owning exports.

    Runs only when the caller's object selection reaches a Blueprint-family
    export (decode of e.g. a single Texture must not pay for the package's
    graphs). One bad graph never aborts the pass: the conversion module emits
    a graph dict with parse_errors instead, and this helper drops it with a
    diagnostic (the export id stays addressable).
    """
    from ..serializers.blueprint_graph import read_blueprint_graphs

    family = {o.id for o in objects if (o.class_name or "") in _BLUEPRINT_FAMILY_CLASSES}
    if not family:
        return
    if object_ids is not None and not family.intersection(object_ids):
        return
    graphs = read_blueprint_graphs(archive, summary, name_map, import_map, export_map)
    owners: dict[str, list[dict]] = {}
    for graph in graphs:
        parse_errors = graph.get("parse_errors") or []
        if parse_errors and not graph.get("nodes"):
            # Whole-graph failure: the conversion emitted an error dict with no
            # nodes. Drop it with a diagnostic; the export id stays addressable.
            diagnostics.append(
                _diag(
                    "BLUEPRINT_GRAPH_PARSE_FAILED",
                    f"graph export {graph['id']}: {parse_errors[0]}",
                    "semantic.blueprint",
                    object_id=graph["id"],
                    effect=None,
                )
            )
            continue
        if parse_errors:
            # Node-level partial failures: the graph stays attached and
            # addressable; each fallback node is already in the projection.
            diagnostics.append(
                _diag(
                    "BLUEPRINT_GRAPH_NODE_PARTIAL",
                    (
                        f"graph export {graph['id']}: {len(parse_errors)} node-level "
                        f"recovery(ies); first: {parse_errors[0]}"
                    ),
                    "semantic.blueprint",
                    object_id=graph["id"],
                    effect="semantic_loss",
                )
            )
        try:
            export_idx = int(graph["id"].split(":")[1])
        except (ValueError, IndexError):
            diagnostics.append(
                _diag(
                    "BLUEPRINT_GRAPH_ID_INVALID",
                    f"graph export {graph['id']} has unparseable export index",
                    "semantic.blueprint",
                    object_id=graph["id"],
                    effect=None,
                )
            )
            continue
        owner = _resolve_graph_owner(export_idx, export_map, objects)
        if owner is None:
            diagnostics.append(
                _diag(
                    "BLUEPRINT_GRAPH_OWNER_UNRESOLVED",
                    f"graph export {graph['id']} has no Blueprint-family owner",
                    "semantic.blueprint",
                    object_id=graph["id"],
                    effect=None,
                )
            )
            continue
        owners.setdefault(owner, []).append(graph)
    total_unresolved = sum(g.get("unresolved_links", 0) for grouped in owners.values() for g in grouped)
    if total_unresolved:
        diagnostics.append(
            _diag(
                "BLUEPRINT_EXTERNAL_PIN_LINK",
                (
                    f"{total_unresolved} pin link(s) did not resolve to a parsed pin "
                    f"(cross-package links are not decoded)"
                ),
                "semantic.blueprint",
                effect=None,
            )
        )
    total_ambiguous = sum(g.get("ambiguous_links", 0) for grouped in owners.values() for g in grouped)
    if total_ambiguous:
        diagnostics.append(
            _diag(
                "BLUEPRINT_LINK_AMBIGUOUS",
                (
                    f"{total_ambiguous} pin link(s) had multiple GUID candidates and no "
                    f"owning-node identity; left unresolved rather than guessed"
                ),
                "semantic.blueprint",
                effect="semantic_loss",
            )
        )
    for grouped in owners.values():
        for graph in grouped:
            graph.pop("unresolved_links", None)
            graph.pop("ambiguous_links", None)
    for owner_id, owner_graphs in owners.items():
        entry = extras.setdefault(owner_id, {})
        entry["graphs"] = owner_graphs
        # Interfaces: BPInterfaceDescription.Interface is a struct-nested
        # negative FPackageIndex (ObjectResource.h convention) that the
        # property normalizer does not resolve — resolve it here against the
        # import map. Class name for display: import.object_name.
        obj = next((o for o in objects if o.id == owner_id), None)
        if obj is not None and obj.properties:
            ifaces = obj.properties.get("ImplementedInterfaces") or obj.properties.get("Interfaces")
            raw = ifaces.get("value") if isinstance(ifaces, dict) else None
            names: list[str] = []
            if isinstance(raw, list):
                for desc in raw:
                    ref = desc.get("fields", {}).get("Interface") if isinstance(desc, dict) else None
                    if isinstance(ref, int) and ref < 0:
                        imp = import_map[-ref - 1]
                        names.append(imp.object_name)
            entry["interfaces"] = names


def _function_analysis_from_result(kr: Any, owner_object_id: str) -> Any:
    """Typed FunctionAnalysis for one Kismet result (plan Task 8).

    Reuses the already-decoded ``kr.expressions`` (no second binary pass) and
    the same normalize/CFG builders the bridge used, keeping the typed IR the
    correlation layer needs while the archive inputs are still open.
    """
    from ..models.analysis import BytecodeStatus, FunctionAnalysis
    from .blueprint.bytecode import normalize_instructions
    from .blueprint.control_flow import build_cfg

    instructions = []
    cfg = build_cfg([])
    if kr.expressions:
        instructions = normalize_instructions(kr.expressions)
        cfg = build_cfg(instructions)
    reads: set[str] = set()
    writes: set[str] = set()
    calls: list[str] = []
    for item in instructions:
        reads.update(item.reads)
        writes.update(item.writes)
        if item.call_target:
            calls.append(item.call_target)
    status = kr.bytecode_status
    if status not in get_args(BytecodeStatus):
        status = "unavailable"
    diagnostics = list(getattr(kr, "errors", None) or [])
    if status == "unavailable" and not diagnostics and getattr(kr, "error_code", None):
        diagnostics.append(
            _diag(
                kr.error_code,
                kr.error_message or "kismet function unavailable",
                "semantic.kismet",
                object_id=kr.object_id or None,
                effect="semantic_loss",
            )
        )
    base = FunctionAnalysis(
        object_id=kr.object_id or (
            f"export:{kr.export_index}" if getattr(kr, "export_index", -1) >= 0 else ""
        ),
        owner_object_id=owner_object_id,
        name=kr.function_name,
        function_name=kr.function_name,
        script_source_range=kr.script_source_range,
        expression_count=len(kr.expressions),
        entrypoint=None,
        instructions=instructions,
        cfg=cfg,
        reads=reads,
        writes=writes,
        calls=calls,
        bytecode_status=status,  # type: ignore[arg-type]
        diagnostics=diagnostics,
    )
    return base


def _attach_kismet_extras(
    *,
    archive,
    summary,
    name_map,
    import_map,
    export_map,
    objects,
    extras,
    diagnostics,
    object_ids,
    include_ir: bool = False,
) -> None:
    """Attach Kismet function results to Blueprint-family owners (asset+decode)."""
    from dataclasses import replace as _replace

    family = {o.id for o in objects if (o.class_name or "") in _BLUEPRINT_FAMILY_CLASSES}
    if not family:
        return
    if object_ids is not None and not family.intersection(object_ids):
        return
    try:
        from ..kismet.decompile_bridge import extract_kismet_decompiled

        kismet_results = extract_kismet_decompiled(
            archive,
            summary,
            name_map,
            import_map,
            export_map,
            tolerant=True,
        )
        if kismet_results:
            # Identity-first attachment: use the bridge's export_index
            # directly; never re-match by display function name (which
            # collides across same-named exports). Attach to every
            # Blueprint-family export on the outer chain so both the asset
            # export and its GeneratedClass expose the function list.
            kismet_by_export: dict[str, list[dict]] = {}
            kismet_ir_by_export: dict[str, list[Any]] = {}
            for kr in kismet_results:
                exp_idx = getattr(kr, "export_index", -1)
                if exp_idx is None or exp_idx < 0 or exp_idx >= len(export_map):
                    continue
                payload = kr.to_dict()
                base_ir = _function_analysis_from_result(kr, "") if include_ir else None
                recorded = False
                idx = exp_idx
                seen: set[int] = set()
                bound = min(len(export_map), MAX_GRAPH_OWNER_HOPS) if export_map else MAX_GRAPH_OWNER_HOPS
                for _ in range(bound):
                    if idx in seen or idx < 0 or idx >= len(export_map):
                        break
                    seen.add(idx)
                    rec_obj = next((o for o in objects if o.table_index == idx), None)
                    if rec_obj is not None and (rec_obj.class_name or "") in _BLUEPRINT_FAMILY_CLASSES:
                        kismet_by_export.setdefault(rec_obj.id, []).append(payload)
                        if base_ir is not None:
                            kismet_ir_by_export.setdefault(rec_obj.id, []).append(
                                _replace(base_ir, owner_object_id=rec_obj.id)
                            )
                        recorded = True
                    outer = export_map[idx].outer_index
                    value = outer.index if outer is not None else 0
                    if value > 0:
                        idx = value - 1
                    else:
                        break
                if not recorded:
                    owner = _resolve_graph_owner(exp_idx, export_map, objects)
                    if owner is not None:
                        kismet_by_export.setdefault(owner, []).append(payload)
                        if base_ir is not None:
                            kismet_ir_by_export.setdefault(owner, []).append(
                                _replace(base_ir, owner_object_id=owner)
                            )
            for owner_id, funcs in kismet_by_export.items():
                entry = extras.setdefault(owner_id, {})
                entry["kismet"] = funcs
                owner_ir = kismet_ir_by_export.get(owner_id) or []
                if owner_ir:
                    entry["kismet_ir"] = owner_ir
            # A BlueprintGeneratedClass has a null outer; mirror its function
            # list onto Blueprint asset exports whose GeneratedClass property
            # points at it so the asset-level K0 view stays complete.
            for owner_id, funcs in list(kismet_by_export.items()):
                owner_obj = next((o for o in objects if o.id == owner_id), None)
                if owner_obj is None or (owner_obj.class_name or "") != "BlueprintGeneratedClass":
                    continue
                gc_pkg_index = owner_obj.table_index + 1
                for obj in objects:
                    if (obj.class_name or "") not in _BLUEPRINT_FAMILY_CLASSES:
                        continue
                    if (obj.class_name or "") == "BlueprintGeneratedClass":
                        continue
                    gen = (obj.properties or {}).get("GeneratedClass")
                    gen_value = gen.get("value") if isinstance(gen, dict) else None
                    if isinstance(gen_value, dict):
                        gen_value = gen_value.get("value")
                    if gen_value == gc_pkg_index:
                        mirror = extras.setdefault(obj.id, {})
                        mirror["kismet"] = funcs
                        source_ir = kismet_ir_by_export.get(owner_id) or []
                        if source_ir:
                            mirror["kismet_ir"] = [
                                _replace(item, owner_object_id=obj.id) for item in source_ir
                            ]
    except Exception as exc:
        diagnostics.append(
            _diag("KISMET_DECOMPILE_FAILED", f"Kismet decompile pass failed: {exc}", "semantic.kismet", effect=None)
        )


def _read_table_rows(
    archive: PackageArchive,
    serial_end: int,
    name_map: list[str],
    object_id: str,
    diagnostics: list[Diagnostic],
    *,
    curve_table: bool = False,
) -> dict[str, Any]:
    """Parse NumRows + row names from the bounded payload after properties.

    The archive is positioned at the payload start and its ``_read_range``
    is the export's serial end, so the slice read can never escape the
    export.  Anything that does not fit is reported as ``complete: False``
    with a diagnostic, never silently truncated.

    ``curve_table`` selects the UCurveTable row block, which inserts the
    ``ECurveTableMode`` byte between the row count and the rows
    (``CurveTable.cpp:112-123`` save branch at ``:202-235``):
    ``int32 NumRows``, ``uint8 CurveTableMode``, then per row ``FName`` +
    ``FSimpleCurve``/``FRichCurve`` tagged stream. DataTable has no mode byte
    (``DataTable.cpp`` ``SaveRowData``).
    """
    result: dict[str, Any] = {
        "row_count": 0,
        "row_names": [],
        "rows": [],
        "curve_table_mode": None,
        "row_bytes_consumed": 0,
        "complete": False,
    }
    remaining = serial_end - archive.tell()
    if remaining < 4:
        return result
    blob = archive.read(min(remaining, _MAX_TABLE_BLOB))
    (row_count,) = struct.unpack_from("<i", blob, 0)
    if row_count < 0 or row_count > _MAX_TABLE_ROWS:
        diagnostics.append(
            _diag(
                "TABLE_ROW_COUNT_INVALID",
                f"{object_id}: table row count {row_count} outside sane range",
                "payload.table",
                object_id=object_id,
            )
        )
        return result
    header = 4
    if curve_table:
        if len(blob) < 5:
            return result
        mode_raw = blob[4]
        result["curve_table_mode"] = _CURVE_TABLE_MODES.get(mode_raw, f"Unknown({mode_raw})")
        header = 5
    names: list[str] = []
    rows_out: list[dict[str, Any]] = []
    payload = ByteArchive(blob[header:])
    # Tag reads must use the real package layout version, not a fresh default.
    payload._file_version_ue4 = getattr(archive, "_file_version_ue4", 0)
    payload._file_version_ue5 = getattr(archive, "_file_version_ue5", 0)
    limit = len(blob) - header
    for _ in range(row_count):
        if payload.tell() + 8 > limit:
            break
        idx, number = struct.unpack_from("<II", blob, header + payload.tell())
        payload.seek(payload.tell() + 8)
        if not 0 <= idx < len(name_map):
            display_name = f"<row:{idx}>"
        elif number > 0:
            # NAME_INTERNAL_TO_EXTERNAL: the on-disk Number is internal, so the
            # display instance is Number-1 (LinkerLoad.h, same rule as FArchive.read_name).
            display_name = f"{name_map[idx]}_{number - 1}"
        else:
            display_name = name_map[idx]
        names.append(display_name)
        # Each row is a tagged property stream terminated by the None tag (DataTable.cpp
        # LoadStructData -> SerializeItem; versioned path = SerializeTaggedProperties,
        # CurveTable.cpp:112-171 same). Collect field name/type/size descriptors
        # (values not decoded yet); stop at None.
        row_fields: dict[str, Any] = {}
        while payload.tell() < limit:
            header_pos = payload.tell()
            try:
                t = read_property_tag(payload, name_map)
            except ParseError:
                payload.seek(header_pos)
                break
            if t.name == "None":
                break
            if t.value_end_offset is None or t.value_end_offset <= payload.tell():
                # Non-advancing or size-less tag: malformed row. Stop rather than seek()
                # on None, which would raise out of a recoverable parse path.
                payload.seek(header_pos)
                break
            row_fields[t.name] = {"type": t.type, "size": int(getattr(t, "size", 0) or 0)}
            payload.seek(t.value_end_offset)
        rows_out.append({"name": display_name, "fields": row_fields})
    complete = len(names) == row_count
    # The row block is the whole payload: NumRows followed by exactly that many
    # (FName + tagged row stream) records, each ending on its own None tag. Bytes
    # left over mean the anchor or a row walk drifted, which is never reportable
    # as decoded rows.
    residue = limit - payload.tell()
    if complete and residue:
        complete = False
        diagnostics.append(
            _diag(
                "TABLE_PAYLOAD_RESIDUE",
                (
                    f"{object_id}: {residue} undecoded byte(s) after {row_count} row(s) in the "
                    f"table payload ({limit} bytes); row data not marked complete"
                ),
                "payload.table",
                object_id=object_id,
                reason="conservative_complete",
            )
        )
    if not complete:
        diagnostics.append(
            _diag(
                "TABLE_ROWS_TRUNCATED",
                (
                    f"{object_id}: parsed {len(names)}/{row_count} rows within the "
                    f"export payload ({min(remaining, _MAX_TABLE_BLOB)} bytes sliced)"
                ),
                "payload.table",
                object_id=object_id,
                reason="conservative_complete",
            )
        )
    result["row_count"] = len(names)
    result["row_names"] = names
    result["rows"] = rows_out[:row_count]
    result["row_bytes_consumed"] = payload.tell()
    result["complete"] = complete
    return result


# StringTable assets serialize an FStringTable trailer right after the
# tagged properties. UE source:
# Engine/Source/Runtime/Core/Private/Internationalization/StringTableCore.cpp
# FStringTable::Serialize, reached from
# Engine/Source/Runtime/Engine/Private/Internationalization/StringTable.cpp
# UStringTable::Serialize (Super::Serialize then StringTable->Serialize(Ar)).
# Layout: FString Namespace, int32 NumEntries, then NumEntries x
# (FString Key, FString SourceString[, FString DevNotes]). On save the
# editor writes DevNotes when not cooking and editor-only data is not
# filtered (StringTableCore.cpp, no version check at write time); on
# load they are read only when FFortniteMainBranchObjectVersion >=
# AddDevNotesToFText (260) and editor-only data is not filtered — that
# read gate is evaluated per package in _string_table_has_dev_notes. The
# trailing key->(FName,FString) metadata map is not parsed here.
# Corroborated (not proof): UAssetAPI StringTableExport.Read,
# CUE4Parse FStringTable ctor.


def _string_table_has_dev_notes(summary: PackageFileSummary) -> bool:
    """True when the editor-saved trailer wrote per-entry DevNotes strings."""
    if summary.package_flags & PKG_FilterEditorOnly:
        return False
    return get_custom_version(summary, FORTNITE_GUID) >= 260


def _read_string_table(
    archive: PackageArchive,
    object_id: str,
    diagnostics: list[Diagnostic],
    dev_notes: bool,
) -> dict[str, Any]:
    """Parse the bounded FStringTable trailer (namespace + key/value entries).

    The archive is positioned at the trailer start with its ``_read_range``
    at the export's serial end, so a corrupt table cannot escape the export.
    Anything unreadable ends up as ``complete: False`` with a diagnostic,
    never a silently truncated table.

    Key format note: FTextKey in StringTable packages is serialized as a raw
    null-terminated ANSI string (byte-at-a-time), NOT a length-prefixed
    FString.  The namespace and values remain FStrings.  This matches the
    binary layout observed in real UE4.27/5.2 editor-saved StringTable assets
    and corroborates CUE4Parse's ``FStringTable`` read path where the archive
    position yields null-terminated keys.

    Alignment note: when the serialization_control byte is absent (UE4
    content), the archive position after property parsing may be 1 byte
    before the actual StringTable trailer start.  The trailer format has a
    1-byte prefix (observed as 0x00) that is not part of the None tag.
    We detect this by checking whether the parsed entry count looks sane
    and shift by 1 byte if not.
    """
    result: dict[str, Any] = {"namespace": "", "entry_count": 0, "entries": [], "complete": False}
    try:
        result["namespace"] = archive.read_fstring()
        entry_count = archive.read_i32()
        if entry_count < 0 or entry_count > _MAX_TABLE_ROWS:
            diagnostics.append(
                _diag(
                    "TABLE_ENTRY_COUNT_INVALID",
                    f"{object_id}: string table entry count {entry_count} outside sane range",
                    "payload.string_table",
                    object_id=object_id,
                )
            )
            return result
        result["entry_count"] = entry_count
        # Probe: if the first key fails to read (non-standard format with
        # extra fields between count and entries), skip 16 bytes and retry.
        # Observed in UE4.27 StringTable assets where a null-terminated
        # identifier + metadata int32 precedes the actual entry data.
        probe_pos = archive.tell()
        probe_key = archive.read_fstring()
        if not probe_key and archive.tell() == probe_pos:
            # read_fstring rolled back — non-standard format; skip prefix
            archive.seek(probe_pos + 16)
            first_key = None
        else:
            # Good read — store first key for first iteration
            first_key = probe_key
        for _ in range(entry_count):
            key = first_key if first_key is not None else archive.read_fstring()
            first_key = None  # only used once
            value = archive.read_fstring()
            if dev_notes:
                archive.read_fstring()  # DevNotes, parsed but not surfaced
            result["entries"].append({"key": key, "value": value})
        result["complete"] = True
    except (ExportBoundsExceeded, ParseError, EOFError, struct.error, ValueError, UnicodeError) as e:
        diagnostics.append(
            _diag(
                "STRING_TABLE_TRUNCATED",
                (
                    f"{object_id}: string table trailer unreadable after "
                    f"{len(result['entries'])}/{result['entry_count']} entries: {type(e).__name__}: {e}"
                ),
                "payload.string_table",
                object_id=object_id,
            )
        )
    return result
