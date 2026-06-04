---
title: Agent API 分类索引（已废弃）
section: agent-index-api-reference
---

> [!WARNING] 已废弃 — 0.4.1 移除
>
> 本文档引用了已删除的 `exporter/`、`n2c/`、`agent/` 模块。
> 请参阅 [[Agent 速查索引]] 获取最新 API 索引。
>
> 本文档保留仅供参考。

# Agent API 分类索引

完整的 API 函数/类分类索引，供 Agent 快速查找和定位。

## 解析入口 (3)

| 函数 | 说明 |
|------|------|
| `parse_package` | 标准包解析入口，支持 provider 抽象 |
| `parse_uasset` | 委托给 parse_package，向后兼容 |
| `parse_uasset_with_linker` | 带对象图链接器的完整解析 |

## 属性解析器 (38+)

### 基础类型
`parse_bool_property` `parse_int_property` `parse_float_property` `parse_double_property` `parse_str_property` `parse_name_property` `parse_utf8_str_property` `parse_ansi_str_property` `parse_guid_property`

### 整型变体
`parse_uint16_property` `parse_uint32_property` `parse_uint64_property`

### 对象引用
`parse_object_property` `parse_soft_object_property` `parse_weak_object_property` `parse_lazy_object_property` `parse_class_property` `parse_soft_class_property` `parse_asset_object_property` `parse_interface_property` `parse_field_path_property`

### 复合类型
`parse_array_property` `parse_struct_property` `parse_map_property` `parse_set_property` `parse_enum_property`

### 特殊类型
`parse_text_property` `parse_delegate_property` `parse_multicast_delegate_property` `parse_multicast_inline_delegate_property` `parse_multicast_sparse_delegate_property` `parse_optional_property`

### Verse 类型
`parse_verse_string_property` `parse_verse_class_property` `parse_verse_function_property` `parse_verse_dynamic_property` `parse_verse_cell_property` `parse_verse_value_property`

## 蓝图与图 (17+)

### 蓝图元数据
`extract_blueprint_metadata` `extract_blueprint_variables` `extract_components` `parse_component_transform` `extract_component_transforms` `read_blueprint_variable` `parse_property_flags_to_labels`

### 图提取
`extract_blueprint_graphs` `build_execution_flow_entries` `build_data_flows` `build_connections_map` `build_execution_chains` `build_graphs_summary` `format_graphs_json` `build_blueprint_node_index` `format_pin_ref`

### 兼容层
`build_execution_flows` `write_pin_trace_report` `is_function_graph` `build_function_graphs` `write_phase75_diagnostic`

## Kismet 反编译 (11+)

### 提取
`extract_bytecode_bytes` `parse_bytecode_stream` `extract_and_parse` `FKismetArchive` `EXPR_CLASS_MAP`

### 翻译
`KismetTranslator` `MathFunctionCleaner` `TypeRegistry` `line_cpp` `FunctionBodyBuilder` `StructuredControlFlow`

### 管线
`decompile_uasset` `decompile_single_function` `KismetDecompiledResult`

## 序列化 (18+)

### Summary
`read_package_summary` `read_name_table` `build_version_container`

### Import/Export
`read_import_map` `read_export_map` `resolve_class_name` `get_asset_class` `detect_blueprint` `resolve_parent_class` `get_asset_class_with_linker` `resolve_class_name_with_linker` `detect_blueprint_with_linker` `resolve_parent_class_with_linker` `build_imports_list`

### PropertyTag
`read_property_tag` `parse_ctrl_flags` `parse_ue511_ctrl_flags`

### 图序列化
`read_ue_graph` `read_ue_graph_node` `read_ue_graph_pin` `read_ed_graph_pin_type` `read_fmember_reference` `create_node_from_archive`

### 安全
`detect_circular_deps` `validate_package_index`

## 格式化与导出 (18+)

### JSON
`format_json_full` `format_json_summary` `format_exports_list` `format_properties_list` `format_blueprint_dict`

### 文本
`format_text_full` `format_text_summary`

### Markdown/蓝图
`format_markdown` `format_blueprint_translation_text` `format_blueprint_ue_text`

### 辅助
`build_status_info` `build_schema_info` `resolve_fpackage_index`

### 导出系统
`ExportOptions` `IExporter` `ExporterRegistry` `export` `BatchExporter` `BatchExportResult`

## C++ 代码生成 (15+)

### IR
`CppClassIR` `CppProperty` `CppMethodIR` `CppHeaderMeta` `CppCallParameter` `CppCallStatement`

### 提取
`extract_cpp_class_skeleton` `extract_cpp_constructor` `extract_cpp_functions`

### 格式化
`format_cpp_header` `format_cpp_class_json` `format_cpp_call_statements` `format_cpp_default_value` `format_cpp_transform` `format_cpp_component_init` `format_cpp_input_action_load` `format_cpp_constructor` `build_constructor_sections`

### 类型映射
`ue_path_to_cpp_type` `ue_package_path_to_cpp_class` `cpf_flags_to_uproperty_marks` `UE_TO_CPP_TYPE_MAP` `ENGINE_CLASS_PATHS` `CPF_TO_UPROPERTY_MAP`

## 容器与原始文件 (12+)

### PAK
`PakFileReader` `FPakInfo` `FPakEntry` `FPakDirectoryEntry` `FPakCompressedBlock` `decompress_block` `decompress_entry` `read_fstring`

### IoStore
`IoStoreReader` `FIoChunkId` `FIoOffsetAndSize`

### 原始文件
`parse_raw_file` `parse_json_descriptor` `parse_ini_file` `parse_locres` `parse_locmeta` `parse_audio_metadata`

## N2C 中间格式 (10+)

### 数据类
`N2CStruct` `N2CGraph` `N2CNode` `N2CPin` `N2CNodeDefinition` `N2CNodeType` `N2CNodeProcessor`

### 序列化
`to_n2c_json` `from_n2c_json` `N2C_JSON_SCHEMA` `validate_n2c_json` `N2CIdMapper`

### 注册表
`N2CProcessorRegistry` `N2CNodeTypeRegistry`

## Agent 管线 (4)

| 函数/类 | 说明 |
|---------|------|
| `AgentTranslationPipeline` | Agent 翻译管线整合类 |
| `translate_blueprint_to_cpp` | 便捷翻译函数 |
| `CppFileWriter` | C++ 文件写入器 |
| `write_cpp_class_files` | 写入完整 C++ 类文件 |

## 版本管理 (3)

| 函数/类 | 说明 |
|---------|------|
| `VersionContainer` | 统一版本查询数据类 |
| `build_version_container` | 从 Summary 构建 |
| `EUEVersion` | UE 版本阈值枚举 |

## 链接器 (3)

| 函数/类 | 说明 |
|---------|------|
| `PackageLinker` | 两阶段对象图重建 |
| `UObjectInstance` | 轻量 UE 对象表示 |
| `LinkerParseResult` | 完整链接解析结果 |

## 包管理 (7)

| 函数/类 | 说明 |
|---------|------|
| `PackageBundle` | 包捆绑数据类 |
| `PackageArchive` | 虚拟归档（.uasset + .uexp 合并） |
| `PackageProvider` | Provider 基类 |
| `FileSystemPackageProvider` | 文件系统 Provider |
| `PakPackageProvider` | PAK 容器 Provider |
| `IoStorePackageProvider` | IoStore 容器 Provider |
| `open_package_bundle` | 工厂函数 |

## 辅助解析器 (6)

| 函数 | 说明 |
|------|------|
| `parse_default_value` | 解析默认值 |
| `format_variable_type` | 格式化变量类型字符串 |
| `get_struct_size` | 获取结构体大小 |
| `resolve_name_from_index` | 从索引解析名称 |
| `read_validated_count` | 读取验证后的计数 |
| `make_enum_value` | 创建枚举值 |
