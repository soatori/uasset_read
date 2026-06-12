"""FunctionRefResolver 增强功能测试。

覆盖：
- 统计跟踪（resolve_attempts, resolve_failures, unresolved_refs）
- is_local_function() 蓝图本地函数检测
- resolve_virtual_function_class() 虚函数类名解析
- get_statistics() / get_unresolved_report() 统计报告
- build_cache() 增强（虚函数、多播委托）
- 与 KismetTranslator 集成
"""
from unittest.mock import MagicMock

import pytest

from uasset_read.kismet.function_resolver import FunctionRefResolver
from uasset_read.kismet.expressions.base import KismetExpression
from uasset_read.kismet.expressions.functions import (
    EX_CallMath,
    EX_CallMulticastDelegate,
    EX_FinalFunction,
    EX_LocalFinalFunction,
    EX_LocalVirtualFunction,
    EX_VirtualFunction,
)


def _make_linker():
    """创建 mock linker。"""
    linker = MagicMock()
    linker._export_objects = []
    linker.export_objects.return_value = []
    return linker


def _make_instance(
    object_name,
    object_class=None,
    outer=None,
    is_export=True,
    package_index=1,
):
    """创建 mock UObjectInstance。"""
    inst = MagicMock()
    inst.object_name = object_name
    inst.object_class = object_class
    inst.outer = outer
    inst.is_export = is_export
    inst.package_index = package_index
    return inst


# ===========================================================================
# 统计跟踪
# ===========================================================================


class TestStatistics:
    """统计计数器功能。"""

    def test_resolve_tracks_attempts(self):
        """每次 resolve() 调用应增加 attempts 计数。"""
        linker = _make_linker()
        inst = _make_instance("Func", object_class="Cls")
        linker.resolve_package_index.return_value = inst

        resolver = FunctionRefResolver(linker)
        resolver.resolve(1)
        resolver.resolve(2)
        resolver.resolve(3)

        stats = resolver.get_statistics()
        assert stats["resolve_attempts"] == 3

    def test_resolve_tracks_failures(self):
        """解析失败应增加 failures 计数。"""
        linker = _make_linker()
        linker.resolve_package_index.return_value = None

        resolver = FunctionRefResolver(linker)
        resolver.resolve(1)
        resolver.resolve(2)

        stats = resolver.get_statistics()
        assert stats["resolve_attempts"] == 2
        assert stats["resolve_failures"] == 2

    def test_resolve_tracks_unresolved_refs(self):
        """失败的 StackNode 应记录在 unresolved_refs 中。"""
        linker = _make_linker()
        linker.resolve_package_index.return_value = None

        resolver = FunctionRefResolver(linker)
        resolver.resolve(42)
        resolver.resolve(42)
        resolver.resolve(99)

        stats = resolver.get_statistics()
        assert stats["unresolved_count"] == 2
        assert stats["unresolved_refs"][42] == 2
        assert stats["unresolved_refs"][99] == 1

    def test_resolve_null_index_tracked(self):
        """stack_node=0 应被统计为失败。"""
        linker = _make_linker()
        resolver = FunctionRefResolver(linker)

        resolver.resolve(0)

        stats = resolver.get_statistics()
        assert stats["resolve_attempts"] == 1
        assert stats["resolve_failures"] == 1
        assert 0 in stats["unresolved_refs"]

    def test_success_rate_calculation(self):
        """成功率应正确计算。"""
        linker = _make_linker()

        def side_effect(pkg_idx):
            if pkg_idx.index > 0:
                return _make_instance("Func", object_class="Cls")
            return None

        linker.resolve_package_index.side_effect = side_effect

        resolver = FunctionRefResolver(linker)
        resolver.resolve(1)   # 成功
        resolver.resolve(2)   # 成功
        resolver.resolve(-1)  # 失败

        stats = resolver.get_statistics()
        assert stats["resolve_attempts"] == 3
        assert stats["resolve_failures"] == 1
        assert stats["success_rate"] == pytest.approx(66.7, abs=0.1)

    def test_statistics_empty_resolver(self):
        """空解析器应返回 100% 成功率。"""
        linker = _make_linker()
        resolver = FunctionRefResolver(linker)

        stats = resolver.get_statistics()
        assert stats["resolve_attempts"] == 0
        assert stats["resolve_failures"] == 0
        assert stats["success_rate"] == 100.0
        assert stats["unresolved_count"] == 0
        assert stats["unresolved_refs"] == {}

    def test_cache_hit_still_counts_attempt(self):
        """缓存命中也应计入 attempts。"""
        linker = _make_linker()
        inst = _make_instance("Func", object_class="Cls")
        linker.resolve_package_index.return_value = inst

        resolver = FunctionRefResolver(linker)
        resolver.resolve(5)
        resolver.resolve(5)  # 缓存命中

        stats = resolver.get_statistics()
        assert stats["resolve_attempts"] == 2
        assert stats["resolve_failures"] == 0


# ===========================================================================
# is_local_function
# ===========================================================================


class TestIsLocalFunction:
    """蓝图本地函数检测。"""

    def test_export_with_blueprint_outer_is_local(self):
        """export 对象且 outer 是 BlueprintGeneratedClass → 本地函数。"""
        linker = _make_linker()
        outer = _make_instance("MyBlueprint_C", object_class="BlueprintGeneratedClass")
        inst = _make_instance(
            "MyFunction",
            object_class="Function",
            outer=outer,
            is_export=True,
        )
        linker.resolve_package_index.return_value = inst

        resolver = FunctionRefResolver(linker)
        assert resolver.is_local_function(1) is True

    def test_negative_index_is_not_local(self):
        """负数 StackNode（import）不是本地函数。"""
        linker = _make_linker()
        resolver = FunctionRefResolver(linker)

        assert resolver.is_local_function(-1) is False

    def test_zero_is_not_local(self):
        """stack_node=0 不是本地函数。"""
        linker = _make_linker()
        resolver = FunctionRefResolver(linker)

        assert resolver.is_local_function(0) is False

    def test_unresolvable_is_not_local(self):
        """无法解析的 StackNode 不是本地函数。"""
        linker = _make_linker()
        linker.resolve_package_index.return_value = None

        resolver = FunctionRefResolver(linker)
        assert resolver.is_local_function(1) is False

    def test_export_without_blueprint_outer(self):
        """export 对象但 outer 不是 BlueprintGeneratedClass → 也视为本地。"""
        linker = _make_linker()
        outer = _make_instance("Engine", object_class="Package")
        inst = _make_instance(
            "SomeFunc",
            object_class="Function",
            outer=outer,
            is_export=True,
        )
        linker.resolve_package_index.return_value = inst

        resolver = FunctionRefResolver(linker)
        assert resolver.is_local_function(1) is True

    def test_import_is_not_local(self):
        """import 对象（is_export=False）不是本地函数。"""
        linker = _make_linker()
        inst = _make_instance(
            "K2Node_CallFunction",
            object_class="KismetSystemLibrary",
            is_export=False,
        )
        linker.resolve_package_index.return_value = inst

        resolver = FunctionRefResolver(linker)
        assert resolver.is_local_function(1) is False


# ===========================================================================
# resolve_virtual_function_class
# ===========================================================================


class TestResolveVirtualFunctionClass:
    """虚函数类名解析。"""

    def test_resolve_matching_export(self):
        """在 export 对象中找到匹配函数名时返回类名。"""
        linker = _make_linker()
        outer = _make_instance("MyBlueprint_C", object_class="BlueprintGeneratedClass")
        inst = _make_instance(
            "ReceiveBeginPlay",
            object_class="Function",
            outer=outer,
        )
        linker._export_objects = [inst]
        linker.export_objects.return_value = [inst]

        resolver = FunctionRefResolver(linker)
        result = resolver.resolve_virtual_function_class("ReceiveBeginPlay")

        assert result == "MyBlueprint_C"

    def test_resolve_no_match(self):
        """无匹配时返回 None。"""
        linker = _make_linker()
        linker._export_objects = []
        linker.export_objects.return_value = []

        resolver = FunctionRefResolver(linker)
        result = resolver.resolve_virtual_function_class("NonExistentFunc")

        assert result is None

    def test_resolve_empty_name(self):
        """空函数名返回 None。"""
        linker = _make_linker()
        resolver = FunctionRefResolver(linker)

        assert resolver.resolve_virtual_function_class("") is None

    def test_resolve_caches_result(self):
        """结果应被缓存。"""
        linker = _make_linker()
        inst = _make_instance("TestFunc", object_class="TestClass")
        linker._export_objects = [inst]
        linker.export_objects.return_value = [inst]

        resolver = FunctionRefResolver(linker)
        result1 = resolver.resolve_virtual_function_class("TestFunc")
        result2 = resolver.resolve_virtual_function_class("TestFunc")

        assert result1 == result2
        assert "TestFunc" in resolver._virtual_class_cache

    def test_resolve_non_blueprint_class(self):
        """非 BlueprintGeneratedClass 应直接使用 object_class。"""
        linker = _make_linker()
        inst = _make_instance("Tick", object_class="Actor")
        linker._export_objects = [inst]
        linker.export_objects.return_value = [inst]

        resolver = FunctionRefResolver(linker)
        result = resolver.resolve_virtual_function_class("Tick")

        assert result == "Actor"

    def test_resolve_none_class_fallback(self):
        """object_class 为 None 时回退到 Unknown。"""
        linker = _make_linker()
        inst = _make_instance("SomeFunc", object_class=None)
        linker._export_objects = [inst]
        linker.export_objects.return_value = [inst]

        resolver = FunctionRefResolver(linker)
        result = resolver.resolve_virtual_function_class("SomeFunc")

        assert result == "Unknown"


# ===========================================================================
# get_unresolved_report
# ===========================================================================


class TestUnresolvedReport:
    """未解析引用报告。"""

    def test_report_empty_when_all_resolved(self):
        """所有引用都解析成功时返回空字符串。"""
        linker = _make_linker()
        inst = _make_instance("Func", object_class="Cls")
        linker.resolve_package_index.return_value = inst

        resolver = FunctionRefResolver(linker)
        resolver.resolve(1)

        assert resolver.get_unresolved_report() == ""

    def test_report_contains_statistics(self):
        """报告应包含统计信息。"""
        linker = _make_linker()
        linker.resolve_package_index.return_value = None

        resolver = FunctionRefResolver(linker)
        resolver.resolve(42)
        resolver.resolve(42)
        resolver.resolve(99)

        report = resolver.get_unresolved_report()
        assert "函数引用解析统计" in report
        assert "总尝试: 3" in report
        assert "失败: 3" in report
        assert "成功率: 0.0%" in report

    def test_report_contains_unresolved_details(self):
        """报告应包含未解析引用详情。"""
        linker = _make_linker()
        linker.resolve_package_index.return_value = None

        resolver = FunctionRefResolver(linker)
        resolver.resolve(42)
        resolver.resolve(42)

        report = resolver.get_unresolved_report()
        assert "Function_42: 2 次" in report

    def test_report_sorted_by_count(self):
        """未解析引用应按出现次数降序排列。"""
        linker = _make_linker()
        linker.resolve_package_index.return_value = None

        resolver = FunctionRefResolver(linker)
        resolver.resolve(10)
        resolver.resolve(20)
        resolver.resolve(20)
        resolver.resolve(20)

        report = resolver.get_unresolved_report()
        lines = report.split("\n")
        # 找到详情部分
        detail_lines = [l for l in lines if "Function_" in l and "次" in l]
        assert len(detail_lines) >= 2
        # Function_20 应在 Function_10 前面（出现次数更多）
        idx_20 = next(i for i, l in enumerate(detail_lines) if "Function_20" in l)
        idx_10 = next(i for i, l in enumerate(detail_lines) if "Function_10" in l)
        assert idx_20 < idx_10

    def test_report_limits_to_10_entries(self):
        """报告最多显示 10 条未解析引用。"""
        linker = _make_linker()
        linker.resolve_package_index.return_value = None

        resolver = FunctionRefResolver(linker)
        for i in range(15):
            resolver.resolve(i + 100)

        report = resolver.get_unresolved_report()
        assert "还有 5 个" in report


# ===========================================================================
# build_cache 增强
# ===========================================================================


class TestBuildCacheEnhanced:
    """build_cache() 增强功能。"""

    def test_build_cache_virtual_function(self):
        """EX_VirtualFunction 应被扫描并解析类名。"""
        linker = _make_linker()
        inst = _make_instance("ReceiveTick", object_class="Actor")
        linker._export_objects = [inst]
        linker.export_objects.return_value = [inst]

        expr = EX_VirtualFunction(VirtualFunctionName="ReceiveTick")
        resolver = FunctionRefResolver(linker)
        resolver.build_cache([expr])

        assert "ReceiveTick" in resolver._virtual_class_cache
        assert resolver._virtual_class_cache["ReceiveTick"] == "Actor"

    def test_build_cache_local_virtual_function(self):
        """EX_LocalVirtualFunction 应被扫描并解析类名。"""
        linker = _make_linker()
        inst = _make_instance("CustomEvent", object_class="MyBP_C")
        linker._export_objects = [inst]
        linker.export_objects.return_value = [inst]

        expr = EX_LocalVirtualFunction(VirtualFunctionName="CustomEvent")
        resolver = FunctionRefResolver(linker)
        resolver.build_cache([expr])

        assert "CustomEvent" in resolver._virtual_class_cache

    def test_build_cache_multicast_delegate(self):
        """EX_CallMulticastDelegate 应被扫描并缓存 StackNode。"""
        linker = _make_linker()
        inst = _make_instance("OnClicked", object_class="Delegate")
        linker.resolve_package_index.return_value = inst

        expr = EX_CallMulticastDelegate(StackNode=15)
        resolver = FunctionRefResolver(linker)
        resolver.build_cache([expr])

        assert 15 in resolver._cache

    def test_build_cache_virtual_function_with_params(self):
        """EX_VirtualFunction 的参数中的嵌套表达式应被递归处理。"""
        linker = _make_linker()
        func_inst = _make_instance("InnerFunc", object_class="InnerCls")
        vfunc_inst = _make_instance("OuterVFunc", object_class="OuterCls")
        linker.resolve_package_index.return_value = func_inst
        linker._export_objects = [vfunc_inst]
        linker.export_objects.return_value = [vfunc_inst]

        inner = EX_FinalFunction(StackNode=5)
        outer = EX_VirtualFunction(
            VirtualFunctionName="OuterVFunc",
            Parameters=[inner],
        )
        resolver = FunctionRefResolver(linker)
        resolver.build_cache([outer])

        assert 5 in resolver._cache
        assert "OuterVFunc" in resolver._virtual_class_cache

    def test_build_cache_mixed_expressions(self):
        """混合类型表达式应全部被处理。"""
        linker = _make_linker()

        def side_effect(pkg_idx):
            mapping = {
                10: _make_instance("FinalFunc", object_class="FinalCls"),
                20: _make_instance("MathFunc", object_class="MathCls"),
                30: _make_instance("LocalFunc", object_class="LocalCls"),
                40: _make_instance("DelegateFunc", object_class="DelegateCls"),
            }
            return mapping.get(pkg_idx.index)

        linker.resolve_package_index.side_effect = side_effect
        linker._export_objects = [
            _make_instance("VirtualFunc", object_class="VirtualCls"),
        ]
        linker.export_objects.return_value = linker._export_objects

        expressions = [
            EX_FinalFunction(StackNode=10),
            EX_CallMath(StackNode=20),
            EX_LocalFinalFunction(StackNode=30),
            EX_CallMulticastDelegate(StackNode=40),
            EX_VirtualFunction(VirtualFunctionName="VirtualFunc"),
        ]

        resolver = FunctionRefResolver(linker)
        resolver.build_cache(expressions)

        assert 10 in resolver._cache
        assert 20 in resolver._cache
        assert 30 in resolver._cache
        assert 40 in resolver._cache
        assert "VirtualFunc" in resolver._virtual_class_cache


# ===========================================================================
# KismetTranslator 集成
# ===========================================================================


class TestTranslatorIntegration:
    """与 KismetTranslator 的集成测试。"""

    def test_virtual_function_with_class_prefix(self):
        """EX_VirtualFunction 应输出 类名::函数名 格式。"""
        from uasset_read.kismet.translator import KismetTranslator

        linker = _make_linker()
        inst = _make_instance("ReceiveBeginPlay", object_class="Actor")
        linker._export_objects = [inst]
        linker.export_objects.return_value = [inst]
        linker.resolve_package_index.return_value = None

        translator = KismetTranslator(linker=linker)
        expr = EX_VirtualFunction(VirtualFunctionName="ReceiveBeginPlay")
        result = translator.line_cpp(expr)

        assert result == "Actor::ReceiveBeginPlay()"

    def test_virtual_function_without_resolver(self):
        """无 resolver 时虚函数应只输出函数名。"""
        from uasset_read.kismet.translator import KismetTranslator

        translator = KismetTranslator()
        expr = EX_VirtualFunction(VirtualFunctionName="SomeFunc")
        result = translator.line_cpp(expr)

        assert result == "SomeFunc()"

    def test_local_final_function_as_this_call(self):
        """蓝图本地函数应输出 this->FuncName 格式。"""
        from uasset_read.kismet.translator import KismetTranslator

        linker = _make_linker()
        outer = _make_instance("MyBP_C", object_class="BlueprintGeneratedClass")
        inst = _make_instance(
            "MyLocalFunc",
            object_class="Function",
            outer=outer,
            is_export=True,
        )

        def side_effect(pkg_idx):
            if pkg_idx.index == 5:
                return inst
            return None

        linker.resolve_package_index.side_effect = side_effect

        translator = KismetTranslator(linker=linker)
        expr = EX_LocalFinalFunction(StackNode=5)
        result = translator.line_cpp(expr)

        assert result == "this->MyLocalFunc()"

    def test_local_final_function_external_import(self):
        """外部 import 函数应输出 ClassName::FuncName 格式。"""
        from uasset_read.kismet.translator import KismetTranslator

        linker = _make_linker()
        inst = _make_instance(
            "ExternalFunc",
            object_class="ExternalClass",
            is_export=False,
        )

        def side_effect(pkg_idx):
            if pkg_idx.index == -1:
                return inst
            return None

        linker.resolve_package_index.side_effect = side_effect

        translator = KismetTranslator(linker=linker)
        expr = EX_LocalFinalFunction(StackNode=-1)
        result = translator.line_cpp(expr)

        assert result == "ExternalClass::ExternalFunc()"

    def test_virtual_function_class_not_found(self):
        """虚函数类名未找到时应只输出函数名。"""
        from uasset_read.kismet.translator import KismetTranslator

        linker = _make_linker()
        linker._export_objects = []
        linker.export_objects.return_value = []

        translator = KismetTranslator(linker=linker)
        expr = EX_VirtualFunction(VirtualFunctionName="UnknownFunc")
        result = translator.line_cpp(expr)

        assert result == "UnknownFunc()"

    def test_local_virtual_function_with_class(self):
        """EX_LocalVirtualFunction 应同样解析类名。"""
        from uasset_read.kismet.translator import KismetTranslator

        linker = _make_linker()
        inst = _make_instance("CustomEvent", object_class="MyBP_C")
        linker._export_objects = [inst]
        linker.export_objects.return_value = [inst]
        linker.resolve_package_index.return_value = None

        translator = KismetTranslator(linker=linker)
        expr = EX_LocalVirtualFunction(VirtualFunctionName="CustomEvent")
        result = translator.line_cpp(expr)

        assert result == "MyBP_C::CustomEvent()"
