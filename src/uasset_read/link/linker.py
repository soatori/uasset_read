from __future__ import annotations

"""PackageLinker — two-phase loading coordinator.

Mirrors UE's FLinkerLoad pattern: link() creates UObjectInstance shells,
preload(index) lazily deserializes properties on demand.
"""

import logging
import re
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.package_summary import PackageFileSummary
    from uasset_read.serializers.object_resources import (
        ObjectImport, ObjectExport, PackageIndex,
    )
    from uasset_read.versioning import VersionContainer

from uasset_read.bounded_events import BoundedEventBuffer
from uasset_read.serializers.object_resources import resolve_class_name
from uasset_read.link.object_instance import UObjectInstance
from uasset_read.models.diagnostics import OffsetRangeDiagnostic
from uasset_read.models.validators import validate_parse_status

logger = logging.getLogger(__name__)

# # World Partition path normalization regex: matches _<digits> suffix at end of path segment
_WP_HASH_RE = re.compile(r'_(\d{3,})$')


def normalize_world_partition_path(path: str) -> str:
    """Strip World Partition hash suffix to normalize import paths.

    World Partition generates paths like ``/Script/Engine_3103784960`` for
    external sub-packages, where ``_3103784960`` is a numeric MD5-based hash
    suffix. This function restores such paths to the base module path
    (e.g. ``/Script/Engine``) for path matching.

    Only strips the suffix from the last segment (after ``split('/')``),
    and requires at least 3 digits to avoid false positives on normal
    identifiers.

    Args:
        path: Raw import path (e.g. ``/Script/Engine_3103784960``)

    Returns:
        Normalized path (e.g. ``/Script/Engine``). Returned as-is if no hash suffix.
    """
    if not path:
        return path
    last_slash = path.rfind('/')
    if last_slash < 0:
        segment = path
        prefix = ''
    else:
        segment = path[last_slash + 1:]
        prefix = path[:last_slash + 1]
    normalized_segment = _WP_HASH_RE.sub('', segment)
    return prefix + normalized_segment


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
        self._diagnostics: BoundedEventBuffer = BoundedEventBuffer(max_entries=10000)
        self._file_size: int = getattr(archive, '_file_size', 0)
        self._import_verification_errors: List[str] = []

    @property
    def diagnostics(self) -> List[OffsetRangeDiagnostic]:
        """Return all offset diagnostic records."""
        return list(self._diagnostics.entries)

    def link(self) -> None:
        """Create UObjectInstance shells from import/export maps.

        Note: The current implementation creates all instances at once.
        For very large packages (>10000 objects), lazy creation optimization may be considered.
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

            # Early validation of serial_offset (prevent overflow values from propagating to preload phase)
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
                    error=f"Export #{idx} ({obj_name}) serial_offset {serial_offset} out of file range [0, {self._file_size}]",
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

        # Resolve super_index (parent class reference)
        for idx, exp in enumerate(self._export_map):
            if idx < len(self._export_objects):
                inst = self._export_objects[idx]
                if hasattr(exp, 'super_index') and exp.super_index and not exp.super_index.is_null:
                    super_inst = self.resolve_package_index(exp.super_index)
                    if super_inst is not None:
                        inst.super_object = super_inst

    def export_objects(self) -> List[UObjectInstance]:
        """Return a read-only copy of the export objects list."""
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
            # Out-of-bounds diagnostic
            self._diagnostics.append(OffsetRangeDiagnostic(
                module="linker",
                field="PackageIndex",
                export_index=idx,
                file_size=self._file_size,
                source="resolve_package_index",
                error=f"Export PackageIndex {pkg_idx.index} (idx={idx}) out of bounds, export count {len(self._export_objects)}",
            ))
            return None
        if pkg_idx.is_import:
            idx = pkg_idx.to_import_index()
            if 0 <= idx < len(self._import_objects):
                return self._import_objects[idx]
            # Out-of-bounds diagnostic
            self._diagnostics.append(OffsetRangeDiagnostic(
                module="linker",
                field="PackageIndex",
                import_index=idx,
                file_size=self._file_size,
                source="resolve_package_index",
                error=f"Import PackageIndex {pkg_idx.index} (idx={idx}) out of bounds, import count {len(self._import_objects)}",
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

        # === NoneType Guard (#328) ===
        # Prevent TypeError when serial_offset/serial_size is None
        if self._archive is None:
            logger.warning("preload: archive is None for export #%d", index)
            instance._preloaded = True
            self._preload_cache[index] = True
            return
        if instance.serial_offset is None or instance.serial_size is None:
            logger.warning(
                "preload: export %d (%s) has None serial_offset or serial_size, skipping",
                index, instance.object_name,
            )
            instance._preloaded = True
            self._preload_cache[index] = True
            return

        # === Class Serialization Strategy Check ===
        # For SKIP_UNSUPPORTED classes, intercept early at the linker layer
        # For OPAQUE_CLASS_PAYLOAD classes, set initial state but do not early return;
        # let parse_properties_from_export() call the asset type handler to extract metadata
        # See Issue #23: class serialization strategy should not bypass asset type handler
        from uasset_read.parsers.class_serialization_strategy import (
            get_serialization_strategy,
            SerializationStrategy,
        )
        class_name = instance.object_class
        if class_name is not None:
            strategy = get_serialization_strategy(class_name)
            exp = self._export_map[index]
            if strategy == SerializationStrategy.SKIP_UNSUPPORTED:
                # Completely unsupported class, skip directly (no asset handler)
                setattr(instance, "parse_status", validate_parse_status("skipped"))
                setattr(instance, "fallback_reason", f"skip_unsupported:{class_name}")
                setattr(exp, "parse_status", validate_parse_status("skipped"))
                setattr(exp, "fallback_reason", f"skip_unsupported:{class_name}")
                # Ensure properties is at least an empty list
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
                # Opaque payload — set initial state, but do not early return
                # let parse_properties_from_export() call the asset type handler
                # the handler may update parse_status to partial_metadata
                setattr(instance, "parse_status", validate_parse_status("opaque"))
                setattr(instance, "fallback_reason", f"opaque_payload:{class_name}")
                setattr(exp, "parse_status", validate_parse_status("opaque"))
                setattr(exp, "fallback_reason", f"opaque_payload:{class_name}")
                # Store ScriptSerialization absolute offset for diagnostics
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
                # Do not return; continue to parse_properties_from_export()
            # TAGGED_PROPERTIES_ONLY — continue normal parsing

        # === Offset Validation ===
        # Validate serial_offset range (prevent overflow values like 4294967296 from causing crashes)
        if instance.serial_offset < 0 or instance.serial_offset > self._file_size:
            self._diagnostics.append(OffsetRangeDiagnostic(
                module="linker",
                field="serial_offset",
                export_index=index,
                object_name=instance.object_name,
                target_offset=instance.serial_offset,
                file_size=self._file_size,
                source="preload",
                error=f"Export #{index} ({instance.object_name}) serial_offset {instance.serial_offset} out of file range [0, {self._file_size}]",
            ))
            instance._preloaded = True
            self._preload_cache[index] = True
            return

        # === serial_size validation ===
        # Negative value check (prevent offset+size producing unexpected results)
        if instance.serial_size < 0:
            self._diagnostics.append(OffsetRangeDiagnostic(
                module="linker",
                field="serial_size",
                export_index=index,
                object_name=instance.object_name,
                target_offset=instance.serial_offset,
                read_size=instance.serial_size,
                file_size=self._file_size,
                source="preload",
                error=f"Export #{index} ({instance.object_name}) serial_size {instance.serial_size} is negative",
            ))
            instance._preloaded = True
            self._preload_cache[index] = True
            return

        # Zero-value skip (executed after offset validation so invalid offsets are diagnosed first)
        if instance.serial_size == 0:
            instance._preloaded = True
            self._preload_cache[index] = True
            return

        # Validate serial_offset + serial_size does not exceed file size
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
                error=f"Export #{index} ({instance.object_name}) offset+size {instance.serial_offset}+{instance.serial_size} exceeds file size {self._file_size}",
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
        """Stage 4: Post-processing phase (mirrors UE FLinkerLoad::PostLoad).

        Executed after all object creation and preloading:
        1. Resolve ObjectProperty references
        2. Resolve WeakObjectProperty references
        3. Validate import object validity
        4. Resolve template_index (CDO) references
        5. Build dependency graph
        """
        self._resolve_property_references()
        self._resolve_weak_references()
        self._import_verification_errors = self._verify_imports()
        self._resolve_template_objects()
        self._build_dependency_graph()

    def _resolve_property_references(self) -> None:
        """Resolve ObjectProperty FPackageIndex values to UObjectInstance references.

        Iterates over all preloaded export objects and populates the
        property_references field. Supports both int and PackageIndex value types.
        """
        from uasset_read.serializers.object_resources import PackageIndex
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
                    if isinstance(pkg_idx, PackageIndex):
                        resolved = self.resolve_package_index(pkg_idx)
                    elif isinstance(pkg_idx, int):
                        resolved = self.resolve_package_index(PackageIndex(pkg_idx))
                    else:
                        continue
                    if resolved:
                        prop_name = prop.get('name', '')
                        if not hasattr(inst, 'property_references'):
                            inst.property_references = {}
                        inst.property_references[prop_name] = resolved

    def _resolve_weak_references(self) -> None:
        """Resolve WeakObjectProperty FPackageIndex values to UObjectInstance weak references.

        Iterates over all preloaded export objects and populates the
        weak_references field. Supports both int and PackageIndex value types.
        """
        from uasset_read.serializers.object_resources import PackageIndex
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
                    if isinstance(pkg_idx, PackageIndex):
                        resolved = self.resolve_package_index(pkg_idx)
                    elif isinstance(pkg_idx, int):
                        resolved = self.resolve_package_index(PackageIndex(pkg_idx))
                    else:
                        continue
                    if resolved:
                        inst.weak_references.append(resolved)

    def _verify_imports(self) -> List[str]:
        """Validate all import objects.

        Returns:
            List of validation errors (used for warnings in tolerant mode).
        """
        errors = []
        for idx, imp in enumerate(self._import_map):
            inst = self._import_objects[idx] if idx < len(self._import_objects) else None
            if inst is None:
                continue

            # Validate class_name index in name_map
            if isinstance(imp.class_name, int):
                if imp.class_name < 0 or imp.class_name >= len(self._name_map):
                    errors.append(f"Import {inst.object_name}: class_name index {imp.class_name} out of bounds")
            elif isinstance(imp.class_name, str) and not imp.class_name:
                errors.append(f"Import {inst.object_name}: class_name is empty")

            # Validate outer_index
            if hasattr(imp, 'outer_index') and imp.outer_index and not imp.outer_index.is_null:
                outer_inst = self.resolve_package_index(imp.outer_index)
                if outer_inst is None:
                    # World Partition sub-package hashed path (e.g. /Script/Engine_3103784960)
                    # Its outer_index may reference a package not included in the current
                    # import table. This is normal sub-package splitting behavior; downgrade to debug.
                    obj_name = inst.object_name
                    if isinstance(obj_name, str) and _WP_HASH_RE.search(obj_name):
                        logger.debug(
                            "Import %s: outer_index unresolvable (World Partition hashed path, ignored)",
                            obj_name,
                        )
                    else:
                        errors.append(f"Import {inst.object_name}: outer_index unresolvable")

        return errors

    def _resolve_template_objects(self) -> None:
        """Resolve template_index (CDO) references for export objects.

        Sets template_object attribute on each preloaded export.
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
        """Convert DependsMap into UObjectInstance dependency links.

        DependsMap values are FPackageIndex (int32):
        - Positive: export index (1-based)
        - Negative: import index (-1 based)
        - Zero: null

        DependsMap[export_index] = [FPackageIndex list]
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

                # Type validation: only accept int-typed FPackageIndex values
                if not isinstance(raw_dep, int):
                    self._diagnostics.append(OffsetRangeDiagnostic(
                        module="linker",
                        field="DependsMap",
                        export_index=exp_idx,
                        source="_build_dependency_graph",
                        error=f"Export #{exp_idx} dependency has unexpected type: {type(raw_dep).__name__}({raw_dep})",
                    ))
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
