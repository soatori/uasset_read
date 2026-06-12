---
title: Agent 速查索引
section: agent-index
---

# Agent 速查索引

> [!NOTE]
> 本文档已为 AI Agent 优化。所有表格采用结构化格式，API 签名使用 `data-api` 注释标记。Agent 可通过 grep `<!-- data-api="函数名" -->` 定位 API。
>
> **0.4.1 变更**：`exporter/`、`n2c/`、`agent/` 模块已移除。新增 `core.py`（parse_single/parse_batch）、`renderers/`、`models/ir.py`。

## 按任务类型快速定位

| Agent 任务 | 定位章节 | 关键文件 |
|------------|----------|----------|
| 解析 .uasset 文件 | [[解析管线]] | `parse_uasset/` / `core.py` |
| 读取二进制字段 | [[FArchive]] | `archive.py` |
| 新增属性类型解析器 | [[属性解析器]] | `parsers/` |
| 修改蓝图输出格式 | [[蓝图解析]] | `blueprint/` |
| 修改图分析逻辑 | [[图分析]] | `graph/` |
| 修复 Kismet 反编译 | [[Kismet 反编译]] | `kismet/` |
| 新增输出格式 | [[渲染器系统]] | `renderers/` |
| 版本兼容性适配 | [[版本管理]] | `versioning.py` |
| 跨包引用修复 | [[对象链接器]] | `link/` |
| PAK/IoStore 容器支持 | [[PAK]] / [[IoStore]] | `pak/` / `iostore/` |
| 添加测试用例 | [[测试指南]] | `tests/` |
| 对照 UE 源码 | [[UE 源码对照]] | `docs/formats/uasset/` |

> [!WARNING] 已移除任务
> - ~~N2C Schema 变更~~ → `n2c/` 已整体删除
> - ~~C++ 代码生成~~ → `cpp_gen/` 已在 0.4.5 删除
> - ~~新增导出格式（旧）~~ → 使用 [[渲染器系统]] 替代

## 完整 API 分类索引

### 解析入口 (3)

<!-- data-api="parse_package" -->
| 函数 | 说明 |
|------|------|
| `parse_package` | 标准包解析入口，支持 provider 抽象 |
| `parse_uasset` | 委托给 parse_package，向后兼容 |
| `parse_uasset_with_linker` | 带对象图链接器的完整解析 |

### 属性解析器 (38+)

#### 基础类型
`parse_bool_property` · `parse_int_property` · `parse_float_property` · `parse_double_property` · `parse_str_property` · `parse_name_property` · `parse_utf8_str_property` · `parse_ansi_str_property` · `parse_guid_property`

#### 整型变体
`parse_uint16_property` · `parse_uint32_property` · `parse_uint64_property`

#### 对象引用
`parse_object_property` · `parse_soft_object_property` · `parse_weak_object_property` · `parse_lazy_object_property` · `parse_class_property` · `parse_soft_class_property` · `parse_asset_object_property` · `parse_interface_property` · `parse_field_path_property`

#### 复合类型
`parse_array_property` · `parse_struct_property` · `parse_map_property` · `parse_set_property` · `parse_enum_property`

#### 特殊类型
`parse_text_property` · `parse_delegate_property` · `parse_multicast_delegate_property` · `parse_multicast_inline_delegate_property` · `parse_multicast_sparse_delegate_property` · `parse_optional_property`

#### Verse 类型
`parse_verse_string_property` · `parse_verse_class_property` · `parse_verse_function_property` · `parse_verse_dynamic_property` · `parse_verse_cell_property` · `parse_verse_value_property`

### 蓝图与图 (17+)

#### 蓝图元数据
`extract_blueprint_metadata` · `extract_blueprint_variables` · `extract_components` · `parse_component_transform` · `extract_component_transforms` · `read_blueprint_variable` · `parse_property_flags_to_labels`

#### 图提取
`extract_blueprint_graphs` · `build_execution_flow_entries` · `build_data_flows` · `build_connections_map` · `build_execution_chains` · `build_graphs_summary` · `format_graphs_json` · `build_blueprint_node_index` · `format_pin_ref`

#### 兼容层
`build_execution_flows` · `write_pin_trace_report` · `is_function_graph` · `build_function_graphs` · `write_phase75_diagnostic`

### Kismet 反编译 (11+)

#### 提取
`extract_bytecode_bytes` · `parse_bytecode_stream` · `extract_and_parse` · `FKismetArchive` · `EXPR_CLASS_MAP`

#### 翻译
`KismetTranslator` · `MathFunctionCleaner` · `TypeRegistry` · `line_cpp` · `FunctionBodyBuilder` · `StructuredControlFlow`

#### 管线
`decompile_uasset` · `decompile_single_function` · `KismetDecompiledResult`

### 序列化 (18+)

#### Summary
`read_package_summary` · `read_name_table` · `build_version_container`

#### Import/Export
`read_import_map` · `read_export_map` · `resolve_class_name` · `get_asset_class` · `detect_blueprint` · `resolve_parent_class` · `get_asset_class_with_linker` · `resolve_class_name_with_linker` · `detect_blueprint_with_linker` · `resolve_parent_class_with_linker` · `build_imports_list`

#### PropertyTag
`read_property_tag` · `parse_ctrl_flags` · `parse_ue511_ctrl_flags`

#### 图序列化
`read_ue_graph` · `read_ue_graph_node` · `read_ue_graph_pin` · `read_ed_graph_pin_type` · `read_fmember_reference` · `create_node_from_archive`

#### 安全
`detect_circular_deps` · `validate_package_index`

### 格式化与渲染（0.4.1+）

#### 核心 API
`parse_single` · `parse_batch` · `list_formats` · `BatchResult`

#### 渲染器系统
`IRenderer` · `RenderOptions` · `get_renderer` · `list_formats` · `register_renderer` · `RENDERER_REGISTRY` · `JsonRenderer` · `MarkdownRenderer`

### 容器与原始文件 (12+)

#### PAK
`PakFileReader` · `FPakInfo` · `FPakEntry` · `FPakDirectoryEntry` · `FPakCompressedBlock` · `decompress_block` · `decompress_entry` · `read_fstring`

#### IoStore
`IoStoreReader` · `FIoChunkId` · `FIoOffsetAndSize`

#### 原始文件
`parse_raw_file` · `parse_json_descriptor` · `parse_ini_file` · `parse_locres` · `parse_locmeta` · `parse_audio_metadata`

### 版本管理 (3)

<!-- data-api="VersionContainer" -->
| 函数/类 | 说明 |
|---------|------|
| `VersionContainer` | 统一版本查询数据类 |
| `build_version_container` | 从 Summary 构建 |
| `EUEVersion` | UE 版本阈值枚举 |

### 链接器 (3)

<!-- data-api="PackageLinker" -->
| 函数/类 | 说明 |
|---------|------|
| `PackageLinker` | 两阶段对象图重建 |
| `UObjectInstance` | 轻量 UE 对象表示 |
| `LinkerParseResult` | 完整链接解析结果 |

### 包管理 (7)

<!-- data-api="PackageBundle" -->
| 函数/类 | 说明 |
|---------|------|
| `PackageBundle` | 包捆绑数据类 |
| `PackageArchive` | 虚拟归档（.uasset + .uexp 合并） |
| `PackageProvider` | Provider 基类 |
| `FileSystemPackageProvider` | 文件系统 Provider |
| `PakPackageProvider` | PAK 容器 Provider |
| `IoStorePackageProvider` | IoStore 容器 Provider |
| `open_package_bundle` | 工厂函数 |

### 辅助解析器 (6)

<!-- data-api="parse_default_value" -->
| 函数 | 说明 |
|------|------|
| `parse_default_value` | 解析默认值 |
| `format_variable_type` | 格式化变量类型字符串 |
| `get_struct_size` | 获取结构体大小 |
| `resolve_name_from_index` | 从索引解析名称 |
| `read_validated_count` | 读取验证后的计数 |
| `make_enum_value` | 创建枚举值 |
