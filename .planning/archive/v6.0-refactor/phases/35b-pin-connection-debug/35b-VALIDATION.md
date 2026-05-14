---
phase: 35b
type: validation
created: 2026-05-13
---

# Phase 35b: Validation Plan

## Automated Verification Commands

| Task | Plan | Wave | Command |
|------|------|------|---------|
| T1: read_bool_ue5() exists | 35b-01 | 1 | `python -c "from uasset_read.archive import FArchive; assert hasattr(FArchive, 'read_bool_ue5'); print('OK')"` |
| T2: PinType uses read_bool_ue5 | 35b-01 | 1 | `grep -c 'read_bool_ue5' src/uasset_read/serializers/graph.py` (expect >= 4) |
| T3: Bool serialization unit tests | 35b-01 | 1 | `python -m pytest tests/test_ue5_bool_serialization.py -v -x` |
| T1: BitField reads u32 | 35b-02 | 2 | `grep -n 'read_u8' src/uasset_read/serializers/graph.py \| grep -i bitfield` (expect 0 matches) |
| T2: BitField unit tests | 35b-02 | 2 | `python -m pytest tests/test_ue5_pin_bitfield.py -v -x` |
| T1: FText ue5_mode param | 35b-03 | 2 | `grep -n 'ue5_mode' src/uasset_read/serializers/graph.py` |
| T2: FText call site updated | 35b-03 | 2 | `grep -n 'read_ftext_with_history' src/uasset_read/serializers/graph.py` |
| T3: FText unit tests | 35b-03 | 2 | `python -m pytest tests/test_ue5_ftext_serialization.py -v -x` |
| T1: Binary trace tool CLI | 35b-04 | 1 | `python tools/binary_trace_pin.py --help` |
| T2: Binary trace tool run | 35b-04 | 1 | `python tools/binary_trace_pin.py --asset <path>` |
| T1: Integration tests | 35b-05 | 3 | `python -m pytest tests/test_ue5_pin_integration.py -v -x` |
| T2: Phase 21 unskip | 35b-05 | 3 | `python -m pytest tests/test_phase21_verification.py -v --tb=short` |
| T3: Full regression | 35b-05 | 3 | `python -m pytest tests/ --tb=short -x` |

## Sampling Plan

| Wave | Entry Gate | Exit Gate |
|------|------------|-----------|
| Wave 1 (35b-01, 35b-04) | All tests green on main | T1-T3 of 35b-01 pass; 35b-04 tool runs |
| Wave 2 (35b-02, 35b-03) | Wave 1 green | All unit tests pass |
| Wave 3 (35b-05) | Wave 2 green | Integration tests pass; full suite 397+ passed, 0 failed |

## Success Criteria Trace

| Criterion | Verifying Task |
|-----------|----------------|
| read_pin_array returns non-empty list | 35b-05 Task 1 |
| pin.linked_to_raw populated | 35b-05 Task 1 |
| execution_flows traces IA_Jump → Jump → StopJumping | 35b-05 Task 1 |
| data_flows contains ActionValue_X/Y connections | 35b-05 Task 1 |
| All existing tests pass (397+) | 35b-05 Task 3 |
| Phase 21 historical tests pass | 35b-05 Task 2 |
