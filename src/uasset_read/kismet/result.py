"""
Kismet Decompilation Result — Single function decompilation result.

Data model for Kismet bytecode decompilation output.
"""

from dataclasses import dataclass, field
from typing import Any


# Allowed (bytecode_status, translation_status) pairs
ALLOWED_STATUS_PAIRS = frozenset(
    {
        ("parsed", "complete"),
        ("parsed", "partial"),
        ("parsed", "failed"),
        ("no_script", "not_applicable"),
        ("failed", "not_applicable"),
    }
)


def _validate_status_pair(bytecode_status: str, translation_status: str) -> None:
    """Raise ValueError for disallowed (bytecode_status, translation_status) pairs."""
    if (bytecode_status, translation_status) not in ALLOWED_STATUS_PAIRS:
        raise ValueError(
            f"disallowed status pair: ({bytecode_status!r}, {translation_status!r}); "
            f"allowed: {sorted(ALLOWED_STATUS_PAIRS)}"
        )


def infer_bytecode_confidence(
    bytecode_status: str = "unknown",
    logic_source: str = "current_asset",
) -> str:
    """Classify the confidence of a public function body.

    Keep this shared by direct Kismet serialization and PackageIR projection so
    callers cannot receive conflicting provenance for the same function body.
    """
    if logic_source == "graph_topology":
        return "graph_topology"
    if bytecode_status == "failed":
        return "failed"
    if bytecode_status == "no_script":
        return "no_script"
    return "verified"


@dataclass
class KismetDecompiledResult:
    """
    Single function decompilation result (D-04).

    Contains all information extracted from a Blueprint UStruct's bytecode:
    - function_name: Name of the decompiled function
    - signature: Full C++ function signature (return type + params)
    - local_variables: List of local variable type info (currently unpopulated)
    - cpp_code: Complete C++ pseudocode body
    - expressions: Raw KismetExpression list for debugging

    Supports JSON serialization via to_dict().
    """

    function_name: str  # e.g. "ExecuteUbergraph_MyBP"
    signature: str  # e.g. "void ExecuteUbergraph_MyBP(int32 EntryPoint)"
    local_variables: list[dict[str, str]]  # [{name, type}, ...] (currently unpopulated)
    cpp_code: str  # C++ pseudocode string (multi-line, indented)
    expressions: list[Any] = field(default_factory=list)  # raw KismetExpression list for debugging
    bytecode_source: str = "unknown"
    bytecode_status: str = "unknown"
    translation_status: str = "not_applicable"
    # Native field-derived signature data
    parameters: list[dict[str, object]] = field(default_factory=list)
    return_type: str = "void"
    native_signature: bool = False  # True when parameters/return_type from native fields
    # "complete" | "partial" | "failed" | "not_applicable"
    error_code: str | None = None
    error_message: str | None = None
    error_context: dict[str, Any] | None = None
    script_metrics: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)
    fallback_reasons: list[str] = field(default_factory=list)
    semantic_calls: list[dict[str, Any]] = field(default_factory=list)
    logic_source: str = "current_asset"
    function_ref_stats: dict[str, Any] = field(default_factory=dict)
    structured_rate: float | None = None

    def __post_init__(self) -> None:
        """Validate status pair on construction."""
        _validate_status_pair(self.bytecode_status, self.translation_status)

    def to_dict(self) -> dict:
        """
        JSON-serializable dict.

        expressions field is serialized via each expression's to_dict() if available,
        else falls back to str() representation.
        """
        d = {
            "function_name": self.function_name,
            "signature": self.signature,
            "local_variables": self.local_variables,
            "cpp_code": self.cpp_code,
            "bytecode_source": self.bytecode_source,
            "bytecode_status": self.bytecode_status,
            "translation_status": self.translation_status,
            "parameters": self.parameters,
            "return_type": self.return_type,
            "native_signature": self.native_signature,
            "bytecode_confidence": infer_bytecode_confidence(
                bytecode_status=self.bytecode_status,
                logic_source=self.logic_source,
            ),
            "warnings": self.warnings,
            "fallback_reasons": self.fallback_reasons,
            "semantic_calls": self.semantic_calls,
            "logic_source": self.logic_source,
            "function_ref_stats": self.function_ref_stats,
            "structured_rate": self.structured_rate,
            "expressions": [e.to_dict() if hasattr(e, "to_dict") else str(e) for e in self.expressions],
        }
        if self.error_code is not None:
            d["error_code"] = self.error_code
        if self.error_message is not None:
            d["error_message"] = self.error_message
        if self.error_context is not None:
            d["error_context"] = self.error_context
        if self.script_metrics is not None:
            d["script_metrics"] = self.script_metrics
        return d


__all__ = ["KismetDecompiledResult", "infer_bytecode_confidence", "ALLOWED_STATUS_PAIRS"]
