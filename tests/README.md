# 测试目录结构

## 概览

本目录包含 `uasset_read` 项目的全部测试用例，共 92 个测试文件，1320+ 个测试用例。

## 目录结构

```
tests/
├── conftest.py                    # pytest fixtures 和辅助函数
├── README.md                      # 本文件
│
├── graph/                         # 蓝图图执行测试 (10 个文件)
│   ├── test_chain_exec_pins.py
│   ├── test_control_flow_expansion.py
│   ├── test_custom_event_naming.py
│   ├── test_exec_pin_names.py
│   ├── test_execution_trace_safety.py
│   ├── test_internal_flows.py
│   ├── test_latent_detection.py
│   ├── test_macro_expander.py
│   ├── test_macro_flow_penetration.py
│   └── test_standard_macro_cpp_mapping.py
│
├── kismet/                        # Kismet 反编译测试 (1 个文件)
│   └── test_semantic_multi_call.py
│
├── renderers/                     # 渲染器测试 (1 个文件)
│   └── test_json_macro_output.py
│
└── *.py                           # 根目录测试文件 (80 个文件)
```

## 测试分类

### 按模块（13 类）

| 模块 | 文件数 | 说明 |
|------|--------|------|
| **blueprint** | 8 | 蓝图元数据、节点清理、变量提取、Pin 恢复 |
| **serialization** | 13 | 类注册、属性解析、fallback、tagged 结构体 |
| **renderer** | 4 | JSON/诊断输出、宏展开数据 |
| **ir_builder** | 5 | IR 构建、状态模型、safe_int |
| **kismet** | 11 | 反编译、函数解析、控制流、goto/跳转分析 |
| **graph** | 10 | 执行链、宏展开、Latent 检测 |
| **cpp** | 6 | C++ 类作用域、include 去重、标识符清理 |
| **linker** | 6 | 生命周期、偏移检查、DependsMap、payload |
| **asset_parsing** | 13 | 核心 API、版本兼容、截断诊断 |
| **pak** | 3 | 解压缩、结构体、处理 |
| **iostore** | 1 | IoStore Reader 分区读取 |
| **archive** | 6 | 偏移诊断、数组越界、FString、容错 |
| **misc** | 5 | 动画数据、音效衰减、Raw 读取 |

### 按标记

| 标记 | 说明 | 使用场景 |
|------|------|----------|
| `integration` | 需要外部样本资产 | 需要真实 UE 资产的测试 |
| `quality` | C++ 输出质量门禁 | 验证 C++ 输出准确性 |
| `regression` | 真实资产回归 | 防止已修复问题复发 |
| `slow` | 慢速测试 | 耗时较长的测试 |
| `auxiliary` | 辅助/历史回归 | 默认不运行 |

## 运行测试

### 快速命令

```bash
# 烟雾测试（最快）
python scripts/test_matrix.py smoke

# 单元测试
python scripts/test_matrix.py unit

# 全量测试
python scripts/test_matrix.py all

# 直接 pytest
python -m pytest tests/ -v
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

## 测试要求

1. **100% 通过率**：所有测试必须通过
2. **≥12 种资产类型**：集成测试需覆盖多种资产类型
3. **双模式验证**：稳定资产必须在 strict 和 tolerant 双模式下通过

## 配置

- `pytest.ini`: pytest 配置
- `tests/conftest.py`: fixtures 和辅助函数
- `DEFAULT_SAMPLE_ROOT`: `E:\Develop\lib\Samples`

## 添加新测试

1. 在对应模块目录创建 `test_*.py` 文件
2. 使用 `pytest.mark` 标记测试类型
3. 遵循现有测试风格
4. 确保测试可独立运行

## 故障排除

| 问题 | 解决方案 |
|------|----------|
| 样本资产缺失 | 使用 `--allow-missing-assets` 跳过 |
| 内存不足 | 检查 `MAX_PARSE_FILE_SIZE` 配置 |
| 测试超时 | 检查 `PARSE_TIMEOUT` 配置 |

## 冗余测试分析

| 测试对 | 说明 |
|--------|------|
| `test_linker_lifecycle.py` ↔ `test_lifecycle_preload.py` | 都测试 link→preload→post_load 生命周期 |
| `test_status_model.py` ↔ `test_status_model_unified.py` | 后者是更完整的集成测试 |
| `test_function_resolver.py` ↔ `test_function_resolver_enhanced.py` | 后者是前者的增强版本 |
| `test_jump_analyzer.py` ↔ `test_control_flow_enhanced.py` | 都测试 JumpAnalyzer，后者覆盖更多增强功能 |
