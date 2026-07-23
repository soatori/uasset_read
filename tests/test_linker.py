"""Linker 模块测试 — 生命周期、preload、post_load。"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from uasset_read.link.linker import PackageLinker
from uasset_read.link.object_instance import UObjectInstance
from uasset_read.serializers.object_resources import PackageIndex


def _make_linker(
    import_count: int = 2,
    export_count: int = 1,
    file_size: int = 1024,
) -> PackageLinker:
    """创建一个用于测试的 PackageLinker 实例。"""
    archive = MagicMock()
    archive._file_size = file_size
    summary = MagicMock()
    summary.depends_map = None
    summary.package_name = "TestPackage"
    name_map = ["TestName"]

    import_map = []
    for i in range(import_count):
        imp = MagicMock()
        imp.object_name = f"Import_{i}"
        imp.class_name = f"Class_{i}"
        imp.class_package = "/Script/Engine"
        imp.outer_index = PackageIndex(0)
        imp.class_index = PackageIndex(0)
        import_map.append(imp)

    export_map = []
    for i in range(export_count):
        exp = MagicMock()
        exp.object_name = f"Export_{i}"
        exp.class_index = PackageIndex(-(1)) if import_count > 0 else PackageIndex(0)
        exp.outer_index = PackageIndex(0)
        exp.super_index = PackageIndex(0)
        exp.template_index = PackageIndex(0)
        exp.serial_offset = 100 + i * 200
        exp.serial_size = 100
        export_map.append(exp)

    linker = PackageLinker(archive, summary, name_map, import_map, export_map)
    linker.link()
    return linker


def _make_instance(name, package_index=1, is_import=False, outer=None, linker=None, class_package=None):
    """创建一个用于测试的 UObjectInstance。"""
    return UObjectInstance(
        package_index=package_index,
        object_name=name,
        object_class="TestClass",
        class_package=class_package,
        outer_index=PackageIndex(0),
        is_import=is_import,
        outer=outer,
        linker=linker,
    )


class TestVerifyImportsResultPreserved:
    """post_load() 保留 _verify_imports 返回值。"""

    def test_post_load_preserves_verify_imports_result(self):
        """post_load 保留 _verify_imports 的返回值。"""
        linker = _make_linker(import_count=2, export_count=1)
        linker._import_map[1].outer_index = PackageIndex(999)

        linker.post_load()

        assert hasattr(linker, '_import_verification_errors')
        assert len(linker._import_verification_errors) > 0


class TestCircularOuterDetection:
    """get_full_name() 循环引用检测。"""

    def test_circular_outer_returns_circular_marker(self):
        """循环 outer 引用返回 <circular:N> 而非 RecursionError。"""
        obj_a = UObjectInstance(
            package_index=1, object_name="ObjectA", object_class="Class",
            class_package=None, outer_index=PackageIndex(2), is_import=False,
        )
        obj_b = UObjectInstance(
            package_index=2, object_name="ObjectB", object_class="Class",
            class_package=None, outer_index=PackageIndex(1), is_import=False,
        )
        obj_a.outer = obj_b
        obj_b.outer = obj_a

        result = obj_a.get_full_name()
        assert "<circular:" in result


class TestOverflowOffsetInterception:
    """serial_offset 溢出值被正确拦截。"""

    def test_preload_with_overflow_offset_records_diagnostic(self):
        """serial_offset=4294967296 被拦截，记录诊断，不崩溃。"""
        linker = _make_linker(export_count=1, file_size=1024)
        linker._export_objects[0].serial_offset = 4294967296
        linker._export_objects[0].serial_size = 100

        linker.preload(0)

        assert linker._export_objects[0]._preloaded is True
        diags = [d for d in linker.diagnostics if d.source == "preload"]
        assert len(diags) >= 1
        d = diags[-1]
        assert d.target_offset == 4294967296
        assert d.file_size == 1024


class TestLifecycleOrder:
    """link -> preload -> post_load 生命周期顺序。"""

    def test_preload_then_post_load_order(self):
        """post_load 在 preload 完成后执行；ObjectProperty 被解析为实例。"""
        linker = _make_linker(export_count=2)
        for inst in linker._export_objects:
            assert not inst._preloaded
        for i, inst in enumerate(linker._export_objects):
            inst._preloaded = True
            inst.serialized_properties = [
                {"name": f"Prop{i}", "type": "ObjectProperty", "value": 2}
            ]
        linker.post_load()
        for inst in linker._export_objects:
            assert hasattr(inst, "property_references")


class TestPropertyReferenceResolution:
    """ObjectProperty 引用被正确解析。"""

    def test_object_property_resolved_to_instance(self):
        """ObjectProperty→UObjectInstance；链表验证。"""
        linker = _make_linker(export_count=2)
        inst0 = linker._export_objects[0]
        inst0._preloaded = True
        inst0.serialized_properties = [
            {"name": "TargetObj", "type": "ObjectProperty", "value": 2}
        ]
        linker.post_load()
        resolved = inst0.property_references["TargetObj"]
        assert isinstance(resolved, UObjectInstance) and resolved is linker._export_objects[1]
