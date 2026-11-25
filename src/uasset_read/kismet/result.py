"""
Kismet Decompilation Result — Single function decompilation result.

Data model for Kismet bytecode decompilation output (expressions + diagnostics).
C++ pseudocode generation was retired 2026-09-10 (Gate K).
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, asdict
from typing import TYPE_CHECKING, Any

from uasset_read.models.byte_ranges import ByteRegion, project_region
from uasset_read.models.diagnostics import Diagnostic
from uasset_read.parsers.blueprint.bytecode import BytecodeInstruction, project_instruction
from uasset_read.parsers.blueprint.control_flow import ControlFlowGraph, project_cfg

if TYPE_CHECKING:
    from uasset_read.kismet.native_fields import NativeFieldDeclaration

# status -> public confidence (analysis vocabulary: parsed|partial|unavailable)
BYTECODE_CONFIDENCE: dict[str, str] = {
    "parsed": "verified",
    "partial": "partial",
    "unavailable": "unavailable",
}


def infer_bytecode_confidence(bytecode_status: str) -> str:
    """Classify the confidence of a public function body.

    Shared by direct Kismet serialization and the v2 decompile output so
    callers cannot receive conflicting provenance for the same function body.
    """
    try:
        return BYTECODE_CONFIDENCE[bytecode_status]
    except KeyError:
        raise ValueError(
            f"disallowed bytecode_status: {bytecode_status!r}; allowed: {sorted(BYTECODE_CONFIDENCE)}"
        ) from None


@dataclass
class KismetDecompiledResult:
    """
    Single function decompilation result.

    Contains information extracted from a Blueprint UStruct's bytecode:
    - function_name: Name of the decompiled function
    - signature: Full C++ function signature (return type + params) from native fields
    - expressions: Parsed KismetExpression list (public function-logic representation)

    Identity fields (export_index / object_id / class_name) come from the
    export table before parsing; a successful parse never reconstructs
    identity from the display function name. ``script_source_range`` is the
    package-source range of the serialized script region.

    Supports JSON serialization via to_dict().
    """

    function_name: str
    signature: str
    bytecode_status: str
    export_index: int = -1
    object_id: str = ""
    class_name: str = ""
    script_source_range: ByteRegion | None = None
    expressions: list[Any] = field(default_factory=list)
    # Typed instruction IR + CFG are shared with FunctionAnalysis.
    instructions: list[BytecodeInstruction] = field(default_factory=list)
    cfg: ControlFlowGraph | None = None
    error_code: str | None = None
    error_message: str | None = None
    error_context: dict[str, Any] | None = None
    script_metrics: dict[str, Any] | None = None
    fallback_reasons: list[str] = field(default_factory=list)
    # Native FProperty declarations already decoded by ufunction_reader
    # (native_property_count > 0). Empty means "no signature evidence".
    native_fields: list[NativeFieldDeclaration] = field(default_factory=list)
    # UFunction::FunctionFlags (EFunctionFlags) from the native UFunction tail.
    function_flags: int | None = None
    # Structured CFG/diagnostics from the decompile pass (plan C1):
    # CFG_JUMP_TARGET_UNRESOLVED reaches semantic.functions[].diagnostics
    # through legacy_reader's FunctionAnalysis seeding from this field.
    errors: list[Diagnostic] = field(default_factory=list)

    def __post_init__(self) -> None:
        infer_bytecode_confidence(self.bytecode_status)  # validates

    def to_dict(self) -> dict:
        projected_fields = {"instructions", "cfg", "expressions", "native_fields", "errors", "script_source_range"}
        d = {
            item.name: deepcopy(getattr(self, item.name))
            for item in self.__dataclass_fields__.values()
            if item.name not in projected_fields
        }
        d["native_fields"] = [asdict(item) for item in self.native_fields]
        d["errors"] = [asdict(item) for item in self.errors]
        d["bytecode_confidence"] = infer_bytecode_confidence(self.bytecode_status)
        d["expressions"] = [e.to_dict() for e in self.expressions]
        d["instructions"] = [project_instruction(i) for i in self.instructions]
        if self.cfg is not None:
            d["cfg"] = project_cfg(self.cfg)
        if self.script_source_range is not None:
            d["script_source_range"] = project_region(self.script_source_range)
        return {k: v for k, v in d.items() if v is not None}


__all__ = ["KismetDecompiledResult", "infer_bytecode_confidence", "BYTECODE_CONFIDENCE"]
