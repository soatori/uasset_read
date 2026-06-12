"""FunctionRefResolver 单元测试。"""
from unittest.mock import MagicMock

from uasset_read.kismet.function_resolver import FunctionRefResolver
from uasset_read.kismet.expressions.base import KismetExpression
from uasset_read.kismet.expressions.functions import (
    EX_FinalFunction,
    EX_CallMath,
    EX_LocalFinalFunction,
)


def _make_linker():
    """创建 mock linker。"""
    return MagicMock()


def _make_instance(object_name, object_class=None, outer=None):
    """创建 mock UObjectInstance。"""
    inst = MagicMock()
    inst.object_name = object_name
    inst.object_class = object_class
    inst.outer = outer
    return inst


class TestResolve:
    """resolve() 各种 StackNode 解析场景。"""

    def test_resolve_null_index(self):
        """stack_node=0 直接返回 None，不访问 linker。"""
        linker = _make_linker()
        resolver = FunctionRefResolver(linker)

        result = resolver.resolve(0)

        assert result is None
        linker.resolve_package_index.assert_not_called()

    def test_resolve_import_index(self):
        """负数 StackNode（import）应正确解析。"""
        linker = _make_linker()
        inst = _make_instance("K2Node_CallFunction", object_class="KismetSystemLibrary")
        linker.resolve_package_index.return_value = inst

        resolver = FunctionRefResolver(linker)
        result = resolver.resolve(-1)

        assert result == ("KismetSystemLibrary", "K2Node_CallFunction")
        linker.resolve_package_index.assert_called_once()

    def test_resolve_export_index(self):
        """正数 StackNode（export）应正确解析。"""
        linker = _make_linker()
        inst = _make_instance("MyFunc", object_class="MyClass")
        linker.resolve_package_index.return_value = inst

        resolver = FunctionRefResolver(linker)
        result = resolver.resolve(1)

        assert result == ("MyClass", "MyFunc")
        linker.resolve_package_index.assert_called_once()

    def test_resolve_blueprint_function(self):
        """BlueprintGeneratedClass 应取 outer.object_name 作为类名。"""
        linker = _make_linker()
        outer_inst = _make_instance("MyBlueprint_C")
        inst = _make_instance(
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
        linker = _make_linker()
        linker.resolve_package_index.return_value = None

        resolver = FunctionRefResolver(linker)
        result = resolver.resolve(1)

        assert result is None

    def test_resolve_caches_result(self):
        """连续两次 resolve 相同 stack_node 应只查询 linker 一次。"""
        linker = _make_linker()
        inst = _make_instance("Func", object_class="Cls")
        linker.resolve_package_index.return_value = inst

        resolver = FunctionRefResolver(linker)
        resolver.resolve(5)
        resolver.resolve(5)

        linker.resolve_package_index.assert_called_once()

    def test_resolve_non_blueprint_class(self):
        """非 BlueprintGeneratedClass 应直接使用 object_class。"""
        linker = _make_linker()
        inst = _make_instance("ReceiveBeginPlay", object_class="Actor")
        linker.resolve_package_index.return_value = inst

        resolver = FunctionRefResolver(linker)
        result = resolver.resolve(2)

        assert result == ("Actor", "ReceiveBeginPlay")

    def test_resolve_class_none_fallback(self):
        """object_class 为 None 时应回退到 Unknown。"""
        linker = _make_linker()
        inst = _make_instance("SomeFunc", object_class=None)
        linker.resolve_package_index.return_value = inst

        resolver = FunctionRefResolver(linker)
        result = resolver.resolve(3)

        assert result == ("Unknown", "SomeFunc")


class TestResolveString:
    """resolve_string() 格式化输出。"""

    def test_resolve_string_format(self):
        """正常解析应返回 ClassName::FuncName 格式。"""
        linker = _make_linker()
        inst = _make_instance("MyFunc", object_class="MyClass")
        linker.resolve_package_index.return_value = inst

        resolver = FunctionRefResolver(linker)
        result = resolver.resolve_string(1)

        assert result == "MyClass::MyFunc"

    def test_resolve_string_fallback(self):
        """无法解析时应返回 Function_{stack_node} 格式。"""
        linker = _make_linker()
        linker.resolve_package_index.return_value = None

        resolver = FunctionRefResolver(linker)
        result = resolver.resolve_string(42)

        assert result == "Function_42"

    def test_resolve_string_null_returns_fallback(self):
        """stack_node=0 应回退到 Function_0。"""
        linker = _make_linker()
        resolver = FunctionRefResolver(linker)

        result = resolver.resolve_string(0)

        assert result == "Function_0"


class TestBuildCache:
    """build_cache() 预扫描表达式列表构建缓存。"""

    def test_build_cache_final_function(self):
        """EX_FinalFunction 应被扫描并缓存。"""
        linker = _make_linker()
        inst = _make_instance("Func", object_class="Cls")
        linker.resolve_package_index.return_value = inst

        expr = EX_FinalFunction(StackNode=10)
        resolver = FunctionRefResolver(linker)
        resolver.build_cache([expr])

        assert 10 in resolver._cache
        assert resolver._cache[10] == ("Cls", "Func")

    def test_build_cache_call_math(self):
        """EX_CallMath 应被扫描并缓存。"""
        linker = _make_linker()
        inst = _make_instance("MathFunc", object_class="MathLibrary")
        linker.resolve_package_index.return_value = inst

        expr = EX_CallMath(StackNode=20)
        resolver = FunctionRefResolver(linker)
        resolver.build_cache([expr])

        assert 20 in resolver._cache
        assert resolver._cache[20] == ("MathLibrary", "MathFunc")

    def test_build_cache_local_final_function(self):
        """EX_LocalFinalFunction 应被扫描并缓存。"""
        linker = _make_linker()
        inst = _make_instance("LocalFunc", object_class="LocalCls")
        linker.resolve_package_index.return_value = inst

        expr = EX_LocalFinalFunction(StackNode=30)
        resolver = FunctionRefResolver(linker)
        resolver.build_cache([expr])

        assert 30 in resolver._cache
        assert resolver._cache[30] == ("LocalCls", "LocalFunc")

    def test_build_cache_nested_parameters(self):
        """应递归处理 Parameters 中的嵌套函数表达式。"""
        linker = _make_linker()

        def side_effect(pkg_idx):
            mapping = {
                -1: _make_instance("InnerFunc", object_class="InnerCls"),
                -2: _make_instance("OuterFunc", object_class="OuterCls"),
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
        linker = _make_linker()
        expr = EX_FinalFunction(StackNode=0)
        resolver = FunctionRefResolver(linker)
        resolver.build_cache([expr])

        assert 0 not in resolver._cache
        linker.resolve_package_index.assert_not_called()

    def test_build_cache_skips_non_function_expressions(self):
        """非函数调用表达式应被跳过。"""
        linker = _make_linker()

        class _DummyExpr(KismetExpression):
            @property
            def Token(self):
                return 0xFF

        expr = _DummyExpr()
        resolver = FunctionRefResolver(linker)
        resolver.build_cache([expr])

        linker.resolve_package_index.assert_not_called()
