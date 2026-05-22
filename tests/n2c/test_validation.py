"""N2C JSON Schema 验证测试。

覆盖 validate_n2c_json() 对有效/无效输入的识别能力。
零外部依赖 — 纯 Python 实现。
"""
import pytest

from uasset_read.n2c.validation import N2C_JSON_SCHEMA, validate_n2c_json


# ---------------------------------------------------------------------------
# Helper: 构建最小有效 N2CStruct dict
# ---------------------------------------------------------------------------
def _make_valid_json() -> dict:
    """构建一个通过验证的最小 N2CStruct JSON dict。"""
    return {
        "version": "1.0.0",
        "metadata": {"Name": "BP_Test", "BlueprintType": "Normal", "BlueprintClass": "Test"},
        "graphs": [
            {
                "name": "EventGraph",
                "graph_type": "EventGraph",
                "nodes": [
                    {
                        "id": "N1",
                        "type": "CallFunction",
                        "name": "Print String",
                        "comment": "",
                        "pure": False,
                        "latent": False,
                        "input_pins": [
                            {
                                "pin_name": "Exec",
                                "pin_category": "exec",
                                "pin_subcategory": "",
                                "direction": "input",
                                "default_value": None,
                            }
                        ],
                        "output_pins": [],
                        "extra_data": {"member_name": "PrintString", "member_parent": "KismetSystemLibrary"},
                    }
                ],
                "flows": {
                    "execution": [],
                    "data": {},
                },
            }
        ],
        "structs": [],
        "enums": [],
    }


# ---------------------------------------------------------------------------
# Schema 本身验证
# ---------------------------------------------------------------------------
class TestN2CJsonSchema:
    """N2C_JSON_SCHEMA 结构验证。"""

    def test_schema_is_dict(self):
        assert isinstance(N2C_JSON_SCHEMA, dict)

    def test_schema_has_title(self):
        assert N2C_JSON_SCHEMA.get("title") == "N2CStruct"

    def test_schema_has_required_fields(self):
        assert set(N2C_JSON_SCHEMA["required"]) == {"version", "metadata", "graphs"}

    def test_schema_has_defs(self):
        assert "$defs" in N2C_JSON_SCHEMA
        assert "n2c_node" in N2C_JSON_SCHEMA["$defs"]
        assert "n2c_pin" in N2C_JSON_SCHEMA["$defs"]
        assert "n2c_flows" in N2C_JSON_SCHEMA["$defs"]


# ---------------------------------------------------------------------------
# 有效输入验证
# ---------------------------------------------------------------------------
class TestValidateValidInput:
    """合法输入应返回空列表。"""

    def test_minimal_valid_json(self):
        data = {
            "version": "1.0.0",
            "metadata": {"Name": "BP_Test"},
            "graphs": [],
            "structs": [],
            "enums": [],
        }
        assert validate_n2c_json(data) == []

    def test_full_valid_json(self):
        data = _make_valid_json()
        assert validate_n2c_json(data) == []

    def test_valid_json_multiple_nodes(self):
        data = _make_valid_json()
        data["graphs"][0]["nodes"].append({
            "id": "N2",
            "type": "Event",
            "name": "BeginPlay",
            "comment": "",
            "pure": False,
            "latent": False,
            "input_pins": [],
            "output_pins": [],
            "extra_data": {"event_name": "BeginPlay"},
        })
        assert validate_n2c_json(data) == []


# ---------------------------------------------------------------------------
# 非 dict 输入
# ---------------------------------------------------------------------------
class TestNonDictInput:
    """非 dict 输入应被拒绝 (T-70-06: 防御性检查)。"""

    def test_none_input(self):
        errors = validate_n2c_json(None)
        assert len(errors) >= 1
        assert "must be a dict" in errors[0].lower() or "must be a dict" in errors[0]

    def test_list_input(self):
        errors = validate_n2c_json([])
        assert len(errors) >= 1

    def test_string_input(self):
        errors = validate_n2c_json("not a dict")
        assert len(errors) >= 1


# ---------------------------------------------------------------------------
# 顶层 required 字段验证
# ---------------------------------------------------------------------------
class TestTopLevelRequiredFields:
    """顶层 required 字段验证。"""

    def test_empty_dict_missing_version(self):
        errors = validate_n2c_json({})
        assert any("version" in e for e in errors)

    def test_empty_dict_missing_metadata(self):
        errors = validate_n2c_json({})
        assert any("metadata" in e for e in errors)

    def test_empty_dict_missing_graphs(self):
        errors = validate_n2c_json({})
        assert any("graphs" in e for e in errors)

    def test_missing_metadata_name(self):
        data = {"version": "1.0.0", "metadata": {}, "graphs": []}
        errors = validate_n2c_json(data)
        assert any("Name" in e for e in errors)

    def test_version_wrong_type(self):
        data = {"version": 123, "metadata": {"Name": "Test"}, "graphs": []}
        errors = validate_n2c_json(data)
        assert any("version" in e for e in errors)


# ---------------------------------------------------------------------------
# 版本格式验证
# ---------------------------------------------------------------------------
class TestVersionFormat:
    """version 必须符合 semver 格式 (X.Y.Z)。"""

    def test_bad_version_no_dots(self):
        data = {"version": "bad", "metadata": {"Name": "Test"}, "graphs": []}
        errors = validate_n2c_json(data)
        assert any("version" in e for e in errors)

    def test_bad_version_partial(self):
        data = {"version": "1.0", "metadata": {"Name": "Test"}, "graphs": []}
        errors = validate_n2c_json(data)
        assert any("version" in e for e in errors)

    def test_good_version(self):
        data = {"version": "2.1.0", "metadata": {"Name": "Test"}, "graphs": []}
        errors = validate_n2c_json(data)
        assert "version" not in " ".join(errors).lower() or errors == []


# ---------------------------------------------------------------------------
# Graph 验证
# ---------------------------------------------------------------------------
class TestGraphValidation:
    """Graph 数组及内部字段验证。"""

    def test_graph_wrong_type(self):
        data = {"version": "1.0.0", "metadata": {"Name": "Test"}, "graphs": "not an array"}
        errors = validate_n2c_json(data)
        assert any("graphs" in e for e in errors)

    def test_graph_missing_required(self):
        data = {
            "version": "1.0.0",
            "metadata": {"Name": "Test"},
            "graphs": [{"name": "BadGraph"}],  # 缺少 graph_type, nodes, flows
        }
        errors = validate_n2c_json(data)
        assert any("graph_type" in e or "nodes" in e or "flows" in e for e in errors)

    def test_graph_type_not_in_enum(self):
        data = {
            "version": "1.0.0",
            "metadata": {"Name": "Test"},
            "graphs": [{
                "name": "BadGraph",
                "graph_type": "InvalidType",
                "nodes": [],
                "flows": {"execution": [], "data": {}},
            }],
        }
        errors = validate_n2c_json(data)
        assert any("graph_type" in e for e in errors)


# ---------------------------------------------------------------------------
# Node 验证
# ---------------------------------------------------------------------------
class TestNodeValidation:
    """Node 数组及内部字段验证。"""

    def test_node_missing_required(self):
        data = {
            "version": "1.0.0",
            "metadata": {"Name": "Test"},
            "graphs": [{
                "name": "EventGraph",
                "graph_type": "EventGraph",
                "nodes": [{"type": "CallFunction"}],  # 缺少 id, name
                "flows": {"execution": [], "data": {}},
            }],
        }
        errors = validate_n2c_json(data)
        assert any("id" in e for e in errors)
        assert any("name" in e for e in errors)

    def test_node_id_bad_format(self):
        data = {
            "version": "1.0.0",
            "metadata": {"Name": "Test"},
            "graphs": [{
                "name": "EventGraph",
                "graph_type": "EventGraph",
                "nodes": [{"id": "invalid", "type": "CallFunction", "name": "Test"}],
                "flows": {"execution": [], "data": {}},
            }],
        }
        errors = validate_n2c_json(data)
        assert any("id" in e for e in errors)

    def test_node_id_good_format(self):
        data = {
            "version": "1.0.0",
            "metadata": {"Name": "Test"},
            "graphs": [{
                "name": "EventGraph",
                "graph_type": "EventGraph",
                "nodes": [{"id": "N42", "type": "CallFunction", "name": "Test"}],
                "flows": {"execution": [], "data": {}},
            }],
        }
        errors = validate_n2c_json(data)
        assert not any("id" in e.lower() for e in errors) or errors == []

    def test_node_pure_wrong_type(self):
        data = {
            "version": "1.0.0",
            "metadata": {"Name": "Test"},
            "graphs": [{
                "name": "EventGraph",
                "graph_type": "EventGraph",
                "nodes": [{
                    "id": "N1", "type": "CallFunction", "name": "Test",
                    "pure": "yes",  # should be boolean
                }],
                "flows": {"execution": [], "data": {}},
            }],
        }
        errors = validate_n2c_json(data)
        assert any("pure" in e for e in errors)


# ---------------------------------------------------------------------------
# Pin 验证
# ---------------------------------------------------------------------------
class TestPinValidation:
    """Pin 字段验证。"""

    def test_pin_missing_required(self):
        data = {
            "version": "1.0.0",
            "metadata": {"Name": "Test"},
            "graphs": [{
                "name": "EventGraph",
                "graph_type": "EventGraph",
                "nodes": [{
                    "id": "N1", "type": "CallFunction", "name": "Test",
                    "input_pins": [{"pin_category": "exec"}],  # 缺少 pin_name
                    "output_pins": [],
                }],
                "flows": {"execution": [], "data": {}},
            }],
        }
        errors = validate_n2c_json(data)
        assert any("pin_name" in e for e in errors)

    def test_pin_direction_bad_enum(self):
        data = {
            "version": "1.0.0",
            "metadata": {"Name": "Test"},
            "graphs": [{
                "name": "EventGraph",
                "graph_type": "EventGraph",
                "nodes": [{
                    "id": "N1", "type": "CallFunction", "name": "Test",
                    "input_pins": [{"pin_name": "Exec", "pin_category": "exec", "direction": "both"}],
                    "output_pins": [],
                }],
                "flows": {"execution": [], "data": {}},
            }],
        }
        errors = validate_n2c_json(data)
        assert any("direction" in e for e in errors)
