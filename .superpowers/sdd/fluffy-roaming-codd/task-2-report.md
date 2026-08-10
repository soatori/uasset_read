# Task 2 Report: Move 22 temp tests to proper subdirectories

## Status: DONE

## Summary

All 22 test files were moved from `tests/temp/` to their appropriate subdirectories using `git mv`. No import changes were needed -- all imports reference `uasset_read` or standard library modules, with zero cross-references to `tests.temp`.

## Files Moved

### tests/core/ (15 files)
- test_batch_worker_logging.py
- test_batch_worker_timeouts.py
- test_corrupted_recovery.py
- test_dead_code_contract.py
- test_export_diagnostic_provenance.py
- test_json_diagnostic_aggregation.py
- test_json_export_accounting.py
- test_json_output_levels.py
- test_json_schema_contract.py
- test_resolved_references.py
- test_schema_consistency.py
- test_serial_size_clamp.py
- test_source_encoding.py
- test_status_propagation.py
- test_warning_types.py

### tests/kismet/ (6 files)
- test_decompiled_function_provenance.py
- test_issue_77_kismet_archive.py
- test_issue_77_pipeline_contract.py
- test_issue_77_real_samples.py
- test_issue_77_ufunction_reader.py
- test_issue_77_virtual_function_fname.py

### tests/iostore/ (1 file)
- test_iostore_encrypted_reads.py

## Import Changes

None required. All 22 test files import only from `uasset_read.*` and standard library modules. No file references `tests.temp` in its imports.

## Test Collection Results

- `python -m pytest --collect-only -q` collected **433 tests** total
- Promoted directories (tests/core/, tests/kismet/, tests/iostore/) contribute **386 tests**
- All tests collected without errors

## Additional Actions

- Removed the now-empty `tests/temp/` directory
- Target directories (tests/core/, tests/kismet/, tests/iostore/) were created as empty directories (no `__init__.py` -- pytest discovers tests via directory traversal, not Python packages)

## Notes

- The plan listed 17 files for tests/core/ but only 15 exist; the total across all destinations is still 22 (15 + 6 + 1)
- Changes are staged and ready to commit
