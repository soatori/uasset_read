# Ponytail Audit Cleanup Implementation Plan

> **Status (2026-09-08):** Executed via [code-size waves 0-5 plan](../superpowers/plans/2026-09-08-code-size-reduction-waves.md). Tasks 1-2, 7-14 of this design were implemented as Wave 0-5 tasks. Tasks 3 (Source/ArchiveLike family), 4 (VersionContext slimming), 5 (CLI log flags), 6 (JmapParser) were rejected by the roadmap exclusion list. Net result: src 28,085→23,327 lines (−4,758), wheel 300,836→249,257 bytes (−51,579), 208 tests passing.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete the ~5,580 lines of unreachable, write-only, and duplicated code identified by the 2026-09-08 whole-repo ponytail audit, plus extract shared patterns to reduce additional ~15-20% code size while preserving all functionality and memory safety.

**Architecture:** Pure subtraction. Nothing here changes a live parse path; each task removes code that is gated off, write-only, or a verbatim duplicate, and the existing suite (samples + synthetic) is the regression gate. Where a task replaces code with an equivalent shorter form (dispatch tables, `struct.Struct`, tuples), the new form must produce byte-identical reads and dict/dataclass outputs.

**Tech Stack:** Python 3.10+ (local gate is Windows + Python 3.14), pytest, `git rm`, stdlib `struct`/`pathlib`.

**Spec:** This file. Findings were grep-verified against all of `src/` and `tests/` on 2026-09-08; re-verify each "zero callers" claim before cutting — the tree is active.

## Global Constraints

- Commit format `<type>: <summary>`; type is `refactor:` for every task here. No push.
- English code/comments. Run tests from repo root: `python -m pytest -q`.
- `tests/test_size_baseline.py` ratchets `tests/size-baseline.json` with BOTH `max_lines` (ceilings — deletions are fine) and `min_files` (floors — file-deleting waves MUST lower `src_python.min_files` in the same commit or the suite fails). Repo convention: after each wave re-measure and set `max_lines`/`min_files` to exact values with a one-line `_note` append. Measure with:

  ```bash
  python -c "
  import subprocess,json,pathlib
  files=subprocess.run(['git','ls-files','-z','src'],capture_output=True).stdout.decode().split('\0')
  py=[f for f in files if f.endswith('.py')]
  lines=sum(len((pathlib.Path(f)).read_bytes().splitlines()) for f in py)
  tf=subprocess.run(['git','ls-files','-z','tests'],capture_output=True).stdout.decode().split('\0')
  tpy=[f for f in tf if f.endswith('.py')]
  tlines=sum(len(pathlib.Path(f).read_bytes().splitlines()) for f in tpy)
  print('src',len(py),lines,'tests',len(tpy),tlines)"
  ```

- If the full suite has pre-existing failures (WIP on the branch), record them in Task 0 and treat "same failures, no new ones" as the parity gate.
- Read-only parser; never introduce writes. Never touch `external/`, `UnrealEngine/`, `dist/`.

---

### Task 0: Prerequisites and baseline

**Files:** none (branch + record only)

- [ ] **Step 0.1:** Confirm the user has committed or stashed the current `dev-0.6.0` WIP (git status showed modifications in `archive.py`, `cli.py`, `package.py`, `class_registry.py`, `asset_types/__init__.py`, `movie_scene*.py`, `property_types.py`, `object_resources.py`, `package_summary.py`, kismet files). Line references in this plan track the *current working tree*; re-locate by symbol, not line number, if the base moved. If WIP is uncommitted, STOP and ask the user.
- [ ] **Step 0.2:** `git checkout -b cleanup/ponytail-audit`
- [ ] **Step 0.3:** Baseline run: `python -m pytest -q 2>&1 | tail -5` — record pass/fail counts and the exact list of any failing test ids in the working notes for later parity checks.
- [ ] **Step 0.4:** Sanity-confirm the audit gate is still closed (if this fails, Task 1 is void):

  ```bash
  grep -n "run_class_handlers" src/uasset_read/parsers/legacy_reader.py src/uasset_read/parsers/property_parser.py
  ```

  Expected: exactly one `run_class_handlers=False` call site (legacy_reader.py:~838) plus the flag/gate plumbing in property_parser.py.

---

### Task 1: Delete the unreachable v1 ClassHandler stack (~3,850 lines)

**Files:**

- Delete: `src/uasset_read/parsers/class_registry.py`
- Delete: `src/uasset_read/parsers/asset_types/{anim_blueprint,anim_common,anim_montage,anim_sequence,curve_table,data_table,level_sequence,movie_scene,movie_scene_control_rig,niagara_node,niagara_projection,opaque_stub,property_extractor,property_metadata,skeleton,sound_wave,user_defined}.py`
- Delete: `src/uasset_read/models/ir_anim.py` (only consumers are the v1 anim handlers above; `models/core.py:12` only mentions it in a docstring)
- Modify: `src/uasset_read/parsers/asset_types/__init__.py` (keep only a docstring), `src/uasset_read/parsers/property_parser.py:448-543` + `:1097` + `:1199`, `src/uasset_read/parsers/legacy_reader.py:838`, `src/uasset_read/models/core.py:12`, `tests/test_core.py:2135-2147`
- Modify: `tests/size-baseline.json`

**Interfaces:** Consumes nothing new. Produces: `asset_types` package containing only `handlers_impl.py`; `parse_properties_from_export(...)` loses the `run_class_handlers` parameter.

**Checkpoint (gate for the whole task):** v2 must cover the v1 classes. Open `asset_types/__init__.py`'s registration tables and `_OPAQUE_STUB_CLASS_NAMES`, and confirm every listed class name is either (a) registered in `handlers_impl.py`, or (b) handled by the generic fallback/`class_specific_skip` path. If any class has no v2 home, STOP and report the names; do not delete those modules.

- [ ] **Step 1.1:** In `property_parser.py`: delete `_try_asset_type_handler` (def at :448 through its end ~:543), the `run_class_handlers: bool = True` parameter (:1097) and its docstring entry, the gate block at :1199 (`if run_class_handlers and skip_class_name is not None:` + body), and any `get_class_registry` import.
- [ ] **Step 1.2:** In `legacy_reader.py:838` delete the `run_class_handlers=False,` line and the two-line comment above it ("v2 has no v1 class-handler dispatch at any depth.").
- [ ] **Step 1.3:** `git rm` the 19 files above. Replace `asset_types/__init__.py` with:

  ```python
  """Asset-type semantic handlers (v2). handlers_impl.run_handlers is the only dispatch path."""
  ```

  In `models/core.py` delete the docstring line that references `models/ir_anim.py`.
- [ ] **Step 1.4:** Fix tests: in `test_core.py::test_guid_display_is_36_chars` delete the two `u_src` lines (`u_src = ...` and `assert "00000000" not in u_src`). Then verify nothing still references the deleted symbols:

  ```bash
  grep -rn "class_registry\|AssetTypeHandler\|PropertyMetadataHandler\|register_asset_type\|parse_material_instance\|_OPAQUE_STUB\|ir_anim\|anim_common\|property_extractor\|build_property_metadata\|NiagaraNodeHandler\|parse_skeleton\|parse_sound_wave\|parse_curve_table\|parse_data_table\|parse_level_sequence\|parse_user_defined\|AnimBlueprintHandler\|AnimMontageHandler\|AnimSequenceHandler\|MovieSceneHandler" src tests --include="*.py"
  ```

  Expected: no hits. Fix any stray hit by deleting the referencing line.
- [ ] **Step 1.5:** Re-measure + update `tests/size-baseline.json` (expect roughly `src_python.min_files 95→~78`, `max_lines` to the new exact count; append one `_note` sentence). Run `python -m pytest -q`; parity with Task 0 baseline.
- [ ] **Step 1.6:** Commit: `git commit -am "refactor: delete unreachable v1 ClassHandler stack (gated off at the sole call site)"`

---

### Task 2: Delete MathFunctionCleaner (~430 lines)

> **Canceled / superseded 2026-09-10 by Gate K** (`2026-09-10-codebase-slimming-plan.md`): the entire C++ pseudocode generator chain (`translator.py`, `body_builder.py`, `jump_analyzer.py`) was deleted. This task is no longer applicable.

**Files:** Modify `src/uasset_read/kismet/translator.py`

**Interfaces:** Unchanged public surface; `line_cpp` output for `EX_CallMath` is byte-identical (clean() already always fell to the generic fallback).

- [ ] **Step 2.1:** Verify the premise from a clean shell before cutting (must print nothing):

  ```bash
  grep -rn "MathFunctionCleaner" src tests --include="*.py" | grep -v "translator.py"
  ```

- [ ] **Step 2.2:** In translator.py replace the call (line ~1019-1020):

  ```python
  return MathFunctionCleaner.clean(cn, f"Call_{stack_node}", params_list)
  ```

  with the fallback it always produced:

  ```python
  return f"{cn}::Call_{stack_node}({', '.join(params_list)})"
  ```

- [ ] **Step 2.3:** Delete the whole `class MathFunctionCleaner` block (:157 up to the `# KismetTranslator — central line_cpp() dispatcher` banner) and the module docstring/`# Decision D-04, D-05` header lines about it (keep the banner comment for KismetTranslator). Check translator docstring lines near the top (":9") mention and remove.
- [ ] **Step 2.4:** Suite parity; update `size-baseline.json` lines; commit `refactor: delete MathFunctionCleaner — caller passes synthetic names so every branch fell through to the generic fallback`.

---

### Task 3: Delete the Source abstraction family, ArchiveLike, read_cstring (~180 lines)

> **Executed 2026-09-10** (`319d9179`): ArchiveLike, read_cstring, Source/FileSource/MemorySource/SliceReader deleted; package/package_trailer annotations → FArchive; SourceInfo kept; Source-family tests removed (export_bounds retained).

**Files:** Modify `src/uasset_read/archive.py` (lines :27-35 `ArchiveLike`, :349-364 `read_cstring`, :743-879 protocol+impls), `src/uasset_read/package.py:12,29-30,175`, `tests/test_core.py` (Source nested defs in `test_reader_boundaries_reject_malformed_access`, :~97-190 and :~253-267), `src/uasset_read/serializers/graph_pin.py:452` + `archive.py:662` (`_contains_binary_data` params), `tests/size-baseline.json`

**Interfaces:** `package.py` annotations become `FArchive`; `PackageArchive` still accepts `FArchive`/`ByteArchive` (both subclasses).

- [ ] **Step 3.1:** Verify zero production consumers (only archive.py internals + tests match):

  ```bash
  grep -rn "FileSource\|MemorySource\|SliceReader\|ArchiveLike\|read_cstring" src tests --include="*.py" | grep -v "archive.py\|test_core.py"
  ```

  Expected: only `package.py` `ArchiveLike` annotations and the `legacy_reader.py:~1294` docstring word "read_cstring" (that docstring describes the *wire format*, keep the prose, optionally reword "(`read_cstring`)" → "(byte-at-a-time)").
- [ ] **Step 3.2:** archive.py: delete `ArchiveLike` (:27-35), `read_cstring` (:349-364), and the block from `# Source abstraction` (:743) to end-of-file EXCEPT the `SourceInfo` dataclass — keep `SourceInfo` verbatim (move it next to `ByteArchive`). Drop now-unused imports (`Protocol`, `runtime_checkable`; keep `dataclass`, `Path`).
- [ ] **Step 3.3:** In `_contains_binary_data` (:662) drop the `threshold` and `max_check_length` parameters (sole caller `graph_pin.py:456` uses defaults); inline `0.3`/`256` as locals.
- [ ] **Step 3.4:** package.py: change `ArchiveLike` annotations (:29-30, :175) to `FArchive` and drop `ArchiveLike` from the line-12 import.
- [ ] **Step 3.5:** test_core.py: inside `test_reader_boundaries_reject_malformed_access`, delete the `from uasset_read.package import PackageArchive` + `from uasset_read.archive import FileSource, MemorySource, SliceReader` import and these nested defs: `test_size`, `test_read_at`, `test_read_at_negative_offset`, `test_read_at_overflow`, `test_describe`, `test_file_read`, `test_file_read_out_of_range`, `test_file_close_without_handle`, `test_basic_read`, `test_seek`, `test_seek_out_of_range`, `test_read_exceeds_slice`, `test_sub_slice`, `test_sub_slice_out_of_range`, `test_nested_sub_slice`, `test_invalid_slice_negative_base`, `test_invalid_slice_exceeds_source`, `test_slice_reader_satisfies_archive_like`, `sources_reject_negative_size` — and their 19 matching entries in the `_run_cases([...])` list. KEEP every other nested def and entry (`core_contract`, `test_export_read_within_range_succeeds`, iostore cases, etc.).
- [ ] **Step 3.6:** Suite parity, baseline json, commit `refactor: delete Source protocol family, ArchiveLike and read_cstring (zero production consumers)`.

---

### Task 4: Slim VersionContext to `depth` (~100 lines)

> **SKIP 2026-09-10:** G1 contract (`2026-08-31-version-context-field-contract.md`) requires frozen multi-field VersionContext; an identical cut was already reverted (`280b7e09`). Fields remain extension points for Zen/#623/#624. Revisit only after amending G1.

**Files:** Modify `src/uasset_read/versioning.py:40-159` (keep `EngineVersion`, GUID constants, `get_custom_version`), `src/uasset_read/parsers/legacy_reader.py:50,693-699`, `tests/test_core.py` (`test_v2_mappings_never_passes_raw_path_string` + its `_run_cases` entry), `tests/size-baseline.json`

**Interfaces:** `VersionContext` becomes a frozen dataclass with one field. All `context: VersionContext` annotations in `handlers_impl.py` stay valid.

- [ ] **Step 4.1:** Re-verify only `depth` is read:

  ```bash
  grep -rn "context\.[a-z_]*" src/uasset_read/parsers/ --include="*.py" -o | grep -v "\.depth" | grep -v "def \|context:"
  ```

  Expected: no VersionContext-field hits (other `context.` objects exist in kismet — inspect matches; only `file_version_ue4|ue5|custom_versions|engine_version|is_ue5|version_string|package_layout|cooked|editor_only_filtered|platform|game|byte_order|mappings` reads would void the cut).
- [ ] **Step 4.2:** versioning.py:

  ```python
  @dataclass(frozen=True)
  class VersionContext:
      """Immutable parse context. All readers share this."""

      depth: Literal["package", "object", "asset", "decode"] = "package"
  ```

  Delete `MappingInfo`, `is_ue5`, `version_string`, and `build_version_context_from_summary` entirely; drop now-unused imports (`field`, `Mapping`, `Any`, `TYPE_CHECKING` block if `PackageFileSummary` was its only use).
- [ ] **Step 4.3:** legacy_reader.py: replace the `build_version_context_from_summary(...)` call block with `context = VersionContext(depth=depth)`; change the import on :50 to `from ..versioning import VersionContext` (keep `MappingInfo` import removed only if grep confirms no other use).
- [ ] **Step 4.4:** In test_core.py read `test_v2_mappings_never_passes_raw_path_string` first: if it asserts `VersionContext.mappings` shape, delete the def and its `_run_cases` entry; if it asserts something about `TypeMappingsProvider` instead, keep it and adapt.
- [ ] **Step 4.5:** Suite parity, baseline json, commit `refactor: slim VersionContext to depth-only — remaining fields were written but never read`.

---

### Task 5: Delete five dead CLI log flags (~35 lines)

**Files:** Modify `src/uasset_read/cli.py:113-145`, plus grep tests for `--log-` usage; `tests/size-baseline.json`

- [x] **Step 5.1:** `grep -rn "log_level\|log_format\|log_max_bytes\|log_backup_count\|log_cleanup" src tests --include="*.py"` — confirm the only hits are the five `add_argument` blocks.
- [x] **Step 5.2:** Delete the `--log-level`, `--log-cleanup`, `--log-max-bytes`, `--log-backup-count`, `--log-format` `add_argument` calls. Keep `--log-dir`, `--log-keep-latest`, `--log-max-total-mb` (they feed `--clean-logs` at cli.py:291-294). *(Gate L 2026-09-10 later retired `--clean-logs` and those three inputs as well.)*
- [x] **Step 5.3:** Fix help texts that reference the deleted flags: `--log-keep-latest` "When cleanup is enabled..." → "When --clean-logs runs, keep only the newest N complete runs"; `--log-max-total-mb` "When --log-cleanup is set..." → "When --clean-logs runs, cap total log storage to MB megabytes". *(Superseded by Gate L: the remaining cleanup flags no longer exist.)*
- [x] **Step 5.4:** Suite parity (`tests/test_cli.py` must stay green), baseline json, commit `refactor: drop five CLI log flags that were parsed but never read`.

---

### Task 6: Delete JmapParser + mappings tidy (~95 lines)

> **Executed 2026-09-10** (`2509f99d` + `74e1ad7b`): JmapParser and `.jmap` dispatch deleted; pathlib; constants.MAX_RECURSION_DEPTH dropped; CLI/README `.jmap` claims removed.

**Files:** Modify `src/uasset_read/mappings.py` (:304-389 class, :401-402 `.jmap` branch, `:5 import json`, `Dict` typing import if orphaned, :172/:312→ wait 312 dies with the class; remaining `os.path.getsize`/`os.path.basename` → `pathlib`), `src/uasset_read/cli.py:108` (`--mappings` help), `src/uasset_read/constants.py:61-63` (`MAX_RECURSION_DEPTH` — zero importers; mappings.py keeps its own `= 64`), `tests/size-baseline.json`

- [ ] **Step 6.1:** Verify zero fixtures/tests reference jmap: `grep -rni "jmap" src tests --include="*.py" | grep -v mappings.py`; confirm `constants.MAX_RECURSION_DEPTH` has no importers: `grep -rn "MAX_RECURSION_DEPTH" src tests --include="*.py"`.
- [ ] **Step 6.2:** Delete `class JmapParser`, the `if lower.endswith(".jmap")...` branch in `TypeMappingsProvider.from_file`, and the `json` import. Reword the provider docstring "Load Usmap/Jmap mapping by file extension." → "Load a .usmap mapping file."
- [ ] **Step 6.3:** In `UsmapParser.__init__` and `from_file`, replace `os.path.getsize(p)` → `Path(p).stat().st_size` and `os.path.basename(path)` → `Path(path).name`; add `from pathlib import Path` if missing; drop the `os` import if nothing else uses it (`grep -n "os\." mappings.py`). Keep `gzip` (UsmapParser uses it).
- [ ] **Step 6.4:** cli.py `--mappings` help: ".usmap/.jmap" → ".usmap". Delete `MAX_RECURSION_DEPTH` from constants.py.
- [ ] **Step 6.5:** Suite parity, baseline json, commit `refactor: delete speculative JmapParser; unify path handling on pathlib; drop duplicate MAX_RECURSION_DEPTH`.

---

### Task 7: Dedup class resolvers + delete dead model/constant scraps (~60 lines)

**Files:** Modify `src/uasset_read/serializers/object_resources.py:390-401` (`get_asset_class`) + `:455` (internal caller), `serializers/graph_helpers.py:57-66` (`_rcn`,`_gac`) + `:29-32` import block, `serializers/{graph_node.py,graph_pin.py,graph.py,blueprint_graph.py}` call sites, `src/uasset_read/iostore.py:64-70,118-124,176-183,201-202`, dead-field list below, `tests/size-baseline.json`

- [ ] **Step 7.1:** Delete `get_asset_class`; fix its internal caller `object_resources.py:455` → `resolve_class_name(exp.class_index, import_map, export_map)`, `blueprint_graph.py:112,124` same pattern. Delete `_rcn`/`_gac` wrappers from graph_helpers.py (and the `get_asset_class` import there); mechanically rename every `_rcn(` call to `resolve_class_name(` (import it directly in graph_node.py/graph_pin.py), and `_gac(X, im, em)` calls to `resolve_class_name(X.class_index, im, em)` (graph.py:147,200, graph_node.py:442).
- [ ] **Step 7.2:** iostore.py: delete the four unused accessors (`IoStoreChunk.memory_mapped`, `IoStoreToc.physical_bytes`, `IoStoreToc.flag_names`, `IoStoreToc.files_for`) and `_FLAG_NAMES`. Keep all `FLAG_*`/`META_*` constants (used in `read_toc` gating and meta masking).
- [ ] **Step 7.3:** Delete the grep-verified zero-reference scraps (one grep before each): `models/diagnostics.py:12-13` (`DIAGNOSTIC_CODE_INVALID_SERIAL_SIZE`, `DIAGNOSTIC_CODE_INVALID_OFFSET`), `models/core.py:33-34` (`FEdGraphPinType.is_map_key/is_map_value` — check `graph_pin.py` map handling doesn't write them; it sets `map_key_terminal_*` on FEdGraphPinType fields instead — verify before deleting), `models/properties.py` (`PropertyTypeName.child()`), `models/payloads.py` (`PayloadDescriptor.hash`), `models/fallback.py` (`FallbackReason.PARTIAL_PARSE`, `CUSTOM_PAYLOAD`), `package.py` `_normalize_ext` + its dead call sites (callers already pass dotted literals).
- [ ] **Step 7.4:** `grep -rn "read_package_trailer(" src` — `serializers/package_trailer.py:85` `read_package_trailer(archive, payload_toc_offset)` ignores the offset: change signature to `(archive)` and update `legacy_reader.py:475`.
- [ ] **Step 7.5:** Suite parity, baseline json, commit `refactor: dedup get_asset_class/_rcn/_gac, drop dead accessors and constants`.

---

### Task 8: Collapse graph_node tag-handler zoo + graph_pin dead outputs (~100 lines)

**Files:** Modify `src/uasset_read/serializers/graph_node.py:582-790`, `src/uasset_read/serializers/graph_pin.py` (dead output build lines + fields + `_read_pin_ftext_field`), `tests/size-baseline.json`

**Interfaces:** `_read_node_property_tag` keeps its signature and the same returned updates-dict keys. JSON output keys `linked_to_objects`/`sub_pins_objects`/`parent_pin_object`/`ref_pass_through_object`/`default_object_ref`/`is_event`/`pin_subcategory_object_ref` disappear from pin payloads — run `grep -rn "linked_to_objects\|sub_pins_objects\|parent_pin_object\|ref_pass_through_object\|default_object_ref\|is_event\|pin_subcategory_object_ref" tests` first; if `test_schema_contract_statics` or sample tests assert these keys, update those expectations in this task (the keys are always `None`/`[None...]` today).

- [ ] **Step 8.1:** Add above `_NODE_TAG_HANDLERS` in graph_node.py:

  ```python
  # tag name -> (reader, out_key | None, skip_when_empty)
  #   out_key None writes only raw_properties[tag.name]; skip_when_empty mirrors the
  #   former size guards in _handle_i32_to_raw / _handle_function_flags.
  _NODE_SIMPLE_TAGS: dict[str, tuple[str, str | None, bool]] = {
      "NodePosX": ("i32", "node_pos_x", False),
      "NodePosY": ("i32", "node_pos_y", False),
      "NodeWidth": ("i32", None, True),
      "NodeHeight": ("i32", None, True),
      "FontSize": ("i32", None, True),
      "CommentDepth": ("i32", None, True),
      "ExtraFlags": ("i32", None, True),
      "bCommentBubbleVisible_InDetailsPanel": ("bool", None, False),
      "bDefaultsToPureFunc": ("bool", None, False),
      "bIsEditable": ("bool", None, False),
      "bOverrideFunction": ("bool", "b_override_function", False),
      "bInternalEvent": ("bool", "b_internal_event", False),
      "CustomFunctionName": ("fname", "custom_function_name", False),
      "CustomGeneratedFunctionName": ("fname", None, False),
      "FunctionFlags": ("i32", "function_flags", True),
  }
  ```

- [ ] **Step 8.2:** Delete the nine functions `_handle_node_pos_x`, `_handle_node_pos_y`, `_handle_i32_to_raw`, `_handle_bool_to_raw`, `_handle_override_function`, `_handle_internal_event`, `_handle_custom_function_name`, `_handle_fname_to_raw`, `_handle_function_flags`; remove their 15 entries from `_NODE_TAG_HANDLERS`. In `_read_node_property_tag`, before the `_NODE_TAG_HANDLERS.get` lookup:

  ```python
  if tag.name in _NODE_SIMPLE_TAGS:
      kind, out_key, skip_when_empty = _NODE_SIMPLE_TAGS[tag.name]
      if skip_when_empty and tag.size <= 0:
          return {}
      if kind == "i32":
          val = _read_tag_i32(archive, tag)
      elif kind == "bool":
          val = _read_tag_bool(archive, tag)
      else:
          val = _read_tag_fname(archive, tag, name_map)
      raw_properties[tag.name] = val
      return {} if out_key is None else {out_key: val}
  ```

- [ ] **Step 8.3:** graph_pin.py: delete the four `*_objects`/`parent_pin_object`/`ref_pass_through_object` extraction lines (`read_pin_reference` never emits key `"owning_node_object"` — verify with `grep -n "owning_node_object" serializers/graph_pin.py`: only these `.get(...)` reads exist), the hardcoded `default_object_ref = None`, and the matching `UEdGraphPin` dataclass fields; delete `is_event` and `pin_subcategory_object_ref` fields + their assignments (the except branch sets it to None only).
- [ ] **Step 8.4:** `_read_pin_ftext_field` returns `str | None` (drop the always-discarded `ok` half of the tuple): change both call sites `x, _ = _read_pin_ftext_field(...)` → `x = _read_pin_ftext_field(...)`.
- [ ] **Step 8.5:** Suite parity (graph tests in `test_blueprint_graph.py`, `test_samples.py`, handler cases in `test_core.py`), baseline json, commit `refactor: table-drive trivial node PropertyTag handlers; drop never-populated pin outputs`.

---

### Task 9: validate_pin_reference_at + ftext helper returns (~30 lines)

**Files:** Modify `src/uasset_read/serializers/graph_helpers.py:310-409`, callers in `graph_pin.py:199,299,305,394`

- [ ] **Step 9.1:** Verify which result keys callers read:

  ```bash
  grep -n 'ref_validation\[\|pin_ref_1\[\|pin_ref_2\[\|pin_ref_result\[\|\.get("valid\|\.get("reason\|\.get("serialized_size\|\["serialized_size"\]' src/uasset_read/serializers/graph_pin.py
  ```

  If only `valid`/`reason` (and null-vs-nonnull size via `is not None`) are read, change the return to `tuple[bool, str] | None` (`None` = escape risk that the old `None` meant), delete the 7-key dict construction, and update the 4 callers. Also inside, `struct.unpack(fmt+"i", ...)` is a hand-rolled `archive.read_i32` with seek/save — keep the manual seek pattern (it must not move the cursor permanently) but use `int.from_bytes(..., "big"/"little")`? No: simplest faithful form is what exists — only collapse the dict, do not rewrite the reads.
- [ ] **Step 9.2:** graph_helpers.py: `_read_fstring_safe` — keep its seek-back-on-oversize tolerance, but replace its body with the same `abs(length)` + decode logic it duplicates from `FArchive.read_fstring` only where it saves lines; if the diff is not clearly smaller, leave it (this sub-cut is optional; skip when the tolerance paths make it a wash — decide by line delta after editing).
- [ ] **Step 9.3:** Suite parity, baseline json, commit `refactor: validate_pin_reference_at returns (valid, reason) instead of a 7-key dict`.

---

### Task 10: package_summary dict helpers → tuples; merge twin helpers; property_tags branch merge (~55 lines)

**Files:** Modify `src/uasset_read/serializers/package_summary.py:175-204,416-673,780-815`, `serializers/property_tags.py:313-337`

- [ ] **Step 10.1:** Change the five dict-returning helpers to return positional tuples, and unpack once in `read_package_summary`:
  - `_read_pre_export_fields(...) -> tuple[int, int, str, int, int]` (soft_count, soft_offset, localization_id, gather_count, gather_offset)
  - `_read_post_import_optional_fields(...) -> tuple[int, int, int, int, int]` (cell_export_count, cell_export_offset, cell_import_count, cell_import_offset, metadata_offset)
  - `_read_secondary_offset_fields(...) -> tuple[int, int, int, int, int]` (depends, soft_pkg_count, soft_pkg_offset, searchable, thumbnail)
  - `_read_tail_offsets(...) -> tuple[int, int, int, list]` (asset_registry, bulk_start, world_tile, chunk_ids)
  - `_read_late_versioned_fields(...) -> tuple[int, int, int, int, int]` (preload_count, preload_offset, names_referenced, payload_toc, data_resource)
  In the consumer, e.g. `pre_export = _read_pre_export_fields(...)` becomes
  `soft_object_paths_count, soft_object_paths_offset, localization_id, gatherable_text_data_count, gatherable_text_data_offset = _read_pre_export_fields(archive, file_version_ue5, file_version_ue4, has_filter_editor_only)`
  and the `PackageFileSummary(...)` kwargs drop their `pre_export["..."]` indexing for the bare names. Same for `post_import`/`secondary`/`tail`/`late` (grep `pre_export[\|post_import[\|secondary[\|tail[\|late[` to confirm the only consumers are inside `read_package_summary`).
- [ ] **Step 10.2:** Merge `_read_custom_versions` + `_read_custom_versions_guids` into `def _read_custom_versions(archive: FArchive, with_names: bool = False) -> list:` — inside the loop, `if with_names: archive.read_fstring()  # FriendlyName (FGuid format)` after the version read. Update both call sites by keyword.
- [ ] **Step 10.3:** property_tags.py `_read_property_tag_legacy`: merge Byte/Enum branches (`elif tag.type in ("ByteProperty", "EnumProperty"):` — identical bodies) and the Array/Set/Optional trio via a module-level

  ```python
  _INNER_TAG_GATES = {
      "ArrayProperty": UE4_ARRAY_PROPERTY_INNER_TAGS,
      "SetProperty": UE4_PROPERTY_TAG_SET_MAP_SUPPORT,
      "OptionalProperty": UE4_PROPERTY_TAG_SET_MAP_SUPPORT,
  }
  ```

  with `elif tag.type in _INNER_TAG_GATES and file_version_ue4 >= _INNER_TAG_GATES[tag.type]: tag.inner_type = archive.read_name(name_map)`.
- [ ] **Step 10.4:** Suite parity, baseline json, commit `refactor: positional tuples for package-summary field groups; merge duplicate custom-version and property-tag readers`.

---

### Task 11: data_resource / package_trailer to struct.Struct (~25 lines)

**Files:** Modify `src/uasset_read/serializers/data_resource.py`, `serializers/package_trailer.py`; tests `tests/serialization/test_data_resource.py`, `tests/serialization/test_package_trailer.py`

- [ ] **Step 11.1:** data_resource.py module constants + rewritten loop (field order per ObjectResource.cpp: `Flags`, v2+`CookedIndex`, `SerialOffset`, `DuplicateSerialOffset`, `SerialSize`, `RawSize`, `OuterIndex`, `LegacyBulkDataFlags`):

  ```python
  _ROW_V2 = struct.Struct("<IBqqqqiI")
  _ROW_V1 = struct.Struct("<IqqqqiI")
  ...
    row = _ROW_V2 if version >= 2 else _ROW_V1
    resources = []
    for fields in row.iter_unpack(archive.read(count * row.size)):
        if version >= 2:
            flags, cooked_index, serial_offset, dup, size, raw, outer, legacy = fields
        else:
            flags, serial_offset, dup, size, raw, outer, legacy = fields
            cooked_index = 0
        resources.append(FObjectDataResource(
            flags=flags, cooked_index=cooked_index, serial_offset=serial_offset,
            duplicate_serial_offset=dup, serial_size=size, raw_size=raw,
            outer_index=outer, legacy_bulk_data_flags=legacy,
        ))
  ```

  Also hoist the header: `version, count = struct.unpack("<Ii", archive.read(8))`.
- [ ] **Step 11.2:** package_trailer.py: header `tag, version, header_length, payloads_data_length, num_payloads = struct.unpack("<QIIQi", archive.read(28))` (keep the two ValueError checks and their messages); entry head `_ENTRY_HEAD = struct.Struct("<20sqQQ")` then version tails `_TAIL_V2 = struct.Struct("<HHB")`, `_TAIL_V1 = struct.Struct("<B")` — rewrite `read_lookup_table_entry` to read head + (tail per version), preserving the short-read error `f"Short read for FIoHash: got {len(identifier)} bytes"` (check head read length < 44 raises the same message using first 20 bytes length).
- [ ] **Step 11.3:** Suite parity (the two serialization test files are the gate), baseline json, commit `refactor: precompiled struct formats for data-resource rows and package trailer`.

---

### Task 12: Kismet micro-cuts batch (~220 lines)

**Files:** Modify `src/uasset_read/kismet/{property_pointer,ufunction_reader,archive,native_fields}.py`, `kismet/expressions/{casts,special,functions,delegates}.py`, `tests/size-baseline.json`

> **Note 2026-09-10 (Gate K):** `body_builder.py`, `jump_analyzer.py`, and `translator.py` no longer exist. Steps 12.2 and 12.3 are canceled; in step 12.5, skip only the deleted `translator.py` portion and independently re-evaluate any surviving `kismet/archive.py` work.

Each sub-cut below is independent; do them in listed order, suite-run after every 3-4.

- [ ] **Step 12.1** property_pointer.py — delete the legacy generic-archive branch in `from_archive` (everything after the `if hasattr(archive, "xfer_field_pointer")` return); verify first that every caller passes `FKismetArchive`: `grep -rn "FKismetPropertyPointer.from_archive" src tests --include="*.py"`. New body:

  ```python
  @classmethod
  def from_archive(cls, archive: FArchive, name_map: list[str]) -> FKismetPropertyPointer:
      # Persistent Kismet Script serialization routes FProperty* through
      # FPropertyProxyArchive, which writes an FFieldPath directly.
      return cls(bNew=True, path=archive.xfer_field_pointer())
  ```

  Drop the now-unused `name_map` parameter only if no caller uses it (keep otherwise).
- [x] **Step 12.2 — canceled 2026-09-10 (Gate K).** `body_builder.py` and its C++ pseudocode call path were deleted as a product change; the proposed equivalent tidy must not be applied.
- [x] **Step 12.3 — canceled 2026-09-10 (Gate K).** `jump_analyzer.py` was deleted with the C++ pseudocode generator chain; no residual analyzer implementation remains to tidy.
- [ ] **Step 12.4** ufunction_reader.py — drop the unused params: `summary` from `_make_control_bit_error` and `_make_offset_mismatch_error`, `declared_start` from the latter, field `remaining_serialized` from `FunctionScriptFailure` (`grep -rn remaining_serialized src tests` first). Then collapse the two near-identical `_make_*_error` builders into one:

  ```python
  def _make_failure(export, export_index, error_code, error_message) -> FunctionScriptFailure:
      return FunctionScriptFailure(
          error_code=error_code, error_message=error_message,
          function_name=export.object_name, export_index=export_index,
          class_name=resolve_class_name(export.class_index, [], [export]) or "Unknown",
          package_offset=export.serial_offset, export_offset=export.serial_offset,
      )
  ```

  and raise `UnsupportedSerializationVersion(_make_failure(export, export_index, "unsupported_serialization_version", f"Unknown serialization-control bits 0x{ctrl_byte:02X} (known: 0x{_SER_CTRL_OVERRIDE_OPERATION:02X})"))` / `InvalidScriptPropertyRange(_make_failure(export, export_index, "invalid_script_property_range", f"Script serialization offset mismatch: declared end={declared_end}, measured end={measured_end}"))` at the two call sites (keep the existing exception classes and the `except (UnsupportedSerializationVersion, InvalidScriptPropertyRange)` catch shape; the catch sites must switch to constructing-and-raising with `_make_failure`).
- [ ] **Step 12.5** translator.py — delete `_build_structured_indices`; in `__init__` use `self._structured_indices = self._jump_analyzer.get_structured_indices()` inside the `if expressions is not None:` block. kismet/archive.py: delete `self.bytecode_buffer_size` (grep-verify: written once, read nowhere: `grep -rn bytecode_buffer_size src tests`).
- [ ] **Step 12.6** expressions Ref fields — delete `ClassPtrRef` (casts.py) + `ObjectRef` and set the site to `return cls(Value=obj_ref.index)` (delegates.py EX_BindDelegate + EX_InstanceDelegate `FunctionNameRef` fields + their assignment lines, keeping whatever read the string value uses), `NameRef` (NameConst), `EventNameRef`, `VirtualFunctionNameRef`, plus any now-dead `FNameRef` imports in those files (`grep -rn "Ref:" src/uasset_read/kismet/expressions/` should end at zero). Before deleting each, `grep -rn "<FieldName>" src tests` to confirm no reader.
- [ ] **Step 12.7** native_fields.py — delete dead `NativeFieldDeclaration` fields `array_dim`, `element_size`, `metadata`, `rep_notify_name`, `replication_condition` and their `decl.*` assignments (~:72-77, 395-402); keep the *reads* inside `_read_fproperty_prefix` (cursor advance). Shrink `_read_fproperty_prefix`'s 9-tuple to `(name, property_flags)` — the other seven values have no consumer after the field delete; adjust the unpack in `_read_single_field` to `name, property_flags = _read_fproperty_prefix(archive, context)`.
- [ ] **Step 12.8** result.py — delete `logic_source` param + `graph_topology` branch from `infer_bytecode_confidence`, and the `logic_source`/`semantic_calls` fields ONLY IF no test/schema gate asserts them (`grep -rn "logic_source\|semantic_calls\|bytecode_confidence" tests src` — if `logic_source` appears in an output-key assertion, keep the field, delete only the param/branch).
- [ ] **Step 12.9** Suite parity, baseline json, commit `refactor: kismet dead branches, write-only fields, single-detect structured blocks`.

---

### Task 13: Parsers micro-cuts batch (~160 lines)

**Files:** Modify `src/uasset_read/parsers/{bulk_data,property_parser,property_types,custom_properties,class_specific_skip,legacy_reader}.py`, `parsers/asset_types/handlers_impl.py`, `parsers/binary_or_native_handlers.py`, `src/uasset_read/agent_tools.py`, `tests/size-baseline.json`

- [ ] **Step 13.1** bulk_data.py — `grep -rn "BULKDATA_" src tests` and keep only the constants actually imported/used (`CompressedZlib`, `CompressedOodle`; `None` only if used). Delete unused params `base_offset`/`export_index` from `extract_bulk_data_descriptors` and update the `agent_tools.py` call. agent_tools.py `extract_payload`: collapse the dead control flow (regex `\d+` makes `int()` unfailable — delete the `try/except ValueError` and the second `if export_index is None` block) to:

  ```python
  if export_index is None:
      import re
      match = re.search(r"\((export|import):(\d+)\)", payload_id)
      if match:
          export_index = int(match.group(2))
  if export_index is None:
      response = {
          "id": payload_id,
          "error": "Payload extraction is deferred: real payloads require per-export BulkData mapping from cooked fixtures (issue #627)",
          "code": PAYLOAD_EXTRACTION_DEFERRED,
          "available_ids": [], "offset": 0, "returned": 0, "total": 0,
      }
      return fit_list_response(response, max_bytes, list_key="available_ids")
  ```

  and drop the `offset` parameter only if `grep -rn "extract_payload(" src tests` shows no caller passing it.
- [ ] **Step 13.2** custom_properties.py — delete `CustomPropertyContext` fields `type_id`, `mappings`, `game`, `summary` (verify no handler reads them: `grep -rn "\.type_id\|ctx\.mappings\|ctx\.game\|ctx\.summary" src`), and the corresponding kwargs at the two `handle_custom_property(...)` call sites in property_parser.py (~:629-638) plus the context construction inside `handle_custom_property`.
- [ ] **Step 13.3** property_types.py —

  ```python
  def _get_inner_type(array_type: str) -> str:
      inner = extract_inner_from_tag(array_type)
      return inner.rsplit(".", 1)[-1] if inner else "Unknown"
  ```

  (`extract_inner_from_tag` already imported in this file; behavior differs only for nested-paren type strings, where the new form is strictly more correct). `parse_float_property` body becomes `return archive.read_f32()` after verifying the dispatcher binds `DoubleProperty` → `parse_double_property` (`grep -n '"DoubleProperty"' src/uasset_read/parsers/property_parser.py`). `_EXPECTED_STRUCT_SIZES`: delete the `"TopLevelAssetPath": None` row and the `| None` from the annotation — verify consumers treat a missing key like a `None` size (`grep -rn "_EXPECTED_STRUCT_SIZES" src`).
- [ ] **Step 13.4** legacy_reader.py — replace `_string_table_has_dev_notes`'s GUID loop and `_FORTNITE_MB_GUID`/`_FORTNITE_ADD_DEV_NOTES` constants with the repo pattern (graph_helpers.py:190 does exactly this):

  ```python
  def _string_table_has_dev_notes(summary: PackageFileSummary) -> bool:
      """True when the editor-saved trailer wrote per-entry DevNotes strings."""
      if summary.package_flags & PKG_FilterEditorOnly:
          return False
      return get_custom_version(summary, FORTNITE_GUID) >= 260
  ```

  Import `FORTNITE_GUID` and `get_custom_version` from `uasset_read.versioning` (legacy_reader.py already imports other symbols from there — extend the existing import).
- [ ] **Step 13.5** class_specific_skip.py — collapse to:

  ```python
  if class_name == "CubeBuilder":
      return False
  object_name = str(export.object_name)
  return object_name.startswith(SKIP_CLASS_PREFIXES) or (class_name or "").startswith(SKIP_CLASS_PREFIXES)
  ```

- [ ] **Step 13.6** handlers_impl.py — convert the seven hand-written `supports()` (`cn in self._X_CLASSES`) at :450, :508, :653, :820, :1266, :1462, :1679 to the existing `_SupportsClasses` mixin: base list `classes = ("...", ...)` (rename the `_X_CLASSES` tuple contents into a `classes` class attribute, delete the `supports` override). One class at a time; suite after each.
- [ ] **Step 13.7** property_parser.py — `data_boundary` 4-branch chain → `data_boundary = min((b for b in (property_end, file_size) if isinstance(b, int)), default=limit)` (verify the read-back semantics: original picks property_end/file_size/limit in exactly that min-without-limit form; do NOT include `limit` in the min when either is present — the `default=limit` covers the both-None case).
- [ ] **Step 13.8** binary_or_native_handlers.py — delete `_decode_vector`, `_decode_rotator`, `_decode_vector2d`, `_decode_vector4`, `_decode_quat`, `_decode_plane` and put the key tuples at the call point in the table:

  ```python
  "Vector": ((12, 24), lambda raw, size: _decode_nd(raw, size, ("X", "Y", "Z"))),
  ```

  (same for Vector3f/Vector3d/Rotator*/Vector2D/Vector2f/Vector2d/DeprecateSlateVector2D/Vector4*/Quat*/Plane*/LinearColor via `("R","G","B","A")`). Keep `_decode_color/_decode_guid/_decode_int_point/_decode_int_vector/_decode_two_vectors/_decode_sphere` (their bodies are not `_decode_nd` forwards).
- [ ] **Step 13.9** Suite parity, baseline json, commit `refactor: parsers dead params, duplicated helpers and wrapper indirection`.

---

### Task 14: Final wave

- [ ] **Step 14.1:** `python -m pytest -q` full suite — must equal or better Task 0 baseline (deleted-case counts drop; zero new failures).
- [ ] **Step 14.2:** Confirm net cut: `git diff --stat dev-0.6.0...HEAD` — report line delta vs the ~5,580 estimate.
- [ ] **Step 14.3:** Re-measure and tighten `tests/size-baseline.json` exactly (also `tests_python`), append the `_note` sentence summarizing the wave.
- [ ] **Step 14.4:** Append a status line to the audit section header in the canonical design doc ONLY if it references cleanup waves (check `docs/designs/2026-08-26-package-first-uasset-parser-refactor.md` for a Migration Completion Gate list with a "size baseline" item; update the gate note if present).
- [ ] **Step 14.5:** Commit `chore: re-measure size baseline after ponytail cleanup wave`.
- [ ] **Step 14.6:** Report to user: lines removed per task, suite parity proof, and the deferred/caveat list below.

---

## Explicitly NOT planned (audit items rejected or deferred)

- `_PROPERTY_ARGS` → ctx-dataclass rework (audit shrink #4/parsers): invasive 25-handler churn for a data table; rejected as worse than the bloat.
- `handlers_impl` `if context.depth == "decode":` unwrap: tests call `run_handlers` with the default `depth="package"`, so the guard is load-bearing there — deleting it would change test-visible behavior.
- `graph_pin.py:209-439` pin-array recovery heuristics: over-built, but removing changes tolerant-parse output = correctness scope. Route to a normal design review, not this plan.
- `cli.py::_sanitize_error_message` 6→2 regex collapse and `iostore` CLI wiring: small/risky; skip unless the user asks.
- `parent_resolver._find_parent_package` repeated `rglob` per depth: performance, out of scope.

## Self-review notes

- Coverage: every audit finding maps to Task 1-13 or to the NOT-planned list.
- Cross-task ordering: Tasks 3 (ArchiveLike/SliceReader) must precede nothing else that touches `package.py` annotations; Task 4 (VersionContext) and Task 1 (handlers_impl untouched) are independent; Tasks 8 and 9 both touch graph_pin — run 8 before 9.
- The `VersionContext` literal in test_core.py:1141/1167 (`H.VersionContext()`) stays valid after Task 4 (single default field).
