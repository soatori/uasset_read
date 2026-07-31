"""
Kismet Decompilation Result — Single function decompilation result.

Data model for Kismet bytecode decompilation output.
"""

import json
from dataclasses import dataclass, field
from typing import Any


def infer_bytecode_confidence(
    fallback_reasons: list[str],
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
    if "serial_scan_recovery" in fallback_reasons:
        return "heuristic"
    if "bpgc_bytecode_extraction" in fallback_reasons:
        return "fallback"
    return "verified"


@dataclass
class KismetDecompiledResult:
    """
    Single function decompilation result (D-04).

    Contains all information extracted from a Blueprint UStruct's bytecode:
    - function_name: Name of the decompiled function
    - signature: Full C++ function signature (return type + params)
    - local_variables: List of local variable type info from TypeRegistry
    - cpp_code: Complete C++ pseudocode body
    - expressions: Raw KismetExpression list for debugging

    Supports JSON serialization via to_dict() and to_json().
    """

    function_name: str                    # e.g. "ExecuteUbergraph_MyBP"
    signature: str                         # e.g. "void ExecuteUbergraph_MyBP(int32 EntryPoint)"
    local_variables: list[dict[str, str]]  # [{name, type}, ...] from TypeRegistry snapshot
    cpp_code: str                          # C++ pseudocode string (multi-line, indented)
    expressions: list[Any] = field(default_factory=list)  # raw KismetExpression list for debugging
    bytecode_source: str = "unknown"
    bytecode_status: str = "unknown"
    warnings: list[str] = field(default_factory=list)
    fallback_reasons: list[str] = field(default_factory=list)
    semantic_calls: list[dict[str, Any]] = field(default_factory=list)
    logic_source: str = "current_asset"
    function_ref_stats: dict[str, Any] = field(default_factory=dict)
    structured_rate: float | None = None

    def to_dict(self) -> dict:
        """
        JSON-serializable dict.

        expressions field is serialized via each expression's to_dict() if available,
        else falls back to str() representation.
        """
        return {
            "function_name": self.function_name,
            "signature": self.signature,
            "local_variables": self.local_variables,
            "cpp_code": self.cpp_code,
            "bytecode_source": self.bytecode_source,
            "bytecode_status": self.bytecode_status,
            "bytecode_confidence": infer_bytecode_confidence(
                self.fallback_reasons,
                bytecode_status=self.bytecode_status,
                logic_source=self.logic_source,
            ),
            "warnings": self.warnings,
            "fallback_reasons": self.fallback_reasons,
            "semantic_calls": self.semantic_calls,
            "logic_source": self.logic_source,
            "function_ref_stats": self.function_ref_stats,
            "structured_rate": self.structured_rate,
            "expressions": [
                e.to_dict() if hasattr(e, "to_dict") else str(e)
                for e in self.expressions
            ],
        }

    def to_json(self, indent: int = 2) -> str:
        """JSON string view (D-08)."""
        return json.dumps(self.to_dict(), indent=indent)

    def to_cpp_string(self) -> str:
        """C++ pseudocode string view (D-08). Returns cpp_code directly."""
        return self.cpp_code


__all__ = ["KismetDecompiledResult", "infer_bytecode_confidence"]
