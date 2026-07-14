"""ParseConfig 参数合并测试 — 确保 config 值不被函数签名默认值覆盖。

测试 _resolve_parse_params() 与 parse_package() / parse_single() 的合并行为。
"""

import warnings

import pytest

from uasset_read.config import ParseConfig
from uasset_read.parse_uasset import _resolve_parse_params


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
