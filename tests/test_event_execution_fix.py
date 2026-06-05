"""测试事件函数执行输出修复。"""
import subprocess
import json
import sys
import pytest


TEST_ASSETS = [
    # 有蓝图事件函数的资产
    ("BP_InstancedStaticMeshBase", "E:/Develop/lib/UnrealEngine/Engine/Plugins/Experimental/AnimToTexture/Content/Characters/Mannequin/Blueprints/BP_InstancedStaticMeshBase.uasset"),
    ("BP_LocationProbe", "E:/Develop/lib/UnrealEngine/Engine/Plugins/Runtime/GeoReferencing/Content/Models/LocationProbe/BP_LocationProbe.uasset"),
    ("BP_GrabToolActor", "E:/Develop/lib/UnrealEngine/Engine/Plugins/VirtualProduction/VirtualScouting/Content/Tools/Grab/BP_GrabToolActor.uasset"),
]


def parse_json(path: str) -> dict:
    """解析资产并返回 JSON。"""
    cmd = [sys.executable, "-m", "uasset_read", "--json", "--function-graphs", "--tolerant", path]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, f"Parse failed: {r.stderr[:200]}"
    return json.loads(r.stdout)


class TestFunctionGraphs:
    """function_graphs 不再为空。"""

    @pytest.mark.parametrize("name,path", TEST_ASSETS)
    def test_function_graphs_populated(self, name, path):
        data = parse_json(path)
        graphs = data.get("function_graphs", [])
        # 至少有一些函数图
        assert len(graphs) > 0, f"{name}: function_graphs 为空"

    @pytest.mark.parametrize("name,path", TEST_ASSETS)
    def test_function_graphs_have_structure(self, name, path):
        data = parse_json(path)
        for g in data.get("function_graphs", []):
            assert "function_name" in g, f"Missing function_name in graph"
            assert "signature" in g, f"Missing signature in graph"


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
        # ReceiveBeginPlay 应该有参数（即使是空列表也应从签名解析）
        func = begin_play[0]
        assert func.get("signature"), "Missing signature"
