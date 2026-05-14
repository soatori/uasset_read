"""PackageLinker — two-phase loading coordinator.

Mirrors UE's FLinkerLoad pattern: link() creates UObjectInstance shells,
preload(index) lazily deserializes properties on demand.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.package_summary import PackageFileSummary
    from uasset_read.serializers.object_resources import (
        ObjectImport, ObjectExport, PackageIndex,
    )

from uasset_read.serializers.object_resources import resolve_class_name, PackageIndex as PI
from uasset_read.link.object_instance import UObjectInstance


class PackageLinker:
    """FLinkerLoad-style two-phase object graph constructor.

    link()     — creates UObjectInstance shells from ImportMap/ExportMap.
    preload()  — lazily deserializes properties for a given export.
    """

    def __init__(
        self,
        archive: "FArchive",
        summary: "PackageFileSummary",
        name_map: List[str],
        import_map: List["ObjectImport"],
        export_map: List["ObjectExport"],
    ):
        self._archive = archive
        self._summary = summary
        self._name_map = name_map
        self._import_map = import_map
        self._export_map = export_map

        self._import_objects: List[UObjectInstance] = []
        self._export_objects: List[UObjectInstance] = []
        self._root_objects: List[UObjectInstance] = []
        self._preload_cache: dict[int, bool] = {}

    def link(self) -> None:
        """Phase 1: create UObjectInstance shells from import/export maps."""
        self._create_import_instances()
        self._create_export_instances()
        self.build_outer_tree()
        self._collect_root_objects()

    def _create_import_instances(self) -> None:
        """Create UObjectInstance for each ImportMap entry."""
        self._import_objects = []
        for idx, imp in enumerate(self._import_map):
            pkg_idx = -(idx + 1)
            obj_name = (
                self._name_map[imp.object_name]
                if isinstance(imp.object_name, int) else imp.object_name
            )
            cls_name = (
                self._name_map[imp.class_name]
                if isinstance(imp.class_name, int) else imp.class_name
            )
            cls_pkg = (
                self._name_map[imp.class_package]
                if isinstance(imp.class_package, int) else imp.class_package
            )
            inst = UObjectInstance(
                package_index=pkg_idx,
                object_name=obj_name,
                object_class=cls_name,
                class_package=cls_pkg,
                outer_index=imp.outer_index,
                is_import=True,
                linker=self,
                _raw_import=imp,
            )
            self._import_objects.append(inst)

    def _create_export_instances(self) -> None:
        """Create UObjectInstance for each ExportMap entry."""
        self._export_objects = []
        for idx, exp in enumerate(self._export_map):
            pkg_idx = idx + 1
            obj_name = (
                self._name_map[exp.object_name]
                if isinstance(exp.object_name, int) else exp.object_name
            )
            cls_name = resolve_class_name(
                exp.class_index, self._import_map, self._export_map
            )
            inst = UObjectInstance(
                package_index=pkg_idx,
                object_name=obj_name,
                object_class=cls_name,
                class_package=None,
                outer_index=exp.outer_index,
                is_import=False,
                serial_offset=exp.serial_offset,
                serial_size=exp.serial_size,
                linker=self,
                _raw_export=exp,
            )
            self._export_objects.append(inst)

    def build_outer_tree(self) -> None:
        """Resolve OuterIndex → UObjectInstance for all objects."""
        all_objs = self._import_objects + self._export_objects
        for inst in all_objs:
            if inst.outer_index is None or inst.outer_index.is_null:
                continue
            parent = self.resolve_package_index(inst.outer_index)
            if parent is not None:
                inst.outer = parent

    def resolve_package_index(
        self, pkg_idx: "PackageIndex"
    ) -> Optional[UObjectInstance]:
        """Resolve a PackageIndex to its UObjectInstance.

        Returns None for null or out-of-bounds indices.
        """
        if pkg_idx.is_null:
            return None
        if pkg_idx.is_export:
            idx = pkg_idx.to_export_index()
            if 0 <= idx < len(self._export_objects):
                return self._export_objects[idx]
            return None
        if pkg_idx.is_import:
            idx = pkg_idx.to_import_index()
            if 0 <= idx < len(self._import_objects):
                return self._import_objects[idx]
            return None
        return None

    def get_children(self, obj: UObjectInstance) -> List[UObjectInstance]:
        """Return all objects whose Outer is *obj*."""
        all_objs = self._import_objects + self._export_objects
        return [inst for inst in all_objs if inst.outer is obj]

    def preload(self, index: int) -> None:
        """Phase 2: lazily deserialize properties for export *index*."""
        if index in self._preload_cache:
            return
        if index < 0 or index >= len(self._export_objects):
            return

        instance = self._export_objects[index]
        if instance._preloaded:
            self._preload_cache[index] = True
            return

        if instance.serial_size == 0:
            instance._preloaded = True
            self._preload_cache[index] = True
            return

        self._archive.seek(instance.serial_offset)

        # Delayed import to avoid circular dependency at module load time.
        from uasset_read.parsers.property_parser import (
            parse_properties_from_export,
        )

        exp = self._export_map[index]
        instance.serialized_properties = parse_properties_from_export(
            exp,
            self._archive,
            self._summary,
            self._name_map,
            self._export_map,
            self._import_map,
        )
        instance._preloaded = True
        self._preload_cache[index] = True

    def _collect_root_objects(self) -> None:
        """Collect objects with no outer into _root_objects."""
        self._root_objects = [
            inst
            for inst in self._import_objects + self._export_objects
            if inst.outer_index is None
            or inst.outer_index.is_null
        ]
