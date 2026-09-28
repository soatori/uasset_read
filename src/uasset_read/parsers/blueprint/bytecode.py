"""Kismet bytecode instruction normalization (plan Task 7).

Maps top-level ``parse_bytecode_stream`` expression records onto analysis
``BytecodeInstruction`` objects. Nested expression trees stay on
``instruction.expression``; they are never promoted to CFG nodes. Dual
offsets come from the archive-captured StatementIndex / SerializedStart /
SerializedEnd fields.
"""

from __future__ import annotations

import base64
import dataclasses
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal

from uasset_read.kismet.expressions import (
    EX_ComputedJump,
    EX_FinalFunction,
    EX_Jump,
    EX_JumpIfNot,
    EX_Let,
    EX_LetBase,
    EX_LetValueOnPersistentFrame,
    EX_VirtualFunction,
    KismetExpression,
    OpaqueExpression,
)
from uasset_read.models.analysis import OpaqueOperand
from uasset_read.models.byte_ranges import ByteRegion, project_region

# Call-family opcodes that carry a resolved target name/index.
_CALL_OPCODES = frozenset(
    {
        "EX_FinalFunction",
        "EX_VirtualFunction",
        "EX_CallMath",
        "EX_LocalFinalFunction",
        "EX_LocalVirtualFunction",
    }
)

_LET_BASE_NAMES = frozenset(
    {
        "EX_Let",
        "EX_LetBool",
        "EX_LetDelegate",
        "EX_LetMulticastDelegate",
        "EX_LetObj",
        "EX_LetWeakObjPtr",
        "EX_LetValueOnPersistentFrame",
    }
)

# Why a record has no source_node_id: no bytecode<->graph mapping exists.
# Never guessed (audit item 3); normal-mode content, not evidence.
DEBUG_MAPPING_UNAVAILABLE = "debug_mapping_unavailable"


@dataclass
class BytecodeInstruction:
    """One top-level script statement with dual offsets and analysis fields."""

    statement_index: int  # UE logical script address (StatementIndex/CodeOffset)
    statement_ordinal: int  # zero-based order among top-level expressions
    logical_end: int  # bytecode_index after this top-level expression
    serialized_start: int
    serialized_end: int
    opcode: str
    operands: dict[str, Any]
    expression: Any
    reads: list[str]
    writes: list[str]
    call_target: str | None
    jump_target_statement_index: int | None
    jump_kind: Literal["unconditional", "conditional_false", "computed", "none"]
    source_node_id: str | None
    parse_status: Literal["parsed", "partial", "unavailable"] = "parsed"
    source_node_reason: str | None = None


def _variable_name(expr: Any) -> str | None:
    """Best-effort display name for a variable reference expression."""
    if expr is None:
        return None
    var = getattr(expr, "Variable", None)
    if var is None:
        return None
    text = str(var)
    return text if text and text != "None" else None


def _extract_operands(expr: KismetExpression) -> dict[str, Any]:
    """Collect known operand fields from an expression into a dict."""
    operands: dict[str, Any] = {}

    if isinstance(expr, OpaqueExpression):
        operands["raw_region"] = project_region(expr.raw_region)
        operands["token"] = expr.token
        operands["reason"] = expr.reason
        return operands

    if isinstance(expr, (EX_FinalFunction, EX_VirtualFunction)):
        # EX_CallMath subclasses EX_FinalFunction; EX_Local* subclass these.
        parameters = list(getattr(expr, "Parameters", None) or [])
        operands["parameters"] = parameters
        if isinstance(expr, EX_VirtualFunction):
            operands["name"] = expr.VirtualFunctionName
        else:
            operands["stack_node"] = getattr(expr, "StackNode", None)
    elif isinstance(expr, EX_JumpIfNot):
        operands["code_offset"] = expr.CodeOffset
        operands["boolean_expression"] = expr.BooleanExpression
    elif isinstance(expr, EX_Jump):
        operands["code_offset"] = expr.CodeOffset
    elif isinstance(expr, EX_ComputedJump):
        operands["code_offset_expression"] = expr.CodeOffsetExpression
    elif isinstance(expr, EX_Let):
        operands["property"] = expr.Property
        operands["variable"] = expr.Variable
        operands["assignment"] = expr.Assignment
    elif isinstance(expr, EX_LetBase):
        operands["variable"] = expr.Variable
        operands["assignment"] = expr.Assignment
    elif isinstance(expr, EX_LetValueOnPersistentFrame):
        operands["destination_property"] = expr.DestinationProperty
        operands["assignment"] = expr.AssignmentExpression
    else:
        # Generic retention: copy public dataclass-ish fields when present.
        # EX_Return and the Context/Container/Cast/Switch families land here —
        # their retained payload fields become operands automatically.
        if dataclasses.is_dataclass(expr) and not isinstance(expr, type):
            for f in dataclasses.fields(expr):
                if f.name in {"Token"}:
                    continue
                operands[f.name] = getattr(expr, f.name)

    return operands


def _derive_call_target(opcode: str, operands: dict[str, Any]) -> str | None:
    if opcode not in _CALL_OPCODES:
        return None
    name = operands.get("name")
    if isinstance(name, str) and name:
        return name
    stack_node = operands.get("stack_node")
    if isinstance(stack_node, int) and stack_node != 0:
        return f"export:{stack_node - 1}" if stack_node > 0 else f"import:{-stack_node - 1}"
    return None


def _derive_reads_writes(opcode: str, operands: dict[str, Any]) -> tuple[list[str], list[str]]:
    reads: list[str] = []
    writes: list[str] = []
    if opcode in _LET_BASE_NAMES or opcode.startswith("EX_Let"):
        dest = _variable_name(operands.get("variable")) or _variable_name(operands.get("destination_property"))
        if dest:
            writes.append(dest)
        assign = operands.get("assignment")
        if assign is not None:
            assign_name = _variable_name(assign)
            if assign_name:
                reads.append(assign_name)
    return reads, writes


def _derive_jump(
    opcode: str, operands: dict[str, Any]
) -> tuple[int | None, Literal["unconditional", "conditional_false", "computed", "none"]]:
    if opcode == "EX_JumpIfNot":
        target = operands.get("code_offset")
        return (target if isinstance(target, int) else None), "conditional_false"
    if opcode == "EX_Jump":
        target = operands.get("code_offset")
        return (target if isinstance(target, int) else None), "unconditional"
    if opcode == "EX_ComputedJump":
        return None, "computed"
    return None, "none"


def normalize_instructions(expressions: list[KismetExpression]) -> list[BytecodeInstruction]:
    """One instruction per top-level statement from parse_bytecode_stream.

    Nested expression trees stay on ``instruction.expression``; they are not
    promoted to CFG nodes. Dual offsets come from the archive-captured
    StatementIndex / SerializedStart / SerializedEnd fields.
    """
    instructions: list[BytecodeInstruction] = []
    count = len(expressions)
    for ordinal, expr in enumerate(expressions):
        token = getattr(expr, "Token", None)
        if isinstance(expr, OpaqueExpression):
            opcode = f"Opaque_0x{expr.token:02X}"
            parse_status: Literal["parsed", "partial", "unavailable"] = "unavailable"
        else:
            opcode = token.name if token is not None else type(expr).__name__
            parse_status = "parsed"

        operands = _extract_operands(expr)
        statement_index = getattr(expr, "StatementIndex", ordinal)
        serialized_start = getattr(expr, "SerializedStart", -1)
        serialized_end = getattr(expr, "SerializedEnd", -1)

        # Logical end: next top-level statement's StatementIndex when known;
        # otherwise the byte length of this statement's logical token span.
        if ordinal + 1 < count:
            logical_end = getattr(expressions[ordinal + 1], "StatementIndex", statement_index + 1)
        else:
            logical_end = statement_index + 1
        if logical_end <= statement_index:
            logical_end = statement_index + 1

        jump_target, jump_kind = _derive_jump(opcode, operands)
        call_target = _derive_call_target(opcode, operands)
        reads, writes = _derive_reads_writes(opcode, operands)

        source_node_id: str | None = None
        instructions.append(
            BytecodeInstruction(
                statement_index=statement_index,
                statement_ordinal=ordinal,
                logical_end=logical_end,
                serialized_start=serialized_start,
                serialized_end=serialized_end,
                opcode=opcode,
                operands=operands,
                expression=expr,
                reads=reads,
                writes=writes,
                call_target=call_target,
                jump_target_statement_index=jump_target,
                jump_kind=jump_kind,
                source_node_id=source_node_id,
                parse_status=parse_status,
                source_node_reason=DEBUG_MAPPING_UNAVAILABLE if source_node_id is None else None,
            )
        )
    return instructions


def project_operand(value: Any) -> Any:
    """Recursively project operands to JSON-safe values without repr()."""
    if isinstance(value, OpaqueOperand):
        return {
            "kind": "opaque_operand",
            "role": value.role,
            "source_range": project_region(value.source_range),
            "payload_ref": value.payload_ref,
            "reason": value.reason,
        }
    if isinstance(value, ByteRegion):
        return project_region(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {
            "kind": "bytes",
            "encoding": "base64",
            "value": base64.b64encode(bytes(value)).decode("ascii"),
        }
    if isinstance(value, Enum):
        return project_operand(value.value)
    if hasattr(value, "to_dict"):
        return project_operand(value.to_dict())
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        # Route each field VALUE through project_operand before recursing:
        # dataclasses.asdict() would pre-flatten ByteRegion/OpaqueOperand
        # fields into raw dicts that are not schema-shaped Regions.
        return project_operand({f.name: getattr(value, f.name) for f in dataclasses.fields(value)})
    if isinstance(value, (list, tuple)):
        return [project_operand(item) for item in value]
    if isinstance(value, dict):
        return {str(key): project_operand(item) for key, item in value.items()}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return {
        "kind": "opaque_operand",
        "role": "unprojected_value",
        "source_range": None,
        "payload_ref": None,
        "reason": type(value).__name__,
    }


def project_instruction(instruction: BytecodeInstruction) -> dict[str, Any]:
    """Project one instruction to a JSON-safe dict."""
    return {
        "statement_index": instruction.statement_index,
        "statement_ordinal": instruction.statement_ordinal,
        "logical_end": instruction.logical_end,
        "serialized_start": instruction.serialized_start,
        "serialized_end": instruction.serialized_end,
        "opcode": instruction.opcode,
        "operands": project_operand(instruction.operands),
        "expression": project_operand(instruction.expression),
        "reads": list(instruction.reads),
        "writes": list(instruction.writes),
        "call_target": instruction.call_target,
        "jump_target_statement_index": instruction.jump_target_statement_index,
        "jump_kind": instruction.jump_kind,
        "source_node_id": instruction.source_node_id,
        "source_node_reason": instruction.source_node_reason,
        "parse_status": instruction.parse_status,
    }
