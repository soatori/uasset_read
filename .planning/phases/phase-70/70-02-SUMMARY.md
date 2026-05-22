---
phase: 70-n2cstruct-schema
plan: 02
subsystem: N2C Serializer & Flow Extractor
tags: [serializer, flow-extractor, n2c, json, roundtrip]
dependency_graph:
  requires: [70-01]
  provides: [SCHEMA-02]
  affects: [n2c/serializer.py, n2c/flow_extractor.py, n2c/__init__.py, __init__.py]
tech_stack:
  added: [N2CStruct serialization, N2CStruct deserialization, flow chain extraction]
  patterns: [dataclass roundtrip, DFS cycle detection, token estimation]
key_files:
  created:
    - src/uasset_read/n2c/serializer.py
    - src/uasset_read/n2c/flow_extractor.py
    - src/uasset_read/n2c/compat.py
    - tests/n2c/test_roundtrip.py
    - tests/n2c/test_flow_extractor.py
    - tests/n2c/test_token_reduction.py
  modified:
    - src/uasset_read/n2c/__init__.py
    - src/uasset_read/__init__.py
decisions:
  - "Idempotent registry initialization in to_n2c_json() to avoid duplicate registration errors"
  - "Cycle detection fallback to pair format with _format marker for downstream consumers"
  - "Knot node exclusion handled in both serializer (skip registration) and flow_extractor (skip processing)"
metrics:
  duration: ~30min
  completed_date: "2026-05-22"
  tests_added: 33
  tests_total_n2c: 142
---

# Phase 70 Plan 02: N2C Serializer and Flow Extractor Summary

**One-liner:** Implemented bidirectional N2CStruct JSON serialization (`to_n2c_json` / `from_n2c_json`) with roundtrip consistency, plus execution flow chain extraction with cycle detection fallback and Knot node penetration.

## Tasks Completed

| # | Task | Type | Commit | Key Files |
|---|------|------|--------|-----------|
| 1 | to_n2c_json() implementation | auto+tdd | 8609fac | serializer.py, test_roundtrip.py |
| 2 | from_n2c_json() implementation | auto+tdd | 8609fac | serializer.py, test_roundtrip.py |
| 3 | flow_extractor implementation | auto+tdd | 8609fac | flow_extractor.py, test_flow_extractor.py |
| 4 | Token reduction test + exports | auto | 8734800 | test_token_reduction.py, __init__.py |

## Verification Results

- **33 plan-specific tests:** All passing
- **142 total n2c tests:** All passing
- **951 overall tests:** All passing (excluding 2 pre-existing failures)
- **Roundtrip consistency:** `from_n2c_json(to_n2c_json(graphs=[g])).to_dict() == to_n2c_json(graphs=[g])` verified
- **Token reduction:** N2C format achieves >= 40% token savings over existing format
- **Top-level imports:** `from uasset_read import to_n2c_json, from_n2c_json, N2CStruct, N2CNode, N2CPin, N2CIdMapper, N2CGraph` works

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

- `N2CStruct.structs` and `N2CStruct.enums` are empty lists (placeholder for future plans)
- `latent` field on N2CNode is not populated (requires latent action analysis, not in scope)

## Threat Flags

None introduced. All threat model mitigations (T-70-03 to T-70-05) are implemented:
- `from_n2c_json()` validates required top-level fields (version, metadata, graphs)
- `extract_chains()` uses MAX_CHAIN_DEPTH=1000 for DFS cycle detection
- No external package installs
