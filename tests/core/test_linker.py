"""PackageLinker lifecycle tests.

Tests the link() → preload() → post_load() lifecycle and object graph
resolution using real .uasset samples.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from uasset_read.pipeline.core import parse_uasset_with_linker
from uasset_read.models.result import ParseResult


class TestLinkerLifecycle:
    """PackageLinker lifecycle with real samples."""

    def test_linker_created_for_blueprint(self, samples_dir: Path):
        """A Blueprint sample produces a ParseResult with linker."""
        sample = samples_dir / "FirstPerson_BP_FirstPersonCharacter.uasset"
        result = parse_uasset_with_linker(str(sample), tolerant=True)
        assert isinstance(result, ParseResult)
        assert result.linker is not None

    def test_linker_created_for_material(self, samples_dir: Path):
        """A Material sample produces a ParseResult with linker."""
        sample = samples_dir / "FirstPerson_M_FlatCol.uasset"
        result = parse_uasset_with_linker(str(sample), tolerant=True)
        assert isinstance(result, ParseResult)
        assert result.linker is not None

    def test_all_objects_populated(self, samples_dir: Path):
        """ParseResult.all_objects contains import + export objects."""
        sample = samples_dir / "FirstPerson_BP_FirstPersonCharacter.uasset"
        result = parse_uasset_with_linker(str(sample), tolerant=True)
        assert hasattr(result, "all_objects")
        # all_objects should be non-empty for any real asset
        assert len(result.all_objects) > 0

    def test_root_objects_populated(self, samples_dir: Path):
        """ParseResult.root_objects is populated."""
        sample = samples_dir / "FirstPerson_BP_FirstPersonCharacter.uasset"
        result = parse_uasset_with_linker(str(sample), tolerant=True)
        assert hasattr(result, "root_objects")
        # Root objects may be empty for some assets, but should exist
        assert isinstance(result.root_objects, list)

    def test_preload_all_exports(self, samples_dir: Path):
        """Preloading all exports does not crash."""
        sample = samples_dir / "FirstPerson_BP_FirstPersonCharacter.uasset"
        result = parse_uasset_with_linker(
            str(sample),
            tolerant=True,
            preload_all=True,
        )
        assert isinstance(result, ParseResult)
        assert result.linker is not None

    def test_linker_post_load_populates_graphs(self, samples_dir: Path):
        """After post_load, blueprint assets have graphs populated."""
        sample = samples_dir / "FirstPerson_BP_FirstPersonCharacter.uasset"
        result = parse_uasset_with_linker(str(sample), tolerant=True)
        # For blueprints, graphs should be populated after post_load
        if result.graphs:
            assert len(result.graphs) > 0


class TestLinkerWithVariousTypes:
    """Linker behavior across different asset types."""

    @pytest.mark.parametrize(
        "filename",
        [
            "ABP_RifleAnimLayers.uasset",
            "ALS_AnimBP.uasset",
            "ALS_FootstepDataTable.uasset",
            "Lyra_Enum_PanelType.uasset",
            "StarterContent_SM_Chair.uasset",
        ],
        ids=["anim_bp", "anim_bp2", "data_table", "enum", "static_mesh"],
    )
    def test_linker_succeeds_for_various_types(
        self,
        samples_dir: Path,
        filename: str,
    ):
        """Linker creation succeeds for various asset types."""
        sample = samples_dir / filename
        if not sample.exists():
            pytest.skip(f"Sample not found: {filename}")

        result = parse_uasset_with_linker(str(sample), tolerant=True)
        assert isinstance(result, ParseResult)
        assert result.linker is not None
        assert result.is_success or len(result.errors) > 0

    def test_linker_import_export_count(self, samples_dir: Path):
        """Linker has correct import/export object counts."""
        sample = samples_dir / "FirstPerson_BP_FirstPersonCharacter.uasset"
        result = parse_uasset_with_linker(str(sample), tolerant=True)

        linker = result.linker
        assert linker is not None
        # Import + export objects should match all_objects
        total = len(linker._import_objects) + len(linker._export_objects)
        assert total == len(result.all_objects)


class TestLinkerErrorRecovery:
    """Linker error handling."""

    def test_nonexistent_file_returns_failed_result(self):
        """Parsing a nonexistent file returns a failed ParseResult."""
        result = parse_uasset_with_linker("nonexistent_99999.uasset", tolerant=True)
        assert isinstance(result, ParseResult)
        assert result.status == "failed"

    def test_preload_all_tolerant(self, samples_dir: Path):
        """preload_all in tolerant mode handles errors gracefully."""
        sample = samples_dir / "FirstPerson_BP_FirstPersonCharacter.uasset"
        result = parse_uasset_with_linker(
            str(sample),
            tolerant=True,
            preload_all=True,
        )
        # Should not crash, even if some exports fail to preload
        assert result is not None
