"""Tests for LinkerParseResult dataclass."""

import pytest
from uasset_read.link.result import LinkerParseResult


class TestLinkerParseResult:
    """LinkerParseResult structure tests."""

    def test_default_values(self):
        """All fields have correct defaults."""
        r = LinkerParseResult()
        assert r.is_success is False
        assert r.errors == []
        assert r.root_objects == []
        assert r.all_objects == []
        assert r.name_map == []
        assert r.import_map == []
        assert r.export_map == []
        assert r.linker is None
        assert r.summary is None
        assert r.mmap_used is False
        assert r.mmap_warning is None

    def test_success_flag(self):
        """is_success can be set to True."""
        r = LinkerParseResult(is_success=True)
        assert r.is_success is True

    def test_errors_append(self):
        """Errors can be appended as a list."""
        r = LinkerParseResult()
        r.errors.append("test error")
        assert r.errors == ["test error"]

    def test_all_fields_exist(self):
        """All expected fields exist on the dataclass."""
        r = LinkerParseResult()
        expected = [
            "summary", "name_map", "import_map", "export_map",
            "linker", "root_objects", "all_objects", "errors",
            "is_success", "mmap_used", "mmap_warning",
        ]
        for field_name in expected:
            assert hasattr(r, field_name)
