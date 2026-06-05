"""测试事件函数执行输出修复。"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from uasset_read.ir_builder import _extract_parameters_from_signature

# --- 资产路径配置（可移植） ---

_ASSET_ROOT = os.environ.get("UE_ASSET_ROOT", r"E:\Develop\lib\UnrealEngine")

TEST_ASSETS = [
    ("BP_InstancedStaticMeshBase", os.path.join(
        _ASSET_ROOT, "Engine", "Plugins", "Experimental", "AnimToTexture",
        "Content", "Characters", "Mannequin", "Blueprints",
        "BP_InstancedStaticMeshBase.uasset",
    )),
    ("BP_LocationProbe", os.path.join(
        _ASSET_ROOT, "Engine", "Plugins", "Runtime", "GeoReferencing",
        "Content", "Models", "LocationProbe",
        "BP_LocationProbe.uasset",
    )),
    ("BP_GrabToolActor", os.path.join(
        _ASSET_ROOT, "Engine", "Plugins", "VirtualProduction",
        "VirtualScouting", "Content", "Tools", "Grab",
        "BP_GrabToolActor.uasset",
    )),
]

_has_real_asset = any(os.path.isfile(p) for _, p in TEST_ASSETS)


# --- 辅助函数 ---


def parse_json(path: str) -> dict:
    """解析资产并返回 JSON。"""
    cmd = [sys.executable, "-m", "uasset_read", "--json", "--function-graphs", "--tolerant", path]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, f"Parse failed: {r.stderr[:200]}"
    return json.loads(r.stdout)


# --- 单元测试：_extract_parameters_from_signature（无需外部资产） ---


class TestExtractParametersFromSignature:
    """签名解析器单元测试 — 不依赖外部资产。"""

    def test_empty_string_returns_empty(self):
        assert _extract_parameters_from_signature("") == []

    def test_none_returns_empty(self):
        assert _extract_parameters_from_signature(None) == []

    def test_no_parens_returns_empty(self):
        assert _extract_parameters_from_signature("void Func") == []

    def test_empty_parens(self):
        assert _extract_parameters_from_signature("void Func()") == []

    def test_single_param(self):
        result = _extract_parameters_from_signature("void Tick(float DeltaTime)")
        assert result == [{"name": "DeltaTime", "type": "float"}]

    def test_multiple_params(self):
        result = _extract_parameters_from_signature(
            "int32 Add(int32 A, int32 B)"
        )
        assert result == [
            {"name": "A", "type": "int32"},
            {"name": "B", "type": "int32"},
        ]

    def test_complex_type(self):
        result = _extract_parameters_from_signature(
            "void OnHit(AActor* OtherActor, FVector NormalImpulse)"
        )
        assert result == [
            {"name": "OtherActor", "type": "AActor*"},
            {"name": "NormalImpulse", "type": "FVector"},
        ]

    def test_type_with_const_ref(self):
        result = _extract_parameters_from_signature(
            "void foo(const FString& Name)"
        )
        assert result == [{"name": "Name", "type": "const FString&"}]

    def test_type_only_no_name(self):
        # rsplit(None, 1) on single token -> type-only
        result = _extract_parameters_from_signature("void Foo(int32)")
        assert result == [{"name": "", "type": "int32"}]

    def test_leading_trailing_commas(self):
        result = _extract_parameters_from_signature(
            "void Foo( , int32 A, )"
        )
        assert result == [{"name": "A", "type": "int32"}]

    def test_pointer_type(self):
        result = _extract_parameters_from_signature(
            "void OnOverlap(UPrimitiveComponent* OverlappedComp)"
        )
        assert result == [
            {"name": "OverlappedComp", "type": "UPrimitiveComponent*"}
        ]


# --- 集成测试（依赖外部 UE 资产） ---


@pytest.mark.integration
@pytest.mark.skipif(not _has_real_asset, reason="真实 UE 资产不可用")
class TestFunctionGraphs:
    """function_graphs 不再为空。"""

    @pytest.mark.parametrize("name,path", TEST_ASSETS)
    def test_function_graphs_populated(self, name, path):
        data = parse_json(path)
        graphs = data.get("function_graphs", [])
        assert len(graphs) > 0, f"{name}: function_graphs 为空"

    @pytest.mark.parametrize("name,path", TEST_ASSETS)
    def test_function_graphs_have_structure(self, name, path):
        data = parse_json(path)
        for g in data.get("function_graphs", []):
            assert "function_name" in g, "Missing function_name in graph"
            assert "signature" in g, "Missing signature in graph"


@pytest.mark.integration
@pytest.mark.skipif(not _has_real_asset, reason="真实 UE 资产不可用")
class TestEventFunctionParameters:
    """事件函数参数不再为空。"""

    @pytest.mark.parametrize("name,path", TEST_ASSETS)
    def test_decompiled_functions_have_params_key(self, name, path):
        data = parse_json(path)
        events = [f for f in data.get("decompiled_functions", [])
                  if any(kw in f["name"] for kw in ["BeginPlay", "Tick", "ConstructionScript", "Receive"])]
        for ev in events:
            assert "parameters" in ev, \
                f"{ev['name']}: missing parameters key"

    def test_receive_begin_play_has_params(self):
        data = parse_json(TEST_ASSETS[0][1])
        begin_play = [f for f in data["decompiled_functions"] if f["name"] == "ReceiveBeginPlay"]
        assert len(begin_play) == 1
        func = begin_play[0]
        assert func.get("signature"), "Missing signature"
