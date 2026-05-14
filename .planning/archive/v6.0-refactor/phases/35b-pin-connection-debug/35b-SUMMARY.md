# Phase 35b Summary: Pin Connection Deep Debug & Fix

## Phase Overview
- **Phase:** 35b
- **Duration:** 2026-05-13
- **Plans Executed:** 5/5 (35b-01 through 35b-05)
- **Status:** Partially Complete (linked_to_raw still empty)

## Execution Summary

### Wave 1 (Independent)
| Plan | Description | Status | Test Result |
|------|-------------|--------|-------------|
| 35b-01 | read_bool_ue5() + PinType bools | ✓ Complete | 6 tests passed |
| 35b-04 | Binary trace tool | ✓ Complete (tool created) | N/A (diagnostic) |

### Wave 2 (Depends on 35b-01)
| Plan | Description | Status | Test Result |
|------|-------------|--------|-------------|
| 35b-02 | BitField u32 fix | ✓ Complete | 11 tests passed |
| 35b-03 | FText b_has_culture fix | ✓ Complete | 6 tests passed |

### Wave 3 (Depends on Wave 1+2)
| Plan | Description | Status | Test Result |
|------|-------------|--------|-------------|
| 35b-05 | Integration tests | Partial | 3/6 tests passed |

## Key Changes Made

### 1. FArchive Extension (35b-01)
**File:** `src/uasset_read/archive.py`
- Added `read_bool_ue5()` method reading uint8 (1 byte) instead of uint32 (4 bytes)

### 2. PinType Bool Fix (35b-01)
**File:** `src/uasset_read/serializers/graph.py`
- Lines 115, 116, 128, 134: Conditional bool reading based on `file_version_ue5 > 0`
- Pattern: `read_bool_ue5() if ue5_mode else read_bool()`

### 3. BitField Fix (35b-02)
**File:** `src/uasset_read/serializers/graph.py`
- Line 463: Always reads `read_u32()` for BitField (UE4 and UE5)
- Removed incorrect version-conditional `read_u8()` for UE5

### 4. FText Fix (35b-03)
**File:** `src/uasset_read/serializers/graph.py`
- Lines 188-193: Added `ue5_mode` parameter to `read_ftext_with_history()`
- Line 215: Conditional `read_bool_ue5()` for b_has_culture in None type
- Lines 237-261: Handle custom history_type with 8-byte mystery data skip
- Line 352: Call site passes `ue5_mode=(summary.file_version_ue5 > 0)`

### 5. Binary Trace Tool (35b-04)
**File:** `tools/binary_trace_pin.py`
- CLI tool for field-level position verification
- Supports `--asset`, `--node-export-idx`, `--pin-index` arguments

## Test Results

### Unit Tests
| Category | Tests | Status |
|----------|-------|--------|
| Bool serialization | 6 | ✓ All passed |
| BitField reading | 11 | ✓ All passed |
| FText serialization | 6 | ✓ All passed |

### Integration Tests
| Test | Status | Reason |
|------|--------|--------|
| linked_to_raw non-empty | ✗ FAIL | linked_to_raw empty |
| execution_flows populated | ✓ PASS | Flows present (incomplete) |
| data_flows populated | ✗ FAIL | Empty in Move graph |
| connections populated | ✗ FAIL | Empty |

### Full Suite
- **Result:** 423 passed, 67 skipped, 7 failed
- **Failures:** Cascading from linked_to_raw empty

## Byte Drift Analysis

### Fixed Drift (Total: ~12 bytes)
| Field | Before Fix | After Fix | Bytes Corrected |
|-------|------------|-----------|-----------------|
| bIsReference | read_bool (4B) | read_bool_ue5 (1B) | -3 |
| bIsWeakPointer | read_bool (4B) | read_bool_ue5 (1B) | -3 |
| bIsConst | read_bool (4B) | read_bool_ue5 (1B) | -3 |
| bIsUObjectWrapper | read_bool (4B) | read_bool_ue5 (1B) | -3 |
| BitField | read_u8 (1B) | read_u32 (4B) | +3 |
| FText b_has_culture | read_bool (4B) | read_bool_ue5 (1B) | -3 |
| FText custom 8 bytes | Not consumed | Skip 8B | +8 |
| **Net Change** | — | — | **+8 bytes** |

### Remaining Drift (Approximately 4 bytes)
After applying all fixes, SourceIndex and PinToolTipLen read correctly, but PinType Direction/FName fields are misaligned:

- **Expected:** Direction u8 (1B) → PinCategory FName (8B)
- **Actual:** Direction reads 0 (valid), but PinCategory index = garbage (16711680 = 0x00FF0000)

Raw bytes after PinToolTipLen=0:
```
00 00 00 00 ff 00 00 00 00 ff ff ff ff 00 00 00 00 94 00 00 00
```

**Hypothesis:** UE5 may have 4 bytes of padding or a special marker byte (`ff`) between Direction and PinCategory FName.

## Commits

1. `b9839f2`: feat(35b-01): add read_bool_ue5() to FArchive
2. `7252a5e`: feat(35b-01): use read_bool_ue5() for UE5 FEdGraphPinType bools
3. `a110f9e`: test(35b-01): add UE5 bool serialization unit tests
4. `0e75f30`: docs(35b-01): complete UE5 bool serialization fix plan summary
5. `6363f82`: Merge 35b-01: UE5 bool serialization fix
6. `4302180`: feat(35b): partial UE5 pin serialization fixes (35b-02, 35b-03, 35b-05)

## Recommendations for Future Work

1. **UE5 C++ Source Reference:** Obtain EdGraphPin.cpp L1838-1964 exact field boundaries for version 1017
2. **Direction Field Format:** Investigate if Direction has padding or is serialized differently in UE5
3. **Complete Binary Trace:** Run full pin body trace with known-good anchor points
4. **Custom Version GUIDs:** Investigate mismatch between asset's 13 custom versions and project's 3 known GUIDs

## Phase Status

**Verification Status:** PARTIAL
- Unit tests pass (23/23)
- Integration tests partially pass (3/6)
- linked_to_raw still empty (root goal not achieved)

**Blocking Issue:** Additional byte drift in Direction/FName structure requires further investigation with UE5 source reference.