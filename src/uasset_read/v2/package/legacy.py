"""LegacyPackageReader — direct binary reader for legacy .uasset packages.

Reads package summary, name table, import/export maps, depends, and
preload dependencies directly from binary, building a PackageDocument
without going through the v1 pipeline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Sequence

from ...archive import FArchive
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

    PackageArchive inherits from FArchive but does not call FArchive.__init__.
    We must initialize the attributes it needs for inherited read methods
    (read_i32, read_fstring, etc.) and for hex_view/structured_diagnostics.
    """
    reader = SliceReader(source, 0, source.size())

    # Initialize FArchive internal state without opening a file.
    # _init_archive_attrs would open a real file — we override the path
    # and open/close a temp FArchive to get the attributes set up cleanly.
    import tempfile, os

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".tmp")
    os.close(tmp_fd)
    try:
        tmp_archive = FArchive(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    # Transfer initialized attributes to our SliceReader-backed archive.
    archive = object.__new__(PackageArchive)
    archive._path = tmp_archive._path  # not used, but kept for repr
    archive._file = None  # SliceReader handles I/O
    archive._byte_swapping = tmp_archive._byte_swapping
    archive._file_size = source.size()
    archive._tolerant = tolerant
    archive._mmap = None
    archive._use_mmap = False
    archive._mmap_warning = None
    archive._logger = tmp_archive._logger
    archive._name_map = None
    archive._diagnostics = tmp_archive._diagnostics
    archive._name_warnings_seen = set()
    archive._hex_view_enabled = tmp_archive._hex_view_enabled
    archive._hex_view_entries = tmp_archive._hex_view_entries
    archive._hex_view_context = ""
    archive._structured_diagnostics = []
    # PackageArchive position tracking
    archive._main_archive = reader
    archive._uexp_archive = None
    archive._main_size = source.size()
    archive._uexp_size = 0
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

            # 6. Read depends map (boundary validation only — not stored in document yet)
            read_depends_map(archive, summary)

            # 7. Read preload dependencies (boundary validation only)
            read_preload_dependencies(archive, summary)

            # 8. Build VersionContext (reserved for future use — handlers, depth routing)
            build_version_context_from_summary(
                summary,
                package_layout="legacy",
                game=self._game,
            )

            # 9. Build ObjectRecords — ALL exports, no filtering
            objects = [
                _build_object_record_direct(exp, i, import_map, export_map)
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

            # 16. Build SourceInfo
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
