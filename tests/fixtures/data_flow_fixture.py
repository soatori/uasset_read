"""
tests/fixtures/data_flow_fixture.py — Phase 54 数据流追踪测试 fixture。

模拟 Move 函数图的数据流结构（基于 reference/蓝图节点文本参考.md）：
- FunctionEntry + Knot 链 + CallFunction + Pure 函数
- 完整的 pin 连接关系（linked_to_raw）

Created: 2026-05-17 (Phase 54-01)
"""

import pytest
from uasset_read import (
    UEdGraph,
    UEdGraphNode,
    UEdGraphPin,
    FEdGraphPinType,
    FMemberReference,
    K2NodeFunctionEntry,
    K2NodeKnot,
    K2NodeCallFunction,
)


@pytest.fixture
def sample_function_graph_with_data_flow():
    """
    创建 Move 函数图的数据流 fixture。

    节点结构（基于真实蓝图）：
    1. K2Node_FunctionEntry_0 — 函数入口，输出参数 "Left / Right" 和 "Forward / Backward"
    2. K2Node_Knot_2 → K2Node_Knot_1 — Knot 链（穿透测试）
    3. K2Node_CallFunction_7445 — AddMovementInput（接收 ScaleValue 来自 Knot_1）
    4. K2Node_CallFunction_8520 — GetActorRightVector（Pure 函数）
    5. K2Node_CallFunction_7346 — AddMovementInput（另一个调用）
    6. K2Node_CallFunction_8029 — GetActorForwardVector（Pure 函数）
    7. K2Node_Knot_3 → K2Node_Knot_4 — 另一条 Knot 链

    关键数据流路径：
    - FunctionEntry_0 "Left / Right" → Knot_2 InputPin → Knot_2 OutputPin →
      Knot_1 InputPin → Knot_1 OutputPin → CallFunction_7445 "ScaleValue"
    - CallFunction_8520 "ReturnValue" → CallFunction_7445 "WorldDirection"
    - FunctionEntry_0 "Forward / Backward" → Knot_3 → Knot_4 → CallFunction_7346 "ScaleValue"
    - CallFunction_8029 "ReturnValue" → CallFunction_7346 "WorldDirection"

    Returns:
        UEdGraph: 包含完整数据流结构的测试图
    """

    # Pin 类型定义
    exec_pin_type = FEdGraphPinType(
        pin_category="exec",
        pin_subcategory="",
        container_type=0
    )
    real_double_pin_type = FEdGraphPinType(
        pin_category="real",
        pin_subcategory="double",
        container_type=0
    )
    real_float_pin_type = FEdGraphPinType(
        pin_category="real",
        pin_subcategory="float",
        container_type=0
    )
    vector_pin_type = FEdGraphPinType(
        pin_category="struct",
        pin_subcategory="",
        container_type=0
    )
    object_pin_type = FEdGraphPinType(
        pin_category="object",
        pin_subcategory="",
        container_type=0
    )
    bool_pin_type = FEdGraphPinType(
        pin_category="bool",
        pin_subcategory="",
        container_type=0
    )

    # === K2Node_FunctionEntry_0 ===
    # GUID: 0A89B7514654265DD7C4A0BC3D2433F9
    # 输出: then (exec), "Left / Right" (real), "Forward / Backward" (real)

    fe_then_pin = UEdGraphPin(
        pin_id="B251EF8A4CD680F8E2765589C6BDE7F7",
        pin_name="then",
        direction=1,  # output
        pin_type=exec_pin_type,
        linked_to_raw=[{"pin_guid": "B629F5F54B5728127871F1830D75560F"}]  # → CallFunction_7445 exec input
    )

    fe_left_right_pin = UEdGraphPin(
        pin_id="84E069914221C8BA662D2CACACA212D4",
        pin_name="Left / Right",
        direction=1,  # output
        pin_type=real_double_pin_type,
        linked_to_raw=[{"pin_guid": "D73D5F1B4D1803E6E5FEBE9541573462"}]  # → Knot_2 input
    )

    fe_forward_backward_pin = UEdGraphPin(
        pin_id="F4D73BE64E4B4882F0DBD9B162C77CB0",
        pin_name="Forward / Backward",
        direction=1,  # output
        pin_type=real_double_pin_type,
        linked_to_raw=[{"pin_guid": "FAA683EF47E48D150F30479CAE16A751"}]  # → Knot_3 input
    )

    fe_node = UEdGraphNode(
        node_guid="0A89B7514654265DD7C4A0BC3D2433F9",
        node_pos_x=2080,
        node_pos_y=-1008,
        pins=[fe_then_pin, fe_left_right_pin, fe_forward_backward_pin],
        class_name="K2Node_FunctionEntry",
        node_data=K2NodeFunctionEntry(
            node_guid="0A89B7514654265DD7C4A0BC3D2433F9",
            function_reference=FMemberReference(member_name="Move"),
            b_is_editable=True
        )
    )

    # === K2Node_Knot_2 ===
    # GUID: 837C1E844F7A32FA1487768C3BF61BE9
    # 连接: FunctionEntry.Left/Right → Knot_2 → Knot_1

    knot2_input_pin = UEdGraphPin(
        pin_id="D73D5F1B4D1803E6E5FEBE9541573462",
        pin_name="InputPin",
        direction=0,  # input
        pin_type=real_double_pin_type,
        linked_to_raw=[{"pin_guid": "84E069914221C8BA662D2CACACA212D4"}]  # ← FunctionEntry Left / Right
    )

    knot2_output_pin = UEdGraphPin(
        pin_id="AB447120424DFEB51A3916BA20BD4B78",
        pin_name="OutputPin",
        direction=1,  # output
        pin_type=real_double_pin_type,
        linked_to_raw=[{"pin_guid": "F9EAD3EB4E49044404B771AC20C28436"}]  # → Knot_1 input
    )

    knot2_node = UEdGraphNode(
        node_guid="837C1E844F7A32FA1487768C3BF61BE9",
        node_pos_x=2352,
        node_pos_y=-784,
        pins=[knot2_input_pin, knot2_output_pin],
        class_name="K2Node_Knot",
        node_data=K2NodeKnot(node_guid="837C1E844F7A32FA1487768C3BF61BE9")
    )

    # === K2Node_Knot_1 ===
    # GUID: 5DA12B624225F8CD19A59BB18E30848F
    # 连接: Knot_2 → Knot_1 → CallFunction_7445

    knot1_input_pin = UEdGraphPin(
        pin_id="F9EAD3EB4E49044404B771AC20C28436",
        pin_name="InputPin",
        direction=0,  # input
        pin_type=real_double_pin_type,
        linked_to_raw=[{"pin_guid": "AB447120424DFEB51A3916BA20BD4B78"}]  # ← Knot_2 OutputPin
    )

    knot1_output_pin = UEdGraphPin(
        pin_id="5246D4F84ECABD92CC322BBAD7DCD742",
        pin_name="OutputPin",
        direction=1,  # output
        pin_type=real_double_pin_type,
        linked_to_raw=[{"pin_guid": "944E2F714D82CC9B729C2599E28C130A"}]  # → CallFunction_7445 ScaleValue
    )

    knot1_node = UEdGraphNode(
        node_guid="5DA12B624225F8CD19A59BB18E30848F",
        node_pos_x=2544,
        node_pos_y=-784,
        pins=[knot1_input_pin, knot1_output_pin],
        class_name="K2Node_Knot",
        node_data=K2NodeKnot(node_guid="5DA12B624225F8CD19A59BB18E30848F")
    )

    # === K2Node_CallFunction_7445 (AddMovementInput) ===
    # GUID: 80513E42423F4BFC7026A5AF32A5167B
    # 输入: execute, self, WorldDirection (from GetActorRightVector), ScaleValue (from Knot_1), bForce

    call7445_exec_in = UEdGraphPin(
        pin_id="B629F5F54B5728127871F1830D75560F",
        pin_name="execute",
        direction=0,  # input
        pin_type=exec_pin_type,
        linked_to_raw=[]  # 从 FunctionEntry then 连接过来
    )

    call7445_then_out = UEdGraphPin(
        pin_id="B4F2267F407509927C003C858811C040",
        pin_name="then",
        direction=1,  # output
        pin_type=exec_pin_type,
        linked_to_raw=[{"pin_guid": "B27FCDDF43B9261BD870CE965B82DF38"}]  # → CallFunction_7346 exec input
    )

    call7445_self_pin = UEdGraphPin(
        pin_id="2F8A8E574DD9288695A177820F3C5F9F",
        pin_name="self",
        direction=0,  # input
        pin_type=object_pin_type,
        linked_to_raw=[]  # self 引用（边界）
    )

    call7445_world_dir = UEdGraphPin(
        pin_id="F7F1DA6A4A9AD273C811828673CC525C",
        pin_name="WorldDirection",
        direction=0,  # input
        pin_type=vector_pin_type,
        linked_to_raw=[{"pin_guid": "5889B2F64B98C1422768DEA8D82E641F"}]  # → GetActorRightVector ReturnValue
    )

    call7445_scale_val = UEdGraphPin(
        pin_id="944E2F714D82CC9B729C2599E28C130A",
        pin_name="ScaleValue",
        direction=0,  # input
        pin_type=real_float_pin_type,
        linked_to_raw=[{"pin_guid": "5246D4F84ECABD92CC322BBAD7DCD742"}]  # ← Knot_1 OutputPin
    )

    call7445_bforce = UEdGraphPin(
        pin_id="36C6B0594E78226D19235C97A266EC4D",
        pin_name="bForce",
        direction=0,  # input
        pin_type=bool_pin_type,
        linked_to_raw=[],
        default_value="false"
    )

    call7445_node = UEdGraphNode(
        node_guid="80513E42423F4BFC7026A5AF32A5167B",
        node_pos_x=2640,
        node_pos_y=-1024,
        pins=[call7445_exec_in, call7445_then_out, call7445_self_pin,
              call7445_world_dir, call7445_scale_val, call7445_bforce],
        class_name="K2Node_CallFunction",
        node_data=K2NodeCallFunction(
            node_guid="80513E42423F4BFC7026A5AF32A5167B",
            function_reference=FMemberReference(member_name="AddMovementInput", b_self_context=True),
            b_defaults_to_pure=False
        )
    )

    # === K2Node_CallFunction_8520 (GetActorRightVector - Pure) ===
    # GUID: 1334BFF84CD17534B7DC1082BCEF3841
    # 输入: self (隐式)
    # 输出: ReturnValue (Vector) → CallFunction_7445 WorldDirection

    call8520_self_pin = UEdGraphPin(
        pin_id="FF046F244E7400826D6A6896F6D5D37D",
        pin_name="self",
        direction=0,  # input
        pin_type=object_pin_type,
        linked_to_raw=[]  # self 引用（边界）
    )

    call8520_return_pin = UEdGraphPin(
        pin_id="5889B2F64B98C1422768DEA8D82E641F",
        pin_name="ReturnValue",
        direction=1,  # output
        pin_type=vector_pin_type,
        linked_to_raw=[{"pin_guid": "F7F1DA6A4A9AD273C811828673CC525C"}]  # → CallFunction_7445 WorldDirection
    )

    call8520_node = UEdGraphNode(
        node_guid="1334BFF84CD17534B7DC1082BCEF3841",
        node_pos_x=2336,
        node_pos_y=-928,
        pins=[call8520_self_pin, call8520_return_pin],
        class_name="K2Node_CallFunction",
        node_data=K2NodeCallFunction(
            node_guid="1334BFF84CD17534B7DC1082BCEF3841",
            function_reference=FMemberReference(member_name="GetActorRightVector", b_self_context=True),
            b_defaults_to_pure=True  # Pure function 标记
        )
    )

    # === K2Node_Knot_3 ===
    # GUID: A3BB360E4B1C78100DA81BB3F98FAC18
    # 连接: FunctionEntry.Forward/Backward → Knot_3 → Knot_4

    knot3_input_pin = UEdGraphPin(
        pin_id="FAA683EF47E48D150F30479CAE16A751",
        pin_name="InputPin",
        direction=0,
        pin_type=real_double_pin_type,
        linked_to_raw=[]
    )

    knot3_output_pin = UEdGraphPin(
        pin_id="862708354F737F7045944D8F5BA281C0",
        pin_name="OutputPin",
        direction=1,
        pin_type=real_double_pin_type,
        linked_to_raw=[{"pin_guid": "C19802684AD252493850E497DEB8E04E"}]  # → Knot_4 input
    )

    knot3_node = UEdGraphNode(
        node_guid="A3BB360E4B1C78100DA81BB3F98FAC18",
        node_pos_x=2368,
        node_pos_y=-720,
        pins=[knot3_input_pin, knot3_output_pin],
        class_name="K2Node_Knot",
        node_data=K2NodeKnot(node_guid="A3BB360E4B1C78100DA81BB3F98FAC18")
    )

    # === K2Node_Knot_4 ===
    # GUID: A8FE725843242CEF67F51B9921CC1945
    # 连接: Knot_3 → Knot_4 → CallFunction_7346 ScaleValue

    knot4_input_pin = UEdGraphPin(
        pin_id="C19802684AD252493850E497DEB8E04E",
        pin_name="InputPin",
        direction=0,
        pin_type=real_double_pin_type,
        linked_to_raw=[]
    )

    knot4_output_pin = UEdGraphPin(
        pin_id="30485995480A49A17B2DB8B87C390771",
        pin_name="OutputPin",
        direction=1,
        pin_type=real_double_pin_type,
        linked_to_raw=[{"pin_guid": "D95413A34BE985375A5C2F905CD8109F"}]  # → CallFunction_7346 ScaleValue
    )

    knot4_node = UEdGraphNode(
        node_guid="A8FE725843242CEF67F51B9921CC1945",
        node_pos_x=3168,
        node_pos_y=-720,
        pins=[knot4_input_pin, knot4_output_pin],
        class_name="K2Node_Knot",
        node_data=K2NodeKnot(node_guid="A8FE725843242CEF67F51B9921CC1945")
    )

    # === K2Node_CallFunction_7346 (AddMovementInput) ===
    # GUID: 88B37EA64560471D2025ECBF404484EA
    # 输入: execute (from CallFunction_7445), self, WorldDirection (from GetActorForwardVector),
    #       ScaleValue (from Knot_4), bForce

    call7346_exec_in = UEdGraphPin(
        pin_id="B27FCDDF43B9261BD870CE965B82DF38",
        pin_name="execute",
        direction=0,
        pin_type=exec_pin_type,
        linked_to_raw=[]
    )

    call7346_then_out = UEdGraphPin(
        pin_id="3489619D4C61A10A00FA138D7A6E7516",
        pin_name="then",
        direction=1,
        pin_type=exec_pin_type,
        linked_to_raw=[]
    )

    call7346_self_pin = UEdGraphPin(
        pin_id="ADDDA4724E644BACD850A79243F45A73",
        pin_name="self",
        direction=0,
        pin_type=object_pin_type,
        linked_to_raw=[]
    )

    call7346_world_dir = UEdGraphPin(
        pin_id="375CEFD8460F7D3B99771F9AA623A2B8",
        pin_name="WorldDirection",
        direction=0,
        pin_type=vector_pin_type,
        linked_to_raw=[{"pin_guid": "33F14CE248A39D719A4E5B881DD6E2D7"}]  # → GetActorForwardVector ReturnValue
    )

    call7346_scale_val = UEdGraphPin(
        pin_id="D95413A34BE985375A5C2F905CD8109F",
        pin_name="ScaleValue",
        direction=0,
        pin_type=real_float_pin_type,
        linked_to_raw=[{"pin_guid": "30485995480A49A17B2DB8B87C390771"}]  # ← Knot_4 OutputPin
    )

    call7346_bforce = UEdGraphPin(
        pin_id="8B908E9C4C3F2AF6B0A13EA75A8CEEF5",
        pin_name="bForce",
        direction=0,
        pin_type=bool_pin_type,
        linked_to_raw=[],
        default_value="false"
    )

    call7346_node = UEdGraphNode(
        node_guid="88B37EA64560471D2025ECBF404484EA",
        node_pos_x=3312,
        node_pos_y=-1024,
        pins=[call7346_exec_in, call7346_then_out, call7346_self_pin,
              call7346_world_dir, call7346_scale_val, call7346_bforce],
        class_name="K2Node_CallFunction",
        node_data=K2NodeCallFunction(
            node_guid="88B37EA64560471D2025ECBF404484EA",
            function_reference=FMemberReference(member_name="AddMovementInput", b_self_context=True),
            b_defaults_to_pure=False
        )
    )

    # === K2Node_CallFunction_8029 (GetActorForwardVector - Pure) ===
    # GUID: 054800AE4F623F6319EB0C9412DA82D9
    # 输入: self (隐式)
    # 输出: ReturnValue (Vector) → CallFunction_7346 WorldDirection

    call8029_self_pin = UEdGraphPin(
        pin_id="A73671E14C2B0E048DEFAE8F666DACE0",
        pin_name="self",
        direction=0,
        pin_type=object_pin_type,
        linked_to_raw=[]
    )

    call8029_return_pin = UEdGraphPin(
        pin_id="33F14CE248A39D719A4E5B881DD6E2D7",
        pin_name="ReturnValue",
        direction=1,
        pin_type=vector_pin_type,
        linked_to_raw=[{"pin_guid": "375CEFD8460F7D3B99771F9AA623A2B8"}]  # → CallFunction_7346 WorldDirection
    )

    call8029_node = UEdGraphNode(
        node_guid="054800AE4F623F6319EB0C9412DA82D9",
        node_pos_x=2976,
        node_pos_y=-912,
        pins=[call8029_self_pin, call8029_return_pin],
        class_name="K2Node_CallFunction",
        node_data=K2NodeCallFunction(
            node_guid="054800AE4F623F6319EB0C9412DA82D9",
            function_reference=FMemberReference(member_name="GetActorForwardVector", b_self_context=True),
            b_defaults_to_pure=True  # Pure function 标记
        )
    )

    # === 构造完整图 ===
    graph = UEdGraph(
        graph_name="Move",
        graph_class="EdGraph",  # Function graph
        nodes=[fe_node, knot2_node, knot1_node, call7445_node,
               call8520_node, knot3_node, knot4_node, call7346_node,
               call8029_node],
        b_editable=True
    )

    return graph


@pytest.fixture
def sample_graph_with_sub_pins():
    """
    创建包含 SubPin 结构的测试 fixture。

    用于测试 struct pin（如 Vector）的第一级展开。

    Returns:
        UEdGraph: 包含 SubPin 结构的测试图
    """

    # Pin 类型
    vector_pin_type = FEdGraphPinType(
        pin_category="struct",
        pin_subcategory="",
        container_type=0
    )
    float_pin_type = FEdGraphPinType(
        pin_category="real",
        pin_subcategory="float",
        container_type=0
    )

    # Vector pin with sub_pins (X, Y, Z)
    vector_pin = UEdGraphPin(
        pin_id="vector_main",
        pin_name="MyVector",
        direction=1,  # output
        pin_type=vector_pin_type,
        linked_to_raw=[],
        sub_pins=[
            {"pin_id": "vector_x", "pin_name": "X", "direction": 1, "pin_type": float_pin_type},
            {"pin_id": "vector_y", "pin_name": "Y", "direction": 1, "pin_type": float_pin_type},
            {"pin_id": "vector_z", "pin_name": "Z", "direction": 1, "pin_type": float_pin_type},
        ]
    )

    # 简单节点包含 Vector pin
    node_with_vector = UEdGraphNode(
        node_guid="vector_node_1",
        node_pos_x=0,
        node_pos_y=0,
        pins=[vector_pin],
        class_name="K2Node_VariableGet",
    )

    graph = UEdGraph(
        graph_name="SubPinTestGraph",
        graph_class="UberEdGraph",
        nodes=[node_with_vector],
    )

    return graph