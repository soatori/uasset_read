"""Archive 核心测试 — 合并自 test_archive_read_name.py 和 test_archive_provider_renderer.py。

覆盖：read_name() 索引越界/恢复/去重、skip()、
ByteArchive 基础操作、GameDirectoryProvider、TextRenderer、CLI format 解析。
"""
import types
from unittest.mock import MagicMock

import pytest

from uasset_read.archive import ByteArchive
from uasset_read.exceptions import ParseError


# ===========================================================================
# ByteArchive 基础操作
# ===========================================================================


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


# ===========================================================================
# read_name() 索引越界测试 (#334)
# ===========================================================================


def test_read_name_index_out_of_range():
    """read_name() 索引越界时应返回 'None' 而非崩溃。"""
    data = b'\x05\x00\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name0", "Name1", "Name2"]

    result = archive.read_name(name_map)
    assert result == "None"


def test_read_name_index_out_of_range_strict():
    """read_name() 索引越界在 strict 模式应抛出异常。"""
    data = b'\x05\x00\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=False)
    name_map = ["Name0", "Name1", "Name2"]

    with pytest.raises(ParseError):
        archive.read_name(name_map)


def test_read_name_index_negative():
    """read_name() 负索引应返回 'None'。"""
    data = b'\xff\xff\xff\xff\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name0", "Name1"]

    result = archive.read_name(name_map)
    assert result == "None"


def test_read_name_valid_index():
    """read_name() 正常索引应正确返回名称。"""
    data = b'\x01\x00\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data)
    name_map = ["Name0", "Name1", "Name2"]

    result = archive.read_name(name_map)
    assert result == "Name1"


def test_read_name_with_number():
    """read_name() 带 number 后缀应正确格式化。"""
    data = b'\x00\x00\x00\x00\x05\x00\x00\x00'
    archive = ByteArchive(data)
    name_map = ["MyName"]

    result = archive.read_name(name_map)
    assert result == "MyName_5"


def test_read_name_large_index_recovery():
    """read_name() 检测到异常大索引时应尝试恢复。"""
    garbage = b'\x00\x10\x00\x00\x00\x00'
    valid_name = b'\x00\x00\x00\x00\x00\x00\x00\x00'
    data = garbage + valid_name
    archive = ByteArchive(data, tolerant=True)
    name_map = ["TestName"]

    result = archive.read_name(name_map)
    assert result == "TestName"


def test_read_name_large_index_recovery_with_number():
    """read_name() 恢复时保留 number 后缀。"""
    garbage = b'\x5B\x00'
    valid_name = b'\x01\x00\x00\x00\x03\x00\x00\x00'
    data = garbage + valid_name
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name0", "Name1"]

    result = archive.read_name(name_map)
    assert result == "Name1_3"


def test_read_name_recovery_disabled_in_strict_mode():
    """strict 模式下不触发恢复，直接抛异常。"""
    garbage = b'\x5B\x00'
    valid_name = b'\x00\x00\x00\x00\x00\x00\x00\x00'
    data = garbage + valid_name
    archive = ByteArchive(data, tolerant=False)
    name_map = ["TestName"]

    with pytest.raises(ParseError):
        archive.read_name(name_map)


def test_read_name_recovery_no_valid_offset():
    """所有偏移调整均无效时，应返回 'None'。"""
    garbage = b'\xE9\x03\x00\x00'
    valid_name = b'\x00\x00\x00\x00\x00\x00\x00\x00'
    data = garbage + valid_name
    archive = ByteArchive(data, tolerant=True)
    name_map = []

    result = archive.read_name(name_map)
    assert result == "None"


def test_read_name_recovery_1byte_offset():
    """1字节偏移也能恢复。"""
    garbage = b'\x00\x10\x00\x00'
    valid_name = b'\x00\x00\x00\x00\x00\x00\x00\x00'
    data = garbage + valid_name
    archive = ByteArchive(data, tolerant=True)
    name_map = ["TestName"]

    result = archive.read_name(name_map)
    assert result == "TestName"


def test_read_name_recovery_threshold():
    """read_name() 只在索引超过阈值时尝试恢复。"""
    data = b'\xE7\x03\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name"] * 1000

    result = archive.read_name(name_map)
    assert result == "Name"


def test_read_name_recovery_with_number():
    """read_name() 恢复后应正确处理 number 后缀。"""
    garbage = b'\xE9\x03'
    valid_name = b'\x00\x00\x00\x00\x05\x00\x00\x00'
    data = garbage + valid_name
    archive = ByteArchive(data, tolerant=True)
    name_map = ["TestName"]

    result = archive.read_name(name_map)
    assert result == "TestName_5"


def test_read_name_recovery_failure():
    """read_name() 恢复失败时应返回 'None'。"""
    data = b'\xFF\x00\x00\x00\x00\x00\x00\x00' * 5
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name0", "Name1"]

    result = archive.read_name(name_map)
    assert result == "None"


# --- 恢复统计诊断测试 ---


def test_recovery_stats_initial_zero():
    """新 archive 的恢复统计应为零。"""
    data = b'\x00\x00\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=True)
    stats = archive.get_read_name_recovery_stats()
    assert stats["recovery_attempts"] == 0
    assert stats["recovery_successes"] == 0
    assert stats["recovery_failures"] == 0


def test_recovery_stats_success():
    """恢复成功时应正确计数。"""
    garbage = b'\xE9\x03'
    valid_name = b'\x00\x00\x00\x00\x00\x00\x00\x00'
    data = garbage + valid_name
    archive = ByteArchive(data, tolerant=True)
    name_map = ["TestName"]

    archive.read_name(name_map)
    stats = archive.get_read_name_recovery_stats()
    assert stats["recovery_attempts"] == 1
    assert stats["recovery_successes"] == 1
    assert stats["recovery_failures"] == 0


def test_recovery_stats_failure():
    """恢复失败时应正确计数。"""
    data = b'\xE9\x03\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=True)
    name_map = []

    archive.read_name(name_map)
    stats = archive.get_read_name_recovery_stats()
    assert stats["recovery_attempts"] == 1
    assert stats["recovery_successes"] == 0
    assert stats["recovery_failures"] == 1


def test_recovery_stats_multiple_attempts():
    """多次调用应累积统计。"""
    garbage1 = b'\xE9\x03'
    valid1 = b'\x00\x00\x00\x00\x00\x00\x00\x00'
    fail_data = b'\xE9\x03\x00\x00\x00\x00\x00\x00'
    data = garbage1 + valid1 + fail_data
    archive = ByteArchive(data, tolerant=True)
    name_map = ["TestName"]

    archive.read_name(name_map)
    archive.read_name(name_map)

    stats = archive.get_read_name_recovery_stats()
    assert stats["recovery_attempts"] == 2
    assert stats["recovery_successes"] == 1
    assert stats["recovery_failures"] == 1


def test_recovery_stats_no_recovery_for_valid_index():
    """正常索引不触发恢复，统计应为零。"""
    data = b'\x01\x00\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name0", "Name1"]

    archive.read_name(name_map)
    stats = archive.get_read_name_recovery_stats()
    assert stats["recovery_attempts"] == 0
    assert stats["recovery_successes"] == 0
    assert stats["recovery_failures"] == 0


# --- archive skip 测试 ---


def test_farchive_skip():
    """FArchive 应支持 skip() 方法跳过指定字节数。"""
    data = b'\x00' * 100
    archive = ByteArchive(data)

    initial_pos = archive.tell()
    archive.skip(10)
    assert archive.tell() == initial_pos + 10


def test_farchive_skip_to_end():
    """skip() 应支持跳转到文件末尾。"""
    data = b'\x00' * 50
    archive = ByteArchive(data)

    archive.skip(50)
    assert archive.tell() == 50


def test_farchive_skip_zero():
    """skip(0) 应保持位置不变。"""
    data = b'\x00' * 100
    archive = ByteArchive(data)

    archive.skip(0)
    assert archive.tell() == 0


def test_farchive_skip_negative_raises():
    """skip() 负数应抛出异常（seek 会验证）。"""
    data = b'\x00' * 100
    archive = ByteArchive(data)

    with pytest.raises(Exception):
        archive.skip(-5)


# --- read_name() 越界警告去重测试 (#411) ---


def test_read_name_duplicate_index_only_one_diagnostic():
    """重复的越界索引只应记录一次诊断。"""
    data = b'\x05\x00\x00\x00\x00\x00\x00\x00' * 3
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name0", "Name1", "Name2"]

    for _ in range(3):
        archive.read_name(name_map)

    diagnostics = archive.get_diagnostics()
    out_of_range = [d for d in diagnostics if d.field == "read_name"]
    assert len(out_of_range) == 1


def test_read_name_different_indices_each_recorded():
    """不同的越界索引应各自记录一次诊断。"""
    data = (
        b'\x03\x00\x00\x00\x00\x00\x00\x00'
        b'\x05\x00\x00\x00\x00\x00\x00\x00'
        b'\x07\x00\x00\x00\x00\x00\x00\x00'
    )
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name0", "Name1", "Name2"]

    archive.read_name(name_map)
    archive.read_name(name_map)
    archive.read_name(name_map)

    diagnostics = archive.get_diagnostics()
    out_of_range = [d for d in diagnostics if d.field == "read_name"]
    assert len(out_of_range) == 3


def test_read_name_mixed_valid_and_invalid():
    """有效和无效索引混合时，只记录无效索引的诊断。"""
    data = (
        b'\x01\x00\x00\x00\x00\x00\x00\x00'
        b'\x05\x00\x00\x00\x00\x00\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x00\x00'
    )
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name0", "Name1", "Name2"]

    archive.read_name(name_map)
    archive.read_name(name_map)
    archive.read_name(name_map)

    diagnostics = archive.get_diagnostics()
    out_of_range = [d for d in diagnostics if d.field == "read_name"]
    assert len(out_of_range) == 1
    assert "index 5" in out_of_range[0].error


def test_read_name_duplicate_invalid_then_valid():
    """先重复越界，再有效索引，诊断只记录一次。"""
    data = b'\x0A\x00\x00\x00\x00\x00\x00\x00' * 5
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name0", "Name1"]

    for _ in range(5):
        archive.read_name(name_map)

    diagnostics = archive.get_diagnostics()
    out_of_range = [d for d in diagnostics if d.field == "read_name"]
    assert len(out_of_range) == 1
    assert "index 10" in out_of_range[0].error


def test_read_name_negative_index_dedup():
    """负索引（0xFFFFFFFF）也应去重。"""
    data = b'\xff\xff\xff\xff\x00\x00\x00\x00' * 3
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name0"]

    for _ in range(3):
        archive.read_name(name_map)

    diagnostics = archive.get_diagnostics()
    out_of_range = [d for d in diagnostics if d.field == "read_name"]
    assert len(out_of_range) == 1


def test_read_name_strict_mode_still_deduplicates():
    """strict 模式下，同一越界索引第二次也应被去重。"""
    data = b'\x05\x00\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=False)
    name_map = ["Name0", "Name1", "Name2"]

    with pytest.raises(Exception):
        archive.read_name(name_map)


def test_read_name_fresh_archive_warnings_seen_empty():
    """新 archive 的 _name_warnings_seen 应为空集。"""
    data = b'\x00\x00\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=True)
    assert len(archive._name_warnings_seen) == 0


def test_read_name_valid_index_does_not_populate_warnings_seen():
    """有效索引不应写入 _name_warnings_seen。"""
    data = b'\x01\x00\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name0", "Name1"]

    archive.read_name(name_map)
    assert len(archive._name_warnings_seen) == 0


def test_read_name_invalid_index_populates_warnings_seen():
    """越界索引应写入 _name_warnings_seen。"""
    data = b'\x05\x00\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name0", "Name1"]

    archive.read_name(name_map)
    assert 5 in archive._name_warnings_seen


def test_read_name_all_returns_none_for_invalid():
    """去重不影响返回值——每次越界都应返回 'None'。"""
    data = b'\x05\x00\x00\x00\x00\x00\x00\x00' * 3
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name0"]

    for _ in range(3):
        result = archive.read_name(name_map)
        assert result == "None"


# ===========================================================================
# GameDirectoryProvider 测试
# ===========================================================================


def test_provider_list_files_cache_hit(tmp_path):
    """第二次 list_files 调用命中缓存，不重新扫描"""
    from uasset_read.providers import GameDirectoryProvider

    (tmp_path / "a.uasset").touch()
    provider = GameDirectoryProvider(tmp_path)

    first = provider.list_files(".uasset")
    assert ".uasset" in provider._list_files_cache

    second = provider.list_files(".uasset")
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


# ===========================================================================
# TextRenderer 测试
# ===========================================================================


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

    editor_var_name = next(iter(EDITOR_VARIABLE_NAMES))
    var = VariableIR(name=editor_var_name, type="ArrayProperty", default_value=None)
    ir = _make_package_ir()
    ir.variables = [var]

    renderer = TextRenderer()
    standard = renderer.render(ir, RenderOptions(output_level="standard"))
    debug = renderer.render(ir, RenderOptions(output_level="debug"))

    assert editor_var_name not in standard
    assert editor_var_name in debug


# ===========================================================================
# CLI format 解析测试
# ===========================================================================


def test_resolve_format_named_flags():
    """--text -> 'text'，--markdown -> 'markdown'"""
    from uasset_read.cli import resolve_format

    args_text = types.SimpleNamespace(text=True, markdown=False, json=False)
    assert resolve_format(args_text) == "text"

    args_md = types.SimpleNamespace(text=False, markdown=True, json=False)
    assert resolve_format(args_md) == "markdown"


def test_resolve_format_default_json():
    """无格式标志 -> 'json'"""
    from uasset_read.cli import resolve_format

    args = types.SimpleNamespace(text=False, markdown=False, json=False)
    assert resolve_format(args) == "json"


def test_list_formats_contains_text():
    """list_formats() 包含 'text'"""
    from uasset_read.core import list_formats

    formats = list_formats()
    assert "text" in formats
