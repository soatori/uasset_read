"""Tests for semantic_json format routing in core API."""
import json
import pytest
from unittest.mock import patch, MagicMock

from uasset_read.core import parse_single


class TestSemanticJsonRouting:
    def test_format_list_includes_semantic_json(self):
        from uasset_read.renderers import list_formats
        formats = list_formats()
        assert "semantic_json" in formats

    def test_semantic_json_renderer_gettable(self):
        from uasset_read.renderers import get_renderer
        renderer = get_renderer("semantic_json")
        assert renderer.format_name == "semantic_json"

    @patch("uasset_read.core.build_package_ir")
    @patch("uasset_read.core.parse_uasset_with_linker")
    def test_semantic_json_routes_through_builder(self, mock_parse, mock_build_ir):
        """Verify semantic_json format triggers build_semantic_ir + SemanticJSONRenderer."""
        # Create a minimal mock parse result
        mock_result = MagicMock()
        mock_result.is_success = True
        mock_result.errors = []
        mock_result.export_map = []
        mock_result.imports = []
        mock_result.diagnostics_data = None
        mock_result.exports = [
            MagicMock(
                object_class="UTexture2D",
                object_name="TestTexture",
                serial_size=1024,
                parse_status="success",
                asset_type_data={"Width": 256, "Height": 256, "SourceFile": None},
            )
        ]
        mock_parse.return_value = mock_result

        # Mock the PackageIR
        mock_ir = MagicMock()
        mock_ir.exports = mock_result.exports
        mock_ir.imports = []
        mock_ir.diagnostics_data = None
        mock_build_ir.return_value = mock_ir

        output = parse_single("dummy.uasset", format="semantic_json")

        # Should return valid JSON
        data = json.loads(output)
        assert data["format"] == "uasset_read.asset_semantic"
        assert data["asset"]["class_name"] == "UTexture2D"
        assert data["asset"]["object_name"] == "TestTexture"

    @patch("uasset_read.core.build_package_ir")
    @patch("uasset_read.core.parse_uasset_with_linker")
    def test_semantic_json_uses_correct_mode(self, mock_parse, mock_build_ir):
        """Verify output_level maps to mode parameter in build_semantic_ir."""
        mock_result = MagicMock()
        mock_result.is_success = True
        mock_result.errors = []
        mock_result.export_map = []
        mock_result.imports = []
        mock_result.diagnostics_data = None
        mock_result.exports = [
            MagicMock(
                object_class="UStaticMesh",
                object_name="TestMesh",
                serial_size=2048,
                parse_status="success",
                asset_type_data=None,
            )
        ]
        mock_parse.return_value = mock_result

        # Mock the PackageIR
        mock_ir = MagicMock()
        mock_ir.exports = mock_result.exports
        mock_ir.imports = []
        mock_ir.diagnostics_data = None
        mock_build_ir.return_value = mock_ir

        output = parse_single("dummy.uasset", format="semantic_json", output_level="debug")
        data = json.loads(output)
        assert data["mode"] == "debug"
