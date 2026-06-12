"""Object Resources — ObjectImport, ObjectExport, PackageIndex 及相关读取函数。

从 uasset_read.py 提取（第 940-3048 行核心部分）。
"""
from __future__ import annotations

from .models import (
    PackageIndex,
    ResolvedPackageIndex,
    ObjectImport,
    ObjectExport,
)

from .readers import (
    read_import_map,
    read_soft_object_paths,
    read_export_map,
)

from .resolvers import (
    build_imports_list,
    detect_circular_deps,
    get_asset_class,
    resolve_class_name,
    detect_blueprint,
    detect_blueprint_generated_class,
    validate_package_index,
    resolve_class_name_with_linker,
    get_asset_class_with_linker,
    detect_blueprint_with_linker,
    resolve_parent_class_with_linker,
    find_main_blueprint_generated_class,
    resolve_parent_class,
    resolve_package_index_to_reference,
)

__all__ = [
    # Data models
    "PackageIndex",
    "ResolvedPackageIndex",
    "ObjectImport",
    "ObjectExport",
    # Readers
    "read_import_map",
    "read_soft_object_paths",
    "read_export_map",
    # Resolvers
    "build_imports_list",
    "detect_circular_deps",
    "get_asset_class",
    "resolve_class_name",
    "detect_blueprint",
    "detect_blueprint_generated_class",
    "validate_package_index",
    "resolve_class_name_with_linker",
    "get_asset_class_with_linker",
    "detect_blueprint_with_linker",
    "resolve_parent_class_with_linker",
    "find_main_blueprint_generated_class",
    "resolve_parent_class",
    "resolve_package_index_to_reference",
]
