# 测试目录结构

## 概览

本目录包含 `uasset_read` 项目的全部测试用例，共约 75 个测试文件，1400+ 个测试用例。

## 目录结构

```
tests/
├── conftest.py                    # pytest fixtures 和辅助函数
├── README.md                      # 本文件
│
├── core/                          # 核心解析测试 (5 文件)
│   ├── test_core_api.py
│   ├── test_parse_package_core.py
│   ├── test_package_archive_read.py
│   ├── test_package_bundle.py
│   └── test_api_cleanup.py
│
├── serialization/                 # 序列化测试 (6 文件)
│   ├── test_class_registry.py
│   ├── test_class_serialization_strategy.py
│   ├── test_binary_or_native_handlers.py
│   ├── test_property_parser_error_handling.py
│   ├── test_package_summary_fields.py
│   └── test_payload_offset_strategy.py
│
├── ir/                            # IR 构建测试 (4 文件)
│   ├── test_ir_builder.py
│   ├── test_status_model.py
│   ├── test_safe_int.py
│   └── test_json_completeness.py
│
├── kismet/                        # Kismet 反编译测试 (7 文件)
│   ├── test_control_flow_enhanced.py
│   ├── test_function_resolver_enhanced.py
│   ├── test_kismet_decompilation.py
│   ├── test_goto_label_emission.py
│   ├── test_bytecode_scanner_fix.py
│   ├── test_event_execution_fix.py
│   └── test_kismet_deprecated_tokens.py
│
├── graph/                         # 蓝图图执行测试 (10 文件)
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
├── cpp/                           # C++ 生成测试 (6 文件)
│   ├── test_cpp_output_quality.py
│   ├── test_cpp_class_scope.py
│   ├── test_cpp_wrapper_nesting.py
│   ├── test_cpp_sanitizer.py
│   ├── test_cpp_default_value.py
│   └── test_cpp_include_dedup.py
│
├── linker/                        # Linker 生命周期测试 (5 文件)
│   ├── test_linker_lifecycle.py
│   ├── test_linker_offset_check.py
│   ├── test_depends_map_resolution.py
│   ├── test_depends_map_package_index.py
│   └── test_soft_object_path_index.py
│
├── renderer/                      # 渲染器测试 (1 文件)
│   └── test_renderers.py
│
├── blueprint/                     # 蓝图元数据测试 (6 文件)
│   ├── test_blueprint_node_cleaner.py
│   ├── test_pin_recovery.py
│   ├── test_variable_extractor.py
│   ├── test_empty_function_enrichment.py
│   ├── test_blueprint_field_validation.py
│   └── test_blueprint_metadata_keys.py
│
├── archive/                       # 归档/容错测试 (10 文件)
│   ├── test_fallback.py
│   ├── test_tolerant_parsing.py
│   ├── test_diagnostics.py
│   ├── test_truncated_file.py
│   ├── test_error_recovery.py
│   ├── test_version_compatibility.py
│   ├── test_fstring_utf16.py
│   ├── test_fstring_corruption.py
│   ├── test_export_error_context.py
│   └── test_array_count_check.py
│
├── structs/                       # 结构体解析测试 (5 文件)
│   ├── test_struct_lwc.py
│   ├── test_struct_scalar_param.py
│   ├── test_struct_blend_sample.py
│   ├── test_struct_editor_element.py
│   └── test_box_sphere_bounds.py
│
├── asset/                         # 资产解析测试 (7 文件)
│   ├── test_pak_structures.py
│   ├── test_pak_handling.py
│   ├── test_pak_decompress_validation.py
│   ├── test_asset_registry.py
│   ├── test_subgraph.py
│   ├── test_iostore_partition_validation.py
│   └── test_raw_readers.py
│
├── integration/                   # 集成/端到端测试 (6 文件)
│   ├── test_acceptance.py
│   ├── test_bp_firstpersoncharacter_validation.py
│   ├── test_ue_fidelity_integration.py
│   ├── test_ue_mcp_blueprint_comparison.py
│   ├── test_cue4parse_gap_completion.py
│   └── test_sample_assets_representative.py
│
└── misc/                          # 杂项测试 (4 文件)
    ├── test_hex_view.py
    ├── test_framerate_animnotify.py
    ├── test_sound_attenuation.py
    └── test_anim_data_model.py
```

## 测试分类

### 按模块（14 类）

| 模块 | 文件数 | 说明 |
|------|--------|------|
| **core** | 5 | 核心 API、解析入口、包读取 |
| **serialization** | 6 | 类注册、属性解析、策略、summary |
| **ir** | 4 | IR 构建、状态模型、safe_int、JSON 完整性 |
| **kismet** | 7 | 反编译、函数解析、控制流、字节码 |
| **graph** | 10 | 执行链、宏展开、Latent 检测 |
| **cpp** | 6 | C++ 类作用域、include 去重、标识符清理 |
| **linker** | 5 | 生命周期、偏移检查、DependsMap |
| **renderer** | 1 | JSON/Markdown 渲染、宏展开输出 |
| **blueprint** | 6 | 蓝图元数据、节点清理、变量提取、Pin 恢复 |
| **archive** | 10 | Fallback、容错、诊断、版本兼容 |
| **structs** | 5 | LWC、标量参数、BlendSample、EditorElement |
| **asset** | 7 | PAK 结构、解压、Asset Registry、IoStore |
| **integration** | 6 | 端到端、验收、UE 保真度 |
| **misc** | 4 | Hex 视图、动画、音效、帧率 |

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
python -m pytest tests/ -x --tb=short -q

# 单元测试
python -m pytest tests/ -v -m "not integration and not slow"

# 全量测试
python -m pytest tests/ -v

# 按模块运行
python -m pytest tests/core/ -v
python -m pytest tests/kismet/ -v
python -m pytest tests/graph/ -v
python -m pytest tests/cpp/ -v

# 按标记运行
python -m pytest tests/ -v -m integration
python -m pytest tests/ -v -m "not slow"
python -m pytest tests/ -v -m quality
```

### 按目录运行

```bash
# 核心模块
python -m pytest tests/core/ -v

# 蓝图模块
python -m pytest tests/blueprint/ -v

# 图执行模块
python -m pytest tests/graph/ -v

# C++ 输出模块
python -m pytest tests/cpp/ -v

# Kismet 反编译
python -m pytest tests/kismet/ -v
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
