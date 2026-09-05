# v1 Residue Cuts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete the v1 pipeline residue that the package-first (v2) migration left unreachable at runtime, without changing any v2 output.

**Architecture:** Pure deletion + data-shrinking pass. The v2 path (`__init__` → `v2/api` → `v2/package/legacy` → `v2/handlers` → `v2/projection`) is the only production path; everything proven unreachable from it is removed, and two dynamic dispatch tables are converted from code to data. No new modules, no new abstractions, no new dependencies.

**Tech Stack:** Python 3.10+ stdlib only (repo is zero-runtime-dependency), pytest, ruff, pyright.

**Spec:** `temp/ponytail-audit-final.md` (ranked cuts A1–A19) and `temp/v2-migration-audit.md` (migration verdict + marker inventory). Both are gitignored investigation output, so the load-bearing numbers are restated in this plan; the audit is the *why*, this plan is the *how*.

**Plan location note:** the writing-plans default `docs/superpowers/plans/` is rejected by this repo's CI directory-compliance job (`.github/workflows/ci.yml` forbids `^docs/superpowers/` and `^temp/` on master). Plans live in `docs/plans/`, matching the four existing plans.

---

## Verified Baseline (measured on `f2fa0f61` + external `5e0ae958`, Windows / Python 3.14)

Run these three commands before Task 1 and record the output in your working notes. Every task must return the tree to these states.

```bash
python -m pytest -q                      # expect: 110 passed
python -m ruff check src/uasset_read tests   # expect: All checks passed!
python -m pyright src/uasset_read        # expect: 0 errors (psutil warnings are expected; psutil is not installed)
python -c "import uasset_read; print(sorted(uasset_read.__all__))"   # expect: 10 public names
PYTHONPATH=src python -m uasset_read tests/samples/ABP_RifleAnimLayers.uasset --depth package > temp/baseline-cli.json   # smoke artefact
```

`src/` = 116 files / 34,754 physical lines / 22,527 logic lines (`git ls-files src` = 117 including `py.typed`). Target net after Task 10: about **-5,600 to -6,300 lines**, 14 files removed, 0 new dependencies, v2 output byte-identical.

## Global Constraints (bind every task)

- Python 3.10+, stdlib only in `src/`. `brotli`/`zstandard` stay optional extras; nothing else may be added.
- **No new test files and no new top-level test functions.** `tests/test_core.py::test_test_suite_structure_gate` (lines 2658–2682) asserts exactly the four files `test_blueprint_decode.py`, `test_blueprint_graph.py`, `test_core.py`, `test_samples.py`, exactly **10** top-level `test_*` functions in `test_core.py`, no top-level classes, no decorators on `test_*`, and that `tests/` contains only the `samples` subdirectory. Deleting a nested `_run_cases` entry or an inner function is allowed; deleting a top-level `test_*` function is not.
- v2 output must not change. `docs/designs/contract/package_document_v2.schema.json` locks the envelope; `tests/test_core.py:2429` asserts `format_version` is required; `projection.py:235` emits `"format_version": "2.0"`. Never rename that field.
- `legacy` in `v2/package/legacy.py`, `serializers/property_tags.py:33,40,277` and `v2/version.py:42,68` means the **UE legacy package layout**, not v1 code. `v2`/`"V2"` at `parsers/binary_or_native_handlers.py:330-333` is an **FVector2D**. Never sweep these.
- The 11 asset-type parser modules listed in `_optional` are loaded by `__import__` at `asset_types/__init__.py:330`, so static reachability does not see them. They are **live** — including `anim_common.py` and `movie_scene_control_rig.py`. Do not delete any of them.
- `cli.py:255-261` (retired `--legacy-json/--markdown/--list-formats/--diff/--batch` error) is a live user contract: those flags shipped in tags `v0.4.4 … v0.5.4.45`. Keep it.
- One commit per task, message `refactor: <what was deleted>`. Never mix a cut task with behaviour changes.
- Do not touch `external/`, `wiki/` (submodule), or `docs/designs/**` prose; the only allowed doc edits are those named in Task 10.
- Preserve unrelated work: the tree is dirty at plan time (`.claude/rules/constraints.md`, `.github/workflows/ci.yml`, `docs/designs/2026-09-02-peer-corroboration-usage-scheme.md`, `docs/reference/external-peer-inventory.md`). In every commit step below, `git add -A <paths>` is path-scoped on purpose — never run bare `git add -A` or `git add .`.

## Explicitly Out Of Scope (needs a decision, not a deletion)

| Item | Why deferred |
| --- | --- |
| `v2/agent_tools.py` (196L) + its test at `test_core.py:2487` | Reachable only from tests, but `docs/designs/2026-08-31-agent-doc-cache-contract.md` reserves the six-tool contract. Deleting it is a product decision (#621 follow-up), not a cleanup. |
| `v2/payloads.py` (15L) | README:9 advertises it as the stable deferred interface (`PAYLOAD_EXTRACTION_DEFERRED`). |
| Whole `kismet/` package retirement (7,458L) | Deprecated in docs but **live**: `v2/package/legacy.py:963` imports `decompile_bridge` at runtime. Tracked in #642. |
| Renaming package `uasset_read/v2/`, flattening directories, renaming `package_document_v2.schema.json` | Import-path and doc-link churn; the marker inventory in `temp/v2-migration-audit.md` records it for a separate design decision. |
| Moving/archiving the 9,387 lines in `docs/plans/` + `docs/superpowers/plans/` | Repo owns that process (design-status index in `docs/designs/README.md`). |

---

## Execution Lanes (parallel dispatch)

The 10 tasks are one refactor chain, but they split into four **file-disjoint** writer lanes plus a serial tail. Verified facts that make this safe:

- The v1 subsystems being deleted have **zero test coverage**: `grep -rn "uasset_read\.graph|flow_builder|macro_expander|chain_builder|graph_utils|extract_blueprint_graphs|_validate_graph_export_offset|uasset_read\.link|PackageLinker|class_serialization_strategy|kismet\.semantic|models\.ir|models\.blueprint|models\.transforms|project_logging|configure_logging|decode_package_flags|_EXPRESSION_TYPE_PATTERNS|classify_expression_type|MATERIAL_DOMAIN_MAP|LIGHTWEIGHT_TOLERANT|CONTROL_RIG_LARGE|ResourceBudget|hex_view|MAX_REASONABLE_CAP" tests/` → no hits. Lanes A/B/D therefore make **no** `test_core.py` edits.
- `tests/` is exactly 4 files, `test_core.py` exactly 10 top-level mega-tests, no classes; suite runtime ~45s. The `test_v2_*.py` files named in early drafts no longer exist.
- Only two nested `test_*` defs constrain deletions, and they are **adjacent** (`test_import_package_name_not_gated_by_filter_editor_only` :721 reads `object_resources.py` text; `test_asset_registry_dependency_gate_uses_521` :725 reads `asset_registry_parser.py` text). Tasks 5 and 7 must therefore share a lane, or two agents rewrite the same `_run_cases` region.
- `constants.UE4_ASSETREGISTRY_DEPENDENCYFLAGS` has exactly two consumers (the parser and that nested test) → it leaves in Task 7, lane A only.
- `test_class_handlers_kwarg_defaults_true_for_v1` (:1264) pins `parse_properties_from_export(run_class_handlers=True)` — Task 3 strips `linker` from that signature but must not touch `run_class_handlers`.

| Lane | Tasks | Owned paths (exclusive; touch nothing else) |
| --- | --- | --- |
| **A** | 1, 2, 3, 5, 7 | `src/uasset_read/graph/`, `src/uasset_read/link/`, `kismet/semantic.py` **and `kismet/{decompile_bridge,body_builder,translator,function_resolver}.py`** — the latter four are Task 3's `linker=`/`TYPE_CHECKING` plumbing (each does `from uasset_read.link.linker import PackageLinker`, so deleting `link/` without them leaves pyright unresolved imports; verified no other lane owns any `kismet/` path), `parsers/class_serialization_strategy.py`, `parsers/asset_registry_parser.py`, `parsers/property_parser.py`, `parsers/asset_types/niagara_node.py`, all of `serializers/`, `models/core.py`, `models/diagnostics.py`, `models/object.py`, `v2/blueprint_graph.py`, `v2/package/legacy.py`, `constants.py` (`UE4_ASSETREGISTRY_DEPENDENCYFLAGS` only), `tests/test_core.py` (the two nested defs + their `_run_cases` entries) |
| **B** | 4 | `models/ir.py`, `models/blueprint.py`, `models/transforms.py`, `models/__init__.py`, `parsers/asset_types/anim_blueprint.py`, `anim_common.py`, `anim_montage.py`, `anim_sequence.py` |
| **C** | 6 | `parsers/asset_types/__init__.py`, `parsers/asset_types/material_instance.py` — no `tests/` edits at all; correctness is proven by the Step 5 handler-name golden diff. **`parsers/class_handler.py` does not exist** (earlier draft error): `AssetTypeHandler` and its `inspect.signature` probe are defined in `asset_types/__init__.py` itself, so Step 4 lands there. |
| **D** | 8, 9 | `project_logging.py`, `cli.py`, `config.py`, `__main__.py`, `exceptions.py`, `src/uasset_read/__init__.py`, `constants.py` (the 13 dead names, ≥1,000 lines from lane A's single hunk), `memory_safety.py`, `debug.py`, `package.py`, `mappings.py` |
| tail | 10 | `v2/*`, `README.md`, `wiki/`, the 18 empty directories, test duplication convergence — runs alone, after A–D merge |

Merge order **A → B → C → D**, full suite after each merge. Lane A is the largest but is internally sequential (Task 1 must precede 2 and 3, which precede 5 and 7).

---

## Wave 1 Outcome (executed 2026-09-05, merged at `43c3ce97`)

Lanes A → B → C → D merged with no conflicts except a clean auto-merge in `constants.py` (lane A's 521-constant hunk and lane D's 11-name hunk are far apart). Gate state after **each** merge: `110 passed`, `ruff` All checks passed, `pyright` **0 errors / 0 warnings** (the 3 psutil warnings disappeared with the memory monitor), `--depth package` output byte-identical to the pre-wave baseline.

- `src/`: 116 → **100** `.py` files, 34,754 → **28,022** physical lines (**-6,732**, better than the -5,600..-6,300 estimate).
- 16 files deleted: `graph/`×6, `link/`×3, `kismet/semantic.py`, `parsers/class_serialization_strategy.py`, `parsers/asset_registry_parser.py`, `models/{ir,blueprint,transforms}.py`, `parsers/asset_types/material_instance.py`.
- `parse_package_document` / CLI / JSON output unchanged; `uasset_read.__all__` 10 → **5**.
- Independent parity re-check for Task 6: handler count identical at base and merged (70 handlers / 70 names), `find_handler()` resolution preserved.

**Accepted deviations (the plan was wrong in 4 places, lanes were right):**

1. **Task 5 Step 3 not executed.** `read_ftext_with_history` (77L, 2 callers), `_read_pin_fstring_field` (3 callers) and `_read_pin_ftext_field` (2 callers) are *not* single-use wrappers; inlining would have added ~150 lines and forked three safety mechanisms across call sites. Step 2's 6 genuinely zero-caller functions (-137L) landed.
2. **Task 9 Step 3 (`mappings._BytesReader` → `struct.unpack_from`) and the `_sanitize_error_message` → `os.path.basename` swap not executed.** Both are behaviour-preserving *rewrites*, not deletions: `_BytesReader` is a bounds-checked cursor threaded through 20 call sites in 5 parsers, and the sanitizer strips absolute Windows/UNC/POSIX paths embedded in error prose at 3 stderr sites with zero test coverage — `basename` cannot do that, so the swap risks path leakage. They belong to the A16/A17 rewrite plan.
3. **Task 3 needed 3 test edits the plan predicted would not exist**, because `tests/test_core.py:1886/1907/1912` passed the dead `linker` argument **positionally as a bare `None`**. Generalizable: grepping tests for a parameter *name* under-detects arity coupling — for any future "no test impact" claim, also check positional `None`/literal arguments at call sites.
4. **Task 6 uses one interleaved 55-row table, not the plan's two-block append shape**, because `ClassHandlerRegistry` is order-sensitive (`find_handler()` returns the first match) and reordering rows would silently change dispatch priority. Keep the interleaved shape in any follow-up.

**New finding, raises Task 10's empty-directory step from cosmetic to correctness:** the 18 empty directories under `src/uasset_read/` are still *importable as implicit namespace packages* — after merging lane A, `importlib.import_module("uasset_read.graph")` succeeded even though every `graph/*.py` was deleted. `git rm` removes tracked files, not the physical directory, so a deleted subsystem keeps resolving as an empty namespace package until the directory itself goes. Task 10 must remove them and then re-run the import probe above for all 16 deleted module paths.

**Open decisions created by wave 1 (not deletions — they need a call):**

| Item | State | Decision needed |
|---|---|---|
| `kismet/function_resolver.py` (188L) | now constructed nowhere: stripping `linker` from `KismetTranslator` left `_func_resolver` permanently `None`; its 5 guards are inert, kept type-clean to avoid cascading into `line_cpp` | fold into the whole-`kismet/` retirement decision, or delete with a `line_cpp` behaviour test first |
| `models/memory_safety.ResourceLimits` | orphaned by lane D's own commit (its sole consumer `MemoryPolicy` is gone) | keep as bounded-read vocabulary, or delete in Task 10 |
| 5 inert CLI flags `--log-level`, `--log-cleanup`, `--log-max-bytes`, `--log-backup-count`, `--log-format` | parsed into `LogConfig`, read by nobody; already inert before this wave | retire into the `cli.py:255-261` retired-flag error, or re-wire them to a real CLI logging path |
| `wiki/07-Dev-Guide/Public-API.md` | lists 5 now-deleted public names; `wiki/` is a gitignored nested repo | run `openwiki code --update` after Task 10 |

---

### Task 1: Delete the v1 graph-analysis package

**Files:**

- Modify: `src/uasset_read/v2/blueprint_graph.py:64` (import site) and add one private helper near `_is_graph_class` (~line 34)
- Delete: `src/uasset_read/graph/__init__.py` (38L), `chain_builder.py` (198L), `flow_builder.py` (1406L), `graph_utils.py` (464L), `macro_expander.py` (576L)
- Delete: `src/uasset_read/graph/parser.py` (162L) **after** its one live symbol is relocated
- Test: `tests/test_blueprint_graph.py` (must keep passing unchanged)

**Interfaces:**

- Consumes: nothing.
- Produces: `uasset_read.graph` no longer exists. `v2/blueprint_graph.read_blueprint_graphs(archive, summary, name_map, import_map, export_map)` keeps its exact signature. The relocated helper is private to that module: `_validate_graph_export_offset(export, archive_size: int) -> bool`.

**Why this is a deletion and not a refactor:** the only thing v2 consumes from `uasset_read.graph` is one 25-line private validator (`v2/blueprint_graph.py:64` imports `_validate_graph_export_offset`, used at `:84`). `extract_blueprint_graphs` is imported only by `graph/__init__.py:6,25`, and `graph/__init__.py`'s other exports (`build_execution_flow_entries`, `format_graphs_json`, `build_function_graphs`) have exactly two consumers: `graph/__init__.py` itself and `kismet/semantic.py:118,171,287,419` — which Task 2 deletes. No test imports `uasset_read.graph` (verified: `grep -rn "uasset_read\.graph" tests/` → 0 hits).

- [ ] **Step 1: Prove the claim before deleting**

```bash
cd /e/Develop/uasset_read
grep -rn "uasset_read\.graph\|from \.graph import\|from \.\.graph import" src tests | grep -v "^src/uasset_read/graph/"
```

Expected — exactly three lines: `src/uasset_read/v2/blueprint_graph.py:64` (the validator import), `src/uasset_read/kismet/semantic.py:118` and its siblings. If any *other* file appears, STOP and report; the cut is stale.

- [ ] **Step 2: Move the surviving validator into its only consumer**

Copy `_validate_graph_export_offset` verbatim from `src/uasset_read/graph/parser.py:37-77` into `src/uasset_read/v2/blueprint_graph.py`, placed immediately above the `_is_graph_class` helper, and delete the import at line 64. The function is complete as-is — it touches only `export.serial_offset`, `export.serial_size`, `export.object_name` and the module logger; `logger` already exists in `blueprint_graph.py`:

```python
def _validate_graph_export_offset(export, archive_size: int) -> bool:
    """Validate whether a graph export's serialization offset is within valid range.

    When serial_offset is 0 and serial_size > 0, the offset is abnormal (non-Default__ export).
    When serial_offset + serial_size exceeds archive boundary, data is truncated.
    """
    serial_offset = getattr(export, "serial_offset", 0)
    serial_size = getattr(export, "serial_size", 0)
    if serial_size == 0:
        return True
    if serial_offset < 0 or serial_size < 0:
        logger.warning("Graph export '%s' offset abnormal: offset=%d, size=%d",
                       export.object_name, serial_offset, serial_size)
        return False
    if serial_offset == 0 and not str(getattr(export, "object_name", "")).startswith("Default__"):
        logger.warning("Graph export '%s' serial_offset=0 and serial_size=%d, offset abnormal",
                       export.object_name, serial_size)
        return False
    if archive_size > 0 and serial_offset + serial_size > archive_size:
        logger.warning("Graph export '%s' offset out of bounds: offset=%d + size=%d > archive_size=%d",
                       export.object_name, serial_offset, serial_size, archive_size)
        return False
    return True
```

Compare against the original before committing: the only intentional difference is dropping the `Args/Returns` doc block; every branch and log message stays byte-identical.

- [ ] **Step 3: Delete the package**

```bash
cd /e/Develop/uasset_read
git rm -r src/uasset_read/graph
```

- [ ] **Step 4: Verify nothing broke**

```bash
python -m pytest -q
python -m ruff check src/uasset_read tests
python -m pyright src/uasset_read
PYTHONPATH=src python -m uasset_read tests/samples/ABP_RifleAnimLayers.uasset --depth package > temp/after-task1-cli.json
python - <<'PY'
import json
a=json.load(open('temp/baseline-cli.json',encoding='utf-8'))
b=json.load(open('temp/after-task1-cli.json',encoding='utf-8'))
assert a==b, 'v2 output changed'
print('v2 output identical')
PY
```

Expected: `110 passed`, ruff clean, pyright 0 errors, output identical. `test_blueprint_graph.py` exercises the relocated validator through `read_blueprint_graphs`, so it is the real proof.

**Known gate exception (measured on lane A at `c8b72909`):** the pyright gate cannot be 0-errors at the end of Task 1. `kismet/semantic.py` holds dead lazy imports into `uasset_read.graph`, so deleting the package leaves 8 unresolved-import errors until Task 2 deletes that file. Either land Task 2 **before** Task 1 (preferred: `semantic.py` has no importers, so removing it first leaves no dangling reference and every commit is green), or keep the two commits adjacent and treat the pair as the atomic unit — never cherry-pick Task 1 alone onto a branch that CI tests. The pair's combined end state must still show `110 passed` + pyright 0.

- [ ] **Step 5: Commit**

```bash
git add -A src/uasset_read/v2/blueprint_graph.py src/uasset_read/graph
git commit -m "refactor: delete the v1 graph-analysis package, relocate its one live validator"
```

---

### Task 2: Delete `kismet/semantic.py`

**Files:**

- Delete: `src/uasset_read/kismet/semantic.py` (524L)
- Modify: `src/uasset_read/graph/…` — gone in Task 1; also fix the two comments that reference it: `src/uasset_read/v2/package/legacy.py` (any `semantic.py` mention) — verify with the grep in Step 1

**Interfaces:**

- Consumes: Task 1 (so `uasset_read.graph` is already absent). **Ordering is not actually load-bearing in that direction**: `semantic.py` has zero importers, so running Task 2 *first* is strictly better — it removes the only dangling reference to `graph/` before the package disappears, and then both commits pass the pyright gate individually. If Task 1 landed first, this task is what turns pyright green again (see Task 1 Step 4's gate exception).
- Produces: nothing new. `enrich_decompiled_functions` and its helpers had zero callers.

- [ ] **Step 1: Prove it is dead**

```bash
cd /e/Develop/uasset_read
grep -rn "semantic import\|semantic\.\(enrich\|build\)\|from \.semantic\|kismet\.semantic\|kismet import semantic" src tests || echo NO-IMPORTER
```

Expected: `NO-IMPORTER`, or comment/doc-only lines. If any live `import` or call remains, STOP.

- [ ] **Step 2: Delete**

```bash
git rm src/uasset_read/kismet/semantic.py
```

- [ ] **Step 3: Verify**

```bash
python -m pytest -q && python -m ruff check src/uasset_read tests && python -m pyright src/uasset_read
```

Expected: `110 passed`, ruff clean, pyright 0 errors.

- [ ] **Step 4: Commit**

```bash
git add src/uasset_read/kismet
git commit -m "refactor: delete kismet/semantic.py, the last v1 graph-enrichment layer"
```

---

### Task 3: Delete `link/` and the `linker=` plumbing

**Files:**

- Delete: `src/uasset_read/link/__init__.py` (10L), `linker.py` (462L), `object_instance.py` (127L)
- Delete: `src/uasset_read/parsers/class_serialization_strategy.py` (178L) — its only importer is `link/linker.py:282`
- Modify (remove `linker` parameters, `*_with_linker` variants and the dead `TYPE_CHECKING` imports) — verified list, `grep -rl linker src/uasset_read --include="*.py" | grep -v "^src/uasset_read/\(graph\|link\)/"` returns exactly these 16: `serializers/graph_node.py`, `serializers/graph_helpers.py`, `serializers/graph_pin.py`, `serializers/graph.py`, `serializers/object_resources.py`, `parsers/property_parser.py`, `parsers/asset_types/niagara_node.py`, `kismet/body_builder.py`, `kismet/decompile_bridge.py`, `kismet/function_resolver.py`, `kismet/translator.py`, `models/core.py` (comment only), `models/diagnostics.py`, `v2/blueprint_graph.py` (one `None,  # linker not needed` positional slot at :96), `v2/package/legacy.py` (`linker=None` at :973), plus the deleted `parsers/class_serialization_strategy.py`
- Test: **none required** — verified `grep -rn "linker\|PackageLinker\|uasset_read.link\|class_serialization_strategy" tests/` returns zero hits. If the suite goes red after this task, that is tree drift: stop and report it rather than editing tests.

**Interfaces:**

- Consumes: Task 1 removes `graph/parser.py:14`'s `TYPE_CHECKING` linker import site automatically.
- Produces: every signature that took `linker=` now takes one fewer argument. Concretely: `FunctionBodyBuilder(linker=None)` → `FunctionBodyBuilder()`; `KismetTranslator(linker=..., expressions=...)` → `KismetTranslator(expressions=...)`; `extract_kismet_decompiled(..., linker=None)` → no `linker` kwarg. `parse_properties_from_export(..., linker=...)` → no `linker` kwarg.

**Why:** every `PackageLinker` mention outside `link/` is a quoted annotation inside `if TYPE_CHECKING:` (12 files), and the single real call site passes `linker=None` (`v2/package/legacy.py:973`). So the linker is not used by the shipping path at all.

- [ ] **Step 1: Confirm no runtime importer**

```bash
cd /e/Develop/uasset_read
grep -rn "PackageLinker" src | grep -v "^src/uasset_read/link/" | grep -v "TYPE_CHECKING" | grep -v ': *#' || echo ALL-UNDER-TYPE-CHECKING
```

Expected: `ALL-UNDER-TYPE-CHECKING` (only `if TYPE_CHECKING:` blocks and `Optional["PackageLinker"]` annotations remain). Then confirm the sole instantiation:

```bash
grep -rn "linker=None\|linker=self" src | grep -v "^src/uasset_read/link/"
```

Expected: one line, `src/uasset_read/v2/package/legacy.py:973: linker=None,`.

- [ ] **Step 2: Delete the two modules**

```bash
git rm -r src/uasset_read/link src/uasset_read/parsers/class_serialization_strategy.py
```

- [ ] **Step 3: Strip the plumbing, file by file**

In each file listed under **Files:** delete the `linker` parameter from the signature, delete the `if linker is not None:` branch and keep the linker-free branch, delete `*_with_linker` function definitions, and delete the now-empty `from uasset_read.link.linker import PackageLinker` line inside `if TYPE_CHECKING:` blocks. In `v2/blueprint_graph.py:96` delete the `None,  # linker not needed for single-package resolution` positional argument and the matching parameter in the callee (do not leave a bare `None` hole). Do not reformat anything else. Work through the files in this order so each edit leaves the tree importable: `serializers/object_resources.py` → `serializers/graph.py` → `serializers/graph_pin.py` → `serializers/graph_node.py` → `serializers/graph_helpers.py` → `parsers/property_parser.py` → `parsers/asset_types/niagara_node.py` → `models/diagnostics.py` → `models/core.py` → `kismet/function_resolver.py` → `kismet/translator.py` → `kismet/body_builder.py` → `kismet/decompile_bridge.py` → `v2/blueprint_graph.py` → `v2/package/legacy.py`.

After each file, run the import smoke so a missed call site surfaces immediately:

```bash
python -c "import uasset_read, uasset_read.v2.package.legacy, uasset_read.kismet.decompile_bridge; print('ok')"
```

Expected: `ok`.

- [ ] **Step 4: Prove no residue**

```bash
grep -rn "linker" src/uasset_read | grep -v "linker-free\|# " || echo CLEAN
```

Expected: `CLEAN` apart from prose comments. Then:

```bash
python -m pytest -q && python -m ruff check src/uasset_read tests && python -m pyright src/uasset_read
PYTHONPATH=src python -m uasset_read tests/samples/ABP_RifleAnimLayers.uasset --depth package > temp/after-task3-cli.json
python -c "import json;a=json.load(open('temp/baseline-cli.json',encoding='utf-8'));b=json.load(open('temp/after-task3-cli.json',encoding='utf-8'));assert a==b;print('identical')"
```

Expected: `110 passed`, ruff clean, pyright 0 errors, `identical`.

- [ ] **Step 5: Commit**

```bash
git add -A src/uasset_read tests
git commit -m "refactor: delete link/ and the linker= plumbing that no live path used"
```

---

### Task 4: Collapse the two object models into one

**Files:**

- Modify: `src/uasset_read/parsers/asset_types/anim_blueprint.py:17-23`, `anim_common.py:11`, `anim_montage.py:17`, `anim_sequence.py:19` — repoint `uasset_read.models.ir` → `uasset_read.models.ir_anim`
- Delete: `src/uasset_read/models/ir.py` (673L), `models/blueprint.py` (172L), `models/transforms.py` (59L)
- Modify: `src/uasset_read/models/__init__.py` if it re-exports any deleted name (it is currently 1 line)

**Interfaces:**

- Consumes: nothing.
- Produces: `uasset_read.models.ir_anim` is the single IR import for animation types. Exact names that must still resolve: `AnimBlueprintIR`, `BakedStateMachineIR`, `BakedStateIR`, `BakedExitTransitionIR`, `BakedTransitionIR` (anim_blueprint), `AnimNotifyIR` (anim_common), `AnimMontageIR` (anim_montage), `AnimSequenceIR` (anim_sequence). All eight are already defined in `ir_anim.py` and merely re-exported through `ir.py:663-673`.

- [ ] **Step 1: Prove the eight names live in `ir_anim.py`**

```bash
cd /e/Develop/uasset_read
python - <<'PY'
import uasset_read.models.ir_anim as A, uasset_read.models.ir as I
names=["AnimBlueprintIR","BakedStateMachineIR","BakedStateIR","BakedExitTransitionIR","BakedTransitionIR","AnimNotifyIR","AnimMontageIR","AnimSequenceIR"]
assert all(getattr(I,n) is getattr(A,n) for n in names), 'ir.py defines a different object'
print('ir.py anim names are pure re-exports of ir_anim.py')
PY
```

Expected: `ir.py anim names are pure re-exports of ir_anim.py`. If it fails, `ir.py` defines something live — STOP and report.

- [ ] **Step 2: Repoint the four importers**

Change `from uasset_read.models.ir import …` to `from uasset_read.models.ir_anim import …` in the four files. `models/ir.py:663-673` is the only bridge today, so nothing else can break.

- [ ] **Step 3: Prove the rest of `ir.py` plus the two modules are unreferenced**

```bash
grep -rn "PackageIR\|ExportIR\|ImportIR\|GraphIR\|NodeIR\|PinIR\|MaterialInputIR\|KismetIR" src tests | grep -v "^src/uasset_read/models/ir.py" || echo IR-DEAD
grep -rn "BlueprintMetadata\|BlueprintVariable\|MulticastDelegate\|BlueprintInterface\|FunctionParameter" src tests | grep -v "^src/uasset_read/models/blueprint.py" || echo BLUEPRINT-DEAD
grep -rn "VectorValue\|RotatorValue\|ScaleValue\|format_transform_value" src tests | grep -v "^src/uasset_read/models/transforms.py" || echo TRANSFORMS-DEAD
```

Expected: the three `*-DEAD` markers. (`models/blueprint.py` and `models/transforms.py` have zero references anywhere in `src` or `tests` — verified independently by both the models lane and the reachability scan.)

- [ ] **Step 4: Delete and verify**

```bash
git rm src/uasset_read/models/ir.py src/uasset_read/models/blueprint.py src/uasset_read/models/transforms.py
python -m pytest -q && python -m ruff check src/uasset_read tests && python -m pyright src/uasset_read
```

Expected: `110 passed`, ruff clean, pyright 0 errors. Anim semantics still come through: `PYTHONPATH=src python -m uasset_read tests/samples/ABP_RifleAnimLayers.uasset --depth decode > temp/after-task4.json && python -c "import json;d=json.load(open('temp/after-task4.json',encoding='utf-8'));print(sum(1 for o in d['objects'] if o.get('role','').startswith('Anim')) or 'see diff')"`, then diff against `temp/baseline-cli.json` at `--depth package` (must be identical; the `decode` file is for eyeballing anim data still present).

- [ ] **Step 5: Commit**

```bash
git add -A src/uasset_read
git commit -m "refactor: retire the v1 presentation IR; animation types live only in models/ir_anim.py"
```

---

### Task 5: Delete the zero-caller functions in `serializers/`

**Files:**

- Modify: `src/uasset_read/serializers/object_resources.py` — delete `build_imports_list:170-180`, `read_soft_object_paths:182-195`, `detect_blueprint:429-432`, `resolve_parent_class_with_linker:449-460`, `detect_blueprint_with_linker:470-474`, `resolve_parent_class:479-506`
- Modify: `src/uasset_read/serializers/package_summary.py` — delete `validate_export_data_range:845-870`, `read_soft_package_references:1046-1060`
- Modify: `src/uasset_read/serializers/graph_helpers.py` — inline `read_ftext_with_history:210-275` into its two in-file callers
- Modify: `src/uasset_read/serializers/graph_node.py` — collapse `_handle_node_pos_x`/`_handle_node_pos_y` into the existing `_handle_i32_to_raw` dispatch entry; collapse `_handle_node_comment` onto `_read_tag_fname`; `read_k2node_knot` body is `return {}` → `lambda ctx: {}` in the handler dict
- Modify: `src/uasset_read/serializers/graph_pin.py` + `graph_helpers.py` — `_read_pin_fstring_field`, `_read_pin_ftext_field`, `_get_thread_local` are 1–2 call-site wrappers; inline them

**Interfaces:**

- Consumes: Task 3 (the `*_with_linker` variants are already gone, so `resolve_parent_class`/`detect_blueprint` are the plain leftovers).
- Produces: no signature changes for anything that survives. `read_ue_graph`, `read_package_summary`, `read_name_table`, `read_import_map`, `read_export_map`, `get_asset_class`, `resolve_class_name` keep their signatures — `test_blueprint_graph.py:18-20` imports four of them.

- [ ] **Step 1: Re-verify each symbol has no caller (a stale deletion here is the main risk of this task)**

```bash
cd /e/Develop/uasset_read
for f in build_imports_list read_soft_object_paths detect_blueprint detect_blueprint_with_linker resolve_parent_class resolve_parent_class_with_linker validate_export_data_range read_soft_package_references read_ftext_with_history _read_pin_fstring_field _read_pin_ftext_field _get_thread_local; do printf "%-34s %s\n" "$f" "$(grep -rn "\b$f\b" src tests | grep -v "def $f" | wc -l)"; done
```

Expected: `0` for every row except `read_ftext_with_history` (2 — its two in-file callers) and `_read_pin_fstring_field`/`_read_pin_ftext_field`/`_get_thread_local` (>0, call sites to inline). Any other symbol with a nonzero count: STOP, leave it in place, note it in your report.

- [ ] **Step 2: Delete the eight zero-caller functions**

Delete the whole `def` block including its docstring. Do not replace them with `NotImplementedError` stubs; the replacement is nothing.

- [ ] **Step 3: Inline the three wrappers**

`read_ftext_with_history` → merge its body into `_read_ftext_value` and `read_ftext`. `_read_pin_fstring_field`/`_read_pin_ftext_field` → replace each call site with the guarded call to `_read_fstring_safe`/`_read_ftext_value` it wraps. `_get_thread_local` → put the single `threading.local()` attribute read at its one call site.

- [ ] **Step 4: Verify**

```bash
python -m pytest -q && python -m ruff check src/uasset_read tests && python -m pyright src/uasset_read
PYTHONPATH=src python -m uasset_read tests/samples/ABP_RifleAnimLayers.uasset --depth package > temp/after-task5-cli.json
python -c "import json;a=json.load(open('temp/baseline-cli.json',encoding='utf-8'));b=json.load(open('temp/after-task5-cli.json',encoding='utf-8'));assert a==b;print('identical')"
```

Expected: `110 passed`, ruff clean, pyright 0 errors, `identical`. `serializers/graph_node.py`/`graph_pin.py` are exercised by the blueprint-graph golden tables in `test_samples.py::test_v2_tables_match_independent_golden_reference` — that test is the real guard for the inlining.

- [ ] **Step 5: Commit**

```bash
git add -A src/uasset_read/serializers
git commit -m "refactor: drop zero-caller serializers and inline three single-use wrappers"
```

---

### Task 6: Turn the asset-type registration table into data

**Files:**

- Modify: `src/uasset_read/parsers/asset_types/__init__.py` (`_OPAQUE_STUBS:39-85`, `_optional` inside `register_asset_type_handlers:212-315`, the `__import__` block at `:316-352`, the `inspect.signature` probe at `:128-136`)
- Modify: `src/uasset_read/parsers/asset_types/material_instance.py` (14L, one function returning a two-key dict) — inline it as a `PropertyMetadataHandler`-style entry or a one-line lambda in the table

**Interfaces:**

- Consumes: nothing.
- Produces: `register_asset_type_handlers()` and `get_class_registry()` keep their exact signatures and register the same handler set. `ClassHandler`, `HandlerResult` stay exported from `class_registry.py` unchanged (the `asset_types` modules import them).

**Facts (measured):** the `_optional` table has **55 rows / 43 of them resolve to `make_opaque_stub()`**, 12 rows point at real parsers (`movie_scene_control_rig` contributes two). Zero rows hit the `except ImportError` path. So the dynamic import machinery exists only to carry 43 identical stubs.

- [ ] **Step 1: Capture the exact registration set as a golden assertion**

```bash
cd /e/Develop/uasset_read
python - <<'PY'
from uasset_read.parsers.class_registry import get_class_registry
from uasset_read.parsers.asset_types import register_asset_type_handlers
register_asset_type_handlers()
reg = get_class_registry()
names = sorted({h.handler_name for h in reg._handlers})   # verified attr: ClassHandlerRegistry._handlers (class_registry.py:80)
print(len(names), names)
open('temp/handlers-before.txt','w').write('\n'.join(names))
PY
```

Expected: one line per registered handler (56+ names, including the 43 `*Handler` stubs). Keep `temp/handlers-before.txt` — Step 5 compares against it. `ClassHandlerRegistry` stores handlers in `self._handlers` (`class_registry.py:80`), confirmed by introspection: `vars(get_class_registry())` → `['_handlers', '_cache']`.

**Do not call `register_asset_type_handlers()` and then `get_class_registry()` in the same snippet** (lane C finding): `get_class_registry()` bootstraps registration itself, so the explicit call double-registers and yields 140 handler objects / 70 names. Use `get_class_registry()` alone; the true production count is **70 handlers / 70 unique names** (verified identical at `c8b72909` and after the merge).

- [ ] **Step 2: Replace the stub rows with data**

Replace `_OPAQUE_STUBS` + the 43 stub rows with one table of `(class_names, handler_name)` pairs and build the handlers in a loop:

```python
_OPAQUE_STUB_HANDLERS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("SoundAttenuation",), "SoundAttenuationHandler"),
    (("AnimationDataModel",), "AnimDataModelHandler"),
    (("StringTable",), "StringTableHandler"),
    (("PoseAsset",), "PoseAssetHandler"),
    (("AnimBoneCompressionSettings",), "AnimBoneCompressionHandler"),
    (("AnimCurveCompressionCodec",), "AnimCurveCompressionHandler"),
    (("SubsurfaceProfile",), "SubsurfaceProfileHandler"),
    (("FoliageType",), "FoliageTypeHandler"),
    (("SkeletalMeshLODSettings",), "SkeletalMeshLODSettingsHandler"),
    (("CurveFloat",), "CurveFloatHandler"),
    (("AnimComposite",), "AnimCompositeHandler"),
    (("AnimBlendSpace", "AnimBlendSpace1D", "AimOffsetBlendSpace", "AimOffsetBlendSpace1D"), "AnimBlendSpaceHandler"),
    (("SoundConcurrency",), "SoundConcurrencyHandler"),
    (("DialogueWave",), "DialogueWaveHandler"),
    (("DialogueVoice",), "DialogueVoiceHandler"),
    (("CurveLinearColor",), "CurveLinearColorHandler"),
    (("CurveVector",), "CurveVectorHandler"),
    (("TextureRenderTarget2D", "TextureRenderTargetCube"), "TextureRenderTargetHandler"),
    (("PhysicsAsset",), "PhysicsAssetHandler"),
    (("PhysicalMaterial",), "PhysicalMaterialHandler"),
    (("AnimLayerInterface",), "AnimLayerInterfaceHandler"),
    (("SoundMix",), "SoundMixHandler"),
    (("SoundClass",), "SoundClassHandler"),
    (("SoundSubmix",), "SoundSubmixHandler"),
    (("BehaviorTree",), "BehaviorTreeHandler"),
    (("BlackboardData",), "BlackboardDataHandler"),
    (("DataAsset",), "DataAssetHandler"),
    (("PrimaryDataAsset",), "PrimaryDataAssetHandler"),
    (("Landscape",), "LandscapeHandler"),
    (("LandscapeGrassType",), "LandscapeGrassTypeHandler"),
    (("LandscapeLayerInfoObject",), "LandscapeLayerInfoHandler"),
    (("World",), "WorldHandler"),
    (("Level",), "LevelHandler"),
    (("ParticleSystem",), "ParticleSystemHandler"),
    (("WidgetBlueprintGeneratedClass", "WidgetBlueprint"), "WidgetBlueprintHandler"),
    (("Texture2DArray",), "Texture2DArrayHandler"),
    (("VolumeTexture",), "VolumeTextureHandler"),
    (("MediaPlayer",), "MediaPlayerHandler"),
    (("MediaTexture",), "MediaTextureHandler"),
    (("MediaSource",), "MediaSourceHandler"),
    (("ClothAsset",), "ClothAssetHandler"),
    (("GroomAsset",), "GroomAssetHandler"),
    (("SparseVolumeTexture",), "SparseVolumeTextureHandler"),
)

# then extend the `handlers` list that register_asset_type_handlers() already builds
# (today that literal ends with `*NIAGARA_HANDLERS, NiagaraNodeHandler(),` at :207-208):
handlers.extend(
    AssetTypeHandler(list(class_names), make_opaque_stub(), handler_name)
    for class_names, handler_name in _OPAQUE_STUB_HANDLERS
)
```

- [ ] **Step 3: Import the 12 real rows statically instead of `__import__`**

The `__import__`/`getattr`/`try/except ImportError` block becomes a static import group; classes are instantiated, functions are wrapped:

```python
from uasset_read.parsers.asset_types.anim_blueprint import AnimBlueprintHandler
from uasset_read.parsers.asset_types.anim_montage import AnimMontageHandler
from uasset_read.parsers.asset_types.anim_sequence import AnimSequenceHandler
from uasset_read.parsers.asset_types.curve_table import parse_curve_table
from uasset_read.parsers.asset_types.data_table import parse_data_table
from uasset_read.parsers.asset_types.level_sequence import parse_level_sequence
from uasset_read.parsers.asset_types.movie_scene import MovieSceneHandler
from uasset_read.parsers.asset_types.movie_scene_control_rig import (
    MovieSceneControlRigParameterSectionHandler,
    MovieSceneControlRigParameterTrackHandler,
)
from uasset_read.parsers.asset_types.skeleton import parse_skeleton
from uasset_read.parsers.asset_types.sound_wave import parse_sound_wave
from uasset_read.parsers.asset_types.user_defined import parse_user_defined
```

then in the handler list:

```python
    AnimSequenceHandler(),
    AnimBlueprintHandler(),
    AnimMontageHandler(),
    MovieSceneHandler(),
    MovieSceneControlRigParameterTrackHandler(),
    MovieSceneControlRigParameterSectionHandler(),
    AssetTypeHandler(["SoundWave"], parse_sound_wave, "SoundWaveHandler"),
    AssetTypeHandler(["DataTable"], parse_data_table, "DataTableHandler"),
    AssetTypeHandler(["CurveTable"], parse_curve_table, "CurveTableHandler"),
    AssetTypeHandler(["Skeleton"], parse_skeleton, "SkeletonHandler"),
    AssetTypeHandler(["LevelSequence"], parse_level_sequence, "LevelSequenceHandler"),
    AssetTypeHandler(["UserDefinedEnum", "UserDefinedStruct"], parse_user_defined, "UserDefinedHandler"),
```

Delete the whole `for module, func_name, class_names, handler_name in _optional:` loop, the `_optional` list, `_OPAQUE_STUBS`, and the `except ImportError as e: logger.debug(...)` fail-silent branch. A missing parser must now fail loudly at import — that is the point of the change.

`make_opaque_stub()` returns a 2-parameter `_parse(archive, name_map)` (`opaque_stub.py:21`), so Step 4's `_takes_export` is `False` for all 43 stubs — which is what happens today. Preserve that: do not add an `export` parameter to the stub.

- [ ] **Step 4: Kill the hot-path `inspect.signature` probe**

`AssetTypeHandler.parse` calls `inspect.signature(self._parse_func)` on **every parse**. Compute it once in `__init__`:

```python
    def __init__(self, class_names, parse_func, handler_name) -> None:
        self._class_names = set(class_names)
        self._parse_func = parse_func
        self._handler_name = handler_name
        self._takes_export = len(inspect.signature(parse_func).parameters) >= 3
```

and in `parse()`: `data = self._parse_func(archive, name_map, export) if self._takes_export else self._parse_func(archive, name_map)`. Move `import inspect` to the module header and delete the per-call import.

- [ ] **Step 5: Prove the registered set is unchanged**

```bash
python - <<'PY'
from uasset_read.parsers.class_registry import get_class_registry
from uasset_read.parsers.asset_types import register_asset_type_handlers
register_asset_type_handlers()
reg = get_class_registry()
names = sorted({h.handler_name for h in reg._handlers})
before = open('temp/handlers-before.txt').read().split()
assert names == before, [x for x in set(names) ^ set(before)]
print('handler set identical:', len(names))
PY
python -m pytest -q && python -m ruff check src/uasset_read tests && python -m pyright src/uasset_read
```

Expected: `handler set identical: N`, `110 passed`, ruff clean, pyright 0 errors.

- [ ] **Step 6: Commit**

```bash
git add -A src/uasset_read/parsers/asset_types
git commit -m "refactor: express asset-type registration as data; drop the dynamic import table"
```

---

### Task 7: Delete `asset_registry_parser.py` and its source-text test

**Files:**

- Delete: `src/uasset_read/parsers/asset_registry_parser.py` (201L)
- Modify: `tests/test_core.py` — delete the test at `:729` (`test_asset_registry_dependency_gate_uses_521`) which reads that file's **source text**; delete its nested `_run_cases` entry only, never a top-level function
- Modify: `tests/test_core.py` — delete the nested def `test_asset_registry_dependency_gate_uses_521` (starts :725, inside the top-level `test_package_document_preserves_every_export_and_role`); it does `(SRC / "uasset_read/parsers/asset_registry_parser.py").read_text()`, so it fails the moment the parser goes. Also delete its `entry` in the `_run_cases([...])` list at the end of that top-level function, and the top-level import list entry if the name appears there.
- Modify: `src/uasset_read/constants.py:218` — delete `UE4_ASSETREGISTRY_DEPENDENCYFLAGS`. Verified consumers are only `asset_registry_parser.py:25,119` and the nested test, so all three leave in this one commit. **This lane owns that constant** — Task 9 must not touch it.

**Interfaces:**

- Consumes: nothing.
- Produces: nothing. `EUEVerion`/`VER_UE4_*` names inside the file are UE-format constants; the live path reads versions from `serializers/package_summary.py`, not here.

- [ ] **Step 1: Prove no production importer**

```bash
cd /e/Develop/uasset_read
grep -rn "asset_registry_parser" src tests docs README.md wiki 2>/dev/null | grep -v "docs/designs\|docs/plans" || echo NO-LIVE-REF
```

Expected: only `tests/test_core.py:729` (the source-text assertion) plus `docs/` history. That test reading a `.py` file as text is exactly the implementation-pinning the audit flagged.

- [ ] **Step 2: Delete module + the source-text test body**

Keep the enclosing top-level `test_*` function (structure gate). Remove only the nested `_run_cases` case that reads `asset_registry_parser.py`.

Note on the neighbouring nested tests, which constrain other lanes: `test_import_package_name_not_gated_by_filter_editor_only:721` reads `serializers/object_resources.py` source text and splits on `"def build_imports_list"` — so that function must keep existing until Task 5 lands; `test_class_handlers_kwarg_defaults_true_for_v1:1264` asserts `parse_properties_from_export` keeps `run_class_handlers` defaulting to `True` — Task 3 must strip `linker` from that signature but must not touch `run_class_handlers`.

- [ ] **Step 3: Verify**

```bash
python -m pytest -q && python -m ruff check src/uasset_read tests && python -m pyright src/uasset_read
python -m pytest tests/test_core.py::test_test_suite_structure_gate -q
```

Expected: `110 passed` (or `109 passed` plus a note if the removed case was its own top-level function — it must not have been), ruff clean, pyright 0 errors, structure gate passes.

- [ ] **Step 4: Commit**

```bash
git add -A src/uasset_read/parsers tests/test_core.py
git commit -m "refactor: delete unreferenced asset_registry_parser and the test that pinned its source text"
```

---

### Task 8: Shrink `project_logging.py` to what the CLI actually uses

**Files:**

- Modify: `src/uasset_read/project_logging.py` (531L → ~80L) — keep only `log_context` and `cleanup_project_logs`
- Modify: `src/uasset_read/__init__.py:19-24` (drop `ProjectLogSession`, `configure_project_logging`, `project_logging_session`, `shutdown_project_logging` from imports and `__all__`), `src/uasset_read/cli.py` (drop `LogConfig.to_configure_kwargs()` usage), `src/uasset_read/config.py:84-115` (`to_configure_kwargs`), `src/uasset_read/config.py:17-58` (`ParseConfig`, if still unconsumed)
- Test: `tests/test_core.py` — nested cases referencing the removed symbols only

**Interfaces:**

- Consumes: Task 3 must be merged first — `link/linker.py` was `log_context`'s only library consumer, so the surviving surface is CLI-only.
- Produces: `uasset_read.__all__` loses four logging names. `parse_package_document(**kwargs)` is unchanged. `cleanup_project_logs(...)` and `log_context(...)` keep their signatures (CLI's `--clean-logs` and the remaining `with log_context(...)` call sites).

**Invariant this restores (AGENTS.md):** "library code returns structured diagnostics and does not configure process-global logging."

- [ ] **Step 1: Enumerate the surviving consumers**

```bash
cd /e/Develop/uasset_read
grep -rn "project_logging import\|from uasset_read.project_logging" src tests
grep -rn "configure_project_logging\|shutdown_project_logging\|ProjectLogSession\|project_logging_session\|scoped_project_logging\|JSONFormatter\|new_log_run_id\|current_log_run_id\|_LogContextFilter" src tests | grep -v "^src/uasset_read/project_logging.py"
```

Expected: the first grep returns `cli.py:14` (`cleanup_project_logs`), `__init__.py:19`, and `link/linker.py:11` **only if Task 3 has not landed**. The second grep's only hits should be `__init__.py`'s re-export block and `config.py`'s `to_configure_kwargs`. Anything else is a live consumer — keep that symbol and note it.

**Verified at `c8b72909` (lane D escalation, 2026-09-05):** `main()` never configures logging. `grep -rn "configure_project_logging|project_logging_session|scoped_project_logging|shutdown_project_logging" src tests` hits only `project_logging.py` self-references, the `config.py:97` docstring, and the `__init__.py` re-export block; `basicConfig|dictConfig|fileConfig` has **zero** hits in `src`. So the process-global logging machinery is already unreachable from every entry point, and the AGENTS.md invariant holds only accidentally. This task is therefore **delete-only** — see Step 3.

`config.to_configure_kwargs` (`config.py:96`) has exactly one consumer: `project_logging.py:289` inside `scoped_project_logging`. Deleting that function makes the method dead in the same commit, so it goes too (`effective_enabled` at `config.py:100` is local to it).

- [ ] **Step 2: Reduce the module**

Keep `log_context` (≈10 lines: a `contextvars`-free `LoggerAdapter`-based scope, or the existing body if it is already that small) and `cleanup_project_logs` (≈60 lines: it globs the log dir). Delete `configure_project_logging`, `shutdown_project_logging`, `ProjectLogSession`, `_DisabledLogSession`, `project_logging_session`, `scoped_project_logging`, `JSONFormatter`, `_LogContextFilter`, `configure_worker_stream_logging`, `new_log_run_id`, `current_log_run_id` and the module-level globals they used.

- [ ] **Step 3: Do NOT add CLI logging setup (delete-only)**

The original draft of this step told the reader to add `_configure_cli_logging(verbose, logfile)` with `logging.config.dictConfig` and call it from `main()`. That premise was **wrong**: there is no `-v/--verbose` flag and no `--logfile` flag in `cli.py` (verified: `grep -rn "verbose|logfile" src/uasset_read/cli.py` → no hits), and `main()` has no logging call to replace. Adding the function would create new CLI surface, change stderr, and install root-logger handlers — i.e. it would add behavior and a new abstraction, which this plan's Global Constraints forbid and which would break the `test_cli_python_agent_share_default_projection_and_logging_inert` assertions that `logging.root.handlers` and `logging.root.level` do not move.

So: delete the machinery, keep `log_context` and `cleanup_project_logs` with unchanged signatures, and change nothing in `cli.py` for this task. Do not add `dictConfig`.

The 5 `--log-*` flags that reach only the deleted machinery (`--log-level`, `--log-cleanup`, `--log-max-bytes`, `--log-backup-count`, `--log-format`) stay **inert and unpoked**: retiring shipped flags is a product decision (Out Of Scope), not a cleanup. Note them in the commit message body as a known dead surface.

Because `configure_project_logging` is gone, also delete `config.to_configure_kwargs` (`config.py:96-…`) — its sole consumer was `scoped_project_logging`.

- [ ] **Step 4: Verify behaviour is unchanged for the two CLI paths**

```bash
PYTHONPATH=src python -m uasset_read tests/samples/ABP_RifleAnimLayers.uasset --depth package > temp/after-task8-cli.json
python -c "import json;a=json.load(open('temp/baseline-cli.json',encoding='utf-8'));b=json.load(open('temp/after-task8-cli.json',encoding='utf-8'));assert a==b;print('identical')"
TMP=$(mktemp -d) && for i in 1 2 3; do : > "$TMP/uasset_read_2026090$i_run1.log"; done
ls "$TMP" | sort > temp/clean-before.txt
PYTHONPATH=src python -m uasset_read --clean-logs --log-dir "$TMP" --log-keep-latest 1 >/dev/null 2>&1; ls "$TMP" | sort > temp/clean-after.txt
diff temp/clean-before.txt temp/clean-after.txt >/dev/null && echo "CLEAN-LOGS NO-OP (suspicious: cleanup did not run)" || echo "cleanup ran; surviving:"; ls "$TMP"
python -m pytest -q && python -m ruff check src/uasset_read tests && python -m pyright src/uasset_read
python -c "import uasset_read; print(sorted(uasset_read.__all__))"
```

Expected: `identical`; `110 passed`; ruff clean; pyright 0 errors; `__all__` = the **6** remaining public names (10 minus `ProjectLogSession`, `configure_project_logging`, `project_logging_session`, `shutdown_project_logging`). Also confirm `logging.root.handlers` is untouched by an import — `test_cli_python_agent_share_default_projection_and_logging_inert` asserts this, so if it passes you are fine.

**Measured after the merge: `__all__` is actually 5, not 6** — `ParseConfig` disappears in Task 9 (same lane D), leaving `FArchive`, `LogConfig`, `ParseError`, `__version__`, `parse_package_document`. Both tasks are in lane D, so the pair's end state is what matters; the 10 → 6 shrink stated here is the Task 8 intermediate only.

Prove the `_configured_log_path` "active family" guard deletion is a no-op, not just plausible: that global is always `None` on the shipping path because nothing configures logging, so the skip branch can never fire; the `--clean-logs` before/after run above is the empirical check that the surviving-file set is unchanged by your edit (run it once before the edit, once after).

**Do not touch `wiki/`** to fix the public-API table: `wiki/` is gitignored (`.gitignore:103`) and is a separate nested repo (`git ls-files wiki` → 0 files), so it cannot appear in a commit here. OpenWiki regenerates it from source; record the `__all__` shrink in the commit message instead.

- [ ] **Step 5: Commit**

```bash
git add -A src/uasset_read tests
git commit -m "refactor: delete the unreachable process-global logging machinery (delete-only)

Nothing in src/ or tests/ configured logging: main() had no logging call, and
basicConfig/dictConfig/fileConfig had zero occurrences in src. The AGENTS.md
no-process-global-logging invariant therefore held only accidentally.

Drops configure_project_logging, shutdown_project_logging, ProjectLogSession,
project_logging_session, scoped_project_logging, JSONFormatter,
_LogContextFilter, configure_worker_stream_logging, new_log_run_id,
current_log_run_id and config.to_configure_kwargs; keeps log_context and
cleanup_project_logs. Public surface uasset_read.__all__ shrinks 10 -> 6, so
the OpenWiki public-API table needs regeneration (wiki/ is a gitignored nested
repo and is not patched here). --log-level/--log-cleanup/--log-max-bytes/
--log-backup-count/--log-format remain accepted but inert: flag retirement is a
separate product decision."
```

---

### Task 9: Delete dead tables and classes in the root modules

**Files:**

- Modify: `src/uasset_read/constants.py` — delete `decode_package_flags:92-123` plus all 13 names measured as unreferenced outside `constants.py`: `UE5_LEGACY_VERSION`, `LIGHTWEIGHT_TOLERANT_PARSE_THRESHOLD:151`, `CONTROL_RIG_LARGE_FILE_THRESHOLD:152`, `CONTROL_RIG_LARGE_FILE_CLASSES:153`, `BLUEPRINT_METADATA_KEYS`, `CONTAINER_TYPE_MAP`, `CONTAINER_TYPE_PREFIX`, `MAX_REASONABLE_CAP`, `UE5_LARGE_PROPERTY_TYPES`, `UE5_LARGE_PROPERTY_MAX_REASONABLE`, `MATERIAL_DOMAIN_MAP:447`, `MATERIAL_USAGE_FLAG_NAMES`, `_EXPRESSION_TYPE_PATTERNS:497-733` — and with them their only consumer `classify_expression_type:734-766` (Step 1 re-checks all of them; the line numbers are from `f2fa0f61` and may have shifted)
  - **Do NOT delete `BLEND_MODE_MAP` or `SHADING_MODEL_MAP`** (corrected at `c8b72909`): contrary to the first draft, they are asserted by the live nested test `test_material_enum_tables_match_engine_types` (`tests/test_core.py:735`), which pins the engine's real enum numbering. That test is a deliberate contract check, not residue. `UE4_ASSETREGISTRY_DEPENDENCYFLAGS` is likewise not yours — Task 7 (same lane A) owns it.
- Modify: `src/uasset_read/memory_safety.py` — delete `MemoryMonitor:134-192`, `MemoryStats:73-91`, `get_memory_stats:193-214`, `should_isolate:19-32`, `_get_process_rss_mb`, `MemoryPolicy:92-133`; **keep** `ResourceBudget:33-72`, `ResourceLimits`, `MemoryLimitExceeded`
- Modify: `src/uasset_read/debug.py` — delete `format_hex_view:32-80`; keep `HexViewEntry`
- Modify: `src/uasset_read/package.py` — delete the `PackageProvider` alias, `open_file`, `read_file`, `list_files`, `_get_root_mtime` (`:152-206,245`)
- Modify: `src/uasset_read/mappings.py` — replace the 30-line `_BytesReader` class with `struct.Struct` unpacking at its call sites
- Modify: `src/uasset_read/cli.py:25-63` — replace `_sanitize_error_message`'s regex pile with `os.path.basename`
- Modify: `src/uasset_read/__main__.py:5-10` — delete the `sys.path.insert` hack (the package is installed; `pytest.ini` already sets `pythonpath = src`)
- Modify: `src/uasset_read/exceptions.py` — delete `UAssetError`, `SemanticContractError` if Step 1 confirms they are never raised or caught
- Modify: `src/uasset_read/config.py` — delete `ParseConfig` if still unconsumed after Task 8, and the 6 unreferenced keys (`asset_roots`, `effective_enabled`, `force_full_parse`, `include_parent_assets`, `lightweight_threshold`, `memory_policy`)

**Interfaces:**

- Consumes: Task 8 for `config.py`.
- Produces: `uasset_read.__all__` may drop `ParseConfig`/`LogConfig` if their consumers vanish — check `__init__.py:17` before deleting, and keep the `__all__` list consistent in the same edit.

**Guard:** `ResourceBudget`/`ResourceLimits`/`MemoryLimitExceeded` implement the bounded-read discipline AGENTS.md mandates at binary trust boundaries. They stay. The same is true of every `MAX_*`/`validate_count` helper that `serializers/` calls.

- [ ] **Step 1: Re-verify each name is referenced nowhere but its own definition**

```bash
cd /e/Develop/uasset_read
for n in _EXPRESSION_TYPE_PATTERNS classify_expression_type MATERIAL_DOMAIN_MAP MATERIAL_USAGE_FLAG_NAMES LIGHTWEIGHT_TOLERANT_PARSE_THRESHOLD CONTROL_RIG_LARGE_FILE_THRESHOLD CONTROL_RIG_LARGE_FILE_CLASSES decode_package_flags MemoryMonitor MemoryStats get_memory_stats should_isolate MemoryPolicy format_hex_view PackageProvider _BytesReader UAssetError SemanticContractError ParseConfig; do printf "%-38s %s\n" "$n" "$(grep -rln "\b$n\b" src tests | grep -v "^src/uasset_read/constants.py$" | tr '\n' ' ')"; done
```

Expected: blank (or `config.py` only for `MemoryPolicy`/`ParseConfig`) for every row. A row listing any other file = live → keep that name and report it. Do not delete anything whose row is non-empty.

- [ ] **Step 2: Delete, then re-check the bounded-read guards are intact**

```bash
grep -rn "ResourceBudget\|ResourceLimits\|MemoryLimitExceeded" src | wc -l
```

Expected: nonzero (unchanged from before the edit — compare with `git stash`-free re-count after).

- [ ] **Step 3: Replace `_BytesReader` with `struct`**

Its reads are `u8/u16/u32/i32/read(n)`. At each call site use `struct.unpack_from('<H', buf, off)[0]` style one-liners (endianness per the existing code path — mirror whatever `_BytesReader` did, `<` unless the file proves `>`), then delete the class. Keep the byte-order decision in one named constant if the original encoded it.

- [ ] **Step 4: Verify**

```bash
python -m pytest -q && python -m ruff check src/uasset_read tests && python -m pyright src/uasset_read
PYTHONPATH=src python -m uasset_read tests/samples/ABP_RifleAnimLayers.uasset --depth package > temp/after-task9-cli.json
python -c "import json;a=json.load(open('temp/baseline-cli.json',encoding='utf-8'));b=json.load(open('temp/after-task9-cli.json',encoding='utf-8'));assert a==b;print('identical')"
PYTHONPATH=src python -m uasset_read tests/samples/ALS_AnimBP.uasset --depth package > /dev/null && echo big-sample-ok
python -c "import uasset_read; print(len(uasset_read.__all__))"
```

Expected: `110 passed`, ruff clean, pyright 0 errors, `identical`, `big-sample-ok` (this sample is 10 MB and exercises the memory-budget path — it is why `ResourceBudget` stays).

- [ ] **Step 5: Commit**

```bash
git add -A src/uasset_read
git commit -m "refactor: delete dead root tables, monitor classes and path helpers"
```

---

### Task 10: Remove the v2 micro-cuts, the empty directories, and the test duplication

**Files:**

- Modify: `src/uasset_read/v2/version.py:57-64` (`version_string`, zero callers), `:25-28` (`MappingInfo` — replace with `str | None` on `VersionContext.mappings`; the value is set at `legacy.py:545` and never read), `src/uasset_read/v2/source.py:15-21` (`Source` Protocol, one annotation-only consumer → annotate the two concrete classes), `:130-134` (`sub_slice`, test-only), `:137-138` (`source_size`, redundant with `total_size()`), `src/uasset_read/v2/blueprint_graph.py:231-236` (`_collect_all_nodes` recursion is a no-op — the emitter never writes a `subgraphs` key), `src/uasset_read/v2/projection.py:141` (move `_VALID_VIEWS` to module level like `_VALID_DEPTHS`)
- Delete: the 18 empty directories
- Modify: `tests/test_core.py` — `_isolated_handlers` context manager for the 11 handler save/restore blocks (`:1215,1240,1291,1324,1345,1360,1394,1476,1525,1631,1723`), one `_ReaderBase` for the two duplicated stub readers (`:1763-1783`, `:1837-1860`), and the 3 remaining source-text tests (`:1751`, `:1917`, `:1932` — `:722`/`:729` are handled in Task 7)
- Modify: `tests/test_samples.py:594-607` — drop `_StubArchive`, use `ByteArchive` with a pre-packed payload
- Modify: `README.md:27` (drop `0.5.5 (stable)`; no such tag was ever released — highest tag is `v0.5.4.45`), `README.md:211` and `README.md` module table rows for `graph/`/`link/` (they must stop describing modules Tasks 1 and 3 delete)

**Interfaces:**

- Consumes: all earlier tasks (do this last; the README rows are only correct once the modules are actually gone).
- Produces: end state of the plan.

- [ ] **Step 1: v2 micro-cuts, each verified first**

```bash
for n in version_string MappingInfo sub_slice source_size _collect_all_nodes; do printf "%-20s %s\n" "$n" "$(grep -rn "\b$n\b" src tests | grep -v "def $n\|class $n" | wc -l)"; done
```

Expected: `version_string` 0; `MappingInfo` ≥1 (the `legacy.py:545` construction — that is the one to delete along with the class); `sub_slice` tests-only; `source_size` tests-only; `_collect_all_nodes` 1 in-file caller. Replace `_collect_all_nodes` body with:

```python
def _collect_all_nodes(graphs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [n for g in graphs for n in g.get("nodes", [])]
```

- [ ] **Step 2: Remove the 18 empty directories**

```bash
find src -type d -empty -print -delete
```

Expected 18 lines: `blueprint`, `core`, `pipeline`, `renderers`, and the 14 `semantic/*` subdirs. `git status` will show nothing (git does not track empty dirs) — this step only stops them misleading readers and tools.

- [ ] **Step 3: Shared handler-isolation helper in the tests**

Add one module-level context manager (context managers are not test functions, so the structure gate is unaffected) and use it at all 11 sites:

```python
from contextlib import contextmanager

@contextmanager
def _isolated_handlers(*handlers):
    from uasset_read.v2 import handlers as H
    saved = list(H._HANDLERS)
    try:
        H._HANDLERS[:] = list(handlers)
        yield
    finally:
        H._HANDLERS[:] = saved
```

Then delete the 11 `saved = list(...)` / `try:` / `finally:` blocks in favour of `with _isolated_handlers(...):`.

- [ ] **Step 4: One reader stub base**

`_KismetLike` (`:1763-1783`) and `_WidthProbe` (`:1837-1860`) both wrap `ByteArchive` with the same `__init__`/`read_u8`/`read_i32`. Extract `_ReaderBase` with those three, keep each stub's unique methods (`xfer_ansi_string`/`xfer_unicode_string` vs `read_u16`/`read_bool`/`tell`) in its subclass.

- [ ] **Step 5: Fix the two README claims that are now false-by-construction**

Line 27 → drop `0.5.5 (stable)` (never tagged) and state the released line honestly. Line 211 → remove `link/` and `graph/` from the "Shared readers behind that document" sentence; `kismet/` stays (it is still reached through `v2/package/legacy.py`, tracked in #642). Any module table row naming `graph/` or `link/` is deleted in the same edit.

- [ ] **Step 6: Final verification of the whole plan**

```bash
python -m pytest -q
python -m ruff check src/uasset_read tests
python -m pyright src/uasset_read
python -m pytest tests/test_core.py::test_test_suite_structure_gate -q
PYTHONPATH=src python -m uasset_read tests/samples/ABP_RifleAnimLayers.uasset --depth package > temp/final-cli.json
python -c "import json;a=json.load(open('temp/baseline-cli.json',encoding='utf-8'));b=json.load(open('temp/final-cli.json',encoding='utf-8'));assert a==b;print('v2 output identical end-to-end')"
python -m pip install build && python -m build && cd "$(mktemp -d)" && pip install e:/Develop/uasset_read/dist/*.whl && python -c "import uasset_read;print('import outside checkout ok')"
git ls-files src | wc -l
find src -type d -empty | wc -l
```

Expected: `110 passed`; ruff clean; pyright 0 errors; structure gate passes; `v2 output identical end-to-end`; wheel builds and imports outside the checkout (mirrors the `package-smoke` CI job); `git ls-files src` drops from **117** (116 `.py` + `py.typed`) to **103** — 14 files deleted (graph 6, link 3, models 3, `asset_registry_parser`, `class_serialization_strategy`), plus 102 if Task 6 inlines `material_instance.py`; `0` empty directories.

- [ ] **Step 7: Report the totals**

Write the achieved line delta (`git diff --stat <plan-base>..HEAD`) into the commit message body or the PR description, and list every finding you skipped in Step-1 verifications with the reason. The audit's estimates are not proof — the measured delta is.

- [ ] **Step 8: Commit**

```bash
git add -A src tests README.md
git commit -m "refactor: retire v2 micro-cruft, empty v1 directories, and test-only duplication"
```

---

## Self-Review Record

**1. Spec coverage.** A1 graph → Task 1. A2 link → Task 3. A3 models/ir → Task 4. A4 kismet/semantic → Task 2. A5 project_logging → Task 8. A6 constants → Task 9. A7 `graph/parser` helper relocation → Task 1 Step 2. A8 asset_registry_parser → Task 7. A9 blueprint/transforms → Task 4. A10 asset_types table → Task 6. A11 strategy merge → Task 3 (deleted outright, so no merge needed — its sole consumer was `link/`). A12 serializers dead functions → Task 5. A13 memory_safety/debug/package/mappings/cli/`__main__` → Task 9. A14 v2 yagni → Task 10. A15 exceptions/config keys → Task 9. A16 struct-decoder duplication → **not covered**: the `property_types`↔`binary_or_native_handlers` overlap needs a behaviour-preserving rewrite with per-decoder tests, and the parsers-core lane itself flagged the BinaryOrNative path's liveness as unverified. Split it into its own plan after re-verifying which samples exercise it. A17 FString reader pair → Task 5 Step 3 covers the `graph_helpers` half; the `_read_fstring_safe`/`read_ftext_fstring` merge is in the same family and was deliberately left out of Step 3 because the two differ in error semantics (raise vs sentinel) — treat it with A16. A18 tag-reader wrappers → Task 5 Step 3. A19 tests → Task 10 Steps 3–4.

**2. Placeholder scan.** Every step has a command or code. No "similar to Task N", no "add appropriate validation".

**3. Type consistency.** `_validate_graph_export_offset(export, archive_size: int) -> bool` is spelled the same in Task 1 and Task 10 references. The eight animation IR class names in Task 4 Step 1 match the four import lines in Task 4 Step 2 exactly. `AssetTypeHandler(class_names, parse_func, handler_name)` positional order is the same in Task 6 Steps 2 and 3. `_isolated_handlers(*handlers)` in Task 10 Step 3 matches the 11 call sites' intent (they all assign a full replacement list, not an append).
