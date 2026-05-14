# Phase 35 Code Review

**Date:** 2026-05-13
**Commits:** 32e6e9f..e9230ae
**Files:** 8 (6 source, 1 test, 1 config)
**Review Depth:** Standard

## Critical

### CR-01: `_read_fstring_safe` corrupts stream on abnormal length — seek-back without consuming data

**File:** `src/uasset_read/serializers/graph.py:153-156`
**Issue:** When `abs(length) > max_length`, the function seeks back 4 bytes (over the length field) and returns `""`. The raw data bytes are never consumed. The next read call will interpret those data bytes as a new length field, corrupting the entire parse stream from that point forward.
**Fix:** Do NOT seek back. Consume (skip) the data using the abnormal length value, or read a safe number of bytes to drain the stream:
```python
if abs(length) > max_length:
    # Consume the data to avoid stream corruption; use a safe bound
    skip = min(abs(length) * (2 if length < 0 else 1), max_length * 2)
    archive.read(skip)
    return ""
```

### CR-02: `read_blueprint_variable` infinite loop on negative `meta_count`

**File:** `src/uasset_read/blueprint/variable_extractor.py:506-512`
**Issue:** `meta_count = archive.read_i32()` can return a negative value (corrupt data or misaligned stream). In Python, `range(-5)` produces an empty sequence, so the loop is skipped — but more critically, the following `archive.read_fstring()` for DefaultValue will read from a position that expected N metadata entries, causing the entire rest of the parse to be misaligned. A negative `meta_count` should be treated as an error.
**Fix:**
```python
meta_count = archive.read_i32()
if meta_count < 0:
    raise ParseError(f"Invalid metadata array count: {meta_count}")
if meta_count > MAX_PROPERTY_COUNT:
    raise ParseError(f"Metadata count {meta_count} exceeds limit")
```

### CR-03: `_map_property_flags` duplicates `CPF_Net` for both `is_net` and `is_replicated`

**File:** `src/uasset_read/blueprint/variable_extractor.py:60-61`
**Issue:** Both `is_net` and `is_replicated` are mapped to `CPF_Net`. `is_replicated` should use `CPF_Replicated` (`0x00100000`) instead. This causes `is_replicated` to be set incorrectly for any variable that has `CPF_Net` but not `CPF_Replicated`.
**Fix:**
```python
"is_replicated": bool(flags & CPF_Replicated),  # was: CPF_Net
```

### CR-04: `read_ue_graph_pin` fallback skip of 180 bytes may corrupt stream

**File:** `src/uasset_read/serializers/graph.py:786-787`
**Issue:** When `b_null_ptr != 0` and `read_ue_graph_pin` fails on the pin body, the code does `archive.seek(archive.tell() + 180)`. The 180-byte estimate is a hardcoded magic number with no basis in the actual UE serialization size. If the actual body is smaller or larger, all subsequent pin reads will be misaligned.
**Fix:** Catch the exception inside `read_ue_graph_pin` and have it return the number of bytes consumed, or use a try/except within `read_ue_graph_pin` itself to ensure the stream position is always correct after return:
```python
# In the NULL pin handler:
try:
    read_ue_graph_pin(archive, name_map, summary, export_map, import_map)
except Exception:
    # If body parsing fails, we cannot reliably recover position.
    # Better approach: wrap read_ue_graph_pin internally so it always
    # leaves the stream in a consistent state.
    pass  # Remove the +180 seek entirely
```

## Warnings

### WR-01: `status` property in ParseResult creates tight coupling via lazy import

**File:** `src/uasset_read/models/result.py:47-49`
**Issue:** The `status` property imports `build_status_info` from `formatters.helpers` inside the property body. While this avoids module-level circular imports, it means `result.py` (a core data model) now has a runtime dependency on `formatters.helpers` (an output formatting module). If the formatters module is ever restructured, this breaks silently. The behavior also differs from the direct call to `build_status_info` since it cannot be easily mocked in tests.
**Fix:** Move `status` computation to `helpers.py` as a standalone function, or define the property in a separate mixin class in the formatters module. Alternatively, document the dependency contract explicitly.

### WR-02: `extract_blueprint_variables` treats every non-metadata property as a variable

**File:** `src/uasset_read/blueprint/variable_extractor.py:175-244`
**Issue:** The function iterates over ALL properties and only skips those in `BLUEPRINT_METADATA_PROPERTY_NAMES`. Every other property (including system properties like "NodeGuid", "NodePosX", "NodeComment", "FunctionReference", etc.) is treated as a BlueprintVariable and added to the result. This inflates the variable count with non-variable entries.
**Fix:** Add an explicit allowlist or prefix-based filter to identify actual variable properties (e.g., properties with a known variable pattern or specific property types), rather than a denylist approach:
```python
# Skip non-variable properties (system/internal)
if prop_name.startswith(("Node", "Function", "Event")):
    continue
```

### WR-03: `serialize_property_value` MapValue and SetValue entries are not recursively serialized

**File:** `src/uasset_read/formatters/json_formatter.py:159-168`
**Issue:** `MapValue.entries` and `SetValue.elements` are returned directly without calling `serialize_property_value` on each element. If the entries contain nested `StructValue`, `MapValue`, etc., they will not be converted to JSON-compatible dicts, potentially causing `json.dumps` to fail with a `TypeError`.
**Fix:**
```python
if hasattr(value, "entries") and hasattr(value, "key_type"):  # MapValue
    return {
        "key_type": value.key_type,
        "value_type": value.value_type,
        "entries": [
            {k: serialize_property_value(v, depth + 1, max_depth) for k, v in e.items()}
            for e in value.entries
        ]
    }
if hasattr(value, "elements") and hasattr(value, "element_type"):  # SetValue
    return {
        "element_type": value.element_type,
        "elements": [serialize_property_value(e, depth + 1, max_depth) for e in value.elements]
    }
```

### WR-04: `_read_ftext_fstring` "no seek-back" approach assumes length field is genuine

**File:** `src/uasset_read/serializers/graph.py:175-185`
**Issue:** When `abs(length) > 10_000`, the function returns `""` without seeking back (consuming the i32) but also without reading the data bytes. If the `length` field is not actually a length (e.g., garbage data interpreted as a large integer), the subsequent reads will interpret the raw bytes as the next FString's length, causing cascading parse errors. The "no seek-back" design is correct only if the length field is genuinely a length — but if it is garbage, this silently corrupts the stream.
**Fix:** Add a comment documenting this assumption, or better, attempt to read and discard `min(abs(length), some_safe_bound)` bytes even in the overflow case:
```python
if abs(length) > 10_000:
    # Consume what we can to avoid stream corruption
    skip = min(abs(length) * (2 if length < 0 else 1), 20_000)
    archive.read(skip)
    return ""
```

### WR-05: `format_node_dict._get` helper fails when `node_data` contains dict-wrapped references

**File:** `src/uasset_read/graph/flow_builder.py:102-122`
**Issue:** When `nd` is a dict, `_get('function_reference')` returns a dict (not an `FMemberReference` dataclass). But the code then does `getattr(fr, 'member_name', None)` which returns `None` for dicts (since dicts don't have a `member_name` attribute). The correct access would be `fr.get('member_name')` if `fr` is a dict.
**Fix:**
```python
if fr is not None:
    def _ref_get(obj, key, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)
    result["function_reference"] = {
        "member_name": _ref_get(fr, 'member_name'),
        "member_parent": _ref_get(fr, 'member_parent'),
        "self_context": _ref_get(fr, 'b_self_context')
    }
```

### WR-06: `extract_blueprint_metadata` bare except swallows all errors silently

**File:** `src/uasset_read/blueprint/variable_extractor.py:362-367`
**Issue:** The `try/except Exception` block around `parse_properties_from_export` catches all exceptions and returns `(None, None)`. This means parse failures are completely invisible to the caller — there is no warning logged, no error recorded, and no way to distinguish "this is not a blueprint" from "this IS a blueprint but parsing failed."
**Fix:**
```python
try:
    properties = parse_properties_from_export(...)
except Exception as e:
    logger.warning("Failed to parse properties for export: %s", e)
    return None, f"Property parsing failed: {e}"
```

### WR-07: `build_execution_flows` processes all `START_EVENT_TYPES` including `K2Node_VariableSet` without extracting a meaningful name

**File:** `src/uasset_read/graph/flow_builder.py:368-383`
**Issue:** `K2Node_VariableSet` is in `START_EVENT_TYPES` but `_get_start_event_name` returns the literal string `"VariableSet"` for all such nodes (line 179). If a blueprint has many VariableSet nodes as start events, they will all be labeled identically in execution_flows output, making the output ambiguous. This is not a bug per se, but reduces the usefulness of the output.
**Fix:** Extract the actual variable name from `node_data` when available:
```python
elif node.class_name == "K2Node_VariableSet":
    if nd:
        var_name = nd.get("variable_name") if isinstance(nd, dict) else getattr(nd, 'variable_name', None)
        return f"VariableSet:{var_name}" if var_name else "VariableSet"
    return "VariableSet"
```

### WR-08: `_trace_execution_from_event` extracts function/event name via `getattr` which returns None for dict data

**File:** `src/uasset_read/graph/flow_builder.py:248-259`
**Issue:** When `nd` is a dict (from `read_k2node_call_function` / `read_k2node_event`), `getattr(fr, 'member_name', None)` will return `None` because `fr` is a dict, not an `FMemberReference` object. This means function names and event names in execution flows will always be missing when `node_data` is a dict.
**Fix:**
```python
fr = nd.get("function_reference") if isinstance(nd, dict) else getattr(nd, 'function_reference', None)
if fr:
    mn = fr.get('member_name') if isinstance(fr, dict) else getattr(fr, 'member_name', None)
    if mn:
        node_info["function_name"] = mn
```

## Info

### IN-01: `_format_variable_enhanced` accesses attributes that may not exist on `BlueprintVariable`

**File:** `src/uasset_read/formatters/json_formatter.py:348`
**Issue:** `variable.is_visible_anywhere` is accessed but `BlueprintVariable` does not define this attribute (it has `is_blueprint_readable` instead). This will raise `AttributeError` at runtime unless the attribute was set dynamically somewhere.
**Fix:** Use `getattr(variable, 'is_visible_anywhere', False)` or add the field to `BlueprintVariable`.

### IN-02: `serialize_property_value` depth check uses `>` instead of `>=`

**File:** `src/uasset_read/formatters/json_formatter.py:148`
**Issue:** With `depth > max_depth` and initial `depth=0`, `max_depth=10`, the function processes 11 levels (depth 0 through 10) before truncating. The intended behavior is likely to limit to `max_depth` levels, which would be `depth >= max_depth`. This is a minor semantic issue.
**Fix:** Change `if depth > max_depth` to `if depth >= max_depth` if strict `max_depth` limit is desired.

### IN-03: `read_pin_reference` returns `None` for NULL pins but the format might still have body data

**File:** `src/uasset_read/serializers/graph.py:256-282`
**Issue:** `read_pin_reference` reads only the 24-byte header (b_null + owning + guid) and returns `None` when `b_null_ptr != 0`. It does NOT consume the pin body. Callers that use this function directly will have their stream position off by the size of the pin body. The current callers (`read_pin_array`) handle this correctly by filtering out `None`, but this function is not safe for general use.
**Fix:** Add a docstring warning or rename to make it clear this only reads the reference header.

### IN-04: `detect_circular_deps` now always returns `[]` — callers expecting actual detection get silent no-op

**File:** `src/uasset_read/serializers/object_resources.py:174-186`
**Issue:** The function previously performed dependency density analysis. Now it unconditionally returns `[]`. While the tests have been updated to expect `[]`, any external consumers of the API (e.g., via JSON output `circular_deps` field) will silently receive empty results without any indication that detection is disabled.
**Fix:** Consider returning `None` or raising `NotImplementedError` to signal that detection is not available, rather than silently returning an empty list which looks like "no cycles found."

### IN-05: `read_k2node_enhanced_input` only reads `input_action_path`, missing potential additional fields

**File:** `src/uasset_read/serializers/graph.py:580-588`
**Issue:** The function only reads a single FString (`input_action_path`). According to UE source, `K2Node_EnhancedInputAction` may serialize additional fields (e.g., trigger event type). If those exist in the binary, the stream position will be incorrect after this function returns.
**Fix:** Verify the UE serialization format for `K2Node_EnhancedInputAction` and read all fields, or add a comment documenting the known format subset.

### IN-06: `use_complete_type_name` in constants.py uses `legacy_version <= -8` threshold

**File:** `src/uasset_read/constants.py:250`
**Issue:** The function checks `legacy_version <= -8` to determine if it's a UE5 file. This is correct per UE conventions, but the comment in the docstring says "UE4 always uses old format" without mentioning that `legacy_version <= -8` means UE5. The logic is correct but the docstring could be clearer.
**Fix:** Minor docstring clarification only — no code change needed.

---

## Summary

| Severity | Count |
|----------|-------|
| Critical | 4 |
| Warning  | 8 |
| Info     | 6 |
| **Total** | **18** |

### High-level Assessment

The phase 35 changes introduce several meaningful improvements (UE5 FText/FString handling, dict/dataclass compatibility, NULL pin handling). However, there are 4 critical issues that must be fixed before merging:

1. **Stream corruption in `_read_fstring_safe`** — seek-back without consuming data will cause cascading parse errors
2. **Missing negative `meta_count` validation** in `read_blueprint_variable` — could cause silent infinite loops or misalignment
3. **`CPF_Net` duplicated for `is_replicated`** — incorrect flag mapping
4. **Magic 180-byte fallback** in NULL pin body skip — arbitrary value risks stream corruption

The 8 warnings include several dict/dataclass handling gaps in `flow_builder.py` that would cause function and event names to be missing from execution flow output when node_data is stored as dicts (which it is, per the `read_k2node_*` functions that all return dicts).
