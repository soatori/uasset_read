---
title: 测试指南
section: testing
---

# 测试指南

## 测试分层

```
tests/
├── 单元测试（无外部依赖，CI 每次运行）
├── 集成测试（@pytest.mark.integration，需要真实资产文件）
│   ├── test_real_asset_coverage.py    — 20 资产 / 18 类型
│   ├── test_engine_content.py         — 12 Engine 内置资产
│   ├── test_known_failures.py         — 8 类已知失败回归
│   ├── test_formatter_outputs.py      — 6 资产 × 7 格式化器
│   └── test_asset_type_depth.py       — 6 类型深度字段验证
└── fixtures/                          — 已知失败记录（8 个 txt）
```

## 运行测试

```python
python -m pytest tests/ -v                                    # 单元测试
UE_SAMPLE_ROOT=/path python -m pytest tests/ -v -m integration # 集成测试
python -m pytest tests/ -v --cov=uasset_read                   # 覆盖率报告
```

## 覆盖率要求

- 核心解析模块覆盖率 **≥ 90%**
- 新增代码不得降低总体覆盖率
- 新功能必须配套至少一个单元测试
- 解析器变更需补充集成测试
