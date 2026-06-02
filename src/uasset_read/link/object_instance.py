"""UObjectInstance -- lightweight UE object representation.

Each UObjectInstance represents one entry in the ImportMap or ExportMap,
with identity (name, type, package_index), references to other
UObjectInstances (outer, class_ref), and lazily-loaded serialized_properties.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from uasset_read.serializers.object_resources import (
        ObjectExport,
        ObjectImport,
        PackageIndex,
    )
    from uasset_read.link.linker import PackageLinker


@dataclass
class UObjectInstance:
    """Lightweight UE object representation for object graph navigation."""

    # ---- Identity ----
    package_index: int
    """Encoded: positive=export, negative=import, 0=null."""

    object_name: str
    """Object name (e.g. 'Default__MyBlueprint_C', 'ExecuteUbergraph_0')."""

    object_class: Optional[str]
    """Class name (e.g. 'BlueprintGeneratedClass', 'EdGraph')."""

    class_package: Optional[str]
    """Package containing the class (e.g. '/Script/Engine')."""

    # ---- References ----
    outer_index: Optional["PackageIndex"]
    """PackageIndex pointing to the Outer (parent) object."""

    # ---- Serialization info ----
    is_import: bool
    """True if from ImportMap, False if from ExportMap."""

    serial_offset: int = 0
    """Byte offset in file where serialized data starts."""

    serial_size: int = 0
    """Size of serialized data in bytes."""

    # ---- Linker back-reference ----
    linker: Optional["PackageLinker"] = None
    """Reference to the owning PackageLinker."""

    # ---- Resolved references (set by build_outer_tree) ----
    outer: Optional["UObjectInstance"] = None
    """Resolved parent object."""

    # ---- Lazy-loaded data ----
    serialized_properties: List[Any] = field(default_factory=list)
    """Parsed property values (filled by PackageLinker.preload())."""

    property_references: Dict[str, "UObjectInstance"] = field(
        default_factory=dict
    )
    """ObjectProperty values resolved to UObjectInstance references."""

    template_object: Optional["UObjectInstance"] = None
    """Resolved template (CDO) object from template_index."""

    dependencies: List["UObjectInstance"] = field(default_factory=list)
    """Resolved dependencies from DependsMap."""

    super_object: Optional["UObjectInstance"] = None
    """Resolved super (parent class) object from super_index."""

    weak_references: List["UObjectInstance"] = field(default_factory=list)
    """Resolved weak object references (WeakObjectProperty)."""

    script_serialization_start_offset: int = 0
    """UE5 蓝图脚本序列化起始偏移。"""

    # ---- Internal state ----
    _preloaded: bool = False
    """Whether properties have been loaded."""

    _raw_export: Optional["ObjectExport"] = None
    """Reference to raw ObjectExport dataclass (for backward compat)."""

    _raw_import: Optional["ObjectImport"] = None
    """Reference to raw ObjectImport dataclass (for backward compat)."""

    @property
    def is_export(self) -> bool:
        return not self.is_import

    @property
    def is_null(self) -> bool:
        return self.package_index == 0

    def get_full_name(self) -> str:
        """Get full UE object path: 'Outermost.Outer.Inner.ObjectName'."""
        if self.outer is not None:
            parent_name = self.outer.get_full_name()
            return f"{parent_name}.{self.object_name}"
        elif self.is_import and self.class_package:
            return f"{self.class_package}.{self.object_name}"
        elif self.linker and self.linker.summary:
            pkg_name = getattr(self.linker.summary, "package_name", "Unknown")
            if isinstance(pkg_name, int) and self.linker.name_map:
                idx = pkg_name
                if 0 <= idx < len(self.linker.name_map):
                    pkg_name = self.linker.name_map[idx]
                else:
                    pkg_name = "Unknown"
            return f"{pkg_name}.{self.object_name}"
        return self.object_name

    def get_class_object(self) -> Optional["UObjectInstance"]:
        """Resolve the class of this object to a UObjectInstance."""
        if self.is_import:
            return None
        if self._raw_export and self.linker:
            return self.linker.resolve_package_index(
                self._raw_export.class_index
            )
        return None

    def get_template_object(self) -> Optional["UObjectInstance"]:
        """Resolve the template (CDO) object for this export."""
        if self.is_import or not self._raw_export or not self.linker:
            return None
        return self.linker.resolve_package_index(
            self._raw_export.template_index
        )

    def get_children(self) -> List["UObjectInstance"]:
        """Get child objects (objects whose Outer is this object)."""
        if self.linker is None:
            return []
        return self.linker.get_children(self)

    def ensure_preloaded(self) -> None:
        """Ensure properties are loaded (lazy load if needed)."""
        if not self._preloaded and self.is_export and self.linker:
            exp_idx = self.package_index - 1
            self.linker.preload(exp_idx)

    def __repr__(self) -> str:
        kind = "Import" if self.is_import else "Export"
        return (
            f"<UObjectInstance {kind}#{abs(self.package_index)}: "
            f"{self.object_name} ({self.object_class})>"
        )
