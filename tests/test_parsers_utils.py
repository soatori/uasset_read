"""测试 parsers 共享辅助函数"""
import pytest
from unittest.mock import MagicMock


def test_resolve_name_from_index_valid():
    from uasset_read.parsers.utils import resolve_name_from_index
    assert resolve_name_from_index(None, ["A", "B"], 0) == "A"
    assert resolve_name_from_index(None, ["A", "B"], 1) == "B"


def test_resolve_name_from_index_out_of_bounds():
    from uasset_read.parsers.utils import resolve_name_from_index
    assert resolve_name_from_index(None, ["A"], 99, "bone") == "bone_99"
    assert resolve_name_from_index(None, [], 0) == "param_0"


def test_read_validated_count_ok():
    from uasset_read.parsers.utils import read_validated_count
    archive = MagicMock()
    archive.read_int32.return_value = 5
    assert read_validated_count(archive, 100, "test") == 5


def test_read_validated_count_negative():
    from uasset_read.parsers.utils import read_validated_count
    archive = MagicMock()
    archive.read_int32.return_value = -1
    with pytest.raises(ValueError, match="不能为负数"):
        read_validated_count(archive, 100, "test")


def test_read_validated_count_exceeds_max():
    from uasset_read.parsers.utils import read_validated_count
    archive = MagicMock()
    archive.read_int32.return_value = 200
    with pytest.raises(ValueError, match="超过最大值"):
        read_validated_count(archive, 100, "test")


def test_make_enum_value():
    from uasset_read.parsers.utils import make_enum_value
    result = make_enum_value("EMyEnum", "Val")
    assert result == {"enum_type": "EMyEnum", "value_name": "EMyEnum::Val"}


def test_extract_inner_from_tag_with_parens():
    from uasset_read.parsers.utils import extract_inner_from_tag
    assert extract_inner_from_tag("Array(IntProperty)") == "IntProperty"
    assert extract_inner_from_tag("Map(StrProperty, BoolProperty)") == "StrProperty, BoolProperty"


def test_extract_inner_from_tag_without_parens():
    from uasset_read.parsers.utils import extract_inner_from_tag
    assert extract_inner_from_tag("IntProperty") is None
    assert extract_inner_from_tag("") is None
