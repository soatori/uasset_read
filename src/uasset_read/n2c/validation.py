"""N2C JSON Schema 定义与验证函数。

纯 Python 实现，零外部依赖。
验证 N2CStruct to_dict() 输出是否符合 JSON Schema 约束。

Trust boundary (T-70-06): validate_n2c_json 不信任输入，逐层检查所有字段。
Schema 本身是不可变常量。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

# ============================================================================
# N2C JSON Schema 定义 (Draft-07 compatible)
# ============================================================================

N2C_JSON_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "N2CStruct",
    "type": "object",
    "required": ["version", "metadata", "graphs"],
    "properties": {
        "version": {
            "type": "string",
            "pattern": r"^\d+\.\d+\.\d+$",
        },
        "metadata": {
            "type": "object",
            "required": ["Name"],
            "properties": {
                "Name": {"type": "string"},
                "BlueprintType": {"type": "string"},
                "BlueprintClass": {"type": "string"},
            },
        },
        "graphs": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "graph_type", "nodes", "flows"],
                "properties": {
                    "name": {"type": "string"},
                    "graph_type": {
                        "type": "string",
                        "enum": ["EventGraph", "Function", "Macro", "Animation"],
                    },
                    "nodes": {
                        "type": "array",
                        "items": {"$ref": "#/$defs/n2c_node"},
                    },
                    "flows": {"$ref": "#/$defs/n2c_flows"},
                },
            },
        },
        "structs": {"type": "array"},
        "enums": {"type": "array"},
        "blueprint": {
            "type": "object",
            "properties": {
                "blueprint_name": {"type": "string"},
                "parent_class": {"type": "string"},
                "variables": {"type": "array"},
                "functions": {"type": "array"},
                "events": {"type": "array"},
            },
        },
        "properties": {"type": "array"},
        "decompiled_functions": {"type": "array"},
    },
    "$defs": {
        "n2c_node": {
            "type": "object",
            "required": ["id", "type", "name"],
            "properties": {
                "id": {
                    "type": "string",
                    "pattern": r"^N\d+$",
                },
                "type": {"type": "string"},
                "name": {"type": "string"},
                "comment": {"type": "string"},
                "pure": {"type": "boolean"},
                "latent": {"type": "boolean"},
                "input_pins": {
                    "type": "array",
                    "items": {"$ref": "#/$defs/n2c_pin"},
                },
                "output_pins": {
                    "type": "array",
                    "items": {"$ref": "#/$defs/n2c_pin"},
                },
                "extra_data": {"type": "object"},
            },
        },
        "n2c_pin": {
            "type": "object",
            "required": ["pin_name", "pin_category"],
            "properties": {
                "pin_name": {"type": "string"},
                "pin_category": {"type": "string"},
                "pin_subcategory": {"type": "string"},
                "direction": {
                    "type": "string",
                    "enum": ["input", "output"],
                },
                "default_value": {},
            },
        },
        "n2c_flows": {
            "type": "object",
            "properties": {
                "execution": {"type": "array"},
                "data": {"type": "object"},
            },
        },
    },
}

# ============================================================================
# 内部验证引擎
# ============================================================================

# Python type name -> JSON Schema type name mapping
_JSON_TYPE_MAP = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}

# Reverse lookup for type checking
_TYPE_CHECK_MAP = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
}

# Compiled patterns cache
_PATTERN_CACHE: Dict[str, re.Pattern] = {}


def _compile_pattern(pattern: str) -> re.Pattern:
    """Compile and cache regex pattern."""
    if pattern not in _PATTERN_CACHE:
        _PATTERN_CACHE[pattern] = re.compile(pattern)
    return _PATTERN_CACHE[pattern]


def _get_def(schema: dict, ref: str) -> dict:
    """Resolve a $ref to its definition in $defs."""
    # Support format: #/$defs/definition_name
    parts = ref.split("/")
    if len(parts) >= 3 and parts[-2] == "$defs":
        def_name = parts[-1]
        return schema.get("$defs", {}).get(def_name, {})
    return {}


def _check_type(value: Any, expected_type: str) -> bool:
    """Check if value matches the expected JSON Schema type."""
    if expected_type not in _TYPE_CHECK_MAP:
        return True  # Unknown type spec, skip
    python_type = _TYPE_CHECK_MAP[expected_type]

    # Special case: in JSON Schema, boolean is NOT integer
    # Python bool is subclass of int, so we need explicit check
    if expected_type == "integer" and isinstance(value, bool):
        return False
    if expected_type == "number" and isinstance(value, bool):
        return False

    return isinstance(value, python_type)


def _validate_value(value: Any, prop_schema: dict, full_schema: dict, path: str, errors: list) -> None:
    """Validate a single value against its property schema."""
    # Type check
    if "type" in prop_schema:
        if not _check_type(value, prop_schema["type"]):
            errors.append(f"Type error at '{path}': expected {prop_schema['type']}, got {type(value).__name__}")
            return  # Don't continue type-specific checks if type is wrong

    # Enum check
    if "enum" in prop_schema:
        if value not in prop_schema["enum"]:
            errors.append(
                f"Invalid value at '{path}': '{value}' not in allowed values {prop_schema['enum']}"
            )

    # Pattern check (for strings)
    if "pattern" in prop_schema and isinstance(value, str):
        pattern = prop_schema["pattern"]
        if not _compile_pattern(pattern).match(value):
            errors.append(
                f"Pattern mismatch at '{path}': '{value}' does not match '{pattern}'"
            )

    # Object validation
    if isinstance(value, dict):
        _validate_object(value, prop_schema, full_schema, path, errors)

    # Array validation
    if isinstance(value, list):
        _validate_array(value, prop_schema, full_schema, path, errors)


def _validate_object(obj: dict, schema: dict, full_schema: dict, path: str, errors: list) -> None:
    """Validate an object against its schema."""
    # Check required fields
    required = schema.get("required", [])
    for field_name in required:
        if field_name not in obj:
            errors.append(f"Missing required field: '{field_name}' at '{path or '(root)'}'")

    # Validate properties
    properties = schema.get("properties", {})
    for key, value in obj.items():
        if key in properties:
            prop_schema = properties[key]
            child_path = f"{path}.{key}" if path else key
            _validate_value(value, prop_schema, full_schema, child_path, errors)


def _validate_array(arr: list, schema: dict, full_schema: dict, path: str, errors: list) -> None:
    """Validate an array against its schema."""
    items_schema = schema.get("items")
    if items_schema is None:
        return  # No items constraint

    for i, item in enumerate(arr):
        # Resolve $ref if present
        if "$ref" in items_schema:
            item_schema = _get_def(full_schema, items_schema["$ref"])
        else:
            item_schema = items_schema

        item_path = f"{path}[{i}]"
        _validate_value(item, item_schema, full_schema, item_path, errors)


# ============================================================================
# 公共 API
# ============================================================================


def validate_n2c_json(data: Any) -> List[str]:
    """验证 N2C JSON 数据是否符合 N2C_JSON_SCHEMA。

    Args:
        data: 待验证的字典（通常为 N2CStruct.to_dict() 的输出）

    Returns:
        错误消息列表。空列表表示验证通过。
    """
    # T-70-06: 防御性检查 -- 不信任输入
    if not isinstance(data, dict):
        return ["Input must be a dict"]

    errors: List[str] = []
    _validate_object(data, N2C_JSON_SCHEMA, N2C_JSON_SCHEMA, "", errors)
    return errors
