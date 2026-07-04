"""测试 BasePropertyOverrides 提取"""
import unittest
from unittest.mock import MagicMock

from uasset_read.objects.exports.material import (
    _collect_base_property_overrides,
    _BASE_PROPERTY_OVERRIDE_NAMES,
)


class TestBasePropertyOverrides(unittest.TestCase):
    """测试 _collect_base_property_overrides"""

    def test_empty_source(self):
        """空输入返回空 dict"""
        self.assertEqual(_collect_base_property_overrides(None), {})
        self.assertEqual(_collect_base_property_overrides({}), {})
        self.assertEqual(_collect_base_property_overrides([]), {})

    def test_dict_passthrough(self):
        """dict 输入直接返回"""
        data = {"BlendMode": 1, "TwoSided": True}
        result = _collect_base_property_overrides(data)
        self.assertEqual(result, data)

    def test_extracts_overridden_properties(self):
        """提取被 override 的属性"""
        mock_obj = MagicMock()
        # 模拟 prop_value 调用
        mock_props = {
            "bOverride_BlendMode": True,
            "BlendMode": 2,
            "bOverride_TwoSided": True,
            "TwoSided": True,
            "bOverride_ShadingModel": False,  # 未 override
            "ShadingModel": 1,  # 即使有值也不应被提取
        }
        def mock_prop_value(obj, *names, default=None):
            for name in names:
                if name in mock_props:
                    return mock_props[name]
            return default

        import uasset_read.objects.exports.material as mat_mod
        original_prop_value = mat_mod.prop_value
        mat_mod.prop_value = mock_prop_value
        try:
            result = _collect_base_property_overrides(mock_obj)
            self.assertEqual(result, {"BlendMode": 2, "TwoSided": True})
        finally:
            mat_mod.prop_value = original_prop_value

    def test_override_flag_names(self):
        """确认所有 override 标记名格式正确"""
        for name in _BASE_PROPERTY_OVERRIDE_NAMES:
            self.assertTrue(name[0].isupper() or name.startswith("b"),
                            f"属性名应以大写字母或 b 开头: {name}")


if __name__ == "__main__":
    unittest.main()
