# Test Suite Consolidation Inventory

## Current Snapshot

- Current test file count: 249 at plan execution.
- Target test file count: <= 100.
- Target core benchmark/acceptance entry files: <= 10.
- Worktree: `.worktrees/test-consolidation` on branch `test/consolidation`.

## Coverage Domains

| Domain | Must Preserve | Target Files |
| --- | --- | --- |
| Archive and binary IO | read/seek/skip/name, FString/FName, diagnostics, tolerant recovery, validated counts, error recovery, export error context | tests/archive/test_*.py |
| Serialization | package summary, property tags, class registry/strategy, native/binary handlers, property parser error handling | tests/serialization/test_*.py |
| Parsers and mappings | USMap, property parser bounds/recovery, asset registry, mappings, top-level path, error diagnostics | tests/parsers/test_*.py |
| Package containers | Pak, IoStore, provider, raw readers, security/resource limits | tests/asset/test_*.py |
| Blueprint and graph | metadata, pins, variables, node cleaner, subgraphs, execution flow | tests/blueprint/test_*.py and tests/graph/test_*.py |
| Kismet | bytecode, CFG, resolver, translator, decompile output, semantic calls | tests/kismet/test_*.py |
| Renderers and output | JSON, Markdown, C++, output levels, status model, renderer consistency | tests/renderers/test_*.py |
| Core API and CLI | parse API, logging/session ownership, batch, cache, status, utility contracts, error handling | tests/core/test_*.py |
| Unit tests | opaque handlers, animation models, struct parsing, miscellaneous | tests/unit/test_*.py |
| Real assets and acceptance | BP_FirstPersonCharacter, StackOBot, representative samples, JSON/Markdown acceptance | tests/integration/test_*.py |
| Quality gates | imports, code quality, memory/resource safety, entry points, exception context, silent exception detection | tests/quality/test_*.py (or root) |

## File-by-File Mapping

### tests/archive/ (15 files → target 7-9)

| Source File | Tests | Markers | Target | Action |
|---|---|---|---|---|
| test_archive_coverage.py | 78 | - | test_binary_archive.py | Merge |
| test_array_count_check.py | 15 | - | test_validated_counts.py | Merge |
| test_diagnostics.py | 45 | - | test_diagnostics.py | Keep |
| test_error_recovery.py | 7 | - | test_error_recovery.py | Keep (distinct concern) |
| test_export_error_context.py | 12 | - | test_export_error_context.py | Keep (distinct concern) |
| test_fallback.py | 17 | - | test_fallback.py | Keep |
| test_fname_index_recovery.py | 4 | - | test_binary_archive.py | Merge |
| test_fstring_all_null.py | 12 | - | test_fstring_fname.py | Merge |
| test_fstring_corruption.py | 6 | - | test_fstring_fname.py | Merge |
| test_fstring_utf16.py | 15 | - | test_fstring_fname.py | Merge |
| test_tolerant_parsing.py | 16 | parametrize | test_tolerant_parsing.py | Keep |
| test_truncated_file.py | 14 | - | test_binary_archive.py | Merge |
| test_ue4_legacy.py | 11 | - | test_ue4_legacy.py | Keep |
| test_utf_string.py | 14 | - | test_fstring_fname.py | Merge |
| test_version_compatibility.py | 3 | parametrize | test_version_compatibility.py | Keep |

### tests/core/ (37 files → target 8-10)

| Source File | Tests | Markers | Target | Action |
|---|---|---|---|---|
| test_api_cleanup.py | 13 | auxiliary | test_api_and_cli.py | Merge |
| test_archive_provider_renderer.py | 15 | - | test_api_and_cli.py | Merge |
| test_archive_read_name.py | 18 | - | test_read_name.py | Merge |
| test_archive_skip.py | 4 | - | test_api_and_cli.py | Merge |
| test_batch_hybrid.py | 8 | - | test_logging_and_batch.py | Merge |
| test_batch_worker.py | 6 | skipif | test_logging_and_batch.py | Merge |
| test_cli_logging_args.py | 4 | - | test_logging.py | Merge |
| test_cli_logging_ownership.py | 7 | - | test_logging.py | Merge |
| test_core_api.py | 16 | - | test_api_and_cli.py | Merge |
| test_depends_map.py | 6 | - | test_depends_map.py | Keep |
| test_error_handling.py | 2 | - | test_error_handling.py | Merge v1+v2 |
| test_error_handling_v2.py | 25 | parametrize | test_error_handling.py | Merge v1+v2 |
| test_eventgraph.py | 4 | - | test_api_and_cli.py | Merge |
| test_fstring_corruption.py | 4 | - | test_fstring.py | Merge |
| test_fstring_limit.py | 11 | - | test_fstring.py | Merge |
| test_ftext_args.py | 2 | - | test_ftext.py | Merge |
| test_ftext_safety.py | 1 | - | test_ftext.py | Merge |
| test_graph_node.py | 5 | - | test_api_and_cli.py | Merge |
| test_locres_and_integration.py | 10 | - | test_api_and_cli.py | Merge |
| test_logging_config.py | 2 | - | test_logging.py | Merge |
| test_logging_ownership.py | 7 | parametrize | test_logging.py | Merge |
| test_package_archive_read.py | 4 | - | test_api_and_cli.py | Merge |
| test_package_bundle.py | 5 | - | test_api_and_cli.py | Merge |
| test_package_cache.py | 3 | - | test_api_and_cli.py | Merge |
| test_parse_package_core.py | 4 | - | test_api_and_cli.py | Merge |
| test_preload.py | 3 | - | test_api_and_cli.py | Merge |
| test_project_logging.py | 8 | - | test_logging.py | Merge |
| test_project_logging_session.py | 10 | - | test_logging.py | Merge |
| test_property_parser_cache.py | 3 | - | test_api_and_cli.py | Merge |
| test_read_name.py | 10 | - | test_read_name.py | Merge |
| test_serialization_control.py | 5 | - | test_api_and_cli.py | Merge |
| test_status_model.py | 52 | - | test_status_and_models.py | Merge |
| test_status_validation.py | 4 | - | test_status_and_models.py | Merge |
| test_struct_property.py | 8 | - | test_api_and_cli.py | Merge |
| test_subgraphs.py | 2 | - | test_api_and_cli.py | Merge |
| test_logging_config.py | 2 | - | test_logging.py | Merge |
| test_utf8_length.py | 7 | - | test_api_and_cli.py | Merge |

### tests/integration/ (12 files → target 7)

| Source File | Tests | Markers | Target | Action |
|---|---|---|---|---|
| test_acceptance.py | 11 | - | test_acceptance.py | Keep |
| test_anim_blueprint_integration.py | 3 | integration | test_animation_assets.py | Merge |
| test_anim_montage_integration.py | 3 | integration | test_animation_assets.py | Merge |
| test_anim_sequence_integration.py | 2 | integration | test_animation_assets.py | Merge |
| test_bp_firstpersoncharacter_validation.py | 10 | - | test_bp_firstpersoncharacter.py | Merge |
| test_cue4parse_gap_completion.py | 25 | - | test_ue_fidelity.py | Merge |
| test_real_asset_e2e.py | 10 | - | test_real_assets.py | Merge |
| test_sample_assets.py | 8 | - | test_real_assets.py | Merge |
| test_sample_assets_representative.py | 5 | - | test_real_assets.py | Merge |
| test_status_model_integration.py | 4 | - | test_ue_fidelity.py | Merge |
| test_ue_fidelity_integration.py | 8 | - | test_ue_fidelity.py | Merge |
| test_ue_mcp_blueprint_comparison.py | 2 | - | test_bp_firstpersoncharacter.py | Merge |

### Other directories (consolidation straightforward)

| Directory | Files | Target | Action |
|---|---|---|---|
| tests/serialization/ | 12 | 6-8 | Merge overlapping |
| tests/parsers/ | 14 | 6-8 | Merge overlapping |
| tests/kismet/ | 17 | 8-10 | Merge overlapping |
| tests/graph/ | 11 | 5-7 | Merge overlapping |
| tests/blueprint/ | 7 | 5-7 | Minor merges |
| tests/renderers/ + tests/renderer/ | 3 | 4-6 | Merge dirs |
| tests/unit/ | 13 | 5-8 | Merge small files |
| tests/linker/ + tests/link/ | 9 | 5-7 | Merge dirs |
| tests/structs/ | 5 | 2-3 | Merge |
| tests/misc/ | 4 | 2-3 | Merge |
| tests/pak/ | 4 | 2-3 | Merge |
| tests/iostore/ | 3 | 1-2 | Merge |
| tests/cpp/ + tests/cpp_gen/ | 7 | 4-5 | Merge dirs |
| tests/batch/ | 2 | 0 | Move to core |
| tests/config/ | 1 | 0 | Move to core |
| Root test_*.py files | 4 | 0 | Move to quality |
