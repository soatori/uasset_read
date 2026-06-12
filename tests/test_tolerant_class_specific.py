"""Class-specific tolerant skip 测试。"""
import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _read_fixture_lines(name: str) -> list[str]:
    """读取 fixture 文件中的非空行。"""
    path = FIXTURES_DIR / name
    if not path.exists():
        pytest.skip(f"Fixture file not found: {path}", allow_module_level=True)
    return [line.strip() for line in path.read_text().splitlines() if line.strip()]


class TestCubeBuilderTolerantSkip:
    """CubeBuilder_* export 的 tolerant skip 测试。"""

    @pytest.mark.parametrize("asset_path", _read_fixture_lines("real_asset_failures_cube_builder.txt"))
    def test_cube_builder_tolerant_parse_succeeds(self, asset_path: str):
        """CubeBuilder 资产应能解析成功（可能有局部错误，但资产级 is_success 为 True）。"""
        from uasset_read.parse_uasset import parse_uasset_with_linker

        result = parse_uasset_with_linker(asset_path, tolerant=True)
        assert result.summary is not None, "Summary should be parsed"
        assert result.export_map is not None, "Export map should be parsed"
        fatal_errors = [e for e in result.errors if "serial_offset" in e.lower() or "payloadtoc" in e.lower()]
        assert len(fatal_errors) == 0, f"Fatal errors should not occur: {fatal_errors}"


class TestAnimationDataModelTolerantSkip:
    """AnimationDataModel export 的 tolerant skip 测试。"""

    @pytest.mark.parametrize("asset_path", _read_fixture_lines("real_asset_failures_animation_data_model.txt"))
    def test_animation_data_model_tolerant_parse_succeeds(self, asset_path: str):
        """AnimationDataModel 资产应能解析成功。"""
        from uasset_read.parse_uasset import parse_uasset_with_linker

        result = parse_uasset_with_linker(asset_path, tolerant=True)
        assert result.summary is not None
        assert result.export_map is not None
        fatal_errors = [e for e in result.errors if "serial_offset" in e.lower() or "payloadtoc" in e.lower()]
        assert len(fatal_errors) == 0, f"Fatal errors should not occur: {fatal_errors}"


class TestPayloadOffsetsTolerant:
    """Payload TOC / export offset 异常的 tolerant 处理测试。"""

    @pytest.mark.parametrize("asset_path", _read_fixture_lines("real_asset_failures_payload_offsets.txt"))
    def test_payload_offset_tolerant_parse(self, asset_path: str):
        """Payload offset 异常资产应能解析到 summary 和 export_map。"""
        from uasset_read.parse_uasset import parse_uasset_with_linker
        result = parse_uasset_with_linker(asset_path, tolerant=True)
        assert result.summary is not None
        assert result.export_map is not None
        fatal_errors = [e for e in result.errors if "serial_offset" in e.lower() or "payloadtoc" in e.lower()]
        assert len(fatal_errors) == 0, f"Fatal errors should not occur: {fatal_errors}"


class TestNiagaraTolerantSkip:
    """Niagara payload 的 tolerant skip 测试。"""

    @pytest.mark.parametrize("asset_path", _read_fixture_lines("real_asset_failures_niagara.txt"))
    def test_niagara_tolerant_parse(self, asset_path: str):
        from uasset_read.parse_uasset import parse_uasset_with_linker
        result = parse_uasset_with_linker(asset_path, tolerant=True)
        assert result.summary is not None
        assert result.export_map is not None
        fatal_errors = [e for e in result.errors if "serial_offset" in e.lower() or "payloadtoc" in e.lower()]
        assert len(fatal_errors) == 0, f"Fatal errors should not occur: {fatal_errors}"


class TestMovieSceneTolerantSkip:
    """MovieScene payload 的 tolerant skip 测试。"""

    @pytest.mark.parametrize("asset_path", _read_fixture_lines("real_asset_failures_movie_scene.txt"))
    def test_movie_scene_tolerant_parse(self, asset_path: str):
        from uasset_read.parse_uasset import parse_uasset_with_linker
        result = parse_uasset_with_linker(asset_path, tolerant=True)
        assert result.summary is not None
        assert result.export_map is not None
        fatal_errors = [e for e in result.errors if "serial_offset" in e.lower() or "payloadtoc" in e.lower()]
        assert len(fatal_errors) == 0, f"Fatal errors should not occur: {fatal_errors}"


class TestK2NodeTolerantSkip:
    """K2Node payload 的 tolerant skip 测试。"""

    @pytest.mark.parametrize("asset_path", _read_fixture_lines("real_asset_failures_k2_nodes.txt"))
    def test_k2node_tolerant_parse(self, asset_path: str):
        from uasset_read.parse_uasset import parse_uasset_with_linker
        result = parse_uasset_with_linker(asset_path, tolerant=True)
        assert result.summary is not None
        assert result.export_map is not None
        fatal_errors = [e for e in result.errors if "serial_offset" in e.lower() or "payloadtoc" in e.lower()]
        assert len(fatal_errors) == 0, f"Fatal errors should not occur: {fatal_errors}"


class TestMetaSoundTolerantSkip:
    """MetaSound payload 的 tolerant skip 测试。"""

    @pytest.mark.parametrize("asset_path", _read_fixture_lines("real_asset_failures_metasound.txt"))
    def test_metasound_tolerant_parse(self, asset_path: str):
        from uasset_read.parse_uasset import parse_uasset_with_linker
        result = parse_uasset_with_linker(asset_path, tolerant=True)
        assert result.summary is not None
        assert result.export_map is not None
        fatal_errors = [e for e in result.errors if "serial_offset" in e.lower() or "payloadtoc" in e.lower()]
        assert len(fatal_errors) == 0, f"Fatal errors should not occur: {fatal_errors}"


class TestMaterialExpressionTolerantSkip:
    """MaterialExpression payload 的 tolerant skip 测试。"""

    @pytest.mark.parametrize("asset_path", _read_fixture_lines("real_asset_failures_material_expression.txt"))
    def test_material_expression_tolerant_parse(self, asset_path: str):
        from uasset_read.parse_uasset import parse_uasset_with_linker
        result = parse_uasset_with_linker(asset_path, tolerant=True)
        assert result.summary is not None
        assert result.export_map is not None
        fatal_errors = [e for e in result.errors if "serial_offset" in e.lower() or "payloadtoc" in e.lower()]
        assert len(fatal_errors) == 0, f"Fatal errors should not occur: {fatal_errors}"
