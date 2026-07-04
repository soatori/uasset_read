---
name: test-runner
description: 运行测试、分析结果、生成报告的自动化测试技能
---

# Test Runner Skill

## Overview

自动化测试执行技能，支持按模块、标记、优先级运行测试，并生成结构化报告。

## 触发场景

当用户需要：
- 运行全部或部分测试
- 分析测试失败原因
- 生成测试覆盖率报告
- 执行回归测试
- 验证代码变更的影响

## 工作流

```
用户请求 → 解析测试范围 → 执行测试 → 分析结果 → 生成报告
```

## 测试分类（13 模块）

| 模块 | 文件数 | 说明 |
|------|--------|------|
| blueprint | 8 | 蓝图元数据、节点清理、变量提取、Pin 恢复 |
| serialization | 13 | 类注册、属性解析、fallback、tagged 结构体 |
| renderer | 4 | JSON/诊断输出、宏展开数据 |
| ir_builder | 5 | IR 构建、状态模型、safe_int |
| kismet | 11 | 反编译、函数解析、控制流、goto/跳转分析 |
| graph | 10 | 执行链、宏展开、Latent 检测 |
| cpp | 6 | C++ 类作用域、include 去重、标识符清理 |
| linker | 6 | 生命周期、偏移检查、DependsMap、payload |
| asset_parsing | 13 | 核心 API、版本兼容、截断诊断 |
| pak | 3 | 解压缩、结构体、处理 |
| iostore | 1 | IoStore Reader 分区读取 |
| archive | 6 | 偏移诊断、数组越界、FString、容错 |
| misc | 5 | 动画数据、音效衰减、Raw 读取 |

### 按标记

| 标记 | 说明 |
|------|------|
| `integration` | 需要外部样本资产 |
| `quality` | C++ 输出质量门禁 |
| `regression` | 真实资产回归 |
| `slow` | 慢速测试 |

## 命令模板

### 快速烟雾测试
```bash
cd e:/Develop/uasset_read && python -m pytest tests/ -v -x --tb=short -q
```

### 按模块运行
```bash
# 核心模块
python -m pytest tests/test_core_api.py tests/test_parse_package_core.py -v

# 蓝图模块
python -m pytest tests/test_blueprint_*.py tests/test_bp_*.py -v

# 图执行模块
python -m pytest tests/graph/ -v

# C++ 输出模块
python -m pytest tests/test_cpp_*.py -v
```

### 按标记运行
```bash
# 仅集成测试
python -m pytest tests/ -v -m integration

# 排除慢速测试
python -m pytest tests/ -v -m "not slow"

# 质量门禁
python -m pytest tests/ -v -m quality
```

### 生成覆盖率报告
```bash
python -m pytest tests/ --cov=src/uasset_read --cov-report=html
```

## 输出格式

### 测试结果摘要
```
=== 测试结果摘要 ===
总测试数: XXX
通过: XXX
失败: XXX
跳过: XXX
耗时: XX.Xs

=== 失败用例详情 ===
1. test_xxx.py::test_yyy
   错误: AssertionError: ...
   位置: line XX

=== 建议 ===
- 检查依赖文件是否存在
- 验证样本资产路径配置
```

## 错误处理

| 错误类型 | 处理方式 |
|----------|----------|
| 样本资产缺失 | 使用 `--allow-missing-assets` 跳过 |
| 内存不足 | 使用 `MAX_PARSE_FILE_SIZE` 限制 |
| 超时 | 使用 `PARSE_TIMEOUT` 控制 |

## 配置参考

- `pytest.ini`: pytest 配置
- `tests/conftest.py`: fixtures 和辅助函数
- `DEFAULT_SAMPLE_ROOT`: `E:\Develop\lib\Samples`

## 使用示例

```
用户: /test-runner core
Agent: 执行核心模块测试，分析结果并报告

用户: /test-runner integration --allow-missing-assets
Agent: 执行集成测试，跳过缺失资产的测试

用户: /test-runner coverage
Agent: 生成测试覆盖率报告

用户: /test-runner analyze
Agent: 运行 python scripts/test_organize.py 分析测试分类
```
