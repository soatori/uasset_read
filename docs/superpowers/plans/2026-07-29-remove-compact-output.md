# Remove Compact Output Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove `compact` so only `standard` and `debug` are valid output levels and every graph emits `nodes`.

**Architecture:** Validate `output_level` in `RenderOptions`, which is shared by renderers, single parsing, batch parsing, and worker requests. Simplify JSON graph output and the published schema to one `nodes` shape.

**Tech Stack:** Python 3.10+, dataclasses, pytest, jsonschema, Ruff.

## Global Constraints

- Only `standard` and `debug` are valid public output levels.
- Both modes retain `graphs[].nodes`; neither emits `node_summary`.
- Invalid levels, including `compact`, raise `ValueError` naming the invalid value and accepted levels.
- Do not add new output modes, truncation, pagination, export summaries, or parsers.

---

### Task 1: Define the active two-level contract

**Files:**
- Create: `tests/test_json_output_levels.py`
- Modify: `tests/temp/test_json_schema_contract.py`

**Interfaces:**
- Consumes: `RenderOptions(output_level: str)` and `parse_single(..., output_level: str)`.
- Produces: default-collected tests for two-level validation and one graph payload shape.

- [x] **Step 1: Add failing tests**

```python
@pytest.mark.parametrize("level", ["compact", "verbose", ""])
def test_render_options_reject_unknown_output_levels(level: str) -> None:
    with pytest.raises(ValueError, match=rf"{level!r}.*standard.*debug"):
        RenderOptions(output_level=level)

def test_parse_single_rejects_compact_output_level() -> None:
    with pytest.raises(ValueError, match="'compact'.*standard.*debug"):
        parse_single(str(SAMPLES / "FirstPerson_BP_FirstPersonCharacter.uasset"), format="json", output_level="compact", log_enabled=False)

def test_parse_batch_rejects_compact_before_scanning_input(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="'compact'.*standard.*debug"):
        parse_batch(str(tmp_path), output_level="compact", log_enabled=False)
```

Also test standard/debug FirstPerson JSON against the schema, assert every graph has a list `nodes`, assert no graph has `node_summary`, and assert a summary-only graph fails schema validation. Remove compact calls and `NodeSummary` assertions from `tests/temp/test_json_schema_contract.py`.

- [x] **Step 2: Confirm RED**

Run `python -m pytest tests/test_json_output_levels.py -q`.

Expected: compact is accepted and the current schema accepts a summary-only graph.

### Task 2: Remove production compact support

**Files:**
- Modify: `src/uasset_read/renderers/base.py`
- Modify: `src/uasset_read/renderers/json_renderer.py`

**Interfaces:**
- Produces: `validate_output_level(output_level: str) -> str` and `RenderOptions.__post_init__() -> None`.
- Produces: `_graph_to_dict()` that always emits `nodes`.

- [x] **Step 1: Implement the minimum change**

```python
VALID_OUTPUT_LEVELS = frozenset({"standard", "debug"})

def validate_output_level(output_level: str) -> str:
    if output_level not in VALID_OUTPUT_LEVELS:
        raise ValueError(
            f"Unsupported output_level {output_level!r}; expected one of: 'standard', 'debug'"
        )
    return output_level

def __post_init__(self) -> None:
    validate_output_level(self.output_level)
```

Import and call `validate_output_level(output_level)` at the start of `parse_single()` and `parse_batch()` so normal and isolated batch requests fail before input scanning or worker creation. Remove the compact branch in `_export_to_dict()` and `_graph_to_dict()`. Always construct the nodes list, and delete `_aggregate_nodes()` and `_pin_semantic_key()`.

- [x] **Step 2: Confirm GREEN**

Run `python -m pytest tests/test_json_output_levels.py -q`.

Expected: all new tests pass.

- [x] **Step 3: Commit implementation**

Run `git add src/uasset_read/renderers/base.py src/uasset_read/renderers/json_renderer.py tests/test_json_output_levels.py` then `git commit -m "fix: remove compact JSON output mode"`.

### Task 3: Restore the single graph schema and verify #509

**Files:**
- Modify: `schemas/package.schema.json`
- Modify: `tests/temp/test_json_schema_contract.py`
- Modify: `tests/test_json_output_levels.py`

**Interfaces:**
- Produces: `$defs.GraphEntry` with mandatory `nodes`, no `node_summary`, and no `NodeSummary` definition.

- [x] **Step 1: Simplify schema**

Make `nodes` required in `GraphEntry`. Delete the `oneOf` alternate shape, the `node_summary` property, and the `NodeSummary` definition.

- [x] **Step 2: Verify real outputs**

Run:

```powershell
python -m pytest tests/test_json_output_levels.py tests/temp/test_json_schema_contract.py -q
python -m pytest -q
python -m pytest tests/temp -q
python -m ruff check src
python -m compileall -q src tests
git diff --check
rg -n -i 'output_level.*compact|node_summary|_aggregate_nodes|_pin_semantic_key' src schemas README.md docs
```

Expected: validation passes; final search has no production, schema, README, or documentation references to compact or node summaries. Negative tests may mention rejected values. Inspect ALS AnimBP, FirstPerson Blueprint, and StackOBot GI JSON to confirm graphs use `nodes` only and ALS remains large due to export count.

- [x] **Step 3: Update #509 and commit verification artifacts**

Replace #509's body with the two-level scope after local verification; add a comment with commit IDs and named-sample evidence. Commit schema, tests, and this plan with `git add -f docs/superpowers/plans/2026-07-29-remove-compact-output.md` and message `test: enforce two-level JSON graph schema`.
