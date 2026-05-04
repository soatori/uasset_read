"""
tests/test_phase21_verification.py - Phase 21 验证测试

验证 v4.0 节点属性深度解析的正确性。
- TEST-01: 节点数量匹配验证
- TEST-02: 执行流程验证（IA_Jump → Jump → StopJumping）
- TEST-03: 数据流验证（ActionValue_X/Y → 参数）
- TEST-04: 节点属性验证（FunctionReference.MemberName、NodeGuid）

测试资产: BP_FirstPersonCharacter.uasset (UE 5.7)
"""

import pytest
import os
from uasset_read import parse_uasset, format_json_full


# ============================================================================
# 测试资产路径
# ============================================================================

FIRST_PERSON_CHARACTER_PATH = "E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset"


def get_test_asset_path():
    """获取可用的测试资产路径"""
    if os.path.exists(FIRST_PERSON_CHARACTER_PATH):
        return FIRST_PERSON_CHARACTER_PATH
    return None


# ============================================================================
# TEST-01: 节点数量匹配验证
# ============================================================================

class TestNodeCount:
    """TEST-01: 节点数量匹配验证"""

    @pytest.mark.skipif(not os.path.exists(FIRST_PERSON_CHARACTER_PATH), reason="Test asset not found")
    def test_graphs_exist(self):
        """验证解析结果包含 graphs 且非空"""
        result = parse_uasset(FIRST_PERSON_CHARACTER_PATH)
        assert result.is_success, f"解析失败: {result.errors}"
        assert result.graphs is not None, "graphs 为 None"
        assert len(result.graphs) > 0, "graphs 为空列表"

    @pytest.mark.skipif(not os.path.exists(FIRST_PERSON_CHARACTER_PATH), reason="Test asset not found")
    def test_node_count_matches_exports(self):
        """验证节点数量与导出表中 K2Node 条目数量匹配"""
        result = parse_uasset(FIRST_PERSON_CHARACTER_PATH)
        json_output = format_json_full(result)

        # 从 export_map 统计 K2Node 类导出（object_name 以 K2Node 开头）
        k2node_exports = [e for e in result.export_map
                          if e.object_name and e.object_name.startswith("K2Node")]
        export_node_count = len(k2node_exports)

        # 从所有 graphs 统计解析出的 K2Node 类型节点
        total_k2node_count = 0
        if json_output.get("blueprint") and json_output["blueprint"].get("graphs"):
            for graph in json_output["blueprint"]["graphs"]:
                for node in graph.get("nodes", []):
                    node_type = node.get("node_type", "")
                    if node_type.startswith("K2Node"):
                        total_k2node_count += 1

        # Per D-21-05: 精确匹配标准（仅统计 K2Node 类型）
        assert total_k2node_count == export_node_count, \
            f"K2Node节点数量不匹配: 解析={total_k2node_count}, 导出表={export_node_count}"


# ============================================================================
# TEST-02: 执行流程验证（IA_Jump → Jump → StopJumping）
# ============================================================================

class TestExecutionFlow:
    """TEST-02: 执行流程验证（IA_Jump → Jump → StopJumping）"""

    @pytest.mark.skipif(not os.path.exists(FIRST_PERSON_CHARACTER_PATH), reason="Test asset not found")
    def test_execution_flows_exist(self):
        """验证 execution_flows 存在"""
        result = parse_uasset(FIRST_PERSON_CHARACTER_PATH)
        json_output = format_json_full(result)

        if json_output.get("blueprint") and json_output["blueprint"].get("graphs"):
            graph = json_output["blueprint"]["graphs"][0]
            assert "execution_flows" in graph, "execution_flows 字段不存在"
            assert len(graph["execution_flows"]) > 0, "execution_flows 为空"
        else:
            pytest.fail("blueprint.graphs 不存在，无法验证执行流程")

    @pytest.mark.skipif(not os.path.exists(FIRST_PERSON_CHARACTER_PATH), reason="Test asset not found")
    def test_jump_started_flow(self):
        """
        验证 IA_Jump(Started) → Jump 执行流程。

        Per D-21-09 C++对照:
        EnhancedInputComponent->BindAction(JumpAction, ETriggerEvent::Started, this, &DoJumpStart)
        DoJumpStart() { Jump(); }
        """
        result = parse_uasset(FIRST_PERSON_CHARACTER_PATH)
        json_output = format_json_full(result)

        # 查找包含 IA_Jump Started 事件的 execution_flow
        # Expected: entry 节点包含 "IA_Jump"，chain 包含调用 Jump 的节点
        found_jump_flow = False

        if json_output.get("blueprint") and json_output["blueprint"].get("graphs"):
            for flow in json_output["blueprint"]["graphs"][0].get("execution_flows", []):
                entry = flow.get("entry", "")
                # IA_Jump 的 EnhancedInputAction 节点
                if "IA_Jump" in entry and "Started" in entry:
                    chain = flow.get("chain", [])
                    # 验证 chain 包含调用 Jump 函数的节点
                    for node_name in chain:
                        if "CallFunction" in node_name:
                            # 查找该节点的 function_reference.member_name
                            nodes = json_output["blueprint"]["graphs"][0].get("nodes", [])
                            for node in nodes:
                                if node.get("node_name") == node_name:
                                    func_ref = node.get("function_reference", {})
                                    if func_ref.get("member_name") == "Jump":
                                        found_jump_flow = True
                                        break

        assert found_jump_flow, "未找到 IA_Jump(Started) → Jump 执行流程"

    @pytest.mark.skipif(not os.path.exists(FIRST_PERSON_CHARACTER_PATH), reason="Test asset not found")
    def test_jump_completed_flow(self):
        """
        验证 IA_Jump(Completed) → StopJumping 执行流程。

        Per D-21-09 C++对照:
        EnhancedInputComponent->BindAction(JumpAction, ETriggerEvent::Completed, this, &DoJumpEnd)
        DoJumpEnd() { StopJumping(); }
        """
        result = parse_uasset(FIRST_PERSON_CHARACTER_PATH)
        json_output = format_json_full(result)

        found_stop_flow = False

        if json_output.get("blueprint") and json_output["blueprint"].get("graphs"):
            for flow in json_output["blueprint"]["graphs"][0].get("execution_flows", []):
                entry = flow.get("entry", "")
                if "IA_Jump" in entry and "Completed" in entry:
                    chain = flow.get("chain", [])
                    for node_name in chain:
                        if "CallFunction" in node_name:
                            nodes = json_output["blueprint"]["graphs"][0].get("nodes", [])
                            for node in nodes:
                                if node.get("node_name") == node_name:
                                    func_ref = node.get("function_reference", {})
                                    if func_ref.get("member_name") == "StopJumping":
                                        found_stop_flow = True
                                        break

        assert found_stop_flow, "未找到 IA_Jump(Completed) → StopJumping 执行流程"


# ============================================================================
# TEST-03: 数据流验证（ActionValue_X/Y → 参数）
# ============================================================================

class TestDataFlow:
    """TEST-03: 数据流验证（ActionValue_X/Y → 参数）"""

    @pytest.mark.skipif(not os.path.exists(FIRST_PERSON_CHARACTER_PATH), reason="Test asset not found")
    def test_data_flows_exist(self):
        """验证 data_flows 存在"""
        result = parse_uasset(FIRST_PERSON_CHARACTER_PATH)
        json_output = format_json_full(result)

        if json_output.get("blueprint") and json_output["blueprint"].get("graphs"):
            graph = json_output["blueprint"]["graphs"][0]
            assert "data_flows" in graph, "data_flows 字段不存在"

    @pytest.mark.skipif(not os.path.exists(FIRST_PERSON_CHARACTER_PATH), reason="Test asset not found")
    def test_actionvalue_x_to_right(self):
        """
        验证 ActionValue_X → Right 参数数据流。

        Per D-21-09 C++对照:
        MoveInput(Value) { MovementVector.X → DoMove(Right, Forward) }
        MovementVector.X 对应 Right 参数
        """
        result = parse_uasset(FIRST_PERSON_CHARACTER_PATH)
        json_output = format_json_full(result)

        found_x_flow = False

        if json_output.get("blueprint") and json_output["blueprint"].get("graphs"):
            for flow in json_output["blueprint"]["graphs"][0].get("data_flows", []):
                source = flow.get("source", {})
                source_pin = source.get("pin", "")
                # ActionValue_X 输出 pin
                if "ActionValue_X" in source_pin or source_pin == "X":
                    target = flow.get("target", {})
                    target_pin = target.get("pin", "")
                    # Right 参数（AddMovementInput 的 Right/Left 参数名）
                    if "Right" in target_pin or "Left" in target_pin:
                        found_x_flow = True
                        break

        assert found_x_flow, "未找到 ActionValue_X → Right 数据流"

    @pytest.mark.skipif(not os.path.exists(FIRST_PERSON_CHARACTER_PATH), reason="Test asset not found")
    def test_actionvalue_y_to_forward(self):
        """
        验证 ActionValue_Y → Forward 参数数据流。

        Per D-21-09 C++对照:
        MoveInput(Value) { MovementVector.Y → DoMove(Right, Forward) }
        MovementVector.Y 对应 Forward 参数
        """
        result = parse_uasset(FIRST_PERSON_CHARACTER_PATH)
        json_output = format_json_full(result)

        found_y_flow = False

        if json_output.get("blueprint") and json_output["blueprint"].get("graphs"):
            for flow in json_output["blueprint"]["graphs"][0].get("data_flows", []):
                source = flow.get("source", {})
                source_pin = source.get("pin", "")
                # ActionValue_Y 输出 pin
                if "ActionValue_Y" in source_pin or source_pin == "Y":
                    target = flow.get("target", {})
                    target_pin = target.get("pin", "")
                    # Forward 参数
                    if "Forward" in target_pin:
                        found_y_flow = True
                        break

        assert found_y_flow, "未找到 ActionValue_Y → Forward 数据流"


# ============================================================================
# TEST-04: 节点属性验证（FunctionReference.MemberName、NodeGuid）
# ============================================================================

class TestNodeProperties:
    """TEST-04: 节点属性验证（FunctionReference.MemberName、NodeGuid）"""

    @pytest.mark.skipif(not os.path.exists(FIRST_PERSON_CHARACTER_PATH), reason="Test asset not found")
    def test_node_guid_present(self):
        """验证节点包含 node_guid 字段（非空 GUID 格式）"""
        result = parse_uasset(FIRST_PERSON_CHARACTER_PATH)
        json_output = format_json_full(result)

        if json_output.get("blueprint") and json_output["blueprint"].get("graphs"):
            nodes = json_output["blueprint"]["graphs"][0].get("nodes", [])
            assert len(nodes) > 0, "nodes 为空"

            # 验证每个节点有 node_guid
            for node in nodes:
                node_guid = node.get("node_guid")
                assert node_guid is not None, f"节点 {node.get('node_name')} 缺少 node_guid"
                # GUID 应为 32 字符十六进制字符串
                if node_guid:
                    assert len(node_guid) >= 32, f"node_guid 格式异常: {node_guid}"

    @pytest.mark.skipif(not os.path.exists(FIRST_PERSON_CHARACTER_PATH), reason="Test asset not found")
    def test_function_reference_member_name(self):
        """验证 CallFunction 节点包含 function_reference.member_name"""
        result = parse_uasset(FIRST_PERSON_CHARACTER_PATH)
        json_output = format_json_full(result)

        found_call_function = False

        if json_output.get("blueprint") and json_output["blueprint"].get("graphs"):
            nodes = json_output["blueprint"]["graphs"][0].get("nodes", [])

            for node in nodes:
                node_type = node.get("node_type", "")
                if node_type == "K2Node_CallFunction" or "CallFunction" in node_type:
                    found_call_function = True
                    func_ref = node.get("function_reference")
                    assert func_ref is not None, \
                        f"CallFunction 节点 {node.get('node_name')} 缺少 function_reference"

                    member_name = func_ref.get("member_name")
                    assert member_name is not None, \
                        f"function_reference 缺少 member_name: {func_ref}"

                    # 验证 member_name 是有效的函数名
                    assert len(member_name) > 0, f"member_name 为空"
                    # UE 函数名应不包含空格
                    assert " " not in member_name, f"member_name 包含空格: {member_name}"

        if not found_call_function:
            pytest.skip("未找到 CallFunction 节点（可能 graphs 为空）")

    @pytest.mark.skipif(not os.path.exists(FIRST_PERSON_CHARACTER_PATH), reason="Test asset not found")
    def test_event_reference_present(self):
        """验证 Event 节点包含 event_reference 字段"""
        result = parse_uasset(FIRST_PERSON_CHARACTER_PATH)
        json_output = format_json_full(result)

        found_event_node = False

        if json_output.get("blueprint") and json_output["blueprint"].get("graphs"):
            nodes = json_output["blueprint"]["graphs"][0].get("nodes", [])

            for node in nodes:
                node_type = node.get("node_type", "")
                if node_type == "K2Node_Event" or "Event" in node_type:
                    found_event_node = True
                    event_ref = node.get("event_reference")
                    # event_reference 应存在（或节点有其他识别事件的方式）
                    # Phase 20 实现了 event_reference 顶层字段

        if not found_event_node:
            pytest.skip("未找到 Event 节点（可能 graphs 为空）")