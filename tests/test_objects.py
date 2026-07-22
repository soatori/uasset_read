"""UObject 注册与引用解析测试。"""
from __future__ import annotations

import pytest

from uasset_read.objects.registry import ObjectTypeRegistry, global_registry
from uasset_read.objects.uobject import UObject


class TestObjectTypeRegistry:
    """ObjectTypeRegistry 注册与查找。"""

    def test_decorator_register_and_get_class(self):
        """装饰器注册后可通过 get_class 查找。"""
        registry = ObjectTypeRegistry()

        @registry.register("MyCustomClass")
        class UMyCustomClass(UObject):
            pass

        found = registry.get_class("MyCustomClass")
        assert found is UMyCustomClass

    def test_get_class_unknown_returns_uobject(self):
        """未注册类型返回 UObject 基类。"""
        registry = ObjectTypeRegistry()
        found = registry.get_class("UnknownClass")
        assert found is UObject

    def test_get_class_strips_c_suffix(self):
        """蓝图生成类 _C 后缀应被剥离后查找。"""
        registry = ObjectTypeRegistry()

        @registry.register("StaticMesh")
        class UStaticMesh(UObject):
            pass

        found = registry.get_class("StaticMesh_C")
        assert found is UStaticMesh


class TestUObjectBasic:
    """UObject 基础构造。"""

    def test_uobject_creation_and_properties(self):
        """UObject 应正确设置属性并支持 get/set。"""
        obj = UObject(name="TestObject")
        assert obj.name == "TestObject"
        assert obj.flags == 0
        assert obj.outer is None
        obj.set_property("CustomData", 42)
        assert obj.get_property("CustomData") == 42
        assert obj.get_property("Missing", "default") == "default"
