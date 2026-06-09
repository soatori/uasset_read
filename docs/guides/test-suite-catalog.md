# Test Suite Catalog

This report classifies the current test files against the project goal:

> Read UE `.uasset` / `.umap` without opening the editor, emit unified agent-readable output, and keep Blueprint text aligned with C++ semantics.

## Keep as core coverage

- `tests/test_core_api.py`
- `tests/test_renderers.py`
- `tests/test_ir_structures.py`
- `tests/test_truncated_file.py`
- `tests/test_version_compatibility.py`
- `tests/test_unknown_property_fallback.py`
- `tests/test_tolerant_early_parse_diagnostics.py`
- `tests/test_package_summary_fields.py`
- `tests/test_parse_package_core.py`
- `tests/test_blueprint_node_cleaner.py`
- `tests/test_function_resolver.py`
- `tests/test_function_resolver_enhanced.py`
- `tests/test_ir_builder.py`
- `tests/test_json_completeness.py`
- `tests/test_kismet_decompilation.py`
- `tests/test_kismet_deprecated_tokens.py`
- `tests/test_pak_handling.py`
- `tests/test_pak_structures.py`
- `tests/test_raw_readers.py`
- `tests/test_archive_diagnostic.py`
- `tests/test_array_count_check.py`
- `tests/test_binary_or_native_handlers.py`
- `tests/test_class_registry.py`
- `tests/test_export_error_context.py`
- `tests/test_linker_offset_check.py`
- `tests/test_property_parser_error_handling.py`
- `tests/test_variable_extractor.py`
- `tests/test_sample_assets_representative.py`
- `tests/test_tolerant_class_specific.py`
- `tests/test_compat_check.py`
- `tests/test_cpp_quality_gate.py`
- `tests/test_constructor_metadata.py`
- `tests/test_event_execution_fix.py`
- `tests/test_real_asset_e2e.py`
- `tests/test_acceptance.py` — 最终验收测试（5 个维度，89 个用例）

## Keep, but treat as auxiliary

These tests are useful, but they do not directly prove the main user-facing contract.

- `tests/test_api_cleanup.py`
- `tests/test_quality_stats.py`
- `tests/test_cue4parse_gap_completion.py`
- `tests/test_diagnostic_output.py`
- `tests/test_fallback_models.py`
- `tests/test_pin_recovery.py`
- `tests/test_jump_analyzer.py`

## Review before deletion

These files are the first candidates if you want to prune history-only or duplicate coverage.

- `tests/test_api_cleanup.py`
- `tests/test_quality_stats.py`
- `tests/test_cue4parse_gap_completion.py`

## Notes

- I ran the full suite before this report: `1226 passed, 2 skipped, 2 xfailed`.
- I also added `scripts/test_matrix.py` to standardize local and CI execution.
- No tests were deleted in this step. The next safe move is to review the "Review before deletion" set against current product scope and remove only what no longer exercises a supported path.
