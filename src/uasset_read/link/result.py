"""Linker 解析结果数据类 — LinkerParseResult。"""


from dataclasses import dataclass, field
from typing import Optional, List, Dict, TYPE_CHECKING

from uasset_read.models.result import BaseResult

if TYPE_CHECKING:
    from uasset_read.link.linker import PackageLinker
    from uasset_read.link.object_instance import UObjectInstance
    from uasset_read.models.blueprint import BlueprintMetadata
    from uasset_read.models.core import UEdGraph
    from uasset_read.kismet.result import KismetDecompiledResult
    from uasset_read.versioning import VersionContainer


@dataclass
class LinkerParseResult(BaseResult):
    """Linker 解析结果 — 包含 ImportMap/ExportMap 反序列化后的完整对象图。"""

    linker: Optional["PackageLinker"] = None
    root_objects: List["UObjectInstance"] = field(default_factory=list)
    all_objects: List["UObjectInstance"] = field(default_factory=list)

    # Post-process fields (shared with ParseResult via _post_process)
    blueprint: Optional["BlueprintMetadata"] = None
    graphs: List["UEdGraph"] = field(default_factory=list)
    imports: List[Dict] = field(default_factory=list)
    soft_references: List[Dict] = field(default_factory=list)
    circular_deps: List[List[str]] = field(default_factory=list)
    components: List[Dict] = field(default_factory=list)
    decompiled_functions: List["KismetDecompiledResult"] = field(default_factory=list)
    version_container: Optional["VersionContainer"] = None
    resolved_parent_assets: List[Dict] = field(default_factory=list)
    inherited_blueprint_graphs: List[Dict] = field(default_factory=list)
    logic_sources: List[Dict] = field(default_factory=list)
    soft_object_path_list: List[Dict] = field(default_factory=list)
