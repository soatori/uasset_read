"""Tests for Task 6: Unified status model success|partial|failed."""
import pytest
from pathlib import Path
from uasset_read.parse_uasset import parse_uasset


# Sample assets
STATIC_MESH = Path("E:/Develop/lib/UnrealEngine/Samples/StarterContent/Content/StarterContent/Architecture/SM_AssetPlatform.uasset")
BLUEPRINT = Path("E:/Develop/lib/UnrealEngine/Samples/CiciToonCharacterShaderPa/Content/CiciToonCharacterShaderPak/Blueprints/Pawn/BP_Character.uasset")


class TestUnifiedStatusModel:
    """Test unified status model: success|partial|failed."""

    @pytest.mark.skipif(not BLUEPRINT.exists(), reason="Blueprint sample not found")
    def test_status_is_success_partial_or_failed(self):
        """Status should be one of: success, partial, failed."""
        result = parse_uasset(str(BLUEPRINT))

        assert result.status in ('success', 'partial', 'failed'), \
            f"Status should be success|partial|failed, not {result.status}"

    @pytest.mark.skipif(not STATIC_MESH.exists(), reason="StaticMesh sample not found")
    def test_opaque_export_makes_status_partial(self):
        """If any export is opaque, overall status should be partial."""
        result = parse_uasset(str(STATIC_MESH))

        # Check if any export is opaque/partial/skipped
        has_non_success = any(
            getattr(e, 'parse_status', 'success') in ('opaque', 'partial', 'skipped', 'metadata')
            for e in result.export_map
        )

        if has_non_success:
            assert result.status == 'partial', \
                f"Status should be partial when exports are opaque, not {result.status}"

    @pytest.mark.skipif(not BLUEPRINT.exists(), reason="Blueprint sample not found")
    def test_errors_make_status_partial_or_failed(self):
        """If there are errors, status should be partial (with data) or failed (no data)."""
        result = parse_uasset(str(BLUEPRINT))

        if result.errors:
            # Should be partial (if we have some data) or failed (if no data)
            assert result.status in ('partial', 'failed'), \
                f"Status should be partial/failed when errors exist, not {result.status}"

            # If we have summary/name_map/export_map, should be partial not failed
            if result.summary and result.name_map and result.export_map:
                assert result.status == 'partial', \
                    "Should be partial (not failed) when we have core data"

    @pytest.mark.skipif(not BLUEPRINT.exists(), reason="Blueprint sample not found")
    def test_no_errors_and_all_success_exports(self):
        """No errors + all exports success + not lightweight → status is success."""
        result = parse_uasset(str(BLUEPRINT))

        # Check if all exports are success
        all_success = all(
            getattr(e, 'parse_status', 'success') == 'success'
            for e in result.export_map
        )

        # Lightweight parse is also partial
        is_lightweight = result.metadata.get('lightweight_tolerant_parse', False)

        if not result.errors and all_success and not is_lightweight:
            assert result.status == 'success', \
                f"Status should be success when no errors and all exports success"


class TestStatusModelUnitTests:
    """Unit tests for status model logic."""

    def test_empty_result_is_failed(self):
        """ParseResult with no data should be failed."""
        from uasset_read.models.result import ParseResult
        result = ParseResult()
        assert result.status == "failed"

    def test_result_with_summary_is_not_failed(self):
        """ParseResult with summary should not be failed."""
        from uasset_read.models.result import ParseResult
        result = ParseResult()
        result.summary = object()  # Mock summary
        assert result.status != "failed"

    def test_result_with_errors_is_partial(self):
        """ParseResult with errors should be partial."""
        from uasset_read.models.result import ParseResult
        result = ParseResult()
        result.summary = object()
        result.errors = ["test error"]
        assert result.status == "partial"

    def test_result_with_opaque_export_is_partial(self):
        """ParseResult with opaque export should be partial."""
        from uasset_read.models.result import ParseResult
        result = ParseResult()
        result.summary = object()

        # Mock export with opaque status
        class MockExport:
            parse_status = "opaque"

        result.export_map = [MockExport()]
        assert result.status == "partial"

    def test_result_with_all_success_is_success(self):
        """ParseResult with all success exports should be success."""
        from uasset_read.models.result import ParseResult
        result = ParseResult()
        result.summary = object()

        # Mock export with success status
        class MockExport:
            parse_status = "success"

        result.export_map = [MockExport()]
        assert result.status == "success"
