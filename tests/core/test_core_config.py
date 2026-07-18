"""Core 配置测试 — 合并自 test_config_and_limits.py。

覆盖：ParseConfig 参数合并、FString/FText 安全容错、StructProperty 解析。
"""
from __future__ import annotations

import os
import struct
import warnings
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from uasset_read.archive import ByteArchive, MAX_FSTRING_LENGTH
from uasset_read.config import ParseConfig
from uasset_read.constants import UE5_PROPERTY_TAG_EXTENSION
from uasset_read.exceptions import ParseError
from uasset_read.parsers.property_parser import parse_properties_from_export
from uasset_read.parse_uasset import _resolve_parse_params, parse_package
from uasset_read.serializers.graph import read_ftext_with_history
import uasset_read.parsers.property_parser as pp

# 测试样本路径
_SAMPLES_DIR = Path(__file__).parent.parent / "samples"
_SAMPLE_BLUEPRINT = str(_SAMPLES_DIR / "FirstPerson_BP_FirstPersonGameMode.uasset")
_has_sample = os.path.isfile(_SAMPLE_BLUEPRINT)


# ---------------------------------------------------------------------------
# ParseConfig 参数合并测试
# ---------------------------------------------------------------------------

class TestResolveParseParams:
    """_resolve_parse_params() 单元测试。"""

    def test_config_values_used_when_kwargs_empty(self):
        """空 kwargs 时，config 值应原样返回。"""
        cfg = ParseConfig(
            tolerant=False,
            force_full_parse=True,
            hex_view=True,
            include_parent_assets=True,
            game="Fortnite",
            lightweight_threshold=7,
        )
        result = _resolve_parse_params(cfg, {})
        assert result["tolerant"] is False
        assert result["force_full_parse"] is True
        assert result["hex_view"] is True
        assert result["include_parent_assets"] is True
        assert result["game"] == "Fortnite"
        assert result["lightweight_threshold"] == 7

    def test_explicit_kwargs_override_config(self):
        """显式旧参数应覆盖 config 值。"""
        cfg = ParseConfig(tolerant=False, game="Default")
        result = _resolve_parse_params(cfg, {"tolerant": True, "game": "Overridden"})
        assert result["tolerant"] is True
        assert result["game"] == "Overridden"

    def test_none_kwargs_not_override_config(self):
        """None 值的 kwargs 不应覆盖 config。"""
        cfg = ParseConfig(tolerant=False, game="Default")
        result = _resolve_parse_params(cfg, {"tolerant": None, "game": None})
        assert result["tolerant"] is False
        assert result["game"] == "Default"

    def test_mixed_config_and_explicit_warns(self):
        """config 和显式旧参数同时传入时应发出 DeprecationWarning。"""
        cfg = ParseConfig(tolerant=False)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _resolve_parse_params(cfg, {"tolerant": True})
            deprecation_warnings = [
                x for x in w if issubclass(x.category, DeprecationWarning)
            ]
            assert len(deprecation_warnings) == 1
            assert "tolerant" in str(deprecation_warnings[0].message)

    def test_no_config_returns_kwargs_unchanged(self):
        """未传 config 时，kwargs 原样返回。"""
        result = _resolve_parse_params(None, {"tolerant": True, "extra": 123})
        assert result == {"tolerant": True, "extra": 123}

    def test_non_config_kwargs_preserved(self):
        """kwargs 中不属于 config 的键（如 path、provider）应保留。"""
        cfg = ParseConfig(tolerant=False)
        result = _resolve_parse_params(cfg, {"tolerant": True, "path": "/test.uasset"})
        assert result["tolerant"] is True
        assert result["path"] == "/test.uasset"

    def test_config_all_none_fields_preserves_defaults(self):
        """config 中所有字段为 None 时，应保留 None。"""
        cfg = ParseConfig()
        result = _resolve_parse_params(cfg, {})
        assert result["game"] is None
        assert result["lightweight_threshold"] is None
        assert result["mappings_path"] is None

    def test_config_with_empty_kwargs_uses_all_config(self):
        """全部配置项通过 config 传入，空 kwargs。"""
        cfg = ParseConfig(
            tolerant=False,
            force_full_parse=True,
            hex_view=True,
            include_parent_assets=True,
            asset_roots=["/root1"],
            mappings_path="/path/to/usmap",
            game="Minecraft",
            lightweight_threshold=10,
        )
        result = _resolve_parse_params(cfg, {})
        assert result["tolerant"] is False
        assert result["force_full_parse"] is True
        assert result["hex_view"] is True
        assert result["include_parent_assets"] is True
        assert result["asset_roots"] == ["/root1"]
        assert result["mappings_path"] == "/path/to/usmap"
        assert result["game"] == "Minecraft"
        assert result["lightweight_threshold"] == 10

    def test_bool_false_from_function_signature_does_not_override_config(self):
        """函数签名的 False 默认值（通过 kwargs 传入）不应覆盖 config 的 True。

        模拟 parse_single → parse_package 调用链：
        parse_single(hex_view=None) → parse_package(hex_view=None) → _resolve_parse_params
        """
        cfg = ParseConfig(hex_view=True)
        # kwargs 中 hex_view=None 模拟 parse_package 的默认值
        result = _resolve_parse_params(cfg, {"hex_view": None})
        assert result["hex_view"] is True

    def test_explicit_false_overrides_config_true(self):
        """调用方显式传入 False 应覆盖 config 的 True。"""
        cfg = ParseConfig(hex_view=True)
        result = _resolve_parse_params(cfg, {"hex_view": False})
        assert result["hex_view"] is False

    def test_config_bool_fields_survive_full_chain(self):
        """所有 bool 类型的 config 字段在空 kwargs 下正确保留。"""
        cfg = ParseConfig(
            tolerant=False,
            force_full_parse=True,
            hex_view=True,
            include_parent_assets=True,
        )
        result = _resolve_parse_params(cfg, {})
        assert result["tolerant"] is False
        assert result["force_full_parse"] is True
        assert result["hex_view"] is True
        assert result["include_parent_assets"] is True

    def test_config_string_fields_survive_full_chain(self):
        """字符串类型 config 字段在空 kwargs 下正确保留。"""
        cfg = ParseConfig(game="Fortnite", mappings_path="/test.usmap")
        result = _resolve_parse_params(cfg, {})
        assert result["game"] == "Fortnite"
        assert result["mappings_path"] == "/test.usmap"


# ---------------------------------------------------------------------------
# parse_package() 调用链回归测试
# ---------------------------------------------------------------------------

class TestParsePackageConfigPropagation:
    """验证 parse_package() 正确将 config 值传递给 _parse_package_core()。"""

    @pytest.mark.skipif(not _has_sample, reason="测试样本不可用")
    def test_config_hex_view_reaches_core(self):
        """config 中 hex_view=True 应传递到 _parse_package_core()。"""
        cfg = ParseConfig(hex_view=True)
        with patch(
            "uasset_read.parse_uasset._parse_package_core"
        ) as mock_core:
            # _parse_package_core 被 mock，不会实际解析
            from uasset_read.models.result import ParseResult
            mock_core.side_effect = lambda path, result, **kw: setattr(
                result, "_received_kw", kw
            )
            result = parse_package(_SAMPLE_BLUEPRINT, config=cfg)
            # 验证 hex_view=True 传递到了 _parse_package_core
            call_kwargs = mock_core.call_args
            assert call_kwargs.kwargs.get("hex_view") is True

    @pytest.mark.skipif(not _has_sample, reason="测试样本不可用")
    def test_config_tolerant_reaches_core(self):
        """config 中 tolerant=False 应传递到 _parse_package_core()。"""
        cfg = ParseConfig(tolerant=False)
        with patch(
            "uasset_read.parse_uasset._parse_package_core"
        ) as mock_core:
            from uasset_read.models.result import ParseResult
            mock_core.side_effect = lambda path, result, **kw: setattr(
                result, "_received_kw", kw
            )
            result = parse_package(_SAMPLE_BLUEPRINT, config=cfg)
            call_kwargs = mock_core.call_args
            assert call_kwargs.kwargs.get("tolerant") is False

    @pytest.mark.skipif(not _has_sample, reason="测试样本不可用")
    def test_config_game_reaches_core(self):
        """config 中 game 值应传递到 _parse_package_core()。"""
        cfg = ParseConfig(game="TestGame")
        with patch(
            "uasset_read.parse_uasset._parse_package_core"
        ) as mock_core:
            from uasset_read.models.result import ParseResult
            mock_core.side_effect = lambda path, result, **kw: setattr(
                result, "_received_kw", kw
            )
            result = parse_package(_SAMPLE_BLUEPRINT, config=cfg)
            call_kwargs = mock_core.call_args
            assert call_kwargs.kwargs.get("game") == "TestGame"

    @pytest.mark.skipif(not _has_sample, reason="测试样本不可用")
    def test_no_config_old_params_still_work(self):
        """不传 config 时，旧风格参数仍正常工作（向后兼容）。"""
        with patch(
            "uasset_read.parse_uasset._parse_package_core"
        ) as mock_core:
            from uasset_read.models.result import ParseResult
            mock_core.side_effect = lambda path, result, **kw: setattr(
                result, "_received_kw", kw
            )
            result = parse_package(
                _SAMPLE_BLUEPRINT, tolerant=False, hex_view=True
            )
            call_kwargs = mock_core.call_args
            assert call_kwargs.kwargs.get("tolerant") is False
            assert call_kwargs.kwargs.get("hex_view") is True

    @pytest.mark.skipif(not _has_sample, reason="测试样本不可用")
    def test_mixed_config_and_old_params_warns(self):
        """同时传入 config 和旧参数时发出 DeprecationWarning。"""
        cfg = ParseConfig(hex_view=True)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            with patch(
                "uasset_read.parse_uasset._parse_package_core"
            ) as mock_core:
                from uasset_read.models.result import ParseResult
                mock_core.side_effect = lambda path, result, **kw: None
                # 旧参数 hex_view=False 与 config hex_view=True 冲突
                parse_package(
                    _SAMPLE_BLUEPRINT, hex_view=False, config=cfg
                )
            dep_warnings = [
                x for x in w if issubclass(x.category, DeprecationWarning)
            ]
            assert any("hex_view" in str(dw.message) for dw in dep_warnings)

    @pytest.mark.skipif(not _has_sample, reason="测试样本不可用")
    def test_explicit_none_does_not_trigger_deprecation(self):
        """显式传入 None 不应触发 DeprecationWarning（None 是函数签名默认值）。"""
        cfg = ParseConfig(hex_view=True)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            with patch(
                "uasset_read.parse_uasset._parse_package_core"
            ) as mock_core:
                from uasset_read.models.result import ParseResult
                mock_core.side_effect = lambda path, result, **kw: None
                parse_package(_SAMPLE_BLUEPRINT, hex_view=None, config=cfg)
            dep_warnings = [
                x for x in w if issubclass(x.category, DeprecationWarning)
            ]
            # 不应有关于 hex_view 的 deprecation warning
            assert not any(
                "hex_view" in str(dw.message) for dw in dep_warnings
            )


# ---------------------------------------------------------------------------
# parse_single() → parse_package() 调用链回归测试
# ---------------------------------------------------------------------------

class TestParseSingleConfigPropagation:
    """验证 parse_single() 正确将 parse_config 传递到 parse_package()。"""

    @pytest.mark.skipif(not _has_sample, reason="测试样本不可用")
    def test_parse_single_config_reaches_parse_package(self):
        """parse_single(parse_config=ParseConfig(hex_view=True), format='markdown')
        应将 config 传递到 parse_package()（非 linker 格式路径）。"""
        from uasset_read.core import parse_single

        cfg = ParseConfig(hex_view=True)
        captured_args = {}

        def capture_and_short_circuit(*args, **kwargs):
            captured_args.update(kwargs)
            # 返回一个不完整的 ParseResult，让 parse_single 后续步骤失败
            # 但我们只关心 parse_package 的调用参数
            from uasset_read.models.result import ParseResult
            r = ParseResult()
            r.is_success = False
            r.errors = ["test short-circuit"]
            return r

        with patch(
            "uasset_read.core.parse_package", side_effect=capture_and_short_circuit
        ):
            with pytest.raises(Exception):
                # format="markdown" 走 parse_package() 路径
                parse_single(
                    _SAMPLE_BLUEPRINT, format="markdown", parse_config=cfg
                )

        # parse_single 将 parse_config 作为 config 参数传递
        assert captured_args.get("config") is cfg
        # hex_view=None 由 parse_single 传入（函数签名默认值）
        assert "hex_view" in captured_args


# ---------------------------------------------------------------------------
# 真实样本 HexView 集成测试
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.regression
@pytest.mark.skipif(not _has_sample, reason="测试样本不可用")
class TestRealAssetHexViewIntegration:
    """验证 ParseConfig(hex_view=True) 能产生 HexView entries。"""

    def test_hex_view_entries_populated(self):
        """config=ParseConfig(hex_view=True) 应产生 hex_view_entries。"""
        cfg = ParseConfig(hex_view=True)
        result = parse_package(_SAMPLE_BLUEPRINT, config=cfg)
        assert result.is_success, f"解析失败: {result.errors}"
        assert len(result.hex_view_entries) > 0, (
            "hex_view_entries 为空 — config 的 hex_view=True 未到达 archive"
        )

    def test_hex_view_disabled_by_default(self):
        """不传 config 时不应产生 hex_view_entries。"""
        result = parse_package(_SAMPLE_BLUEPRINT)
        assert result.is_success, f"解析失败: {result.errors}"
        assert len(result.hex_view_entries) == 0


# ---------------------------------------------------------------------------
# FString 超长声明长度诊断增强测试 (#413)
# ---------------------------------------------------------------------------


# --- UTF-8 超长 ---

def test_fstring_utf8_exceeds_limit_tolerant_returns_empty():
    """UTF-8 FString 长度超过 MAX_FSTRING_LENGTH 时 tolerant 返回空字符串。"""
    # length=100_000_000 (远超 10MB 限制)
    length_val = 100_000_000
    data = struct.pack('<i', length_val)
    archive = ByteArchive(data, tolerant=True)

    result = archive.read_fstring()
    assert result == ""


def test_fstring_utf8_exceeds_limit_tolerant_records_diagnostic():
    """UTF-8 FString 超长时 tolerant 模式记录诊断信息。"""
    length_val = 100_000_000
    data = struct.pack('<i', length_val)
    archive = ByteArchive(data, tolerant=True)

    archive.read_fstring()

    diags = archive.get_diagnostics()
    assert len(diags) == 1
    d = diags[0]
    assert d.module == "archive"
    assert d.field == "fstring"
    assert d.source == "read_fstring"
    assert d.target_offset == 0  # pos_before
    assert d.read_size == length_val
    assert "exceeds MAX_FSTRING_LENGTH" in d.error


def test_fstring_utf8_exceeds_limit_strict_raises():
    """UTF-8 FString 长度超过 MAX_FSTRING_LENGTH 时 strict 抛出 ParseError。"""
    length_val = 100_000_000
    data = struct.pack('<i', length_val)
    archive = ByteArchive(data, tolerant=False)

    with pytest.raises(ParseError, match="exceeds"):
        archive.read_fstring()


# --- UTF-16 超长 ---

def test_fstring_utf16_exceeds_limit_tolerant_returns_empty():
    """UTF-16 FString 长度超过 MAX_FSTRING_LENGTH 时 tolerant 返回空字符串。"""
    # length=-50_000_000 → utf16_len = 100_000_000
    length_val = -50_000_000
    data = struct.pack('<i', length_val)
    archive = ByteArchive(data, tolerant=True)

    result = archive.read_fstring()
    assert result == ""


def test_fstring_utf16_exceeds_limit_tolerant_records_diagnostic():
    """UTF-16 FString 超长时 tolerant 模式记录诊断信息。"""
    length_val = -50_000_000
    data = struct.pack('<i', length_val)
    archive = ByteArchive(data, tolerant=True)

    archive.read_fstring()

    diags = archive.get_diagnostics()
    assert len(diags) == 1
    d = diags[0]
    assert d.module == "archive"
    assert d.field == "fstring"
    assert d.source == "read_fstring"
    assert d.target_offset == 0
    assert d.read_size == 100_000_000  # utf16_len = -length * 2
    assert "exceeds MAX_FSTRING_LENGTH" in d.error


def test_fstring_utf16_exceeds_limit_strict_raises():
    """UTF-16 FString 长度超过 MAX_FSTRING_LENGTH 时 strict 抛出 ParseError。"""
    length_val = -50_000_000
    data = struct.pack('<i', length_val)
    archive = ByteArchive(data, tolerant=False)

    with pytest.raises(ParseError, match="exceeds"):
        archive.read_fstring()


# --- 边界条件 ---

def test_fstring_exactly_at_limit_succeeds():
    """长度恰好等于 MAX_FSTRING_LENGTH 时应正常读取（不触发超长检测）。"""
    # 构造长度恰好等于 MAX_FSTRING_LENGTH 的 UTF-8 FString
    # 需要提供足够的数据
    length_val = MAX_FSTRING_LENGTH
    data = struct.pack('<i', length_val) + b'\x00' * length_val
    archive = ByteArchive(data, tolerant=True)

    result = archive.read_fstring()
    assert result == ""  # 全 null 数据


def test_fstring_just_above_limit_tolerant():
    """长度刚好超过 MAX_FSTRING_LENGTH 时 tolerant 返回空字符串。"""
    length_val = MAX_FSTRING_LENGTH + 1
    data = struct.pack('<i', length_val)
    archive = ByteArchive(data, tolerant=True)

    result = archive.read_fstring()
    assert result == ""

    diags = archive.get_diagnostics()
    assert len(diags) == 1
    assert diags[0].read_size == length_val


def test_fstring_negative_just_above_limit_tolerant():
    """UTF-16 长度刚好超过 MAX_FSTRING_LENGTH 时 tolerant 返回空字符串。"""
    # utf16_len = MAX_FSTRING_LENGTH + 2 → -length = (MAX_FSTRING_LENGTH + 2) / 2
    utf16_len = MAX_FSTRING_LENGTH + 2
    length_val = -(utf16_len // 2)
    data = struct.pack('<i', length_val)
    archive = ByteArchive(data, tolerant=True)

    result = archive.read_fstring()
    assert result == ""

    diags = archive.get_diagnostics()
    assert len(diags) == 1
    assert diags[0].read_size == utf16_len


# --- 异常值（来自 issue #413 的实际案例）---

def test_fstring_issue413_value_956301312():
    """Issue #413: 长度值 956301312 超过限制，tolerant 应返回空字符串。"""
    data = struct.pack('<i', 956301312)
    archive = ByteArchive(data, tolerant=True)

    result = archive.read_fstring()
    assert result == ""

    diags = archive.get_diagnostics()
    assert len(diags) == 1
    assert diags[0].read_size == 956301312


def test_fstring_issue413_value_419430400():
    """Issue #413: 长度值 419430400 超过限制，tolerant 应返回空字符串。"""
    data = struct.pack('<i', 419430400)
    archive = ByteArchive(data, tolerant=True)

    result = archive.read_fstring()
    assert result == ""

    diags = archive.get_diagnostics()
    assert len(diags) == 1
    assert diags[0].read_size == 419430400


# --- FString 全空损坏检测 (#330) ---

def test_fstring_all_nulls_utf8_tolerant():
    """UTF-8 FString 全空在 tolerant 模式应返回空字符串。"""
    # length=5 (u32 LE), 5 个 null 字节
    data = b'\x05\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=True)

    result = archive.read_fstring()
    assert result == ""


def test_fstring_all_nulls_utf16_tolerant():
    """UTF-16 FString 全空在 tolerant 模式应返回空字符串。"""
    # length=-3 (i32 LE) → utf16_len=6, 6 个 null 字节
    data = b'\xfd\xff\xff\xff\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=True)

    result = archive.read_fstring()
    assert result == ""


def test_fstring_all_nulls_utf8_strict():
    """UTF-8 FString 全空在 strict 模式应抛出 ParseError。"""
    data = b'\x05\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=False)

    with pytest.raises(ParseError):
        archive.read_fstring()


def test_fstring_all_nulls_utf16_strict():
    """UTF-16 FString 全空在 strict 模式应抛出 ParseError。"""
    data = b'\xfd\xff\xff\xff\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=False)

    with pytest.raises(ParseError):
        archive.read_fstring()


# --- FText args 数量限制 ---

def test_ftext_named_format_arg_overflow():
    """FText NamedFormat arg_count 超限时应容错而非崩溃。"""
    from uasset_read.constants import MAX_SAFE_COUNT

    # 构造一个畸形的 FText 数据
    # format_text 是一个完整的 FText（history_type = -1, None）
    # history_type = 1 (NamedFormat)
    # arg_count = MAX_SAFE_COUNT + 1 (超限)
    data = b'\x00\x00\x00\x00'  # format_text 的 flags
    data += b'\xFF'  # format_text 的 history_type = -1 (None)
    data += b'\x00\x00\x00\x00'  # format_text 的 bHasCultureInvariantString = False
    data += (MAX_SAFE_COUNT + 1).to_bytes(4, 'little', signed=True)  # arg_count

    archive = ByteArchive(data, tolerant=True)

    # 在 tolerant 模式下应返回空字符串而非崩溃
    value, consumed = read_ftext_with_history(archive, history_type=1, tolerant=True)
    assert isinstance(value, str)


def test_ftext_named_format_negative_arg_count():
    """FText NamedFormat 负 arg_count 应容错而非崩溃。"""
    # 构造一个畸形的 FText 数据
    # format_text 是一个完整的 FText（history_type = -1, None）
    # history_type = 1 (NamedFormat)
    # arg_count = -1 (负数)
    data = b'\x00\x00\x00\x00'  # format_text 的 flags
    data += b'\xFF'  # format_text 的 history_type = -1 (None)
    data += b'\x00\x00\x00\x00'  # format_text 的 bHasCultureInvariantString = False
    data += (-1).to_bytes(4, 'little', signed=True)  # -1

    archive = ByteArchive(data, tolerant=True)

    # 在 tolerant 模式下应返回空字符串而非崩溃
    value, consumed = read_ftext_with_history(archive, history_type=1, tolerant=True)
    assert isinstance(value, str)


# --- FTEXT-SAFETY 恢复位置 ---

def test_ftext_safety_recovery_position():
    """FTEXT-SAFETY 消耗超限时应回退到字段起始位置。"""
    from uasset_read.serializers.graph_pin import _read_pin_ftext_field
    from uasset_read.constants import MAX_FTEXT_CONSUMPTION

    mock_archive = MagicMock()
    # tell() 首次返回 0（字段起始），_read_ftext_value 后返回超限值
    mock_archive.tell.side_effect = [0, MAX_FTEXT_CONSUMPTION + 100]

    # 模拟一个消耗大量字节的 FText
    def mock_read_ftext_value(archive, tolerant=True):
        return ("value", 0, 0, MAX_FTEXT_CONSUMPTION + 100)

    with patch('uasset_read.serializers.graph_pin._read_ftext_value', mock_read_ftext_value):
        trace_fields = {}
        value, success = _read_pin_ftext_field(
            mock_archive, "TestField", False, trace_fields
        )

        # 应回退到 _start（字段起始位置），而非 _start + 5
        # 验证 seek 被调用且参数为 0（_start）
        mock_archive.seek.assert_called_with(0)


# ===========================================================================
# StructProperty Transform 解析测试 (#329) + SerializationControlExtensions (#339)
# ===========================================================================


def test_transform_size_f32():
    """FTransform3f 大小应为 40 字节。"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("Transform") == 40


def test_transform_size_lwc():
    """Transform LWC 映射应为 (40, 80)。"""
    from uasset_read.parsers.property_types import _LWC_TYPE_MAP
    assert _LWC_TYPE_MAP.get("Transform") == (40, 80)


def test_transform3f_size():
    """Transform3f 紧凑格式大小应为 40 字节。"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("Transform3f") == 40


def test_transform_read_f32():
    """FTransform3f 应正确读取 40 字节。"""
    from uasset_read.parsers.property_types import _try_fast_path_struct

    data = struct.pack('<10f',
        0.0, 0.0, 0.0, 1.0,
        100.0, 200.0, 300.0,
        1.0, 1.0, 1.0
    )
    archive = ByteArchive(data)

    tag = MagicMock()
    tag.size = 40
    tag.struct_type = "Transform"

    result = _try_fast_path_struct("Transform", tag, archive, name_map=[])

    assert result is not None
    assert result.struct_type == "Transform"
    assert result.fields["Translation"]["X"] == 100.0
    assert result.fields["Translation"]["Y"] == 200.0
    assert result.fields["Translation"]["Z"] == 300.0
    assert result.fields["Rotation"]["W"] == 1.0
    assert result.fields["Scale3D"]["X"] == 1.0
    assert result.fields["Scale3D"]["Y"] == 1.0
    assert result.fields["Scale3D"]["Z"] == 1.0


def test_transform_read_f64():
    """FTransform3d 应正确读取 80 字节。"""
    from uasset_read.parsers.property_types import _try_fast_path_struct

    data = struct.pack('<10d',
        0.0, 0.0, 0.0, 1.0,
        100.0, 200.0, 300.0,
        1.0, 1.0, 1.0
    )
    archive = ByteArchive(data)

    tag = MagicMock()
    tag.size = 80
    tag.struct_type = "Transform"

    result = _try_fast_path_struct("Transform", tag, archive, name_map=[])

    assert result is not None
    assert result.struct_type == "Transform"
    assert result.fields["Translation"]["X"] == 100.0
    assert result.fields["Translation"]["Y"] == 200.0
    assert result.fields["Translation"]["Z"] == 300.0
    assert result.fields["Rotation"]["W"] == 1.0
    assert result.fields["Scale3D"]["X"] == 1.0
    assert result.fields["Scale3D"]["Y"] == 1.0
    assert result.fields["Scale3D"]["Z"] == 1.0


def test_transform_read_unexpected_size():
    """非标准大小的 Transform 在 tolerant 模式下应跳过并返回警告。"""
    from uasset_read.parsers.property_types import _try_fast_path_struct

    data = struct.pack('<10f',
        1.0, 2.0, 3.0, 4.0,
        10.0, 20.0, 30.0,
        100.0, 200.0, 300.0
    )
    archive = ByteArchive(data, tolerant=True)

    tag = MagicMock()
    tag.size = 52
    tag.struct_type = "Transform"

    result = _try_fast_path_struct("Transform", tag, archive, name_map=[])
    assert result is not None
    assert result.struct_type == "Transform"
    assert "_warning" in result.fields
    assert "52" in result.fields["_warning"]


def test_transform_read_unexpected_size_strict():
    """非标准大小的 Transform 在 strict 模式下应抛出 ParseError。"""
    from uasset_read.parsers.property_types import _try_fast_path_struct

    data = struct.pack('<10f',
        1.0, 2.0, 3.0, 4.0,
        10.0, 20.0, 30.0,
        100.0, 200.0, 300.0
    )
    archive = ByteArchive(data)
    archive._tolerant = False

    tag = MagicMock()
    tag.size = 52
    tag.struct_type = "Transform"

    with pytest.raises(ParseError, match="unexpected size 52"):
        _try_fast_path_struct("Transform", tag, archive, name_map=[])


def test_transform_serialization_order():
    """验证 Transform 序列化顺序：Rotation -> Translation -> Scale3D。"""
    from uasset_read.parsers.property_types import _try_fast_path_struct

    data = struct.pack('<10f',
        1.0, 2.0, 3.0, 4.0,
        10.0, 20.0, 30.0,
        100.0, 200.0, 300.0
    )
    archive = ByteArchive(data)

    tag = MagicMock()
    tag.size = 40
    tag.struct_type = "Transform"

    result = _try_fast_path_struct("Transform", tag, archive, name_map=[])

    assert result.fields["Rotation"]["X"] == 1.0
    assert result.fields["Rotation"]["W"] == 4.0
    assert result.fields["Translation"]["X"] == 10.0
    assert result.fields["Translation"]["Z"] == 30.0
    assert result.fields["Scale3D"]["X"] == 100.0
    assert result.fields["Scale3D"]["Z"] == 300.0


# --- SerializationControlExtensions 未知位处理测试 (#339) ---


def _make_archive_for_sc(control_byte: int, tell_first: int = 0, tell_loop: int = 200):
    """构造模拟 archive，控制 SerializationControlExtensions 和属性循环。"""
    archive = MagicMock()
    archive.read_u8.return_value = control_byte
    archive.tell.side_effect = [tell_first] + [tell_loop] * 20
    archive._file_size = tell_loop
    archive._tolerant = True
    return archive


def _make_export(transforms=None):
    """构造模拟 export。"""
    export = MagicMock()
    export.serial_offset = 0
    export.serial_size = 100
    export.object_name = "TestExport"
    export.transforms = transforms if transforms is not None else {}
    return export


def _make_summary():
    """构造模拟 summary。"""
    summary = MagicMock()
    summary.file_version_ue5 = UE5_PROPERTY_TAG_EXTENSION
    summary.package_flags = 0
    return summary


def test_serialization_control_unknown_bits():
    """SerializationControlExtensions 未知位应被记录但不影响解析。"""
    control_byte = 0xB8

    archive = _make_archive_for_sc(control_byte)
    summary = _make_summary()
    export = _make_export()

    _result = parse_properties_from_export(
        export, archive, summary, [], [], tolerant=True
    )

    assert "serialization_control" in export.transforms
    assert export.transforms["serialization_control"]["value"] == control_byte


def test_serialization_control_diagnostic_recorded():
    """未知位应在 archive 上记录诊断信息。"""
    control_byte = 0x04

    archive = _make_archive_for_sc(control_byte, tell_first=42)
    summary = _make_summary()
    export = _make_export()

    parse_properties_from_export(
        export, archive, summary, [], [], tolerant=True
    )

    archive._record_diagnostic.assert_called_once()
    call_kwargs = archive._record_diagnostic.call_args[1]
    assert call_kwargs["module"] == "property_parser"
    assert call_kwargs["field"] == "serialization_control"
    assert "0x04" in call_kwargs["error"]


def test_serialization_control_bit_names_in_diagnostic():
    """多个未知位应有对应的位名诊断。"""
    control_byte = 0x18

    archive = _make_archive_for_sc(control_byte, tell_first=10)
    summary = _make_summary()
    export = _make_export()

    parse_properties_from_export(
        export, archive, summary, [], [], tolerant=True
    )

    archive._record_diagnostic.assert_called_once()
    error_msg = archive._record_diagnostic.call_args[1]["error"]
    assert "Unknown_Bit3" in error_msg
    assert "Unknown_Bit4" in error_msg


def test_serialization_control_no_unknown_bits():
    """已知位 0x01|0x02 不应记录诊断。"""
    control_byte = 0x03

    archive = _make_archive_for_sc(control_byte)
    summary = _make_summary()
    export = _make_export()

    parse_properties_from_export(
        export, archive, summary, [], [], tolerant=True
    )

    archive._record_diagnostic.assert_not_called()

    assert "serialization_control" in export.transforms
    sc = export.transforms["serialization_control"]
    assert sc["value"] == 0x03
    assert sc["unknown_bits"] == 0


def test_serialization_control_transforms_fields():
    """transforms 中应包含 value, overridden_operation, unknown_bits, offset。"""
    control_byte = 0x02
    overridden_byte = 0x01

    archive = MagicMock()
    archive.read_u8.side_effect = [control_byte, overridden_byte]
    archive.tell.side_effect = [5, 200, 200, 200, 200]
    archive._file_size = 200
    archive._tolerant = True

    summary = _make_summary()
    export = _make_export()

    parse_properties_from_export(
        export, archive, summary, [], [], tolerant=True
    )

    sc = export.transforms["serialization_control"]
    assert sc["value"] == 0x02
    assert sc["overridden_operation"] == 0x01
    assert sc["unknown_bits"] == 0
    assert sc["offset"] == 5


# --- 测试 _TYPE_HANDLER_MAP 缓存机制（parsers/property_parser.py） ---


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
