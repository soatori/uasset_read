"""Kismet 函数引用解析器。

将 EX_FinalFunction / EX_CallMath / EX_LocalFinalFunction 中的
StackNode（FPackageIndex int）解析为可读的 "ClassName::FuncName" 格式。

增强功能：
- EX_VirtualFunction：从 linker 解析函数所属类名
- EX_LocalFinalFunction：检测是否为蓝图本地函数（export）
- unresolved 函数引用统计报告
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
        # 虚函数名 → 类名缓存（用于 EX_VirtualFunction 类名解析）
        self._virtual_class_cache: dict[str, str | None] = {}
        # 统计计数器
        self._resolve_attempts: int = 0
        self._resolve_failures: int = 0
        self._unresolved_refs: dict[int, int] = {}  # {stack_node: 出现次数}

    def resolve(self, stack_node: int) -> tuple[str, str] | None:
        """解析 StackNode 为 (class_name, func_name)，失败返回 None。"""
        if stack_node == 0:
            self._resolve_attempts += 1
            self._resolve_failures += 1
            self._unresolved_refs[stack_node] = self._unresolved_refs.get(stack_node, 0) + 1
            return None

        # 优先使用缓存
        if stack_node in self._cache:
            self._resolve_attempts += 1
            return self._cache[stack_node]

        self._resolve_attempts += 1

        from uasset_read.serializers.object_resources import PackageIndex

        pkg_idx = PackageIndex(stack_node)
        if pkg_idx.is_null:
            self._resolve_failures += 1
            self._unresolved_refs[stack_node] = self._unresolved_refs.get(stack_node, 0) + 1
            return None

        inst = self._linker.resolve_package_index(pkg_idx)
        if inst is None:
            self._resolve_failures += 1
            self._unresolved_refs[stack_node] = self._unresolved_refs.get(stack_node, 0) + 1
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

    def is_local_function(self, stack_node: int) -> bool:
        """检测 StackNode 是否指向蓝图本地函数（export）。

        正数 PackageIndex 表示 export（当前包内定义的对象），
        即蓝图本地函数。负数表示 import（外部引用）。
        """
        if stack_node <= 0:
            return False

        from uasset_read.serializers.object_resources import PackageIndex

        inst = self._linker.resolve_package_index(PackageIndex(stack_node))
        if inst is None:
            return False
        # export 对象且 outer 是 BlueprintGeneratedClass → 蓝图本地函数
        if inst.outer is not None and inst.outer.object_class == "BlueprintGeneratedClass":
            return True
        # 或者直接是 export 对象（非引擎类）
        return inst.is_export

    def resolve_virtual_function_class(self, func_name: str) -> str | None:
        """为 EX_VirtualFunction 解析函数所属类名。

        遍历 linker 的 export 对象，查找包含同名函数的
        BlueprintGeneratedClass，返回其类名。
        结果会被缓存。
        """
        if not func_name:
            return None

        if func_name in self._virtual_class_cache:
            return self._virtual_class_cache[func_name]

        # 在 export 对象中搜索匹配的函数名
        for inst in self._linker.export_objects():
            if inst.object_name == func_name:
                class_name = inst.object_class or "Unknown"
                # 函数对象的 outer 是 BlueprintGeneratedClass 时，
                # 真正的类名是 outer 的 object_name
                if inst.outer is not None and inst.outer.object_class == "BlueprintGeneratedClass":
                    class_name = inst.outer.object_name
                elif class_name == "BlueprintGeneratedClass" and inst.outer is not None:
                    class_name = inst.outer.object_name
                self._virtual_class_cache[func_name] = class_name
                return class_name

        # 未找到匹配
        self._virtual_class_cache[func_name] = None
        return None

    def build_cache(self, expressions: list["KismetExpression"]) -> None:
        """预扫描表达式列表，构建 StackNode 缓存。递归处理嵌套表达式。

        增强：同时处理 EX_VirtualFunction / EX_LocalVirtualFunction
        和 EX_CallMulticastDelegate。
        """
        from uasset_read.kismet.expressions.functions import (
            EX_CallMath,
            EX_CallMulticastDelegate,
            EX_FinalFunction,
            EX_LocalFinalFunction,
            EX_LocalVirtualFunction,
            EX_VirtualFunction,
        )

        for expr in expressions:
            # 处理 StackNode 类函数调用
            if isinstance(expr, (EX_FinalFunction, EX_CallMath, EX_LocalFinalFunction)):
                stack_node = getattr(expr, "StackNode", 0)
                if isinstance(stack_node, int) and stack_node != 0:
                    # resolve 会自动写入缓存
                    self.resolve(stack_node)
                # 递归处理参数中的嵌套表达式
                if hasattr(expr, "Parameters") and expr.Parameters:
                    self.build_cache(expr.Parameters)

            # 处理虚函数调用（预解析类名）
            elif isinstance(expr, (EX_VirtualFunction, EX_LocalVirtualFunction)):
                func_name = getattr(expr, "VirtualFunctionName", "")
                if isinstance(func_name, str) and func_name:
                    self.resolve_virtual_function_class(func_name)
                if hasattr(expr, "Parameters") and expr.Parameters:
                    self.build_cache(expr.Parameters)

            # 处理多播委托调用
            elif isinstance(expr, EX_CallMulticastDelegate):
                stack_node = getattr(expr, "StackNode", 0)
                if isinstance(stack_node, int) and stack_node != 0:
                    self.resolve(stack_node)
                if hasattr(expr, "Parameters") and expr.Parameters:
                    self.build_cache(expr.Parameters)

    def get_statistics(self) -> dict:
        """返回函数引用解析统计信息。

        Returns:
            包含以下字段的字典：
            - resolve_attempts: 总解析尝试次数
            - resolve_failures: 解析失败次数
            - success_rate: 解析成功率（百分比）
            - unresolved_count: 未解析的不同 StackNode 数量
            - unresolved_refs: 未解析的 {stack_node: 出现次数} 字典
            - local_function_count: 已缓存的本地函数数量
        """
        total = self._resolve_attempts
        failures = self._resolve_failures
        success_rate = ((total - failures) / total * 100) if total > 0 else 100.0

        # 统计本地函数数量（export 类型的缓存条目）
        local_count = 0
        for stack_node in self._cache:
            if stack_node > 0:  # 正数 = export = 本地函数
                local_count += 1

        return {
            "resolve_attempts": total,
            "resolve_failures": failures,
            "success_rate": round(success_rate, 1),
            "unresolved_count": len(self._unresolved_refs),
            "unresolved_refs": dict(self._unresolved_refs),
            "local_function_count": local_count,
        }

    def get_unresolved_report(self) -> str:
        """返回未解析函数引用的格式化报告。

        Returns:
            人类可读的统计报告字符串。
            如果所有引用都已解析，返回空字符串。
        """
        if not self._unresolved_refs:
            return ""

        stats = self.get_statistics()
        lines = [
            f"函数引用解析统计:",
            f"  总尝试: {stats['resolve_attempts']}",
            f"  失败: {stats['resolve_failures']}",
            f"  成功率: {stats['success_rate']}%",
            f"  未解析的不同引用: {stats['unresolved_count']}",
            f"  本地函数数量: {stats['local_function_count']}",
        ]

        if self._unresolved_refs:
            lines.append("  未解析引用详情:")
            # 按出现次数降序排列
            sorted_refs = sorted(
                self._unresolved_refs.items(),
                key=lambda x: x[1],
                reverse=True,
            )
            for stack_node, count in sorted_refs[:10]:  # 最多显示 10 条
                lines.append(f"    Function_{stack_node}: {count} 次")
            if len(sorted_refs) > 10:
                lines.append(f"    ... 还有 {len(sorted_refs) - 10} 个")

        return "\n".join(lines)
