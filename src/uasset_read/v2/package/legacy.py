"""LegacyPackageReader — direct binary reader for legacy .uasset packages.

Reads package summary, name table, import/export maps, depends, and
preload dependencies directly from binary, building a PackageDocument
without going through the v1 pipeline.
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Any, Literal, Sequence

from ...archive import ByteArchive
from ...constants import PKG_FilterEditorOnly
from ...exceptions import ParseError, ExportBoundsExceeded
from ...memory_safety import ResourceBudget
from ...package import PackageArchive
from ...serializers.property_tags import read_property_tag
from ...serializers.object_resources import (
    ObjectExport,
    ObjectImport,
    PackageIndex,
    read_export_map,
    read_import_map,
    resolve_class_name,
)
from ...serializers.package_summary import (
    PackageFileSummary,
    read_depends_map,
    read_name_table,
    read_package_summary,
    read_preload_dependencies,
)
from ...v2.diagnostics import Diagnostic
from ...v2.handlers import run_handlers
from ...v2.document import PackageDocument, PackageInfo, SourceInfo, Summary
from ...v2.object_model import (
    Dependency,
    ObjectRecord,
    ObjectRef,
    ObjectStatus,
    Region,
    Relation,
    ROLES_ASSET,
    ROLES_CDO,
    ROLES_GENERATED_CLASS,
)
from ...v2.source import FileSource, SliceReader
from ...v2.version import MappingInfo, build_version_context_from_summary


def _make_package_archive(source: FileSource, tolerant: bool = False) -> PackageArchive:
    """Create a PackageArchive backed by a FileSource via SliceReader.

    Uses _init_archive_attrs (designed for non-file-backed archives) to
    initialize all FArchive attributes without opening a real file.
    """
    reader = SliceReader(source, 0, source.size())

    archive = object.__new__(PackageArchive)
    archive._init_archive_attrs(str(source._path), tolerant, hex_view=False)
    archive._main_archive = reader
    archive._uexp_archive = None
    archive._main_size = source.size()
    archive._uexp_size = 0
    archive._file_size = source.size()
    archive._pos = 0

    return archive


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
                Diagnostic(
                    severity="warning",
                    code="PRELOAD_DEPENDENCY_RANGE_INVALID",
                    message=f"Export {i} preload span [{start},{end}) exceeds preload array size {len(preload_deps)}",
                    stage="package.preload",
                    object_id=f"export:{i}",
                    recoverable=True,
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
        idx = int(raw_idx)
        limit = export_count if table == "export" else import_count
        if table not in ("export", "import") or idx >= limit:
            diagnostics.append(
                Diagnostic(
                    severity="warning",
                    code="RELATION_TARGET_OUT_OF_RANGE",
                    message=f"{rel.kind} target {rel.to_id} from {rel.from_id} exceeds {table} table size {limit}",
                    stage="package.relations",
                    object_id=rel.from_id,
                    recoverable=True,
                )
            )
            continue
        kept.append(rel)
    return kept, diagnostics


def _build_object_record_direct(
    export: ObjectExport,
    index: int,
    import_map: list[ObjectImport],
    export_map: list[ObjectExport],
) -> ObjectRecord:
    """Convert an ObjectExport to an ObjectRecord using direct binary data."""
    name = export.object_name
    b_is_asset = export.b_is_asset

    # Determine roles
    roles: list[str] = []
    if b_is_asset:
        roles.append(ROLES_ASSET)
    if name.startswith("Default__"):
        roles.append(ROLES_CDO)
    if name.endswith("_C") and not name.startswith("Default__"):
        roles.append(ROLES_GENERATED_CLASS)

    # Serial region
    serial_region = None
    if export.serial_size > 0:
        serial_region = Region(offset=export.serial_offset, size=export.serial_size)

    # Class name resolution
    class_name = resolve_class_name(export.class_index, import_map, export_map)

    # ObjectRef fields
    class_ref = _package_index_to_ref(export.class_index)
    outer_ref = _package_index_to_ref(export.outer_index)
    super_ref = _package_index_to_ref(export.super_index)
    template_ref = _package_index_to_ref(export.template_index)

    return ObjectRecord(
        id=f"export:{index}",
        table_index=index,
        name=name,
        class_name=class_name,
        class_ref=class_ref,
        outer_ref=outer_ref,
        super_ref=super_ref,
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
        recovered = sd.fallback != "stop_table"
        diagnostics.append(
            Diagnostic(
                severity=sev,
                code=sd.code,
                message=sd.message or sd.fallback,
                stage=sd.stage,
                object_id=sd.object_id or None,
                offset=sd.offset,
                effect="recovery" if recovered else "data_loss",
                recoverable=recovered,
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


class LegacyPackageReader:
    """Direct binary reader for legacy .uasset packages.

    Reads the binary format using existing serializers and builds
    a PackageDocument without going through the v1 pipeline.
    """

    def __init__(
        self,
        source: FileSource,
        *,
        tolerant: bool = True,
        mappings_path: str | None = None,
        game: str | None = None,
    ) -> None:
        self._source = source
        self._tolerant = tolerant
        self._mappings_path = mappings_path
        self._game = game

    def read(
        self,
        *,
        depth: Literal["package", "object", "asset", "decode"] = "package",
        object_ids: Sequence[str] | None = None,
    ) -> PackageDocument:
        """Read the package and return a PackageDocument.

        At depth="package", only the package structure is read (no object properties).
        """
        archive = _make_package_archive(self._source, self._tolerant)
        diagnostics: list[Diagnostic] = []

        try:
            # 0. Load the mappings provider once per document (mirrors v1
            # _init_parse_env); None + diagnostic when unloadable.
            budget = ResourceBudget()
            mappings_provider = self._load_mappings(budget, diagnostics)

            # 1. Read summary
            summary = read_package_summary(archive, budget)

            # Property tag format is version-gated; set the gates the same
            # way pipeline/stages.py does so UE5.0-5.2 tags don't fall into
            # the UE5.3+ FPropertyTypeName path (mirrors v1 behavior).
            archive._file_version_ue4 = summary.file_version_ue4
            archive._file_version_ue5 = summary.file_version_ue5

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

            # 6. Read depends map
            depends_map = read_depends_map(archive, summary, budget)

            # 7. Read preload dependencies
            preload_deps = read_preload_dependencies(archive, summary)

            # 8. Build ObjectRecords — ALL exports, no filtering
            objects = [_build_object_record_direct(exp, i, import_map, export_map) for i, exp in enumerate(export_map)]

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
                        relations.append(
                            Relation(kind="default_object_of", from_id=f"export:{i}", to_id=cls_id)
                        )

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

            # 11. Build dependencies from import map
            dependencies = [
                Dependency(
                    index=i,
                    class_name=imp.class_name,
                    object_name=imp.object_name,
                    package_name=imp.class_package,
                )
                for i, imp in enumerate(import_map)
            ]

            # 12. FArchive structured recoveries are merged in step 17c, after
            # property parsing has attributed them to their objects.

            # 13. Compute asset_object_ids
            asset_ids = tuple(obj.id for obj in objects if ROLES_ASSET in obj.roles)

            # 14. Build PackageInfo
            package_info = _build_package_info_from_summary(
                summary, name_map, source_path=str(self._source._path)
            )

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
                )

            # 17. Run asset handlers at depth >= asset
            if depth in ("asset", "decode"):
                context = build_version_context_from_summary(
                    summary,
                    package_layout="legacy",
                    game=self._game,
                    mappings=MappingInfo(path=self._mappings_path) if self._mappings_path else None,
                    depth=depth,
                )
                for obj in objects:
                    try:
                        semantic, cov, handler_diags = run_handlers(
                            obj, context, objects, (export_map, name_map, extras)
                        )
                        if semantic is not None:
                            obj.semantic = semantic
                        obj.coverage.extend(cov)
                        diagnostics.extend(handler_diags)
                    except Exception as exc:
                        diagnostics.append(
                            Diagnostic(
                                severity="warning",
                                code="HANDLER_FAILURE",
                                message=f"Handler error for {obj.id}: {exc}",
                                stage="semantic.handler",
                                object_id=obj.id,
                                recoverable=True,
                            )
                        )

            # 17b. Payloads stay deferred: real descriptors require
            # .uexp/.ubulk/.utoc/.ucas container support, so nothing is
            # emitted (the projection keeps an empty payloads list for
            # schema compatibility).

            # 17c. Merge FArchive structured recoveries (header maps +
            # property parsing) once every read has had its object context.
            _merge_archive_recoveries(archive, objects, diagnostics)

            # 18. Build SourceInfo
            source_info = _build_source_info(str(self._source._path))

            return PackageDocument(
                source=source_info,
                package=package_info,
                objects=objects,
                relations=relations,
                dependencies=dependencies,
                diagnostics=diagnostics,
                summary=summary_obj,
                depth=depth,
            )

        except ParseError as e:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="PACKAGE_READ_FAILED",
                    message=str(e),
                    stage="package.read",
                    recoverable=True,
                )
            )
            return self._build_minimal_document(None, diagnostics)
        finally:
            archive.close()

    def _load_mappings(self, budget: ResourceBudget, diagnostics: list[Diagnostic]) -> Any | None:
        """Build the mappings provider once per document (mirrors v1 _init_parse_env).

        The property decoder expects a loaded provider object, never a raw
        path string. On any load failure (missing file, bad magic, missing
        optional codec) returns None and records a MAPPINGS_LOAD_FAILED
        diagnostic; the parse continues and unversioned exports stay opaque.
        """
        if not self._mappings_path:
            return None
        try:
            # Lazy import mirrors v1 (pipeline/core.py, pipeline/stages.py):
            # the mappings module and its optional codecs must not become a
            # core-import dependency.
            from ...mappings import TypeMappingsProvider

            return TypeMappingsProvider.from_file(self._mappings_path, budget=budget)
        except Exception as exc:
            diagnostics.append(
                Diagnostic(
                    severity="warning",
                    code="MAPPINGS_LOAD_FAILED",
                    message=f"Failed to load mappings '{self._mappings_path}': {type(exc).__name__}: {exc}",
                    stage="package.mappings",
                    effect="semantic_loss",
                    recoverable=True,
                )
            )
            return None

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
        from ...parsers.property_parser import parse_properties_from_export
        from ...v2.properties import normalize_property_bag

        # Determine which exports to parse
        target_indices: set[int] | None = None
        if object_ids is not None:
            target_indices = set()
            for oid in object_ids:
                if oid.startswith("export:"):
                    try:
                        target_indices.add(int(oid.split(":")[1]))
                    except (ValueError, IndexError):
                        pass

        extras: dict[str, dict[str, Any]] = {}

        for i, obj in enumerate(objects):
            if target_indices is not None and i not in target_indices:
                continue
            if not obj.serial_region or obj.serial_region.size <= 0:
                obj.properties = {}
                continue

            serial_end = export_map[i].serial_offset + export_map[i].serial_size
            prev_range = archive.set_read_range((export_map[i].serial_offset, serial_end))
            archive._current_object_id = obj.id
            try:
                # Absolute-offset parser over the full archive, bounded by
                # _read_range enforced inside PackageArchive.read/validate_offset.
                raw_props = parse_properties_from_export(
                    export=export_map[i],
                    archive=archive,
                    summary=summary,
                    name_map=name_map,
                    export_map=export_map,
                    import_map=import_map,
                    mappings=mappings,
                    game=self._game,
                    tolerant=self._tolerant,
                    # v2 has no v1 class-handler dispatch at any depth.
                    run_class_handlers=False,
                )
                overrun = archive.tell() - serial_end
                obj.properties = normalize_property_bag(raw_props)
                cn = obj.class_name or ""
                if overrun <= 0 and cn in _TABLE_CLASSES:
                    extras[obj.id] = {
                        "table_rows": _read_table_rows(archive, serial_end, name_map, obj.id, diagnostics)
                    }
                elif overrun <= 0 and cn == "StringTable":
                    extras[obj.id] = {
                        "string_table": _read_string_table(
                            archive, obj.id, diagnostics, _string_table_has_dev_notes(summary)
                        )
                    }
                elif (
                    overrun <= 0
                    and cn not in _TABLE_CLASSES
                    and cn != "StringTable"
                    and archive.tell() < serial_end
                ):
                    # Properties ended early but the export still has bytes: a
                    # class raw trailer (e.g. UPhysicsAsset::Serialize writes
                    # CollisionDisableTable after the tagged properties) we do
                    # not decode yet. Preserve them and say so — never silently
                    # skip and claim coverage (#638). Exports may also carry a
                    # short all-zero alignment pad at their end; that is not a
                    # trailer worth reporting.
                    remaining = serial_end - archive.tell()
                    padded = remaining <= 16 and not any(archive.read(remaining))
                    if not padded:
                        diagnostics.append(
                            Diagnostic(
                                severity="warning",
                                code="EXPORT_TRAILING_BYTES_UNCONSUMED",
                                message=(
                                    f"Export {i} ({obj.name}) leaves {remaining} undecoded "
                                    f"bytes after the tagged properties (class {cn})"
                                ),
                                stage="objects.export",
                                object_id=obj.id,
                                effect="semantic_loss",
                                recoverable=True,
                            )
                        )
                if overrun > 0:
                    obj.status = ObjectStatus(parse="partial", semantic=obj.status.semantic)
                    diagnostics.append(
                        Diagnostic(
                            severity="warning",
                            code="EXPORT_PROPERTY_BOUNDS_EXCEEDED",
                            message=(
                                f"Export {i} ({obj.name}) property parse ran "
                                f"{overrun} bytes past serial_end {serial_end}"
                            ),
                            stage="properties.tagged",
                            object_id=obj.id,
                            effect="semantic_loss",
                            recoverable=True,
                        )
                    )

            except ExportBoundsExceeded as e:
                obj.properties = {}
                obj.status = ObjectStatus(parse="partial", semantic=obj.status.semantic)
                diagnostics.append(
                    Diagnostic(
                        severity="warning",
                        code="EXPORT_PROPERTY_BOUNDS_EXCEEDED",
                        message=f"Export {i} ({obj.name}) read exceeded serial bound: {e}",
                        stage="properties.tagged",
                        object_id=obj.id,
                        effect="semantic_loss",
                        recoverable=True,
                    )
                )
            except (ParseError, EOFError, struct.error, ValueError, UnicodeError) as e:
                obj.properties = {}
                obj.status = ObjectStatus(parse="partial", semantic=obj.status.semantic)
                diagnostics.append(
                    Diagnostic(
                        severity="warning",
                        code="EXPORT_PROPERTY_PARSE_FAILED",
                        message=f"Export {i} ({obj.name}) property parse failed: {type(e).__name__}: {e}",
                        stage="properties.tagged",
                        object_id=obj.id,
                        effect="semantic_loss",
                        recoverable=True,
                    )
                )
            finally:
                archive._current_object_id = ""
                archive.set_read_range(prev_range)

        return extras

    def _build_minimal_document(
        self,
        summary: PackageFileSummary | None,
        diagnostics: list[Diagnostic],
    ) -> PackageDocument:
        """Build a minimal PackageDocument when parsing fails early."""
        package_info = PackageInfo(name="", layout="legacy")
        if summary:
            package_info = _build_package_info_from_summary(
                summary, [], source_path=str(self._source._path)
            )

        return PackageDocument(
            source=_build_source_info(str(self._source._path)),
            package=package_info,
            diagnostics=diagnostics,
        )


# DataTable-family rows are serialized after the tagged properties as
# NumRows(i32) + per-row FName(Index,Number) + row value (tagged property
# stream terminated by the None tag, no int32 size prefix).
# UE source: Engine/Source/Runtime/Engine/Private/DataTable.cpp LoadStructData.
# StringTable is NOT this layout — it uses the FStringTable trailer below (#615).
_TABLE_CLASSES = ("DataTable", "CurveTable")
_MAX_TABLE_BLOB = 64 * 1024 * 1024  # bounded read; larger tables report partial
_MAX_TABLE_ROWS = 100000  # garbage row counts are rejected, not trusted


def _read_table_rows(
    archive: PackageArchive,
    serial_end: int,
    name_map: list[str],
    object_id: str,
    diagnostics: list[Diagnostic],
) -> dict[str, Any]:
    """Parse NumRows + row names from the bounded payload after properties.

    The archive is positioned at the payload start and its ``_read_range``
    is the export's serial end, so the slice read can never escape the
    export.  Anything that does not fit is reported as ``complete: False``
    with a diagnostic, never silently truncated.
    """
    result: dict[str, Any] = {"row_count": 0, "row_names": [], "complete": False}
    remaining = serial_end - archive.tell()
    if remaining < 4:
        return result
    blob = archive.read(min(remaining, _MAX_TABLE_BLOB))
    (row_count,) = struct.unpack_from("<i", blob, 0)
    if row_count < 0 or row_count > _MAX_TABLE_ROWS:
        diagnostics.append(
            Diagnostic(
                severity="warning",
                code="TABLE_ROW_COUNT_INVALID",
                message=f"{object_id}: table row count {row_count} outside sane range",
                stage="payload.table",
                object_id=object_id,
                effect="semantic_loss",
                recoverable=True,
            )
        )
        return result
    off = 4
    names: list[str] = []
    payload = ByteArchive(blob[4:])
    # Tag reads must use the real package layout version, not a fresh default.
    payload._file_version_ue4 = getattr(archive, "_file_version_ue4", 0)
    payload._file_version_ue5 = getattr(archive, "_file_version_ue5", 0)
    limit = len(blob) - 4
    for _ in range(row_count):
        if payload.tell() + 8 > limit:
            break
        idx = payload.read_u32()
        payload.read_u32()  # on-disk FName internal number (unused for row lookup)
        names.append(name_map[idx] if 0 <= idx < len(name_map) else f"<row:{idx}>")
        # Each row is a tagged property stream terminated by the None tag (DataTable.cpp
        # LoadStructData -> SerializeItem; versioned path = SerializeTaggedProperties,
        # CurveTable.cpp:112-171 same). Skip field values; stop at None.
        while payload.tell() < limit:
            header_pos = payload.tell()
            try:
                t = read_property_tag(payload, name_map)
            except ParseError:
                payload.seek(header_pos)
                break
            if t.name == "None":
                break
            if t.value_end_offset <= payload.tell():
                # Non-advancing tag (e.g. zero size, no in-tag payload): malformed row.
                payload.seek(header_pos)
                break
            payload.seek(t.value_end_offset)
    complete = len(names) == row_count
    if not complete:
        diagnostics.append(
            Diagnostic(
                severity="warning",
                code="TABLE_ROWS_TRUNCATED",
                message=(
                    f"{object_id}: parsed {len(names)}/{row_count} rows within the "
                    f"export payload ({min(remaining, _MAX_TABLE_BLOB)} bytes sliced)"
                ),
                stage="payload.table",
                object_id=object_id,
                effect="semantic_loss",
                recoverable=True,
            )
        )
    result["row_count"] = len(names)
    result["row_names"] = names
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
_FORTNITE_MB_GUID = "86181d60844f64acded316aad6c7ea0d"  # FGuid(0x601D1886,0xAC644F84,0xAA16D3DE,0x0DEAC7D6), little-endian bytes
_FORTNITE_ADD_DEV_NOTES = 260  # FFortniteMainBranchObjectVersion::AddDevNotesToFText


def _string_table_has_dev_notes(summary: PackageFileSummary) -> bool:
    """True when the editor-saved trailer wrote per-entry DevNotes strings."""
    if summary.package_flags & PKG_FilterEditorOnly:
        return False
    for cv in getattr(summary, "custom_versions", []):
        if getattr(cv, "guid", "") == _FORTNITE_MB_GUID:
            return getattr(cv, "version", 0) >= _FORTNITE_ADD_DEV_NOTES
    return False


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
    """
    result: dict[str, Any] = {"namespace": "", "entry_count": 0, "entries": [], "complete": False}
    try:
        result["namespace"] = archive.read_fstring()
        entry_count = archive.read_i32()
        if entry_count < 0 or entry_count > _MAX_TABLE_ROWS:
            diagnostics.append(
                Diagnostic(
                    severity="warning",
                    code="TABLE_ENTRY_COUNT_INVALID",
                    message=f"{object_id}: string table entry count {entry_count} outside sane range",
                    stage="payload.string_table",
                    object_id=object_id,
                    effect="semantic_loss",
                    recoverable=True,
                )
            )
            return result
        result["entry_count"] = entry_count
        for _ in range(entry_count):
            key = archive.read_fstring()
            value = archive.read_fstring()
            if dev_notes:
                archive.read_fstring()  # DevNotes, parsed but not surfaced
            result["entries"].append({"key": key, "value": value})
        result["complete"] = True
    except (ExportBoundsExceeded, ParseError, EOFError, struct.error, ValueError, UnicodeError) as e:
        diagnostics.append(
            Diagnostic(
                severity="warning",
                code="STRING_TABLE_TRUNCATED",
                message=(
                    f"{object_id}: string table trailer unreadable after "
                    f"{len(result['entries'])}/{result['entry_count']} entries: {type(e).__name__}: {e}"
                ),
                stage="payload.string_table",
                object_id=object_id,
                effect="semantic_loss",
                recoverable=True,
            )
        )
    return result
