# 35b-03 Summary: FText b_has_culture Fix

## Plan
- **ID:** 35b-03
- **Type:** Execute
- **Wave:** 2
- **Depends On:** 35b-01

## Status
- **Completed:** ✓ Yes
- **Tasks:** 3/3

## Changes Made

### 1. Add `ue5_mode` Parameter to `read_ftext_with_history()`
**File:** `src/uasset_read/serializers/graph.py`
**Lines:** 188-193

**Change:** Added `ue5_mode: bool = False` parameter to function signature.

**Before:**
```python
def read_ftext_with_history(
    archive: FArchive,
    history_type: int,
    tolerant: bool = True,
) -> tuple[str, int]:
```

**After:**
```python
def read_ftext_with_history(
    archive: FArchive,
    history_type: int,
    tolerant: bool = True,
    ue5_mode: bool = False,
) -> tuple[str, int]:
```

### 2. Conditional bool Reading for `b_has_culture`
**File:** `src/uasset_read/serializers/graph.py`
**Line:** 215

**Change:** Use `read_bool_ue5()` (1 byte) when `ue5_mode=True`, otherwise `read_bool()` (4 bytes).

**Before:**
```python
b_has_culture = archive.read_bool()  # Always 4 bytes
```

**After:**
```python
b_has_culture = archive.read_bool_ue5() if ue5_mode else archive.read_bool()
```

### 3. Update Call Site to Pass `ue5_mode`
**File:** `src/uasset_read/serializers/graph.py`
**Line:** 352

**Change:** Pass `ue5_mode=(summary.file_version_ue5 > 0)` from `read_ue_graph_pin()`.

**Before:**
```python
read_ftext_with_history(archive, history_type, tolerant=True)
```

**After:**
```python
read_ftext_with_history(archive, history_type, tolerant=True, ue5_mode=(summary.file_version_ue5 > 0))
```

### 4. Unit Tests (test_ue5_ftext_serialization.py)
**File:** `tests/test_ue5_ftext_serialization.py`

**Tests Added:** 6 tests

| Test | Description | Status |
|------|-------------|--------|
| `test_ftext_none_ue5_mode_consumes_one_byte_for_bool` | UE5 mode = 1 byte | ✓ PASS |
| `test_ftext_none_ue4_mode_consumes_four_bytes_for_bool` | UE4 mode = 4 bytes | ✓ PASS |
| `test_ftext_none_total_consumption_ue5` | Total = 6 bytes (4+1+1) | ✓ PASS |
| `test_ftext_none_total_consumption_ue4` | Total = 9 bytes (4+1+4) | ✓ PASS |
| `test_ftext_base_unaffected_by_ue5_mode` | history_type=0 unchanged | ✓ PASS |
| `test_ftext_custom_unaffected_by_ue5_mode` | history_type=1-254 unchanged | ✓ PASS |

## Verification Results

**New Tests:** 6/6 passed
**Full Test Suite:** 420 passed, 71 skipped, 0 failed

**Test Commands:**
```bash
python -m pytest tests/test_ue5_ftext_serialization.py -v -x  # 6 passed
python -m pytest tests/ --tb=short -q  # 420 passed, 71 skipped
```

## Impact Assessment

- **Byte Drift Resolution:** Fixed -3 bytes drift for FText b_has_culture (4→1 byte)
- **history_type=0xFF Only:** Affects only `None` type FText; Base/Custom types unchanged
- **Backward Compatible:** UE4 behavior preserved via default `ue5_mode=False`
- **UE5 Detection:** Uses `summary.file_version_ue5 > 0` from package header
- **No Regressions:** Full test suite passes

## Total Drift Corrected (Summary)

| Component | Bytes Drift Fixed |
|-----------|-------------------|
| PinType 4 bools | +12 bytes |
| FText b_has_culture | +3 bytes |
| BitField | -3 bytes |
| **Total Net Drift** | **+12 bytes** |

The LinkedTo array should now be read at the correct position, yielding non-empty `linked_to_raw` entries for connected pins.

## Next Steps
Proceed to 35b-05: Integration tests to verify `linked_to_raw` is non-empty, execution flows work, and data flows are populated.
