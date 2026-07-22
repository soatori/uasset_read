"""Structured report summary for parse results."""
from dataclasses import dataclass, field
from collections import Counter


@dataclass
class ReportSummary:
    """Structured summary of parsing results."""

    total: int = 0
    success: int = 0
    partial: int = 0
    failed: int = 0

    # Detailed breakdown
    partial_reasons: dict[str, int] = field(default_factory=dict)
    error_types: Counter = field(default_factory=Counter)

    # Statistics
    total_exports: int = 0
    total_warnings: int = 0
    avg_exports_per_file: float = 0.0

    # Common issues
    most_common_error: str = ""
    most_common_partial_reason: str = ""

    @classmethod
    def from_results(cls, results: list[dict]) -> 'ReportSummary':
        """Create summary from list of parse results."""
        summary = cls()
        summary.total = len(results)

        for result in results:
            status = result.get('status', 'unknown')
            if status == 'success':
                summary.success += 1
            elif status == 'partial':
                summary.partial += 1
                reason = result.get('parse_status', 'unknown')
                summary.partial_reasons[reason] = summary.partial_reasons.get(reason, 0) + 1
            elif status == 'failed':
                summary.failed += 1
                error = result.get('error', 'unknown')
                summary.error_types[error] += 1

            summary.total_exports += result.get('exports', 0)
            summary.total_warnings += result.get('warnings', 0)

        if summary.total > 0:
            summary.avg_exports_per_file = summary.total_exports / summary.total

        if summary.error_types:
            summary.most_common_error = summary.error_types.most_common(1)[0][0]
        if summary.partial_reasons:
            summary.most_common_partial_reason = max(
                summary.partial_reasons.items(), key=lambda x: x[1]
            )[0]

        return summary

    def to_text(self) -> str:
        """Generate human-readable text summary."""
        lines = [
            "=== Parse Summary ===",
            f"Total files: {self.total}",
            f"Success: {self.success} ({self.success*100//max(self.total,1)}%)",
            f"Partial: {self.partial} ({self.partial*100//max(self.total,1)}%)",
            f"Failed: {self.failed} ({self.failed*100//max(self.total,1)}%)",
            "",
            "Statistics:",
            f"  Total exports: {self.total_exports}",
            f"  Avg exports per file: {self.avg_exports_per_file:.1f}",
            f"  Total warnings: {self.total_warnings}",
        ]

        if self.partial_reasons:
            lines.append("")
            lines.append("Partial reasons:")
            for reason, count in sorted(self.partial_reasons.items(), key=lambda x: -x[1]):
                lines.append(f"  {reason}: {count}")

        if self.error_types:
            lines.append("")
            lines.append("Error types:")
            for error, count in self.error_types.most_common(5):
                lines.append(f"  {error}: {count}")

        return "\n".join(lines)
