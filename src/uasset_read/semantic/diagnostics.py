"""Diagnostic aggregator — collects diagnostics from parse + build stages."""
from __future__ import annotations

from typing import TYPE_CHECKING

from uasset_read.semantic.ir import DiagnosticEntry

if TYPE_CHECKING:
    from uasset_read.models.ir import DiagnosticsDataIR


class DiagnosticAggregator:
    """Collects and deduplicates diagnostics."""

    def __init__(self) -> None:
        self._entries: list[DiagnosticEntry] = []
        self._seen: set[tuple[str, str, str]] = set()

    def add(self, severity: str, code: str, message: str) -> None:
        """Add a diagnostic entry.

        Args:
            severity: "error" | "warning" | "info"
            code: Machine-readable diagnostic code
            message: Human-readable message
        """
        key = (severity, code, message)
        if key not in self._seen:
            self._seen.add(key)
            self._entries.append(DiagnosticEntry(
                severity=severity,
                code=code,
                message=message,
            ))

    def from_ir(self, diagnostics_data: DiagnosticsDataIR) -> None:
        """Collect diagnostics from DiagnosticsDataIR.

        Args:
            diagnostics_data: DiagnosticsDataIR from PackageIR
        """
        for error in diagnostics_data.errors or []:
            self.add("error", "PARSE_ERROR", error)
        for warning in diagnostics_data.warnings or []:
            self.add("warning", "PARSE_WARNING", warning)

    def build(self) -> tuple[DiagnosticEntry, ...]:
        """Build the immutable diagnostic tuple.

        Returns:
            Tuple of DiagnosticEntry, sorted by (severity, code)
        """
        return tuple(sorted(
            self._entries,
            key=lambda d: (d.severity, d.code),
        ))
