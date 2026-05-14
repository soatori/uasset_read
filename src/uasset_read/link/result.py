"""Linker 解析结果数据类 — LinkerParseResult。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.link.linker import PackageLinker
    from uasset_read.link.object_instance import UObjectInstance
    from uasset_read.serializers.object_resources import (
        PackageFileSummary,
        ObjectImport,
        ObjectExport,
    )
    from uasset_read.models.blueprint import BlueprintMetadata
    from uasset_read.models.core import UEdGraph


@dataclass
class LinkerParseResult:
    """Linker 解析结果 — 包含 ImportMap/ExportMap 反序列化后的完整对象图。"""

    summary: Optional["PackageFileSummary"] = None
    name_map: List[str] = field(default_factory=list)
    import_map: List["ObjectImport"] = field(default_factory=list)
    export_map: List["ObjectExport"] = field(default_factory=list)
    linker: Optional["PackageLinker"] = None
    root_objects: List["UObjectInstance"] = field(default_factory=list)
    all_objects: List["UObjectInstance"] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    is_success: bool = False
    mmap_used: bool = False
    mmap_warning: Optional[str] = None

    # Post-process fields (shared with ParseResult via _post_process)
    blueprint: Optional["BlueprintMetadata"] = None
    graphs: List["UEdGraph"] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    imports: List[Dict] = field(default_factory=list)
    soft_references: List[Dict] = field(default_factory=list)
    circular_deps: List[List[str]] = field(default_factory=list)
