---
phase: "35e"
plan: "02"
subsystem: "serializers"
tags: ["fix", "pin-offset", "FText", "uobject-wrapper"]
key-files:
  created: []
  modified:
    - "src/uasset_read/serializers/graph.py"
    - "src/uasset_read/constants.py"
  verified: []
metrics:
  task_count: 3
  tasks_passed: 3
  total_commits: 1
  duration_minutes: 5
---

# Plan 35e-02: DefaultTextValue FText + bIsUObjectWrapper Fallback

## Commits

| # | Commit | Description |
|---|--------|-------------|
| 1 | (current) | feat(35e-02): fix DefaultTextValue as FText and bIsUObjectWrapper fallback |

## Tasks

| # | Name | Status | Notes |
|---|------|--------|-------|
| 1 | FUE5ReleaseStreamObjectVersion GUID in constants.py | ✅ | Added GUID and threshold (SerializeFloatPinDefaultValuesAsSinglePrecision=36) |
| 2 | bIsUObjectWrapper fallback in read_ed_graph_pin_type() | ✅ | Added `or summary.file_version_ue5 > 0` fallback for UE5 assets |
| 3 | DefaultTextValue FString→FText in read_ue_graph_pin() | ✅ | Replaced `_read_ftext_fstring()` with full FText read (flags + history_type + body via read_ftext_with_history) |

## Key Changes

### src/uasset_read/constants.py
- Added `FUE5RELEASESTREAM_OBJECT_VERSION_GUID = "D89B5E42-24BD4D46-8412ACA8-DF641779"`
- Added `FUE5RELEASESTREAM_VERSION_SERIALIZE_FLOAT_PIN_DEFAULTS_AS_SINGLE_PRECISION = 36`

### src/uasset_read/serializers/graph.py
- **Import**: Added `FUE5RELEASESTREAM_OBJECT_VERSION_GUID` and `FUE5RELEASESTREAM_VERSION_SERIALIZE_FLOAT_PIN_DEFAULTS_AS_SINGLE_PRECISION`
- **bIsUObjectWrapper (D1)**: Changed condition from `release_version >= FRELEASE_VERSION_PIN_TYPE_UOBJECT_WRAPPER` to `release_version >= FRELEASE_VERSION_PIN_TYPE_UOBJECT_WRAPPER or summary.file_version_ue5 > 0` to handle UE5 assets where GUID is missing from the custom version table
- **DefaultTextValue (D3)**: Replaced simplified FString read with full FText deserialization: read_i32 (flags) + read_u8 (history_type) + read_ftext_with_history (body)

## Deviations
- None

## Verification
- Syntax: ✅ constants.py + graph.py
- Module import: ✅ (read_ue_graph_pin, read_ed_graph_pin_type)
- Parse test: ✅ (BP_FirstPersonCharacter.uasset parses with 4 graphs, no crash)

## Self-Check: PASSED
- D1 (+1 byte): bIsUObjectWrapper fallback implemented ✅
- D3 (+2~13 bytes): DefaultTextValue als FText ✅
- linked_to_raw still expected empty until Plan 03 (D2 fix) ✅
