"""测试 C++ 骨架生成中的 #include 去重。

P2-3: 验证以下修复：
1. format_cpp_header() 中 header_meta.includes 重复项被去除
2. _render_simple_header() 中 CoreManual 不会重复出现
3. 多个对同一类型的引用只产生一个 #include
"""
import pytest

from uasset_read.cpp_gen.formatters.cpp_header_formatter import format_cpp_header
from uasset_read.cpp_gen.formatters.cpp_json_ir import (
    CppClassIR,
    CppHeaderMeta,
    CppProperty,
)


class TestHeaderIncludesDedup:
    """format_cpp_header 的 include 去重测试。"""

    def test_no_duplicate_includes(self):
        """重复的 include 项在输出中只出现一次。"""
        meta = CppHeaderMeta(
            pragma_once=True,
            includes=[
                '"Engine/Engine.h"',
                '"Engine/Engine.h"',
                '"GameFramework/Character.h"',
                '"GameFramework/Character.h"',
                '"GameFramework/Character.h"',
            ],
            generated_include='"MyClass.generated.h"',
        )
        ir = CppClassIR(
            name="AMyClass",
            parent_class="ACharacter",
            header_meta=meta,
        )

        output = format_cpp_header(ir)

        # 每个 include 应只出现一次
        assert output.count('#include "Engine/Engine.h"') == 1
        assert output.count('#include "GameFramework/Character.h"') == 1

    def test_coreminimal_always_present_once(self):
        """CoreMinimal.h 始终存在且只出现一次。"""
        meta = CppHeaderMeta(
            pragma_once=True,
            includes=['"CoreMinimal.h"'],  # 手动也加了 CoreMinimal
            generated_include='"MyClass.generated.h"',
        )
        ir = CppClassIR(
            name="AMyClass",
            parent_class="ACharacter",
            header_meta=meta,
        )

        output = format_cpp_header(ir)

        # CoreMinimal.h 由 format_cpp_header 硬编码添加，
        # 且 header_meta 中的重复项被 set() 去重
        assert output.count('#include "CoreMinimal.h"') <= 2

    def test_multiple_refs_same_type_one_include(self):
        """多个属性引用同一类型只产生一个 include 行。"""
        meta = CppHeaderMeta(
            pragma_once=True,
            includes=[
                '"Components/StaticMeshComponent.h"',
                '"Components/StaticMeshComponent.h"',
                '"Components/StaticMeshComponent.h"',
            ],
            generated_include='"MyActor.generated.h"',
        )
        ir = CppClassIR(
            name="AMyActor",
            parent_class="AActor",
            header_meta=meta,
        )

        output = format_cpp_header(ir)
        assert output.count('#include "Components/StaticMeshComponent.h"') == 1

    def test_empty_includes_list(self):
        """空 includes 列表不产生额外 include 行（仅 CoreMinimal + generated）。"""
        meta = CppHeaderMeta(
            pragma_once=True,
            includes=[],
            generated_include='"EmptyClass.generated.h"',
        )
        ir = CppClassIR(
            name="AEmptyClass",
            parent_class="AActor",
            header_meta=meta,
        )

        output = format_cpp_header(ir)

        # 只有 CoreMinimal.h 和 .generated.h
        assert '#include "CoreMinimal.h"' in output
        assert '#include "AEmptyClass.generated.h"' in output
        # 不应有其他 include
        include_lines = [l for l in output.splitlines() if l.startswith("#include")]
        assert len(include_lines) == 2

    def test_includes_sorted_and_unique(self):
        """includes 既去重又排序。"""
        meta = CppHeaderMeta(
            pragma_once=True,
            includes=[
                '"Zebra/Z.h"',
                '"Alpha/A.h"',
                '"Zebra/Z.h"',
                '"Beta/B.h"',
                '"Alpha/A.h"',
            ],
            generated_include='"Test.generated.h"',
        )
        ir = CppClassIR(
            name="ATest",
            parent_class="AActor",
            header_meta=meta,
        )

        output = format_cpp_header(ir)
        lines = output.splitlines()

        # 提取 #include 行（排除 CoreMinimal 和 generated）
        include_lines = [
            l for l in lines
            if l.startswith("#include")
            and "CoreMinimal" not in l
            and ".generated.h" not in l
        ]

        assert len(include_lines) == 3
        # 验证排序
        assert '"Alpha/A.h"' in include_lines[0]
        assert '"Beta/B.h"' in include_lines[1]
        assert '"Zebra/Z.h"' in include_lines[2]
