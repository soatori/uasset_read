---
phase: "35d"
plan: 05
subsystem: graph
tags: [flow_builder, linked_to_raw, node_guid, visited-set, safety]
requires: []
affects: [src/uasset_read/graph/flow_builder.py]
tech-stack:
  added: []
  patterns:
    - "(pin.linked_to_raw or []) — safe iteration guard for None linked_to_raw"
    - "current_guid = current_node.node_guid; if current_guid is None: continue — None-guard for node_guid in visited set"
key-files:
  created: []
  modified:
    - src/uasset_read/graph/flow_builder.py
decisions:
  - "LOW-06: Use `(x or [])` pattern instead of `if x is not None` to handle both None and empty list uniformly"
  - "LOW-07: When node_guid is None, record warning and skip visited-set tracking rather than adding None to the set (which causes false cycle detection)"
metrics:
  duration: null
  completed_date: 2026-05-13
---

# Phase 35d Plan 05: flow_builder.py Safety Fixes Summary

**One-liner:** Add safe iteration guards for `linked_to_raw` (LOW-06) and None-check for `node_guid` (LOW-07) in visited set across `_find_next_exec_node`, `_trace_execution_from_event`, `_trace_execution_from_pin`, `build_connections_map`, and `build_data_flows`.

## Overview

Fixed two low-severity defensive coding issues in `flow_builder.py`:
- **LOW-06**: `linked_to_raw` could be `None` in malformed data, causing `TypeError` when iterating
- **LOW-07**: `node_guid` could be `None`, causing `None` to be added to the visited set, which would lead to false cycle detection across multiple nodes with missing GUIDs

## Tasks Executed

| # | Task | Type | Commit | Files Modified |
|---|------|------|--------|----------------|
| 1 | LOW-06: Safe iteration for linked_to_raw | auto | 0c89222 | src/uasset_read/graph/flow_builder.py (4 sites) |
| 2 | LOW-07: None-check for node_guid in visited | auto | 2570295 | src/uasset_read/graph/flow_builder.py (1 function) |

### Task 1: Safe iteration for `linked_to_raw` (LOW-06)

**Files modified:** `src/uasset_read/graph/flow_builder.py`

**Changes:**
- `_find_next_exec_node` (line 204): `for linked_pin_id in (pin.linked_to_raw or []):`
- `_trace_execution_from_pin` (line 284): `for linked_pin_id in (start_pin.linked_to_raw or []):`
- `build_connections_map` (line 326): `for linked_pin_ref in (pin.linked_to_raw or []):`
- `build_data_flows` (line 414): `for linked_pin_ref in (pin.linked_to_raw or []):`

**Pattern:** Uses `(pin.linked_to_raw or [])` which handles both `None` (falsy) and empty list (also falsy) uniformly, falling back to an empty iteration.

### Task 2: None-check for `node_guid` in visited set (LOW-07)

**Files modified:** `src/uasset_read/graph/flow_builder.py`

**Changes in `_trace_execution_from_event`:**
1. Extract `current_guid = current_node.node_guid` before visited check
2. If `current_guid is None`: record node with `"warning": "missing node_guid"` and continue tracing (skip visited tracking for this node)
3. Use `current_guid` consistently instead of repeated `current_node.node_guid` access

**Rationale:** Adding `None` to the visited set causes all nodes with missing GUIDs to be treated as the same node, triggering false cycle detection and terminating execution flow tracing prematurely.

## Test Results

- **398 passed, 67 skipped, 33 failed** (identical to baseline before changes)
- All 3 `test_ue5_pin_integration` failures (`test_pins_have_linked_to_raw`, `test_data_flows_not_empty`, `test_connections_not_empty`) are **pre-existing** — confirmed by running against original code at `b179794`
- No regressions introduced

## Verification

- All 4 `linked_to_raw` iteration sites now guarded with `or []`
- `_trace_execution_from_event` handles `node_guid is None` by recording warning and continuing
- `node_lookup` and `pin_lookup` dictionary keying with `node_guid` remains unchanged (out of scope for this plan — the deserialization layer should ensure GUIDs are never None)

## Deviations from Plan

None — plan executed exactly as described.

## Known Stubs

None.

## Threat Flags

None.

## Self-Check: PASSED

- [x] `src/uasset_read/graph/flow_builder.py` exists
- [x] Commit `0c89222` exists: `fix(35d-05): add safe iteration guards for linked_to_raw (LOW-06)`
- [x] Commit `2570295` exists: `fix(35d-05): add None-check for node_guid in visited set (LOW-07)`
- [x] Pre-existing test failures confirmed unchanged
