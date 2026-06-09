"""Task 1: FPackageIndex 语义解析测试 (#42)"""
import pytest
from uasset_read.serializers.object_resources import PackageIndex, ObjectImport, ObjectExport


def test_package_index_null():
    """Index = 0 表示 null 引用"""
    idx = PackageIndex(index=0)
    assert idx.is_null
    assert not idx.is_import
    assert not idx.is_export
    assert idx.resolved_type == "null"


def test_package_index_import():
    """Index < 0 表示 Import，实际下标 = -Index - 1"""
    idx = PackageIndex(index=-3)
    assert idx.is_import
    assert not idx.is_export
    assert idx.import_index == 2  # -(-3) - 1 = 2
    assert idx.resolved_type == "import"


def test_package_index_export():
    """Index > 0 表示 Export，实际下标 = Index - 1"""
    idx = PackageIndex(index=5)
    assert idx.is_export
    assert not idx.is_import
    assert idx.export_index == 4  # 5 - 1 = 4
    assert idx.resolved_type == "export"


def test_package_index_resolution_with_context():
    """提供 ImportMap/ExportMap 上下文时，解析目标名称"""
    # Mock import/export map
    import_map = [
        ObjectImport(
            class_package="/Script/CoreUObject",
            class_name="Class",
            outer_index=PackageIndex(0),
            object_name="BlueprintGeneratedClass"
        ),
        ObjectImport(
            class_package="/Script/UMGEditor",
            class_name="Class",
            outer_index=PackageIndex(0),
            object_name="WidgetTree"
        ),
    ]
    export_map = [
        ObjectExport(
            class_index=PackageIndex(-1),
            super_index=PackageIndex(0),
            outer_index=PackageIndex(0),
            object_name="MyBlueprint",
            object_flags=0,
            serial_size=100,
            serial_offset=200,
        ),
    ]

    idx = PackageIndex(index=-1)
    resolved = idx.resolve(import_map=import_map, export_map=export_map)
    assert resolved.name == "BlueprintGeneratedClass"
    assert resolved.full_path == "/Script/CoreUObject.BlueprintGeneratedClass"
    assert resolved.ref_type == "import"


def test_package_index_resolution_export():
    """解析 Export 引用"""
    import_map = []
    export_map = [
        ObjectExport(
            class_index=PackageIndex(0),
            super_index=PackageIndex(0),
            outer_index=PackageIndex(0),
            object_name="Default__MyActor",
            object_flags=0,
            serial_size=100,
            serial_offset=200,
        ),
    ]

    idx = PackageIndex(index=1)
    resolved = idx.resolve(import_map=import_map, export_map=export_map)
    assert resolved.name == "Default__MyActor"
    assert resolved.full_path == "Default__MyActor"
    assert resolved.ref_type == "export"


def test_package_index_resolution_null():
    """解析 Null 引用"""
    import_map = []
    export_map = []

    idx = PackageIndex(index=0)
    resolved = idx.resolve(import_map=import_map, export_map=export_map)
    assert resolved.name == "None"
    assert resolved.full_path == "None"
    assert resolved.ref_type == "null"


def test_resolved_package_index_to_dict():
    """ResolvedPackageIndex.to_dict() 序列化"""
    import_map = [
        ObjectImport(
            class_package="/Script/CoreUObject",
            class_name="Class",
            outer_index=PackageIndex(0),
            object_name="BlueprintGeneratedClass"
        ),
    ]
    export_map = []

    idx = PackageIndex(index=-1)
    resolved = idx.resolve(import_map=import_map, export_map=export_map)
    result = resolved.to_dict()

    assert result["type"] == "import"
    assert result["name"] == "BlueprintGeneratedClass"
    assert result["full_path"] == "/Script/CoreUObject.BlueprintGeneratedClass"
