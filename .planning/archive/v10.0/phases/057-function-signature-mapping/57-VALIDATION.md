# Phase 57 — 函数签名映射：验证策略

---
phase: "57"
phase-slug: function-signature-mapping
date: "2026-05-18"
---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | pyproject.toml (pytest section) |
| Quick run command | `python -m pytest tests/test_cpp_gen.py -x` |
| Full suite command | `python -m pytest tests/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File |
|--------|----------|-----------|-------------------|------|
| FUNC-01 | FunctionEntry → C++ declaration with correct name, params, types, return type | unit | `pytest tests/test_cpp_gen.py::test_extract_cpp_functions_move -x` | tests/test_cpp_gen.py |
| FUNC-01 | Event override → C++ declaration with is_override=True, no UFUNCTION | unit | `pytest tests/test_cpp_gen.py::test_extract_event_override -x` | tests/test_cpp_gen.py |
| FUNC-02 | CallFunction → C++ call statement (self-context) | unit | `pytest tests/test_cpp_gen.py::test_extract_call_statement_jump -x` | tests/test_cpp_gen.py |
| FUNC-02 | CallFunction with args → call statement with parameters | unit | `pytest tests/test_cpp_gen.py::test_extract_call_statement_move -x` | tests/test_cpp_gen.py |
| FUNC-03 | UFUNCTION(BlueprintCallable) for impure functions | unit | `pytest tests/test_cpp_gen.py::test_ufunction_callable -x` | tests/test_cpp_gen.py |
| FUNC-03 | UFUNCTION(BlueprintPure) for pure functions | unit | `pytest tests/test_cpp_gen.py::test_ufunction_pure -x` | tests/test_cpp_gen.py |
| ALL | Golden-path: BP_FirstPersonCharacter → .h output with methods | integration | `pytest tests/test_cpp_gen.py::test_golden_path_with_methods -x` | tests/test_cpp_gen.py |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_cpp_gen.py -x`
- **Per wave merge:** `python -m pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`
