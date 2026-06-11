"""Export payload strategy 拆分测试。"""
import pytest
import inspect
import os
from unittest.mock import MagicMock


class TestExportPayloadContext:
    def test_has_required_fields(self):
        from uasset_read.parsers.property_parser import ExportPayloadContext
        ctx = ExportPayloadContext(
            export=MagicMock(), archive=MagicMock(), summary=MagicMock(),
            name_map=[], export_map=[], import_map=[],
        )
        assert hasattr(ctx, "class_name")
        assert ctx.class_name is None
        assert hasattr(ctx, "linker")
        assert hasattr(ctx, "mappings")


class TestOrchestration:
    def test_is_short(self):
        from uasset_read.parsers.property_parser import parse_properties_from_export
        source = inspect.getsource(parse_properties_from_export)
        lines = [l for l in source.split('\n') if l.strip() and not l.strip().startswith('#')]
        assert len(lines) < 60, f"parse_properties_from_export has {len(lines)} lines, expected < 60"

    def test_parse_real_asset(self):
        from uasset_read.parse_uasset import parse_package
        asset = os.path.join(
            os.environ.get("UE_ASSET_ROOT", r"E:\Develop\lib\UnrealEngine\Samples"),
            "FirstPerson", "Content", "FirstPerson", "Blueprints",
            "BP_FirstPersonCharacter.uasset",
        )
        if not os.path.isfile(asset):
            pytest.skip("Real asset not available")
        result = parse_package(asset, tolerant=True)
        assert result.is_success is True
        assert len(result.export_map) > 0
