"""
Parse result data classes -- BaseResult, ParseResult, and StatusInfo.

BaseResult is the single shared base for ParseResult and 
holding all common fields including post-process data and the unified
``status`` property.

Hierarchy:  BaseResult -> ParseResult
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

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

from uasset_read.models.fallback import ExportParseStatus

# Partial status set: auto-generated from ExportParseStatus.is_partial
# Fully covers all partial variants, ensuring consistent status determination (#315)
PARTIAL_STATUSES: frozenset[str] = frozenset(
    s.value for s in ExportParseStatus if s.is_partial
)

# Failed status set: auto-generated from ExportParseStatus.is_failed
FAILED_STATUSES: frozenset[str] = frozenset(
    s.value for s in ExportParseStatus if s.is_failed
)


@dataclass
class BaseResult:
    """Single shared base for all parse result types.

    Contains the core table fields (summary, name/import/export maps),
    error/warning accumulators, and all post-process fields that
    ``_post_process()`` populates for both ``ParseResult`` and
    ``ParseResult``.

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

    # -- Post-process fields  --
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

        Status rules:
        - failed: all exports are failed, or no core data and is_success=False
        - partial: any export is partial / has errors / has structural diagnostics / lightweight tolerant parsing
        - success: no errors and all exports succeeded

        Check order: export-level status > non-success branch > is_success=True branch

        Returns:
            "success" | "partial" | "failed"
        """
        # 1. Check export-level status (highest priority)
        export_map = getattr(self, "export_map", None) or []
        if export_map and isinstance(export_map, list):
            failed_count = 0
            partial_count = 0
            for exp in export_map:
                exp_status = getattr(exp, "parse_status", None)
                if exp_status in FAILED_STATUSES:
                    failed_count += 1
                elif exp_status in PARTIAL_STATUSES:
                    partial_count += 1
            # All exports failed -> overall failed
            if failed_count == len(export_map):
                return "failed"
            # Any partial or present failed (not all failed) -> overall partial
            if failed_count > 0 or partial_count > 0:
                return "partial"

        # 2. Non-success branch: check if core data exists
        if not getattr(self, "is_success", False):
            if (
                getattr(self, "summary", None) is not None
                or getattr(self, "name_map", None)
                or getattr(self, "import_map", None)
                or getattr(self, "export_map", None)
            ):
                return "partial"
            return "failed"

        # 3. is_success=True branch: comprehensive check
        # 3.1 Check errors
        if getattr(self, "errors", None):
            return "partial"

        # 3.2 Check warning-based degradation (corruption / data-skip)
        warnings = getattr(self, "warnings", None) or []
        if any("AssetRegistryData is corrupted" in w for w in warnings):
            return "partial"
        if any("DependsMap" in w for w in warnings):
            return "partial"

        # 3.3 Check lightweight tolerant parsing
        metadata = getattr(self, "metadata", None) or {}
        if metadata.get("lightweight_tolerant_parse"):
            return "partial"

        # 3.4 Check structural diagnostics
        diagnostics = getattr(self, "diagnostics", None) or []
        has_structural_diagnostic = any(
            getattr(d, "is_structural", lambda: False)()
            for d in diagnostics
            if hasattr(d, "is_structural")
        )
        if has_structural_diagnostic:
            return "partial"

        # 3.5 Check native function status (failed/partial translation)
        decompiled_functions = getattr(self, "decompiled_functions", None) or []
        for func in decompiled_functions:
            bytecode_status = getattr(func, "bytecode_status", "unknown")
            translation_status = getattr(func, "translation_status", "not_applicable")
            if bytecode_status == "failed":
                return "partial"
            if bytecode_status == "parsed" and translation_status in ("partial", "failed"):
                return "partial"

        return "success"


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


