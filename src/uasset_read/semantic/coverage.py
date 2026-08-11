"""Coverage model — tracks field-level parse coverage."""
from __future__ import annotations

from uasset_read.semantic.ir import CoverageInfo


class CoverageModel:
    """Tracks expected vs parsed fields and builds CoverageInfo."""

    def __init__(self) -> None:
        self._expected: int = 0
        self._parsed: int = 0
        self._unparsed: list[str] = []

    def track(
        self,
        fields_expected: int,
        fields_parsed: int,
        unparsed_fields: list[str],
    ) -> None:
        """Record field coverage for a domain section.

        Args:
            fields_expected: Total fields expected by the domain extractor
            fields_parsed: Fields successfully parsed
            unparsed_fields: Names of fields that were not parsed
        """
        self._expected += fields_expected
        self._parsed += fields_parsed
        self._unparsed.extend(unparsed_fields)

    def build(self) -> CoverageInfo:
        """Build the immutable CoverageInfo.

        Returns:
            CoverageInfo with computed coverage percentage
        """
        pct = (self._parsed / self._expected * 100.0) if self._expected > 0 else 0.0
        return CoverageInfo(
            fields_expected=self._expected,
            fields_parsed=self._parsed,
            coverage_pct=round(pct, 1),
            unparsed_fields=tuple(self._unparsed),
        )
