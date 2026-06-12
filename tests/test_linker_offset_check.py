"""tests/test_linker_offset_check.py — PackageLinker 偏移越界检查测试。

验证：
1. 越界 PackageIndex 返回 None 而非崩溃
2. 诊断信息包含 offset 和 file_size
3. serial_offset 溢出值（如 4294967296）被正确拦截
"""
from unittest.mock import MagicMock
import pytest

from uasset_read.serializers.object_resources import PackageIndex, ObjectImport, ObjectExport
from uasset_read.link.linker import PackageLinker
from uasset_read.link.object_instance import UObjectInstance
from uasset_read.models.diagnostics import OffsetRangeDiagnostic


def _make_linker(
    import_count: int = 0,
    export_count: int = 0,
    file_size: int = 1024,
) -> PackageLinker:
    """创建一个用于测试的 PackageLinker 实例。"""
    archive = MagicMock()
    archive._file_size = file_size
    summary = MagicMock()
    name_map = ["TestName"]
    import_map = []
    for i in range(import_count):
        imp = MagicMock(spec=ObjectImport)
        imp.class_package = 0
        imp.class_name = 0
        imp.outer_index = PackageIndex(0)
        imp.object_name = 0
        import_map.append(imp)
    export_map = []
    for i in range(export_count):
        exp = MagicMock(spec=ObjectExport)
        exp.class_index = PackageIndex(0)
        exp.super_index = PackageIndex(0)
        exp.outer_index = PackageIndex(0)
        exp.object_name = 0
        exp.serial_offset = 0
        exp.serial_size = 0
        export_map.append(exp)
    linker = PackageLinker(archive, summary, name_map, import_map, export_map)
    linker.link()
    return linker


class TestResolvePackageIndexBounds:
    """resolve_package_index() 边界检查。"""

    def test_null_index_returns_none(self):
        """Null PackageIndex 返回 None，无诊断。"""
        linker = _make_linker(import_count=2, export_count=2)
        result = linker.resolve_package_index(PackageIndex(0))
        assert result is None
        assert len(linker.diagnostics) == 0

    def test_valid_export_index(self):
        """有效 export index 正确解析。"""
        linker = _make_linker(export_count=3)
        result = linker.resolve_package_index(PackageIndex(1))
        assert result is not None
        assert result.object_name == "TestName"

    def test_valid_import_index(self):
        """有效 import index 正确解析。"""
        linker = _make_linker(import_count=3)
        result = linker.resolve_package_index(PackageIndex(-1))
        assert result is not None

    def test_export_index_out_of_bounds_returns_none(self):
        """越界 export index 返回 None 并记录诊断。"""
        linker = _make_linker(export_count=2)
        result = linker.resolve_package_index(PackageIndex(100))
        assert result is None
        diags = linker.diagnostics
        assert len(diags) >= 1
        d = diags[-1]
        assert d.module == "linker"
        assert d.field == "PackageIndex"
        assert d.export_index == 99
        assert d.file_size == 1024
        assert "越界" in d.error

    def test_import_index_out_of_bounds_returns_none(self):
        """越界 import index 返回 None 并记录诊断。"""
        linker = _make_linker(import_count=2)
        result = linker.resolve_package_index(PackageIndex(-100))
        assert result is None
        diags = linker.diagnostics
        assert len(diags) >= 1
        d = diags[-1]
        assert d.module == "linker"
        assert d.field == "PackageIndex"
        assert d.import_index == 99
        assert "越界" in d.error

    def test_huge_export_index_no_crash(self):
        """极大 export index（如 4294967296）不崩溃，返回 None。"""
        linker = _make_linker(export_count=1)
        # PackageIndex(4294967296) => is_export=True, to_export_index()=4294967295
        result = linker.resolve_package_index(PackageIndex(4294967296))
        assert result is None
        assert len(linker.diagnostics) >= 1

    def test_huge_negative_index_no_crash(self):
        """极大负数 import index 不崩溃，返回 None。"""
        linker = _make_linker(import_count=1)
        result = linker.resolve_package_index(PackageIndex(-4294967296))
        assert result is None
        assert len(linker.diagnostics) >= 1


class TestPreloadOffsetValidation:
    """preload() serial_offset 验证。"""

    def test_preload_with_overflow_offset_records_diagnostic(self):
        """serial_offset=4294967296 被拦截，记录诊断，不崩溃。"""
        linker = _make_linker(export_count=1, file_size=1024)
        # 手动设置 export 的 serial_offset 和 serial_size
        linker._export_objects[0].serial_offset = 4294967296
        linker._export_objects[0].serial_size = 100
        # 不应崩溃
        linker.preload(0)
        # 应标记为已预加载（容错）
        assert linker._export_objects[0]._preloaded is True
        # 应记录诊断
        diags = [d for d in linker.diagnostics if d.source == "preload"]
        assert len(diags) >= 1
        d = diags[-1]
        assert d.target_offset == 4294967296
        assert d.file_size == 1024

    def test_preload_with_negative_offset_records_diagnostic(self):
        """serial_offset=-1 被拦截。"""
        linker = _make_linker(export_count=1, file_size=1024)
        linker._export_objects[0].serial_offset = -1
        linker._export_objects[0].serial_size = 100
        linker.preload(0)
        assert linker._export_objects[0]._preloaded is True
        diags = [d for d in linker.diagnostics if d.source == "preload"]
        assert len(diags) >= 1
        assert diags[-1].target_offset == -1

    def test_preload_with_offset_plus_size_overflow(self):
        """serial_offset+serial_size 超出文件大小时记录诊断。"""
        linker = _make_linker(export_count=1, file_size=1024)
        linker._export_objects[0].serial_offset = 900
        linker._export_objects[0].serial_size = 200  # 900+200=1100 > 1024
        linker.preload(0)
        assert linker._export_objects[0]._preloaded is True
        diags = [d for d in linker.diagnostics if d.field == "serial_size"]
        assert len(diags) >= 1

    def test_preload_valid_offset_seeks(self):
        """有效 offset 正常 seek（mock archive）。"""
        linker = _make_linker(export_count=1, file_size=1024)
        linker._export_objects[0].serial_offset = 100
        linker._export_objects[0].serial_size = 50
        # mock archive.seek 不应抛出异常
        # preload 会调用 parse_properties_from_export，用 try/except 隔离
        try:
            linker.preload(0)
        except (TypeError, AttributeError):
            # mock summary 不完整，但 seek 应已被调用
            pass
        # 验证至少有一次 seek 到有效 offset
        seek_calls = [c for c in linker._archive.seek.call_args_list if c.args[0] == 100]
        assert len(seek_calls) >= 1, f"Expected seek(100), got calls: {linker._archive.seek.call_args_list}"

    def test_preload_zero_size_skips(self):
        """serial_size=0 跳过 preload，不产生诊断。"""
        linker = _make_linker(export_count=1, file_size=1024)
        linker._export_objects[0].serial_offset = 100
        linker._export_objects[0].serial_size = 0
        linker.preload(0)
        assert linker._export_objects[0]._preloaded is True
        assert len(linker.diagnostics) == 0


class TestCreateExportInstancesValidation:
    """_create_export_instances() 早期 serial_offset 验证。"""

    def test_overflow_offset_sanitized_to_zero(self):
        """溢出 serial_offset 在创建实例时被归零。"""
        linker = _make_linker(export_count=0, file_size=1024)
        # 手动构造一个带溢出 offset 的 export_map
        exp = MagicMock(spec=ObjectExport)
        exp.class_index = PackageIndex(0)
        exp.super_index = PackageIndex(0)
        exp.outer_index = PackageIndex(0)
        exp.object_name = "BadExport"
        exp.serial_offset = 4294967296
        exp.serial_size = 100
        linker._export_map = [exp]
        linker._create_export_instances()
        assert len(linker._export_objects) == 1
        # serial_offset 应被归零
        assert linker._export_objects[0].serial_offset == 0
        assert linker._export_objects[0].serial_size == 0
        # 应记录诊断
        diags = [d for d in linker.diagnostics if d.source == "_create_export_instances"]
        assert len(diags) == 1
        assert diags[0].target_offset == 4294967296

    def test_negative_offset_sanitized_to_zero(self):
        """负数 serial_offset 在创建实例时被归零。"""
        linker = _make_linker(export_count=0, file_size=1024)
        exp = MagicMock(spec=ObjectExport)
        exp.class_index = PackageIndex(0)
        exp.super_index = PackageIndex(0)
        exp.outer_index = PackageIndex(0)
        exp.object_name = "NegExport"
        exp.serial_offset = -1
        exp.serial_size = 50
        linker._export_map = [exp]
        linker._create_export_instances()
        assert linker._export_objects[0].serial_offset == 0
        assert linker._export_objects[0].serial_size == 0


class TestDiagnosticsProperty:
    """diagnostics 属性暴露诊断记录。"""

    def test_diagnostics_initially_empty(self):
        """初始状态 diagnostics 为空。"""
        linker = _make_linker()
        assert linker.diagnostics == []

    def test_diagnostics_accumulate(self):
        """多次越界操作的诊断记录累积。"""
        linker = _make_linker(export_count=1)
        linker.resolve_package_index(PackageIndex(100))
        linker.resolve_package_index(PackageIndex(200))
        assert len(linker.diagnostics) == 2

    def test_diagnostic_to_dict(self):
        """诊断记录可序列化为 dict。"""
        linker = _make_linker(export_count=1, file_size=2048)
        linker.resolve_package_index(PackageIndex(100))
        d = linker.diagnostics[0].to_dict()
        assert d["kind"] == "offset_range_diagnostic"
        assert d["module"] == "linker"
        assert d["file_size"] == 2048
        assert "越界" in d["error"]
