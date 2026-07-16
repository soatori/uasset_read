"""jmap 属性递归深度限制测试。"""
import pytest
from uasset_read.parsers.usmap import _jmap_prop_type


def _make_nested_dict(depth: int) -> dict:
    """构造 depth 层嵌套的 jmap 属性 dict。"""
    node = {"type": "StrProperty"}
    for _ in range(depth):
        node = {"type": "ArrayProperty", "container": node}
    return node


class TestJmapRecursionDepth:
    def test_normal_depth_succeeds(self):
        """正常深度（<64）应成功解析。"""
        prop = _make_nested_dict(10)
        result = _jmap_prop_type(prop)
        assert result.type_name == "ArrayProperty"

    def test_depth_at_limit_succeeds(self):
        """恰好等于限制深度应成功。"""
        prop = _make_nested_dict(63)
        result = _jmap_prop_type(prop)
        assert result is not None

    def test_depth_exceeding_limit_raises(self):
        """超过限制深度应抛出 ValueError。"""
        prop = _make_nested_dict(65)
        with pytest.raises(ValueError, match="递归深度"):
            _jmap_prop_type(prop)

    def test_depth_tracking_is_correct(self):
        """depth 参数应正确传递。"""
        prop = {"type": "ArrayProperty", "container": {"type": "StrProperty"}}
        result = _jmap_prop_type(prop, depth=62)
        assert result is not None
        with pytest.raises(ValueError):
            _jmap_prop_type(prop, depth=64)
