"""tests/test_knot_chain_debug.py — Diagnostic test for Knot chain resolution.

诊断发现：
  所有函数（Aim, Move 等）的 implementation_status 为 "decompiled"，
  fallback_reasons 为 ["serial_scan_recovery"]。
  函数内 nodes 列表为空 — 图数据完全未被解析。
  C++ 代码是从字节码反编译生成的（serial_scan_recovery 回退路径），
  而非从图节点遍历生成。因此 _trace_data_source() 从未被调用。

  根因：解析器使用了字节码反编译路径而非图遍历路径。
  Knot 链解析代码存在但未被执行，因为根本没有图节点。
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

    # 关键诊断：节点为空意味着图遍历路径未被使用
    assert len(nodes) == 0, f"预期 nodes 为空（字节码反编译路径），实际有 {len(nodes)} 个节点"
    assert "serial_scan_recovery" in fallback, "预期 fallback 为 serial_scan_recovery"


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

    # 关键诊断：节点为空意味着图遍历路径未被使用
    assert len(nodes) == 0, f"预期 nodes 为空（字节码反编译路径），实际有 {len(nodes)} 个节点"
    assert "serial_scan_recovery" in fallback, "预期 fallback 为 serial_scan_recovery"


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
