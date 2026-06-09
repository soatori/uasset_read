"""PackageLinker — two-phase loading coordinator.

Mirrors UE's FLinkerLoad pattern: link() creates UObjectInstance shells,
preload(index) lazily deserializes properties on demand.
"""
from __future__ import annotations

import logging
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
from uasset_read.models.diagnostics import OffsetRangeDiagnostic

logger = logging.getLogger(__name__)


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
        self._diagnostics: List[OffsetRangeDiagnostic] = []
        self._file_size: int = getattr(archive, '_file_size', 0)

    @property
    def diagnostics(self) -> List[OffsetRangeDiagnostic]:
        """返回所有偏移诊断记录。"""
        return self._diagnostics

    def link(self) -> None:
        """Create UObjectInstance shells from import/export maps.

        注意：当前实现一次性创建所有实例。
        对于超大包（>10000 个对象），可考虑延迟创建优化。
        """
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

            # 早期验证 serial_offset（防止溢出值传播到 preload 阶段）
            serial_offset = exp.serial_offset
            serial_size = exp.serial_size
            if serial_offset < 0 or serial_offset > self._file_size:
                self._diagnostics.append(OffsetRangeDiagnostic(
                    module="linker",
                    field="serial_offset",
                    export_index=idx,
                    object_name=obj_name,
                    target_offset=serial_offset,
                    file_size=self._file_size,
                    source="_create_export_instances",
                    error=f"Export #{idx} ({obj_name}) serial_offset {serial_offset} 超出文件范围 [0, {self._file_size}]",
                ))
                serial_offset = 0
                serial_size = 0

            inst = UObjectInstance(
                package_index=pkg_idx,
                object_name=obj_name,
                object_class=cls_name,
                class_package=None,
                outer_index=exp.outer_index,
                is_import=False,
                serial_offset=serial_offset,
                serial_size=serial_size,
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

        # 解析 super_index（父类引用）
        for idx, exp in enumerate(self._export_map):
            if idx < len(self._export_objects):
                inst = self._export_objects[idx]
                if hasattr(exp, 'super_index') and exp.super_index and not exp.super_index.is_null:
                    super_inst = self.resolve_package_index(exp.super_index)
                    if super_inst is not None:
                        inst.super_object = super_inst

    def export_objects(self) -> List[UObjectInstance]:
        """返回导出对象列表的只读副本。"""
        return list(self._export_objects)

    def resolve_package_index(
        self, pkg_idx: "PackageIndex"
    ) -> Optional[UObjectInstance]:
        """Resolve a PackageIndex to its UObjectInstance.

        Validates index bounds and records OffsetRangeDiagnostic on out-of-bounds.
        Returns None for null or out-of-bounds indices.
        """
        if pkg_idx.is_null:
            return None
        if pkg_idx.is_export:
            idx = pkg_idx.to_export_index()
            if 0 <= idx < len(self._export_objects):
                return self._export_objects[idx]
            # 越界诊断
            self._diagnostics.append(OffsetRangeDiagnostic(
                module="linker",
                field="PackageIndex",
                export_index=idx,
                file_size=self._file_size,
                source="resolve_package_index",
                error=f"Export PackageIndex {pkg_idx.index} (idx={idx}) 越界，export 数量 {len(self._export_objects)}",
            ))
            return None
        if pkg_idx.is_import:
            idx = pkg_idx.to_import_index()
            if 0 <= idx < len(self._import_objects):
                return self._import_objects[idx]
            # 越界诊断
            self._diagnostics.append(OffsetRangeDiagnostic(
                module="linker",
                field="PackageIndex",
                import_index=idx,
                file_size=self._file_size,
                source="resolve_package_index",
                error=f"Import PackageIndex {pkg_idx.index} (idx={idx}) 越界，import 数量 {len(self._import_objects)}",
            ))
            return None
        return None

    def get_children(self, obj: UObjectInstance) -> List[UObjectInstance]:
        """Return all objects whose Outer is *obj*."""
        all_objs = self._import_objects + self._export_objects
        return [inst for inst in all_objs if inst.outer is obj]

    def preload(
        self,
        index: int,
        mappings=None,
        game: Optional[str] = None,
        tolerant: bool = True,
    ) -> None:
        """Lazily deserialize properties for export *index*.

        Args:
            index: Export index to preload.
            mappings: Type mappings provider (optional).
            game: Game identifier (optional).
            tolerant: Tolerant parsing mode (default True).
        """
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

        # === Class Serialization Strategy Check ===
        # 对 SKIP_UNSUPPORTED 类，在 linker 层提前拦截
        # 对 OPAQUE_CLASS_PAYLOAD 类，设置初始状态但不 early return，
        # 让 parse_properties_from_export() 调用 asset type handler 提取元数据
        # 参见 Issue #23: class serialization strategy 不应绕过 asset type handler
        from uasset_read.parsers.class_serialization_strategy import (
            get_serialization_strategy,
            SerializationStrategy,
        )
        class_name = instance.object_class
        if class_name is not None:
            strategy = get_serialization_strategy(class_name)
            exp = self._export_map[index]
            if strategy == SerializationStrategy.SKIP_UNSUPPORTED:
                # 完全不支持的类，直接跳过（无 asset handler）
                setattr(instance, "parse_status", "skipped")
                setattr(instance, "fallback_reason", f"skip_unsupported:{class_name}")
                setattr(exp, "parse_status", "skipped")
                setattr(exp, "fallback_reason", f"skip_unsupported:{class_name}")
                # 确保 properties 至少为空列表
                exp.properties = []
                logger.debug(
                    "Skipping export #%d (%s): unsupported class '%s'",
                    index,
                    instance.object_name,
                    class_name,
                )
                instance._preloaded = True
                self._preload_cache[index] = True
                return
            elif strategy == SerializationStrategy.OPAQUE_CLASS_PAYLOAD:
                # Opaque payload — 设置初始状态，但不 early return
                # 让 parse_properties_from_export() 调用 asset type handler
                # handler 可能会更新 parse_status 为 partial_metadata
                setattr(instance, "parse_status", "opaque")
                setattr(instance, "fallback_reason", f"opaque_payload:{class_name}")
                setattr(exp, "parse_status", "opaque")
                setattr(exp, "fallback_reason", f"opaque_payload:{class_name}")
                # 存储 ScriptSerialization 绝对偏移用于诊断
                if hasattr(exp, 'script_serialization_start_offset'):
                    exp._script_serialization_start_absolute = (
                        exp.serial_offset + exp.script_serialization_start_offset
                    )
                if hasattr(exp, 'script_serialization_end_offset'):
                    exp._script_serialization_end_absolute = (
                        exp.serial_offset + exp.script_serialization_end_offset
                    )
                logger.debug(
                    "Marking export #%d (%s) as opaque: class '%s' has custom Serialize()",
                    index,
                    instance.object_name,
                    class_name,
                )
                # 不 return，继续进入 parse_properties_from_export()
            # TAGGED_PROPERTIES_ONLY / FULL_SERIALIZER — 继续正常解析

        # === Offset Validation ===
        # 验证 serial_offset 范围（防止 4294967296 等溢出值导致崩溃）
        if instance.serial_offset < 0 or instance.serial_offset > self._file_size:
            self._diagnostics.append(OffsetRangeDiagnostic(
                module="linker",
                field="serial_offset",
                export_index=index,
                object_name=instance.object_name,
                target_offset=instance.serial_offset,
                file_size=self._file_size,
                source="preload",
                error=f"Export #{index} ({instance.object_name}) serial_offset {instance.serial_offset} 超出文件范围 [0, {self._file_size}]",
            ))
            instance._preloaded = True
            self._preload_cache[index] = True
            return

        # 验证 serial_offset + serial_size 不超出文件
        if instance.serial_offset + instance.serial_size > self._file_size:
            self._diagnostics.append(OffsetRangeDiagnostic(
                module="linker",
                field="serial_size",
                export_index=index,
                object_name=instance.object_name,
                target_offset=instance.serial_offset,
                read_size=instance.serial_size,
                file_size=self._file_size,
                source="preload",
                error=f"Export #{index} ({instance.object_name}) offset+size {instance.serial_offset}+{instance.serial_size} 超出文件大小 {self._file_size}",
            ))
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
            linker=self,
            mappings=mappings,
            game=game,
            tolerant=tolerant,
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
        2. 解析 WeakObjectProperty 引用
        3. 验证导入对象有效性
        4. 解析 template_index (CDO) 引用
        5. 构建依赖图
        """
        self._resolve_property_references()
        self._resolve_weak_references()
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

    def _resolve_weak_references(self) -> None:
        """将 WeakObjectProperty 的 FPackageIndex 解析为 UObjectInstance 弱引用。

        遍历所有已 preload 的 export 对象，填充 weak_references 字段。
        """
        for inst in self._export_objects:
            if not inst._preloaded:
                continue
            if not hasattr(inst, 'serialized_properties') or not inst.serialized_properties:
                continue
            for prop in inst.serialized_properties:
                if not isinstance(prop, dict):
                    continue
                if prop.get('type') == 'WeakObjectProperty':
                    pkg_idx = prop.get('value')
                    if isinstance(pkg_idx, int):
                        from uasset_read.serializers.object_resources import PackageIndex
                        resolved = self.resolve_package_index(PackageIndex(pkg_idx))
                        if resolved:
                            inst.weak_references.append(resolved)

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

        DependsMap values are FPackageIndex (int32):
        - Positive: export index (1-based)
        - Negative: import index (-1 based)
        - Zero: null

        DependsMap[export_index] = [FPackageIndex 列表]
        """
        if not hasattr(self._summary, 'depends_map') or not self._summary.depends_map:
            return

        from uasset_read.serializers.object_resources import PackageIndex

        depends_map = self._summary.depends_map
        for exp_idx, dep_indices in enumerate(depends_map):
            if exp_idx >= len(self._export_objects):
                continue

            inst = self._export_objects[exp_idx]
            inst.dependencies = []

            for raw_dep in dep_indices:
                if raw_dep == 0:
                    # Null dependency, skip
                    continue

                # Convert FPackageIndex to UObjectInstance
                pkg_idx = PackageIndex(raw_dep)
                resolved = self.resolve_package_index(pkg_idx)

                if resolved is not None:
                    inst.dependencies.append(resolved)
                else:
                    # Record diagnostic for unresolvable dependency
                    self._diagnostics.append(OffsetRangeDiagnostic(
                        module="linker",
                        field="DependsMap",
                        export_index=exp_idx,
                        target_offset=raw_dep,
                        source="_build_dependency_graph",
                        error=f"Export #{exp_idx} dependency {raw_dep} could not be resolved",
                    ))
