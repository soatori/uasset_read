---
status: complete
phase: 28-core-serialization
source: [src/uasset_read/archive.py, src/uasset_read/serializers/package_summary.py, src/uasset_read/serializers/object_resources.py, .planning/STATE.md]
started: "2026-05-10T12:00:00Z"
updated: "2026-05-10T12:05:00Z"
---

## Current Test

[testing complete]

## Tests

### 1. FArchive Module Import and Binary Reading
expected: `from uasset_read.archive import FArchive` imports without error. FArchive can open a .uasset file, read basic types (u8/u16/u32/i32/i64/f32/f64), and read_fstring returns valid strings.
result: pass

### 2. PackageFileSummary Header Parsing
expected: `from uasset_read.serializers.package_summary import read_package_summary, PackageFileSummary` imports without error. Parsing a .uasset file returns a PackageFileSummary with correct tag, version fields, name_count, export_count, import_count.
result: pass

### 3. Name Table Reading
expected: `from uasset_read.serializers.package_summary import read_name_table` imports without error. Given a valid archive and summary, read_name_table returns a non-empty list of strings matching the UE name map.
result: pass

### 4. ImportMap Parsing
expected: `from uasset_read.serializers.object_resources import read_import_map, ObjectImport` imports without error. Given a valid archive, summary, and name_map, read_import_map returns a list of ObjectImport with correct class_package, class_name, object_name fields.
result: pass

### 5. ExportMap Parsing
expected: `from uasset_read.serializers.object_resources import read_export_map, ObjectExport` imports without error. Given a valid archive, summary, and name_map, read_export_map returns a list of ObjectExport with correct serial_size, serial_offset, object_flags, and PackageIndex fields.
result: pass

### 6. PackageIndex Encoding and Validation
expected: `from uasset_read.serializers.object_resources import PackageIndex, validate_package_index` imports without error. PackageIndex correctly identifies is_import/is_export/is_null, to_import_index/to_export_index conversions work, validate_package_index returns None for valid indices and error string for out-of-range.
result: pass

### 7. Blueprint Detection Helpers
expected: `from uasset_read.serializers import detect_blueprint, detect_blueprint_generated_class, resolve_class_name, get_asset_class` imports work. detect_blueprint correctly identifies Blueprint exports, resolve_class_name resolves PackageIndex to class names.
result: pass

### 8. Module __init__ Exports
expected: `from uasset_read.serializers import PackageFileSummary, PackageIndex, ObjectImport, ObjectExport, read_package_summary, read_name_table, read_import_map, read_export_map` all import without error. __all__ lists all 17 exported symbols.
result: pass

### 9. End-to-End Serialization Pipeline
expected: Running a full parse chain (archive -> read_package_summary -> read_name_table -> read_import_map -> read_export_map) on a real .uasset file completes without exceptions and returns non-empty results for all tables.
result: pass

## Summary

total: 9
passed: 9
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none]
