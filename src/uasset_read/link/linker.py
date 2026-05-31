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
    from uasset_read.versioning import VersionContainer

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
        version_container: Optional["VersionContainer"] = None,
    ):
        self._archive = archive
        self._summary = summary
        self._name_map = name_map
        self._import_map = import_map
        self._export_map = export_map
        self._version_container = version_container

        # Public aliases (used by UObjectInstance.get_full_name() etc.)
        self.summary = summary
        self.name_map = name_map
        self.version_container = version_container

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

    def post_load(self) -> None:
        """Stage 4: 后处理阶段（镜像 UE FLinkerLoad::PostLoad）。

        在所有对象创建和预加载后执行：
        1. 解析 ObjectProperty 引用
        2. 验证导入对象有效性
        3. 解析 template_index (CDO) 引用
        4. 构建依赖图
        """
        self._resolve_property_references()
        self._verify_imports()
        self._resolve_template_objects()
        self._build_dependency_graph()

    def _resolve_property_references(self) -> None:
        """将 ObjectProperty 的 FPackageIndex 解析为 UObjectInstance 引用。

        遍历所有已 preload 的 export 对象，填充 property_references 字段。
        """
        for inst in self._export_objects:
            if not inst._preloaded:
                continue
            if not hasattr(inst, 'serialized_properties') or not inst.serialized_properties:
                continue
            for prop in inst.serialized_properties:
                if not isinstance(prop, dict):
                    continue
                if prop.get('type') == 'ObjectProperty':
                    pkg_idx = prop.get('value')
                    if isinstance(pkg_idx, int):
                        # 转换为 PackageIndex 并解析
                        from uasset_read.serializers.object_resources import PackageIndex
                        resolved = self.resolve_package_index(PackageIndex(pkg_idx))
                        if resolved:
                            prop_name = prop.get('name', '')
                            if not hasattr(inst, 'property_references'):
                                inst.property_references = {}
                            inst.property_references[prop_name] = resolved

    def _verify_imports(self) -> List[str]:
        """验证所有导入对象的有效性。

        Returns:
            验证错误列表（用于 tolerant 模式下的 warnings）
        """
        errors = []
        for idx, imp in enumerate(self._import_map):
            inst = self._import_objects[idx] if idx < len(self._import_objects) else None
            if inst is None:
                continue

            # 验证 class_index
            if hasattr(imp, 'class_index') and imp.class_index and not imp.class_index.is_null:
                class_inst = self.resolve_package_index(imp.class_index)
                if class_inst is None:
                    errors.append(f"Import {inst.object_name}: class_index 无法解析")

            # 验证 outer_index
            if hasattr(imp, 'outer_index') and imp.outer_index and not imp.outer_index.is_null:
                outer_inst = self.resolve_package_index(imp.outer_index)
                if outer_inst is None:
                    errors.append(f"Import {inst.object_name}: outer_index 无法解析")

        return errors

    def _resolve_template_objects(self) -> None:
        """解析导出对象的 template_index (CDO) 引用。

        为每个已 preload 的 export 设置 template_object 属性。
        """
        for idx, inst in enumerate(self._export_objects):
            if idx >= len(self._export_map):
                continue
            exp = self._export_map[idx]
            if hasattr(exp, 'template_index') and exp.template_index and not exp.template_index.is_null:
                template = self.resolve_package_index(exp.template_index)
                if template:
                    inst.template_object = template

    def _build_dependency_graph(self) -> None:
        """将 DependsMap 转换为 UObjectInstance 之间的依赖链接。

        DependsMap[export_index] = [依赖的 export_index 列表]
        """
        if not hasattr(self._summary, 'depends_map') or not self._summary.depends_map:
            return

        depends_map = self._summary.depends_map
        for exp_idx, dep_indices in enumerate(depends_map):
            if exp_idx < len(self._export_objects):
                inst = self._export_objects[exp_idx]
                inst.dependencies = []
                for dep_idx in dep_indices:
                    if 0 <= dep_idx < len(self._export_objects):
                        inst.dependencies.append(self._export_objects[dep_idx])
