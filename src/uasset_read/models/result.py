"""
Parse result data classes -- BaseResult, ParseResult, and StatusInfo.

BaseResult is the single shared base for ParseResult and LinkerParseResult,
holding all common fields including post-process data and the unified
``status`` property.

Hierarchy:  BaseResult -> ParseResult -> LinkerParseResult
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from uasset_read.models.status import _result_status

if TYPE_CHECKING:
    from uasset_read.serializers.package_summary import PackageFileSummary
    from uasset_read.serializers.object_resources import ObjectImport, ObjectExport
    from uasset_read.models.core import UEdGraph
    from uasset_read.models.blueprint import BlueprintMetadata
    from uasset_read.kismet.result import KismetDecompiledResult
    from uasset_read.versioning import VersionContainer
    from uasset_read.link.linker import PackageLinker
    from uasset_read.parsers.asset_registry_parser import AssetRegistryData
    from uasset_read.models.diagnostics import OffsetRangeDiagnostic, StructuredDiagnostic


@dataclass
class BaseResult:
    """Single shared base for all parse result types.

    Contains the core table fields (summary, name/import/export maps),
    error/warning accumulators, and all post-process fields that
    ``_post_process()`` populates for both ``ParseResult`` and
    ``LinkerParseResult``.

    Status derivation is delegated to ``status._result_status()``.
    """
    # -- Core table fields --
    summary: PackageFileSummary | None = None
    name_map: list[str] = field(default_factory=list)
    import_map: list[ObjectImport] = field(default_factory=list)
    export_map: list[ObjectExport] = field(default_factory=list)

    # -- Error / warning accumulators --
    errors: list[str] = field(default_factory=list)
    is_success: bool = False
    mmap_used: bool = False
    mmap_warning: str | None = None
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    diagnostics: list[OffsetRangeDiagnostic] = field(default_factory=list)
    structured_diagnostics: list[StructuredDiagnostic] = field(default_factory=list)
    """Structured diagnostics with stable codes for audit."""
    diagnostics_dropped_count: int = 0
    """Number of diagnostics entries dropped by BoundedEventBuffer truncation."""
    _error_keys: set = field(default_factory=set)

    # -- Post-process fields (shared by ParseResult & LinkerParseResult) --
    blueprint: BlueprintMetadata | None = None
    graphs: list[UEdGraph] = field(default_factory=list)
    imports: list[dict] = field(default_factory=list)
    soft_references: list[dict] = field(default_factory=list)
    soft_object_path_list: list[dict] = field(default_factory=list)
    """SoftObjectPathList for index-based SoftObjectProperty resolution (UE5.7+)."""
    circular_deps: list[list[str]] = field(default_factory=list)
    components: list[dict] = field(default_factory=list)
    decompiled_functions: list[KismetDecompiledResult] = field(default_factory=list)
    version_container: VersionContainer | None = None
    resolved_parent_assets: list[dict] = field(default_factory=list)
    inherited_blueprint_graphs: list[dict] = field(default_factory=list)
    logic_sources: list[dict] = field(default_factory=list)
    linker: PackageLinker | None = None
    hex_view_entries: list = field(default_factory=list)
    """List[HexViewEntry] -- populated when hex_view=True."""
    hex_view_dropped_count: int = 0
    """Number of hex view entries dropped by BoundedEventBuffer truncation."""

    @property
    def status(self) -> str:
        """Unified status: success | partial | failed.

        Delegates to ``status._result_status()``.
        """
        return _result_status(self)


@dataclass
class ParseResult(BaseResult):
    """Standard parse result returned by ``parse_package`` and ``parse_package_lazy``.

    Extends ``BaseResult`` with parse-path-specific fields that do not
    apply to the linker path.
    """
    soft_package_references: list[str] = field(default_factory=list)
    asset_registry_data: AssetRegistryData | None = None
    root_objects: list = field(default_factory=list)
    """Top-level object instances from the linker object graph."""
    all_objects: list = field(default_factory=list)
    """All object instances from the linker object graph."""


