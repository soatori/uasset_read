"""
解析结果数据类 — ParseResult 和 StatusInfo。

等价覆盖 uasset_read.py 中第 2051-2091 行的数据类定义。
ParseResult 是聚合结果，不使用 from_archive。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.serializers.package_summary import PackageFileSummary
    from uasset_read.serializers.object_resources import ObjectImport, ObjectExport
    from uasset_read.models.core import UEdGraph
    from uasset_read.models.blueprint import BlueprintMetadata


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


@dataclass
class StatusInfo:
    """JSend 风格 status 字段（D-14-02, OUT-01）。"""
    status: str
    message: Optional[str] = None
    code: Optional[str] = None
