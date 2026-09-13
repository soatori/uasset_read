# Ponytail Residual Cuts

> **ARCHIVED (2026-09-26):** Executed closeout / plan-of-record. Historical evidence only — do not re-execute. Binding contracts and the canonical target remain under [`docs/designs/`](../README.md).


> **Status:** current (executed 2026-09-12). Follow-up to the 2026-09-08 whole-repo
> audit waves (Tasks 0–13 already landed). **Do not re-execute completed steps.**
>
> **Scope:** pure subtraction / identity-preserving rewrites. No parse-path behavior
> change except CubeBuilder prefix edges (Task 6), documented below.
>
> **Execution record:** Tasks 1–5 `f55b2d1e`; Task 6 `4bface99`; baseline `e97cb191`.
> Suite parity **220 passed**. Residual risk: CubeBuilder-prefixed non-exact class
> names are no longer force-skipped (intentional).

**Goal:** Delete the remaining write-only fields, identity maps, false circular-import
mirrors, and a dead skip-list entry. Estimated net cut: ~80–120 lines.

**Architecture:** Each task is independent and gated by `python -m pytest -q` parity.
Tasks 1–5 are JSON-output-identical. Task 6 intentionally stops skipping
CubeBuilder-prefixed names that are not exact-class `CubeBuilder`.

**Tech Stack:** Python 3.10+, pytest. Run from repo root: `python -m pytest -q`.

**Spec:** This file. Line numbers track the 2026-09-12 working tree; re-locate by
symbol if the base moves.

## Global Constraints

- Commit format `refactor: <summary>` per task (or one batch commit for Tasks 1–5).
  No push.
- English code/comments.
- `tests/size-baseline.json` `src_python.max_lines` is a ceiling — deletions are fine;
  re-measure and tighten after the wave (Task 7).
- Read-only parser; never introduce writes. Never touch `external/`, `UnrealEngine/`, `dist/`.
- Do **not** re-execute waves already marked done in
  `2026-09-08-ponytail-audit-cleanup-plan.md`.

---

### Task 0: Baseline

**Files:** none (record only)

- [x] **Step 0.1:** Confirm clean tree (or that unrelated WIP is stashed).
- [x] **Step 0.2:** Baseline: `python -m pytest -q` — record pass/fail. Any pre-existing
  failures become the parity gate ("same failures, no new ones").
- [x] **Step 0.3:** Sanity-grep each premise still holds (commands appear in each task).

---

### Task 1: `ETRIGGER_EVENT_PIN_MAP` identity map → frozenset

**Premise (verified 2026-09-12):** The map is `{"Started": "Started", ...}`. Sole
consumer `_build_trigger_events_from_pins` only does membership tests and rewrites
the value as itself. Output JSON is unchanged if the value becomes the key.

**Files:**
- Modify: `src/uasset_read/constants.py` (~:160–168)
- Modify: `src/uasset_read/serializers/graph_node.py` (`_build_trigger_events_from_pins`, ~:172–196)

**Interfaces:** Public name `ETRIGGER_EVENT_PIN_MAP` disappears. No test imports it
(`grep -rn ETRIGGER_EVENT tests` → empty). Wiki/docs do not reference the symbol.

- [x] **Step 1.1:** Verify sole consumer:

  ```bash
  grep -rn "ETRIGGER_EVENT_PIN_MAP" src tests --include="*.py"
  ```

  Expected: `constants.py` definition + `graph_node.py` import/uses only.

- [x] **Step 1.2:** In `constants.py`, replace the dict with:

  ```python
  # EnhancedInput ETriggerEvent pin names (identity: pin name == enum string).
  TRIGGER_EVENT_NAMES = frozenset({"Started", "Triggered", "Completed", "Exited"})
  ```

  (Or keep the symbol private in `graph_node.py` if no other module should own it —
  preferred: move the frozenset next to `_build_trigger_events_from_pins` and delete
  the constants entry entirely, since nothing else needs it.)

- [x] **Step 1.3:** Rewrite `_build_trigger_events_from_pins` body:

  ```python
  def _build_trigger_events_from_pins(pins: list[UEdGraphPin]) -> dict[str, str]:
      """Map EnhancedInputAction trigger pin names onto themselves (ETriggerEvent strings)."""
      trigger_events = {}
      for pin in pins:
          pin_type = pin.pin_type
          pin_category = pin_type.pin_category if pin_type else ""
          pin_name = pin.pin_name or ""
          is_exec_output = pin_category == "exec" and pin.direction == 1
          name = pin_name if pin_name in TRIGGER_EVENT_NAMES else (
              pin_category if pin_category in TRIGGER_EVENT_NAMES else None
          )
          if is_exec_output or name is not None:
              if name is not None:
                  trigger_events[name] = name
      return trigger_events
  ```

  Behavior notes:
  - Old code set `trigger_events[name] = ETRIGGER_EVENT_PIN_MAP[name]` (== name). New
    form is identical.
  - Old code, when `is_exec_output` and neither name nor category matched the map,
    produced no key (the inner `if trigger_name in MAP` failed). New form preserves
    that.
  - Prefer keeping the frozenset **in graph_node.py** (module-level) and deleting
    the constants entry — constants.py should not hold one-callsite UI tables.

- [x] **Step 1.4:** Suite parity. Commit:
  `refactor: replace identity ETRIGGER_EVENT_PIN_MAP with a frozenset of names`

---

### Task 2: Delete false circular-import PKG mirrors in native_fields

**Premise (verified 2026-09-12):** `kismet/native_fields.py:26-27` redefines
`PKG_Cooked` / `PKG_FilterEditorOnly` with comment "mirrored from constants.py to
avoid circular import". `constants.py` imports only `uuid` — no kismet import, no
cycle.

**Files:**
- Modify: `src/uasset_read/kismet/native_fields.py` (lines 23–27)

**Interfaces:** unchanged.

- [x] **Step 2.1:** Verify no cycle:

  ```bash
  grep -n "^import\|^from" src/uasset_read/constants.py
  grep -n "PKG_Cooked\|PKG_FilterEditorOnly" src/uasset_read/kismet/native_fields.py
  ```

- [x] **Step 2.2:** Delete the local constants and the "mirrored" comment block. Add:

  ```python
  from uasset_read.constants import PKG_Cooked, PKG_FilterEditorOnly
  ```

  next to the existing `uasset_read.archive` import. Leave the `_FFIELD_*` version
  thresholds in place (those are legitimately local).

- [x] **Step 2.3:** Suite parity. Commit:
  `refactor: import package-flag constants instead of mirroring them in native_fields`

---

### Task 3: Delete write-only `UEdGraphPin.default_object_ref`

**Premise (verified 2026-09-12):** Field exists at `models/core.py:62-64` with comment
"D-04: reserved for object-reference resolution (unused on the single-package path)".
`grep -rn default_object_ref src tests` → only the dataclass field. Task 8 of the
2026-09-08 plan already removed the matching pin-payload key; the dataclass field
was left behind.

**Files:**
- Modify: `src/uasset_read/models/core.py`

**Interfaces:** dataclass field removed. No constructor call sites pass it
(dataclass default). JSON projection of pins does not include this field (Task 8
already dropped it from payloads).

- [x] **Step 3.1:** Re-verify zero readers/writers:

  ```bash
  grep -rn "default_object_ref" src tests --include="*.py"
  ```

  Expected: one hit in `models/core.py`.

- [x] **Step 3.2:** Delete the field and its two-line comment. Keep `default_object`
  (the real int index field) untouched.

- [x] **Step 3.3:** Suite parity. Commit:
  `refactor: delete write-only UEdGraphPin.default_object_ref field`

---

### Task 4: Delete write-only `is_event` key in K2Node_Event node_data

**Premise (verified 2026-09-12):** `graph_node.py:146` returns `"is_event": True` from
`read_k2node_event`. `grep -rn '"is_event"\|is_event' src tests` → only that line.
No consumer, no schema assertion.

**Files:**
- Modify: `src/uasset_read/serializers/graph_node.py` (`read_k2node_event` return dict)

**Interfaces:** `node_data` for `K2Node_Event` loses the key `"is_event"`. Callers
(`_handle_event` → generic node assembly) treat `node_data` as a free dict.

- [x] **Step 4.1:**

  ```bash
  grep -rn "is_event" src tests --include="*.py"
  ```

  Expected: single hit at graph_node.py:146.

- [x] **Step 4.2:** Delete `"is_event": True,` from the return dict.

- [x] **Step 4.3:** Suite parity. Commit:
  `refactor: drop never-read is_event key from K2Node_Event node_data`

---

### Task 5: Drop unused `name_map` from `FKismetPropertyPointer.from_archive`

**Premise (verified 2026-09-12):** Task 12.1 of the 2026-09-08 plan already deleted the
legacy generic-archive branch. The method body is now only:

```python
return cls(bNew=True, path=archive.xfer_field_pointer())
```

`name_map` is unused. Callers (11 sites under `kismet/expressions/`) still pass it.
The expression `from_archive(archive, name_map)` **dispatch protocol stays** —
`kismet/archive.py:79` calls `expr_class.from_archive(self, self._name_map)`, and
many expression bodies legitimately use `name_map` for FNames. Only the
`FKismetPropertyPointer` call drops the second argument.

**Files:**
- Modify: `src/uasset_read/kismet/property_pointer.py`
- Modify (call sites only): `expressions/{variables,structs,context,containers,assignments}.py`

**Interfaces:** `FKismetPropertyPointer.from_archive(archive)` — one argument.
Expression classmethods keep their two-arg signature.

- [x] **Step 5.1:** Enumerate call sites:

  ```bash
  grep -rn "FKismetPropertyPointer.from_archive" src tests --include="*.py"
  ```

  Expected: 11 hits, all `from_archive(archive, name_map)`.

- [x] **Step 5.2:** In `property_pointer.py`:

  ```python
  @classmethod
  def from_archive(cls, archive: FArchive) -> FKismetPropertyPointer:
      """Deserialize FKismetPropertyPointer from FArchive.

      Persistent Kismet Script serialization routes FProperty* through
      FPropertyProxyArchive, which writes an FFieldPath directly.
      """
      return cls(bNew=True, path=archive.xfer_field_pointer())
  ```

- [x] **Step 5.3:** Mechanically change every call site to
  `FKismetPropertyPointer.from_archive(archive)`. Leave the enclosing expression
  `from_archive(cls, archive, name_map)` signatures alone (dispatch protocol). Unused
  `name_map` params on expression methods that only forwarded it are acceptable —
  the same pattern already exists in `make_value_expression` (`expressions/base.py:98`).

- [x] **Step 5.4:** Suite parity (kismet expression tests in `test_core.py`,
  sample decode paths). Commit:
  `refactor: drop unused name_map from FKismetPropertyPointer.from_archive`

---

### Task 6: CubeBuilder skip-list / allowlist contradiction

**Premise (verified 2026-09-12):** `class_specific_skip.py` contains both:

1. `"CubeBuilder"` inside `SKIP_CLASS_PREFIXES` (line 23)
2. `if class_name == "CubeBuilder": return False` allowlist (lines 68–70, #521)

The allowlist runs first, so the exact-class path never consults the prefix entry.
The prefix entry is only live for:
- `object_name` starting with `"CubeBuilder"` when `class_name` is **not** exactly
  `"CubeBuilder"`
- `class_name` starting with `"CubeBuilder"` but not equal (e.g. hypothetical
  `CubeBuilderFoo`)

Both edges are speculative; #521's intent is "do not skip CubeBuilder". Removing the
list entry makes the allowlist unnecessary.

**Intentional behavior change:** exports whose object or class name merely *starts
with* `CubeBuilder` but whose class is not an exact skip-prefix match will no longer
be force-skipped. Exact `CubeBuilder` class was already allowlisted. Remaining skip
prefixes (`GeomModifier_`, `Niagara*`, …) are unchanged.

**Files:**
- Modify: `src/uasset_read/parsers/class_specific_skip.py`
- Note: `tests/test_handler_capability_ledger.py` lists `"CubeBuilder"` under
  `FALLBACK_CLASSES` (handler registry, **not** skip list) — do not touch.

**Interfaces:** `SKIP_CLASS_PREFIXES` loses one entry; `should_skip_export_for_tolerant_parsing`
signature unchanged.

- [x] **Step 6.1:** Confirm sole skip-list consumer:

  ```bash
  grep -rn "SKIP_CLASS_PREFIXES\|should_skip_export_for_tolerant_parsing" src tests --include="*.py"
  ```

  Expected: definition + `property_parser.py` call site.

- [x] **Step 6.2:** Delete `"CubeBuilder",` from the tuple (keep the surrounding
  category comments that still apply to other prefixes; drop the P0 Builder line if
  only CubeBuilder was under it — keep `GeomModifier_` / `BrushBuilder`).

- [x] **Step 6.3:** Delete the allowlist branch and the `# #521` comment. Collapse:

  ```python
  def should_skip_export_for_tolerant_parsing(
      export: ObjectExport,
      class_name: str | None = None,
  ) -> bool:
      """True when the export should bypass the generic property parser."""
      return str(export.object_name).startswith(SKIP_CLASS_PREFIXES) or (
          class_name or ""
      ).startswith(SKIP_CLASS_PREFIXES)
  ```

  Trim the long docstring to the one-liner above.

- [x] **Step 6.4:** Suite parity. If any sample test asserts CubeBuilder is skipped,
  STOP and report — that would mean a real fixture depends on the dead prefix edge.

- [x] **Step 6.5:** Commit:
  `refactor: remove CubeBuilder from skip prefixes — exact class already allowlisted (#521)`

---

### Task 7: Baseline re-measure + report

- [x] **Step 7.1:** `python -m pytest -q` — parity with Task 0.
- [x] **Step 7.2:** Re-measure src line count and tighten `tests/size-baseline.json`
  `src_python.max_lines` to the exact value; append one `_note` sentence.
- [x] **Step 7.3:** Report: lines removed per task, suite parity proof.

---

## Explicitly NOT planned

- `_recover_pin_array_count` (graph_pin.py ~:212–340): over-built confidence/window
  heuristics, but removing them changes tolerant-parse output. Separate design.
- `cli._sanitize_error_message` 6-regex collapse: small, security-adjacent. Leave.
- Lazy-import wrappers in `property_types.py` (`_get_parse_property_value` family):
  real cycle; wrappers are already one-liners. No win.
- Expression `from_archive` dispatch protocol: leave the two-arg signature.
- `handlers_impl` further splitting: domain-driven size, not bloat.

## Self-review notes

- Tasks 1–5 are independent and JSON-identical; safe to batch as one commit if
  preferred, but one-task-one-commit keeps blame clean.
- Task 6 is the only intentional behavior change; isolate it.
- Task 5 must not "simplify" expression method signatures — only the
  `FKismetPropertyPointer` call.
- CubeBuilder in `test_handler_capability_ledger.FALLBACK_CLASSES` is about the
  handler registry, not this skip list. Do not remove it there.
