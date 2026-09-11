"""
Kismet Decompilation Result — Single function decompilation result.

Data model for Kismet bytecode decompilation output (expressions + diagnostics).
C++ pseudocode generation was retired 2026-09-10 (Gate K).
"""

from dataclasses import dataclass, field, asdict
from typing import Any

BYTECODE_STATUSES = frozenset({"parsed", "no_script", "failed"})


def _validate_bytecode_status(bytecode_status: str) -> None:
    if bytecode_status not in BYTECODE_STATUSES:
        raise ValueError(f"disallowed bytecode_status: {bytecode_status!r}; allowed: {sorted(BYTECODE_STATUSES)}")


def infer_bytecode_confidence(bytecode_status: str) -> str:
    """Classify the confidence of a public function body.

    Keep this shared by direct Kismet serialization and the v2 decompile output so
    callers cannot receive conflicting provenance for the same function body.
    """
    if bytecode_status == "failed":
        return "failed"
    if bytecode_status == "no_script":
        return "no_script"
    return "verified"


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
    local_variables: list[dict[str, str]] = field(default_factory=list)
    expressions: list[Any] = field(default_factory=list)
    bytecode_source: str = "unknown"
    parameters: list[dict[str, object]] = field(default_factory=list)
    return_type: str = "void"
    native_signature: bool = False
    error_code: str | None = None
    error_message: str | None = None
    error_context: dict[str, Any] | None = None
    script_metrics: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)
    fallback_reasons: list[str] = field(default_factory=list)
    function_ref_stats: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_bytecode_status(self.bytecode_status)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["bytecode_confidence"] = infer_bytecode_confidence(
            bytecode_status=self.bytecode_status,
        )
        d["expressions"] = [
            e.to_dict() if hasattr(e, "to_dict") else str(e) for e in self.expressions
        ]
        return {k: v for k, v in d.items() if v is not None}


__all__ = ["KismetDecompiledResult", "infer_bytecode_confidence", "BYTECODE_STATUSES"]
