"""验证 FObjectExport 缺失字段已正确实现。"""
import pytest


def test_export_entry_has_preload_dependency_fields():
    """ExportEntry 包含所有 PreloadDependency 字段"""
    from uasset_read.serializers.object_resources import ObjectExport
    import dataclasses
    field_names = {f.name for f in dataclasses.fields(ObjectExport)}
    expected = {
        'first_export_dependency',
        'serialization_before_serialization_dependencies',
        'create_before_serialization_dependencies',
        'serialization_before_create_dependencies',
        'create_before_create_dependencies',
    }
    missing = expected - field_names
    assert not missing, f"ObjectExport 缺少字段: {missing}"


def test_export_entry_has_script_serialization_fields():
    """ExportEntry 包含 ScriptSerializationOffset 字段"""
    from uasset_read.serializers.object_resources import ObjectExport
    import dataclasses
    field_names = {f.name for f in dataclasses.fields(ObjectExport)}
    assert 'script_serialization_start_offset' in field_names
    assert 'script_serialization_end_offset' in field_names


def test_export_entry_has_inherited_and_hash_flags():
    """ExportEntry 包含 bIsInheritedInstance 和 bGeneratePublicHash"""
    from uasset_read.serializers.object_resources import ObjectExport
    import dataclasses
    field_names = {f.name for f in dataclasses.fields(ObjectExport)}
    assert 'b_is_inherited_instance' in field_names
    assert 'b_generate_public_hash' in field_names


def test_export_preload_default_values():
    """PreloadDependency 默认值正确"""
    from uasset_read.serializers.object_resources import ObjectExport, PackageIndex
    e = ObjectExport(
        class_index=PackageIndex(0), super_index=PackageIndex(0), outer_index=PackageIndex(0),
        object_name="Test", object_flags=0,
        serial_size=0, serial_offset=0,
    )
    assert e.first_export_dependency == -1
    assert e.serialization_before_serialization_dependencies == 0
    assert e.script_serialization_start_offset == 0
    assert e.b_is_inherited_instance is False
    assert e.b_generate_public_hash is False


def test_export_entry_alias_from_init():
    """验证 ExportEntry 别名从 __init__ 正确导出"""
    from uasset_read import ExportEntry
    from uasset_read.serializers.object_resources import ObjectExport
    assert ExportEntry is ObjectExport