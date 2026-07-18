"""端到端集成测试 — 使用 tests/samples/ 本地样本验证完整解析→渲染流程。"""

import json

import pytest

from uasset_read.ir_builder import build_package_ir
from uasset_read.parse_uasset import parse_package
from uasset_read.renderers.base import RenderOptions
from uasset_read.renderers.json_renderer import JSONRenderer
from uasset_read.renderers.markdown_renderer import MarkdownRenderer

from tests.integration.sample_assets import (
    LOCAL_SAMPLES,
    require_local_sample_path,
    pytest_param_for_asset,
)


@pytest.mark.integration
class TestLocalSampleParsing:
    """使用本地样本文件测试完整解析流程。"""

    @pytest.mark.parametrize(
        "asset",
        [pytest_param_for_asset(a) for a in LOCAL_SAMPLES],
        ids=[f"{a.category}:{a.label}" for a in LOCAL_SAMPLES],
    )
    def test_parse_returns_success(self, asset):
        """parse_package 返回成功状态。"""
        path = require_local_sample_path(asset)
        result = parse_package(str(path))

        assert result.is_success is True, f"Parse failed: {result.errors}"
        assert result.summary is not None
        assert result.summary.package_name

    @pytest.mark.parametrize(
        "asset",
        [pytest_param_for_asset(a) for a in LOCAL_SAMPLES],
        ids=[f"{a.category}:{a.label}" for a in LOCAL_SAMPLES],
    )
    def test_parse_has_exports(self, asset):
        """parse_package 返回至少一个 export。"""
        path = require_local_sample_path(asset)
        result = parse_package(str(path))

        assert len(result.export_map) > 0, "No exports found"

    @pytest.mark.parametrize(
        "asset",
        [pytest_param_for_asset(a) for a in LOCAL_SAMPLES],
        ids=[f"{a.category}:{a.label}" for a in LOCAL_SAMPLES],
    )
    def test_build_ir_succeeds(self, asset):
        """build_package_ir 能从 ParseResult 构建 IR。"""
        path = require_local_sample_path(asset)
        result = parse_package(str(path))
        ir = build_package_ir(result)

        assert ir is not None
        assert ir.header is not None
        assert ir.header.package_name == result.summary.package_name

    @pytest.mark.parametrize(
        "asset",
        [pytest_param_for_asset(a) for a in LOCAL_SAMPLES],
        ids=[f"{a.category}:{a.label}" for a in LOCAL_SAMPLES],
    )
    def test_json_renderer_produces_valid_json(self, asset):
        """JSONRenderer 产生有效 JSON。"""
        path = require_local_sample_path(asset)
        result = parse_package(str(path))
        ir = build_package_ir(result)
        renderer = JSONRenderer()
        output = renderer.render(ir, RenderOptions())

        # 验证是有效 JSON
        parsed = json.loads(output)
        assert "summary" in parsed
        assert parsed["summary"]["package_name"] == result.summary.package_name

    @pytest.mark.parametrize(
        "asset",
        [pytest_param_for_asset(a) for a in LOCAL_SAMPLES],
        ids=[f"{a.category}:{a.label}" for a in LOCAL_SAMPLES],
    )
    def test_markdown_renderer_produces_output(self, asset):
        """MarkdownRenderer 产生非空输出。"""
        path = require_local_sample_path(asset)
        result = parse_package(str(path))
        ir = build_package_ir(result)
        renderer = MarkdownRenderer()
        output = renderer.render(ir, RenderOptions())

        assert isinstance(output, str)
        assert len(output) > 0


@pytest.mark.integration
class TestTolerantMode:
    """容错模式端到端测试。"""

    @pytest.mark.parametrize(
        "asset",
        [pytest_param_for_asset(a) for a in LOCAL_SAMPLES],
        ids=[f"{a.category}:{a.label}" for a in LOCAL_SAMPLES],
    )
    def test_tolerant_mode_returns_result(self, asset):
        """tolerant 模式下 parse_package 不抛异常，返回 ParseResult。"""
        path = require_local_sample_path(asset)
        result = parse_package(str(path), tolerant=True)

        assert result is not None
        assert result.status in ("success", "partial", "failed")

    @pytest.mark.parametrize(
        "asset",
        [pytest_param_for_asset(a) for a in LOCAL_SAMPLES],
        ids=[f"{a.category}:{a.label}" for a in LOCAL_SAMPLES],
    )
    def test_error_keys_populated_on_failure(self, asset):
        """出错时 _error_keys 应有对应条目。"""
        path = require_local_sample_path(asset)
        result = parse_package(str(path), tolerant=True)

        if result.errors:
            assert len(result._error_keys) > 0, (
                f"有 {len(result.errors)} 个错误但 _error_keys 为空"
            )
        else:
            # 无错误时 _error_keys 也应为空
            assert len(result._error_keys) == 0

    @pytest.mark.parametrize(
        "asset",
        [pytest_param_for_asset(a) for a in LOCAL_SAMPLES],
        ids=[f"{a.category}:{a.label}" for a in LOCAL_SAMPLES],
    )
    def test_ir_has_header(self, asset):
        """IR 应包含 header（包头信息）。"""
        path = require_local_sample_path(asset)
        result = parse_package(str(path), tolerant=True)
        if result.status == "failed":
            pytest.skip("Parse failed")
        ir = build_package_ir(result)
        assert ir.header is not None
        assert ir.header.package_name == result.summary.package_name
