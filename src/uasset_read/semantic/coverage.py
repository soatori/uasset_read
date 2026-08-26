"""Honest coverage model — reports actual semantic loss, not key counts."""

from __future__ import annotations

from uasset_read.semantic.models import CoverageInfo


class CoverageModel:
    """Tracks domain scopes and builds CoverageInfo."""

    def __init__(self) -> None:
        self._expected: int = 0
        self._available: int = 0
        self._unavailable: list[str] = []

    def track(self, scope: str, available: bool) -> None:
        self._expected += 1
        if available:
            self._available += 1
        else:
            self._unavailable.append(scope)

    def build(self, notes: str = "") -> CoverageInfo:
        return CoverageInfo(
            scopes_expected=self._expected,
            scopes_available=self._available,
            scopes_unavailable=tuple(self._unavailable),
            notes=notes,
        )
