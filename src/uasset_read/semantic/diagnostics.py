"""Diagnostic aggregator — deduplicated, bounded diagnostics."""
from __future__ import annotations

from uasset_read.semantic.models import DiagnosticEntry

_MAX_DIAGNOSTICS = 100


class DiagnosticAggregator:
    """Collects and deduplicates diagnostics."""

    def __init__(self) -> None:
        self._entries: list[DiagnosticEntry] = []
        self._seen: set[tuple[str, str, str]] = set()

    def add(self, severity: str, code: str, message: str) -> None:
        key = (severity, code, message)
        if key not in self._seen and len(self._entries) < _MAX_DIAGNOSTICS:
            self._seen.add(key)
            self._entries.append(DiagnosticEntry(severity=severity, code=code, message=message))

    def from_ir(self, diagnostics_data) -> None:
        for error in diagnostics_data.errors or []:
            self.add("error", "PARSE_ERROR", error)
        for warning in diagnostics_data.warnings or []:
            self.add("warning", "PARSE_WARNING", warning)

    def build(self) -> tuple[DiagnosticEntry, ...]:
        return tuple(sorted(self._entries, key=lambda d: (d.severity, d.code, d.message)))
