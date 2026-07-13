"""Archive / Provider / Renderer 单元测试

覆盖 ByteArchive、GameDirectoryProvider、TextRenderer 和 CLI format 解析。
"""

import types
from unittest.mock import MagicMock

import pytest

from uasset_read.archive import ByteArchive
from uasset_read.exceptions import ParseError


# ── ByteArchive 测试 ──────────────────────────────────────────────────────────


def test_byte_archive_read_bytes_basic():
    """read_bytes 返回正确子节"""
    archive = ByteArchive(b"\xAA\xBB\xCC\xDD", name="test")
    result = archive.read_bytes(2)
    assert result == b"\xAA\xBB"
    assert archive.tell() == 2
    archive.close()


def test_byte_archive_name_sets_path():
    """name 参数正确赋值 _path"""
    archive = ByteArchive(b"\x00", name="my_asset")
    assert archive._path == "my_asset"
    archive.close()


def test_byte_archive_read_overflow_raises():
    """读取超出缓冲区时抛 ParseError"""
    archive = ByteArchive(b"\x01\x02", name="test")
    with pytest.raises(ParseError, match="Cannot read"):
        archive.read(5)
    archive.close()


def test_byte_archive_read_negative_size_raises():
    """负数 size 抛 ParseError"""
    archive = ByteArchive(b"\x01", name="test")
    with pytest.raises(ParseError, match="negative size"):
        archive.read(-1)
    archive.close()


def test_byte_archive_close_releases_buffer():
    """close 清空缓冲区并重置大小"""
    archive = ByteArchive(b"\x01\x02\x03", name="test")
    archive.close()
    assert archive._file_size == 0
    assert archive._buffer == b""


# ── GameDirectoryProvider 测试 ────────────────────────────────────────────────


def test_provider_list_files_cache_hit(tmp_path):
    """第二次 list_files 调用命中缓存，不重新扫描"""
    from uasset_read.providers import GameDirectoryProvider

    (tmp_path / "a.uasset").touch()
    provider = GameDirectoryProvider(tmp_path)

    first = provider.list_files(".uasset")
    assert ".uasset" in provider._list_files_cache

    second = provider.list_files(".uasset")
    # 两次调用应返回同一 list 对象（缓存命中）
    assert first is second


def test_provider_refresh_clears_cache(tmp_path):
    """refresh_file_cache 清空缓存字典"""
    from uasset_read.providers import GameDirectoryProvider

    (tmp_path / "a.uasset").touch()
    provider = GameDirectoryProvider(tmp_path)

    provider.list_files(".uasset")
    assert len(provider._list_files_cache) > 0

    provider.refresh_file_cache()
    assert len(provider._list_files_cache) == 0


def test_provider_list_uasset_files_filters_extensions(tmp_path):
    """list_uasset_files 仅返回 .uasset 和 .umap"""
    from uasset_read.providers import GameDirectoryProvider

    (tmp_path / "char.uasset").touch()
    (tmp_path / "level.umap").touch()
    (tmp_path / "readme.txt").touch()
    (tmp_path / "data.upak").touch()
    provider = GameDirectoryProvider(tmp_path)

    result = provider.list_uasset_files()
    names = [p.name for p in result]
    assert "char.uasset" in names
    assert "level.umap" in names
    assert "readme.txt" not in names
    assert "data.upak" not in names


def test_provider_constructor_nonexistent_dir_raises():
    """构造不存在的目录抛 FileNotFoundError"""
    from uasset_read.providers import GameDirectoryProvider

    with pytest.raises(FileNotFoundError):
        GameDirectoryProvider("/nonexistent_path_xyz_12345")


# ── TextRenderer 测试 ─────────────────────────────────────────────────────────


def _make_package_ir(name: str = "TestPackage") -> MagicMock:
    """构造最小 PackageIR mock，满足 TextRenderer.render 需求。"""
    header = MagicMock()
    header.package_name = name
    header.package_class = "BlueprintGeneratedClass"
    header.ue_version = "5.4"
    header.package_flags = 0
    header.total_export_count = 1
    header.total_import_count = 0
    header.folder_name = ""

    ir = MagicMock()
    ir.header = header
    ir.imports = []
    ir.exports = []
    ir.linker = None
    ir.blueprint = None
    ir.decompiled_functions = []
    ir.execution_chains = []
    ir.variables = []
    ir.diagnostics = []
    ir.function_graphs = []
    ir.resolved_parent_assets = []
    ir.inherited_blueprint_graphs = []
    ir.logic_sources = []
    ir.soft_object_paths = []
    ir.soft_package_references = []
    ir.depends_map = []
    ir.resolved_depends_map = []
    ir.asset_registry_data = None
    ir.errors = []
    ir.status = "success"
    ir.status_message = None
    ir.anim_blueprint = None
    ir.anim_sequence = None
    ir.anim_montage = None
    ir.debug = None
    return ir


def test_text_renderer_render_returns_nonempty():
    """render() 返回非空字符串"""
    from uasset_read.renderers.text_renderer import TextRenderer
    from uasset_read.renderers.base import RenderOptions

    renderer = TextRenderer()
    result = renderer.render(_make_package_ir(), RenderOptions())
    assert isinstance(result, str)
    assert len(result) > 0


def test_text_renderer_includes_package_name():
    """render 输出包含包名"""
    from uasset_read.renderers.text_renderer import TextRenderer
    from uasset_read.renderers.base import RenderOptions

    renderer = TextRenderer()
    result = renderer.render(_make_package_ir("MyAwesomeBP"), RenderOptions())
    assert "MyAwesomeBP" in result


def test_text_renderer_debug_shows_editor_variables():
    """debug 模式显示编辑器内部变量，standard 模式过滤"""
    from uasset_read.renderers.text_renderer import TextRenderer
    from uasset_read.renderers.base import RenderOptions, EDITOR_VARIABLE_NAMES
    from uasset_read.models.ir import VariableIR

    # 取一个编辑器变量名来构造数据
    editor_var_name = next(iter(EDITOR_VARIABLE_NAMES))
    var = VariableIR(name=editor_var_name, type="ArrayProperty", default_value=None)
    ir = _make_package_ir()
    ir.variables = [var]

    renderer = TextRenderer()
    standard = renderer.render(ir, RenderOptions(output_level="standard"))
    debug = renderer.render(ir, RenderOptions(output_level="debug"))

    # standard 应过滤编辑器变量
    assert editor_var_name not in standard
    # debug 应显示编辑器变量
    assert editor_var_name in debug


# ── CLI format 解析测试 ───────────────────────────────────────────────────────


def test_resolve_format_named_flags():
    """--text → 'text'，--markdown → 'markdown'"""
    from uasset_read.cli import resolve_format

    args_text = types.SimpleNamespace(text=True, markdown=False, json=False)
    assert resolve_format(args_text) == "text"

    args_md = types.SimpleNamespace(text=False, markdown=True, json=False)
    assert resolve_format(args_md) == "markdown"


def test_resolve_format_default_json():
    """无格式标志 → 'json'"""
    from uasset_read.cli import resolve_format

    args = types.SimpleNamespace(text=False, markdown=False, json=False)
    assert resolve_format(args) == "json"


def test_list_formats_contains_text():
    """list_formats() 包含 'text'"""
    from uasset_read.core import list_formats

    formats = list_formats()
    assert "text" in formats
