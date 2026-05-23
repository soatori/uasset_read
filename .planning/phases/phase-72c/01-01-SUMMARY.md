---
phase: phase-72c
plan: 01
wave: 1
type: execute
status: completed
depends_on: []
files_created:
  - src/uasset_read/kismet/bpgc_bytecode.py
files_modified: []
---

## Wave 1 Summary: BPGC Bytecode Extraction Module

### Task 1: Create `bpgc_bytecode.py` module

**Created:** `src/uasset_read/kismet/bpgc_bytecode.py` (295 lines)

**Exports:**
- `extract_bpgc_bytecode()` — Reads BPGC `script_serial_region`, skips PropertyTags, parses cooked bytecode format into per-function buffers indexed by ordinal position.
- `map_bytecode_to_functions()` — Maps bytecode buffers to Function exports by ordinal pairing (UE cooked format convention).
- `_parse_cooked_bytecode_buffer()` — Pure logic function for buffer splitting (no archive dependency).

**Design decisions:**
- FArchive stream parsing STRICT: all binary reads use `archive.read_u8()`, `archive.read_bytes()`, etc. No raw byte reads.
- Cooked format parsing: u32 size prefix per function buffer, buffers end with `EX_EndOfScript` (0x53) or cooked variant (0xDD).
- Tolerant sentinel validation: warns on non-standard endings but still accepts buffers.
- Ordinal-based pairing: buffer N maps to Function export N in export table order.
- No modifications to existing `bytecode_extractor.py` (that is Plan 03's scope).

**Imports used:**
- `FArchive` methods (seek, tell, read_u8, read_bytes)
- `detect_blueprint_generated_class`, `resolve_class_name` from `object_resources`
- `read_property_tag` from `property_tags`
- `UE5_PROPERTY_TAG_EXTENSION` from constants
- `EExprToken` from kismet/tokens
- `ParseError` from exceptions

**Verification:**
- `python -c "from uasset_read.kismet.bpgc_bytecode import extract_bpgc_bytecode, map_bytecode_to_functions; print('OK')"` — PASS
- Module: 295 lines (minimum 80 required)

### Task 2: Unit test for cooked bytecode parsing logic

**Added:** `_parse_cooked_bytecode_buffer()` pure logic function + `__main__` inline test.

**Inline tests cover:**
- Synthetic 2-function cooked bytecode buffer — asserts 2 buffers, each ending with 0x53
- Single buffer with trailing garbage — stops after first buffer
- Empty input — returns empty list
- Plan verification command data — single buffer ending with 0x53

**Verification:**
- `python -c "from uasset_read.kismet.bpgc_bytecode import _parse_cooked_bytecode_buffer; bufs = _parse_cooked_bytecode_buffer(b'\\x04\\x00\\x00\\x00\\x01\\x02\\x03\\x53'); assert len(bufs) == 1; assert bufs[0].endswith(b'\\x53'); print('OK')"` — PASS
- `python src/uasset_read/kismet/bpgc_bytecode.py` (inline tests) — PASS

### Threat Model Mitigation

| Threat | Status |
|--------|--------|
| T-72C-01 (Tampering: script_serial_region) | Mitigated — validates size against remaining region bounds |
| T-72C-02 (EoP: function name mapping) | Mitigated — ordinal-based pairing only, no trust in function names |

### Success Criteria

1. `bpgc_bytecode.py` exists with `extract_bpgc_bytecode` and `map_bytecode_to_functions` — DONE
2. `_parse_cooked_bytecode_buffer` handles synthetic buffers correctly — DONE
3. Function signature uses FArchive stream parsing (no raw byte reads) — DONE
4. Module is importable from `uasset_read.kismet.bpgc_bytecode` — DONE
