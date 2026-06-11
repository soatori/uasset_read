"""解析 stage 拆分测试。"""
import pytest
import inspect
from unittest.mock import MagicMock


class TestParseContext:
    def test_has_required_fields(self):
        from uasset_read.parse_uasset import _ParseContext
        ctx = _ParseContext(path="test.uasset", result=MagicMock(), tolerant=True)
        assert hasattr(ctx, "bundle")
        assert hasattr(ctx, "archive")
        assert hasattr(ctx, "mappings_provider")
        assert hasattr(ctx, "linker")
        assert hasattr(ctx, "aborted")
        assert ctx.aborted is False

    def test_abort(self):
        from uasset_read.parse_uasset import _ParseContext
        ctx = _ParseContext(path="test.uasset", result=MagicMock(), tolerant=True)
        ctx.abort()
        assert ctx.aborted is True


class TestOrchestration:
    def test_is_short(self):
        from uasset_read.parse_uasset import _parse_package_core
        source = inspect.getsource(_parse_package_core)
        lines = [l for l in source.split('\n') if l.strip() and not l.strip().startswith('#')]
        assert len(lines) < 80, f"_parse_package_core has {len(lines)} lines, expected < 80"

    def test_parse_real_asset(self):
        from uasset_read.parse_uasset import _parse_package_core
        from uasset_read.models.result import ParseResult
        import os
        asset = os.path.join(
            os.environ.get("UE_ASSET_ROOT", r"E:\Develop\lib\UnrealEngine\Samples"),
            "FirstPerson", "Content", "FirstPerson", "Blueprints",
            "BP_FirstPersonCharacter.uasset",
        )
        if not os.path.isfile(asset):
            pytest.skip("Real asset not available")
        result = ParseResult()
        _parse_package_core(asset, result, tolerant=True)
        assert result.is_success is True
        assert result.summary is not None
        assert len(result.export_map) > 0
