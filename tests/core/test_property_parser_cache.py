"""测试 _TYPE_HANDLER_MAP 缓存机制（parsers/property_parser.py）。"""

import uasset_read.parsers.property_parser as pp


class TestGetParseFunctionsCache:
    """_get_parse_functions() 模块级缓存行为。"""

    def test_returns_dict_with_all_known_property_types(self):
        """首次调用返回包含所有已知属性类型的映射表。"""
        result = pp._get_parse_functions()
        expected_keys = [
            "BoolProperty", "IntProperty", "Int64Property", "Int16Property",
            "Int8Property", "ByteProperty", "UInt16Property", "UInt32Property",
            "UInt64Property", "FloatProperty", "DoubleProperty", "StrProperty",
            "NameProperty", "ObjectProperty", "SoftObjectProperty", "ArrayProperty",
            "StructProperty", "MapProperty", "SetProperty", "EnumProperty",
            "TextProperty", "DelegateProperty", "Utf8StrProperty",
            "WeakObjectProperty", "LazyObjectProperty", "ClassProperty",
            "SoftClassProperty", "AssetObjectProperty", "AssetClassProperty",
            "MulticastDelegateProperty", "MulticastInlineDelegateProperty",
            "MulticastSparseDelegateProperty", "InterfaceProperty",
            "FieldPathProperty", "OptionalProperty", "VerseStringProperty",
            "VerseClassProperty", "VerseFunctionProperty", "VerseDynamicProperty",
            "VerseCellProperty", "VerseValueProperty", "AnsiStrProperty",
            "GuidProperty",
        ]
        assert isinstance(result, dict)
        for key in expected_keys:
            assert key in result, f"缺少已知属性类型 key: {key}"

    def test_all_values_are_callable(self):
        """映射表中每个 value 都是 callable。"""
        result = pp._get_parse_functions()
        for key, handler in result.items():
            assert callable(handler), f"{key} 的值不可调用: {handler!r}"

    def test_second_call_returns_same_object(self):
        """第二次调用返回同一对象（id 相同），验证缓存生效。"""
        first = pp._get_parse_functions()
        second = pp._get_parse_functions()
        assert first is second
        assert id(first) == id(second)

