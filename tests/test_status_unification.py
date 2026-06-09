"""验证 ParseResult.status 对所有 partial 状态的正确处理。"""
import pytest
from unittest.mock import MagicMock
from uasset_read.models.result import ParseResult


def _make_result(parse_status: str) -> ParseResult:
    """构造含指定 parse_status 导出的 ParseResult。"""
    result = ParseResult()
    result.summary = MagicMock()
    mock_export = MagicMock()
    mock_export.parse_status = parse_status
    result.export_map = [mock_export]
    return result


def test_status_partial_metadata():
    """含 partial_metadata 导出 → partial"""
    assert _make_result("partial_metadata").status == "partial"


def test_status_opaque_unversioned():
    """含 opaque_unversioned 导出 → partial"""
    assert _make_result("opaque_unversioned").status == "partial"


def test_status_fallback():
    """含 fallback 导出 → partial"""
    assert _make_result("fallback").status == "partial"


def test_status_mixed_success_and_partial():
    """混合 success + partial_metadata → partial"""
    result = ParseResult()
    result.summary = MagicMock()
    s1 = MagicMock(); s1.parse_status = "success"
    s2 = MagicMock(); s2.parse_status = "partial_metadata"
    result.export_map = [s1, s2]
    assert result.status == "partial"


def test_status_all_success():
    """所有 success → success"""
    assert _make_result("success").status == "success"


def test_status_opaque():
    """含 opaque 导出 → partial（已有逻辑，回归）"""
    assert _make_result("opaque").status == "partial"
