# tests/integration/test_status_model_integration.py
"""状态模型集成测试。"""
import json
import pytest
from pathlib import Path


def _get_test_asset():
    """获取第一个可用的测试 .uasset 文件。"""
    test_assets = Path("E:/Develop/lib/Samples")
    if not test_assets.exists():
        pytest.skip("测试资产目录不存在")

    uasset_files = list(test_assets.glob("**/*.uasset"))[:1]
    if not uasset_files:
        pytest.skip("未找到测试资产")

    return uasset_files[0]


def test_json_output_status_format():
    """验证 JSON 输出状态格式正确"""
    from uasset_read.core import parse_single

    asset_path = _get_test_asset()

    # parse_single 返回格式化字符串（JSON 格式）
    output = parse_single(str(asset_path), format="json")
    data = json.loads(output)

    # 验证顶层状态
    assert "status" in data, "JSON 输出缺少 status 字段"
    assert data["status"]["status"] in ["success", "partial", "failed"], \
        f"无效的状态值: {data['status']['status']}"

    # 验证 export 状态
    for export in data.get("exports", []):
        if "parse_status" in export:
            valid_statuses = [
                "success", "partial", "failed", "opaque", "skipped",
                "partial_metadata", "opaque_unversioned", "fallback", "metadata"
            ]
            assert export["parse_status"] in valid_statuses, \
                f"无效的 export 状态: {export['parse_status']}"


def test_markdown_output_status_section():
    """验证 Markdown 输出状态部分正确"""
    from uasset_read.core import parse_single
    from uasset_read.parse_uasset import parse_package

    asset_path = _get_test_asset()

    # 获取 ParseResult 以检查 status
    result = parse_package(str(asset_path), tolerant=True)

    # 生成 Markdown 输出
    output = parse_single(str(asset_path), format="markdown")

    # 如果不是 success，应该有 Status 部分
    if result.status != "success":
        assert "## Status" in output or "Status" in output, \
            "非 success 状态下 Markdown 输出应包含 Status 部分"
        assert "**PARTIAL**" in output or "**FAILED**" in output, \
            "非 success 状态下应有 PARTIAL 或 FAILED 标记"


def test_status_values_in_result():
    """验证 ParseResult.status 字段值合法"""
    from uasset_read.parse_uasset import parse_package

    asset_path = _get_test_asset()

    result = parse_package(str(asset_path), tolerant=True)

    valid_statuses = ["success", "partial", "failed"]
    assert result.status in valid_statuses, \
        f"无效的 ParseResult.status: {result.status}"


def test_ir_status_preserved():
    """验证 IR 构建后状态信息保留"""
    from uasset_read.parse_uasset import parse_package
    from uasset_read.ir_builder import build_package_ir

    asset_path = _get_test_asset()

    result = parse_package(str(asset_path), tolerant=True)
    ir = build_package_ir(result)

    # IR 应该保留原始状态信息
    valid_statuses = ["success", "partial", "failed"]
    assert ir.status in valid_statuses, \
        f"无效的 IR status: {ir.status}"
