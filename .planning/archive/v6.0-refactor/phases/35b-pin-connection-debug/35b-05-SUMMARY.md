# 35b-05 Summary: Integration Tests & Phase 21 Unskip

## Plan
- **ID:** 35b-05
- **Type:** Execute
- **Wave:** 3
- **Depends On:** 35b-01, 35b-02, 35b-03

## Status
- **Completed:** Partial (Integration tests created, Phase 21 unskipped, but linked_to_raw still empty)
- **Tasks:** 2/3 (Integration tests created, Phase 21 unskipped, regression tests passed)

## Changes Made

### 1. Integration Tests Created
**File:** `tests/test_ue5_pin_integration.py`

**Tests Added:** 6 tests

| Test | Description | Status |
|------|-------------|--------|
| `test_asset_parses_successfully` | Parse success check | ✓ PASS |
| `test_eventgraph_has_nodes_with_pins` | Graph structure | ✓ PASS |
| `test_pins_have_linked_to_raw` | linked_to_raw non-empty | ✗ FAIL |
| `test_execution_flows_not_empty` | execution_flows populated | ✓ PASS |
| `test_data_flows_not_empty` | data_flows populated | ✗ FAIL |
| `test_connections_not_empty` | connections populated | ✗ FAIL |

### 2. Phase 21 Tests Unskipped
**File:** `tests/test_phase21_verification.py`

**Changes:** Removed 4 `@pytest.mark.skip` decorators

| Test | Description | Status |
|------|-------------|--------|
| `test_jump_started_flow` | IA_Jump → Jump flow | ✗ FAIL (no Jump node found) |
| `test_jump_completed_flow` | IA_Jump → StopJumping flow | ✗ FAIL (no StopJumping node found) |
| `test_actionvalue_x_to_right` | Move graph data flow | ✗ FAIL |
| `test_function_reference_member_name` | function_reference check | ✓ PASS |

### 3. Full Test Suite Regression
**Result:** 423 passed, 67 skipped, 7 failed

**Failures:** All related to linked_to_raw being empty, cascading to execution/data flows

## Root Cause Analysis (Updated)

After applying fixes from 35b-01, 35b-02, 35b-03:

### Fixed Issues:
1. ✓ **PinType 4 bools:** Now use read_bool_ue5() (1 byte each)
2. ✓ **BitField:** Now uses read_u32() (4 bytes)
3. ✓ **FText b_has_culture:** Uses read_bool_ue5() when ue5_mode=True
4. ✓ **FText custom types:** Skip 8 mystery bytes for history_type 131-191

### Remaining Issues:
**Direction/FName byte drift:** After PinToolTip, the raw bytes show:
```
00 00 00 00 ff 00 00 00 00 ff ff ff ff 00 00 00 00 94 00 00 00
```

Current code expects:
- Direction u8 (1 byte) → then FName (8 bytes)

But actual structure appears to have:
- 4 bytes before valid FName data
- The `ff` byte might be a special marker
- FName indices read as garbage (16711680 = 0x00FF0000)

**Hypothesis:** UE5 Direction might be serialized differently, or there's alignment/padding between Direction and PinType FName.

## Verification Results

**New Tests:** 6 integration tests created
**Full Test Suite:** 423 passed, 67 skipped, 7 failed

**Test Commands:**
```bash
python -m pytest tests/test_ue5_pin_integration.py -v -x  # 3 passed, 3 failed
python -m pytest tests/ --tb=short -q  # 423 passed, 67 skipped, 7 failed
```

## Impact Assessment

- **linked_to_raw:** Still empty across all pins (0 links in 20 pins)
- **execution_flows:** Present but flow chains incomplete
- **data_flows:** Empty in Move graph
- **connections:** Empty

## Next Steps

Further investigation needed for:
1. **Direction serialization format** in UE5 EdGraphPin
2. **FName alignment/padding** between Direction and PinCategory
3. **Complete pin body byte mapping** for UE5 version 1017

Recommendation: Create detailed binary trace of complete pin body with UE5 C++ source reference (EdGraphPin.cpp L1838-1964) to identify exact field boundaries.

## Test Evidence

Manual trace of pin body parsing:
```python
# Export 40, pin 0: "bIsParentComponentNative"
# FText header: flags=0x43B9261B, history_type=150
# FText mystery 8 bytes consumed ✓
# SourceIndex = 0 ✓
# PinToolTipLen = 0 ✓
# After these: Direction/PinType has drift
# Raw bytes: 00 00 00 00 ff 00 00 00 00 ff ff ff ff...
# PinCategory reads as garbage index 16711680
```

The FText fix advances parsing correctly to SourceIndex/ToolTipLen, but subsequent PinType fields are misaligned.