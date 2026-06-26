"""容错解析相关测试 — 合并自以下测试文件：
- test_tolerant_early_parse_diagnostics.py — 容错早期解析诊断回归测试
- test_tolerant_class_specific.py — Class-specific tolerant skip 测试
"""
from __future__ import annotations

import gc
import json
import struct
from pathlib import Path

import pytest

from uasset_read.constants import PACKAGE_FILE_TAG, UE5_PACKAGE_SAVED_HASH
from uasset_read.core import ParseError, parse_single
from uasset_read.parse_uasset import parse_package, parse_uasset_with_linker

FIXTURES_DIR = Path(__file__).parent / "fixtures"
MAX_PARAM_COUNT = 20  # 参数化资产数量上限


def _read_fixture_lines(name: str) -> list[str]:
    """读取 fixture 文件中的非空行，限制数量防止 OOM。"""
    path = FIXTURES_DIR / name
    if not path.exists():
        pytest.skip(f"Fixture file not found: {path}", allow_module_level=True)
    lines = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    return lines[:MAX_PARAM_COUNT]


def _package_with_bad_custom_version_count(count: int) -> bytes:
    """构造含有异常 custom version count 的最小包数据。"""
    data = bytearray()
    data += struct.pack("<Iiii", PACKAGE_FILE_TAG, -9, 0, 0)
    data += struct.pack("<i", UE5_PACKAGE_SAVED_HASH)
    data += b"\x00" * 20
    data += struct.pack("<i", 0)  # total_header_size
    data += struct.pack("<I", count)
    data += b"\x00" * 128
    return bytes(data)


# ===========================================================================
# 第一部分：容错早期解析诊断回归测试
# ===========================================================================

class TestTolerantEarlyParseDiagnostics:
    """容错早期解析诊断行为测试。"""

    def test_tolerant_json_returns_parse_stage_diagnostic(self, tmp_path):
        """tolerant 模式下 JSON 输出 status=failed。"""
        path = tmp_path / "bad_custom_versions.uasset"
        path.write_bytes(_package_with_bad_custom_version_count(10_000_001))

        output = parse_single(str(path), format="json", tolerant=True)
        data = json.loads(output)

        assert data["status"]["status"] == "failed"

    def test_strict_json_still_raises_on_early_parse_failure(self, tmp_path):
        """strict 模式下早期解析失败应抛出异常。"""
        path = tmp_path / "bad_custom_versions.uasset"
        path.write_bytes(_package_with_bad_custom_version_count(10_000_001))

        with pytest.raises(ParseError):
            parse_single(str(path), format="json", tolerant=False)


class TestStrictModeConsistency:
    """严格模式语义一致性：parse_package / parse_uasset_with_linker 在
    tolerant=False 时必须抛出异常，不能静默返回失败结果。"""

    def test_parse_package_strict_raises(self, tmp_path):
        """parse_package strict 模式抛出 ParseError。"""
        path = tmp_path / "bad.uasset"
        path.write_bytes(_package_with_bad_custom_version_count(10_000_001))
        with pytest.raises(ParseError):
            parse_package(str(path), tolerant=False)

    def test_parse_uasset_with_linker_strict_raises(self, tmp_path):
        """parse_uasset_with_linker strict 模式抛出 ParseError。"""
        path = tmp_path / "bad.uasset"
        path.write_bytes(_package_with_bad_custom_version_count(10_000_001))
        with pytest.raises(ParseError):
            parse_uasset_with_linker(str(path), tolerant=False)

    def test_parse_package_tolerant_returns_failed_result(self, tmp_path):
        """parse_package tolerant 模式返回失败结果。"""
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


# ===========================================================================
# 第二部分：Class-specific tolerant skip 测试
# ===========================================================================

class TestCubeBuilderTolerantSkip:
    """CubeBuilder_* export 的 tolerant skip 测试。"""

    @pytest.mark.parametrize("asset_path", _read_fixture_lines("real_asset_failures_cube_builder.txt"))
    def test_cube_builder_tolerant_parse_succeeds(self, asset_path: str):
        """CubeBuilder 资产应能解析成功（可能有局部错误，但资产级 is_success 为 True）。"""
        result = parse_uasset_with_linker(asset_path, tolerant=True)
        assert result.summary is not None, "Summary should be parsed"
        assert result.export_map is not None, "Export map should be parsed"
        fatal_errors = [e for e in result.errors if "serial_offset" in e.lower() or "payloadtoc" in e.lower()]
        assert len(fatal_errors) == 0, f"Fatal errors should not occur: {fatal_errors}"
        del result
        gc.collect()


class TestAnimationDataModelTolerantSkip:
    """AnimationDataModel export 的 tolerant skip 测试。"""

    @pytest.mark.parametrize("asset_path", _read_fixture_lines("real_asset_failures_animation_data_model.txt"))
    def test_animation_data_model_tolerant_parse_succeeds(self, asset_path: str):
        """AnimationDataModel 资产应能解析成功。"""
        result = parse_uasset_with_linker(asset_path, tolerant=True)
        assert result.summary is not None
        assert result.export_map is not None
        fatal_errors = [e for e in result.errors if "serial_offset" in e.lower() or "payloadtoc" in e.lower()]
        assert len(fatal_errors) == 0, f"Fatal errors should not occur: {fatal_errors}"
        del result
        gc.collect()


class TestPayloadOffsetsTolerant:
    """Payload TOC / export offset 异常的 tolerant 处理测试。"""

    @pytest.mark.parametrize("asset_path", _read_fixture_lines("real_asset_failures_payload_offsets.txt"))
    def test_payload_offset_tolerant_parse(self, asset_path: str):
        """Payload offset 异常资产应能解析到 summary 和 export_map。"""
        result = parse_uasset_with_linker(asset_path, tolerant=True)
        assert result.summary is not None
        assert result.export_map is not None
        fatal_errors = [e for e in result.errors if "serial_offset" in e.lower() or "payloadtoc" in e.lower()]
        assert len(fatal_errors) == 0, f"Fatal errors should not occur: {fatal_errors}"
        del result
        gc.collect()


class TestNiagaraTolerantSkip:
    """Niagara payload 的 tolerant skip 测试。"""

    @pytest.mark.parametrize("asset_path", _read_fixture_lines("real_asset_failures_niagara.txt"))
    def test_niagara_tolerant_parse(self, asset_path: str):
        """Niagara 资产 tolerant 解析测试。"""
        result = parse_uasset_with_linker(asset_path, tolerant=True)
        assert result.summary is not None
        assert result.export_map is not None
        fatal_errors = [e for e in result.errors if "serial_offset" in e.lower() or "payloadtoc" in e.lower()]
        assert len(fatal_errors) == 0, f"Fatal errors should not occur: {fatal_errors}"
        del result
        gc.collect()


class TestMovieSceneTolerantSkip:
    """MovieScene payload 的 tolerant skip 测试。"""

    @pytest.mark.parametrize("asset_path", _read_fixture_lines("real_asset_failures_movie_scene.txt"))
    def test_movie_scene_tolerant_parse(self, asset_path: str):
        """MovieScene 资产 tolerant 解析测试。"""
        result = parse_uasset_with_linker(asset_path, tolerant=True)
        assert result.summary is not None
        assert result.export_map is not None
        fatal_errors = [e for e in result.errors if "serial_offset" in e.lower() or "payloadtoc" in e.lower()]
        assert len(fatal_errors) == 0, f"Fatal errors should not occur: {fatal_errors}"
        del result
        gc.collect()


class TestK2NodeTolerantSkip:
    """K2Node payload 的 tolerant skip 测试。"""

    @pytest.mark.parametrize("asset_path", _read_fixture_lines("real_asset_failures_k2_nodes.txt"))
    def test_k2node_tolerant_parse(self, asset_path: str):
        """K2Node 资产 tolerant 解析测试。"""
        result = parse_uasset_with_linker(asset_path, tolerant=True)
        assert result.summary is not None
        assert result.export_map is not None
        fatal_errors = [e for e in result.errors if "serial_offset" in e.lower() or "payloadtoc" in e.lower()]
        assert len(fatal_errors) == 0, f"Fatal errors should not occur: {fatal_errors}"
        del result
        gc.collect()


class TestMetaSoundTolerantSkip:
    """MetaSound payload 的 tolerant skip 测试。"""

    @pytest.mark.parametrize("asset_path", _read_fixture_lines("real_asset_failures_metasound.txt"))
    def test_metasound_tolerant_parse(self, asset_path: str):
        """MetaSound 资产 tolerant 解析测试。"""
        result = parse_uasset_with_linker(asset_path, tolerant=True)
        assert result.summary is not None
        assert result.export_map is not None
        fatal_errors = [e for e in result.errors if "serial_offset" in e.lower() or "payloadtoc" in e.lower()]
        assert len(fatal_errors) == 0, f"Fatal errors should not occur: {fatal_errors}"
        del result
        gc.collect()


class TestMaterialExpressionTolerantSkip:
    """MaterialExpression payload 的 tolerant skip 测试。"""

    @pytest.mark.parametrize("asset_path", _read_fixture_lines("real_asset_failures_material_expression.txt"))
    def test_material_expression_tolerant_parse(self, asset_path: str):
        """MaterialExpression 资产 tolerant 解析测试。"""
        result = parse_uasset_with_linker(asset_path, tolerant=True)
        assert result.summary is not None
        assert result.export_map is not None
        fatal_errors = [e for e in result.errors if "serial_offset" in e.lower() or "payloadtoc" in e.lower()]
        assert len(fatal_errors) == 0, f"Fatal errors should not occur: {fatal_errors}"
