---
phase: 35d-logic-fixes
verified: 2026-05-13T12:30:00Z
status: passed
score: 16/16 must-haves verified
overrides_applied: 0
gaps: []
---

# Phase 35d: 代码审查逻辑与质量修复 — Verification Report

**Phase Goal:** 修复全量代码审查发现的属性解析 bug、蓝图提取 bug、输出格式问题
**Success Criteria:** 属性解析正确性修复 + 蓝图变量提取修复 + JSON/Markdown 输出修复 + 全部测试通过
**Verified:** 2026-05-13T12:30:00Z
**Status:** passed
**Re-verification:** No (initial verification)

## Goal Achievement

All must-haves verified against actual codebase state. Phase goal fully achieved.

### Observable Truths

| #   | Truth   | Status     | Evidence     |
| --- | ------- | ---------- | ------------ |
| 1   | ArrayProperty remaining_size = tag.size - 4 (subtract 4-byte count field) | VERIFIED | `property_types.py:116` — `remaining_size = tag.size - 4` |
| 2   | MapProperty type extraction uses split(",", 1) (first-comma-only) | VERIFIED | `property_types.py:329` — `parts = params.split(",", 1)` |
| 3   | MAX_ARRAY_COUNT = 1_000_000 validation guard present | VERIFIED | `constants.py:33` — `MAX_ARRAY_COUNT = 1_000_000`; `property_types.py:110-113` — `if count < 0 or count > MAX_ARRAY_COUNT` |
| 4   | is_replicated maps to CPF_Replicated (0x00100000) | VERIFIED | `variable_extractor.py:61` — `"is_replicated": bool(flags & CPF_Replicated)`; line 535 — `var.is_replicated = bool(flags & CPF_Replicated)` |
| 5   | BlueprintVariable has no duplicate meta_data field | VERIFIED | `blueprint.py:128` — only `metadata: Dict[str, str]`, no `meta_data` field exists on BlueprintVariable |
| 6   | getattr guard for prop.type access | VERIFIED | `variable_extractor.py:149` — `getattr(prop, 'type', None)` |
| 7   | StructValue/MapValue/SetValue/EnumValue/TextValue/DelegateValue have default property_type | VERIFIED | `properties.py:52,61,69,77,86,94` — each subclass has `property_type: str = "XXXProperty"` |
| 8   | MapValue entries recursively serialized in JSON | VERIFIED | `json_formatter.py:159-170` — `serialize_property_value(entry.get("key"), depth + 1, max_depth)` |
| 9   | SetValue elements recursively serialized in JSON | VERIFIED | `json_formatter.py:171-175` — `serialize_property_value(elem, depth + 1, max_depth)` |
| 10  | Markdown table cells escape `|` and newlines | VERIFIED | `markdown_formatter.py:18-20` — `_escape_md_cell()` defined; 8 call sites wrapping table cell values |
| 11  | Transform parser uses fields.get() with 0.0 defaults | VERIFIED | `transform_parser.py:19-21,28-30,37-39` — `fields.get("X", 0.0)` pattern throughout |
| 12  | flow_builder.py safe linked_to_raw iteration | VERIFIED | `flow_builder.py:204,295,337,425` — `(pin.linked_to_raw or [])` pattern at all 4 iteration sites |
| 13  | flow_builder.py node_guid None guard before visited check | VERIFIED | `flow_builder.py:233-241` — `if current_guid is None: ... continue` bypassing visited set |
| 14  | UE5_PROPERTY_TAG_COMPLETE_TYPE_NAME is alias (no duplicate literal) | VERIFIED | `constants.py:87` — `UE5_PROPERTY_TAG_COMPLETE_TYPE_NAME = PROPERTY_TAG_COMPLETE_TYPE_NAME` |
| 15  | No unreachable return None in property_parser.py | VERIFIED | `property_parser.py:97` — no `return None`, file ends after final `elif` |
| 16  | No duplicate _derive_node_name in property_types.py | VERIFIED | `property_types.py` — zero matches for `_derive_node_name`; `__init__.py:247` — import removed from property_types line |

**Score:** 16/16 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `src/uasset_read/parsers/property_types.py` | remaining_size fix, comma split fix, MAX_ARRAY_COUNT | VERIFIED | Lines 116, 329, 110-113; no duplicate `_derive_node_name` |
| `src/uasset_read/constants.py` | MAX_ARRAY_COUNT, alias constant | VERIFIED | Line 33, 87 |
| `src/uasset_read/blueprint/variable_extractor.py` | is_replicated fix, getattr guard | VERIFIED | Lines 61, 149 |
| `src/uasset_read/models/blueprint.py` | Removed meta_data field | VERIFIED | Line 128 — only `metadata` |
| `src/uasset_read/models/properties.py` | Default property_type on subclasses | VERIFIED | Lines 52, 61, 69, 77, 86, 94 |
| `src/uasset_read/formatters/json_formatter.py` | Recursive MapValue/SetValue serialization, meta_data output | VERIFIED | Lines 159-175; line 375 `"meta_data": variable.metadata` |
| `src/uasset_read/formatters/markdown_formatter.py` | _escape_md_cell function | VERIFIED | Lines 18-20 + 8 call sites |
| `src/uasset_read/blueprint/transform_parser.py` | fields.get() pattern | VERIFIED | Lines 19-21, 28-30, 37-39 |
| `src/uasset_read/graph/flow_builder.py` | Safe linked_to_raw iteration, node_guid guard | VERIFIED | Lines 204/295/337/425; lines 233-241 |
| `src/uasset_read/parsers/property_parser.py` | Dead code removed | VERIFIED | No unreachable `return None` |
| `src/uasset_read/__init__.py` | Updated import chain | VERIFIED | Line 247 — no `_derive_node_name` from property_types |
| `tests/test_phase35d_variable_extractor_fixes.py` | 7 tests | VERIFIED | 7/7 passed |
| `tests/test_phase35d_model_class_fixes.py` | 17 tests | VERIFIED | 17/17 passed |
| `tests/test_phase35d_formatter_transform_fixes.py` | 10 tests | VERIFIED | 10/10 passed |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `property_types.py` | `constants.py` | import `MAX_ARRAY_COUNT` | WIRED | Line 21 import, line 110 usage |
| `variable_extractor.py` | `constants.py` | import `CPF_Replicated` | WIRED | Line 27 import, line 61 usage |
| `json_formatter.py` | `variable.metadata` | direct field access | WIRED | Line 375 — `"meta_data": variable.metadata` |
| `transform_parser.py` | `fields.get()` | dict access | WIRED | All sites use `.get()` with defaults |
| `markdown_formatter.py` | `_escape_md_cell()` | function call | WIRED | 8 call sites wrapping table values |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `json_formatter.py` `serialize_property_value` | MapValue.entries / SetValue.elements | Recursive call into `value.entries`/`value.elements` | Yes — containers carry real parsed data | FLOWING |
| `json_formatter.py` BlueprintVariable output | `variable.metadata` | `BlueprintVariable.metadata` dataclass field | Yes — populated from prop.value dict or read_blueprint_variable | FLOWING |
| `transform_parser.py` | `struct_value.fields` | `StructValue.fields` dict | Yes — populated from parsed StructProperty data | FLOWING |
| `markdown_formatter.py` | `result.summary.package_name` | ParseResult from parse_uasset() | Yes — real parsed asset data | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| New 35d tests pass | `pytest test_phase35d_variable_extractor_fixes.py test_phase35d_model_class_fixes.py test_phase35d_formatter_transform_fixes.py -v` | 34 passed | PASS |
| No regression in full suite | `pytest tests/ -q --tb=no` | 456 passed, 67 skipped, 9 failed (all pre-existing) | PASS |
| _derive_node_name removed from property_types | `grep _derive_node_name src/uasset_read/parsers/property_types.py` | No matches | PASS |
| Unreachable return None removed | `tail -5 src/uasset_read/parsers/property_parser.py` | No trailing `return None` | PASS |
| CPF_Replicated used for is_replicated | `grep -n "is_replicated.*CPF_Replicated" src/uasset_read/blueprint/variable_extractor.py` | Line 61 match | PASS |
| fields.get() pattern in transform_parser | `grep -c "fields\.get(" src/uasset_read/blueprint/transform_parser.py` | 9 matches | PASS |
| _escape_md_cell calls in markdown | `grep -c "_escape_md_cell" src/uasset_read/formatters/markdown_formatter.py` | 9 (1 def + 8 calls) | PASS |

### Requirements Coverage

No requirements IDs explicitly mapped to Phase 35d in REQUIREMENTS.md. Phase 35d is a code-review cleanup phase addressing CR/MED/HIGH items, which are review-specific identifiers rather than formal requirement IDs.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `variable_extractor.py` | 56 | `CPF_Edit` used for `is_edit_anywhere` (should be `CPF_EditAnywhere`) | Warning | Known CR-01 — out of scope for 35d, not scheduled |
| `variable_extractor.py` | 72, 414 | `_flags_to_labels` and `parse_property_flags_to_labels` use `CPF_Edit` as EditAnywhere surrogate | Warning | Known CR-02 — out of scope for 35d, not scheduled |
| `variable_extractor.py` | 383 | `or` chain discards PackageIndex 0 | Warning | Known CR-03 — out of scope for 35d, not scheduled |

The anti-patterns above are pre-existing issues identified in the Phase 35d Review Report that were not in scope for this phase's plans. They are documented here for awareness but do not affect the 35d goal status.

### Gaps Summary

No gaps found. All 16 must-haves are VERIFIED against actual codebase state.

### Pre-existing Test Failures (Not Introduced by 35d)

The 9 failing tests are all pre-existing Phase 21 / Phase 35b / asset-dependent failures confirmed by commit `b179794` baseline:
- `test_phase21_verification.py` — 4 failures (execution flow, data flow, node properties)
- `test_uasset_read.py` — 2 failures (import_map condition fields, saved hash)
- `test_ue5_pin_integration.py` — 3 failures (linked_to_raw, data_flows, connections)

---

_Verified: 2026-05-13T12:30:00Z_
_Verifier: Claude (gsd-verifier)_
