"""UObject 基类和类型注册表测试"""
def test_uobject_creation():
    """测试 UObject 创建"""
    from uasset_read.objects.uobject import UObject

    obj = UObject(name="TestObject", flags=0)
    assert obj.name == "TestObject"
    assert obj.flags == 0

def test_registry_registration():
    """测试类型注册"""
    from uasset_read.objects.registry import ObjectTypeRegistry
    from uasset_read.objects.uobject import UObject

    registry = ObjectTypeRegistry()

    # 注册一个测试类
    @registry.register("TestAsset")
    class TestAsset(UObject):
        pass

    assert "TestAsset" in registry.classes
    assert registry.get_class("TestAsset") == TestAsset

def test_registry_get_unknown():
    """测试获取未知类型返回 UObject"""
    from uasset_read.objects.registry import ObjectTypeRegistry
    from uasset_read.objects.uobject import UObject

    registry = ObjectTypeRegistry()
    cls = registry.get_class("UnknownType")
    assert cls == UObject

def test_registry_suffix_stripping():
    """测试后缀剥离（_C 蓝图生成类）"""
    from uasset_read.objects.registry import ObjectTypeRegistry
    from uasset_read.objects.uobject import UObject

    registry = ObjectTypeRegistry()

    @registry.register("TestAsset")
    class TestAsset(UObject):
        pass

    # 查找 TestAsset_C 应该返回 TestAsset
    cls = registry.get_class("TestAsset_C")
    assert cls == TestAsset
