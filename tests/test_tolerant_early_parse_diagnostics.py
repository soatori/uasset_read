"""Tolerant early parse diagnostics regression tests."""
from __future__ import annotations

import json
import struct

import pytest

from uasset_read.constants import PACKAGE_FILE_TAG, UE5_PACKAGE_SAVED_HASH
from uasset_read.core import ParseError, parse_single
from uasset_read.parse_uasset import parse_package, parse_uasset_with_linker


def _package_with_bad_custom_version_count(count: int) -> bytes:
    data = bytearray()
    data += struct.pack("<Iiii", PACKAGE_FILE_TAG, -9, 0, 0)
    data += struct.pack("<i", UE5_PACKAGE_SAVED_HASH)
    data += b"\x00" * 20
    data += struct.pack("<i", 0)  # total_header_size
    data += struct.pack("<I", count)
    data += b"\x00" * 128
    return bytes(data)


def test_tolerant_json_summary_returns_parse_stage_diagnostic(tmp_path):
    path = tmp_path / "bad_custom_versions.uasset"
    path.write_bytes(_package_with_bad_custom_version_count(10_000_001))

    output = parse_single(str(path), format="json_summary", tolerant=True)
    data = json.loads(output)

    assert data["status"]["status"] == "failed"
    assert data["diagnostics"]
    stage_diagnostics = [
        d for d in data["diagnostics"] if d["kind"] == "parse_stage_error"
    ]
    assert stage_diagnostics
    assert stage_diagnostics[0]["fallback_used"] is True
    assert stage_diagnostics[0]["error"]


def test_strict_json_summary_still_raises_on_early_parse_failure(tmp_path):
    path = tmp_path / "bad_custom_versions.uasset"
    path.write_bytes(_package_with_bad_custom_version_count(10_000_001))

    with pytest.raises(ParseError):
        parse_single(str(path), format="json_summary", tolerant=False)


class TestStrictModeConsistency:
    """严格模式语义一致性：parse_package / parse_uasset_with_linker 在
    tolerant=False 时必须抛出异常，不能静默返回失败结果。"""

    def test_parse_package_strict_raises(self, tmp_path):
        path = tmp_path / "bad.uasset"
        path.write_bytes(_package_with_bad_custom_version_count(10_000_001))
        with pytest.raises(ParseError):
            parse_package(str(path), tolerant=False)

    def test_parse_uasset_with_linker_strict_raises(self, tmp_path):
        path = tmp_path / "bad.uasset"
        path.write_bytes(_package_with_bad_custom_version_count(10_000_001))
        with pytest.raises(ParseError):
            parse_uasset_with_linker(str(path), tolerant=False)

    def test_parse_package_tolerant_returns_failed_result(self, tmp_path):
        path = tmp_path / "bad.uasset"
        path.write_bytes(_package_with_bad_custom_version_count(10_000_001))
        result = parse_package(str(path), tolerant=True)
        assert result.is_success is False
        assert result.errors


class TestLightweightTolerantParseStatus:
    """轻量容错解析必须输出 status='partial' + status_code。"""

    @staticmethod
    def _make_large_export_package() -> bytes:
        """构造一个 export_count > 300 的最小包头。"""
        data = bytearray()
        data += struct.pack("<Iiii", PACKAGE_FILE_TAG, -9, 0, 0)
        data += struct.pack("<i", UE5_PACKAGE_SAVED_HASH)
        data += b"\x00" * 20
        data += struct.pack("<i", 0)  # total_header_size
        data += struct.pack("<I", 3)  # custom version count (正常值)
        data += b"\x00" * 128
        # name_map
        data += struct.pack("<I", 1)  # name_count
        data += struct.pack("<I", 0)  # name_offset (placeholder)
        # import_map
        data += struct.pack("<I", 0)  # import_count
        data += struct.pack("<I", 0)  # import_offset
        # export_map — 301 exports
        data += struct.pack("<I", 301)  # export_count
        data += struct.pack("<I", 0)  # export_offset
        # 用零字节填充足够长度让解析器能读取
        data += b"\x00" * 4096
        return bytes(data)

    def test_lightweight_parse_marks_status_partial(self, tmp_path):
        """轻量容错路径输出 partial 状态。"""
        # 注意：此测试验证 _result_status 对 lightweight_tolerant_parse
        # metadata 的检测。由于构造触发轻量路径的完整包较复杂，
        # 直接测试 ir_builder 的 _result_status 逻辑。
        from uasset_read.ir_builder import _result_status
        from unittest.mock import MagicMock

        result = MagicMock()
        result.is_success = True
        result.errors = []
        result.metadata = {"lightweight_tolerant_parse": True}
        assert _result_status(result) == "partial"

    def test_normal_success_not_marked_partial(self):
        """正常成功解析不应标记为 partial。"""
        from uasset_read.ir_builder import _result_status
        from unittest.mock import MagicMock

        result = MagicMock()
        result.is_success = True
        result.errors = []
        result.metadata = {}
        assert _result_status(result) == "success"

    def test_success_with_errors_marked_partial(self):
        """成功但有错误时标记为 partial。"""
        from uasset_read.ir_builder import _result_status
        from unittest.mock import MagicMock

        result = MagicMock()
        result.is_success = True
        result.errors = ["some warning"]
        result.metadata = {}
        assert _result_status(result) == "partial"
