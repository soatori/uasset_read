"""cpp_skeleton 管线契约测试 — 验证 cpp_skeleton 是独立管线而非标准渲染器。

目标架构：
- cpp_skeleton 不应在 RENDERER_REGISTRY 中注册
- get_renderer("cpp_skeleton") 应抛出异常
- RenderOptions 不应包含 linker_result 字段
- CppSkeletonRenderer 不应继承 IRenderer
- 但 cpp_skeleton 输出仍应正常工作（集成测试）
"""
from __future__ import annotations

import os

import pytest

from uasset_read.core import parse_single
from uasset_read.renderers import RENDERER_REGISTRY, get_renderer
from uasset_read.renderers.base import RenderOptions, IRenderer
from uasset_read.renderers.cpp_skeleton_renderer import CppSkeletonRenderer

# 真实蓝图资产路径（与 test_real_asset_e2e.py 保持一致）
_REAL_BLUEPRINT = os.path.join(
    os.environ.get("UE_ASSET_ROOT", r"E:\Develop\lib\UnrealEngine\Samples"),
    "FirstPerson", "Content", "FirstPerson", "Blueprints",
    "BP_FirstPersonCharacter.uasset",
)

_has_real_asset = os.path.isfile(_REAL_BLUEPRINT)


# ---------------------------------------------------------------------------
# 契约测试 — 定义目标架构（初始应 FAIL，重构后 PASS）
# ---------------------------------------------------------------------------

class TestCppSkeletonPipelineContract:
    """验证 cpp_skeleton 遵循独立管线架构，而非标准渲染器模式。"""

    def test_cpp_skeleton_not_in_renderer_registry(self):
        """cpp_skeleton 不应注册在标准渲染器注册表中。"""
        assert "cpp_skeleton" not in RENDERER_REGISTRY, (
            "cpp_skeleton 不应在 RENDERER_REGISTRY 中 — "
            "它是独立管线，不是标准渲染器"
        )

    def test_get_renderer_raises_for_cpp_skeleton(self):
        """get_renderer('cpp_skeleton') 应抛出异常。"""
        with pytest.raises((KeyError, ValueError)):
            get_renderer("cpp_skeleton")

    def test_render_options_has_no_linker_result_field(self):
        """RenderOptions 不应包含 linker_result 字段。

        linker_result 是绕过 PackageIR 的反模式，
        重构后 cpp_skeleton 应通过独立管线获取 linker 数据。
        """
        opts = RenderOptions()
        assert not hasattr(opts, "linker_result"), (
            "RenderOptions 不应包含 linker_result — "
            "该字段是绕过 PackageIR 的反模式"
        )

    def test_cpp_skeleton_renderer_not_subclass_of_irenderer(self):
        """CppSkeletonRenderer 不应继承 IRenderer。

        独立管线有自己的接口契约，不需要适配标准渲染器接口。
        """
        assert not issubclass(CppSkeletonRenderer, IRenderer), (
            "CppSkeletonRenderer 不应继承 IRenderer — "
            "它是独立管线，有自己的接口契约"
        )


# ---------------------------------------------------------------------------
# 集成测试 — 验证 cpp_skeleton 输出质量（应 PASS）
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.skipif(not _has_real_asset, reason="真实蓝图资产不可用")
class TestCppSkeletonOutputQuality:
    """验证 cpp_skeleton 管线能正确产出 C++ 骨架输出。"""

    def test_cpp_skeleton_produces_valid_output(self):
        """解析真实蓝图资产，验证 cpp_skeleton 输出非空。"""
        output = parse_single(_REAL_BLUEPRINT, format="cpp_skeleton", tolerant=True)
        assert output, "cpp_skeleton 输出不应为空"
        assert len(output) > 100, "cpp_skeleton 输出应包含有意义的内容"

    def test_cpp_skeleton_output_is_string(self):
        """验证 cpp_skeleton 输出为字符串类型。"""
        output = parse_single(_REAL_BLUEPRINT, format="cpp_skeleton", tolerant=True)
        assert isinstance(output, str), (
            f"cpp_skeleton 输出应为 str，实际为 {type(output).__name__}"
        )
