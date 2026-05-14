---
phase: 30-property-parsing
plan: 01
type: execute
wave: 1
tags: ["property-parsing", "dataclasses", "serializers", "mod-06", "mod-09"]
subsystem: models + serializers
completed_date: "2026-05-11T17:30:00Z"
duration_seconds: 180
files_created:
  - src/uasset_read/models/properties.py
  - src/uasset_read/serializers/property_tags.py
files_modified:
  - src/uasset_read/constants.py
  - src/uasset_read/models/__init__.py
  - src/uasset_read/__init__.py
decisions:
  - "No from_archive classmethods added to property dataclasses (pure data containers)"
  - "use_complete_type_name appended to constants.py, not extracted to separate module"
  - "read_property_tag exported from serializers.property_tags, not top-level __init__.py"

dependency_graph:
  requires: [Phase-29-data-models, Phase-27-constants, Phase-27-exceptions, Phase-28-archive]
  provides: [PropertyTag, PropertyValue, AdvancedPropertyValue, StructValue, MapValue, SetValue, EnumValue, TextValue, DelegateValue, read_property_tag, use_complete_type_name]
  affects: [parsers/property_parser (future), serializers/ (future)]

tech_stack:
  added: []
  patterns: ["dataclass containers", "TYPE_CHECKING for circular import prevention", "standalone serializer functions"]

key_files:
  created:
    - src/uasset_read/models/properties.py (9 dataclasses)
    - src/uasset_read/serializers/property_tags.py (read_property_tag)
  modified:
    - src/uasset_read/constants.py (use_complete_type_name appended)
    - src/uasset_read/models/__init__.py (+9 exports)
    - src/uasset_read/__init__.py (+9 exports)

metrics:
  tasks_completed: 4/4
  deviations: 0
  auth_gates: 0
---

# Phase 30 Plan 01: Property Dataclasses & PropertyTag Serializer Summary

等价迁移 uasset_read.py 第 1294-1427 行（属性 dataclass）和第 5186-5282 行（read_property_tag）。

One-liner: Created 9 property dataclasses (PropertyTag, PropertyValue + 6 AdvancedPropertyValue subclasses) and read_property_tag serializer with UE4/UE5 dual-format support.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create property dataclasses | `8f01994` | `src/uasset_read/models/properties.py` |
| 2 | Move use_complete_type_name to constants | `e1a49db` | `src/uasset_read/constants.py` |
| 3 | Create read_property_tag serializer | `b86892f` | `src/uasset_read/serializers/property_tags.py` |
| 4 | Update module exports | `9814e3b` | `src/uasset_read/models/__init__.py`, `src/uasset_read/__init__.py` |

## Key Decisions

1. **Pure datacontainers**: No `from_archive` classmethods on property dataclasses — serializers handle construction
2. **No top-level serializer export**: `read_property_tag` and `use_complete_type_name` stay in their respective modules, not exported at package level
3. **TYPE_CHECKING pattern**: Used consistently in both new files to prevent circular imports

## Verification

- `python -c "from uasset_read import PropertyTag, PropertyValue, StructValue, MapValue, SetValue, EnumValue, TextValue, DelegateValue; print('OK')"` — OK
- `python -c "from uasset_read.serializers.property_tags import read_property_tag; print('OK')"` — OK
- `python -c "from uasset_read.constants import use_complete_type_name; assert use_complete_type_name(-8, 1012) == True"` — OK
- `grep TYPE_CHECKING` confirms circular import prevention in both new files

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all dataclasses are complete data containers with no placeholder values.

## Threat Flags

None — dataclasses contain no execution logic; serializer uses existing validate_size() for DoS prevention (T-30-01 mitigated).

## Self-Check: PASSED

- [x] `src/uasset_read/models/properties.py` exists
- [x] `src/uasset_read/serializers/property_tags.py` exists
- [x] `src/uasset_read/constants.py` contains `use_complete_type_name`
- [x] All 4 commits present in git log
