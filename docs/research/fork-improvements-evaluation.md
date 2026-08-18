# Fork Improvements Evaluation

Issue #559: Evaluate improvements from [nicky-jov/uasset_read](https://github.com/nicky-jov/uasset_read) fork for upstream adoption.

## Executive Summary

The fork (commit `08f3a9b1`) contains substantial improvements in three areas:
1. **Kismet Bytecode Handling** (High Value) — BPGC cooked bytecode extraction, expanded bytecode extractor
2. **Graph Processing** (High Value) — 6 new modules for edge traversal, execution trace, node formatting
3. **Link/Linker** (Medium Value) — World Partition path normalization

## Detailed Evaluation

### 1. Kismet Bytecode Handling

#### New: `kismet/bpgc_bytecode.py`
- **Purpose**: BPGC (BlueprintGeneratedClass) cooked bytecode extraction for UE5
- **Key Functions**:
  - `extract_bpgc_bytecode()` — Extract bytecode from BPGC's `script_serial_region`
  - `map_bytecode_to_functions()` — Map bytecode offsets to function exports
  - `_parse_cooked_bytecode_buffer()` — Parse cooked bytecode buffer

**Assessment**: HIGH VALUE
- Solves real problem: Function exports in cooked BPGC often contain no bytecode
- BPGC fallback is necessary for complete Blueprint parsing
- Recommendation: **Adopt with modifications**

#### Expanded: `kismet/bytecode_extractor.py`
- `extract_bytecode_bytes()` — Extracts raw ScriptBytecode from UStruct export
- `_scan_export_serial_for_bytecode()` — Recovery for cooked Function exports
- `_bpgc_fallback()` — BPGC fallback with module-level caching
- `extract_and_parse()` — Combined extraction + parsing entry point

**Assessment**: HIGH VALUE
- Recovery logic is valuable for edge cases
- Module-level caching may cause issues with multiple packages
- Recommendation: **Adopt with cache isolation**

### 2. Graph Processing

#### New Modules
| Module | Purpose | Value |
|--------|---------|-------|
| `graph/_edge_traversal.py` | Normalized edge iteration | High |
| `graph/_execution_trace.py` | Execution flow tracing | High |
| `graph/_node_format.py` | Node formatting | Medium |
| `graph/_pin_helpers.py` | Pin naming, GUID validation | High |
| `graph/_sanitize.py` | JSON safety (binary/null removal) | Medium |
| `graph/pin_trace.py` | Pin field-level diagnostics | Medium |

**Assessment**: HIGH VALUE
- Edge traversal and execution trace are critical for Blueprint analysis
- Pin helpers solve real problems with GUID validation
- Recommendation: **Adopt selectively** (edge_traversal, execution_trace, pin_helpers)

#### `graph/flow_builder.py` Refactoring
- Fork imports from new modules
- Adds `_choose_synthetic_source_pin()` — Infers readable source pin names
- Adds `_synthetic_parameter_edges()` — Supplements semantic data edges
- Uses index-based lookup (more efficient)

**Assessment**: MEDIUM VALUE
- Synthetic pin naming improves readability
- Index-based lookup is more efficient
- Recommendation: **Adopt performance improvements**

### 3. Link/Linker

#### `src/uasset_read/link/linker.py`
- `normalize_world_partition_path()` — Strips World Partition hash suffixes
  - Example: `/Script/Engine_3103784960` → `/Script/Engine`
- Uses `BoundedEventBuffer` for diagnostics

**Assessment**: MEDIUM VALUE
- World Partition normalization is useful for UE5 assets
- BoundedEventBuffer is good practice
- Recommendation: **Adopt**

## Implementation Priority

1. **Phase 1**: BPGC bytecode extraction (bpgc_bytecode.py)
2. **Phase 2**: Graph processing modules (edge_traversal, execution_trace, pin_helpers)
3. **Phase 3**: Linker improvements (normalize_world_partition_path)
4. **Phase 4**: Bytecode extractor enhancements

## Compatibility Notes

- Fork uses Chinese comments; upstream convention is English
- Some upstream modules are absent from fork (`kismet/cfg/`, `kismet/diagnostics.py`, etc.)
- Fork diverged earlier; careful integration required
- All changes must maintain zero runtime dependencies

## Validation Criteria

- [ ] All existing tests pass
- [ ] BPGC extraction works on UE5 samples
- [ ] Graph traversal produces correct results
- [ ] No performance regression
- [ ] Memory usage stays bounded
