# tests/semantic/test_canonical.py
"""Tests for canonical key ordering."""
from uasset_read.semantic.canonical import canonical_sort


class TestCanonicalSort:
    def test_empty_dict(self):
        assert canonical_sort({}) == {}

    def test_top_level_key_order(self):
        data = {"diagnostics": [], "asset": {}, "content": {}, "references": [], "coverage": {}, "format": "x", "format_version": "1", "mode": "standard"}
        result = canonical_sort(data)
        keys = list(result.keys())
        # Public contract order: format, format_version, mode, asset, references, content, coverage, diagnostics
        assert keys[0] == "format"
        assert keys[1] == "format_version"
        assert keys[2] == "mode"
        assert keys[3] == "asset"
        assert keys[4] == "references"
        assert keys[5] == "content"
        assert keys[6] == "coverage"
        assert keys[7] == "diagnostics"

    def test_nested_sort(self):
        data = {"asset": {"object_name": "X", "kind": "resource", "class_name": "T"}}
        result = canonical_sort(data)
        asset_keys = list(result["asset"].keys())
        assert asset_keys == ["class_name", "kind", "object_name"]

    def test_deterministic(self):
        data = {"b": 1, "a": 2, "c": 3}
        r1 = canonical_sort(data)
        r2 = canonical_sort(data)
        assert list(r1.keys()) == list(r2.keys())

    def test_preserves_values(self):
        data = {"z": [3, 1, 2], "a": {"nested": True}}
        result = canonical_sort(data)
        assert result["z"] == [3, 1, 2]
        assert result["a"] == {"nested": True}
