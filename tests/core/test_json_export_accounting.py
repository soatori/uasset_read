"""Regression coverage for JSON export accounting after tolerant IR skips."""

# ---------------------------------------------------------------------------
# All tests in this module have been removed. They depended on
# JSONRenderer._build_data(), which no longer exists.
#
# The old JSONRenderer maintained internal statistics (total_exports,
# exports_parsed, exports_built, exports_rendered, exports_omitted,
# omitted_by_reason) that were not part of the semantic pipeline contract.
#
# The semantic pipeline builds SemanticIR directly from PackageIR and does
# not track per-export render/omit accounting.
#
# - test_json_statistics_account_for_skipped_ir_exports_and_all_diagnostics
# - test_json_statistics_keep_loss_accounting_when_header_understates_exports
# - test_json_statistics_account_for_tolerant_export_table_read_failures
# ---------------------------------------------------------------------------
