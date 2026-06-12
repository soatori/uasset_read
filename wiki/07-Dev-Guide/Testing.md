---
title: 测试指南
section: testing
---

# 测试指南

## 测试分层

```
tests/
├── conftest.py         — 自动标记（contract/unit/e2e）
├── test_smoke_core.py  — 核心烟雾测试
├── test_real_assets.py — 真实资产测试
├── test_acceptance.py  — 验收测试
├── test_binary_boundaries.py — 二进制边界测试
└── test_uasset_test_tool.py — 测试工具自身测试
```

## 测试统计

- **总测试数**: 29 tests
- **测试架构**: contracts/units/e2e 三层分离（通过 conftest.py 自动标记）
- **源文件**: 153 个，17 个子包

## 运行测试

```bash
python -m pytest tests/ -v                                    # 全量测试
UE_SAMPLE_ROOT=/path python -m pytest tests/ -v -m integration # 集成测试
python -m pytest tests/ -v --cov=uasset_read                   # 覆盖率报告
```

## 覆盖率要求

- 核心解析模块覆盖率 **≥ 90%**
- 新增代码不得降低总体覆盖率
- 新功能必须配套至少一个单元测试
- 解析器变更需补充集成测试
