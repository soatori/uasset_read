---
title: 测试指南
section: testing
---

# 测试指南

## 测试分层

```
tests/
├── contracts/          — 契约测试（API 稳定性、接口规范）
├── units/              — 单元测试（无外部依赖，CI 每次运行）
├── e2e/                — 端到端测试（真实资产）
│   ├── test_real_asset_coverage.py    — 20 资产 / 18 类型
│   ├── test_engine_content.py         — 12 Engine 内置资产
│   ├── test_known_failures.py         — 8 类已知失败回归
│   ├── test_formatter_outputs.py      — 6 资产 × 7 格式化器
│   └── test_asset_type_depth.py       — 6 类型深度字段验证
├── fixtures/           — 已知失败记录（8 个 txt）
└── 顶层 test_*.py      — 兼容旧测试（自动标记为 units）
```

## 测试统计

- **总测试数**: 1837 tests
- **v0.4.5 新增**: 74 个 UE 保真度测试
- **测试架构**: contracts/units/e2e 三层分离
- **自动标记**: conftest.py 自动为测试添加 contract/unit/e2e 标记

## 运行测试

```python
python -m pytest tests/ -v                                    # 全量测试
UE_SAMPLE_ROOT=/path python -m pytest tests/ -v -m integration # 集成测试
python -m pytest tests/ -v --cov=uasset_read                   # 覆盖率报告
python scripts/test_matrix.py smoke                            # 快速烟雾测试
python scripts/test_matrix.py unit                             # 单元测试
python scripts/test_matrix.py all                              # 全量测试
```

## 覆盖率要求

- 核心解析模块覆盖率 **≥ 90%**
- 新增代码不得降低总体覆盖率
- 新功能必须配套至少一个单元测试
- 解析器变更需补充集成测试
