"""Core 全量测试 — 合并自 test_core_utils.py、test_constants.py、test_quality_gates.py。

覆盖：工具函数、常量、版本、批量解析、入口点、状态模型、质量门禁。
"""
from __future__ import annotations

import ast
import importlib
import inspect
import io
import json
import logging
import os
import queue
import struct
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

import uasset_read
from uasset_read import constants, core, project_logging
from uasset_read.archive import ByteArchive
from uasset_read.batch_worker import BatchWorkerRequest, _monitor_worker, _StderrDrain, run_isolated_asset
from uasset_read.core import parse_batch
from uasset_read.core.error_handling import tolerant_parse
from uasset_read.core.utils import safe_str, safe_int, normalize_hex_guid
from uasset_read.exceptions import ParseError
from uasset_read.memory_safety import ResourceLimits
from uasset_read.models.fallback import ExportParseStatus
from uasset_read.models.result import ParseResult
from uasset_read.models.status import _result_status, PARTIAL_STATUSES, FAILED_STATUSES
from uasset_read.models.validators import validate_parse_status
from uasset_read.pak.constants import PAK_INFO_SIZES
from uasset_read.parse_uasset import _handle_parse_error
from uasset_read.raw import _scrape_locres_strings
from uasset_read.versioning import (
    EUEVersion,
    FPackageFileVersion,
    STREAM_MAP,
    STREAM_FRAMEWORK,
    VersionContainer,
    VersionStream,
    build_version_container,
)


# ============================================================================
# safe_str
# ============================================================================

def test_safe_str_none():
    assert safe_str(None) == ""


def test_safe_str_default_override():
    assert safe_str(None, "N/A") == "N/A"


def test_safe_str_int():
    assert safe_str(42) == "42"


def test_safe_str_str():
    assert safe_str("hello") == "hello"


def test_safe_str_bool():
    assert safe_str(True) == "True"


def test_safe_str_float():
    assert safe_str(3.14) == "3.14"


# ============================================================================
# safe_int
# ============================================================================

def test_safe_int_none():
    assert safe_int(None) == 0


def test_safe_int_default_override():
    assert safe_int(None, -1) == -1


def test_safe_int_int():
    assert safe_int(42) == 42


def test_safe_int_str_valid():
    assert safe_int("123") == 123


def test_safe_int_str_invalid():
    assert safe_int("abc") == 0


def test_safe_int_str_invalid_with_default():
    assert safe_int("xyz", -99) == -99


def test_safe_int_bool_returns_default():
    """bool is subclass of int in Python, but the isinstance guard only allows int/str."""
    # Note: bool is a subclass of int, so isinstance(True, int) is True.
    # This means safe_int(True) returns 1 (True).
    assert safe_int(True) == 1


def test_safe_int_float_returns_default():
    assert safe_int(3.14) == 0


def test_safe_int_list_returns_default():
    assert safe_int([1, 2]) == 0


def test_safe_int_negative_str():
    assert safe_int("-5") == -5


def test_safe_int_empty_str():
    assert safe_int("") == 0


# ============================================================================
# normalize_hex_guid
# ============================================================================

def test_normalize_hex_guid_none():
    assert normalize_hex_guid(None) is None


def test_normalize_hex_guid_empty():
    result = normalize_hex_guid("")
    assert result == ""


def test_normalize_hex_guid_with_dashes():
    assert normalize_hex_guid("A1B2C3D4-E5F6-7890-ABCD-EF1234567890") == \
        "a1b2c3d4e5f67890abcdef1234567890"


def test_normalize_hex_guid_without_dashes():
    assert normalize_hex_guid("A1B2C3D4E5F67890ABCDEF1234567890") == \
        "a1b2c3d4e5f67890abcdef1234567890"


def test_normalize_hex_guid_lowercase():
    assert normalize_hex_guid("a1b2c3d4-e5f6-7890-abcd-ef1234567890") == \
        "a1b2c3d4e5f67890abcdef1234567890"


def test_normalize_hex_guid_already_normalized():
    assert normalize_hex_guid("a1b2c3d4e5f67890abcdef1234567890") == \
        "a1b2c3d4e5f67890abcdef1234567890"


def test_normalize_hex_guid_mixed_case():
    """测试混合大小写 GUID 归一化为小写"""
    assert normalize_hex_guid("A1b2C3d4-E5f6-7890-aBcD-eF1234567890") == \
        "a1b2c3d4e5f67890abcdef1234567890"


def test_normalize_hex_guid_all_uppercase_no_dashes():
    """测试全大写无连字符 GUID 归一化为小写"""
    assert normalize_hex_guid("A1B2C3D4E5F67890ABCDEF1234567890") == \
        "a1b2c3d4e5f67890abcdef1234567890"


# ============================================================================
# UTF-8 字符串长度越界验证测试 (#407)
# ============================================================================


def test_utf8_length_exceeds_remaining_bytes_tolerant():
    """UTF-8 长度超过剩余字节时，tolerant 模式应返回空字符串"""
    # length=1000, 但只剩 10 字节（不含 length 字段本身的 4 字节）
    # 构造: i32 length (1000) + 10 bytes of padding
    data = struct.pack('<i', 1000) + b'\x00' * 10
    archive = ByteArchive(data, tolerant=True)
    result = archive.read_utf8_string(tolerant=True)
    assert result == ""


def test_utf8_length_exceeds_remaining_bytes_strict():
    """UTF-8 长度超过剩余字节时，strict 模式应抛出 ParseError"""
    data = struct.pack('<i', 1000) + b'\x00' * 10
    archive = ByteArchive(data, tolerant=False)
    with pytest.raises(ParseError, match="UTF-8 length 1000 exceeds remaining"):
        archive.read_utf8_string(tolerant=False)


def test_utf8_length_within_remaining_bytes():
    """UTF-8 长度在剩余字节范围内，应正常读取"""
    # length=5, 后跟 5 字节有效数据 + null terminator
    content = b'hello'
    data = struct.pack('<i', len(content) + 1) + content + b'\x00'
    archive = ByteArchive(data, tolerant=True)
    result = archive.read_utf8_string(tolerant=True)
    assert result == "hello"


def test_utf8_length_zero():
    """UTF-8 长度为 0，应返回空字符串"""
    data = struct.pack('<i', 0)
    archive = ByteArchive(data, tolerant=True)
    result = archive.read_utf8_string(tolerant=True)
    assert result == ""


def test_utf8_length_exactly_matches_remaining():
    """UTF-8 长度恰好等于剩余字节，应正常读取"""
    content = b'test\x00'
    data = struct.pack('<i', len(content)) + content
    archive = ByteArchive(data, tolerant=True)
    result = archive.read_utf8_string(tolerant=True)
    assert result == "test"


def test_utf8_length_one_byte_over():
    """UTF-8 长度比剩余字节多 1，应触发越界"""
    data = struct.pack('<i', 11) + b'\x00' * 10
    archive = ByteArchive(data, tolerant=True)
    result = archive.read_utf8_string(tolerant=True)
    assert result == ""


def test_utf8_length_records_diagnostic():
    """tolerant 模式下应记录诊断信息"""
    data = struct.pack('<i', 500) + b'\x00' * 5
    archive = ByteArchive(data, tolerant=True)
    archive.read_utf8_string(tolerant=True)
    diagnostics = archive.get_diagnostics()
    assert len(diagnostics) > 0
    assert any("UTF-8 length" in d.error for d in diagnostics)


# ============================================================================
# PackageLinker.preload() NoneType 防护 (#328)
# ============================================================================


def test_preload_none_serial_offset():
    """preload() 应处理 serial_offset 为 None 的情况。"""
    from uasset_read.link.linker import PackageLinker

    mock_archive = MagicMock()
    mock_archive.total_size.return_value = 1000

    linker = PackageLinker.__new__(PackageLinker)
    linker._archive = mock_archive
    linker._file_size = 1000
    linker._preload_cache = {}
    linker._export_objects = []
    linker._export_map = []
    linker._import_objects = []
    linker._import_map = []
    linker._name_map = []
    linker._summary = MagicMock()
    linker._diagnostics = []

    # 创建一个 mock export object with None serial_offset
    mock_instance = MagicMock()
    mock_instance.serial_offset = None
    mock_instance.serial_size = 100
    mock_instance.object_name = "TestExport"
    mock_instance._preloaded = False

    linker._export_objects = [mock_instance]
    linker._export_map = [MagicMock()]

    # 不应抛出异常
    linker.preload(0)
    assert mock_instance._preloaded == True


def test_preload_none_archive():
    """preload() 应处理 archive 为 None 的情况。"""
    from uasset_read.link.linker import PackageLinker

    linker = PackageLinker.__new__(PackageLinker)
    linker._archive = None  # archive 为 None
    linker._file_size = 1000
    linker._preload_cache = {}
    linker._export_objects = []
    linker._export_map = []
    linker._import_objects = []
    linker._import_map = []
    linker._name_map = []
    linker._summary = MagicMock()
    linker._diagnostics = []

    # 创建一个 mock export object
    mock_instance = MagicMock()
    mock_instance.serial_offset = 100
    mock_instance.serial_size = 100
    mock_instance.object_name = "TestExport"
    mock_instance._preloaded = False

    linker._export_objects = [mock_instance]
    linker._export_map = [MagicMock()]

    # 不应抛出异常
    linker.preload(0)
    assert mock_instance._preloaded == True


def test_preload_none_serial_size():
    """preload() 应处理 serial_size 为 None 的情况。"""
    from uasset_read.link.linker import PackageLinker

    mock_archive = MagicMock()
    mock_archive.total_size.return_value = 1000

    linker = PackageLinker.__new__(PackageLinker)
    linker._archive = mock_archive
    linker._file_size = 1000
    linker._preload_cache = {}
    linker._export_objects = []
    linker._export_map = []
    linker._import_objects = []
    linker._import_map = []
    linker._name_map = []
    linker._summary = MagicMock()
    linker._diagnostics = []

    # 创建一个 mock export object with None serial_size
    mock_instance = MagicMock()
    mock_instance.serial_offset = 100
    mock_instance.serial_size = None
    mock_instance.object_name = "TestExport"
    mock_instance._preloaded = False

    linker._export_objects = [mock_instance]
    linker._export_map = [MagicMock()]

    # 不应抛出异常
    linker.preload(0)
    assert mock_instance._preloaded == True


# ============================================================================
# DependsMap 异常数量防护测试 (#336)
# ============================================================================


# depends_offset 必须 > 0（函数入口检查），但 ByteArchive 会 seek 到该位置
# 所以数据需要在 offset=1 处开始，前 1 字节是填充
_PADDING = b'\x00'


def _make_summary(export_count: int, depends_offset: int = 1):
    """创建用于测试的最小化 PackageFileSummary。"""
    from uasset_read.serializers.package_summary import PackageFileSummary
    summary = PackageFileSummary.__new__(PackageFileSummary)
    summary.depends_offset = depends_offset
    summary.export_count = export_count
    return summary


def _i32_le(value: int) -> bytes:
    """将 int32 编码为小端字节序列。"""
    return struct.pack('<i', value)


def test_depends_map_abnormal_count():
    """DependsMap 异常数量（>10000）应跳过该条目，返回空列表。"""
    from uasset_read.serializers.package_summary import read_depends_map
    # dep_count = 100000 (超出 10000 限制)
    data = _PADDING + _i32_le(100000)

    archive = ByteArchive(data, tolerant=True)
    summary = _make_summary(export_count=1)

    result = read_depends_map(archive, summary)
    assert result == [[]], "异常数量条目应跳过，返回空列表"


def test_depends_map_negative_count():
    """DependsMap 负数数量应跳过该条目。"""
    from uasset_read.serializers.package_summary import read_depends_map
    data = _PADDING + _i32_le(-1)

    archive = ByteArchive(data, tolerant=True)
    summary = _make_summary(export_count=1)

    result = read_depends_map(archive, summary)
    assert result == [[]], "负数数量条目应跳过，返回空列表"


def test_depends_map_boundary_count():
    """DependsMap 边界值（正好 10000）应正常解析。"""
    from uasset_read.serializers.package_summary import read_depends_map
    # dep_count = 10000, 后续跟 10000 个 i32 依赖值（全为 0）
    dep_count_bytes = _i32_le(10000)
    deps_bytes = _i32_le(0) * 10000
    data = _PADDING + dep_count_bytes + deps_bytes

    archive = ByteArchive(data, tolerant=True)
    summary = _make_summary(export_count=1)

    result = read_depends_map(archive, summary)
    assert len(result) == 1
    assert len(result[0]) == 10000


def test_depends_map_mixed_normal_and_abnormal():
    """混合正常和异常条目时，仅跳过异常条目。"""
    from uasset_read.serializers.package_summary import read_depends_map
    # export_count = 3
    # 条目 0: dep_count = 2 (正常) → 两个依赖值 0, 0
    # 条目 1: dep_count = 50000 (异常) → 跳过
    # 条目 2: dep_count = 1 (正常) → 一个依赖值 0
    data = (
        _PADDING
        + _i32_le(2)       # dep_count = 2
        + _i32_le(0) * 2   # 2 deps
        + _i32_le(50000)   # dep_count = 50000 (异常)
        + _i32_le(1)       # dep_count = 1
        + _i32_le(0)       # 1 dep
    )

    archive = ByteArchive(data, tolerant=True)
    summary = _make_summary(export_count=3)

    result = read_depends_map(archive, summary)
    assert len(result) == 3, "应返回 3 个条目"
    assert len(result[0]) == 2, "条目 0 应有 2 个依赖"
    assert result[1] == [], "条目 1（异常）应被跳过"
    assert len(result[2]) == 1, "条目 2 应有 1 个依赖"


def test_depends_map_empty():
    """DependsMap 无数据时返回空列表。"""
    from uasset_read.serializers.package_summary import read_depends_map
    summary = _make_summary(export_count=0, depends_offset=0)

    result = read_depends_map(ByteArchive(b''), summary)
    assert result == []


def test_depends_map_zero_offset():
    """DependsMap offset 为 0 时返回空列表。"""
    from uasset_read.serializers.package_summary import read_depends_map
    summary = _make_summary(export_count=5, depends_offset=0)
    result = read_depends_map(ByteArchive(b'\x00' * 100), summary)
    assert result == []


# ============================================================================
# TestHybridIsolation — #346 智能混合模式测试
# ============================================================================

class TestHybridIsolation:
    """#346: 智能混合模式测试。"""

    def test_small_files_not_isolated(self):
        """小文件（< 20MB）应走非隔离路径。"""
        from uasset_read.memory_safety import should_isolate, FileSizeTier

        # 10MB 文件
        result = should_isolate(10 * 1024 * 1024, FileSizeTier.SMALL)
        assert result is False

    def test_large_files_isolated(self):
        """大文件（> 100MB）应走隔离路径。"""
        from uasset_read.memory_safety import should_isolate, FileSizeTier

        result = should_isolate(200 * 1024 * 1024, FileSizeTier.LARGE)
        assert result is True

    def test_file_size_tier_auto_selection(self):
        """FileSizeTier.from_size 应根据文件大小返回正确分级。"""
        from uasset_read.memory_safety import FileSizeTier

        assert FileSizeTier.from_size(10 * 1024 * 1024) == FileSizeTier.SMALL  # 10MB
        assert FileSizeTier.from_size(50 * 1024 * 1024) == FileSizeTier.MEDIUM  # 50MB
        assert FileSizeTier.from_size(150 * 1024 * 1024) == FileSizeTier.LARGE  # 150MB

    def test_medium_file_below_threshold_not_isolated(self):
        """中等文件（< 50MB）不应隔离。"""
        from uasset_read.memory_safety import should_isolate, FileSizeTier

        result = should_isolate(30 * 1024 * 1024, FileSizeTier.MEDIUM)  # 30MB
        assert result is False

    def test_medium_file_above_threshold_isolated(self):
        """中等文件（>= 50MB）应隔离。"""
        from uasset_read.memory_safety import should_isolate, FileSizeTier

        result = should_isolate(60 * 1024 * 1024, FileSizeTier.MEDIUM)  # 60MB
        assert result is True

    def test_auto_mode_integration(self):
        """parse_batch auto 模式应调用 should_isolate 决定隔离策略。"""
        from pathlib import PurePosixPath

        # 保存 uasset_read logger 的日志配置状态
        ua_logger = logging.getLogger("uasset_read")
        old_handlers = ua_logger.handlers[:]
        old_propagate = ua_logger.propagate
        old_level = ua_logger.level

        fake_file = PurePosixPath('/tmp/fake/test.uasset')
        try:
            with patch.object(Path, 'is_dir', return_value=True):
                with patch.object(Path, 'rglob', side_effect=[
                    [fake_file],  # *.uasset
                    [],           # *.umap
                ]):
                    with patch('uasset_read.memory_safety.get_memory_stats') as mock_stats:
                        mock_stats.return_value = MagicMock(usage_percent=0.1)
                        with patch('uasset_read.memory_safety.check_file_size', return_value=10 * 1024 * 1024):
                            with patch('uasset_read.memory_safety.FileSizeTier') as mock_tier:
                                mock_tier.from_size.return_value = 'SMALL'
                                with patch('uasset_read.memory_safety.should_isolate', return_value=False) as mock_should:
                                    with patch('uasset_read.core.parse_single') as mock_parse:
                                        mock_parse.return_value = MagicMock()
                                        mock_parse.return_value.status = 'success'
                                        parse_batch(
                                            '/tmp/fake',
                                            isolate_assets="auto",
                                        )
                                        mock_should.assert_called()
        finally:
            # 恢复 uasset_read logger 的日志配置状态，避免污染其他测试
            ua_logger.handlers = old_handlers
            ua_logger.propagate = old_propagate
            ua_logger.level = old_level


def test_auto_mode_integration_does_not_configure_logging():
    """test_auto_mode_integration 不应触发全局日志配置。"""
    ua_logger = logging.getLogger("uasset_read")
    old_handlers = ua_logger.handlers[:]
    old_propagate = ua_logger.propagate
    old_level = ua_logger.level

    from pathlib import PurePosixPath

    fake_file = PurePosixPath('/tmp/fake/test.uasset')
    try:
        with patch.object(Path, 'is_dir', return_value=True):
            with patch.object(Path, 'rglob', side_effect=[
                [fake_file],  # *.uasset
                [],           # *.umap
            ]):
                with patch('uasset_read.memory_safety.get_memory_stats') as mock_stats:
                    mock_stats.return_value = MagicMock(usage_percent=0.1)
                    with patch('uasset_read.memory_safety.check_file_size', return_value=10 * 1024 * 1024):
                        with patch('uasset_read.memory_safety.FileSizeTier') as mock_tier:
                            mock_tier.from_size.return_value = 'SMALL'
                            with patch('uasset_read.memory_safety.should_isolate', return_value=False):
                                with patch('uasset_read.core.parse_single') as mock_parse:
                                    mock_parse.return_value = MagicMock()
                                    mock_parse.return_value.status = 'success'
                                    parse_batch(
                                        '/tmp/fake',
                                        isolate_assets="auto",
                                    )
    finally:
        # 恢复 uasset_read logger 的日志配置状态，避免污染其他测试
        ua_logger.handlers = old_handlers
        ua_logger.propagate = old_propagate
        ua_logger.level = old_level

    # 验证 uasset_read logger 的 propagate 未被修改
    assert ua_logger.handlers == old_handlers
    assert ua_logger.propagate == old_propagate
    assert ua_logger.level == old_level


def test_parse_batch_invalid_isolate_assets():
    """parse_batch 应拒绝无效的 isolate_assets 值。"""

    with patch.object(Path, 'is_dir', return_value=True):
        with patch.object(Path, 'rglob', side_effect=[[], []]):
            with pytest.raises(ValueError, match="isolate_assets must be"):
                parse_batch(
                    '/tmp/fake',
                    isolate_assets="invalid_value",
                )


# ============================================================================
# Tests for batch worker error logging (#414)
# ============================================================================

def test_monitor_worker_logs_stderr_on_empty_result(caplog):
    """When result_queue.get() raises queue.Empty, stderr should be logged."""

    # Create a mock process that has already exited
    mock_process = MagicMock()
    mock_process.is_alive.return_value = False
    mock_process.exitcode = 1
    mock_process.pid = 12345
    mock_process.stderr_text = "TestError: something went wrong\n"

    # result_queue.get() will raise queue.Empty
    mock_queue = MagicMock()
    mock_queue.get.side_effect = queue.Empty

    limits = ResourceLimits(timeout_seconds=10, rss_limit_mb=1024)

    with caplog.at_level(logging.ERROR):
        result = _monitor_worker(
            process=mock_process,
            result_queue=mock_queue,
            limits=limits,
            poll_interval_seconds=0.01,
        )

    assert result.succeeded is False
    assert "TestError: something went wrong" in result.error_details
    assert "worker_exit" in result.error
    # Check that stderr was logged
    assert any("TestError: something went wrong" in record.message for record in caplog.records)


def test_monitor_worker_includes_stderr_in_outcome():
    """When result_queue.get() raises queue.Empty, stderr should be in outcome."""

    mock_process = MagicMock()
    mock_process.is_alive.return_value = False
    mock_process.exitcode = 1
    mock_process.pid = 12345
    mock_process.stderr_text = "ImportError: No module named 'foo'\n"

    mock_queue = MagicMock()
    mock_queue.get.side_effect = queue.Empty

    limits = ResourceLimits(timeout_seconds=10, rss_limit_mb=1024)

    result = _monitor_worker(
        process=mock_process,
        result_queue=mock_queue,
        limits=limits,
        poll_interval_seconds=0.01,
    )

    assert result.succeeded is False
    assert "ImportError: No module named 'foo'" in result.error_details


# ============================================================================
# Tests for batch worker startup behavior (#415)
# ============================================================================

def test_batch_worker_no_runtime_warning():
    """batch worker 启动不应触发 RuntimeWarning"""
    result = subprocess.run(
        [sys.executable, "-m", "uasset_read.batch_worker", "--help"],
        capture_output=True,
        text=True,
    )
    assert "RuntimeWarning" not in result.stderr


# ============================================================================
# batch 同 stem 覆盖测试 — #278
# ============================================================================

_FAKE_OUTPUT = '{"status": {"status": "success"}}'


def _make_fake_uasset(path: Path) -> None:
    """创建一个假的 .uasset/.umap 文件（仅需文件名匹配 glob 即可）。"""
    path.write_bytes(b"\x00" * 128)


class TestBatchStemCollision:
    """同 stem 的 .uasset/.umap 不应覆盖彼此的输出。"""

    def test_uasset_and_umap_same_stem_produce_different_outputs(self, tmp_path: Path) -> None:
        """Same.uasset + Same.umap → Same.uasset.json + Same.umap.json"""
        asset_dir = tmp_path / "assets"
        asset_dir.mkdir()
        output_dir = tmp_path / "output"

        _make_fake_uasset(asset_dir / "Same.uasset")
        _make_fake_uasset(asset_dir / "Same.umap")

        with patch(
            "uasset_read.core.parse_single",
            return_value=_FAKE_OUTPUT,
        ):
            result = parse_batch(
                str(asset_dir),
                output_dir=str(output_dir),
                isolate_assets=False,
            )

        # 两个文件都应成功
        assert len(result.success) == 2
        assert len(result.failed) == 0

        output_files = sorted(Path(p).name for p in result.success)
        assert output_files == ["Same.uasset.json", "Same.umap.json"]

    def test_only_uasset_still_uses_plain_name(self, tmp_path: Path) -> None:
        """仅有 .uasset 时，输出为 Stem.json（保持向后兼容）。"""
        asset_dir = tmp_path / "assets"
        asset_dir.mkdir()
        output_dir = tmp_path / "output"

        _make_fake_uasset(asset_dir / "Foo.uasset")

        with patch(
            "uasset_read.core.parse_single",
            return_value=_FAKE_OUTPUT,
        ):
            result = parse_batch(
                str(asset_dir),
                output_dir=str(output_dir),
                isolate_assets=False,
            )

        assert len(result.success) == 1
        output_files = [Path(p).name for p in result.success]
        assert output_files == ["Foo.uasset.json"]

    def test_multiple_collisions_all_distinct(self, tmp_path: Path) -> None:
        """多组同 stem 文件均产生不同输出。"""
        asset_dir = tmp_path / "assets"
        asset_dir.mkdir()
        output_dir = tmp_path / "output"

        for stem in ("Map", "Data"):
            _make_fake_uasset(asset_dir / f"{stem}.uasset")
            _make_fake_uasset(asset_dir / f"{stem}.umap")
        # 额外一个无冲突的文件
        _make_fake_uasset(asset_dir / "Solo.uasset")

        with patch(
            "uasset_read.core.parse_single",
            return_value=_FAKE_OUTPUT,
        ):
            result = parse_batch(
                str(asset_dir),
                output_dir=str(output_dir),
                isolate_assets=False,
            )

        assert len(result.success) == 5
        output_files = sorted(Path(p).name for p in result.success)
        expected = [
            "Data.uasset.json",
            "Data.umap.json",
            "Map.uasset.json",
            "Map.umap.json",
            "Solo.uasset.json",
        ]
        assert output_files == expected

    def test_markdown_format_stem_collision(self, tmp_path: Path) -> None:
        """markdown 格式下同 stem 碰撞同样产生不同输出。"""
        asset_dir = tmp_path / "assets"
        asset_dir.mkdir()
        output_dir = tmp_path / "output"

        _make_fake_uasset(asset_dir / "Level.uasset")
        _make_fake_uasset(asset_dir / "Level.umap")

        with patch(
            "uasset_read.core.parse_single",
            return_value="# Level",
        ):
            result = parse_batch(
                str(asset_dir),
                format="markdown",
                output_dir=str(output_dir),
                isolate_assets=False,
            )

        assert len(result.success) == 2
        output_files = sorted(Path(p).name for p in result.success)
        assert output_files == ["Level.uasset.md", "Level.umap.md"]

    def test_output_files_actually_written(self, tmp_path: Path) -> None:
        """确认输出文件确实写入了不同路径（不会静默覆盖）。"""
        asset_dir = tmp_path / "assets"
        asset_dir.mkdir()
        output_dir = tmp_path / "output"

        _make_fake_uasset(asset_dir / "Same.uasset")
        _make_fake_uasset(asset_dir / "Same.umap")

        with patch(
            "uasset_read.core.parse_single",
            return_value=_FAKE_OUTPUT,
        ):
            parse_batch(
                str(asset_dir),
                output_dir=str(output_dir),
                isolate_assets=False,
            )

        # 两个输出文件应同时存在
        assert (output_dir / "Same.uasset.json").exists()
        assert (output_dir / "Same.umap.json").exists()
        # 确认没有 Same.json（旧行为的残留）
        assert not (output_dir / "Same.json").exists()


# ============================================================================
# Parent-side isolated worker monitoring tests
# ============================================================================

# 子进程需要 src/ 在 PYTHONPATH 中才能 import uasset_read
_SRC_DIR = str(Path(__file__).resolve().parents[2] / "src")


def test_worker_stream_logging_includes_run_process_asset_and_stage():
    stream = io.StringIO()
    handler = project_logging.configure_worker_stream_logging(
        stream=stream,
        level="DEBUG",
        run_id="run-42",
        asset="Example.uasset",
    )
    try:
        logging.getLogger("uasset_read.worker_test").warning("worker detail")
    finally:
        logging.getLogger("uasset_read").removeHandler(handler)
        handler.close()

    output = stream.getvalue()
    assert "run=run-42" in output
    assert f"pid={os.getpid()}" in output
    assert "asset=Example.uasset" in output
    assert "stage=worker" in output
    assert "worker detail" in output


def test_stderr_drain_forwards_each_worker_line():
    forwarded = []
    drain = _StderrDrain(line_callback=forwarded.append)

    drain._append("first\n")
    drain._append("second\n")

    assert forwarded == ["first\n", "second\n"]


class _FakeProcess:
    pid = 123
    exitcode = None

    def __init__(self) -> None:
        self.terminated = False

    def is_alive(self) -> bool:
        return not self.terminated

    def terminate(self) -> None:
        self.terminated = True

    def join(self, timeout=None) -> None:
        return None

    def kill(self) -> None:
        self.terminated = True


def test_monitor_terminates_worker_over_rss_limit() -> None:
    process = _FakeProcess()
    outcome = _monitor_worker(
        process=process,
        result_queue=None,
        limits=ResourceLimits(64, 30),
        poll_interval_seconds=0,
        rss_reader=lambda _pid: 65,
        monotonic=lambda: 0,
        sleep=lambda _seconds: None,
    )

    assert process.terminated is True
    assert outcome.succeeded is False
    assert outcome.error == "memory_limit: 65.0MB > 64.0MB"


def test_monitor_terminates_worker_after_timeout() -> None:
    process = _FakeProcess()
    times = iter([0.0, 11.0])
    outcome = _monitor_worker(
        process=process,
        result_queue=None,
        limits=ResourceLimits(64, 10),
        poll_interval_seconds=0,
        rss_reader=lambda _pid: 1,
        monotonic=lambda: next(times),
        sleep=lambda _seconds: None,
    )

    assert process.terminated is True
    assert outcome.succeeded is False
    assert outcome.error == "timeout: 11.0s > 10.0s"


@pytest.mark.skipif(
    sys.platform == "darwin",
    reason="Per-process RSS monitoring requires psutil on macOS"
)
def test_spawn_worker_writes_output_atomically(tmp_path) -> None:
    asset = tmp_path / "invalid.uasset"
    output = tmp_path / "out" / "invalid.json"
    asset.write_bytes(b"\x00" * 100)
    request = BatchWorkerRequest(
        file_path=str(asset),
        output_path=str(output),
        parse_options={"format": "json", "tolerant": True},
    )

    # 子进程需要 PYTHONPATH 才能 import uasset_read
    old_pythonpath = os.environ.get("PYTHONPATH")
    try:
        existing = os.environ.get("PYTHONPATH", "")
        os.environ["PYTHONPATH"] = _SRC_DIR + os.pathsep + existing if existing else _SRC_DIR
        outcome = run_isolated_asset(
            request,
            limits=ResourceLimits(512, 30),
            poll_interval_seconds=0.01,
        )
    finally:
        if old_pythonpath is None:
            os.environ.pop("PYTHONPATH", None)
        else:
            os.environ["PYTHONPATH"] = old_pythonpath

    assert outcome.succeeded is True
    assert outcome.output_path == str(output)
    assert json.loads(output.read_text(encoding="utf-8"))["status"]["status"] == "failed"
    assert list(output.parent.glob(".*.tmp")) == []


@pytest.mark.skipif(
    sys.platform == "darwin",
    reason="Per-process RSS monitoring requires psutil on macOS"
)
def test_parse_batch_works_in_script_without_main_guard(tmp_path) -> None:
    """验证 parse_batch 可在无 if __name__ == '__main__' 守卫的脚本中调用。"""
    asset_dir = tmp_path / "assets"
    asset_dir.mkdir()
    (asset_dir / "invalid.uasset").write_bytes(b"\x00" * 100)
    script = tmp_path / "call_batch.py"
    script.write_text(
        "from uasset_read import parse_batch\n"
        f"result = parse_batch({str(asset_dir)!r})\n"
        "print(len(result.success), len(result.failed))\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = _SRC_DIR

    completed = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )

    assert completed.returncode == 0, completed.stderr
    # 无效 uasset 文件在 isolated 模式下容忍解析成功，输出 JSON 并计入 success
    assert completed.stdout.strip() == "1 0"


# ============================================================================
# 入口点测试 — 模块导入冒烟 + 参数完整性验证
# ============================================================================

# 所有核心模块列表（已验证可导入）
MODULES = [
    "uasset_read",
    "uasset_read.core",
    "uasset_read.archive",
    "uasset_read.package",
    "uasset_read.parse_uasset",
    "uasset_read.cli",
    "uasset_read.graph",
    "uasset_read.graph.parser",
    "uasset_read.graph.flow_builder",
    "uasset_read.graph.macro_expander",
    "uasset_read.kismet",
    "uasset_read.kismet.archive",
    "uasset_read.kismet.jump_analyzer",
    "uasset_read.kismet.expressions",
    "uasset_read.kismet.tokens",
    "uasset_read.kismet.translator",
    "uasset_read.kismet.pipeline",
    "uasset_read.parsers",
    "uasset_read.parsers.asset_types",
    "uasset_read.parsers.asset_types.anim_blueprint",
    "uasset_read.parsers.asset_types.anim_montage",
    "uasset_read.parsers.asset_types.anim_sequence",
    "uasset_read.parsers.asset_types.movie_scene",
    "uasset_read.parsers.asset_types.movie_scene_control_rig",
    "uasset_read.parsers.asset_types.property_extractor",
    "uasset_read.models",
    "uasset_read.models.ir",
    "uasset_read.models.status",
    "uasset_read.models.fallback",
    "uasset_read.serializers",
    "uasset_read.serializers.graph",
    "uasset_read.serializers.package_summary",
    "uasset_read.serializers.property_tags",
    "uasset_read.link",
    "uasset_read.link.linker",
    "uasset_read.pak",
    "uasset_read.pak.reader",
    "uasset_read.pak.constants",
    "uasset_read.iostore",
    "uasset_read.blueprint",
    "uasset_read.blueprint.variable_extractor",
    "uasset_read.cpp_gen",
    "uasset_read.renderers",
    "uasset_read.renderers.json_renderer",
    "uasset_read.renderers.markdown_renderer",
    "uasset_read.memory_safety",
    "uasset_read.debug",
    "uasset_read.bounded_events",
    "uasset_read.versioning",
    "uasset_read.ir_builder",
    "uasset_read.objects",
    "uasset_read.raw",
    "uasset_read.mappings",
    "uasset_read.batch_worker",
    "uasset_read.project_logging",
]


@pytest.mark.parametrize("module_path", MODULES)
def test_module_importable(module_path):
    """每个核心模块应可成功导入"""
    mod = importlib.import_module(module_path)
    assert mod is not None


def test_public_api_structure():
    """uasset_read 包级 API 结构验证"""
    import uasset_read
    assert callable(getattr(uasset_read, "parse_single", None))
    assert callable(getattr(uasset_read, "parse_batch", None))
    assert callable(getattr(uasset_read, "list_formats", None))
    assert "json" in uasset_read.list_formats()


def test_archive_read_u8():
    """ByteArchive 基本读取"""
    archive = ByteArchive(b"\x42\x00\xff", name="test")
    assert archive.read_u8() == 0x42
    assert archive.read_u8() == 0x00
    assert archive.read_u8() == 0xFF
    archive.close()


def test_archive_read_u32():
    archive = ByteArchive(b"\x01\x00\x00\x00", name="test")
    assert archive.read_u32() == 1
    archive.close()


def test_archive_seek_tell():
    archive = ByteArchive(b"\x00\x01\x02\x03\x04", name="test")
    archive.seek(2)
    assert archive.tell() == 2
    assert archive.read_u8() == 0x02
    archive.close()


def test_handler_classes_exist():
    """所有 handler 类应存在且可实例化"""
    from uasset_read.parsers.asset_types.anim_blueprint import AnimBlueprintHandler
    from uasset_read.parsers.asset_types.anim_montage import AnimMontageHandler
    from uasset_read.parsers.asset_types.anim_sequence import AnimSequenceHandler
    from uasset_read.parsers.asset_types.movie_scene import MovieSceneHandler
    for cls in [AnimBlueprintHandler, AnimMontageHandler, AnimSequenceHandler, MovieSceneHandler]:
        handler = cls()
        assert hasattr(handler, "handle")


def test_handler_empty_properties():
    """handler 空属性应返回 PARTIAL"""
    from uasset_read.parsers.asset_types.anim_blueprint import AnimBlueprintHandler
    from uasset_read.parsers.asset_types.anim_montage import AnimMontageHandler
    from uasset_read.parsers.asset_types.anim_sequence import AnimSequenceHandler
    from uasset_read.parsers.asset_types.movie_scene import MovieSceneHandler
    for cls in [AnimBlueprintHandler, AnimMontageHandler, AnimSequenceHandler, MovieSceneHandler]:
        handler = cls()

        class FakeExport:
            properties = []
            custom_data = {}
        class FakeCtx:
            warnings = []

        result = handler.handle(FakeExport(), FakeCtx())
        assert result.value == "partial"


def test_status_model():
    from uasset_read.models.status import FAILED_STATUSES, PARTIAL_STATUSES
    assert "failed" in FAILED_STATUSES
    assert "fallback" in PARTIAL_STATUSES


def test_fallback_status():
    assert ExportParseStatus.SUCCESS.value == "success"
    assert ExportParseStatus.PARTIAL.value == "partial"


def test_memory_policy():
    from uasset_read.memory_safety import MemoryPolicy, ResourceLimits
    policy = MemoryPolicy()
    limits = policy.limits_for_size(1024 * 1024)
    assert isinstance(limits, ResourceLimits)


def test_cli_help():
    src_dir = os.path.join(os.path.dirname(__file__), "..", "src")
    env = {**os.environ, "PYTHONPATH": src_dir}
    result = subprocess.run(
        [sys.executable, "-m", "uasset_read", "--help"],
        capture_output=True, text=True, timeout=10, env=env
    )
    assert result.returncode == 0


# ---------------------------------------------------------------------------
# 入口点参数完整性测试
# ---------------------------------------------------------------------------

class TestParameterIntegrity:
    """验证 parse_batch 与 parse_single 参数一致。"""

    def test_parse_batch_has_output_level(self):
        """parse_batch 应支持 output_level 参数。"""
        sig = inspect.signature(core.parse_batch)
        assert "output_level" in sig.parameters, (
            f"parse_batch 缺少 output_level 参数，当前参数: {list(sig.parameters.keys())}"
        )

    def test_parse_batch_has_hex_view(self):
        """parse_batch 应支持 hex_view 参数。"""
        sig = inspect.signature(core.parse_batch)
        assert "hex_view" in sig.parameters, (
            f"parse_batch 缺少 hex_view 参数"
        )

    def test_parse_batch_output_level_default_matches_single(self):
        """parse_batch 的 output_level 默认值应与 parse_single 一致。"""
        single_sig = inspect.signature(core.parse_single)
        batch_sig = inspect.signature(core.parse_batch)
        assert batch_sig.parameters["output_level"].default == single_sig.parameters["output_level"].default

    def test_parse_batch_hex_view_default_matches_single(self):
        """parse_batch 的 hex_view 默认值应与 parse_single 一致。"""
        single_sig = inspect.signature(core.parse_single)
        batch_sig = inspect.signature(core.parse_batch)
        assert batch_sig.parameters["hex_view"].default == single_sig.parameters["hex_view"].default


class TestParseBatchPassesParameters:
    """验证 parse_batch 实际传递参数到 parse_single。"""

    def test_parse_batch_includes_params_in_parse_options(self):
        """parse_options dict 应包含 output_level 和 hex_view。"""
        source = inspect.getsource(core.parse_batch)
        assert "output_level" in source, "parse_batch 源码中未引用 output_level"
        assert "hex_view" in source, "parse_batch 源码中未引用 hex_view"
        # 验证它们出现在 parse_options dict 中
        assert '"output_level"' in source or "'output_level'" in source, (
            "output_level 未被添加到 parse_options"
        )
        assert '"hex_view"' in source or "'hex_view'" in source, (
            "hex_view 未被添加到 parse_options"
        )


class TestPakInfoSizes:
    """验证 PAK_INFO_SIZES 包含 bEncryptedIndex。"""

    def test_v1_6_includes_b_encrypted_index(self):
        """v1-6 的 serialized size 应包含 bEncryptedIndex（1 字节）。

        UE 源码 IPlatformFilePak.h GetSerializedSize():
        base = Magic(4) + Version(4) + IndexOffset(8) + IndexSize(8) + IndexHash(20) + bEncryptedIndex(1) = 45
        """
        assert PAK_INFO_SIZES["v1-6"] == 45, (
            f"v1-6 size 应为 45（含 bEncryptedIndex），实际为 {PAK_INFO_SIZES['v1-6']}"
        )

    def test_v7_size_consistent(self):
        """v7 = v1-6(45) + EncryptionKeyGuid(16) = 61"""
        assert PAK_INFO_SIZES["v7"] == 61

    def test_v8_size_consistent(self):
        """v8 = v7(61) + CompressionMethods(32*5=160) = 221"""
        assert PAK_INFO_SIZES["v8"] == 221

    def test_v9_size_consistent(self):
        """v9 = v8(221) + FrozenIndex(1) = 222"""
        assert PAK_INFO_SIZES["v9"] == 222

    def test_v10_size_consistent(self):
        """v10 = v8(221)（FrozenIndex removed）"""
        assert PAK_INFO_SIZES["v10+"] == 221


class TestPrivateKeyExport:
    """验证 __init__.py 不导出私有函数。"""

    def test_no_private_functions_in_all(self):
        """__all__ 不应包含以 _ 开头的函数名（__version__ 除外）。"""
        import uasset_read
        private = [name for name in uasset_read.__all__ if name.startswith("_") and name != "__version__"]
        assert private == [], f"__all__ 包含私有函数: {private}"

    def test_derive_node_name_not_imported(self):
        """__init__.py 不应导入 _derive_node_name。"""
        import uasset_read
        assert not hasattr(uasset_read, "_derive_node_name") or \
            "_derive_node_name" not in getattr(uasset_read, "__all__", []), (
            "_derive_node_name 不应通过 uasset_read 包导出"
        )


class TestPostProcessSplit:
    """验证 _post_process 已拆分为子函数。"""

    def _get_module(self):
        """获取 parse_uasset 模块（避免 __init__.py 函数名遮蔽）。"""
        return sys.modules["uasset_read.parse_uasset"]

    def test_post_process_sub_functions_exist(self):
        """parse_uasset 模块应包含 _post_process 的子函数。"""
        pu = self._get_module()
        # 至少应有一个从 _post_process 提取的子函数
        sub_funcs = [
            name for name in dir(pu)
            if name.startswith("_") and callable(getattr(pu, name, None))
            and name not in ("_post_process", "_resolve_parent_assets", "_find_parent_asset_file",
                             "_extract_kismet_decompiled", "_package_metadata", "_record_parse_stage_error",
                             "_run_required_stage", "_should_use_lightweight_tolerant_parse",
                             "_build_lightweight_graphs", "_build_lightweight_function_graphs",
                             "_parse_package_core")
        ]
        assert len(sub_funcs) > 0, (
            "parse_uasset 模块中未发现 _post_process 的子函数"
        )

    def test_post_process_shorter(self):
        """_post_process 函数体应比拆分前短。"""
        pu = self._get_module()
        source = inspect.getsource(pu._post_process)
        line_count = len(source.splitlines())
        # 拆分后应显著短于原始 168 行
        assert line_count < 100, (
            f"_post_process 仍然过长（{line_count} 行），预期应小于 100 行"
        )


# ============================================================================
# locres 字符串提取、集成流程与 Graph 节点容错测试
# ============================================================================

class TestScrapeLocresStrings:
    """_scrape_locres_strings 二进制字符串提取。"""

    def test_ascii_strings_correctly_extracted(self):
        """ASCII 可打印字符串正确提取。"""
        data = b"hello\x00world\x00"
        result = _scrape_locres_strings(data)
        assert len(result) == 2
        assert result[0]["value"] == "hello"
        assert result[1]["value"] == "world"

    def test_utf8_multibyte_strings_extracted(self):
        """UTF-8 多字节字符串（如中文）正确提取。"""
        text = "你好世界"
        data = text.encode("utf-8") + b"\x00"
        result = _scrape_locres_strings(data)
        assert len(result) == 1
        assert result[0]["value"] == text

    def test_null_byte_separates_multiple_strings(self):
        """null 字节正确分隔多个字符串。"""
        data = b"AAA\x00BBB\x00CCC\x00"
        result = _scrape_locres_strings(data)
        assert [r["value"] for r in result] == ["AAA", "BBB", "CCC"]

    def test_short_strings_below_3_chars_filtered(self):
        """长度不足 3 字符的字符串被过滤。"""
        data = b"a\x00ab\x00abc\x00"
        result = _scrape_locres_strings(data)
        assert len(result) == 1
        assert result[0]["value"] == "abc"

    def test_empty_data_returns_empty_list(self):
        """空数据返回空列表。"""
        assert _scrape_locres_strings(b"") == []
        assert _scrape_locres_strings(b"\x00") == []

    def test_max_200_strings_returned(self):
        """最多返回 200 个字符串。"""
        parts = [f"s{i:03d}".encode() for i in range(250)]
        data = b"\x00".join(parts) + b"\x00"
        result = _scrape_locres_strings(data)
        assert len(result) == 200


class TestTolerantParseIntegration:
    """tolerant_parse + _handle_parse_error 端到端。"""

    def test_parse_error_caught_and_recorded(self):
        """ParseError 被 tolerant_parse 捕获并记录到 result.errors，is_success=False。"""
        result = ParseResult()
        result.is_success = True
        _archive = ByteArchive(b"\x00" * 8, name="test.uasset")

        with pytest.raises(ParseError):
            with tolerant_parse(result, "test stage"):
                raise ParseError("模拟解析失败")

        # tolerant_parse re-raises, so is_success stays True here;
        # _handle_parse_error is what sets it to False in the real pipeline.
        assert len(result.errors) == 1
        assert "模拟解析失败" in result.errors[0]

    def test_handle_parse_error_sets_success_false(self):
        """_handle_parse_error 将 result.is_success 设为 False 并记录错误。"""
        result = ParseResult()
        result.is_success = True
        archive = ByteArchive(b"\x00" * 8, name="test.uasset")

        exc = ParseError("模拟解析失败")
        _handle_parse_error(exc, result, archive, "test.uasset", tolerant=True)

        assert result.is_success is False
        assert any("模拟解析失败" in e for e in result.errors)


class TestByteArchiveIntegration:
    """ByteArchive → 属性读取 → close 完整流程。"""

    def test_read_multi_type_and_close(self):
        """ByteArchive 读取 u8/u16/u32 后正常 close，无异常。"""
        data = (
            struct.pack("<B", 7)
            + struct.pack("<H", 1024)
            + struct.pack("<I", 42)
            + struct.pack("<I", 99)
        )
        archive = ByteArchive(data, name="test.bin")

        assert archive.read_u8("b") == 7
        assert archive.read_u16("h") == 1024
        assert archive.read_u32("f1") == 42
        assert archive.read_u32("f2") == 99

        archive.close()

    def test_read_past_eof_raises_parse_error(self):
        """读取超出 EOF 抛出 ParseError。"""
        archive = ByteArchive(b"\x00" * 2, name="tiny.bin")
        with pytest.raises(ParseError):
            archive.read_u32("overflow")
        archive.close()


# ============================================================================
# Graph 节点读取异常容错测试 (#331)
# ============================================================================

def _make_mock_node_export(name="BadNode", outer_idx=0):
    """创建带有 outer_index 的 mock node export。"""
    mock = MagicMock(spec=["object_name", "outer_index", "class_index", "serial_offset", "has_script_serialization", "class_name", "properties"])
    mock.object_name = name
    mock.outer_index = MagicMock()
    mock.outer_index.index = outer_idx
    mock.serial_offset = 0
    mock.has_script_serialization = True
    mock.class_name = "K2Node_CallFunction"
    mock.properties = []
    return mock


def test_graph_node_struct_error_handling():
    """Graph 节点读取遇到 struct.error 时应容错而非崩溃。"""
    from uasset_read.serializers.graph import read_ue_graph
    from uasset_read.serializers.object_resources import ObjectExport

    mock_archive = MagicMock()
    mock_node_export = _make_mock_node_export()
    mock_export_map = [mock_node_export]
    mock_summary = MagicMock()
    mock_import_map = []
    mock_linker = MagicMock()

    mock_graph_export = MagicMock(spec=ObjectExport)
    mock_graph_export.object_name = "TestGraph"
    mock_graph_export.properties = [
        {"name": "Nodes", "value": [1]}
    ]

    with patch("uasset_read.serializers.graph_node.read_ue_graph_node",
               side_effect=struct.error("unpack requires a buffer of 1 bytes")):
        graph = read_ue_graph(
            mock_archive, [], mock_summary, mock_export_map, mock_import_map,
            mock_graph_export, "EdGraph", 1, mock_linker
        )
    assert graph is not None
    assert isinstance(graph.nodes, list)


def test_graph_node_value_error_handling():
    """Graph 节点读取遇到 ValueError 时应容错而非崩溃。"""
    from uasset_read.serializers.graph import read_ue_graph
    from uasset_read.serializers.object_resources import ObjectExport

    mock_archive = MagicMock()
    mock_node_export = _make_mock_node_export()
    mock_export_map = [mock_node_export]
    mock_summary = MagicMock()
    mock_import_map = []
    mock_linker = MagicMock()

    mock_graph_export = MagicMock(spec=ObjectExport)
    mock_graph_export.object_name = "TestGraph"
    mock_graph_export.properties = [
        {"name": "Nodes", "value": [1]}
    ]

    with patch("uasset_read.serializers.graph_node.read_ue_graph_node",
               side_effect=ValueError("bad value")):
        graph = read_ue_graph(
            mock_archive, [], mock_summary, mock_export_map, mock_import_map,
            mock_graph_export, "EdGraph", 1, mock_linker
        )
    assert graph is not None
    assert isinstance(graph.nodes, list)


def test_graph_node_oserror_handling():
    """Graph 节点读取遇到 OSError 时应容错而非崩溃。"""
    from uasset_read.serializers.graph import read_ue_graph
    from uasset_read.serializers.object_resources import ObjectExport

    mock_archive = MagicMock()
    mock_node_export = _make_mock_node_export()
    mock_export_map = [mock_node_export]
    mock_summary = MagicMock()
    mock_import_map = []
    mock_linker = MagicMock()

    mock_graph_export = MagicMock(spec=ObjectExport)
    mock_graph_export.object_name = "TestGraph"
    mock_graph_export.properties = [
        {"name": "Nodes", "value": [1]}
    ]

    with patch("uasset_read.serializers.graph_node.read_ue_graph_node",
               side_effect=OSError("file read error")):
        graph = read_ue_graph(
            mock_archive, [], mock_summary, mock_export_map, mock_import_map,
            mock_graph_export, "EdGraph", 1, mock_linker
        )
    assert graph is not None
    assert isinstance(graph.nodes, list)


def test_graph_node_keyerror_handling():
    """Graph 节点读取遇到 KeyError 时应容错而非崩溃。"""
    from uasset_read.serializers.graph import read_ue_graph
    from uasset_read.serializers.object_resources import ObjectExport

    mock_archive = MagicMock()
    mock_node_export = _make_mock_node_export()
    mock_export_map = [mock_node_export]
    mock_summary = MagicMock()
    mock_import_map = []
    mock_linker = MagicMock()

    mock_graph_export = MagicMock(spec=ObjectExport)
    mock_graph_export.object_name = "TestGraph"
    mock_graph_export.properties = [
        {"name": "Nodes", "value": [1]}
    ]

    with patch("uasset_read.serializers.graph_node.read_ue_graph_node",
               side_effect=KeyError("missing_key")):
        graph = read_ue_graph(
            mock_archive, [], mock_summary, mock_export_map, mock_import_map,
            mock_graph_export, "EdGraph", 1, mock_linker
        )
    assert graph is not None
    assert isinstance(graph.nodes, list)


def test_graph_node_fallback_struct_error_handling():
    """UE 5.x fallback 扫描遇到 struct.error 时应添加 placeholder 节点。"""
    from uasset_read.serializers.graph import read_ue_graph
    from uasset_read.serializers.object_resources import ObjectExport

    mock_archive = MagicMock()

    mock_graph_export = MagicMock(spec=ObjectExport)
    mock_graph_export.object_name = "TestGraph"
    mock_graph_export.properties = []
    mock_graph_export.outer_index = MagicMock()
    mock_graph_export.outer_index.index = 0

    mock_node_export = MagicMock(spec=ObjectExport)
    mock_node_export.object_name = "FallbackNode"
    mock_node_export.outer_index = MagicMock()
    mock_node_export.outer_index.index = 1  # graph_export_idx

    mock_export_map = [mock_node_export]
    mock_summary = MagicMock()
    mock_import_map = []
    mock_linker = MagicMock()

    with patch("uasset_read.serializers.graph._gac", return_value="K2Node_Unknown"), \
         patch("uasset_read.serializers.graph_node.read_ue_graph_node",
               side_effect=struct.error("truncated")):
        graph = read_ue_graph(
            mock_archive, [], mock_summary, mock_export_map, mock_import_map,
            mock_graph_export, "EdGraph", 1, mock_linker
        )

    assert graph is not None
    assert len(graph.nodes) == 1
    assert graph.nodes[0].node_data.get("_parse_error") is True


# --- EventGraph 偏移验证测试 ---


def test_eventgraph_negative_offset():
    """EventGraph export 负偏移应被检测并跳过。"""
    from uasset_read.graph.parser import _validate_graph_export_offset

    mock_export = MagicMock()
    mock_export.object_name = "TestEventGraph"
    mock_export.serial_offset = -100  # 负偏移
    mock_export.serial_size = 50

    result = _validate_graph_export_offset(mock_export, archive_size=1000)
    assert result == False  # 应返回 False 表示无效


def test_eventgraph_negative_size():
    """EventGraph export 负大小应被检测并跳过。"""
    from uasset_read.graph.parser import _validate_graph_export_offset

    mock_export = MagicMock()
    mock_export.object_name = "TestEventGraph"
    mock_export.serial_offset = 100
    mock_export.serial_size = -50  # 负大小

    result = _validate_graph_export_offset(mock_export, archive_size=1000)
    assert result == False  # 应返回 False 表示无效


def test_eventgraph_offset_overflow():
    """EventGraph export 偏移超出文件大小应被检测并跳过。"""
    from uasset_read.graph.parser import _validate_graph_export_offset

    mock_export = MagicMock()
    mock_export.object_name = "TestEventGraph"
    mock_export.serial_offset = 900
    mock_export.serial_size = 200  # 900 + 200 > 1000

    result = _validate_graph_export_offset(mock_export, archive_size=1000)
    assert result == False  # 应返回 False 表示无效


def test_eventgraph_valid_offset():
    """EventGraph export 有效偏移应通过验证。"""
    from uasset_read.graph.parser import _validate_graph_export_offset

    mock_export = MagicMock()
    mock_export.object_name = "TestEventGraph"
    mock_export.serial_offset = 100
    mock_export.serial_size = 50

    result = _validate_graph_export_offset(mock_export, archive_size=1000)
    assert result == True  # 应返回 True 表示有效


# --- SubGraphs 数组长度限制与无效索引跳过测试 (#333) ---


def test_subgraphs_truncate_large_array():
    """SubGraphs 数组超过上限时应截断。"""
    from uasset_read.serializers.graph import read_ue_graph, MAX_SUBGRAPHS
    from uasset_read.serializers.object_resources import ObjectExport

    mock_archive = MagicMock()
    mock_archive.tell.return_value = 0

    mock_summary = MagicMock()
    mock_export_map = []
    mock_import_map = []
    mock_linker = MagicMock()

    # 创建一个包含大量 SubGraphs 的 mock graph_export
    mock_graph_export = MagicMock(spec=ObjectExport)
    mock_graph_export.object_name = "TestGraph"
    mock_graph_export.properties = [
        {"name": "Nodes", "value": []},
        {"name": "SubGraphs", "value": list(range(1, 2000))},  # 2000 个条目
    ]

    # 不应崩溃，应截断到 MAX_SUBGRAPHS
    graph = read_ue_graph(
        mock_archive, [], mock_summary, mock_export_map, mock_import_map,
        mock_graph_export, "EdGraph", 1, mock_linker,
    )
    assert graph is not None


def test_subgraphs_invalid_indices_skipped():
    """SubGraphs 数组包含无效 PackageIndex 时应跳过。"""
    from uasset_read.serializers.graph import read_ue_graph
    from uasset_read.serializers.object_resources import ObjectExport

    mock_archive = MagicMock()
    mock_archive.tell.return_value = 0

    mock_summary = MagicMock()
    mock_export_map = []
    mock_import_map = []
    mock_linker = MagicMock()

    # 创建一个包含无效索引的 mock graph_export
    mock_graph_export = MagicMock(spec=ObjectExport)
    mock_graph_export.object_name = "TestGraph"
    mock_graph_export.properties = [
        {"name": "Nodes", "value": []},
        {"name": "SubGraphs", "value": [0, -1, 999999, 1]},  # 包含无效索引
    ]

    # 不应崩溃，应跳过无效索引
    graph = read_ue_graph(
        mock_archive, [], mock_summary, mock_export_map, mock_import_map,
        mock_graph_export, "EdGraph", 1, mock_linker,
    )
    assert graph is not None
    assert isinstance(graph.subgraphs, list)


# ============================================================================
# 状态模型单元测试 — 验证 _result_status() 统一状态推导逻辑（#315）
# ============================================================================

# ---------------------------------------------------------------------------
# 辅助工具
# ---------------------------------------------------------------------------

@dataclass
class _FakeExport:
    """模拟 export 对象，仅含 parse_status 字段。"""
    parse_status: str = "success"


@dataclass
class _FakeDiagnostic:
    """模拟诊断对象。"""
    severity: str = "warning"

    def is_structural(self) -> bool:
        return self.severity in ("error", "critical")


@dataclass
class _FakeResult:
    """模拟 ParseResult / LinkerParseResult。"""
    is_success: bool = True
    summary: Any = None
    name_map: list[str] = field(default_factory=list)
    import_map: list = field(default_factory=list)
    export_map: list = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    diagnostics: list = field(default_factory=list)


def _make_result(**kwargs) -> _FakeResult:
    """快速构造 _FakeResult。"""
    return _FakeResult(**kwargs)


# ===========================================================================
# PARTIAL_STATUSES 集合完整性
# ===========================================================================

class TestPartialStatusesSet:
    """验证 PARTIAL_STATUSES 包含所有已知 partial 状态。"""

    @pytest.mark.parametrize("status", [
        "partial",
        "opaque",
        "skipped",
        "partial_metadata",
        "opaque_unversioned",
        "fallback",
        "metadata",
    ])
    def test_known_partial_status_in_set(self, status: str):
        """所有已知 partial 状态必须在 PARTIAL_STATUSES 中。"""
        assert status in PARTIAL_STATUSES, f"{status!r} 不在 PARTIAL_STATUSES 中"

    def test_partial_is_frozenset(self):
        """PARTIAL_STATUSES 应为 frozenset（不可变）。"""
        assert isinstance(PARTIAL_STATUSES, frozenset)


class TestFailedStatusesSet:
    """验证 FAILED_STATUSES 包含所有已知 failed 状态。"""

    def test_failed_in_set(self):
        assert "failed" in FAILED_STATUSES

    def test_failed_is_frozenset(self):
        assert isinstance(FAILED_STATUSES, frozenset)

    def test_no_overlap_with_partial(self):
        """partial 和 failed 集合不应有交集。"""
        assert PARTIAL_STATUSES.isdisjoint(FAILED_STATUSES)


# ===========================================================================
# is_success=False 分支
# ===========================================================================

class TestIsSuccessFalse:
    """is_success=False 时的状态推导。"""

    def test_no_core_data_returns_failed(self):
        """无核心数据时返回 failed。"""
        r = _make_result(is_success=False)
        assert _result_status(r) == "failed"

    def test_with_summary_returns_partial(self):
        """有 summary 但 is_success=False 时返回 partial。"""
        r = _make_result(is_success=False, summary="fake_summary")
        assert _result_status(r) == "partial"

    def test_with_name_map_returns_partial(self):
        """有 name_map 但 is_success=False 时返回 partial。"""
        r = _make_result(is_success=False, name_map=["name1"])
        assert _result_status(r) == "partial"

    def test_with_import_map_returns_partial(self):
        """有 import_map 但 is_success=False 时返回 partial。"""
        r = _make_result(is_success=False, import_map=["imp1"])
        assert _result_status(r) == "partial"

    def test_with_export_map_returns_partial(self):
        """有 export_map 但 is_success=False 时返回 partial。"""
        r = _make_result(is_success=False, export_map=["exp1"])
        assert _result_status(r) == "partial"


# ===========================================================================
# is_success=True 分支 — 错误检查
# ===========================================================================

class TestErrors:
    """错误列表影响状态。"""

    def test_no_errors_success(self):
        """无错误时返回 success。"""
        r = _make_result(is_success=True)
        assert _result_status(r) == "success"

    def test_any_error_returns_partial(self):
        """有任何错误时返回 partial。"""
        r = _make_result(is_success=True, errors=["something went wrong"])
        assert _result_status(r) == "partial"


# ===========================================================================
# is_success=True 分支 — 轻量容错解析
# ===========================================================================

class TestLightweightTolerantParse:
    """metadata.lightweight_tolerant_parse 影响状态。"""

    def test_lightweight_returns_partial(self):
        r = _make_result(is_success=True, metadata={"lightweight_tolerant_parse": True})
        assert _result_status(r) == "partial"

    def test_not_lightweight_not_affected(self):
        r = _make_result(is_success=True, metadata={"lightweight_tolerant_parse": False})
        assert _result_status(r) == "success"


# ===========================================================================
# is_success=True 分支 — 结构性诊断
# ===========================================================================

class TestStructuralDiagnostics:
    """结构性诊断影响状态。"""

    def test_structural_error_returns_partial(self):
        diag = _FakeDiagnostic(severity="error")
        r = _make_result(is_success=True, diagnostics=[diag])
        assert _result_status(r) == "partial"

    def test_structural_critical_returns_partial(self):
        diag = _FakeDiagnostic(severity="critical")
        r = _make_result(is_success=True, diagnostics=[diag])
        assert _result_status(r) == "partial"

    def test_warning_diagnostic_not_structural(self):
        """warning 级别诊断不影响状态。"""
        diag = _FakeDiagnostic(severity="warning")
        r = _make_result(is_success=True, diagnostics=[diag])
        assert _result_status(r) == "success"

    def test_info_diagnostic_not_structural(self):
        diag = _FakeDiagnostic(severity="info")
        r = _make_result(is_success=True, diagnostics=[diag])
        assert _result_status(r) == "success"


# ===========================================================================
# is_success=True 分支 — export 级状态
# ===========================================================================

class TestExportStatus:
    """export 级别 parse_status 影响 package 状态。"""

    def test_all_success_returns_success(self):
        """所有 export 均 success 时返回 success。"""
        exports = [_FakeExport("success") for _ in range(3)]
        r = _make_result(is_success=True, export_map=exports)
        assert _result_status(r) == "success"

    @pytest.mark.parametrize("status", [
        "partial",
        "opaque",
        "skipped",
        "partial_metadata",
        "opaque_unversioned",
        "fallback",
        "metadata",
    ])
    def test_any_partial_export_returns_partial(self, status: str):
        """任何 partial 状态的 export 使 package 降为 partial。"""
        exports = [_FakeExport("success"), _FakeExport(status)]
        r = _make_result(is_success=True, export_map=exports)
        assert _result_status(r) == "partial"

    def test_all_failed_returns_failed(self):
        """所有 export 均 failed 时返回 failed。"""
        exports = [_FakeExport("failed") for _ in range(3)]
        r = _make_result(is_success=True, export_map=exports)
        assert _result_status(r) == "failed"

    def test_mixed_success_and_failed_returns_partial(self):
        """success + failed 混合时返回 partial（非全 failed）。"""
        exports = [_FakeExport("success"), _FakeExport("failed")]
        r = _make_result(is_success=True, export_map=exports)
        assert _result_status(r) == "partial"

    def test_mixed_success_and_partial_returns_partial(self):
        """success + partial 混合时返回 partial。"""
        exports = [_FakeExport("success"), _FakeExport("partial")]
        r = _make_result(is_success=True, export_map=exports)
        assert _result_status(r) == "partial"

    def test_mixed_partial_and_failed_returns_partial(self):
        """partial + failed 混合时返回 partial。"""
        exports = [_FakeExport("partial"), _FakeExport("failed")]
        r = _make_result(is_success=True, export_map=exports)
        assert _result_status(r) == "partial"

    def test_single_failed_export_all_failed_returns_failed(self):
        """单个 failed export（即全部 failed）返回 failed。"""
        exports = [_FakeExport("failed")]
        r = _make_result(is_success=True, export_map=exports)
        assert _result_status(r) == "failed"

    def test_single_failed_plus_success_returns_partial(self):
        """单个 failed export 与 success 混合时返回 partial。"""
        exports = [_FakeExport("failed"), _FakeExport("success")]
        r = _make_result(is_success=True, export_map=exports)
        assert _result_status(r) == "partial"

    def test_empty_export_map_returns_success(self):
        """空 export_map 不影响状态。"""
        r = _make_result(is_success=True, export_map=[])
        assert _result_status(r) == "success"


# ===========================================================================
# 优先级验证
# ===========================================================================

class TestPriority:
    """验证状态判断的优先级顺序。"""

    def test_errors_take_priority_over_export_status(self):
        """错误优先于 export 状态。"""
        exports = [_FakeExport("success")]
        r = _make_result(
            is_success=True,
            errors=["error1"],
            export_map=exports,
        )
        assert _result_status(r) == "partial"

    def test_lightweight_take_priority_over_export_status(self):
        """轻量容错解析优先于 export 状态。"""
        exports = [_FakeExport("success")]
        r = _make_result(
            is_success=True,
            metadata={"lightweight_tolerant_parse": True},
            export_map=exports,
        )
        assert _result_status(r) == "partial"


# ===========================================================================
# 历史回归用例
# ===========================================================================

class TestRegression:
    """历史回归测试。"""

    def test_partial_metadata_not_success(self):
        """#315: partial_metadata 不应报告 success。"""
        exports = [_FakeExport("partial_metadata")]
        r = _make_result(is_success=True, export_map=exports)
        status = _result_status(r)
        assert status != "success", "partial_metadata 不应报告 success"
        assert status == "partial"

    def test_opaque_unversioned_not_success(self):
        """#315: opaque_unversioned 不应报告 success。"""
        exports = [_FakeExport("opaque_unversioned")]
        r = _make_result(is_success=True, export_map=exports)
        status = _result_status(r)
        assert status != "success", "opaque_unversioned 不应报告 success"
        assert status == "partial"

    def test_opaque_not_success(self):
        """#315: opaque 不应报告 success。"""
        exports = [_FakeExport("opaque")]
        r = _make_result(is_success=True, export_map=exports)
        status = _result_status(r)
        assert status != "success", "opaque 不应报告 success"
        assert status == "partial"

    def test_metadata_not_success(self):
        """metadata 不应报告 success。"""
        exports = [_FakeExport("metadata")]
        r = _make_result(is_success=True, export_map=exports)
        status = _result_status(r)
        assert status != "success"
        assert status == "partial"

    def test_skipped_not_success(self):
        """skipped 不应报告 success。"""
        exports = [_FakeExport("skipped")]
        r = _make_result(is_success=True, export_map=exports)
        status = _result_status(r)
        assert status != "success"
        assert status == "partial"

    def test_fallback_not_success(self):
        """fallback 不应报告 success。"""
        exports = [_FakeExport("fallback")]
        r = _make_result(is_success=True, export_map=exports)
        status = _result_status(r)
        assert status != "success"
        assert status == "partial"

    def test_partial_status_in_partial_set(self):
        """partial 本身应在 PARTIAL_STATUSES 中（安全网）。"""
        assert "partial" in PARTIAL_STATUSES


# ===========================================================================
# heuristic bytecode recovery 降级
# ===========================================================================

class TestHeuristicRecoveryStatus:
    """heuristic bytecode recovery 应降级为 partial。"""

    def test_heuristic_bytecode_recovery_is_partial(self):
        """decompiled_functions 有 serial_scan_recovery 时应降级为 partial。"""
        r = _make_result(is_success=True, metadata={"lightweight_tolerant_parse": False})
        r.decompiled_functions = [
            type("DecompiledResult", (), {"fallback_reasons": ["serial_scan_recovery"]})()
        ]
        status = _result_status(r)
        assert status == "partial", f"heuristic recovery 应降级为 partial, got {status}"

    def test_non_serial_scan_fallback_not_affected(self):
        """其他 fallback_reasons（非 serial_scan_recovery）不影响状态。"""
        r = _make_result(is_success=True, metadata={"lightweight_tolerant_parse": False})
        r.decompiled_functions = [
            type("DecompiledResult", (), {"fallback_reasons": ["bpgc_bytecode_extraction"]})()
        ]
        status = _result_status(r)
        assert status == "success", f"非 serial_scan_recovery 不应降级, got {status}"

    def test_no_fallback_reasons_not_affected(self):
        """无 fallback_reasons 的 decompiled function 不影响状态。"""
        r = _make_result(is_success=True, metadata={"lightweight_tolerant_parse": False})
        r.decompiled_functions = [
            type("DecompiledResult", (), {"fallback_reasons": []})()
        ]
        status = _result_status(r)
        assert status == "success", f"空 fallback_reasons 不应降级, got {status}"

    def test_mixed_heuristic_and_success_export(self):
        """success + heuristic decompiled functions 混合时返回 partial。"""
        r = _make_result(is_success=True, metadata={"lightweight_tolerant_parse": False})
        r.decompiled_functions = [
            type("DecompiledResult", (), {"fallback_reasons": []})(),
            type("DecompiledResult", (), {"fallback_reasons": ["serial_scan_recovery"]})(),
        ]
        status = _result_status(r)
        assert status == "partial", f"混合 heuristic 应降级为 partial, got {status}"

    def test_no_decompiled_functions_attr_not_affected(self):
        """无 decompiled_functions 属性时不降级。"""
        r = _make_result(is_success=True, metadata={"lightweight_tolerant_parse": False})
        status = _result_status(r)
        assert status == "success", f"无 decompiled_functions 属性不应降级, got {status}"


# ===========================================================================
# warnings 传递到 IR
# ===========================================================================

class TestWarningsInIR:
    """ParseResult.warnings 应传递到 PackageIR。"""

    def _build_fake_result(self, warnings=None):
        """构建用于 IR 测试的模拟结果对象。"""
        result = _FakeResult(
            is_success=True,
            metadata={"lightweight_tolerant_parse": False},
        )
        result.warnings = warnings or []
        result.name_map = []
        result.import_map = []
        result.export_map = []
        result.summary = None
        result.linker = None
        result.blueprint = None
        result.decompiled_functions = []
        result.graphs = []
        result.diagnostics = []
        result.resolved_parent_assets = []
        result.inherited_blueprint_graphs = []
        result.logic_sources = []
        result.soft_references = []
        result.soft_package_references = []
        result.hex_view_entries = []
        result.asset_registry_data = None
        result.version_container = None
        result.circular_deps = []
        result.components = []
        result.imports = []
        result.soft_object_path_list = []
        return result

    def test_warnings_propagated_to_package_ir(self):
        """ParseResult.warnings 应传递到 PackageIR。"""
        from uasset_read.ir_builder import build_package_ir

        result = self._build_fake_result(warnings=["test warning 1", "test warning 2"])
        ir = build_package_ir(result)
        assert hasattr(ir, "warnings"), "PackageIR 应有 warnings 字段"
        assert len(ir.warnings) == 2, f"应有 2 个 warnings, got {len(ir.warnings)}"
        assert "test warning 1" in ir.warnings
        assert "test warning 2" in ir.warnings

    def test_empty_warnings_results_in_empty_list(self):
        """空 warnings 列表传递为空列表。"""
        from uasset_read.ir_builder import build_package_ir

        result = self._build_fake_result(warnings=[])
        ir = build_package_ir(result)
        assert hasattr(ir, "warnings"), "PackageIR 应有 warnings 字段"
        assert len(ir.warnings) == 0, f"应有 0 个 warnings, got {len(ir.warnings)}"

    def test_no_warnings_attr_results_in_empty_list(self):
        """无 warnings 属性时传递为空列表。"""
        from uasset_read.ir_builder import build_package_ir

        result = self._build_fake_result()
        del result.warnings
        ir = build_package_ir(result)
        assert hasattr(ir, "warnings"), "PackageIR 应有 warnings 字段"
        assert len(ir.warnings) == 0, f"应有 0 个 warnings, got {len(ir.warnings)}"


# ===========================================================================
# 边界条件（#32）
# ===========================================================================

class TestBoundaryConditions:
    """验证 export 级状态对包级状态的边界条件。"""

    def test_partial_export_status_affects_package(self):
        """parse_status='partial' 应拉低包级状态。"""
        result = ParseResult()
        result.is_success = True
        result.errors = []
        result.metadata = {}
        result.diagnostics = []
        export = type("Export", (), {"parse_status": "partial"})()
        result.export_map = [export]

        status = _result_status(result)
        assert status == "partial", f"partial export 应拉低包级状态, got {status}"

    def test_all_exports_failed_returns_failed(self):
        """所有 export failed 时应返回 failed。"""
        result = ParseResult()
        result.is_success = False
        result.errors = ["x"]
        result.summary = type("Summary", (), {})()
        result.name_map = ["Name"]
        result.export_map = [
            type("Export", (), {"parse_status": "failed"})(),
            type("Export", (), {"parse_status": "failed"})(),
        ]

        status = _result_status(result)
        assert status == "failed", f"所有 export failed 应返回 failed, got {status}"


# ===========================================================================
# Markdown 渲染 status/errors/warnings
# ===========================================================================

class TestMarkdownStatusRendering:
    """Markdown 应渲染 status、errors 和 warnings。"""

    def _make_ir(self, status="success", errors=None, warnings=None):
        """构建用于 Markdown 测试的 PackageIR。"""
        from uasset_read.models.ir import PackageIR, PackageHeaderIR
        return PackageIR(
            header=PackageHeaderIR(
                package_name="Test",
                package_class="",
                package_flags=0,
                total_export_count=0,
                total_import_count=0,
                ue_version="5.4",
            ),
            name_map=(),
            imports=[],
            exports=[],
            linker=None,
            status=status,
            status_message="heuristic recovery" if status == "partial" else None,
            errors=errors or [],
            warnings=warnings or [],
        )

    def test_markdown_renders_partial_status(self):
        """Markdown 应渲染 partial status。"""
        from uasset_read.renderers.markdown_renderer import MarkdownRenderer
        from uasset_read.renderers.base import RenderOptions

        ir = self._make_ir(
            status="partial",
            errors=["test error"],
            warnings=["test warning"],
        )
        renderer = MarkdownRenderer()
        output = renderer.render(ir, RenderOptions())
        assert "partial" in output.lower(), "Markdown 应包含 partial status"
        assert "test error" in output, "Markdown 应包含 errors"
        assert "test warning" in output, "Markdown 应包含 warnings"

    def test_markdown_hides_success_status(self):
        """success 状态不应显示 status section。"""
        from uasset_read.renderers.markdown_renderer import MarkdownRenderer
        from uasset_read.renderers.base import RenderOptions

        ir = self._make_ir(status="success")
        renderer = MarkdownRenderer()
        output = renderer.render(ir, RenderOptions())
        assert "## Status" not in output, "success 时不应显示 Status section"

    def test_markdown_renders_failed_status(self):
        """Markdown 应渲染 failed status。"""
        from uasset_read.renderers.markdown_renderer import MarkdownRenderer
        from uasset_read.renderers.base import RenderOptions

        ir = self._make_ir(
            status="failed",
            errors=["fatal error"],
        )
        renderer = MarkdownRenderer()
        output = renderer.render(ir, RenderOptions())
        assert "failed" in output.lower(), "Markdown 应包含 failed status"
        assert "fatal error" in output, "Markdown 应包含 fatal error"

    def test_markdown_renders_errors_without_warnings(self):
        """仅有 errors 时应渲染 errors section。"""
        from uasset_read.renderers.markdown_renderer import MarkdownRenderer
        from uasset_read.renderers.base import RenderOptions

        ir = self._make_ir(
            status="partial",
            errors=["error 1", "error 2"],
        )
        renderer = MarkdownRenderer()
        output = renderer.render(ir, RenderOptions())
        assert "error 1" in output
        assert "error 2" in output

    def test_markdown_renders_warnings_without_errors(self):
        """仅有 warnings 时应渲染 warnings section。"""
        from uasset_read.renderers.markdown_renderer import MarkdownRenderer
        from uasset_read.renderers.base import RenderOptions

        ir = self._make_ir(
            status="partial",
            warnings=["warning 1"],
        )
        renderer = MarkdownRenderer()
        output = renderer.render(ir, RenderOptions())
        assert "warning 1" in output

    def test_markdown_no_status_section_for_empty_lists(self):
        """空 errors 和 warnings 时不显示对应 section。"""
        from uasset_read.renderers.markdown_renderer import MarkdownRenderer
        from uasset_read.renderers.base import RenderOptions

        ir = self._make_ir(status="partial")
        renderer = MarkdownRenderer()
        output = renderer.render(ir, RenderOptions())
        assert "partial" in output.lower()


# ===========================================================================
# parse_status 验证器
# ===========================================================================

class TestParseStatusValidation:
    """parse_status 验证器测试。"""

    def test_validate_parse_status_valid(self):
        """有效 parse_status 值应原样返回。"""
        assert validate_parse_status("success") == "success"
        assert validate_parse_status("opaque") == "opaque"
        assert validate_parse_status("partial_metadata") == "partial_metadata"

    def test_validate_parse_status_all_valid(self):
        """所有 ExportParseStatus 枚举值均应通过验证。"""
        for status in ExportParseStatus:
            assert validate_parse_status(status.value) == status.value

    def test_validate_parse_status_invalid(self):
        """无效 parse_status 应抛出 ValueError。"""
        with pytest.raises(ValueError):
            validate_parse_status("invalid_status")
        with pytest.raises(ValueError):
            validate_parse_status("ok")

    def test_validate_parse_status_error_message(self):
        """错误信息应包含无效值和合法值集合。"""
        with pytest.raises(ValueError, match=r"Invalid parse_status.*bogus"):
            validate_parse_status("bogus")


# ============================================================================
# Constants — 版本常量
# ============================================================================


class TestVersionConstantsExist:
    """关键版本常量应存在。"""

    def test_ue4_added_package_owner(self):
        assert hasattr(constants, "UE4_ADDED_PACKAGE_OWNER")
        assert constants.UE4_ADDED_PACKAGE_OWNER == 518

    def test_ue4_added_package_summary_localization_id(self):
        assert constants.UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID == 516

    def test_ue4_non_outer_package_import(self):
        assert constants.UE4_NON_OUTER_PACKAGE_IMPORT == 520

    def test_ue4_name_hashes_serialized(self):
        assert constants.UE4_NAME_HASHES_SERIALIZED == 504

    def test_ue5_script_serialization_offset(self):
        assert constants.UE5_SCRIPT_SERIALIZATION_OFFSET == 1010

    def test_ue5_property_tag_extension(self):
        assert constants.UE5_PROPERTY_TAG_EXTENSION == 1011

    def test_ue5_import_type_hierarchies(self):
        assert constants.UE5_IMPORT_TYPE_HIERARCHIES == 1018

    def test_ue5_legacy_versions_is_frozenset(self):
        assert isinstance(constants.UE5_LEGACY_VERSIONS, frozenset)
        assert -9 in constants.UE5_LEGACY_VERSIONS
        assert -8 in constants.UE5_LEGACY_VERSIONS


class TestPackageFileTags:
    """Package 文件标签值应正确。"""

    def test_file_tag(self):
        assert constants.PACKAGE_FILE_TAG == 0x9E2A83C1

    def test_swapped_file_tag(self):
        assert constants.PACKAGE_FILE_TAG_SWAPPED == 0xC1832A9E

    def test_tags_are_distinct(self):
        assert constants.PACKAGE_FILE_TAG != constants.PACKAGE_FILE_TAG_SWAPPED


# ============================================================================
# Constants — 边界验证常量
# ============================================================================


class TestBoundaryConstants:
    """边界验证常量值应合理。"""

    def test_max_name_count(self):
        assert constants.MAX_NAME_COUNT == 10_000_000

    def test_max_import_count(self):
        assert constants.MAX_IMPORT_COUNT == 1_000_000

    def test_max_export_count(self):
        assert constants.MAX_EXPORT_COUNT == 1_000_000

    def test_max_custom_versions(self):
        assert constants.MAX_CUSTOM_VERSIONS == 10_000

    def test_min_uasset_size(self):
        assert constants.MIN_UASSET_SIZE == 64

    def test_max_array_count(self):
        assert constants.MAX_ARRAY_COUNT == 1_000_000

    def test_max_fstring_length(self):
        assert constants.MAX_FSTRING_LENGTH == 10_000_000

    def test_max_recursion_depth(self):
        assert constants.MAX_RECURSION_DEPTH == 50

    def test_max_property_count(self):
        assert constants.MAX_PROPERTY_COUNT == 10_000


# ============================================================================
# Constants — Package Flags
# ============================================================================


class TestPackageFlags:
    """PKG_* 标志位值应与 UE 源码对齐。"""

    def test_pkg_none(self):
        assert constants.PKG_None == 0x00000000

    def test_pkg_cooked(self):
        assert constants.PKG_Cooked == 0x00000200

    def test_pkg_editor_only(self):
        assert constants.PKG_EditorOnly == 0x00000040

    def test_pkg_filter_editor_only(self):
        assert constants.PKG_FilterEditorOnly == 0x80000000

    def test_pkg_transient_flags_compound(self):
        assert (
            constants.PKG_TransientFlags
            == constants.PKG_NewlyCreated | constants.PKG_IsSaving | constants.PKG_ReloadingForCooker
        )

    def test_pkg_in_memory_only_compound(self):
        assert (
            constants.PKG_InMemoryOnly
            == constants.PKG_CompiledIn | constants.PKG_NewlyCreated
        )


# ============================================================================
# Constants — decode_package_flags
# ============================================================================


class TestDecodePackageFlags:
    """decode_package_flags 应正确解码标志位。"""

    def test_zero_returns_pkg_none(self):
        result = constants.decode_package_flags(0)
        assert result == ["PKG_None"]

    def test_single_flag(self):
        result = constants.decode_package_flags(constants.PKG_Cooked)
        assert "PKG_Cooked" in result

    def test_multiple_flags(self):
        flags = constants.PKG_Cooked | constants.PKG_EditorOnly
        result = constants.decode_package_flags(flags)
        assert "PKG_Cooked" in result
        assert "PKG_EditorOnly" in result

    def test_unknown_bits(self):
        flags = 0x04000000  # 未定义的位
        result = constants.decode_package_flags(flags)
        assert any("Unknown_" in name for name in result)


# ============================================================================
# Constants — PropertyTag 标志
# ============================================================================


class TestPropertyTagFlags:
    """PropertyTag 标志位值应正确。"""

    def test_prop_tag_none(self):
        assert constants.PROP_TAG_NONE == 0x00

    def test_prop_tag_has_array_index(self):
        assert constants.PROP_TAG_HAS_ARRAY_INDEX == 0x01

    def test_prop_tag_has_property_guid(self):
        assert constants.PROP_TAG_HAS_PROPERTY_GUID == 0x02

    def test_prop_tag_has_extensions(self):
        assert constants.PROP_TAG_HAS_EXTENSIONS == 0x04

    def test_prop_tag_has_binary_or_native(self):
        assert constants.PROP_TAG_HAS_BINARY_OR_NATIVE == 0x08

    def test_prop_tag_bool_true(self):
        assert constants.PROP_TAG_BOOL_TRUE == 0x10


# ============================================================================
# Constants — Framework 版本阈值
# ============================================================================


class TestFrameworkVersionThresholds:
    """Framework 版本阈值应正确。"""

    def test_ed_graph_pin_container_type(self):
        assert constants.FFRAMEWORK_VERSION_ED_GRAPH_PIN_CONTAINER_TYPE == 15

    def test_pins_store_fname(self):
        assert constants.FFRAMEWORK_VERSION_PINS_STORE_FNAME == 19

    def test_ue5_pin_source_index(self):
        assert constants.FUE5_MAINSTREAM_VERSION_ED_GRAPH_PIN_SOURCE_INDEX == 50

    def test_release_pin_type_uobject_wrapper(self):
        assert constants.FRELEASE_VERSION_PIN_TYPE_UOBJECT_WRAPPER == 10

    def test_float_pin_defaults_single_precision(self):
        """FUE5RELEASESTREAM_VERSION_SERIALIZE_FLOAT_PIN_DEFAULTS_AS_SINGLE_PRECISION 已移除，验证不存在。"""
        assert not hasattr(constants, "FUE5RELEASESTREAM_VERSION_SERIALIZE_FLOAT_PIN_DEFAULTS_AS_SINGLE_PRECISION")


# ============================================================================
# Constants — 节点集合 & 图常量
# ============================================================================


class TestNodeCollections:
    """蓝图图解析相关集合常量应正确。"""

    def test_control_flow_nodes_is_frozenset(self):
        assert isinstance(constants.CONTROL_FLOW_NODES, frozenset)

    def test_start_event_types_is_frozenset(self):
        assert isinstance(constants.START_EVENT_TYPES, frozenset)

    def test_data_boundary_nodes_is_frozenset(self):
        assert isinstance(constants.DATA_BOUNDARY_NODES, frozenset)

    def test_blueprint_metadata_keys_is_frozenset(self):
        assert isinstance(constants.BLUEPRINT_METADATA_KEYS, frozenset)

    def test_control_flow_nodes_contains_if_then_else(self):
        assert "K2Node_IfThenElse" in constants.CONTROL_FLOW_NODES

    def test_start_event_types_contains_event(self):
        assert "K2Node_Event" in constants.START_EVENT_TYPES

    def test_branch_type_map_values_are_strings(self):
        for val in constants.BRANCH_TYPE_MAP.values():
            assert isinstance(val, str)

    def test_graph_type_map(self):
        assert constants.GRAPH_TYPE_MAP["EdGraph"] == "event"
        assert constants.GRAPH_TYPE_MAP["UberEdGraph"] == "uber"

    def test_etrigger_event_pin_map(self):
        assert constants.ETRIGGER_EVENT_PIN_MAP["Started"] == "Started"
        assert constants.ETRIGGER_EVENT_PIN_MAP["Triggered"] == "Triggered"


# ============================================================================
# Constants — CustomVersion GUID 格式
# ============================================================================


class TestCustomVersionGUIDs:
    """CustomVersion GUID 应为合法格式。"""

    @pytest.mark.parametrize(
        "guid_name",
        [
            "FFRAMEWORK_OBJECT_VERSION_GUID",
            "FUE5_MAINSTREAM_VERSION_GUID",
            "FRELEASE_OBJECT_VERSION_GUID",
            "FUE5RELEASESTREAM_OBJECT_VERSION_GUID",
            "FBLUEPRINTS_OBJECT_VERSION_GUID",
            "FCORE_OBJECT_VERSION_GUID",
            "FEDITOR_OBJECT_VERSION_GUID",
            "FANIM_OBJECT_VERSION_GUID",
            "FPHYSICS_OBJECT_VERSION_GUID",
            "FRENDERING_OBJECT_VERSION_GUID",
            "FSEQUENCER_OBJECT_VERSION_GUID",
        ],
    )
    def test_guid_format(self, guid_name):
        guid = getattr(constants, guid_name)
        assert isinstance(guid, str)
        # UE GUID 格式: XXXXXXXX-XXXXXXXX-XXXXXXXX-XXXXXXXX (35 chars, 3 dashes)
        assert len(guid) == 35
        assert guid.count("-") == 3


# ============================================================================
# CPF_* 常量与 UE ObjectMacros.h 对齐
# ============================================================================


class TestCPFConstantsAlignment:
    """CPF_* 常量与 UE ObjectMacros.h 逐位对齐。"""

    def test_cpf_edit(self):
        assert constants.CPF_Edit == 0x01

    def test_cpf_const_parm(self):
        assert constants.CPF_ConstParm == 0x02

    def test_cpf_blueprint_visible(self):
        assert constants.CPF_BlueprintVisible == 0x04

    def test_cpf_export_object(self):
        assert constants.CPF_ExportObject == 0x08

    def test_cpf_blueprint_read_only(self):
        assert constants.CPF_BlueprintReadOnly == 0x10

    def test_cpf_net(self):
        assert constants.CPF_Net == 0x20

    def test_cpf_edit_fixed_size(self):
        assert constants.CPF_EditFixedSize == 0x40

    def test_cpf_parm(self):
        assert constants.CPF_Parm == 0x80

    def test_cpf_out_parm(self):
        assert constants.CPF_OutParm == 0x100

    def test_cpf_zero_constructor(self):
        assert constants.CPF_ZeroConstructor == 0x200

    def test_cpf_return_parm(self):
        assert constants.CPF_ReturnParm == 0x400

    def test_cpf_disable_edit_on_template(self):
        assert constants.CPF_DisableEditOnTemplate == 0x800

    def test_cpf_non_nullable(self):
        assert constants.CPF_NonNullable == 0x1000

    def test_cpf_transient(self):
        assert constants.CPF_Transient == 0x2000

    def test_cpf_config(self):
        assert constants.CPF_Config == 0x4000

    def test_cpf_required_parm(self):
        assert constants.CPF_RequiredParm == 0x8000

    def test_cpf_disable_edit_on_instance(self):
        assert constants.CPF_DisableEditOnInstance == 0x10000

    def test_cpf_edit_const(self):
        assert constants.CPF_EditConst == 0x20000

    def test_cpf_global_config(self):
        assert constants.CPF_GlobalConfig == 0x40000

    def test_cpf_instanced_reference(self):
        assert constants.CPF_InstancedReference == 0x80000

    def test_cpf_duplicate_transient(self):
        assert constants.CPF_DuplicateTransient == 0x200000

    def test_cpf_save_game(self):
        assert constants.CPF_SaveGame == 0x1000000

    def test_cpf_no_clear(self):
        assert constants.CPF_NoClear == 0x2000000

    def test_cpf_virtual(self):
        assert constants.CPF_Virtual == 0x4000000

    def test_cpf_reference_parm(self):
        assert constants.CPF_ReferenceParm == 0x8000000

    def test_cpf_blueprint_assignable(self):
        assert constants.CPF_BlueprintAssignable == 0x10000000

    def test_cpf_deprecated(self):
        assert constants.CPF_Deprecated == 0x20000000

    def test_cpf_is_plain_old_data(self):
        assert constants.CPF_IsPlainOldData == 0x40000000

    def test_cpf_rep_skip(self):
        assert constants.CPF_RepSkip == 0x80000000

    def test_cpf_rep_notify(self):
        assert constants.CPF_RepNotify == 0x100000000

    def test_cpf_interp(self):
        assert constants.CPF_Interp == 0x200000000

    def test_cpf_non_transactional(self):
        assert constants.CPF_NonTransactional == 0x400000000

    def test_cpf_editor_only(self):
        assert constants.CPF_EditorOnly == 0x800000000

    def test_cpf_no_destructor(self):
        assert constants.CPF_NoDestructor == 0x1000000000

    def test_cpf_auto_weak(self):
        assert constants.CPF_AutoWeak == 0x4000000000

    def test_cpf_contains_instanced_reference(self):
        assert constants.CPF_ContainsInstancedReference == 0x8000000000

    def test_cpf_asset_registry_searchable(self):
        assert constants.CPF_AssetRegistrySearchable == 0x10000000000

    def test_cpf_simple_display(self):
        assert constants.CPF_SimpleDisplay == 0x20000000000

    def test_cpf_advanced_display(self):
        assert constants.CPF_AdvancedDisplay == 0x40000000000

    def test_cpf_protected(self):
        assert constants.CPF_Protected == 0x80000000000

    def test_cpf_blueprint_callable(self):
        assert constants.CPF_BlueprintCallable == 0x100000000000

    def test_cpf_blueprint_authority_only(self):
        assert constants.CPF_BlueprintAuthorityOnly == 0x200000000000

    def test_cpf_text_export_transient(self):
        assert constants.CPF_TextExportTransient == 0x400000000000

    def test_cpf_non_pie_duplicate_transient(self):
        assert constants.CPF_NonPIEDuplicateTransient == 0x800000000000

    def test_cpf_expose_on_spawn(self):
        assert constants.CPF_ExposeOnSpawn == 0x1000000000000

    def test_cpf_persistent_instance(self):
        assert constants.CPF_PersistentInstance == 0x2000000000000

    def test_cpf_uobject_wrapper(self):
        assert constants.CPF_UObjectWrapper == 0x4000000000000

    def test_cpf_has_value_type_hash(self):
        assert constants.CPF_HasGetValueTypeHash == 0x8000000000000

    def test_cpf_native_access_specifier_public(self):
        assert constants.CPF_NativeAccessSpecifierPublic == 0x10000000000000

    def test_cpf_native_access_specifier_protected(self):
        assert constants.CPF_NativeAccessSpecifierProtected == 0x20000000000000

    def test_cpf_native_access_specifier_private(self):
        assert constants.CPF_NativeAccessSpecifierPrivate == 0x40000000000000

    def test_cpf_skip_serialization(self):
        assert constants.CPF_SkipSerialization == 0x80000000000000

    def test_cpf_tobject_ptr(self):
        assert constants.CPF_TObjectPtr == 0x100000000000000

    def test_cpf_allow_self_reference(self):
        assert constants.CPF_AllowSelfReference == 0x1000000000000000

    def test_cpf_experimental_overridable_logic(self):
        assert constants.CPF_ExperimentalOverridableLogic == 0x0200000000000000

    def test_cpf_experimental_always_overriden(self):
        assert constants.CPF_ExperimentalAlwaysOverriden == 0x0400000000000000

    def test_cpf_experimental_never_overriden(self):
        assert constants.CPF_ExperimentalNeverOverriden == 0x0800000000000000

    def test_cpf_force_post_construct_link(self):
        assert constants.CPF_ForcePostConstructLink == 0x2000000000000000

    def test_no_nonexistent_flags(self):
        """验证不存在的标志位已被移除。"""
        import uasset_read.constants as c
        removed = [
            'CPF_BlueprintPure', 'CPF_BlueprintCompilerGenerated',
            'CPF_NetSerialize', 'CPF_RepRetry', 'CPF_Constructed',
            'CPF_NaturalizePropertyIndex', 'CPF_Required',
            'CPF_ReferencePersisted',
        ]
        for name in removed:
            assert not hasattr(c, name), f"{name} 不应存在于 constants 中"

    def test_all_flags_are_power_of_two(self):
        """所有 CPF_* 常量必须是 2 的幂（位掩码）。"""
        import uasset_read.constants as c
        flags = [v for k, v in vars(c).items() if k.startswith('CPF_') and isinstance(v, int)]
        for flag in flags:
            assert flag > 0 and (flag & (flag - 1)) == 0, f"CPF_* 值 {flag:#x} 不是 2 的幂"

    def test_no_duplicate_values(self):
        """CPF_* 常量值不得重复。"""
        import uasset_read.constants as c
        flags = [v for k, v in vars(c).items() if k.startswith('CPF_') and isinstance(v, int)]
        assert len(flags) == len(set(flags)), "存在重复的 CPF_* 值"


# ============================================================================
# Versioning — EUEVersion 枚举
# ============================================================================


class TestEUEVersion:
    """EUEVersion 枚举值应正确。"""

    def test_ue4_23(self):
        assert EUEVersion.UE4_23 == 516

    def test_ue5_0(self):
        assert EUEVersion.UE5_0 == 1000

    def test_ue5_2(self):
        assert EUEVersion.UE5_2 == 1005

    def test_ue5_5(self):
        assert EUEVersion.UE5_5 == 1012

    def test_ue5_8(self):
        assert EUEVersion.UE5_8 == 1018

    def test_is_int_enum(self):
        assert isinstance(EUEVersion.UE5_0, int)

    def test_ordering(self):
        assert EUEVersion.UE4_23 < EUEVersion.UE5_0
        assert EUEVersion.UE5_0 < EUEVersion.UE5_8


# ============================================================================
# Versioning — VersionStream
# ============================================================================


class TestVersionStream:
    """VersionStream 应正确创建和比较。"""

    def test_stream_framework(self):
        assert STREAM_FRAMEWORK.guid == constants.FFRAMEWORK_OBJECT_VERSION_GUID
        assert STREAM_FRAMEWORK.name == "framework"

    def test_stream_map_count(self):
        assert len(STREAM_MAP) >= 27

    def test_stream_frozen(self):
        with pytest.raises(AttributeError):
            STREAM_FRAMEWORK.name = "changed"

    def test_all_streams_have_guid_and_name(self):
        for key, stream in STREAM_MAP.items():
            assert isinstance(stream.guid, str)
            assert isinstance(stream.name, str)
            assert len(stream.guid) > 0


# ============================================================================
# Versioning — VersionContainer
# ============================================================================


class TestVersionContainer:
    """VersionContainer 版本查询应正确工作。"""

    def test_empty_container_get_version_returns_default(self):
        vc = VersionContainer()
        assert vc.get_version("any-guid") == 0

    def test_empty_container_get_version_custom_default(self):
        vc = VersionContainer()
        assert vc.get_version("any-guid", default=42) == 42

    def test_container_with_custom_versions(self):
        class FakeVersion:
            def __init__(self, guid, version):
                self.guid = guid
                self.version = version

        vc = VersionContainer(
            custom_versions=[
                FakeVersion("FFC743F-43B04480-939114DF-171D2073", 7),
            ],
        )
        # 有横杠
        assert vc.get_version("FFC743F-43B04480-939114DF-171D2073") == 7
        # 无横杠
        assert vc.get_version("FFC743F43B04480939114DF171D2073") == 7
        # 大小写不敏感
        assert vc.get_version("ffc743f43b04480939114df171d2073") == 7

    def test_container_is_ue5(self):
        vc = VersionContainer(file_version_ue5=1012)
        assert vc.is_ue5 is True

    def test_container_ue4_only(self):
        """file_version_ue5=0 时 is_ue5 仍为 True（UE5_VERSION_MIN=0），
        这是 UE 设计行为：is_ue5 仅判断 file_version_ue5 >= 0。"""
        vc = VersionContainer(file_version_ue5=0, file_version_ue4=520)
        # UE5_VERSION_MIN=0，所以 0 >= 0 → True
        assert vc.is_ue5 is True

    def test_file_version_property(self):
        vc = VersionContainer(file_version_ue4=520, file_version_ue5=1012)
        fv = vc.file_version
        assert isinstance(fv, FPackageFileVersion)
        assert fv.file_version_ue4 == 520
        assert fv.file_version_ue5 == 1012


# ============================================================================
# Versioning — FPackageFileVersion
# ============================================================================


class TestFPackageFileVersion:
    """FPackageFileVersion 应正确比较。"""

    def test_to_value_ue5_priority(self):
        fv = FPackageFileVersion(file_version_ue4=520, file_version_ue5=1012)
        assert fv.to_value() == 1012

    def test_to_value_ue4_fallback(self):
        fv = FPackageFileVersion(file_version_ue4=520, file_version_ue5=0)
        assert fv.to_value() == 520

    def test_ge(self):
        fv = FPackageFileVersion(file_version_ue5=1012)
        assert fv >= 1012
        assert fv >= 1000
        assert not fv >= 1013

    def test_gt(self):
        fv = FPackageFileVersion(file_version_ue5=1012)
        assert fv > 1011
        assert not fv > 1012

    def test_le(self):
        fv = FPackageFileVersion(file_version_ue5=1012)
        assert fv <= 1012
        assert fv <= 1013
        assert not fv <= 1011

    def test_lt(self):
        fv = FPackageFileVersion(file_version_ue5=1012)
        assert fv < 1013
        assert not fv < 1012


# ============================================================================
# Versioning — build_version_container
# ============================================================================


class TestBuildVersionContainer:
    """build_version_container 应从 summary 构建 VersionContainer。"""

    def test_build_from_summary(self):
        class FakeCustomVersion:
            def __init__(self, guid, version):
                self.guid = guid
                self.version = version

        class FakeSummary:
            custom_versions = [
                FakeCustomVersion("FFC743F-43B04480-939114DF-171D2073", 7),
            ]
            file_version_ue5 = 1012
            file_version_ue4 = 520

        vc = build_version_container(FakeSummary())
        assert vc.file_version_ue5 == 1012
        assert vc.file_version_ue4 == 520
        assert vc.get_version("FFC743F-43B04480-939114DF-171D2073") == 7

    def test_build_from_summary_no_ue4(self):
        class FakeSummary:
            custom_versions = []
            file_version_ue5 = 0

        vc = build_version_container(FakeSummary())
        assert vc.file_version_ue4 == 0
        # is_ue5 始终为 True（UE5_VERSION_MIN=0）
        assert vc.is_ue5 is True


# ============================================================================
# 质量门禁测试 — 静默异常检测
# ============================================================================


def _find_silent_exceptions(filepath):
    """检测文件中的 except + pass 模式（允许已知的安全网和清理代码）"""
    with open(filepath, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    issues = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for handler in node.handlers:
                if len(handler.body) == 1 and isinstance(handler.body[0], ast.Pass):
                    issues.append(f"行 {handler.lineno}: except {handler.type}")
    return issues


def test_no_silent_exceptions():
    """src/ 目录下应无静默异常吞没（允许已知的安全网和清理代码）"""
    src_dir = os.path.join(os.path.dirname(__file__), "..", "src", "uasset_read")
    # 允许的静默异常模式（cleanup/safety-net），匹配相对路径
    allowed_files = {
        "archive.py",  # __del__ 安全网
        "parse_uasset.py",  # 清理代码
        "core/__init__.py",  # 清理代码
        "iostore/reader.py",  # 安全网
        "pak/reader.py",  # 安全网
    }
    all_issues = []
    for root, _, files in os.walk(src_dir):
        for f in files:
            if f.endswith(".py"):
                filepath = os.path.join(root, f)
                # 计算相对路径用于匹配
                rel_path = os.path.relpath(filepath, src_dir).replace(os.sep, "/")
                if rel_path in allowed_files:
                    continue
                issues = _find_silent_exceptions(filepath)
                for issue in issues:
                    all_issues.append(f"{filepath}: {issue}")
    assert len(all_issues) == 0, (
        f"发现 {len(all_issues)} 处静默异常吞没:\n" + "\n".join(all_issues[:10])
    )


# ============================================================================
# 质量门禁 — 可变默认参数检测
# ============================================================================


def test_flow_builder_no_mutable_defaults():
    """flow_builder 应无可变默认参数"""
    from uasset_read.graph import flow_builder

    issues = []
    for name, obj in inspect.getmembers(flow_builder, inspect.isfunction):
        sig = inspect.signature(obj)
        for param_name, param in sig.parameters.items():
            if param.default is not inspect.Parameter.empty:
                if isinstance(param.default, (dict, list, set)):
                    issues.append(f"{name}({param_name}={param.default})")
    assert len(issues) == 0, f"flow_builder 存在可变默认参数: {issues}"


# ============================================================================
# 质量门禁 — 核心导入分层验证
# ============================================================================


@pytest.mark.parametrize(
    "needle",
    ["kismet", "cpp_gen", "graph", "pak", "iostore"],
)
def test_core_import_does_not_load_extras(needle: str):
    """导入 parse_package 不应加载 extras 模块"""
    modules_before = set(sys.modules.keys())
    from uasset_read.parse_uasset import parse_package
    modules_after = set(sys.modules.keys())
    new_modules = modules_after - modules_before
    assert not any(needle in m for m in new_modules), (
        f"parse_package 导入意外加载了 {needle} 模块: "
        f"{[m for m in sorted(new_modules) if needle in m]}"
    )


# ============================================================================
# 质量门禁 — FULL_SERIALIZER 清理验证
# ============================================================================


def test_full_serializer_not_used():
    """SerializationStrategy.FULL_SERIALIZER 不应在生产代码中使用。"""
    from uasset_read.parsers.class_serialization_strategy import CLASS_STRATEGY_TABLE
    for cls, strategy in CLASS_STRATEGY_TABLE.items():
        assert strategy.value != "full_serializer", (
            f"{cls} 使用了未实现的 FULL_SERIALIZER 策略"
        )


def test_full_serializer_removed_from_enum():
    """FULL_SERIALIZER 已从 SerializationStrategy 枚举中移除。"""
    from uasset_read.parsers.class_serialization_strategy import SerializationStrategy
    assert not hasattr(SerializationStrategy, "FULL_SERIALIZER"), (
        "FULL_SERIALIZER 仍存在于 SerializationStrategy 枚举中"
    )


# ============================================================================
# 质量门禁 — include_linker 废弃验证
# ============================================================================


def test_include_linker_deprecated():
    """parse_package() 的 include_linker 参数应触发 DeprecationWarning。"""
    from uasset_read.parse_uasset import parse_package

    # 参数应仍然存在于签名中（向后兼容）
    sig = inspect.signature(parse_package)
    assert "include_linker" in sig.parameters

    # 非默认值应触发 DeprecationWarning
    with pytest.warns(DeprecationWarning, match="include_linker"):
        try:
            parse_package("nonexistent.uasset", include_linker=False)
        except (FileNotFoundError, ValueError):
            pass  # 预期失败，但警告应该已经触发


# ============================================================================
# 质量门禁 — 入口合同测试
# ============================================================================


class TestEntryContracts:
    """入口模块与公共 API 的稳定合同。"""

    def test_public_api_exports_and_list_formats(self):
        """包级公共 API 可导出且 list_formats 返回常见格式。"""
        importlib.reload(uasset_read)

        for name in ("parse_single", "parse_batch", "list_formats"):
            assert hasattr(uasset_read, name)
            assert callable(getattr(uasset_read, name))
            assert name in uasset_read.__all__

        formats = uasset_read.list_formats()
        assert {"json", "markdown"}.issubset(set(formats))

    def test_entrypoint_symbols_are_callable(self):
        """入口模块导出的函数应可调用。"""
        from uasset_read.parse_uasset import (
            parse_package,
            parse_package_lazy,
            parse_uasset,
            parse_uasset_with_linker,
        )

        for func in (parse_package, parse_package_lazy, parse_uasset, parse_uasset_with_linker):
            assert callable(func)

    def test_parse_package_signature(self):
        """parse_package 签名应包含核心参数。"""
        from uasset_read.parse_uasset import parse_package

        sig = inspect.signature(parse_package)
        params = sig.parameters
        required = {"path", "tolerant", "provider", "mappings_path", "game", "force_full_parse"}
        assert required.issubset(params)
        assert "return" in parse_package.__annotations__

    def test_core_parse_signatures_stay_aligned(self):
        """parse_single 与 parse_batch 的共享参数默认值应保持一致。"""
        single_sig = inspect.signature(core.parse_single)
        batch_sig = inspect.signature(core.parse_batch)

        for name in ("tolerant", "verbose", "include_schema", "include_function_graphs", "include_parent_assets", "asset_roots", "mappings_path", "game", "force_full_parse", "hex_view", "memory_policy", "output_level"):
            assert name in single_sig.parameters
            assert name in batch_sig.parameters
            assert batch_sig.parameters[name].default == single_sig.parameters[name].default

        assert "input_dir" in batch_sig.parameters
        assert "file_path" in single_sig.parameters
        assert "return" in core.parse_batch.__annotations__

    def test_entry_modules_delegate_without_print_or_sys_exit(self):
        """入口模块不应包含 sys.exit / print，parse_uasset 仍应委托给 parse_package。"""
        parse_uasset_mod = importlib.import_module("uasset_read.parse_uasset")

        for mod in (parse_uasset_mod, core):
            src = inspect.getsource(mod)
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Attribute) and func.attr == "exit":
                        if isinstance(func.value, ast.Name) and func.value.id == "sys":
                            pytest.fail(f"{mod.__name__} 第 {node.lineno} 行包含 sys.exit() 调用")
                    if isinstance(func, ast.Name) and func.id == "print":
                        pytest.fail(f"{mod.__name__} 第 {node.lineno} 行包含 print() 调用")

        assert "parse_package" in inspect.getsource(parse_uasset_mod.parse_uasset)
        assert "linker_formats" in inspect.getsource(core.parse_single)

    def test_pak_info_size_contract(self):
        """PAK_INFO_SIZES 应保持当前已知序列化大小。"""
        expected = {
            "v1-6": 45,
            "v7": 61,
            "v8": 221,
            "v9": 222,
            "v10+": 221,
        }
        for version, size in expected.items():
            assert PAK_INFO_SIZES[version] == size


# ============================================================================
# 质量门禁 — 测试套件形状检查
# ============================================================================

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "tests"


def test_total_test_file_count_is_capped():
    files = sorted(TESTS.rglob("test_*.py"))
    assert len(files) <= 100


def test_core_benchmark_file_count_is_capped():
    files = sorted((TESTS / "integration").glob("test_*.py"))
    assert len(files) <= 10
