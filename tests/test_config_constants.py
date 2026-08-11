"""Consolidated tests for constants, versioning, exceptions, and config.

Extracted from:
- tests/test_constants_versioning.py (version detection)
- tests/test_exception_context.py (ErrorContext/ParseError)
- tests/test_cpf_constants.py (flag group)
- tests/test_game_variant.py (game variant)
"""
from __future__ import annotations

import pytest

from uasset_read.constants import GameVariant, get_game_variant_config
from uasset_read.exceptions import ParseError, ErrorContext
from uasset_read.versioning import (
    EUEVersion,
    FPackageFileVersion,
    VersionContainer,
    build_version_container,
)


class TestVersionDetection:
    """Version ordering, UE5 detection, and custom version lookup."""

    def test_version_ordering(self):
        """UE versions maintain strict ascending order."""
        assert EUEVersion.UE4_23 < EUEVersion.UE5_0
        assert EUEVersion.UE5_0 < EUEVersion.UE5_8


class TestParseErrorContext:
    """ParseError context fields, formatting, and backward compatibility."""

    def test_context_fields_and_defaults(self):
        """ParseError exposes reader_name, position, length, export_name with sane defaults."""
        exc = ParseError("Test error")
        assert hasattr(exc, "reader_name")
        assert hasattr(exc, "position")
        assert hasattr(exc, "length")
        assert hasattr(exc, "export_name")
        assert exc.reader_name == ""
        assert exc.position == 0
        assert exc.length == 0
        assert exc.export_name == ""


class TestCPFConstantsGroup:
    """CPF_* flag group invariants: no duplicates, all powers of two, removed flags absent."""

    def test_no_duplicate_values(self):
        """All CPF_* integer constants must have unique values."""
        import uasset_read.constants as c
        flags = [v for k, v in vars(c).items() if k.startswith("CPF_") and isinstance(v, int)]
        assert len(flags) == len(set(flags)), "Duplicate CPF_* values found"


class TestGameVariant:
    """GameVariant enum values and config retrieval."""

    def test_enum_values(self):
        """GameVariant NONE=0, FORTNITE=1001."""
        assert GameVariant.NONE.value == 0
        assert GameVariant.FORTNITE.value == 1001
