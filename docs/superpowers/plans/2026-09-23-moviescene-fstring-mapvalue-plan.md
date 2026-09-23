# MovieScene MapValue FString Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the Lyra MovieScene `fstring_out_of_range` / false `fstring_all_null` cascade at its root — unknown size-0 map-value structs must parse as a bounded, validated tagged fallback instead of consuming zero bytes and desynchronizing the map loop — and correct `read_fstring()` all-null classification and `fstring_out_of_range` reason labeling.

**Architecture:** Two independent single-site fixes in `archive.py` (all-null classification gate; OOR reason tag) plus one fix in `parse_struct_property` (property_types.py): for unknown structs with `tag.size <= 0` (the dummy tags `_dispatch_value_parse` builds for MapProperty values), replace the immediate opaque return with the existing None-terminated tagged loop, then **accept only a clean None stop with zero new diagnostics**, otherwise rewind cursor and diagnostics to the entry start (opaque fallback, byte-identical to today). This makes `FMovieSceneExpansionState` values parse as `bExpanded` fields while native-binary struct values (e.g. export:7 `BindingIdToReferences`) keep their current bounded/opaque behavior. The poison-stop (`_PROPERTY_STREAM_POISON_CODES`) is untouched.

**Tech Stack:** Python 3.10+, pytest, stdlib only (`struct`, `ByteArchive` bounded-bytes reader tests, real fixture `tests/samples/Lyra_SEQ_LobbyScreen_LevelSequence.uasset` with manifest SHA-256).

**Spec:** `docs/designs/2026-08-26-package-first-uasset-parser-refactor.md` (Property System → Tagged / 公共值模型: both readers converge on the same `PropertyValue` tree — struct and map values are part of the common value model; unknown data stays opaque + diagnostic).

## Global Constraints

- Python 3.10+, cross-platform, standard library only, minimal diff, no new abstraction layers.
- Read-only parser: unknown data is preserved as an opaque region + structured diagnostic; never silently skipped and never claimed complete.
- Bounded binary reads: validate ranges/counts before consuming untrusted data; the tagged fallback is bounded by `MAX_PROPERTY_COUNT` plus a local `_MAX_TAGGED_FALLBACK_BYTES = 4096` cap inside `parse_struct_property` (`property_types.py:927`) and the None sentinel.
- Property split: tagged and unversioned readers stay separate; both emit the common value model (`PropertyValue`/`StructValue`/`MapValue`).
- Diagnostics over logs: structured diagnostics only; no process-global logging.
- Tests: bounded bytes for reader tests, real fixture + manifest for support claims; no `MagicMock` for UE binary structures; no `skip`/`xfail`; no wall-clock benchmarks.
- UE source reference required for layout decisions; named peers only (`Corroborated (not proof): <Peer> <symbol>`). Peer coverage for `FMovieSceneExpansionState`: **No peer parser decodes this type**.
- Temp/investigation scripts under `temp/` (untracked).
- Commit format: `<type>: <summary>` (issue number optional); English for code, comments, error messages.
- Do not change generic FString length rules; do not skip the MovieScene object; do not describe deferred gaps as implemented.

---

## Verified Root Cause (read before implementing)

Lyra sample `tests/samples/Lyra_SEQ_LobbyScreen_LevelSequence.uasset` (ue4=522, ue5=1004 < 1012 → **legacy property tag path**):

- `export:9` (MovieScene_0) window `[30212, 38460)`. `EditorData` tag starts at 35072, size 3233, struct name `MovieSceneEditorData`; its value starts at 35121 with the `ExpansionStates` MapProperty tag (key `StrProperty`, value `StructProperty`, size 3052; name indices 67/97/163/164 confirmed against the name table).
- The legacy tag binary stores **only** key/value type FNames for MapProperty — no value-struct name exists to read (`property_tags.py:331-334`, citing PropertyTag.cpp:357-371). So `tag.value_type_struct` is legitimately `None` here; the full-type-name path (`property_tags.py:140-147` → `property_types.py:1383-1386`) already propagates it correctly when present.
- The actual defect: `_dispatch_value_parse` builds a dummy `StructProperty` tag with `size=0` and `struct_type="Unknown"`; `parse_struct_property` at **property_types.py:882-888** returns opaque **consuming 0 bytes** for unknown non-fallback structs with `size<=0`. The map loop then re-reads the struct payload as the next entry's key:
  - cursor 35269 = start of the `bExpanded` inner tag (FName index 16 = `bExpanded`); read as FString length 16 → payload `00 00 00 00 1d 00 00 ...` (1d = name index 29 = `BoolProperty`) → `read_fstring` hits the "leading NUL" branch (archive.py:407-412 — the `first_null_idx == 0` path is the implicit else of the internal-NUL check) and emits false `fstring_all_null` at archive.py:449-457 (prior finding said ~404 — that is the section comment).
  - cursor 35293 → i32 = 7667713 → `fstring_out_of_range` (archive.py:350-366, emitted **without** `reason`) → poison (`property_parser.py:40-45`) → stream stops → `export:9` partial, `EditorData` projected as opaque `parse_error`.
- Naive blanket fix (let every unknown size-0 struct run the tagged loop) **regresses export:7**: `BindingIdToReferences` map struct keys/values are native binary (not tagged); the loop reads garbage FNames → 6 `name_index_out_of_range` + `export:7` flips to partial. Verified by runtime simulation. Therefore the loop must be **validated**: accept only a clean None-sentinel stop with zero new structured diagnostics; otherwise rewind cursor and diagnostics (byte-identical to current behavior).
- After the validated fix (simulated): `export:9` → `complete`, `ExpansionStates` = 31 entries with `bExpanded` parsed (27 True / 4 False), `EditorData` fields `ExpansionStates/ViewStart/ViewEnd/WorkStart/WorkEnd`, top-level gains `NodeGroupCollection` + `Signature`, zero `fstring_*` diagnostics, export:9 trailing-bytes diagnostic gone; `export:7` back to clean/complete with diagnostics rolled back.
- Existing hardening expectation `tests/test_parse_hardening.py:27` `assert movie.status.parse == "partial"` must upgrade to `"complete"` (the poison-stop mechanism itself stays covered by `tests/test_core.py:252` `property_loop_aborts_on_fstring_out_of_range`).

---

### Task 1: FString all-null classification in `read_fstring()`

**Files:**
- Modify: `src/uasset_read/archive.py:433-457` (UTF-8 "leading NUL" branch inside `read_fstring`, currently lines 322-480)
- Test: `tests/test_core.py` (append new module-level functions near the existing fstring tests around line 2053)

**Interfaces:**
- Consumes: `ByteArchive(data, tolerant=True).read_fstring() -> str`, `FArchive.get_structured_diagnostics() -> list[Diagnostic]`
- Produces: unchanged `read_fstring()` signature; `fstring_all_null` diagnostic is emitted **only** when the entire payload is zero bytes (the `if not result:` path at archive.py:382-403 already guarantees that for all-zero payloads and stays untouched).

- [ ] **Step 1: Write the failing tests**

Append as module-level functions in `tests/test_core.py` (no decorators, no classes — `test_test_suite_structure_gate` requires that shape):

```python
def test_fstring_leading_null_with_content_is_not_all_null():
    """A leading NUL plus later non-zero bytes is NOT all-null (Lyra 35269)."""
    import struct

    from uasset_read.archive import ByteArchive

    # The exact misread payload from Lyra MovieScene offset 35273: 16 bytes,
    # first four zero, then 0x1d (BoolProperty name index), rest zero.
    # Mirror Lyra pos 35269: the data starts at 35273 (35273 % 4 == 1), so the
    # alignment-padding heuristic does not mask the false classification (a
    # pos-0 read of this payload is suppressed as padding and the test would
    # pass vacuously).
    payload = b"\xff" + struct.pack("<i", 16) + bytes.fromhex("000000001d0000000000000000000000")
    arc = ByteArchive(payload, tolerant=True)
    arc.seek(1)
    assert arc.read_fstring() == ""
    codes = [d.code for d in arc.get_structured_diagnostics()]
    assert "fstring_all_null" not in codes, codes


def test_fstring_all_zero_payload_still_records_all_null():
    """Entirely-zero payload keeps the existing fstring_all_null classification."""
    import struct

    from uasset_read.archive import ByteArchive

    payload = struct.pack("<i", 8) + b"\x00" * 8
    arc = ByteArchive(payload, tolerant=True)
    assert arc.read_fstring() == ""
    codes = [d.code for d in arc.get_structured_diagnostics()]
    assert "fstring_all_null" in codes, codes
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_core.py::test_fstring_leading_null_with_content_is_not_all_null tests/test_core.py::test_fstring_all_zero_payload_still_records_all_null -v`
Expected: first test FAILS (`'fstring_all_null' in codes` — the leading-NUL payload is misclassified today); second test PINS existing behavior and PASSES.

- [ ] **Step 3: Write minimal implementation**

In `src/uasset_read/archive.py`, the `first_null_idx == 0` else-branch (the comment "All nulls from start …" at lines 433-437, alignment check 438, emission 449-457): wrap the alignment-debug / `fstring_all_null` emission so it runs only when every payload byte is zero. The hex debug, padding-zone scan, and `return ""` below stay exactly as they are.

```python
            # first_null_idx == 0: payload starts with a NUL. Classify as
            # all-null ONLY when the entire payload is zero bytes — a leading
            # NUL plus later non-zero bytes is not all-null and must not emit
            # fstring_all_null (Lyra MovieScene pos 35269: 00 00 00 00 1d ...).
            if not any(data):
                if self._is_likely_alignment_padding(pos_before + 4, len(data)):
                    logger.debug(
                        "FString at pos %d: length=%d, encoding=UTF-8, "
                        "all nulls (likely alignment padding), "
                        "consumed=%d bytes, end_pos=%d",
                        pos_before,
                        length,
                        len(data),
                        self.tell(),
                    )
                else:
                    self._record_structured_diagnostic(
                        code="fstring_all_null",
                        stage="read_fstring",
                        offset=pos_before,
                        raw_value=length,
                        fallback="used_empty_string",
                        message=f"FString at pos {pos_before}: length={length}, encoding=UTF-8, all nulls (completely corrupted)",
                        reason="recovered_corruption",
                    )
            else:
                logger.debug(
                    "FString hex detail: pos=%d, hex=%s (leading NUL, non-zero content)",
                    pos_before,
                    data[:32].hex(),
                )
```

Do **not** touch the all-zero path at archive.py:382-403 (that is where genuinely-all-null payloads are classified), the internal-null truncation at 407-432, or any FString length rule.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_core.py::test_reader_boundaries_reject_malformed_access tests/test_core.py::test_fstring_leading_null_with_content_is_not_all_null tests/test_core.py::test_fstring_all_zero_payload_still_records_all_null -v`
Expected: all PASS. The first target is the registry runner that owns the pre-existing cases `fstring_all_null_recorded_both_encodings` (all-zero payloads still recorded) and `fstring_internal_null_truncation_is_recorded` (leading-NUL truncation unaffected).

- [ ] **Step 5: Commit**

```bash
git add src/uasset_read/archive.py tests/test_core.py
git commit -m "fix: classify fstring_all_null only when payload is all zeros"
```

---

### Task 2: `fstring_out_of_range` reason classification

**Files:**
- Modify: `src/uasset_read/archive.py:350-366` (the tolerant `fstring_out_of_range` `_record_structured_diagnostic` call inside `read_fstring`)
- Test: `tests/test_diagnostics_reason.py` (append after `test_fname_out_of_range_carries_recovered_corruption_reason`, line ~57)

**Interfaces:**
- Consumes: `Diagnostic.reason` vocabulary from `src/uasset_read/models/diagnostics.py:15-23` (`DiagnosticReason = Literal["bulk_expected", "editor_only", "known_unimplemented", "recovered_corruption", "conservative_complete", "unexpected", "schema_required"]`)
- Produces: `fstring_out_of_range` diagnostics carry `reason="recovered_corruption"` (same classification as `fstring_all_null`, `fstring_truncated_at_null`, and `name_index_out_of_range`).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_diagnostics_reason.py`:

```python
def test_fstring_out_of_range_carries_recovered_corruption_reason():
    import struct

    from uasset_read.archive import ByteArchive

    # Claims 1000 bytes, only 2 remain -> fstring_out_of_range (tolerant).
    arc = ByteArchive(struct.pack("<i", 1000) + b"ab", tolerant=True)
    assert arc.read_fstring() == ""
    (diag,) = [
        d for d in arc.get_structured_diagnostics() if d.code == "fstring_out_of_range"
    ]
    assert diag.reason == "recovered_corruption"
    assert diag.fallback == "used_empty_string"
    assert diag.offset == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_diagnostics_reason.py::test_fstring_out_of_range_carries_recovered_corruption_reason -v`
Expected: FAIL with `assert None == 'recovered_corruption'` (reason is not passed today).

- [ ] **Step 3: Write minimal implementation**

In `src/uasset_read/archive.py` lines 353-361, add the `reason` keyword to the existing tolerant-path record call (leave the strict-mode `ParseError` branch and the `fstring_length_exceeds_limit` call untouched):

```python
                self._record_structured_diagnostic(
                    code="fstring_out_of_range",
                    stage="read_fstring",
                    offset=pos_before,
                    raw_value=byte_len,
                    fallback="used_empty_string",
                    message=f"FString at pos {pos_before}: {enc} expected {byte_len} bytes "
                    f"but only {self._file_size - pos_before - 4} remain",
                    reason="recovered_corruption",
                )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_diagnostics_reason.py -v`
Expected: all PASS, including `test_fname_out_of_range_carries_recovered_corruption_reason` (unchanged precedent) and `test_bp_combat_character_trailing_diagnostics_carry_reason`.

- [ ] **Step 5: Commit**

```bash
git add src/uasset_read/archive.py tests/test_diagnostics_reason.py
git commit -m "fix: add recovered_corruption reason to fstring_out_of_range"
```

---

### Task 3: Validated tagged fallback for unknown size-0 struct map values

**Files:**
- Modify: `src/uasset_read/parsers/property_types.py:882-888` (gate), `:913-960` (tagged loop: record `diag_mark` + clean-None flag), `:964-976` (except-path rollback)
- Modify: `src/uasset_read/archive.py:255-257` (add rollback helper next to `get_structured_diagnostics`)
- Test: `tests/test_core.py` (append module-level functions; `parse_array_property` byte tests at line 673 establish the house pattern for direct container-parser tests)

**Interfaces:**
- Consumes: `PropertyTag(name, type, size, key_type, value_type, value_type_struct, struct_type)` (`src/uasset_read/models/properties.py:26-48`); `_dispatch_value_parse` / `_dispatch_key_parse` (`property_types.py:1318-1393`) unchanged — they already pass `tag.value_type_struct` through when present; `UE_NONE_SENTINEL`, `MAX_PROPERTY_COUNT`, `_MAX_TAGGED_FALLBACK_BYTES`
- Produces:
  - `FArchive.rollback_structured_diagnostics(mark: int) -> None` — drops diagnostics recorded after `mark`
  - `parse_map_property(tag, archive, name_map, export_map, summary=None) -> MapValue` (existing signature) now returns entries whose struct values are `StructValue(struct_type="Unknown", fields={"bExpanded": bool}, parse_status="success")` when the value is a clean None-terminated tagged stream, and byte-identical opaque `StructValue` (0 bytes consumed, diagnostics rolled back) otherwise
  - Poison behavior unchanged: `StreamPoisonedError` inside the attempt still re-raises (`property_types.py:961-963`); `_PROPERTY_STREAM_POISON_CODES` untouched (`property_parser.py:40-45`)

- [ ] **Step 1: Write the failing tests**

Append as module-level functions in `tests/test_core.py`:

```python
def test_map_value_unknown_struct_parses_tagged_until_none():
    """MapProperty struct values with no name in the tag parse as tagged fields.

    Legacy tags carry only key/value type FNames (PropertyTag.cpp:357-371), so
    value_type_struct is None; the dummy size=0 struct tag must still consume
    the None-terminated field stream (Lyra MovieScene ExpansionStates).
    """
    import struct

    from uasset_read.archive import ByteArchive
    from uasset_read.models.properties import PropertyTag
    from uasset_read.parsers.property_types import parse_map_property

    def fname(idx: int, number: int = 0) -> bytes:
        return struct.pack("<II", idx, number)

    # name_map: 0=bExpanded, 1=BoolProperty, 2=None
    name_map = ["bExpanded", "BoolProperty", "None"]
    # Legacy inner tag: name + type + size + array_index + BoolVal + HasPropertyGuid
    value = (
        fname(0)
        + fname(1)
        + struct.pack("<ii", 0, 0)
        + bytes([1, 0])  # bExpanded = true, no property guid
        + fname(2)  # None terminator = value boundary
    )
    key = struct.pack("<i", 4) + b"key\x00"
    payload = struct.pack("<ii", 0, 1) + key + value  # keys_to_remove=0, entries=1
    tag = PropertyTag(
        name="ExpansionStates",
        type="MapProperty",
        size=len(payload),
        key_type="StrProperty",
        value_type="StructProperty",
        value_type_struct=None,
    )
    arc = ByteArchive(payload, tolerant=True)
    arc._file_version_ue4 = 522
    arc._file_version_ue5 = 1004  # legacy tag path, same gate as the Lyra sample
    result = parse_map_property(tag, arc, name_map, export_map=[], summary=None)
    assert result.key_type == "StrProperty"
    assert result.value_type == "StructProperty"
    assert len(result.entries) == 1
    entry_value = result.entries[0]["value"]
    assert entry_value.struct_type == "Unknown"  # honest: legacy tag has no name
    assert entry_value.fields == {"bExpanded": True}
    assert entry_value.parse_status == "success"
    # Value boundary honored: cursor exactly at end, nothing spilled, no diagnostics.
    assert arc.tell() == len(payload)
    assert arc.get_structured_diagnostics() == []


def test_map_value_unknown_struct_garbage_rolls_back_without_spill():
    """A non-tagged (native/garbage) value must rewind to the entry start.

    The rejected attempt's diagnostics are rolled back so a failed attempt is
    byte- and diagnostic-identical to the old opaque behavior (export:7
    BindingIdToReferences stays clean).
    """
    import struct

    from uasset_read.archive import ByteArchive
    from uasset_read.models.properties import PropertyTag
    from uasset_read.parsers.property_types import parse_map_property

    name_map = ["bExpanded", "BoolProperty", "None"]
    key = struct.pack("<i", 4) + b"key\x00"
    garbage_value = b"\xff\xff\xff\xff\x00\x00\x00\x00"  # FName index 0xFFFFFFFF -> name OOR
    payload = struct.pack("<ii", 0, 1) + key + garbage_value
    tag = PropertyTag(
        name="BindingIdToReferences",
        type="MapProperty",
        size=len(payload),
        key_type="StrProperty",
        value_type="StructProperty",
        value_type_struct=None,
    )
    arc = ByteArchive(payload, tolerant=True)
    arc._file_version_ue4 = 522
    arc._file_version_ue5 = 1004
    result = parse_map_property(tag, arc, name_map, export_map=[], summary=None)
    entry_value = result.entries[0]["value"]
    assert entry_value.parse_status == "opaque"
    assert entry_value.fields == {}
    # Cursor never advanced into the value (no spill into the next segment).
    assert arc.tell() == 8 + len(key)
    # Diagnostics recorded by the rejected attempt were rolled back.
    assert arc.get_structured_diagnostics() == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_core.py::test_map_value_unknown_struct_parses_tagged_until_none tests/test_core.py::test_map_value_unknown_struct_garbage_rolls_back_without_spill -v`
Expected: first test FAILS (value comes back `parse_status="opaque"`, `fields == {}`, `tell()` short of `len(payload)` because the unknown struct consumes 0 bytes today). Second test PASSes trivially today (no attempt is made, so no diagnostics exist) — it is the regression guard against a naive unvalidated implementation; keep it.

- [ ] **Step 3: Write minimal implementation**

Three edits:

**(a) `src/uasset_read/archive.py` — add rollback helper directly after `get_structured_diagnostics` (line 255-257):**

```python
    def rollback_structured_diagnostics(self, mark: int) -> None:
        """Drop diagnostics recorded after *mark* (failed parse-attempt rewind).

        Only the structured-diagnostics list is rewound. ``_name_warnings_seen``
        dedup slots consumed by the failed attempt are kept, so a later genuine
        ``name_index_out_of_range`` at the same (>= 2**24) index may be
        suppressed once — an accepted ceiling of the validate-and-rollback
        design (ponytail: dedup slot leak per rejected attempt; clear the slots
        too if a real fixture ever hits the suppression).
        """
        del self._structured_diagnostics[mark:]
```

**(b) `src/uasset_read/parsers/property_types.py` — replace the early-opaque gate (lines 882-888):**

Current code:

```python
    if declared_struct_type not in _TAGGED_FALLBACK_STRUCTS and tag.size <= 0:
        return StructValue(
            struct_type=declared_struct_type or "UnknownStruct",
            fields={},
            raw_size=tag.size,
            parse_status="opaque",
        )
```

Replace with (falls through to the tagged loop below; the BinaryOrNative registry is deliberately skipped — see the gate note after this block):

```python
    # Unknown struct with no size (Map/Set dummy tags carry no per-value size;
    # legacy tags do not serialize a map value struct name — PropertyTag.cpp
    # 357-371). Attempt the tagged FStructFallback loop below and validate the
    # result: a clean None stop with no new diagnostics is accepted, anything
    # else rewinds to the entry start and stays opaque so the caller's cursor
    # never spills into the next segment (Lyra MovieScene ExpansionStates;
    # export:7 BindingIdToReferences native values keep old behavior).
    validated_attempt = declared_struct_type not in _TAGGED_FALLBACK_STRUCTS and tag.size <= 0
```

Then gate the BinaryOrNative registry lookup (lines 893-911) so validated attempts never reach it: change its entry condition to `if declared_struct_type and not validated_attempt:`. Today's gate returns before the registry for size<=0 unknowns; a registered handler (ue5>=1012 full-type path only — e.g. `NiagaraVariable`) that raises after a partial read (`:910-911` `pass`, no seek-back) would leave `struct_start` (captured later at line 923) mid-value, and the rewind would land at the wrong position. With this gate the "byte-identical" rollback guarantee below holds exactly.

**(c) same file — validate the attempt around the existing loop (lines 913-986):**

After `struct_start` / `tagged_byte_limit` are computed (lines 923-928), before `try:`, add:

```python
    diag_mark = len(archive.get_structured_diagnostics())
    clean_none_stop = False
```

Change the None-sentinel break (lines 940-941) from:

```python
            if inner_tag.name == UE_NONE_SENTINEL:
                break
```

to:

```python
            if inner_tag.name == UE_NONE_SENTINEL:
                clean_none_stop = True
                break
```

Immediately after the loop's `try/except` completes successfully — i.e. just before the existing boundary check at line 978 (`if struct_end is not None and archive.tell() != struct_end:`) — add the validation gate:

```python
    if validated_attempt and (
        not clean_none_stop or len(archive.get_structured_diagnostics()) > diag_mark
    ):
        # Not a clean None-terminated tagged stream (or the attempt recorded
        # recoveries): rewind exactly to the entry start — cursor and
        # diagnostics — and report opaque, byte-identical to pre-fallback.
        archive.rollback_structured_diagnostics(diag_mark)
        archive.seek(struct_start)
        return StructValue(
            struct_type=declared_struct_type or "UnknownStruct",
            fields={},
            raw_size=tag.size,
            parse_status="opaque",
        )
```

Extend the generic except branch (lines 964-976) so a failed validated attempt also rewinds (keep the in-set re-raise and the size>0 seeks unchanged):

```python
    except (struct.error, ParseError, OSError, ValueError):
        if declared_struct_type in _TAGGED_FALLBACK_STRUCTS:
            raise
        if validated_attempt:
            archive.rollback_structured_diagnostics(diag_mark)
            archive.seek(struct_start)
        elif struct_end is not None:
            archive.seek(struct_end)
        elif tag.size > 0:
            archive.seek(struct_start + tag.size)
        return StructValue(
            struct_type=declared_struct_type or "UnknownStruct",
            fields={},
            raw_size=tag.size,
            parse_status="opaque",
        )
```

Leave untouched: `except StreamPoisonedError: raise` (961-963), `_TAGGED_FALLBACK_STRUCTS` membership behavior for in-set structs (they never set `validated_attempt`, so their current loop/re-raise semantics are preserved), and both `_dispatch_*_parse` functions (propagation already correct where the tag carries a name).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_core.py::test_map_value_unknown_struct_parses_tagged_until_none tests/test_core.py::test_map_value_unknown_struct_garbage_rolls_back_without_spill -v`
Expected: both PASS.

- [ ] **Step 5: Run neighboring suites for regressions**

Run: `python -m pytest tests/test_core.py tests/test_properties.py tests/test_diagnostics_reason.py -q`
Expected: all PASS. Pay special attention to `test_bp_combat_character_category_text_still_decodes` (BPVariableDescription in-set fallback unchanged), `test_als_animbp_ordered_saved_pose_indices_map_keys` (CachedPoseIndices in-set unchanged), and `test_array_of_bools_consumes_one_byte_per_element` (arrays unchanged).

- [ ] **Step 6: Commit**

```bash
git add src/uasset_read/archive.py src/uasset_read/parsers/property_types.py tests/test_core.py
git commit -m "fix: parse unknown size-0 map value structs via validated tagged fallback"
```

---

### Task 4: Lyra fixture regression + hardening expectation upgrade

**Files:**
- Modify: `tests/test_parse_hardening.py:16-30` (`test_lyra_seq_fstring_out_of_range_is_bounded`)
- Modify: `tests/size-baseline.json` (the ratchet has zero headroom — all three areas sit at exact ceiling 28936/10986/58603; Tasks 1-4 add source and test lines, this task adds test lines and tracks this plan doc)
- Track: `docs/superpowers/plans/2026-09-23-moviescene-fstring-mapvalue-plan.md` (gitignored — force-add so `docs_markdown` counts it, matching how prior plan docs entered the count)
- Test: `tests/test_parse_hardening.py` (append new fixture test after line 30)

**Interfaces:**
- Consumes: `parse_package_document(path, depth="asset", tolerant=True)` (`src/uasset_read/package.py`); fixture `tests/samples/Lyra_SEQ_LobbyScreen_LevelSequence.uasset` (in manifest, SHA-256 verified by `tests/test_samples.py`); `_codes(doc)` helper already defined at `tests/test_parse_hardening.py:12-13`; Tasks 1-3 behavior
- Produces: pinned structural assertions — `export:9` complete, `EditorData.fields.ExpansionStates` = 31 entries with `bExpanded`, zero document-wide `fstring_out_of_range`, zero `fstring_all_null`/`name_index_out_of_range`, poison-stop machinery still green via `tests/test_core.py:252`.

- [ ] **Step 1: Run the existing hardening test to see the expectation upgrade it needs**

Run: `python -m pytest tests/test_parse_hardening.py::test_lyra_seq_fstring_out_of_range_is_bounded -v`
Expected: FAIL at `assert movie.status.parse == "partial"` — after Task 3 the MovieScene parses completely (`status.parse == "complete"`). This is the intended behavior upgrade, not a regression: `fstring_out_of_range` is now 0 (still `<= 1`) and all top-level keys are still present.

- [ ] **Step 2: Update the outdated assertion**

In `tests/test_parse_hardening.py`, change line 27 from:

```python
    assert movie.status.parse == "partial"
```

to:

```python
    # With the validated map-value struct fallback the stream is no longer
    # poisoned at ExpansionStates, so the MovieScene now parses completely.
    assert movie.status.parse == "complete"
```

Keep the `len(oor) <= 1` acceptance line and the top-level key loop (lines 23-30) unchanged — the poison-stop fan-out guard stays meaningful as an upper bound.

- [ ] **Step 3: Write the fixture regression test**

Append to `tests/test_parse_hardening.py`:

```python
def test_lyra_seq_expansion_states_parse_cleanly():
    """MapValue struct fallback: ExpansionStates decodes with no FString fallout."""
    doc = parse_package_document(
        SAMPLES / "Lyra_SEQ_LobbyScreen_LevelSequence.uasset",
        depth="asset",
        tolerant=True,
    )
    codes = _codes(doc)
    assert "fstring_out_of_range" not in codes, codes
    assert "name_index_out_of_range" not in codes, codes  # export:7 rollback pin
    movie_fstring = [
        d
        for d in doc.diagnostics
        if d.code == "fstring_all_null" and d.object_id == "export:9"
    ]
    assert not movie_fstring, movie_fstring

    movie = next(o for o in doc.objects if o.id == "export:9")
    assert movie.status.parse == "complete"
    for key in ("Spawnables", "ObjectBindings", "PlaybackRange", "EditorData", "Signature"):
        assert key in (movie.properties or {})

    editor_data = (movie.properties or {})["EditorData"]
    assert editor_data["kind"] == "struct"
    assert editor_data["struct_type"] == "MovieSceneEditorData"
    expansion = editor_data["fields"]["ExpansionStates"]
    assert expansion["kind"] == "map"
    assert expansion["key_type"] == "StrProperty"
    assert expansion["value_type"] == "StructProperty"
    entries = expansion["entries"]
    assert len(entries) == 31  # num_entries word at offset 35166
    first = entries[0]
    assert first["key"].endswith("MovieScene3DTransformTrack_1")
    assert first["value"]["struct_type"] == "Unknown"  # legacy tag carries no name
    assert first["value"]["fields"] == {"bExpanded": True}
    assert all("bExpanded" in e["value"]["fields"] for e in entries)
    # EditorData's other tagged fields came back too.
    for field in ("ViewStart", "ViewEnd", "WorkStart", "WorkEnd"):
        assert field in editor_data["fields"]
```

- [ ] **Step 4: Run the hardening suite**

Run: `python -m pytest tests/test_parse_hardening.py -v`
Expected: all PASS (updated existing test + new regression test).

- [ ] **Step 5: Raise the size-ratchet ceilings (zero headroom — this step is mandatory)**

Run: `git add -f docs/superpowers/plans/2026-09-23-moviescene-fstring-mapvalue-plan.md`
(The path is ignored by `.gitignore:109`; force-add matches how prior plan docs entered the `docs_markdown` count — `test_size_baseline.py` counts `git ls-files` only.)

Run: `python -m pytest tests/test_size_baseline.py -v`
Expected: FAIL on the areas this plan grew (`src_python` from Tasks 1-3, `tests_python` from all tasks, `docs_markdown` from the force-add). Read the measured values from the failure output (form: `"src_python: <measured> tracked lines exceeds baseline <max> (files=<n>)"`). Edit `tests/size-baseline.json`: set each failing area's `max_lines` to its measured value and append one `_note` sentence: `Raised 2026-09-23 moviescene mapvalue plan from measured pytest size-baseline failure output.` Do not raise a ceiling that did not fail; no slack beyond the measured value.

Run: `python -m pytest tests/test_size_baseline.py -v`
Expected: PASS.

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest tests/ -q`
Expected: all PASS (no skips introduced; `test_test_suite_structure_gate` accepts the new module-level tests).

- [ ] **Step 7: Commit**

```bash
git add tests/test_parse_hardening.py tests/size-baseline.json docs/superpowers/plans/2026-09-23-moviescene-fstring-mapvalue-plan.md
git commit -m "test: pin Lyra MovieScene ExpansionStates clean parse"
```
