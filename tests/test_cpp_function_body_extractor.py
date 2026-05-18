"""单元测试：CppFunctionBodyExtractor — execution_flows → CppStatement。"""
import pytest

from uasset_read.cpp_gen.formatters.cpp_json_ir import (
    CppAssignmentStmt,
    CppCallParameter,
    CppCallStmt,
    CppIfStmt,
    CppInlineExprStmt,
    CppMethodIR,
)
from uasset_read.cpp_gen.extractors.cpp_function_body_extractor import (
    _decide_pure_inline,
    _derive_condition,
    extract_function_body,
)


def _make_method_ir(name: str, params: list = None) -> CppMethodIR:
    """辅助函数：创建测试用 CppMethodIR。"""
    return CppMethodIR(
        cpp_name=name,
        return_type="void",
        parameters=[
            CppCallParameter(name=p[0], cpp_type=p[1], direction="input")
            for p in (params or [])
        ],
        ufunction_specifiers=[],
        is_override=False,
    )


# ============================================================================
# Task 1: 数据模型测试
# ============================================================================

class TestCppStatementModels:
    """测试 CppStatement 系列数据模型。"""

    def test_call_stmt_instantiable(self):
        stmt = CppCallStmt(target="this", method_name="Jump", args=[])
        assert stmt.statement_type == "call"
        assert stmt.method_name == "Jump"

    def test_assignment_stmt_instantiable(self):
        stmt = CppAssignmentStmt(lhs="x", rhs="1 + 2", cpp_type="int")
        assert stmt.statement_type == "assignment"

    def test_if_stmt_instantiable(self):
        stmt = CppIfStmt(condition="x > 0", then_body=[], else_body=[])
        assert stmt.statement_type == "if"

    def test_inline_expr_stmt_instantiable(self):
        stmt = CppInlineExprStmt(expression="GetActorRightVector()")
        assert stmt.statement_type == "inline_expr"

    def test_to_dict_serializable(self):
        call = CppCallStmt(target="Super", method_name="Jump")
        d = call.to_dict()
        assert isinstance(d, dict)
        assert d["statement_type"] == "call"
        assert d["method_name"] == "Jump"

    def test_if_stmt_to_dict_with_else(self):
        inner = CppCallStmt(target="this", method_name="Foo")
        stmt = CppIfStmt(condition="x", then_body=[inner], else_body=[])
        d = stmt.to_dict()
        assert "then_body" in d
        assert len(d["then_body"]) == 1

    def test_if_stmt_to_dict_without_else(self):
        stmt = CppIfStmt(condition="x", then_body=[], else_body=[])
        d = stmt.to_dict()
        assert "else_body" not in d  # empty else omitted

    def test_method_ir_has_body_field(self):
        ir = _make_method_ir("Test")
        assert hasattr(ir, "body")
        assert ir.body == []


# ============================================================================
# Task 2: extract_function_body — 执行流翻译
# ============================================================================

class TestExtractFunctionBody:
    """测试 extract_function_body 核心函数。"""

    def test_extract_simple_call(self):
        """单个 CallFunction 节点 → 单个 CppCallStmt。"""
        method_ir = _make_method_ir("Jump")
        execution_flow = {
            "nodes": [
                {
                    "node_type": "K2Node_CallFunction",
                    "function_name": "Jump",
                    "pure": False,
                    "parameters": {"parameters": []},
                }
            ]
        }
        result = extract_function_body(method_ir, execution_flow, [], {})
        assert len(result) == 1
        assert isinstance(result[0], CppCallStmt)
        assert result[0].method_name == "Jump"

    def test_extract_call_with_args(self):
        """CallFunction 带参数 → CppCallStmt 含 args。"""
        method_ir = _make_method_ir("AddControllerYawInput", [("Yaw", "float")])
        execution_flow = {
            "nodes": [
                {
                    "node_type": "K2Node_CallFunction",
                    "function_name": "AddControllerYawInput",
                    "pure": False,
                    "parameters": {
                        "parameters": [
                            {"name": "InYaw", "direction": "input"},
                        ]
                    },
                }
            ]
        }
        result = extract_function_body(method_ir, execution_flow, [], {})
        assert len(result) == 1
        assert isinstance(result[0], CppCallStmt)
        assert result[0].method_name == "AddControllerYawInput"
        assert "InYaw" in result[0].args

    def test_extract_super_call(self):
        """SelfContext=False + MemberParent≠Self → Super::Method()。"""
        method_ir = _make_method_ir("Jump")
        execution_flow = {
            "nodes": [
                {
                    "node_type": "K2Node_CallFunction",
                    "function_name": "Jump",
                    "pure": False,
                    "parameters": {
                        "parameters": [],
                        "function_reference": {
                            "member_parent": "ACharacter",
                            "b_self_context": False,
                        },
                    },
                }
            ]
        }
        result = extract_function_body(method_ir, execution_flow, [], {})
        assert len(result) == 1
        assert result[0].target == "Super"
        assert result[0].method_name == "Jump"

    def test_extract_empty_body(self):
        """无节点的 execution_flow → 空列表。"""
        method_ir = _make_method_ir("Empty")
        execution_flow = {"nodes": []}
        result = extract_function_body(method_ir, execution_flow, [], {})
        assert result == []

    def test_pure_function_marked(self):
        """纯函数节点被标记为 is_pure=True。"""
        method_ir = _make_method_ir("Test")
        execution_flow = {
            "nodes": [
                {
                    "node_type": "K2Node_CallFunction",
                    "function_name": "GetActorRightVector",
                    "pure": True,
                    "parameters": {"parameters": []},
                }
            ]
        }
        result = extract_function_body(method_ir, execution_flow, [], {})
        # Pure 函数走内联决策，可能返回 InlineExprStmt 或 AssignmentStmt
        assert len(result) >= 1
        assert isinstance(result[0], (CppInlineExprStmt, CppAssignmentStmt))

    def test_extract_enhanced_input_handler(self):
        """EnhancedInputAction 触发的函数体 → 正确语句序列。"""
        method_ir = _make_method_ir("Aim", [("Yaw", "float"), ("Pitch", "float")])
        execution_flow = {
            "nodes": [
                {
                    "node_type": "K2Node_CallFunction",
                    "function_name": "AddControllerYawInput",
                    "pure": False,
                    "parameters": {
                        "parameters": [
                            {"name": "InYaw", "direction": "input"},
                        ],
                    },
                },
                {
                    "node_type": "K2Node_CallFunction",
                    "function_name": "AddControllerPitchInput",
                    "pure": False,
                    "parameters": {
                        "parameters": [
                            {"name": "InPitch", "direction": "input"},
                        ],
                    },
                },
            ]
        }
        result = extract_function_body(method_ir, execution_flow, [], {})
        assert len(result) == 2
        assert result[0].method_name == "AddControllerYawInput"
        assert result[1].method_name == "AddControllerPitchInput"


# ============================================================================
# Task 3: Pure 函数内联决策
# ============================================================================

class TestPureInlineDecision:
    """测试 _decide_pure_inline 函数。"""

    def test_single_user_returns_inline_expr(self):
        """单一使用者 → CppInlineExprStmt。"""
        node_info = {
            "data_providers": [{"output_pin": "ReturnValue", "target_node": "NodeA", "target_pin": "X"}]
        }
        result = _decide_pure_inline(node_info, "GetActorRightVector", [], [])
        assert isinstance(result, CppInlineExprStmt)
        assert "GetActorRightVector" in result.expression

    def test_multi_user_returns_assignment(self):
        """多使用者 → CppAssignmentStmt。"""
        node_info = {
            "data_providers": [
                {"output_pin": "ReturnValue", "target_node": "NodeA", "target_pin": "X"},
                {"output_pin": "ReturnValue", "target_node": "NodeB", "target_pin": "Y"},
            ]
        }
        result = _decide_pure_inline(node_info, "GetActorRightVector", [], [])
        assert isinstance(result, CppAssignmentStmt)
        assert result.lhs.startswith("_temp_")

    def test_multiply_vectorfloat_inline(self):
        """Multiply_VectorFloat 内联为 "vec * scale" 格式。"""
        node_info = {"data_providers": []}
        result = _decide_pure_inline(node_info, "Multiply_VectorFloat", ["vec", "scale"], [])
        assert isinstance(result, CppInlineExprStmt)
        assert result.expression == "vec * scale"

    def test_fallback_format(self):
        """非映射函数 fallback 为 "FunctionName(args)" 格式。"""
        node_info = {"data_providers": []}
        result = _decide_pure_inline(node_info, "CustomFunc", ["a", "b"], [])
        assert isinstance(result, CppInlineExprStmt)
        assert result.expression == "CustomFunc(a, b)"


# ============================================================================
# Task 4: 控制流节点翻译
# ============================================================================

class TestControlFlowTranslation:
    """测试控制流节点翻译。"""

    def test_if_then_else_generates_cpp_if_stmt(self):
        """K2Node_IfThenElse → CppIfStmt。"""
        method_ir = _make_method_ir("Test")
        execution_flow = {
            "nodes": [
                {
                    "node_type": "K2Node_IfThenElse",
                    "branch_type": "if",
                    "data_sources": [
                        {
                            "input_pin": "Condition",
                            "data_source": {
                                "data_sources": [
                                    {"source_type": "default_value", "value": "true"}
                                ]
                            },
                        }
                    ],
                }
            ]
        }
        result = extract_function_body(method_ir, execution_flow, [], {})
        assert len(result) == 1
        assert isinstance(result[0], CppIfStmt)
        assert result[0].condition == "true"

    def test_derive_condition_from_default_value(self):
        """条件从 default_value 推导。"""
        node_info = {
            "data_sources": [
                {
                    "input_pin": "Condition",
                    "data_source": {"data_sources": [{"source_type": "default_value", "value": "false"}]},
                }
            ]
        }
        condition = _derive_condition(node_info, [])
        assert condition == "false"

    def test_derive_condition_from_parameter(self):
        """条件从 function_parameter 推导。"""
        node_info = {
            "data_sources": [
                {
                    "input_pin": "Condition",
                    "data_source": {"data_sources": [{"source_type": "function_parameter", "pin": "bIsActive"}]},
                }
            ]
        }
        condition = _derive_condition(node_info, [])
        assert condition == "bIsActive"
