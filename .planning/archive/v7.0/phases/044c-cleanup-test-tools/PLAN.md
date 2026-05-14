# PLAN: Phase 44c — 清理测试工具

**Phase:** 44c  
**Goal:** 清空所有废弃/调试测试文件  
**Type:** cleanup

## Context

代码库中存在大量废弃的调试脚本和已弃用的测试文件，影响可维护性。

| 位置 | 文件数 | 说明 |
|------|--------|------|
| `tests/test_property_parsing.py` | 1 文件（1273 行） | 已标记 `pytest.skip`，针对 v1.0 旧版代码 |
| `tools/` | 27 个 `.py` + `__pycache__` | Phase 44 调试期间创建的 `test_debug*.py` 系列 |
| `temp/` | 13 个 `.py` | 各种 `debug_*.py` / `test_*.py` 调试脚本 |

---

## Tasks

### 44c-T1: 删除废弃测试文件

删除 `tests/test_property_parsing.py`（1273 行，已 `pytest.skip` 标记 DEPRECATED）

```bash
rm tests/test_property_parsing.py
```

**完成标准：** `tests/test_property_parsing.py` 不存在

### 44c-T2: 删除 `tools/` 目录

删除整个 `tools/` 目录（27 个 `test_debug*.py` 文件 + `__pycache__`）

```bash
rm -rf tools/
```

**完成标准：** `tools/` 不存在

### 44c-T3: 清空 `temp/` 目录

删除 `temp/` 下所有文件（13 个调试脚本）

```bash
rm -rf temp/
```

**完成标准：** `temp/` 不存在或为空

### 44c-T4: 回归测试

```bash
python -m pytest tests/ -v --tb=short
```

**完成标准：** 基线 373 passed（删除 `test_property_parsing.py` 后预期测试数可能减少，需确认无其他测试被影响）

### 44c-T5: 最终验证

```bash
test ! -f tests/test_property_parsing.py && test ! -d tools/ && echo "Cleanup complete"
```

**完成标准：** 所有目标文件/目录已删除

---

## Execution Order

1. **Wave 1:** 44c-T1, 44c-T2, 44c-T3（独立文件系统操作，可并行）
2. **Wave 2:** 44c-T4（回归测试）
3. **Wave 3:** 44c-T5（最终验证）

## Success Criteria

1. `tests/test_property_parsing.py` 不存在
2. `tools/` 目录不存在
3. `temp/` 目录不存在或为空
4. 所有测试通过（基线 373 passed，允许已知 pre-existing failures）

## Risks

- **零风险：** 纯删除操作，不影响任何源码或功能
- **零风险：** `test_property_parsing.py` 已整体 `pytest.skip`，不参与测试运行
- **注意：** `temp/` 目录如果被 `.gitignore` 排除，删除是清理工作目录；如果项目约定 `temp/` 作为缓存目录，可保留空目录（`mkdir -p temp/.gitkeep`）
