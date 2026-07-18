"""ParseConfig 参数合并测试 — 确保 config 值不被函数签名默认值覆盖。

测试 _resolve_parse_params() 与 parse_package() / parse_single() 的合并行为。
"""

import os
import warnings
from pathlib import Path
from unittest.mock import patch

import pytest

from uasset_read.config import ParseConfig
from uasset_read.parse_uasset import _resolve_parse_params, parse_package

# 测试样本路径
_SAMPLES_DIR = Path(__file__).parent.parent / "samples"
_SAMPLE_BLUEPRINT = str(_SAMPLES_DIR / "FirstPerson_BP_FirstPersonGameMode.uasset")
_has_sample = os.path.isfile(_SAMPLE_BLUEPRINT)


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
