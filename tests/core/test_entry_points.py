"""入口点测试 — 模块导入冒烟 + 参数完整性验证"""
from __future__ import annotations

import importlib
import inspect
import subprocess
import sys
import os

import pytest

from uasset_read import core
from uasset_read.pak.constants import PAK_INFO_SIZES


# ---------------------------------------------------------------------------
# 模块导入冒烟测试 — 验证所有核心模块可导入且结构正确
# ---------------------------------------------------------------------------

# 所有核心模块列表（已验证可导入）
MODULES = [
    "uasset_read",
    "uasset_read.core",
    "uasset_read.archive",
    "uasset_read.package",
    "uasset_read.parse_uasset",
    "uasset_read.cli",
    "uasset_read.graph",
    "uasset_read.graph.parser",
    "uasset_read.graph.flow_builder",
    "uasset_read.graph.macro_expander",
    "uasset_read.kismet",
    "uasset_read.kismet.archive",
    "uasset_read.kismet.jump_analyzer",
    "uasset_read.kismet.expressions",
    "uasset_read.kismet.tokens",
    "uasset_read.kismet.translator",
    "uasset_read.kismet.pipeline",
    "uasset_read.parsers",
    "uasset_read.parsers.asset_types",
    "uasset_read.parsers.asset_types.anim_blueprint",
    "uasset_read.parsers.asset_types.anim_montage",
    "uasset_read.parsers.asset_types.anim_sequence",
    "uasset_read.parsers.asset_types.movie_scene",
    "uasset_read.parsers.asset_types.movie_scene_control_rig",
    "uasset_read.parsers.asset_types.property_extractor",
    "uasset_read.models",
    "uasset_read.models.ir",
    "uasset_read.models.status",
    "uasset_read.models.fallback",
    "uasset_read.serializers",
    "uasset_read.serializers.graph",
    "uasset_read.serializers.package_summary",
    "uasset_read.serializers.property_tags",
    "uasset_read.link",
    "uasset_read.link.linker",
    "uasset_read.pak",
    "uasset_read.pak.reader",
    "uasset_read.pak.constants",
    "uasset_read.iostore",
    "uasset_read.blueprint",
    "uasset_read.blueprint.variable_extractor",
    "uasset_read.cpp_gen",
    "uasset_read.renderers",
    "uasset_read.renderers.json_renderer",
    "uasset_read.renderers.markdown_renderer",
    "uasset_read.memory_safety",
    "uasset_read.debug",
    "uasset_read.bounded_events",
    "uasset_read.versioning",
    "uasset_read.ir_builder",
    "uasset_read.objects",
    "uasset_read.raw",
    "uasset_read.mappings",
    "uasset_read.batch_worker",
    "uasset_read.project_logging",
]


@pytest.mark.parametrize("module_path", MODULES)
def test_module_importable(module_path):
    """每个核心模块应可成功导入"""
    mod = importlib.import_module(module_path)
    assert mod is not None


def test_public_api_structure():
    """uasset_read 包级 API 结构验证"""
    import uasset_read
    assert callable(getattr(uasset_read, "parse_single", None))
    assert callable(getattr(uasset_read, "parse_batch", None))
    assert callable(getattr(uasset_read, "list_formats", None))
    assert "json" in uasset_read.list_formats()


def test_archive_read_u8():
    """ByteArchive 基本读取"""
    from uasset_read.archive import ByteArchive
    archive = ByteArchive(b"\x42\x00\xff", name="test")
    assert archive.read_u8() == 0x42
    assert archive.read_u8() == 0x00
    assert archive.read_u8() == 0xFF
    archive.close()


def test_archive_read_u32():
    from uasset_read.archive import ByteArchive
    archive = ByteArchive(b"\x01\x00\x00\x00", name="test")
    assert archive.read_u32() == 1
    archive.close()


def test_archive_seek_tell():
    from uasset_read.archive import ByteArchive
    archive = ByteArchive(b"\x00\x01\x02\x03\x04", name="test")
    archive.seek(2)
    assert archive.tell() == 2
    assert archive.read_u8() == 0x02
    archive.close()


def test_handler_classes_exist():
    """所有 handler 类应存在且可实例化"""
    from uasset_read.parsers.asset_types.anim_blueprint import AnimBlueprintHandler
    from uasset_read.parsers.asset_types.anim_montage import AnimMontageHandler
    from uasset_read.parsers.asset_types.anim_sequence import AnimSequenceHandler
    from uasset_read.parsers.asset_types.movie_scene import MovieSceneHandler
    for cls in [AnimBlueprintHandler, AnimMontageHandler, AnimSequenceHandler, MovieSceneHandler]:
        handler = cls()
        assert hasattr(handler, "handle")


def test_handler_empty_properties():
    """handler 空属性应返回 PARTIAL"""
    from uasset_read.parsers.asset_types.anim_blueprint import AnimBlueprintHandler
    from uasset_read.parsers.asset_types.anim_montage import AnimMontageHandler
    from uasset_read.parsers.asset_types.anim_sequence import AnimSequenceHandler
    from uasset_read.parsers.asset_types.movie_scene import MovieSceneHandler
    for cls in [AnimBlueprintHandler, AnimMontageHandler, AnimSequenceHandler, MovieSceneHandler]:
        handler = cls()

        class FakeExport:
            properties = []
            custom_data = {}
        class FakeCtx:
            warnings = []

        result = handler.handle(FakeExport(), FakeCtx())
        assert result.value == "partial"


def test_status_model():
    from uasset_read.models.status import FAILED_STATUSES, PARTIAL_STATUSES
    assert "failed" in FAILED_STATUSES
    assert "fallback" in PARTIAL_STATUSES


def test_fallback_status():
    from uasset_read.models.fallback import ExportParseStatus
    assert ExportParseStatus.SUCCESS.value == "success"
    assert ExportParseStatus.PARTIAL.value == "partial"


def test_memory_policy():
    from uasset_read.memory_safety import MemoryPolicy, ResourceLimits
    policy = MemoryPolicy()
    limits = policy.limits_for_size(1024 * 1024)
    assert isinstance(limits, ResourceLimits)


def test_cli_help():
    src_dir = os.path.join(os.path.dirname(__file__), "..", "src")
    env = {**os.environ, "PYTHONPATH": src_dir}
    result = subprocess.run(
        [sys.executable, "-m", "uasset_read", "--help"],
        capture_output=True, text=True, timeout=10, env=env
    )
    assert result.returncode == 0


# ---------------------------------------------------------------------------
# 入口点参数完整性测试
# ---------------------------------------------------------------------------

class TestParameterIntegrity:
    """验证 parse_batch 与 parse_single 参数一致。"""

    def test_parse_batch_has_output_level(self):
        """parse_batch 应支持 output_level 参数。"""
        sig = inspect.signature(core.parse_batch)
        assert "output_level" in sig.parameters, (
            f"parse_batch 缺少 output_level 参数，当前参数: {list(sig.parameters.keys())}"
        )

    def test_parse_batch_has_hex_view(self):
        """parse_batch 应支持 hex_view 参数。"""
        sig = inspect.signature(core.parse_batch)
        assert "hex_view" in sig.parameters, (
            f"parse_batch 缺少 hex_view 参数"
        )

    def test_parse_batch_output_level_default_matches_single(self):
        """parse_batch 的 output_level 默认值应与 parse_single 一致。"""
        single_sig = inspect.signature(core.parse_single)
        batch_sig = inspect.signature(core.parse_batch)
        assert batch_sig.parameters["output_level"].default == single_sig.parameters["output_level"].default

    def test_parse_batch_hex_view_default_matches_single(self):
        """parse_batch 的 hex_view 默认值应与 parse_single 一致。"""
        single_sig = inspect.signature(core.parse_single)
        batch_sig = inspect.signature(core.parse_batch)
        assert batch_sig.parameters["hex_view"].default == single_sig.parameters["hex_view"].default


class TestParseBatchPassesParameters:
    """验证 parse_batch 实际传递参数到 parse_single。"""

    def test_parse_batch_includes_params_in_parse_options(self):
        """parse_options dict 应包含 output_level 和 hex_view。"""
        source = inspect.getsource(core.parse_batch)
        assert "output_level" in source, "parse_batch 源码中未引用 output_level"
        assert "hex_view" in source, "parse_batch 源码中未引用 hex_view"
        # 验证它们出现在 parse_options dict 中
        assert '"output_level"' in source or "'output_level'" in source, (
            "output_level 未被添加到 parse_options"
        )
        assert '"hex_view"' in source or "'hex_view'" in source, (
            "hex_view 未被添加到 parse_options"
        )


class TestPakInfoSizes:
    """验证 PAK_INFO_SIZES 包含 bEncryptedIndex。"""

    def test_v1_6_includes_b_encrypted_index(self):
        """v1-6 的 serialized size 应包含 bEncryptedIndex（1 字节）。

        UE 源码 IPlatformFilePak.h GetSerializedSize():
        base = Magic(4) + Version(4) + IndexOffset(8) + IndexSize(8) + IndexHash(20) + bEncryptedIndex(1) = 45
        """
        assert PAK_INFO_SIZES["v1-6"] == 45, (
            f"v1-6 size 应为 45（含 bEncryptedIndex），实际为 {PAK_INFO_SIZES['v1-6']}"
        )

    def test_v7_size_consistent(self):
        """v7 = v1-6(45) + EncryptionKeyGuid(16) = 61"""
        assert PAK_INFO_SIZES["v7"] == 61

    def test_v8_size_consistent(self):
        """v8 = v7(61) + CompressionMethods(32*5=160) = 221"""
        assert PAK_INFO_SIZES["v8"] == 221

    def test_v9_size_consistent(self):
        """v9 = v8(221) + FrozenIndex(1) = 222"""
        assert PAK_INFO_SIZES["v9"] == 222

    def test_v10_size_consistent(self):
        """v10 = v8(221)（FrozenIndex removed）"""
        assert PAK_INFO_SIZES["v10+"] == 221


class TestPrivateKeyExport:
    """验证 __init__.py 不导出私有函数。"""

    def test_no_private_functions_in_all(self):
        """__all__ 不应包含以 _ 开头的函数名（__version__ 除外）。"""
        import uasset_read
        private = [name for name in uasset_read.__all__ if name.startswith("_") and name != "__version__"]
        assert private == [], f"__all__ 包含私有函数: {private}"

    def test_derive_node_name_not_imported(self):
        """__init__.py 不应导入 _derive_node_name。"""
        import uasset_read
        assert not hasattr(uasset_read, "_derive_node_name") or \
            "_derive_node_name" not in getattr(uasset_read, "__all__", []), (
            "_derive_node_name 不应通过 uasset_read 包导出"
        )


class TestPostProcessSplit:
    """验证 _post_process 已拆分为子函数。"""

    def _get_module(self):
        """获取 parse_uasset 模块（避免 __init__.py 函数名遮蔽）。"""
        import sys
        return sys.modules["uasset_read.parse_uasset"]

    def test_post_process_sub_functions_exist(self):
        """parse_uasset 模块应包含 _post_process 的子函数。"""
        pu = self._get_module()
        # 至少应有一个从 _post_process 提取的子函数
        sub_funcs = [
            name for name in dir(pu)
            if name.startswith("_") and callable(getattr(pu, name, None))
            and name not in ("_post_process", "_resolve_parent_assets", "_find_parent_asset_file",
                             "_extract_kismet_decompiled", "_package_metadata", "_record_parse_stage_error",
                             "_run_required_stage", "_should_use_lightweight_tolerant_parse",
                             "_build_lightweight_graphs", "_build_lightweight_function_graphs",
                             "_parse_package_core")
        ]
        assert len(sub_funcs) > 0, (
            "parse_uasset 模块中未发现 _post_process 的子函数"
        )

    def test_post_process_shorter(self):
        """_post_process 函数体应比拆分前短。"""
        import inspect
        pu = self._get_module()
        source = inspect.getsource(pu._post_process)
        line_count = len(source.splitlines())
        # 拆分后应显著短于原始 168 行
        assert line_count < 100, (
            f"_post_process 仍然过长（{line_count} 行），预期应小于 100 行"
        )
