"""
解析结果数据类 — BaseResult、ParseResult 和 StatusInfo。

BaseResult 是 ParseResult 和 LinkerParseResult 的共享基类，
包含所有公共字段和统一的 status 属性。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, TYPE_CHECKING

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
    summary: Optional["PackageFileSummary"] = None
    name_map: List[str] = field(default_factory=list)
    import_map: List["ObjectImport"] = field(default_factory=list)
    export_map: List["ObjectExport"] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    is_success: bool = False
    mmap_used: bool = False
    mmap_warning: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    diagnostics: List[OffsetRangeDiagnostic] = field(default_factory=list)
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
    blueprint: Optional["BlueprintMetadata"] = None
    graphs: List["UEdGraph"] = field(default_factory=list)
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
    linker: Optional["PackageLinker"] = None
    hex_view_entries: List = field(default_factory=list)  # List[HexViewEntry]
    asset_registry_data: Optional["AssetRegistryData"] = None


@dataclass
class StatusInfo:
    """JSend 风格 status 字段（D-14-02, OUT-01）。"""
    status: str
    message: Optional[str] = None
    code: Optional[str] = None
