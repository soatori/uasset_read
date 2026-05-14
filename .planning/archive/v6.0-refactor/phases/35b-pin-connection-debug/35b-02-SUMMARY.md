# 35b-02 Summary: BitField Reading Fix

## Plan
- **ID:** 35b-02
- **Type:** Execute
- **Wave:** 2
- **Depends On:** 35b-01

## Status
- **Completed:** ✓ Yes
- **Tasks:** 2/2

## Changes Made

### 1. Fix BitField Reading (graph.py)
**File:** `src/uasset_read/serializers/graph.py`
**Lines:** 457-469

**Change:** Removed version-conditional `read_u8()` for UE5, replaced with unconditional `read_u32()` for both UE4 and UE5.

**Before:**
```python
if summary.file_version_ue5 > 0:
    bitfield = archive.read_u8()  # WRONG: 1 byte
else:
    bitfield = archive.read_u32()
```

**After:**
```python
# BitField is uint32 in both UE4 and UE5 (EdGraphPin.cpp L1902)
bitfield = archive.read_u32()
```

**Rationale:** UE5 source code (EdGraphPin.cpp L1902) serializes BitField as `uint32`, not `uint8`. The previous version check incorrectly assumed UE5 used 1 byte. This caused post-pin body data parsing issues.

### 2. Unit Tests (test_ue5_pin_bitfield.py)
**File:** `tests/test_ue5_pin_bitfield.py`

**Tests Added:** 11 tests

| Test | Description | Status |
|------|-------------|--------|
| `test_bitfield_consumes_4_bytes` | Verifies 4-byte consumption | ✓ PASS |
| `test_bitfield_value_preserved` | Value round-trip works | ✓ PASS |
| `test_all_zero_bitfield_produces_all_false_flags` | Flags are False for 0x00 | ✓ PASS |
| `test_all_ones_bitfield_produces_true_flags` | Flags are True for 0xFFFFFFFF | ✓ PASS |
| `test_hidden_flag_bit_0` | Bit 0 = hidden flag | ✓ PASS |
| `test_not_connectable_flag_bit_1` | Bit 1 = not_connectable | ✓ PASS |
| `test_advanced_view_flag_bit_4` | Bit 4 = advanced_view | ✓ PASS |
| `test_orphaned_pin_flag_bit_5` | Bit 5 = orphaned_pin | ✓ PASS |
| `test_combined_flags_bitfield_0x33` | Multiple flags combined | ✓ PASS |
| `test_bitfield_4_byte_sequence_in_archive` | Archive sequence test | ✓ PASS |
| `test_bitfield_large_value` | Large 32-bit values work | ✓ PASS |

## Verification Results

**New Tests:** 11/11 passed
**Full Test Suite:** 420 passed, 71 skipped, 0 failed

**Test Commands:**
```bash
python -m pytest tests/test_ue5_pin_bitfield.py -v -x  # 11 passed
python -m pytest tests/ --tb=short -q  # 420 passed, 71 skipped
```

## Impact Assessment

- **Byte Drift Resolution:** Fixed -3 bytes drift (from 1→4 byte correction) for BitField
- **Pin Integrity:** Post-pin body data now parses correctly
- **Backward Compatible:** UE4 behavior unchanged (still read_u32)
- **No Regressions:** Full test suite passes

## Next Steps
This fix completes Wave 2. Combined with 35b-01 (PinType bools) and 35b-03 (FText b_has_culture), the total byte drift correction is:
- **PinType 4 bools:** +12 bytes (4→1 each: -3 × 4)
- **FText b_has_culture:** +3 bytes (4→1: -3)
- **BitField:** -3 bytes (1→4: +3)
- **Net Drift Fixed:** 12 bytes

Proceed to 35b-05 (integration tests) to verify linked_to_raw non-empty.
