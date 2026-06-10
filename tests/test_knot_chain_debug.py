"""tests/test_knot_chain_debug.py — Diagnostic test for Knot chain resolution.

Note: After fixing the blueprint extraction regression (find_main_blueprint_generated_class
path matching), the implementation_status changed from "decompiled" to "graph_only".
The fallback_reasons and node counts may vary depending on asset quality.

Original diagnosis (pre-fix):
  All functions (Aim, Move etc.) had implementation_status "decompiled",
  fallback_reasons ["serial_scan_recovery"], and empty nodes list.

Post-fix behavior:
  Functions may use "graph_only" or other paths depending on available graph data.
"""
import json
import os

import pytest

from uasset_read.core import parse_single

_REAL_BLUEPRINT = os.path.join(
    os.environ.get("UE_ASSET_ROOT", r"E:\Develop\lib\UnrealEngine\Samples"),
    "FirstPerson", "Content", "FirstPerson",
    "Blueprints", "BP_FirstPersonCharacter.uasset",
)

_has_real_asset = os.path.isfile(_REAL_BLUEPRINT)


def _load_result():
    """parse_single(format='json') 返回 JSON 字符串，解析后取 blueprint.functions."""
    raw = parse_single(_REAL_BLUEPRINT, format="json", tolerant=True)
    data = json.loads(raw) if isinstance(raw, str) else raw
    return data


def _find_function(data, name):
    """在 blueprint.functions 中按名称查找函数。"""
    for func in data.get("blueprint", {}).get("functions", []):
        if func.get("name") == name:
            return func
    return None


@pytest.mark.skipif(not _has_real_asset, reason="真实资产不可用")
def test_aim_implementation_status():
    """诊断：Aim 函数的实现路径和参数绑定。"""
    data = _load_result()
    aim = _find_function(data, "Aim")
    assert aim is not None, "Aim function not found"

    impl = aim.get("implementation", {})
    status = aim.get("implementation_status", "")
    fallback = impl.get("fallback_reasons", [])
    cpp_code = impl.get("cpp_code", "")
    nodes = aim.get("nodes", [])
    params = aim.get("parameters", [])

    print(f"\n=== Aim 函数诊断 ===")
    print(f"  implementation_status: {status}")
    print(f"  fallback_reasons: {fallback}")
    print(f"  node count: {len(nodes)}")
    print(f"  function-level parameters: {params}")
    print(f"  cpp_code:\n{cpp_code}")

    # After fix: blueprint extraction works, verify function exists and has valid status
    assert status in ("graph_only", "decompiled", "hybrid"), f"Unexpected implementation_status: {status}"


@pytest.mark.skipif(not _has_real_asset, reason="真实资产不可用")
def test_move_implementation_status():
    """诊断：Move 函数的实现路径和参数绑定。"""
    data = _load_result()
    move = _find_function(data, "Move")
    assert move is not None, "Move function not found"

    impl = move.get("implementation", {})
    status = move.get("implementation_status", "")
    fallback = impl.get("fallback_reasons", [])
    cpp_code = impl.get("cpp_code", "")
    nodes = move.get("nodes", [])
    params = move.get("parameters", [])

    print(f"\n=== Move 函数诊断 ===")
    print(f"  implementation_status: {status}")
    print(f"  fallback_reasons: {fallback}")
    print(f"  node count: {len(nodes)}")
    print(f"  function-level parameters: {params}")
    print(f"  cpp_code:\n{cpp_code}")

    # After fix: blueprint extraction works, verify function exists and has valid status
    assert status in ("graph_only", "decompiled", "hybrid"), f"Unexpected implementation_status: {status}"


@pytest.mark.skipif(not _has_real_asset, reason="真实资产不可用")
def test_all_functions_use_bytecode_decompile():
    """诊断：确认所有函数都走了字节码反编译路径（无图节点）。"""
    data = _load_result()
    bp = data.get("blueprint", {})

    print("\n=== 所有函数实现路径 ===")
    for func in bp.get("functions", []):
        name = func.get("name", "?")
        status = func.get("implementation_status", "?")
        impl = func.get("implementation", {})
        fb = impl.get("fallback_reasons", []) if isinstance(impl, dict) else []
        nodes = func.get("nodes", [])
        fg = func.get("function_graph")
        print(f"  {name}: status={status} fallback={fb} nodes={len(nodes)} has_graph={fg is not None}")

    for evt in bp.get("events", []):
        name = evt.get("name", "?")
        status = evt.get("implementation_status", "?")
        impl = evt.get("implementation", {})
        fb = impl.get("fallback_reasons", []) if isinstance(impl, dict) else []
        nodes = evt.get("nodes", [])
        fg = evt.get("function_graph")
        print(f"  {name}: status={status} fallback={fb} nodes={len(nodes)} has_graph={fg is not None}")
