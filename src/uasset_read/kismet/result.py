"""
Kismet Decompilation Result — Single function decompilation result.

Data model for Kismet bytecode decompilation output (expressions + diagnostics).
C++ pseudocode generation was retired 2026-09-10 (Gate K).
"""

from dataclasses import dataclass, field, asdict
from typing import Any

# status -> public confidence (K0 contract)
BYTECODE_CONFIDENCE: dict[str, str] = {
    "parsed": "verified",
    "no_script": "no_script",
    "failed": "failed",
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
            f"disallowed bytecode_status: {bytecode_status!r}; "
            f"allowed: {sorted(BYTECODE_CONFIDENCE)}"
        ) from None


@dataclass
class KismetDecompiledResult:
    """
    Single function decompilation result.

    Contains information extracted from a Blueprint UStruct's bytecode:
    - function_name: Name of the decompiled function
    - signature: Full C++ function signature (return type + params) from native fields
    - expressions: Parsed KismetExpression list (public function-logic representation)

    Supports JSON serialization via to_dict().
    """

    function_name: str
    signature: str
    bytecode_status: str
    expressions: list[Any] = field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    error_context: dict[str, Any] | None = None
    script_metrics: dict[str, Any] | None = None
    fallback_reasons: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        infer_bytecode_confidence(self.bytecode_status)  # validates

    def to_dict(self) -> dict:
        d = asdict(self)
        d["bytecode_confidence"] = infer_bytecode_confidence(self.bytecode_status)
        d["expressions"] = [
            e.to_dict() if hasattr(e, "to_dict") else str(e) for e in self.expressions
        ]
        return {k: v for k, v in d.items() if v is not None}


__all__ = ["KismetDecompiledResult", "infer_bytecode_confidence", "BYTECODE_CONFIDENCE"]
