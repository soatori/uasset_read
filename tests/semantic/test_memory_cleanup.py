"""Test that semantic_json format triggers memory cleanup."""
from unittest.mock import patch, MagicMock

from uasset_read.core import parse_single


class TestSemanticJsonMemoryCleanup:
    @patch("uasset_read.core.build_package_ir")
    @patch("uasset_read.core.parse_uasset_with_linker")
    def test_semantic_json_cleans_up_asset_type_data(self, mock_parse, mock_build_ir):
        """Verify _asset_type_data is deleted after semantic_json render."""
        # Create mock exports that carry the temporary attributes
        mock_export_1 = MagicMock()
        mock_export_1._asset_type_data = {"key": "value"}
        mock_export_1._uclass_native_fields = {"field": "data"}
        mock_export_2 = MagicMock()
        mock_export_2._asset_type_data = {"key2": "value2"}
        mock_export_2._uclass_native_fields = {"field2": "data2"}

        mock_result = MagicMock()
        mock_result.is_success = True
        mock_result.errors = []
        mock_result.export_map = [mock_export_1, mock_export_2]
        mock_result.imports = []
        mock_result.diagnostics_data = None
        mock_result.exports = [
            MagicMock(
                object_class="UTexture2D",
                object_name="TestTexture",
                serial_size=1024,
                parse_status="success",
                asset_type_data={"Width": 256, "Height": 256},
            )
        ]
        mock_parse.return_value = mock_result

        mock_ir = MagicMock()
        mock_ir.exports = mock_result.exports
        mock_ir.imports = []
        mock_ir.diagnostics_data = None
        mock_build_ir.return_value = mock_ir

        parse_single("dummy.uasset", format="semantic_json")

        # After render, the temporary attributes should have been deleted
        assert not hasattr(mock_export_1, "_asset_type_data")
        assert not hasattr(mock_export_1, "_uclass_native_fields")
        assert not hasattr(mock_export_2, "_asset_type_data")
        assert not hasattr(mock_export_2, "_uclass_native_fields")

    @patch("uasset_read.core.get_renderer")
    @patch("uasset_read.core.build_package_ir")
    @patch("uasset_read.core.parse_uasset_with_linker")
    def test_standard_json_cleans_up_asset_type_data(self, mock_parse, mock_build_ir, mock_get_renderer):
        """Verify standard json format also cleans up (regression guard)."""
        mock_export = MagicMock()
        mock_export._asset_type_data = {"key": "value"}
        mock_export._uclass_native_fields = {"field": "data"}

        mock_result = MagicMock()
        mock_result.is_success = True
        mock_result.errors = []
        mock_result.export_map = [mock_export]
        mock_result.imports = []
        mock_result.diagnostics_data = None
        mock_result.exports = []
        mock_parse.return_value = mock_result

        mock_ir = MagicMock()
        mock_ir.exports = []
        mock_ir.imports = []
        mock_ir.diagnostics_data = None
        mock_build_ir.return_value = mock_ir

        mock_renderer = MagicMock()
        mock_renderer.render.return_value = "{}"
        mock_get_renderer.return_value = mock_renderer

        parse_single("dummy.uasset", format="json")

        assert not hasattr(mock_export, "_asset_type_data")
        assert not hasattr(mock_export, "_uclass_native_fields")
