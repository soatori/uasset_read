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
        """解析状态（success/fail/error）。

        代理到 build_status_info().status，保持 API 一致性。
        与 result.is_success 行为一致：
        - is_success=True, errors=[] → "success"
        - is_success=True, errors non-empty → "fail"
        - is_success=False → "error"
        """
        # 延迟导入避免循环依赖（result.py 被 helpers.py 导入）
        from uasset_read.formatters.helpers import build_status_info
        return build_status_info(self).status


@dataclass
class StatusInfo:
    """JSend 风格 status 字段（D-14-02, OUT-01）。"""
    status: str
    message: Optional[str] = None
    code: Optional[str] = None
