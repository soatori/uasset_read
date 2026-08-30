"""LegacyPackageReader — direct binary reader for legacy .uasset packages.

Reads package summary, name table, import/export maps, depends, and
preload dependencies directly from binary, building a PackageDocument
without going through the v1 pipeline.
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Literal, Sequence

from ...exceptions import ParseError
from ...package import PackageArchive
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
from ...v2.version import build_version_context_from_summary


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


def _build_source_info(path: str) -> SourceInfo:
    p = Path(path)
    return SourceInfo(
        kind="loose",
        name=p.name,
        size=p.stat().st_size,
        path=str(p),
    )


def _build_package_info_from_summary(summary: PackageFileSummary, name_map: list[str]) -> PackageInfo:
    engine_version = ""
    saved = summary.saved_by_engine_version
    if saved and hasattr(saved, "major"):
        engine_version = f"{saved.major}.{saved.minor}.{saved.patch}.{saved.changelist}"

    compat_version = ""
    compat = summary.compatible_with_engine_version
    if compat and hasattr(compat, "major"):
        compat_version = f"{compat.major}.{compat.minor}.{compat.patch}.{compat.changelist}"

    return PackageInfo(
        name=summary.package_name,
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
            # 1. Read summary
            summary = read_package_summary(archive)

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

            # 6. Read depends map
            depends_map = read_depends_map(archive, summary)

            # 7. Read preload dependencies
            preload_deps = read_preload_dependencies(archive, summary)

            # 8. Build VersionContext (reserved for future use — handlers, depth routing)
            build_version_context_from_summary(
                summary,
                package_layout="legacy",
                game=self._game,
                depth=depth,
            )

            # 9. Build ObjectRecords — ALL exports, no filtering
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

            # 12. Collect FArchive structured diagnostics
            for sd in archive.get_structured_diagnostics():
                sev = sd.severity if sd.severity in ("info", "warning", "error", "critical") else "warning"
                diagnostics.append(
                    Diagnostic(
                        severity=sev,
                        code=sd.code,
                        message=sd.message or sd.fallback,
                        stage=sd.stage,
                        offset=sd.offset,
                        recoverable=True,
                    )
                )

            # 13. Compute asset_object_ids
            asset_ids = tuple(obj.id for obj in objects if ROLES_ASSET in obj.roles)

            # 14. Build PackageInfo
            package_info = _build_package_info_from_summary(summary, name_map)

            # 15. Build Summary
            summary_obj = Summary(
                object_count=len(objects),
                asset_object_ids=asset_ids,
                total_imports=len(import_map),
                total_exports=len(export_map),
            )

            # 16. Parse properties for requested objects at depth >= object
            if depth in ("object", "asset", "decode"):
                self._parse_requested_object_properties(
                    archive=archive,
                    objects=objects,
                    export_map=export_map,
                    import_map=import_map,
                    name_map=name_map,
                    summary=summary,
                    object_ids=object_ids,
                    diagnostics=diagnostics,
                    run_class_handlers=depth != "object",
                )

            # 17. Run asset handlers at depth >= asset
            if depth in ("asset", "decode"):
                context = build_version_context_from_summary(
                    summary,
                    package_layout="legacy",
                    game=self._game,
                    depth=depth,
                )
                for obj in objects:
                    try:
                        semantic, cov, handler_diags = run_handlers(obj, context, objects, (export_map, name_map))
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
        run_class_handlers: bool = False,
    ) -> None:
        """Parse properties for requested objects at depth="object".

        ``run_class_handlers`` re-enables the v1 AssetTypeHandler dispatch
        at asset/decode depth only: the v2 handlers in ``v2/handlers.py``
        still consume the ``_asset_type_data``/``properties`` mutations it
        makes on exports (DataTable, SoundWave, UserDefinedStruct). Cutting
        that coupling inside handlers.py is a follow-up; at object depth
        nothing needs it, so the dispatch — and its ``logger.warning`` leak
        — stays off there.

        If object_ids is None, parses ALL objects.
        Each export's serial region is bounded via SliceReader.sub_slice().
        Parse errors on one export do not prevent parsing of others.
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

        for i, obj in enumerate(objects):
            if target_indices is not None and i not in target_indices:
                continue
            if not obj.serial_region or obj.serial_region.size <= 0:
                obj.properties = {}
                continue

            try:
                # Absolute-offset parser over the full archive, bounded by the
                # post-parse position check below (recovery plan: do not rebase).
                raw_props = parse_properties_from_export(
                    export=export_map[i],
                    archive=archive,
                    summary=summary,
                    name_map=name_map,
                    export_map=export_map,
                    import_map=import_map,
                    mappings=self._mappings_path,
                    game=self._game,
                    tolerant=self._tolerant,
                    run_class_handlers=run_class_handlers,
                )
                serial_end = export_map[i].serial_offset + export_map[i].serial_size
                overrun = archive.tell() - serial_end
                obj.properties = normalize_property_bag(raw_props)
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
                else:
                    obj.status = ObjectStatus(
                        parse=obj.status.parse,
                        semantic=obj.status.semantic,
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

    def _build_minimal_document(
        self,
        summary: PackageFileSummary | None,
        diagnostics: list[Diagnostic],
    ) -> PackageDocument:
        """Build a minimal PackageDocument when parsing fails early."""
        package_info = PackageInfo(name="", layout="legacy")
        if summary:
            package_info = _build_package_info_from_summary(summary, [])

        return PackageDocument(
            source=_build_source_info(str(self._source._path)),
            package=package_info,
            diagnostics=diagnostics,
        )
