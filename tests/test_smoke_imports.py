"""模块导入冒烟测试 — 验证所有核心模块可导入且结构正确"""
import importlib
import pytest


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
    import subprocess, sys, os
    src_dir = os.path.join(os.path.dirname(__file__), "..", "src")
    env = {**os.environ, "PYTHONPATH": src_dir}
    result = subprocess.run(
        [sys.executable, "-m", "uasset_read", "--help"],
        capture_output=True, text=True, timeout=10, env=env
    )
    assert result.returncode == 0
