"""Kismet 函数引用解析器。

将 EX_FinalFunction / EX_CallMath / EX_LocalFinalFunction 中的
StackNode（FPackageIndex int）解析为可读的 "ClassName::FuncName" 格式。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.kismet.expressions.base import KismetExpression
    from uasset_read.link.linker import PackageLinker


class FunctionRefResolver:
    """通过 PackageLinker 将 StackNode 解析为类名+函数名。"""

    def __init__(self, linker: "PackageLinker") -> None:
        self._linker = linker
        self._cache: dict[int, tuple[str, str]] = {}

    def resolve(self, stack_node: int) -> tuple[str, str] | None:
        """解析 StackNode 为 (class_name, func_name)，失败返回 None。"""
        if stack_node == 0:
            return None

        # 优先使用缓存
        if stack_node in self._cache:
            return self._cache[stack_node]

        from uasset_read.serializers.object_resources import PackageIndex

        pkg_idx = PackageIndex(stack_node)
        if pkg_idx.is_null:
            return None

        inst = self._linker.resolve_package_index(pkg_idx)
        if inst is None:
            return None

        func_name: str = inst.object_name
        class_name: str = inst.object_class or "Unknown"

        # BlueprintGeneratedClass 是蓝图生成的包装类，真正的类名在其 outer 上
        if class_name == "BlueprintGeneratedClass" and inst.outer is not None:
            class_name = inst.outer.object_name

        result = (class_name, func_name)
        self._cache[stack_node] = result
        return result

    def resolve_string(self, stack_node: int) -> str:
        """返回 "ClassName::FuncName" 或回退格式 "Function_{stack_node}"。"""
        result = self.resolve(stack_node)
        if result is None:
            return f"Function_{stack_node}"
        class_name, func_name = result
        return f"{class_name}::{func_name}"

    def build_cache(self, expressions: list["KismetExpression"]) -> None:
        """预扫描表达式列表，构建 StackNode 缓存。递归处理嵌套表达式。"""
        from uasset_read.kismet.expressions.functions import (
            EX_CallMath,
            EX_FinalFunction,
            EX_LocalFinalFunction,
        )

        for expr in expressions:
            if isinstance(expr, (EX_FinalFunction, EX_CallMath, EX_LocalFinalFunction)):
                stack_node = getattr(expr, "StackNode", 0)
                if isinstance(stack_node, int) and stack_node != 0:
                    # resolve 会自动写入缓存
                    self.resolve(stack_node)
                # 递归处理参数中的嵌套表达式
                if hasattr(expr, "Parameters") and expr.Parameters:
                    self.build_cache(expr.Parameters)
