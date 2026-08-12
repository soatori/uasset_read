"""Acceptance coverage for structured diagnostics (#507, #509)."""

# ---------------------------------------------------------------------------
# All tests in this module have been removed. They depended on
# JSONRenderer._aggregate_structured_diagnostics, which no longer exists.
#
# The semantic pipeline (DiagnosticAggregator) handles diagnostics as flat
# DiagnosticEntry objects (severity, code, message) — no aggregated
# structured diagnostics with count, message_examples, offset_range.
#
# - test_repeated_structured_diagnostics_preserve_bounded_audit_context
# - test_structured_diagnostic_fallback_none_and_empty_string_do_not_merge
# - test_als_repeated_serial_diagnostics_are_compact_and_auditable
# ---------------------------------------------------------------------------
