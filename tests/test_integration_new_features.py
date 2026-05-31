# tests/test_integration_new_features.py
"""新功能端到端集成测试"""


def test_iostore_and_objects_import():
    """测试所有新模块可一起导入"""
    from uasset_read import (
        IoStoreReader,
        UObject,
        ObjectTypeRegistry,
        UStaticMesh,
        UTexture2D,
        UMaterial,
        FBulkDataHeader,
        BulkDataFlags,
    )

    assert IoStoreReader is not None
    assert UObject is not None
    assert ObjectTypeRegistry is not None
    assert UStaticMesh is not None
    assert UTexture2D is not None
    assert UMaterial is not None
    assert FBulkDataHeader is not None
    assert BulkDataFlags is not None


def test_object_registry_workflow():
    """测试对象注册表工作流"""
    from uasset_read import ObjectTypeRegistry, UObject, UStaticMesh

    registry = ObjectTypeRegistry()

    # 注册
    @registry.register("TestAsset")
    class TestAsset(UObject):
        pass

    # 查找
    cls = registry.get_class("TestAsset")
    assert cls == TestAsset

    # 蓝图生成类后缀
    cls = registry.get_class("TestAsset_C")
    assert cls == TestAsset

    # 未知类型
    cls = registry.get_class("UnknownType")
    assert cls == UObject
