# Phase 12: BlueprintVariables完整提取 - Validation

**Created:** 2026-05-03
**Source:** 12-RESEARCH.md Validation Architecture

## Test Framework

| Property | Value |
|-----------|-------|
| Framework | pytest 3.10+ |
| Config file | tests/conftest.py (fixtures) |
| Quick run command | `pytest tests/test_phase12_blueprint_variables.py -x -v` |
| Full suite command | `pytest tests/ --tb=short -q` |

## Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| EXTR-02 | 变量名称、类型、默认值提取 | unit | `pytest tests/test_phase12_variables.py::test_variable_extraction -v` | ❌ Wave 0 |
| EXTR-02 | 元数据解析（Category、BlueprintReadWrite等） | unit | `pytest tests/test_phase12_variables.py::test_metadata_extraction -v` | ❌ Wave 0 |
| EXTR-03 | 组件变量识别（is_component字段） | unit | `pytest tests/test_phase12_variables.py::test_component_identification -v` | ❌ Wave 0 |
| EXTR-05 | 默认值类型覆盖验证 | unit | `pytest tests/test_phase12_variables.py::test_default_value_types -v` | ❌ Wave 0 |

## Sampling Rate

- **Per task commit:** `pytest tests/test_phase12_variables.py -x`
- **Per wave merge:** `pytest tests/ --tb=short -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

## Wave 0 Gaps

- [ ] `tests/test_phase12_variables.py` — 覆盖EXTR-02, EXTR-03, EXTR-05所有测试
- [ ] `tests/fixtures/blueprint_with_components.uasset` — 包含组件变量的测试资产
- [ ] `tests/fixtures/blueprint_with_metadata.uasset` — 包含完整元数据的测试资产

## Test Asset Requirements

### Blueprint with Components

需要包含以下特征的蓝图资产用于测试：
- 至少一个SkeletalMeshComponent或StaticMeshComponent
- 至少一个普通变量（非组件）
- CPF_InstancedReference标志位验证

### Blueprint with Metadata

需要包含以下特征的蓝图资产用于测试：
- 变量包含Category元数据
- 变量包含BlueprintReadWrite/BlueprintReadOnly标志
- 变量包含EditAnywhere/EditConst标志
- 变量包含ExposeOnSpawn标志

## Validation Commands Summary

```bash
# Wave 0: 创建测试文件后
pytest tests/test_phase12_variables.py -x -v

# 每个Task完成后
pytest tests/test_phase12_variables.py -x

# Phase完成后（gate）
pytest tests/ --tb=short -q
```