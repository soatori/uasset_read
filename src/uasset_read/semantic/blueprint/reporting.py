"""Blueprint coverage entries and aggregated diagnostics (BP-16)."""
from __future__ import annotations

_MAX_OCCURRENCES = 8


class BlueprintReporting:
    """Collects coverage entries and aggregated diagnostics.

    Coverage entries: {"scope": str, "status": "partial"|"unavailable"|"truncated",
    optional: reason, declared, emitted, omitted}. Diagnostics are aggregated
    by (code, scope, severity, effect); message/occurrence never joins the
    identity (BP-16). Debug occurrences are bounded.
    """

    def __init__(self) -> None:
        self._coverage: list[dict] = []
        self._coverage_scopes: set[str] = set()
        self._diags: dict[tuple, dict] = {}

    def coverage(self, scope: str, status: str, *, reason: str = "",
                 declared: int | None = None, emitted: int | None = None,
                 omitted: int | None = None) -> None:
        if scope in self._coverage_scopes:
            return
        self._coverage_scopes.add(scope)
        entry: dict = {"scope": scope, "status": status}
        if reason:
            entry["reason"] = reason
        if declared is not None:
            entry["declared"] = declared
        if emitted is not None:
            entry["emitted"] = emitted
        if omitted is not None:
            entry["omitted"] = omitted
        self._coverage.append(entry)

    def diagnostic(self, code: str, scope: str, severity: str, effect: str,
                   occurrence: dict | None = None) -> None:
        key = (code, scope, severity, effect)
        entry = self._diags.get(key)
        if entry is None:
            entry = {"code": code, "scope": scope, "severity": severity,
                     "effect": effect, "count": 0, "_occurrences": []}
            self._diags[key] = entry
        entry["count"] += 1
        if occurrence is not None and len(entry["_occurrences"]) < _MAX_OCCURRENCES:
            entry["_occurrences"].append(occurrence)

    def coverage_entries(self) -> list[dict]:
        return sorted(self._coverage, key=lambda e: e["scope"])

    def diagnostics_entries(self, mode: str) -> list[dict]:
        entries = []
        for entry in sorted(self._diags.values(),
                            key=lambda e: (e["severity"], e["code"], e["scope"], e["effect"])):
            item = {k: v for k, v in entry.items() if k != "_occurrences"}
            if mode == "debug" and entry["_occurrences"]:
                item["evidence"] = {"occurrences": entry["_occurrences"]}
            entries.append(item)
        return entries
