---
phase: 05-optimization-security
plan: 02B
type: execute
wave: 2
depends_on: ["05-02"]
files_modified: ["uasset_read.py"]
autonomous: true
requirements: ["SAFE-01", "SAFE-02"]
user_setup: []
must_haves:
  truths:
    - "read_package_summary() validates NameOffset, ImportOffset, ExportOffset"
    - "read_property_tag() validates PropertyTag.Size"
    - "All existing tests pass after validation integration"
  artifacts:
    - path: "uasset_read.py"
      provides: "Integrated boundary validation"
      contains: "validate_offset() calls in read_package_summary(), validate_size() in read_property_tag()"
  key_links:
    - from: "read_package_summary()"
      to: "FArchive.validate_offset()"
      via: "D-10: 表偏移验证"
      pattern: "archive.validate_offset(name_offset, 'NameOffset')"
---

# Phase 5 Plan 02B: 边界验证集成

## Objective

Integrate boundary validation methods into existing parsing functions per D-10, D-11.

## Tasks

<task type="auto">
  <name>Integrate validate_offset() into read_package_summary()</name>
  <files>uasset_read.py</files>
  <read_first>uasset_read.py:read_package_summary() lines 478-698</read_first>
  <action>
Add archive.validate_offset() after reading table offsets:

1. After name_offset: archive.validate_offset(name_offset, "NameOffset")
2. After import_offset: archive.validate_offset(import_offset, "ImportOffset")
3. After export_offset: archive.validate_offset(export_offset, "ExportOffset")
  </action>
  <verify>
    <automated>python -c "from uasset_read import parse_uasset; r = parse_uasset('LyraStarterGame/Content/Characters/Heroes/Abilities/AbilitySets/AS_Hero_Default.uasset'); assert r.is_success"</automated>
  </verify>
  <done>
    - read_package_summary() validates all table offsets
    - Valid files parse successfully
  </done>
</task>

<task type="auto">
  <name>Integrate validate_size() into read_property_tag()</name>
  <files>uasset_read.py</files>
  <read_first>uasset_read.py:read_property_tag() lines 1274-1333</read_first>
  <action>
Add archive.validate_size() after reading size in both UE5 and UE4 branches:

UE5 format: archive.validate_size(tag.size, tag.name)
UE4 format: archive.validate_size(tag.size, tag.name)
  </action>
  <verify>
    <automated>python -m pytest tests/ -v -k "property" --tb=short -x</automated>
  </verify>
  <done>
    - read_property_tag() validates Size
    - All property tests pass
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <what-built>Boundary validation integrated into parsing functions</what-built>
  <how-to-verify>
    1. Parse Lyra file: python -c "from uasset_read import parse_uasset; r = parse_uasset('LyraStarterGame/Content/Characters/Heroes/Abilities/AbilitySets/AS_Hero_Default.uasset'); print(r.is_success)"
    2. Run tests: python -m pytest tests/ -v --tb=short -x
  </how-to-verify>
  <resume-signal>Type "approved" to proceed to Wave 3</resume-signal>
</task>

## Success Criteria

- SAFE-01, SAFE-02 fully implemented
- All existing tests pass
- Validation prevents crashes on invalid files
