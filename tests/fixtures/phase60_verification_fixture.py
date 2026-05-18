"""
tests/fixtures/phase60_verification_fixture.py — Phase 60 验证测试 fixture。

预加载 BP_FirstPersonCharacter.uasset 并通过 parse_uasset_with_linker() 解析，
缓存结果供所有验证测试共享。

Design per D-60-06: pytest.fixture(scope="module") 避免重复解析。
Graceful skip: 文件不存在时 pytest.skip()。
"""

import pytest
from pathlib import Path

from uasset_read.parse_uasset import parse_uasset_with_linker
from uasset_read.graph import build_function_graphs

# 测试资产路径
UASSET_DIR = Path(r"E:\Develop\lib\UnrealEngine\Samples\FirstPerson")


def _find_uasset() -> Path | None:
    """Locate BP_FirstPersonCharacter.uasset in sample directory."""
    candidates = list(UASSET_DIR.rglob("BP_FirstPersonCharacter.uasset"))
    return candidates[0] if candidates else None


@pytest.fixture(scope="module")
def linker_result():
    """Parse real .uasset file through full pipeline.

    Returns:
        LinkerParseResult: 完整解析结果（含 blueprint, graphs, linker 等）
    """
    uasset_path = _find_uasset()
    if uasset_path is None:
        pytest.skip(f"BP_FirstPersonCharacter.uasset not found in {UASSET_DIR}")
    return parse_uasset_with_linker(str(uasset_path))


@pytest.fixture(scope="module")
def function_graphs(linker_result):
    """Extract function_graphs from linker result.

    Returns:
        list[Dict]: function_graphs 数组（Phase 55 输出格式）
    """
    if linker_result is None:
        pytest.skip("Linker result not available")
    graphs = linker_result.graphs or []
    bp_funcs = linker_result.blueprint.functions if linker_result.blueprint else []
    return build_function_graphs(graphs, blueprint_functions=bp_funcs)


@pytest.fixture(scope="module")
def cpp_class_ir(linker_result):
    """Extract CppClassIR from linker result.

    Returns:
        CppClassIR: C++ 类骨架中间表示
    """
    if linker_result is None:
        pytest.skip("Linker result not available")
    from uasset_read.cpp_gen import extract_cpp_class_skeleton
    return extract_cpp_class_skeleton(linker_result)
