"""
解析结果数据类 — ParseResult 和 StatusInfo。

等价覆盖 uasset_read.py 中第 2051-2091 行的数据类定义。
ParseResult 是聚合结果，不使用 from_archive。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.serializers.package_summary import PackageFileSummary
    from uasset_read.serializers.object_resources import ObjectImport, ObjectExport
    from uasset_read.models.core import UEdGraph
    from uasset_read.models.blueprint import BlueprintMetadata
    from uasset_read.kismet.result import KismetDecompiledResult
    from uasset_read.versioning import VersionContainer
    from uasset_read.link.linker import PackageLinker


@dataclass
class ParseResult:
    """解析结果（D-15 部分结果）。"""
    summary: Optional["PackageFileSummary"] = None
    name_map: List[str] = field(default_factory=list)
    import_map: List["ObjectImport"] = field(default_factory=list)
    export_map: List["ObjectExport"] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    blueprint: Optional["BlueprintMetadata"] = None
    graphs: List["UEdGraph"] = field(default_factory=list)
    is_success: bool = False
    mmap_used: bool = False
    mmap_warning: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    imports: List[Dict] = field(default_factory=list)
    soft_references: List[Dict] = field(default_factory=list)
    soft_package_references: List[str] = field(default_factory=list)
    soft_object_path_list: List[Dict] = field(default_factory=list)
    """SoftObjectPathList for index-based SoftObjectProperty resolution (UE5.7+)."""
    circular_deps: List[List[str]] = field(default_factory=list)
    components: List[Dict] = field(default_factory=list)
    decompiled_functions: List["KismetDecompiledResult"] = field(default_factory=list)
    version_container: Optional["VersionContainer"] = None
    resolved_parent_assets: List[Dict] = field(default_factory=list)
    inherited_blueprint_graphs: List[Dict] = field(default_factory=list)
    logic_sources: List[Dict] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    linker: Optional["PackageLinker"] = None
    diagnostics: List = field(default_factory=list)  # List[OffsetRangeDiagnostic]

    @property
    def status(self) -> str:
        """Unified status: success | partial | failed.

        - success: No errors, all exports parsed successfully
        - partial: Some errors or some exports are opaque/skipped, but core data available
        - failed: Critical error, no usable data
        """
        # Failed if no core data
        if not self.summary and not self.name_map and not self.export_map:
            return "failed"

        # Partial if there are errors
        if self.errors:
            return "partial"

        # Partial if any export is not success
        for export in self.export_map:
            export_status = getattr(export, 'parse_status', 'success')
            if export_status in ('opaque', 'partial', 'skipped', 'metadata', 'failed'):
                return "partial"

        # Check metadata for lightweight parse
        if self.metadata.get('lightweight_tolerant_parse'):
            return "partial"

        # Success if no errors and all exports success
        return "success"


@dataclass
class StatusInfo:
    """JSend 风格 status 字段（D-14-02, OUT-01）。"""
    status: str
    message: Optional[str] = None
    code: Optional[str] = None
