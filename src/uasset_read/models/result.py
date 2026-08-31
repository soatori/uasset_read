"""
Parse result data classes -- ParseResult.
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

# Canonical 3-outcome sets over plain parse_status strings
PARTIAL_STATUSES: frozenset[str] = frozenset(
    {"partial", "opaque", "skipped", "partial_metadata", "opaque_unversioned", "fallback", "metadata"}
)
FAILED_STATUSES: frozenset[str] = frozenset({"failed"})


@dataclass
class ParseResult:
    """Standard parse result returned by ``parse_package`` and ``parse_package_lazy``.

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

    # -- Parse-path fields (do not apply to the linker path) --
    soft_package_references: list[str] = field(default_factory=list)
    asset_registry_data: AssetRegistryData | None = None
    root_objects: list = field(default_factory=list)
    """Top-level object instances from the linker object graph."""
    all_objects: list = field(default_factory=list)
    """All object instances from the linker object graph."""

    @property
    def status(self) -> str:
        """Unified status: success | partial | failed."""
        exports = getattr(self, "export_map", None) or []

        # 1. Export-level status (highest priority)
        if exports:
            statuses = {getattr(e, "parse_status", "success") or "success" for e in exports}
            if statuses <= {"success"}:
                pass  # all success, fall through to other checks
            elif all(s in FAILED_STATUSES for s in statuses):
                return "failed"
            else:
                return "partial"

        # 2. Not marked success + has data → partial; no data → failed
        if not getattr(self, "is_success", False):
            has_data = getattr(self, "summary", None) is not None or getattr(self, "name_map", None) or exports
            return "partial" if has_data else "failed"

        # 3. is_success=True — check degrading signals
        if getattr(self, "errors", None):
            return "partial"

        warnings = getattr(self, "warnings", None) or []
        if any("corrupted" in w or "DependsMap" in w for w in warnings):
            return "partial"

        if (getattr(self, "metadata", None) or {}).get("lightweight_tolerant_parse"):
            return "partial"

        if any(getattr(d, "is_structural", lambda: False)() for d in getattr(self, "diagnostics", None) or []):
            return "partial"

        for func in getattr(self, "decompiled_functions", None) or []:
            bs = getattr(func, "bytecode_status", "unknown")
            ts = getattr(func, "translation_status", "not_applicable")
            if bs == "failed" or (bs == "parsed" and ts in ("partial", "failed")):
                return "partial"

        return "success"
