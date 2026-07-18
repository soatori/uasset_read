"""tests/core/test_status_validation.py — parse_status 验证器测试。"""
import pytest


def test_validate_parse_status_valid():
    """有效 parse_status 值应原样返回。"""
    from uasset_read.models.validators import validate_parse_status

    assert validate_parse_status("success") == "success"
    assert validate_parse_status("opaque") == "opaque"
    assert validate_parse_status("partial_metadata") == "partial_metadata"


def test_validate_parse_status_all_valid():
    """所有 ExportParseStatus 枚举值均应通过验证。"""
    from uasset_read.models.validators import validate_parse_status
    from uasset_read.models.fallback import ExportParseStatus

    for status in ExportParseStatus:
        assert validate_parse_status(status.value) == status.value


def test_validate_parse_status_invalid():
    """无效 parse_status 应抛出 ValueError。"""
    from uasset_read.models.validators import validate_parse_status

    with pytest.raises(ValueError):
        validate_parse_status("invalid_status")
    with pytest.raises(ValueError):
        validate_parse_status("ok")


def test_validate_parse_status_error_message():
    """错误信息应包含无效值和合法值集合。"""
    from uasset_read.models.validators import validate_parse_status

    with pytest.raises(ValueError, match=r"Invalid parse_status.*bogus"):
        validate_parse_status("bogus")
