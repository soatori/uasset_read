"""Task 2: Export PreloadDependency 字段测试 (#43)"""
import pytest
from uasset_read.serializers.object_resources import ObjectExport, PackageIndex


def test_export_has_preload_dependency_fields():
    """ObjectExport 包含 UE5 PreloadDependency 字段"""
    export = ObjectExport(
        class_index=PackageIndex(-1),
        super_index=PackageIndex(0),
        outer_index=PackageIndex(0),
        object_name="TestExport",
        object_flags=0,
        serial_size=100,
        serial_offset=200,
    )

    # 验证默认值
    assert hasattr(export, "first_export_dependency")
    assert hasattr(export, "serialization_before_serialization_dependencies")
    assert hasattr(export, "create_before_serialization_dependencies")
    assert hasattr(export, "serialization_before_create_dependencies")
    assert hasattr(export, "create_before_create_dependencies")

    # 验证默认值正确
    assert export.first_export_dependency == -1
    assert export.serialization_before_serialization_dependencies == 0
    assert export.create_before_serialization_dependencies == 0
    assert export.serialization_before_create_dependencies == 0
    assert export.create_before_create_dependencies == 0


def test_export_set_preload_dependency_values():
    """可以设置 PreloadDependency 字段的值"""
    export = ObjectExport(
        class_index=PackageIndex(-1),
        super_index=PackageIndex(0),
        outer_index=PackageIndex(0),
        object_name="TestExport",
        object_flags=0,
        serial_size=100,
        serial_offset=200,
        first_export_dependency=10,
        serialization_before_serialization_dependencies=5,
        create_before_serialization_dependencies=3,
        serialization_before_create_dependencies=2,
        create_before_create_dependencies=1,
    )

    assert export.first_export_dependency == 10
    assert export.serialization_before_serialization_dependencies == 5
    assert export.create_before_serialization_dependencies == 3
    assert export.serialization_before_create_dependencies == 2
    assert export.create_before_create_dependencies == 1


def test_export_ue5_fields_exist():
    """验证其他 UE5 字段仍然存在"""
    export = ObjectExport(
        class_index=PackageIndex(-1),
        super_index=PackageIndex(0),
        outer_index=PackageIndex(0),
        object_name="TestExport",
        object_flags=0,
        serial_size=100,
        serial_offset=200,
        b_is_inherited_instance=True,
        b_generate_public_hash=True,
        script_serialization_start_offset=500,
        script_serialization_end_offset=600,
    )

    assert export.b_is_inherited_instance is True
    assert export.b_generate_public_hash is True
    assert export.script_serialization_start_offset == 500
    assert export.script_serialization_end_offset == 600
    assert export.script_serialization_size == 100
    assert export.has_script_serialization is True
