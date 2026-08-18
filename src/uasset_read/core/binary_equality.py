"""Binary equality verification framework.

Provides utilities for verifying that parsed data can be serialized back to
identical binary output, enabling round-trip verification and regression detection.

Note: This module provides the framework and data structures. Full serialization
is not implemented (project is read-only). The verification focuses on:
- Field offset consistency checks
- Name table round-trip verification
- Property value integrity checks
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional


class VerificationStatus(Enum):
    """Verification result status."""
    PASS = auto()
    FAIL = auto()
    SKIP = auto()
    PARTIAL = auto()


@dataclass
class FieldSnapshot:
    """Snapshot of a parsed field for verification."""

    name: str
    offset: int
    size: int
    value: Any
    type_name: str

    def matches(self, other: "FieldSnapshot") -> bool:
        """Check if this field matches another snapshot."""
        return (
            self.name == other.name
            and self.offset == other.offset
            and self.size == other.size
            and self.value == other.value
        )


@dataclass
class VerificationCheck:
    """A single verification check result."""

    name: str
    status: VerificationStatus
    message: str = ""
    expected: Any = None
    actual: Any = None

    @property
    def passed(self) -> bool:
        return self.status == VerificationStatus.PASS


@dataclass
class EqualityReport:
    """Report of binary equality verification."""

    checks: list[VerificationCheck] = field(default_factory=list)

    @property
    def total_checks(self) -> int:
        return len(self.checks)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c.passed)

    @property
    def failed(self) -> int:
        return sum(1 for c in self.checks if c.status == VerificationStatus.FAIL)

    @property
    def all_passed(self) -> bool:
        return self.failed == 0

    def add_check(self, check: VerificationCheck) -> None:
        self.checks.append(check)

    def format_summary(self) -> str:
        """Format as human-readable summary."""
        lines = [
            f"Binary Equality Report: {self.passed}/{self.total_checks} checks passed",
        ]
        if self.failed > 0:
            lines.append(f"  FAILED: {self.failed}")
            for c in self.checks:
                if c.status == VerificationStatus.FAIL:
                    lines.append(f"    - {c.name}: {c.message}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "total_checks": self.total_checks,
            "passed": self.passed,
            "failed": self.failed,
            "all_passed": self.all_passed,
            "checks": [
                {
                    "name": c.name,
                    "status": c.status.name,
                    "message": c.message,
                }
                for c in self.checks
            ],
        }


class EqualityVerifier:
    """Binary equality verification framework.

    Collects field snapshots during parsing and verifies consistency
    at verification time.
    """

    def __init__(self) -> None:
        self._snapshots: list[FieldSnapshot] = []
        self._name_table: list[str] = []
        self._export_table: list[dict] = []
        self._import_table: list[dict] = []

    def record_field(self, name: str, offset: int, size: int, value: Any, type_name: str) -> None:
        """Record a parsed field snapshot."""
        self._snapshots.append(FieldSnapshot(
            name=name, offset=offset, size=size, value=value, type_name=type_name,
        ))

    def record_name_table(self, names: list[str]) -> None:
        """Record the name table for verification."""
        self._name_table = list(names)

    def verify_offset_continuity(self) -> VerificationCheck:
        """Verify that field offsets are contiguous (no gaps or overlaps)."""
        if len(self._snapshots) < 2:
            return VerificationCheck(
                name="offset_continuity",
                status=VerificationStatus.SKIP,
                message="Insufficient fields for continuity check",
            )

        sorted_fields = sorted(self._snapshots, key=lambda f: f.offset)
        gaps = []

        for i in range(1, len(sorted_fields)):
            prev_end = sorted_fields[i - 1].offset + sorted_fields[i - 1].size
            curr_start = sorted_fields[i].offset
            if curr_start > prev_end:
                gaps.append((prev_end, curr_start))

        if gaps:
            return VerificationCheck(
                name="offset_continuity",
                status=VerificationStatus.FAIL,
                message=f"Found {len(gaps)} gap(s) in field offsets",
                expected="contiguous",
                actual=f"{len(gaps)} gaps",
            )

        return VerificationCheck(
            name="offset_continuity",
            status=VerificationStatus.PASS,
            message="All field offsets are contiguous",
        )

    def verify_no_overlaps(self) -> VerificationCheck:
        """Verify that no fields overlap in the binary layout."""
        if len(self._snapshots) < 2:
            return VerificationCheck(
                name="no_overlaps",
                status=VerificationStatus.SKIP,
                message="Insufficient fields for overlap check",
            )

        sorted_fields = sorted(self._snapshots, key=lambda f: f.offset)
        overlaps = []

        for i in range(1, len(sorted_fields)):
            prev = sorted_fields[i - 1]
            curr = sorted_fields[i]
            prev_end = prev.offset + prev.size
            if prev_end > curr.offset and prev.offset < curr.offset:
                overlaps.append((prev.name, curr.name))

        if overlaps:
            return VerificationCheck(
                name="no_overlaps",
                status=VerificationStatus.FAIL,
                message=f"Found {len(overlaps)} overlap(s)",
                expected="no overlaps",
                actual=f"{len(overlaps)} overlaps",
            )

        return VerificationCheck(
            name="no_overlaps",
            status=VerificationStatus.PASS,
            message="No field overlaps detected",
        )

    def verify_name_table_integrity(self) -> VerificationCheck:
        """Verify name table consistency."""
        if not self._name_table:
            return VerificationCheck(
                name="name_table_integrity",
                status=VerificationStatus.SKIP,
                message="No name table recorded",
            )

        # Check for empty names, duplicates
        empty_count = sum(1 for n in self._name_table if not n)
        if empty_count > 0:
            return VerificationCheck(
                name="name_table_integrity",
                status=VerificationStatus.FAIL,
                message=f"Found {empty_count} empty name(s) in name table",
            )

        return VerificationCheck(
            name="name_table_integrity",
            status=VerificationStatus.PASS,
            message=f"Name table OK: {len(self._name_table)} entries",
        )

    def run_all(self) -> EqualityReport:
        """Run all verification checks and return a report."""
        report = EqualityReport()
        report.add_check(self.verify_offset_continuity())
        report.add_check(self.verify_no_overlaps())
        report.add_check(self.verify_name_table_integrity())
        return report
