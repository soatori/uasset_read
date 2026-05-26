---
phase: 72g
plan: 01
generated: 2026-05-23
---

# Phase 72-G Validation Criteria

## Nyquist Sampling Requirements

### 8a: Automated Verify Presence

| Task | Has automated verify | Test file | Latency target |
|------|---------------------|-----------|----------------|
| Wave 1 | Yes | test_phase72g_connections.py | <60s |
| Wave 2 | Yes | test_phase72g_struct_parsing.py | <60s |
| Wave 3 | Yes | test_phase72g_functions.py | <60s |
| Wave 4 | Yes | test_phase72g_parameters.py | <60s |

**All 4 tasks have automated pytest commands in `<verify><automated>` sections.**

### 8b: Feedback Latency

| Verification type | Command | Expected latency |
|------------------|---------|-----------------|
| Unit test (single file) | `python -m pytest tests/test_phase72g_connections.py -xvs --tb=short` | <30s |
| Regression test | `python -m pytest tests/test_property_parsing.py -x --tb=short` | <60s |
| Full phase test | `python -m pytest tests/ -k "phase72g" --tb=short` | <120s |

**Latency targets met: single-file tests <60s, regression <120s.**

### 8c: Sampling Continuity

| Wave | Test file | Sample count | Coverage |
|------|-----------|--------------|----------|
| Wave 1 | test_phase72g_connections.py | 3 tests | LinkedTo validation |
| Wave 2 | test_phase72g_struct_parsing.py | 4 tests | Vector/Rotator parsing |
| Wave 3 | test_phase72g_functions.py | 3 tests | BPGC extraction |
| Wave 4 | test_phase72g_parameters.py | 3 tests | Parameter extraction |

**Total: 13 new tests. Sampling continuous across all waves.**

### 8d: Wave 0 Completeness

Wave 0 (setup) tasks:
- No Wave 0 setup required — phase directly executes Wave 1-4

**Wave 0 not applicable — phase starts with Wave 1 (LinkedTo validation).**

---

## Test Coverage Matrix

| Requirement | Test | Automated command |
|-------------|------|------------------|
| LinkedTo validation logging | test_linked_to_validation_logs_error | pytest -xvs test_phase72g_connections.py |
| Connections non-empty warning | test_connections_warning_on_empty_linked_to | pytest -xvs test_phase72g_connections.py |
| Vector fast-path | test_vector_fast_path | pytest -xvs test_phase72g_struct_parsing.py |
| Rotator fast-path | test_rotator_fast_path | pytest -xvs test_phase72g_struct_parsing.py |
| BPGC UbergraphFunction | test_bpgc_ubergraph_function_extraction | pytest -xvs test_phase72g_functions.py |
| BPGC FunctionList | test_bpgc_function_list_extraction | pytest -xvs test_phase72g_functions.py |
| Parameter extraction | test_parameter_name_and_type_extracted | pytest -xvs test_phase72g_parameters.py |

---

## Regression Prevention

| Risk area | Existing test suite | Regression check |
|-----------|--------------------|--------------------|
| Property parsing | tests/test_property_parsing.py | Wave 2 verify includes regression |
| Blueprint extraction | tests/test_blueprint_extraction.py | Wave 4 verify includes regression |
| Kismet BPGC | tests/test_kismet_bpgc.py | Full suite run after all waves |

---

## Success Gate

Before phase can be marked complete:

1. All 4 waves pass their automated tests
2. Regression tests pass (no new failures)
3. Sample asset (BP_FirstPersonCharacter.uasset) verification:
   - `connections` array length > 0
   - `Blueprint.functions` contains "Move", "Aim"
   - `RelativeLocation.X/Y/Z` populated
4. No regressions in existing test suite