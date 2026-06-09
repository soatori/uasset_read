# P0 Test Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 4 P0 blocking test failures (13 failures + 4 collection errors) to reach full green test suite.

**Architecture:** Four independent bug fixes targeting module re-exports, mock patch targets, mock completeness, and data flow resolution in C++ code generation.

**Tech Stack:** Python 3.10+, pytest, unittest.mock

---

### Task 1: Fix `_TAGGED_FALLBACK_STRUCTS` ImportError

**Files:**
- Modify: `src/uasset_read/parsers/property_types/__init__.py:11-55,57-101`

- [ ] **Step 1: Add missing re-exports to `__init__.py`**

Add `_TAGGED_FALLBACK_STRUCTS` and `_TAGGED_FALLBACK_STRUCT_SCHEMAS` to both the explicit import block and `__all__` list:

```python
from uasset_read.parsers.property_types._all_types import (  # noqa: F401
    get_struct_size,
    # ... existing imports ...
    _extract_enum_type_from_tag,
    _TAGGED_FALLBACK_STRUCTS,
    _TAGGED_FALLBACK_STRUCT_SCHEMAS,
)

__all__ = [
    # ... existing entries ...
    "_extract_enum_type_from_tag",
    "_TAGGED_FALLBACK_STRUCTS",
    "_TAGGED_FALLBACK_STRUCT_SCHEMAS",
]
```

- [ ] **Step 2: Verify fix**

Run: `python -m pytest tests/test_framerate_animnotify.py tests/test_struct_blend_sample.py tests/test_struct_editor_element.py tests/test_struct_scalar_param.py -v`
Expected: All pass (4 collection errors → 0)

- [ ] **Step 3: Commit**

```bash
git add src/uasset_read/parsers/property_types/__init__.py
git commit -m "fix: re-export _TAGGED_FALLBACK_STRUCTS from property_types package"
```

---

### Task 2: Fix `peek_valid_pin_array_count` mock target

**Files:**
- Modify: `src/uasset_read/serializers/graph/pins.py:20-23`

- [ ] **Step 1: Add re-export of `peek_valid_pin_array_count` in `pins.py`**

The test patches `uasset_read.serializers.graph.pins.peek_valid_pin_array_count` but the function lives in `_common.py`. Add it to the existing import block:

```python
from uasset_read.serializers.graph._common import (
    _read_guid,
    # ... existing imports ...
    validate_pin_reference_at, _recover_pin_array_count, _try_recover_to_subpins,
    peek_valid_pin_array_count,
)
```

- [ ] **Step 2: Verify fix**

Run: `python -m pytest tests/test_pin_recovery.py -v`
Expected: All 22 tests pass

- [ ] **Step 3: Commit**

```bash
git add src/uasset_read/serializers/graph/pins.py
git commit -m "fix: re-export peek_valid_pin_array_count in pins module for mock compatibility"
```

---

### Task 3: Fix `test_export_error_context` MagicMock comparison

**Files:**
- Modify: `tests/test_export_error_context.py:16-26`

- [ ] **Step 1: Add `legacy_file_version` to mock archive's summary**

The error is `TypeError: '>' not supported between instances of 'MagicMock' and 'int'` at `property_parser.py:475` where `legacy_file_version > -6` is evaluated. The mock summary doesn't provide `legacy_file_version`, so `getattr` returns a MagicMock.

Update `_make_mock_summary`:

```python
def _make_mock_summary(file_version_ue5=0, package_flags=0, legacy_file_version=-7):
    """构造一个 mock PackageFileSummary。"""
    summary = MagicMock()
    summary.file_version_ue5 = file_version_ue5
    summary.package_flags = package_flags
    summary.legacy_file_version = legacy_file_version
    return summary
```

- [ ] **Step 2: Verify fix**

Run: `python -m pytest tests/test_export_error_context.py -v`
Expected: All 12 tests pass

- [ ] **Step 3: Commit**

```bash
git add tests/test_export_error_context.py
git commit -m "fix: add legacy_file_version to mock summary in export error context tests"
```

---

### Task 4: Fix C++ parameter binding for Aim() function

**Files:**
- Modify: `src/uasset_read/cpp_gen/extractors/cpp_function_body_extractor.py:179-219`

- [ ] **Step 1: Fix `_extract_call_args` to resolve data flow sources**

The current implementation uses `param.get("name", "")` which gets the CallFunction node's pin name (e.g., "Val") instead of tracing the data flow to find the source parameter (e.g., "Pitch" from FunctionEntry).

Fix: Check `data_flows` for each input pin to find `function_parameter` sources before falling back to raw pin names.

```python
def _extract_call_args(
    node_info: Dict,
    method_ir: CppMethodIR,
    data_flows: List[Dict],
) -> List[str]:
    """从 CallFunction 节点的 parameters 和 data_flows 推导参数列表。"""
    params = node_info.get("parameters", {})
    param_list = params.get("parameters", []) if isinstance(params, dict) else []
    node_guid = node_info.get("guid", "")

    # Build data flow lookup: (target_node_guid, input_pin) → source info
    flow_lookup = _build_data_flow_lookup(data_flows)

    args: List[str] = []
    for param in param_list:
        if isinstance(param, dict):
            name = param.get("name", "")
            direction = param.get("direction", "input")
            # 跳过 exec/return 参数
            if direction in ("exec", "return"):
                continue
            if name:
                # Try to resolve via data flow first
                resolved = _resolve_param_via_data_flow(
                    node_guid, name, flow_lookup
                )
                if resolved:
                    args.append(resolved)
                else:
                    args.append(_sanitize_identifier(name))

    # Fallback: 从 data_sources 推导 (existing logic)
    if not args:
        data_sources = node_info.get("data_sources", [])
        for ds in data_sources:
            if isinstance(ds, dict):
                pin = ds.get("input_pin", "")
                source = ds.get("data_source", {})
                if isinstance(source, dict):
                    sources_list = source.get("data_sources", [])
                    for src in sources_list:
                        if isinstance(src, dict):
                            src_type = src.get("source_type", "")
                            if src_type == "function_parameter":
                                src_pin = src.get("pin", "")
                                args.append(_sanitize_identifier(src_pin))
                            elif src_type == "default_value":
                                args.append(src.get("value", "0"))
                            elif src_type == "pure_function":
                                args.append(src.get("function_name", "Unknown"))

    return args


def _build_data_flow_lookup(data_flows: List[Dict]) -> Dict:
    """Build lookup: (target_guid, input_pin) → resolved arg string."""
    lookup = {}
    for flow in data_flows:
        target_guid = flow.get("target_node_guid", "")
        target_pin = flow.get("target_pin", "")
        sources = flow.get("data_sources", [])
        for src in sources:
            if isinstance(src, dict):
                src_type = src.get("source_type", "")
                if src_type == "function_parameter":
                    key = (target_guid, target_pin)
                    lookup[key] = _sanitize_identifier(src.get("pin", ""))
                elif src_type == "default_value":
                    key = (target_guid, target_pin)
                    lookup[key] = src.get("value", "0")
    return lookup


def _resolve_param_via_data_flow(
    node_guid: str,
    pin_name: str,
    flow_lookup: Dict,
) -> Optional[str]:
    """Try to resolve a parameter name via data flow lookup."""
    key = (node_guid, pin_name)
    return flow_lookup.get(key)
```

- [ ] **Step 2: Verify fix**

Run: `python -m pytest tests/test_cpp_quality_gate.py::TestCppParameterBinding -v`
Expected: All 6 tests pass

- [ ] **Step 3: Commit**

```bash
git add src/uasset_read/cpp_gen/extractors/cpp_function_body_extractor.py
git commit -m "fix: resolve C++ parameter names via data flow instead of raw pin names"
```

---

### Task 5: Full test suite verification

- [ ] **Step 1: Run full test suite**

Run: `python scripts/test_matrix.py all`
Expected: 100% pass rate, 0 failures, 0 errors

- [ ] **Step 2: If all green, create PR or merge to master**

```bash
git log --oneline develop ^master
```
