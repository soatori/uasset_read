"""Kismet 函数解析器 + 未知 token 测试。

合并自：
- test_function_resolver_enhanced.py: FunctionRefResolver 增强功能与集成测试
- test_pipeline_function_failure.py: decompile_single_function 失败处理回归测试（去重 BPGC/Set）
- test_unknown_tokens.py: 未知/游戏特定 token 处理测试
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from uasset_read.exceptions import ParseError
from uasset_read.kismet.archive import FKismetArchive
from uasset_read.kismet.expressions import EXPR_CLASS_MAP, EX_Nothing
from uasset_read.kismet.expressions.base import KismetExpression
from uasset_read.kismet.expressions.functions import (
    EX_CallMath,
    EX_CallMulticastDelegate,
    EX_FinalFunction,
    EX_LocalFinalFunction,
    EX_LocalVirtualFunction,
    EX_VirtualFunction,
)
from uasset_read.kismet.expressions.special import (
    EX_Unknown6E,
    EX_Unknown6F,
    EX_UnknownF9,
    EX_UnknownFD,
    EX_UnknownFE,
)
from uasset_read.kismet.function_resolver import FunctionRefResolver
from uasset_read.kismet.pipeline import decompile_single_function
from uasset_read.kismet.result import KismetDecompiledResult
from uasset_read.kismet.tokens import EExprToken


# ============================================================================
# Helper factories (from test_function_resolver_enhanced.py)
# ============================================================================


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


# ─────────────────────────────────────────────────────────────────────────────
# 合并自 test_function_resolver.py 的基础功能测试
# ─────────────────────────────────────────────────────────────────────────────

def _make_linker_simple():
    """创建 mock linker（简单版本）。"""
    return MagicMock()


def _make_instance_simple(object_name, object_class=None, outer=None):
    """创建 mock UObjectInstance（简单版本）。"""
    inst = MagicMock()
    inst.object_name = object_name
    inst.object_class = object_class
    inst.outer = outer
    return inst


class TestResolve:
    """resolve() 各种 StackNode 解析场景。"""

    def test_resolve_null_index(self):
        """stack_node=0 直接返回 None，不访问 linker。"""
        linker = _make_linker_simple()
        resolver = FunctionRefResolver(linker)

        result = resolver.resolve(0)

        assert result is None
        linker.resolve_package_index.assert_not_called()

    def test_resolve_import_index(self):
        """负数 StackNode（import）应正确解析。"""
        linker = _make_linker_simple()
        inst = _make_instance_simple("K2Node_CallFunction", object_class="KismetSystemLibrary")
        linker.resolve_package_index.return_value = inst

        resolver = FunctionRefResolver(linker)
        result = resolver.resolve(-1)

        assert result == ("KismetSystemLibrary", "K2Node_CallFunction")
        linker.resolve_package_index.assert_called_once()

    def test_resolve_export_index(self):
        """正数 StackNode（export）应正确解析。"""
        linker = _make_linker_simple()
        inst = _make_instance_simple("MyFunc", object_class="MyClass")
        linker.resolve_package_index.return_value = inst

        resolver = FunctionRefResolver(linker)
        result = resolver.resolve(1)

        assert result == ("MyClass", "MyFunc")
        linker.resolve_package_index.assert_called_once()

    def test_resolve_blueprint_function(self):
        """BlueprintGeneratedClass 应取 outer.object_name 作为类名。"""
        linker = _make_linker_simple()
        outer_inst = _make_instance_simple("MyBlueprint_C")
        inst = _make_instance_simple(
            "ExecuteUbergraph_0",
            object_class="BlueprintGeneratedClass",
            outer=outer_inst,
        )
        linker.resolve_package_index.return_value = inst

        resolver = FunctionRefResolver(linker)
        result = resolver.resolve(1)

        assert result == ("MyBlueprint_C", "ExecuteUbergraph_0")

    def test_resolve_null_package_index(self):
        """linker 返回 None 时应返回 None。"""
        linker = _make_linker_simple()
        linker.resolve_package_index.return_value = None

        resolver = FunctionRefResolver(linker)
        result = resolver.resolve(1)

        assert result is None

    def test_resolve_caches_result(self):
        """连续两次 resolve 相同 stack_node 应只查询 linker 一次。"""
        linker = _make_linker_simple()
        inst = _make_instance_simple("Func", object_class="Cls")
        linker.resolve_package_index.return_value = inst

        resolver = FunctionRefResolver(linker)
        resolver.resolve(5)
        resolver.resolve(5)

        linker.resolve_package_index.assert_called_once()

    def test_resolve_non_blueprint_class(self):
        """非 BlueprintGeneratedClass 应直接使用 object_class。"""
        linker = _make_linker_simple()
        inst = _make_instance_simple("ReceiveBeginPlay", object_class="Actor")
        linker.resolve_package_index.return_value = inst

        resolver = FunctionRefResolver(linker)
        result = resolver.resolve(2)

        assert result == ("Actor", "ReceiveBeginPlay")

    def test_resolve_class_none_fallback(self):
        """object_class 为 None 时应回退到 Unknown。"""
        linker = _make_linker_simple()
        inst = _make_instance_simple("SomeFunc", object_class=None)
        linker.resolve_package_index.return_value = inst

        resolver = FunctionRefResolver(linker)
        result = resolver.resolve(3)

        assert result == ("Unknown", "SomeFunc")


class TestResolveString:
    """resolve_string() 格式化输出。"""

    def test_resolve_string_format(self):
        """正常解析应返回 ClassName::FuncName 格式。"""
        linker = _make_linker_simple()
        inst = _make_instance_simple("MyFunc", object_class="MyClass")
        linker.resolve_package_index.return_value = inst

        resolver = FunctionRefResolver(linker)
        result = resolver.resolve_string(1)

        assert result == "MyClass::MyFunc"

    def test_resolve_string_fallback(self):
        """无法解析时应返回 Function_{stack_node} 格式。"""
        linker = _make_linker_simple()
        linker.resolve_package_index.return_value = None

        resolver = FunctionRefResolver(linker)
        result = resolver.resolve_string(42)

        assert result == "Function_42"

    def test_resolve_string_null_returns_fallback(self):
        """stack_node=0 应回退到 Function_0。"""
        linker = _make_linker_simple()
        resolver = FunctionRefResolver(linker)

        result = resolver.resolve_string(0)

        assert result == "Function_0"


class TestBuildCache:
    """build_cache() 预扫描表达式列表构建缓存。"""

    def test_build_cache_final_function(self):
        """EX_FinalFunction 应被扫描并缓存。"""
        linker = _make_linker_simple()
        inst = _make_instance_simple("Func", object_class="Cls")
        linker.resolve_package_index.return_value = inst

        expr = EX_FinalFunction(StackNode=10)
        resolver = FunctionRefResolver(linker)
        resolver.build_cache([expr])

        assert 10 in resolver._cache
        assert resolver._cache[10] == ("Cls", "Func")

    def test_build_cache_call_math(self):
        """EX_CallMath 应被扫描并缓存。"""
        linker = _make_linker_simple()
        inst = _make_instance_simple("MathFunc", object_class="MathLibrary")
        linker.resolve_package_index.return_value = inst

        expr = EX_CallMath(StackNode=20)
        resolver = FunctionRefResolver(linker)
        resolver.build_cache([expr])

        assert 20 in resolver._cache
        assert resolver._cache[20] == ("MathLibrary", "MathFunc")

    def test_build_cache_local_final_function(self):
        """EX_LocalFinalFunction 应被扫描并缓存。"""
        linker = _make_linker_simple()
        inst = _make_instance_simple("LocalFunc", object_class="LocalCls")
        linker.resolve_package_index.return_value = inst

        expr = EX_LocalFinalFunction(StackNode=30)
        resolver = FunctionRefResolver(linker)
        resolver.build_cache([expr])

        assert 30 in resolver._cache
        assert resolver._cache[30] == ("LocalCls", "LocalFunc")

    def test_build_cache_nested_parameters(self):
        """应递归处理 Parameters 中的嵌套函数表达式。"""
        linker = _make_linker_simple()

        def side_effect(pkg_idx):
            mapping = {
                -1: _make_instance_simple("InnerFunc", object_class="InnerCls"),
                -2: _make_instance_simple("OuterFunc", object_class="OuterCls"),
            }
            return mapping.get(pkg_idx.index)

        linker.resolve_package_index.side_effect = side_effect

        inner = EX_FinalFunction(StackNode=-1)
        outer = EX_FinalFunction(StackNode=-2, Parameters=[inner])
        resolver = FunctionRefResolver(linker)
        resolver.build_cache([outer])

        assert -1 in resolver._cache
        assert -2 in resolver._cache

    def test_build_cache_skips_zero_stack_node(self):
        """StackNode=0 的表达式不应被缓存。"""
        linker = _make_linker_simple()
        expr = EX_FinalFunction(StackNode=0)
        resolver = FunctionRefResolver(linker)
        resolver.build_cache([expr])

        assert 0 not in resolver._cache
        linker.resolve_package_index.assert_not_called()

    def test_build_cache_skips_non_function_expressions(self):
        """非函数调用表达式应被跳过。"""
        linker = _make_linker_simple()

        class _DummyExpr(KismetExpression):
            @property
            def Token(self):
                return 0xFF

        expr = _DummyExpr()
        resolver = FunctionRefResolver(linker)
        resolver.build_cache([expr])

        linker.resolve_package_index.assert_not_called()


# ============================================================================
# Helper factories (from test_pipeline_function_failure.py)
# ============================================================================


def _make_mock_export(object_name: str = "TestFunction") -> MagicMock:
    """创建 mock ObjectExport。"""
    export = MagicMock()
    export.object_name = object_name
    return export


def _make_mock_archive() -> MagicMock:
    """创建 mock FArchive。"""
    return MagicMock()


def _make_mock_summary() -> MagicMock:
    """创建 mock PackageFileSummary。"""
    return MagicMock()


def _fake_expressions():
    """创建最小的表达式列表（包含一个 Return token）。"""
    expr = MagicMock()
    expr.StatementIndex = 0
    return [expr]


# ---------------------------------------------------------------------------
# 1. tolerant 模式异常捕获
# ---------------------------------------------------------------------------

class TestDecompileSingleFunctionException:
    """tolerant 模式下异常应返回失败结果而非 None。"""

    @patch("uasset_read.kismet.pipeline.extract_and_parse")
    def test_tolerant_exception_returns_failed_result(self, mock_extract):
        """异常在 tolerant 模式下应返回 bytecode_status='failed' 的结果。"""
        mock_extract.side_effect = ValueError("corrupted bytecode")

        result = decompile_single_function(
            archive=_make_mock_archive(),
            export=_make_mock_export("BrokenFunc"),
            summary=_make_mock_summary(),
            name_map=[],
            import_map=[],
            export_map=[],
            tolerant=True,
        )

        assert result is not None
        assert isinstance(result, KismetDecompiledResult)
        assert result.bytecode_status == "failed"
        assert result.function_name == "BrokenFunc"
        assert any("corrupted bytecode" in r for r in result.fallback_reasons)

    @patch("uasset_read.kismet.pipeline.extract_and_parse")
    def test_non_tolerant_exception_raises(self, mock_extract):
        """非 tolerant 模式下异常应继续 raise。"""
        mock_extract.side_effect = ValueError("corrupted bytecode")

        with pytest.raises(ValueError, match="corrupted bytecode"):
            decompile_single_function(
                archive=_make_mock_archive(),
                export=_make_mock_export(),
                summary=_make_mock_summary(),
                name_map=[],
                import_map=[],
                export_map=[],
                tolerant=False,
            )


# ---------------------------------------------------------------------------
# 2. tolerant 模式 error 返回
# ---------------------------------------------------------------------------

class TestDecompileSingleFunctionError:
    """tolerant 模式下 error 非空应返回失败结果。"""

    @patch("uasset_read.kismet.pipeline.extract_and_parse")
    def test_tolerant_error_returns_failed_result(self, mock_extract):
        """extract_and_parse 返回 error 时应返回 bytecode_status='failed'。"""
        mock_extract.return_value = ([], "parse error occurred", "none")

        result = decompile_single_function(
            archive=_make_mock_archive(),
            export=_make_mock_export("ErrorFunc"),
            summary=_make_mock_summary(),
            name_map=[],
            import_map=[],
            export_map=[],
            tolerant=True,
        )

        assert result is not None
        assert result.bytecode_status == "failed"
        assert result.function_name == "ErrorFunc"
        assert any("parse error occurred" in r for r in result.fallback_reasons)

    @patch("uasset_read.kismet.pipeline.extract_and_parse")
    def test_non_tolerant_error_returns_none(self, mock_extract):
        """非 tolerant 模式下 error 非空应返回 None（原有行为）。"""
        mock_extract.return_value = ([], "parse error occurred", "none")

        result = decompile_single_function(
            archive=_make_mock_archive(),
            export=_make_mock_export(),
            summary=_make_mock_summary(),
            name_map=[],
            import_map=[],
            export_map=[],
            tolerant=False,
        )

        assert result is None


# ---------------------------------------------------------------------------
# 3. tolerant 模式空表达式
# ---------------------------------------------------------------------------

class TestDecompileSingleFunctionEmptyExpressions:
    """tolerant 模式下空表达式应返回失败结果。"""

    @patch("uasset_read.kismet.pipeline.extract_and_parse")
    def test_tolerant_empty_expressions_returns_failed_result(self, mock_extract):
        """空表达式列表在 tolerant 模式下应返回 bytecode_status='failed'。"""
        mock_extract.return_value = ([], None, "none")

        result = decompile_single_function(
            archive=_make_mock_archive(),
            export=_make_mock_export("EmptyFunc"),
            summary=_make_mock_summary(),
            name_map=[],
            import_map=[],
            export_map=[],
            tolerant=True,
        )

        assert result is not None
        assert result.bytecode_status == "failed"
        assert result.function_name == "EmptyFunc"
        assert any("no bytecode" in r for r in result.fallback_reasons)


# ---------------------------------------------------------------------------
# 4. 成功路径不被破坏
# ---------------------------------------------------------------------------

class TestDecompileSingleFunctionSuccess:
    """正常路径不受影响。"""

    @patch("uasset_read.kismet.pipeline.extract_and_parse")
    def test_successful_decompilation(self, mock_extract):
        """正常解析应返回 bytecode_status='parsed' 的结果。"""
        mock_extract.return_value = (_fake_expressions(), None, "function_export")

        result = decompile_single_function(
            archive=_make_mock_archive(),
            export=_make_mock_export("GoodFunc"),
            summary=_make_mock_summary(),
            name_map=[],
            import_map=[],
            export_map=[],
            tolerant=True,
        )

        assert result is not None
        assert result.bytecode_status == "parsed"
        assert result.function_name == "GoodFunc"


# ---------------------------------------------------------------------------
# 5. 一个函数失败 + 一个函数成功 → 后处理合并
# ---------------------------------------------------------------------------

class TestMixedFunctionResults:
    """一个函数失败、一个函数成功时，后处理正确合并结果。"""

    @patch("uasset_read.kismet.pipeline.extract_and_parse")
    def test_one_fail_one_success_post_processing(self, mock_extract):
        """一个函数失败、一个函数成功时，后处理正确合并结果。"""
        call_count = 0

        def side_effect(archive, export, summary, name_map, import_map, export_map, tolerant=True):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("malformed bytecode in function 1")
            else:
                return (_fake_expressions(), None, "function_export")

        mock_extract.side_effect = side_effect

        archive = _make_mock_archive()
        summary = _make_mock_summary()
        export1 = _make_mock_export("FailingFunc")
        export2 = _make_mock_export("SucceedingFunc")

        # 模拟 decompile_uasset 的后处理逻辑
        results = []
        for export in [export1, export2]:
            result = decompile_single_function(
                archive=archive,
                export=export,
                summary=summary,
                name_map=[],
                import_map=[],
                export_map=[],
                tolerant=True,
            )
            if result is not None:
                results.append(result)

        # 应包含两个结果：一个失败、一个成功
        assert len(results) == 2

        failed = [r for r in results if r.bytecode_status == "failed"]
        succeeded = [r for r in results if r.bytecode_status == "parsed"]

        assert len(failed) == 1
        assert len(succeeded) == 1
        assert failed[0].function_name == "FailingFunc"
        assert succeeded[0].function_name == "SucceedingFunc"
        assert any("malformed bytecode" in r for r in failed[0].fallback_reasons)

    @patch("uasset_read.kismet.pipeline.extract_and_parse")
    def test_all_fail_results_returned(self, mock_extract):
        """所有函数都失败时，tolerant 模式返回全部失败结果。"""
        mock_extract.side_effect = ValueError("global corruption")

        # 创建两个 export
        export1 = _make_mock_export("Func1")
        export2 = _make_mock_export("Func2")

        results = []
        for export in [export1, export2]:
            result = decompile_single_function(
                archive=_make_mock_archive(),
                export=export,
                summary=_make_mock_summary(),
                name_map=[],
                import_map=[],
                export_map=[],
                tolerant=True,
            )
            results.append(result)

        # 两个都应返回失败结果
        assert all(r is not None for r in results)
        assert all(r.bytecode_status == "failed" for r in results)
        assert results[0].function_name == "Func1"
        assert results[1].function_name == "Func2"


# ============================================================================
# Helper function (from test_unknown_tokens.py)
# ============================================================================


def _archive(data: bytes, tolerant: bool = True) -> FKismetArchive:
    return FKismetArchive(data, "test-bytecode", [], tolerant=tolerant)


# ---------------------------------------------------------------------------
# Token 枚举定义验证
# ---------------------------------------------------------------------------

class TestTokenDefinitions:
    """验证 token 枚举值与已知 UE5 扩展对齐。"""

    def test_ex_6e_value(self):
        assert EExprToken.EX_6E == 0x6E

    def test_ex_6f_value(self):
        assert EExprToken.EX_6F == 0x6F

    def test_ex_f9_value(self):
        assert EExprToken.EX_F9 == 0xF9

    def test_ex_fd_value(self):
        assert EExprToken.EX_FD == 0xFD

    def test_ex_fe_value(self):
        assert EExprToken.EX_FE == 0xFE

    def test_all_five_tokens_exist(self):
        """五个 token 都应在 EExprToken 中定义。"""
        for name in ("EX_6E", "EX_6F", "EX_F9", "EX_FD", "EX_FE"):
            assert hasattr(EExprToken, name), f"Missing EExprToken.{name}"


# ---------------------------------------------------------------------------
# EXPR_CLASS_MAP 映射验证
# ---------------------------------------------------------------------------

class TestExprClassMapMapping:
    """验证 EXPR_CLASS_MAP 为每个 token 注册了正确的表达式类。"""

    @pytest.mark.parametrize(
        "token,expr_cls",
        [
            (EExprToken.EX_6E, EX_Unknown6E),
            (EExprToken.EX_6F, EX_Unknown6F),
            (EExprToken.EX_F9, EX_UnknownF9),
            (EExprToken.EX_FD, EX_UnknownFD),
            (EExprToken.EX_FE, EX_UnknownFE),
        ],
        ids=["0x6E", "0x6F", "0xF9", "0xFD", "0xFE"],
    )
    def test_expr_class_map_contains_token(self, token, expr_cls):
        assert EXPR_CLASS_MAP.get(token) is expr_cls


# ---------------------------------------------------------------------------
# 表达式类基础属性验证
# ---------------------------------------------------------------------------

class TestExpressionClassBasics:
    """验证每个占位表达式类的基本属性。"""

    @pytest.mark.parametrize(
        "expr_cls,token",
        [
            (EX_Unknown6E, EExprToken.EX_6E),
            (EX_Unknown6F, EExprToken.EX_6F),
            (EX_UnknownF9, EExprToken.EX_F9),
            (EX_UnknownFD, EExprToken.EX_FD),
            (EX_UnknownFE, EExprToken.EX_FE),
        ],
        ids=["0x6E", "0x6F", "0xF9", "0xFD", "0xFE"],
    )
    def test_token_property_matches(self, expr_cls, token):
        expr = expr_cls()
        assert expr.Token == token

    @pytest.mark.parametrize(
        "token_byte",
        [0x6E, 0x6F, 0xF9, 0xFD, 0xFE],
        ids=["0x6E", "0x6F", "0xF9", "0xFD", "0xFE"],
    )
    def test_to_dict_has_inst_key(self, token_byte):
        """通过 archive 创建的表达式应能正确序列化为 dict。"""
        archive = _archive(bytes([token_byte]))
        expr = archive.read_expression()
        d = expr.to_dict()
        assert "Inst" in d
        assert "StatementIndex" in d

    @pytest.mark.parametrize(
        "expr_cls",
        [EX_Unknown6E, EX_Unknown6F, EX_UnknownF9, EX_UnknownFD, EX_UnknownFE],
        ids=["0x6E", "0x6F", "0xF9", "0xFD", "0xFE"],
    )
    def test_default_value_is_empty_bytes(self, expr_cls):
        expr = expr_cls()
        assert expr.Value == b""


# ---------------------------------------------------------------------------
# FKismetArchive 解析集成测试
# ---------------------------------------------------------------------------


class TestFKismetArchiveParsing:
    """验证 FKismetArchive.read_expression() 能正确解析这些 token。"""

    @pytest.mark.parametrize(
        "token_byte,expr_cls",
        [
            (0x6E, EX_Unknown6E),
            (0x6F, EX_Unknown6F),
            (0xF9, EX_UnknownF9),
            (0xFD, EX_UnknownFD),
            (0xFE, EX_UnknownFE),
        ],
        ids=["0x6E", "0x6F", "0xF9", "0xFD", "0xFE"],
    )
    def test_read_expression_single_token(self, token_byte, expr_cls):
        """单个 token 应被正确解析为对应的表达式类。"""
        archive = _archive(bytes([token_byte]))
        expr = archive.read_expression()
        assert isinstance(expr, expr_cls)
        assert archive.tell() == 1

    @pytest.mark.parametrize(
        "token_byte",
        [0x6E, 0x6F, 0xF9, 0xFD, 0xFE],
        ids=["0x6E", "0x6F", "0xF9", "0xFD", "0xFE"],
    )
    def test_token_in_non_tolerant_mode(self, token_byte):
        """非 tolerant 模式下，这些 token 应被正常处理（已在 EXPR_CLASS_MAP 中）。"""
        archive = _archive(bytes([token_byte]), tolerant=False)
        expr = archive.read_expression()
        assert expr.Token.value == token_byte

    def test_mixed_tokens_sequence(self):
        """混合多个未知 token 的序列应被完整解析。"""
        data = bytes([0x6E, 0x6F, 0xF9, 0xFD, 0xFE])
        archive = _archive(data)
        results = []
        while archive.tell() < len(data):
            results.append(archive.read_expression())
        assert len(results) == 5
        expected_types = [EX_Unknown6E, EX_Unknown6F, EX_UnknownF9, EX_UnknownFD, EX_UnknownFE]
        for expr, expected_cls in zip(results, expected_types):
            assert isinstance(expr, expected_cls)

    def test_token_followed_by_end_of_script(self):
        """未知 token 后跟 EX_EndOfScript 应正常终止。"""
        data = bytes([0x6E, 0x53])  # EX_6E then EX_EndOfScript
        archive = _archive(data)
        expr1 = archive.read_expression()
        expr2 = archive.read_expression()
        assert isinstance(expr1, EX_Unknown6E)
        assert expr2.Token == EExprToken.EX_EndOfScript


# ---------------------------------------------------------------------------
# StatementIndex 验证
# ---------------------------------------------------------------------------

class TestStatementIndex:
    """验证 StatementIndex 正确设置。"""

    @pytest.mark.parametrize(
        "token_byte",
        [0x6E, 0x6F, 0xF9, 0xFD, 0xFE],
        ids=["0x6E", "0x6F", "0xF9", "0xFD", "0xFE"],
    )
    def test_statement_index_is_zero_for_first_token(self, token_byte):
        archive = _archive(bytes([token_byte]))
        expr = archive.read_expression()
        assert expr.StatementIndex == 0

    def test_statement_index_increments(self):
        data = bytes([0x6E, 0x6F])
        archive = _archive(data)
        expr1 = archive.read_expression()
        expr2 = archive.read_expression()
        assert expr1.StatementIndex == 0
        assert expr2.StatementIndex == 1


# ---------------------------------------------------------------------------
# 枚举外 opcode 容错处理 (#401)
# ---------------------------------------------------------------------------

class TestEnumOutOfRangeOpcode:
    """验证不在 EExprToken 枚举中的 opcode 在 tolerant 模式下不抛 ValueError。"""

    def test_enum_out_of_range_opcode_tolerant(self):
        """0x03 不在 EExprToken 中，tolerant 模式应跳过它并继续解析。"""
        from uasset_read.kismet.bytecode_extractor import parse_bytecode_stream
        from uasset_read.kismet.tokens import EExprToken

        # 0x03 不在枚举中, 0x53 = EX_EndOfScript
        result = parse_bytecode_stream(bytes([0x03, 0x53]), [], tolerant=True)
        assert len(result) == 1
        assert result[0].Token == EExprToken.EX_EndOfScript

    def test_enum_out_of_range_opcode_strict_raises(self):
        """strict 模式下，枚举外 opcode 应抛 ParseError（不是 ValueError）。"""
        from uasset_read.kismet.bytecode_extractor import parse_bytecode_stream

        with pytest.raises(ParseError, match="Unknown EExprToken"):
            parse_bytecode_stream(bytes([0x03, 0x53]), [], tolerant=False)

    def test_enum_out_of_range_opcode_diagnostic_visible(self):
        """枚举外 opcode 在 tolerant 模式下应产生可见诊断。"""
        from uasset_read.kismet.bytecode_extractor import parse_bytecode_stream

        archive = _archive(bytes([0x03, 0x53]), tolerant=True)
        # read_expression 应成功跳过 0x03
        expr = archive.read_expression()
        # 第一个可解析的 token 是 0x53 (EX_EndOfScript)
        from uasset_read.kismet.tokens import EExprToken
        assert expr.Token == EExprToken.EX_EndOfScript


# ---------------------------------------------------------------------------
# Kismet archive resource-boundary regression tests
# (merged from test_archive_safety.py)
# ---------------------------------------------------------------------------


def test_unknown_6e_consumes_its_opcode() -> None:
    archive = _archive(bytes([EExprToken.EX_6E]))

    expression = archive.read_expression()

    assert expression.Token == EExprToken.EX_6E
    assert archive.tell() == 1


def test_read_expression_rejects_handler_that_makes_no_progress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uasset_read.kismet import archive as archive_module

    class NonProgressingExpression(EX_Nothing):
        @classmethod
        def from_archive(cls, archive, name_map):
            archive.seek(archive.tell() - 1)
            return cls()

    monkeypatch.setitem(
        archive_module.EXPR_CLASS_MAP,
        EExprToken.EX_Nothing,
        NonProgressingExpression,
    )
    archive = _archive(bytes([EExprToken.EX_Nothing]))

    with pytest.raises(ParseError, match="made no progress.*offset 0"):
        archive.read_expression()


def test_read_expression_array_is_bounded_by_remaining_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive = _archive(b"\x00\x00")
    monkeypatch.setattr(archive, "read_expression", lambda: EX_Nothing())

    with pytest.raises(ParseError, match="expression array exceeded 2 items"):
        archive.read_expression_array(EExprToken.EX_EndArray)


def test_read_expression_rejects_excessive_recursion_depth() -> None:
    data = bytes([EExprToken.EX_Return]) * 257 + bytes([EExprToken.EX_Nothing])
    archive = _archive(data)

    with pytest.raises(ParseError, match="recursion depth exceeded 256"):
        archive.read_expression()
