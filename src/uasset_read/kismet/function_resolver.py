"""Kismet function reference resolver.

Resolves StackNode (FPackageIndex int) from EX_FinalFunction / EX_CallMath /
EX_LocalFinalFunction into readable "ClassName::FuncName" format.

Enhanced features:
- EX_VirtualFunction: Resolve owning class name from linker
- EX_LocalFinalFunction: Detect if it is a local Blueprint function (export)
- Unresolved function reference statistics reporting
"""

from __future__ import annotations


from typing import Any


class FunctionRefResolver:
    """Resolves StackNode to class name + function name via PackageLinker."""

    def __init__(self, linker: Any) -> None:
        self._linker = linker
        self._cache: dict[int, tuple[str, str]] = {}
        # Virtual function name → class name cache (for EX_VirtualFunction class name resolution)
        self._virtual_class_cache: dict[str, str | None] = {}
        # Statistics counters
        self._resolve_attempts: int = 0
        self._resolve_failures: int = 0
        self._unresolved_refs: dict[int, int] = {}  # {stack_node: occurrence count}

    def resolve(self, stack_node: int) -> tuple[str, str] | None:
        """Resolve StackNode to (class_name, func_name), returns None on failure."""
        if stack_node == 0:
            self._resolve_attempts += 1
            self._resolve_failures += 1
            self._unresolved_refs[stack_node] = self._unresolved_refs.get(stack_node, 0) + 1
            return None

        # Prefer cache
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

        # BlueprintGeneratedClass is a Blueprint-generated wrapper class, the real class name is on its outer
        if class_name == "BlueprintGeneratedClass" and inst.outer is not None:
            class_name = inst.outer.object_name

        result = (class_name, func_name)
        self._cache[stack_node] = result
        return result

    def is_local_function(self, stack_node: int) -> bool:
        """Check if StackNode points to a local Blueprint function (export).

        Positive PackageIndex indicates export (object defined in current package),
        i.e. a local Blueprint function. Negative indicates import (external reference).
        """
        if stack_node <= 0:
            return False

        from uasset_read.serializers.object_resources import PackageIndex

        inst = self._linker.resolve_package_index(PackageIndex(stack_node))
        if inst is None:
            return False
        # export object and outer is BlueprintGeneratedClass → local Blueprint function
        if inst.outer is not None and inst.outer.object_class == "BlueprintGeneratedClass":
            return True
        # Or directly an export object (non-engine class)
        return inst.is_export

    def resolve_virtual_function_class(self, func_name: str) -> str | None:
        """Resolve the owning class name for EX_VirtualFunction.

        Iterates linker's export objects to find the BlueprintGeneratedClass
        containing a function with the same name, returns its class name.
        Results are cached.
        """
        if not func_name:
            return None

        if func_name in self._virtual_class_cache:
            return self._virtual_class_cache[func_name]

        # Search for matching function name in export objects
        for inst in self._linker.export_objects():
            if inst.object_name == func_name:
                class_name = inst.object_class or "Unknown"
                # When function object's outer is BlueprintGeneratedClass,
                # the real class name is outer's object_name
                if inst.outer is not None and inst.outer.object_class == "BlueprintGeneratedClass":
                    class_name = inst.outer.object_name
                elif class_name == "BlueprintGeneratedClass" and inst.outer is not None:
                    class_name = inst.outer.object_name
                self._virtual_class_cache[func_name] = class_name
                return class_name

        # No match found
        self._virtual_class_cache[func_name] = None
        return None

    def get_statistics(self) -> dict:
        """Return function reference resolution statistics.

        Returns:
            Dictionary containing the following fields:
            - resolve_attempts: Total resolution attempts
            - resolve_failures: Resolution failure count
            - success_rate: Resolution success rate (percentage)
            - unresolved_count: Number of distinct unresolved StackNodes
            - unresolved_refs: Unresolved {stack_node: occurrence count} dict
            - local_function_count: Number of cached local functions
        """
        total = self._resolve_attempts
        failures = self._resolve_failures
        success_rate = ((total - failures) / total * 100) if total > 0 else 100.0

        # Count local functions (export-type cache entries)
        local_count = 0
        for stack_node in self._cache:
            if stack_node > 0:  # Positive = export = local function
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
        """Return a formatted report of unresolved function references.

        Returns:
            Human-readable statistics report string.
            Returns empty string if all references are resolved.
        """
        if not self._unresolved_refs:
            return ""

        stats = self.get_statistics()
        lines = [
            "Function Reference Resolution Statistics:",
            f"  Total attempts: {stats['resolve_attempts']}",
            f"  Failures: {stats['resolve_failures']}",
            f"  Success rate: {stats['success_rate']}%",
            f"  Distinct unresolved references: {stats['unresolved_count']}",
            f"  Local function count: {stats['local_function_count']}",
        ]

        if self._unresolved_refs:
            lines.append("  Unresolved reference details:")
            # Sort by occurrence count descending
            sorted_refs = sorted(
                self._unresolved_refs.items(),
                key=lambda x: x[1],
                reverse=True,
            )
            for stack_node, count in sorted_refs[:10]:  # Show at most 10
                lines.append(f"    Function_{stack_node}: {count} times")
            if len(sorted_refs) > 10:
                lines.append(f"    ... and {len(sorted_refs) - 10} more")

        return "\n".join(lines)
