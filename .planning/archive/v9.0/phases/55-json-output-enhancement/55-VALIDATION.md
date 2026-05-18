# Phase 55: JSON 输出增强 - Validation

**Phase:** 55-JSON 输出增强
**Date:** 2026-05-17
**Status:** Ready for execution

## Automated Verification

### Task 1: build_function_graphs() 核心函数

```bash
python -c "from uasset_read.graph.flow_builder import build_function_graphs; print('OK')"
```

**Expected:** 输出 "OK"，无 ImportError

### Task 2: JSON 输出注入

```bash
python -c "from uasset_read.formatters.json_formatter import format_json_full; import inspect; sig = inspect.signature(format_json_full); assert 'include_function_graphs' in sig.parameters; print('OK')"
```

**Expected:** 输出 "OK"

### Task 3: CLI --function-graphs flag

```bash
python -m uasset_read --help | grep "function-graphs"
```

**Expected:** 输出包含 "--function-graphs" 行

### Task 4: 单元测试

```bash
python -m pytest tests/test_output_formatting.py -k "function_graphs or output_version" --collect-only | grep -c "test_"
```

**Expected:** 计数 >= 7

## Full Test Run

```bash
python -m pytest tests/test_output_formatting.py -v
```

**Expected:** 所有新增测试 pass，无回归失败
