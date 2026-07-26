"""
解析结果数据类 — BaseResult、ParseResult 和 StatusInfo。

BaseResult 是 ParseResult 和 LinkerParseResult 的共享基类，
包含所有公共字段和统一的 status 属性。
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
    from uasset_read.models.diagnostics import OffsetRangeDiagnostic


@dataclass
class BaseResult:
    """ParseResult 和 LinkerParseResult 的共享基类。

    包含所有公共字段和统一的 status 属性。
    状态计算委托给 status._result_status()。
    """
    summary: PackageFileSummary | None = None
    name_map: list[str] = field(default_factory=list)
    import_map: list[ObjectImport] = field(default_factory=list)
    export_map: list[ObjectExport] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    is_success: bool = False
    mmap_used: bool = False
    mmap_warning: str | None = None
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    diagnostics: list[OffsetRangeDiagnostic] = field(default_factory=list)
    diagnostics_dropped_count: int = 0
    """Number of diagnostics entries dropped by BoundedEventBuffer truncation."""
    _error_keys: set = field(default_factory=set)  # 错误去重用：(异常类型, 阶段, 消息)

    @property
    def status(self) -> str:
        """Unified status: success | partial | failed.

        委托给 status._result_status() 实现统一状态推导。
        """
        return _result_status(self)


@dataclass
class ParseResult(BaseResult):
    """解析结果（D-15 部分结果）。"""
    blueprint: BlueprintMetadata | None = None
    graphs: list[UEdGraph] = field(default_factory=list)
    imports: list[dict] = field(default_factory=list)
    soft_references: list[dict] = field(default_factory=list)
    soft_package_references: list[str] = field(default_factory=list)
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
    hex_view_entries: list = field(default_factory=list)  # List[HexViewEntry]
    hex_view_dropped_count: int = 0
    """Number of hex view entries dropped by BoundedEventBuffer truncation."""
    asset_registry_data: AssetRegistryData | None = None


@dataclass
class StatusInfo:
    """JSend 风格 status 字段（D-14-02, OUT-01）。"""
    status: str
    message: str | None = None
    code: str | None = None
