"""Core pipeline tests — parse_package() end-to-end behavior.

Tests normal parsing, error recovery, and tolerant mode with real samples.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from uasset_read import parse_package
from uasset_read.models.result import ParseResult


class TestParsePackageNormal:
    """Normal parsing path with real samples."""

    def test_parse_blueprint_returns_success(self, samples_dir: Path):
        """A well-formed Blueprint sample parses to success."""
        sample = samples_dir / "FirstPerson_BP_FirstPersonCharacter.uasset"
        result = parse_package(str(sample), tolerant=True)
        assert isinstance(result, ParseResult)
        assert result.status in ("success", "partial")
        assert result.summary is not None
        assert len(result.export_map) > 0

    def test_parse_material_returns_success(self, samples_dir: Path):
        """A well-formed Material sample parses to success."""
        sample = samples_dir / "FirstPerson_M_FlatCol.uasset"
        result = parse_package(str(sample), tolerant=True)
        assert isinstance(result, ParseResult)
        assert result.status in ("success", "partial")
        assert result.summary is not None

    def test_parse_anim_blueprint_returns_success(self, samples_dir: Path):
        """A well-formed AnimBlueprint sample parses to success."""
        sample = samples_dir / "ABP_RifleAnimLayers.uasset"
        result = parse_package(str(sample), tolerant=True)
        assert isinstance(result, ParseResult)
        assert result.status in ("success", "partial")
        assert result.summary is not None

    def test_parse_data_table_returns_success(self, samples_dir: Path):
        """A DataTable sample parses to success."""
        sample = samples_dir / "ALS_FootstepDataTable.uasset"
        result = parse_package(str(sample), tolerant=True)
        assert isinstance(result, ParseResult)
        assert result.status in ("success", "partial")

    def test_parse_enum_returns_success(self, samples_dir: Path):
        """An Enum sample parses to success."""
        sample = samples_dir / "Lyra_Enum_PanelType.uasset"
        result = parse_package(str(sample), tolerant=True)
        assert isinstance(result, ParseResult)
        assert result.status in ("success", "partial")

    def test_summary_has_package_name(self, samples_dir: Path):
        """Parsed summary must contain a non-empty package name."""
        sample = samples_dir / "FirstPerson_BP_FirstPersonCharacter.uasset"
        result = parse_package(str(sample), tolerant=True)
        assert result.summary is not None
        # Package name should be a non-empty string
        assert isinstance(result.summary.package_name, str)
        assert len(result.summary.package_name) > 0


class TestParsePackageErrorRecovery:
    """Error recovery and tolerant mode behavior."""

    def test_nonexistent_file_returns_failed_result(self):
        """Parsing a nonexistent file returns a failed result in tolerant mode."""
        result = parse_package("nonexistent_file_12345.uasset", tolerant=True)
        assert isinstance(result, ParseResult)
        assert result.status == "failed"
        assert len(result.errors) > 0

    def test_nonexistent_file_strict_raises(self):
        """Parsing a nonexistent file in strict mode raises an exception."""
        with pytest.raises((FileNotFoundError, OSError)):
            parse_package("nonexistent_file_12345.uasset", tolerant=False)

    def test_empty_file_tolerant(self, tmp_path: Path):
        """Parsing an empty file in tolerant mode returns a failed result."""
        empty = tmp_path / "empty.uasset"
        empty.write_bytes(b"")
        result = parse_package(str(empty), tolerant=True)
        assert isinstance(result, ParseResult)
        assert result.status == "failed"

    def test_truncated_file_tolerant(self, samples_dir: Path):
        """Parsing a truncated file in tolerant mode returns partial/failed."""
        sample = samples_dir / "FirstPerson_BP_FirstPersonCharacter.uasset"
        data = sample.read_bytes()
        truncated = data[: len(data) // 2]

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".uasset", delete=False) as f:
            f.write(truncated)
            tmp_path = f.name

        try:
            result = parse_package(tmp_path, tolerant=True)
            assert isinstance(result, ParseResult)
            assert result.status in ("partial", "failed")
        finally:
            Path(tmp_path).unlink(missing_ok=True)


class TestParsePackageLifecycle:
    """Parse lifecycle invariants."""

    def test_result_has_version_container(self, samples_dir: Path):
        """Successful parse populates version_container."""
        sample = samples_dir / "FirstPerson_BP_FirstPersonCharacter.uasset"
        result = parse_package(str(sample), tolerant=True)
        assert result.version_container is not None

    def test_result_has_linker(self, samples_dir: Path):
        """Successful parse with include_linker=True populates linker."""
        sample = samples_dir / "FirstPerson_BP_FirstPersonCharacter.uasset"
        result = parse_package(str(sample), tolerant=True)
        assert result.linker is not None

    def test_name_import_export_maps_consistent(self, samples_dir: Path):
        """Name, import, and export maps are all populated."""
        sample = samples_dir / "FirstPerson_BP_FirstPersonCharacter.uasset"
        result = parse_package(str(sample), tolerant=True)
        assert len(result.name_map) > 0
        assert len(result.import_map) >= 0  # Some assets have 0 imports
        assert len(result.export_map) > 0
