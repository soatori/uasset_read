"""linker.py 安全修复测试 — Sub 1/4/5。

验证：
1. ObjectProperty/WeakObjectProperty 的 int 和 PackageIndex 值都能被正确解析
2. serial_size 负值被检测并标记失败
3. serial_size == 0 检查在偏移校验之后执行
"""
from unittest.mock import MagicMock
import pytest

from uasset_read.serializers.object_resources import PackageIndex, ObjectImport, ObjectExport
from uasset_read.link.linker import PackageLinker
from uasset_read.link.object_instance import UObjectInstance


# ---- helpers ----

def _make_linker(
    export_count: int = 0,
    file_size: int = 1024,
) -> PackageLinker:
    archive = MagicMock()
    archive._file_size = file_size
    summary = MagicMock()
    name_map = ["TestName"]
    import_map: list = []
    export_map: list = []
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


# ======================================================================
# Sub 1: _resolve_property_references / _resolve_weak_references
# ======================================================================

class TestResolvePropertyReferences:
    """ObjectProperty 值可以是 int 或 PackageIndex。"""

    def test_int_value_resolved(self):
        """int 值的 ObjectProperty 被正确解析。"""
        linker = _make_linker(export_count=2, file_size=1024)
        inst = linker._export_objects[0]
        inst._preloaded = True
        # export index 2 → PackageIndex(2)
        inst.serialized_properties = [
            {"type": "ObjectProperty", "name": "TestProp", "value": 2}
        ]
        linker._resolve_property_references()
        assert "TestProp" in inst.property_references
        assert inst.property_references["TestProp"] is linker._export_objects[1]

    def test_package_index_value_resolved(self):
        """PackageIndex 值的 ObjectProperty 被正确解析。"""
        linker = _make_linker(export_count=2, file_size=1024)
        inst = linker._export_objects[0]
        inst._preloaded = True
        inst.serialized_properties = [
            {"type": "ObjectProperty", "name": "TestProp", "value": PackageIndex(2)}
        ]
        linker._resolve_property_references()
        assert "TestProp" in inst.property_references
        assert inst.property_references["TestProp"] is linker._export_objects[1]

    def test_null_int_value_not_resolved(self):
        """int 值 0（null）不会被解析。"""
        linker = _make_linker(export_count=1, file_size=1024)
        inst = linker._export_objects[0]
        inst._preloaded = True
        inst.serialized_properties = [
            {"type": "ObjectProperty", "name": "NullProp", "value": 0}
        ]
        linker._resolve_property_references()
        assert "NullProp" not in getattr(inst, "property_references", {})

    def test_null_package_index_value_not_resolved(self):
        """PackageIndex(0)（null）不会被解析。"""
        linker = _make_linker(export_count=1, file_size=1024)
        inst = linker._export_objects[0]
        inst._preloaded = True
        inst.serialized_properties = [
            {"type": "ObjectProperty", "name": "NullProp", "value": PackageIndex(0)}
        ]
        linker._resolve_property_references()
        assert "NullProp" not in getattr(inst, "property_references", {})

    def test_out_of_bounds_package_index_not_resolved(self):
        """越界 PackageIndex 不会崩溃，只是不解析。"""
        linker = _make_linker(export_count=1, file_size=1024)
        inst = linker._export_objects[0]
        inst._preloaded = True
        inst.serialized_properties = [
            {"type": "ObjectProperty", "name": "BadProp", "value": PackageIndex(999)}
        ]
        linker._resolve_property_references()
        assert "BadProp" not in getattr(inst, "property_references", {})

    def test_non_property_dict_skipped(self):
        """非 dict 类型的属性被跳过。"""
        linker = _make_linker(export_count=1, file_size=1024)
        inst = linker._export_objects[0]
        inst._preloaded = True
        inst.serialized_properties = ["not_a_dict", 42, None]
        linker._resolve_property_references()
        # 不应崩溃
        assert not hasattr(inst, "property_references") or len(inst.property_references) == 0


class TestResolveWeakReferences:
    """WeakObjectProperty 值可以是 int 或 PackageIndex。"""

    def _make_linker_with_import(self) -> PackageLinker:
        """创建带 1 个 import 和 2 个 export 的 linker。"""
        archive = MagicMock()
        archive._file_size = 1024
        summary = MagicMock()
        name_map = ["TestName"]
        imp = MagicMock(spec=ObjectImport)
        imp.class_package = 0
        imp.class_name = 0
        imp.outer_index = PackageIndex(0)
        imp.object_name = 0
        export_map = []
        for i in range(2):
            exp = MagicMock(spec=ObjectExport)
            exp.class_index = PackageIndex(0)
            exp.super_index = PackageIndex(0)
            exp.outer_index = PackageIndex(0)
            exp.object_name = 0
            exp.serial_offset = 0
            exp.serial_size = 0
            export_map.append(exp)
        linker = PackageLinker(archive, summary, name_map, [imp], export_map)
        linker.link()
        return linker

    def test_int_value_resolved(self):
        """int 值的 WeakObjectProperty 被正确解析。"""
        linker = self._make_linker_with_import()
        inst = linker._export_objects[0]
        inst._preloaded = True
        # import index 0 → PackageIndex(-1)
        inst.serialized_properties = [
            {"type": "WeakObjectProperty", "name": "WeakProp", "value": -1}
        ]
        linker._resolve_weak_references()
        assert len(inst.weak_references) == 1
        assert inst.weak_references[0] is linker._import_objects[0]

    def test_package_index_value_resolved(self):
        """PackageIndex 值的 WeakObjectProperty 被正确解析。"""
        linker = self._make_linker_with_import()
        inst = linker._export_objects[0]
        inst._preloaded = True
        inst.serialized_properties = [
            {"type": "WeakObjectProperty", "name": "WeakProp", "value": PackageIndex(-1)}
        ]
        linker._resolve_weak_references()
        assert len(inst.weak_references) == 1
        assert inst.weak_references[0] is linker._import_objects[0]

    def test_null_int_value_not_resolved(self):
        """int 值 0（null）不会被添加到 weak_references。"""
        linker = _make_linker(export_count=1, file_size=1024)
        inst = linker._export_objects[0]
        inst._preloaded = True
        inst.serialized_properties = [
            {"type": "WeakObjectProperty", "name": "NullWeak", "value": 0}
        ]
        linker._resolve_weak_references()
        assert len(inst.weak_references) == 0

    def test_null_package_index_value_not_resolved(self):
        """PackageIndex(0)（null）不会被添加到 weak_references。"""
        linker = _make_linker(export_count=1, file_size=1024)
        inst = linker._export_objects[0]
        inst._preloaded = True
        inst.serialized_properties = [
            {"type": "WeakObjectProperty", "name": "NullWeak", "value": PackageIndex(0)}
        ]
        linker._resolve_weak_references()
        assert len(inst.weak_references) == 0

    def test_out_of_bounds_package_index_not_resolved(self):
        """越界 PackageIndex 不会崩溃。"""
        linker = _make_linker(export_count=1, file_size=1024)
        inst = linker._export_objects[0]
        inst._preloaded = True
        inst.serialized_properties = [
            {"type": "WeakObjectProperty", "name": "BadWeak", "value": PackageIndex(999)}
        ]
        linker._resolve_weak_references()
        assert len(inst.weak_references) == 0


# ======================================================================
# Sub 4: serial_size 负值检查
# ======================================================================

class TestPreloadNegativeSerialSize:
    """serial_size 为负数时应被检测并标记失败。"""

    def test_negative_serial_size_recorded_diagnostic(self):
        """serial_size=-100 产生诊断，不崩溃，不进入 parse。"""
        linker = _make_linker(export_count=1, file_size=1024)
        linker._export_objects[0].serial_offset = 100
        linker._export_objects[0].serial_size = -100
        linker.preload(0)
        assert linker._export_objects[0]._preloaded is True
        diags = [d for d in linker.diagnostics if d.source == "preload"]
        assert len(diags) >= 1

    def test_negative_serial_size_no_parse(self):
        """serial_size 为负数时不应进入 parse_properties_from_export。"""
        linker = _make_linker(export_count=1, file_size=1024)
        linker._export_objects[0].serial_offset = 100
        linker._export_objects[0].serial_size = -1
        linker.preload(0)
        assert linker._export_objects[0]._preloaded is True
        # serialized_properties 应为空（未进入 parse）
        assert len(linker._export_objects[0].serialized_properties) == 0


# ======================================================================
# Sub 5: serial_size == 0 检查顺序
# ======================================================================

class TestPreloadZeroSizeCheckOrder:
    """serial_size == 0 检查应在偏移校验之后执行。"""

    def test_zero_size_with_invalid_offset_still_records_diagnostic(self):
        """serial_size=0 但 serial_offset 无效时，应先记录偏移诊断。"""
        linker = _make_linker(export_count=1, file_size=1024)
        linker._export_objects[0].serial_offset = -1
        linker._export_objects[0].serial_size = 0
        linker.preload(0)
        assert linker._export_objects[0]._preloaded is True
        # 应记录 serial_offset 越界诊断（即使 serial_size=0）
        diags = [d for d in linker.diagnostics if d.source == "preload"]
        assert len(diags) >= 1

    def test_zero_size_with_out_of_range_offset_records_diagnostic(self):
        """serial_size=0 但 serial_offset 超出文件范围时，应先记录偏移诊断。"""
        linker = _make_linker(export_count=1, file_size=1024)
        linker._export_objects[0].serial_offset = 2000  # > file_size
        linker._export_objects[0].serial_size = 0
        linker.preload(0)
        assert linker._export_objects[0]._preloaded is True
        diags = [d for d in linker.diagnostics if d.source == "preload"]
        assert len(diags) >= 1
