---
title: 公共 API
section: public-api
---

# 公共 API

所有公共符号在 `src/uasset_read/__init__.py` 中通过 `__all__` 导出。当前版本导出约 **400** 个公共符号。

## 导入模式

```python
# 推荐：按需导入
from uasset_read import parse_single, parse_batch, list_formats
from uasset_read import parse_uasset, ParseResult
from uasset_read import FArchive, BlueprintMetadata, UEdGraph
from uasset_read import PakFileReader

# 新代码优先使用聚焦导入
from uasset_read.pak import PakFileReader
from uasset_read.cpp_gen import extract_cpp_class_skeleton
from uasset_read.renderers import get_renderer, list_formats
```

> [!NOTE] 架构变更
> **0.4.1 变更**：`exporter/`、`n2c/`、`agent/` 模块已移除。旧 `export()` 函数被 `parse_single()` 替代。
> `formatters/` 模块已清空，所有格式化功能迁移到 `renderers/` 系统。
> 新代码应优先使用聚焦导入。

## 核心 API（0.4.1+ 新增）

| 符号 | 说明 |
|------|------|
| `parse_single` | 解析单个文件并返回格式化字符串 |
| `parse_batch` | 批量解析目录中所有 .uasset/.umap |
| `list_formats` | 返回所有已注册的格式名 |
| `BatchResult` | 批量导出结果数据类 |

## 版本号

| 符号 | 类型 | 说明 |
|------|------|------|
| `__version__` | `str` | 当前库版本号 |

## 常量

### 基础常量

| 符号 | 说明 |
|------|------|
| `PACKAGE_FILE_TAG` | .uasset 文件魔数 |
| `PACKAGE_FILE_TAG_SWAPPED` | 字节序反转的魔数 |
| `UE5_VERSION_MIN` | UE5 最小版本号 |
| `UE5_LEGACY_VERSION` | UE5 遗留版本号 |
| `MAX_NAME_COUNT` | 名称表最大条目数 |
| `MAX_IMPORT_COUNT` | 导入表最大条目数 |
| `MAX_EXPORT_COUNT` | 导出表最大条目数 |
| `MAX_CUSTOM_VERSIONS` | 自定义版本最大数量 |
| `MMAP_THRESHOLD` | mmap 自动切换阈值 |
| `MAX_PROPERTY_COUNT` | 属性最大数量 |
| `PROPERTY_TAG_COMPLETE_TYPE_NAME` | PropertyTag 完整类型名标志 |

### 图解析边界常量

| 符号 | 说明 |
|------|------|
| `MAX_PINS_PER_NODE` | 单节点最大 Pin 数 |
| `MAX_NODES_PER_GRAPH` | 单图最大节点数 |
| `MAX_LINKEDTO_PER_PIN` | 单 Pin 最大 LinkedTo 数 |

### PropertyTag 标志

| 符号 | 说明 |
|------|------|
| `PROP_TAG_NONE` | 无标志 |
| `PROP_TAG_HAS_ARRAY_INDEX` | 含数组索引 |
| `PROP_TAG_HAS_PROPERTY_GUID` | 含属性 GUID |
| `PROP_TAG_HAS_EXTENSIONS` | 含扩展数据 |
| `PROP_TAG_HAS_BINARY_OR_NATIVE` | 含二进制或原生数据 |
| `PROP_TAG_BOOL_TRUE` | 布尔值为 True |
| `PROP_TAG_SKIPPED_SERIALIZE` | 跳过序列化 |

### 控制流 / 事件类型集合

| 符号 | 说明 |
|------|------|
| `CONTROL_FLOW_NODES` | 控制流节点类型集合 |
| `START_EVENT_TYPES` | 起始事件类型集合 |
| `BRANCH_TYPE_MAP` | 分支类型映射 |

### Package Flags

| 符号 | 说明 |
|------|------|
| `PKG_Cooked` | 已烘焙标志 |
| `PKG_UnversionedProperties` | 无版本属性标志 |
| `PKG_FilterEditorOnly` | 过滤编辑器数据标志 |

### UE5 版本标志

| 符号 | 说明 |
|------|------|
| `UE5_SCRIPT_SERIALIZATION_OFFSET` | 脚本序列化偏移 |
| `UE5_PROPERTY_TAG_EXTENSION` | 属性标签扩展 |
| `UE5_PROPERTY_TAG_COMPLETE_TYPE_NAME` | 完整类型名 |
| `UE5_REMOVE_OBJECT_EXPORT_PACKAGE_GUID` | 移除对象导出包 GUID |
| `UE5_TRACK_OBJECT_EXPORT_IS_INHERITED` | 跟踪对象导出继承 |
| `UE5_OPTIONAL_RESOURCES` | 可选资源 |
| `UE5_NAMES_REFERENCED_FROM_EXPORT_DATA` | 导出数据引用名称 |
| `UE5_PAYLOAD_TOC` | 载荷目录 |
| `UE5_LARGE_WORLD_COORDINATES` | 大世界坐标 |
| `UE5_FSOFTOBJECTPATH_REMOVE_ASSET_PATH_FNAMES` | 软对象路径移除资产路径 FName |
| `UE5_ADD_SOFTOBJECTPATH_LIST` | 添加软对象路径列表 |
| `UE5_DATA_RESOURCES` | 数据资源 |
| `UE5_ASSETREGISTRY_PACKAGEBUILDDEPENDENCIES` | 资产注册表包构建依赖 |
| `UE5_METADATA_SERIALIZATION_OFFSET` | 元数据序列化偏移 |
| `UE5_VERSE_CELLS` | Verse Cells |
| `UE5_PACKAGE_SAVED_HASH` | 包保存哈希 |
| `UE5_OS_SUB_OBJECT_SHADOW_SERIALIZATION` | 子对象阴影序列化 |
| `UE5_IMPORT_TYPE_HIERARCHIES` | 导入类型层次 |

### Framework / UE5MainStream / Release 版本 GUID

| 符号 | 说明 |
|------|------|
| `FFRAMEWORK_OBJECT_VERSION_GUID` | Framework 对象版本 GUID |
| `FFRAMEWORK_VERSION_ED_GRAPH_PIN_CONTAINER_TYPE` | 图 Pin 容器类型版本 |
| `FFRAMEWORK_VERSION_PINS_STORE_FNAME` | Pins 存储 FName 版本 |
| `FUE5_MAINSTREAM_VERSION_GUID` | UE5 主流程版本 GUID |
| `FUE5_MAINSTREAM_VERSION_ED_GRAPH_PIN_SOURCE_INDEX` | 图 Pin 源索引版本 |
| `FRELEASE_OBJECT_VERSION_GUID` | Release 对象版本 GUID |
| `FRELEASE_VERSION_PIN_TYPE_UOBJECT_WRAPPER` | Pin 类型 UObject 包装版本 |

### 输出配置

| 符号 | 说明 |
|------|------|
| `FORMAT_CONFIG` | 输出格式配置 |

### CPF 属性标志

| 符号 | 说明 |
|------|------|
| `CPF_Edit` | 可编辑 |
| `CPF_BlueprintVisible` | 蓝图可见 |
| `CPF_InstancedReference` | 实例引用 |
| `CPF_EditAnywhere` | 任意位置可编辑 |
| `CPF_EditInstanceOnly` | 仅实例可编辑 |
| `CPF_BlueprintReadWrite` | 蓝图读写 |
| `CPF_BlueprintReadOnly` | 蓝图只读 |
| `CPF_Transient` | 瞬态 |
| `CPF_SaveGame` | 存档 |
| `CPF_ExposeOnSpawn` | 生成时暴露 |

## 异常类

| 符号 | 说明 |
|------|------|
| `UAssetError` | 基础异常类 |
| `VersionError` | 版本相关异常 |
| `ErrorContext` | 带上下文的异常 |
| `ParseError` | 解析异常 |

## FArchive 二进制读取器

| 符号 | 说明 |
|------|------|
| `FArchive` | UE FArchive 二进制读取器，支持 mmap、字节交换、容错模式 |

## 序列化模块 (serializers)

### 包结构

| 符号 | 说明 |
|------|------|
| `PackageFileSummary` | 包文件摘要结构 |
| `PackageIndex` | 包索引 |
| `ObjectImport` | 对象导入条目 |
| `ObjectExport` | 对象导出条目 |
| `EngineVersion` | 引擎版本 |
| `CustomVersion` | 自定义版本 |
| `GenerationInfo` | 代信息 |

### 读取函数

| 符号 | 说明 |
|------|------|
| `read_package_summary` | 读取包摘要 |
| `read_name_table` | 读取名称表 |
| `read_import_map` | 读取导入表 |
| `read_export_map` | 读取导出表 |
| `detect_blueprint` | 检测蓝图 |

### 辅助函数

| 符号 | 说明 |
|------|------|
| `build_imports_list` | 构建导入列表 |
| `get_asset_class` | 获取资产类名 |
| `resolve_class_name` | 解析类名 |
| `detect_blueprint_generated_class` | 检测蓝图生成类 |
| `detect_circular_deps` | 检测循环依赖 |
| `validate_package_index` | 验证包索引 |

### 图序列化

| 符号 | 说明 |
|------|------|
| `read_ue_graph` | 读取 UE 图 |
| `read_ue_graph_node` | 读取图节点 |
| `read_ue_graph_pin` | 读取图 Pin |
| `read_ed_graph_pin_type` | 读取 ED 图 Pin 类型 |
| `read_fmember_reference` |读取 FMemberReference |
| `create_node_from_archive` | 从 Archive 创建节点 |

### 节点类型读取器

| 符号 | 说明 |
|------|------|
| `read_k2node_call_function` | 读取函数调用节点 |
| `read_k2node_event` | 读取事件节点 |
| `read_k2node_knot` | 读取 Knot 节点 |
| `read_edgraph_node_comment` | 读取节点注释 |
| `read_k2node_enhanced_input` | 读取增强输入节点 |
| `read_k2node_functionentry` | 读取函数入口节点 |

### PropertyTag 读取

| 符号 | 说明 |
|------|------|
| `read_property_tag` | 读取 PropertyTag |
| `parse_ctrl_flags` | 解析控制标志 |
| `parse_ue511_ctrl_flags` | 解析 UE5.11 控制标志 |

### 对象资源辅助

| 符号 | 说明 |
|------|------|
| `find_main_blueprint_generated_class` | 查找主蓝图生成类 |
| `resolve_parent_class` | 解析父类 |
| `resolve_class_name_with_linker` | 带 Linker 解析类名 |
| `get_asset_class_with_linker` | 带 Linker 获取资产类 |
| `detect_blueprint_with_linker` | 带 Linker 检测蓝图 |
| `resolve_parent_class_with_linker` | 带 Linker 解析父类 |
| `read_soft_object_paths` | 读取软对象路径 |

## 核心数据模型 (models)

### 图模型

| 符号 | 说明 |
|------|------|
| `FEdGraphPinType` | 图 Pin 类型结构 |
| `UEdGraphPin` | 图 Pin 数据模型 |
| `UEdGraphNode` | 图节点数据模型 |
| `UEdGraph` | 图数据模型 |
| `FMemberReference` | 成员引用结构 |

### 节点类型

| 符号 | 说明 |
|------|------|
| `K2NodeCallFunction` | 函数调用节点 |
| `K2NodeEvent` | 事件节点 |
| `K2NodeKnot` | Knot 节点 |
| `EdGraphNodeComment` | 注释节点 |
| `K2NodeEnhancedInputAction` | 增强输入动作节点 |
| `K2NodeFunctionEntry` | 函数入口节点 |

### 解析结果

| 符号 | 说明 |
|------|------|
| `ParseResult` | 解析结果容器 |
| `StatusInfo` | 状态信息 |

### 蓝图元数据

| 符号 | 说明 |
|------|------|
| `BlueprintMetadata` | 蓝图元数据 |
| `BlueprintVariable` | 蓝图变量 |
| `BlueprintFunction` | 蓝图函数 |
| `BlueprintEvent` | 蓝图事件 |
| `FunctionParameter` | 函数参数 |
| `MulticastDelegate` | 多播委托 |

### 属性数据模型

| 符号 | 说明 |
|------|------|
| `PropertyTag` | 属性标签 |
| `PropertyTypeName` | 属性类型名枚举 |
| `PropertyValue` | 属性值基类 |
| `SoftObjectPathValue` | 软对象路径值 |
| `AdvancedPropertyValue` | 高级属性值 |
| `StructValue` | 结构体值 |
| `MapValue` | 映射值 |
| `SetValue` | 集合值 |
| `EnumValue` | 枚举值 |
| `TextValue` | 文本值 |
| `DelegateValue` | 委托值 |

### 变换数据

| 符号 | 说明 |
|------|------|
| `VectorValue` | 向量值 |
| `RotatorValue` | 旋转值 |
| `ScaleValue` | 缩放值 |
| `format_transform_value` | 格式化变换值 |

## 映射模块 (mappings)

| 符号 | 说明 |
|------|------|
| `TypeMappingsProvider` | 类型映射提供者接口 |
| `UsmapParser` | .usmap 文件解析器 |
| `JmapParser` | .jmap 文件解析器 |
| `TypeMappings` | 类型映射容器 |
| `StructMapping` | 结构体映射 |
| `PropertyType` | 属性类型枚举 |
| `PropertyInfo` | 属性信息 |

## 解析器模块 (parsers)

### 属性解析函数

| 符号 | 说明 |
|------|------|
| `parse_property_value` | 通用属性值解析分发 |
| `parse_properties_from_export` | 从导出解析属性列表 |
| `parse_bool_property` | 布尔属性 |
| `parse_int_property` | 整型属性 |
| `parse_float_property` | 浮点属性 |
| `parse_str_property` | 字符串属性 |
| `parse_name_property` | 名称属性 |
| `parse_object_property` | 对象属性 |
| `parse_soft_object_property` | 软对象属性 |
| `parse_array_property` | 数组属性 |
| `parse_struct_property` | 结构体属性 |
| `parse_map_property` | 映射属性 |
| `parse_set_property` | 集合属性 |
| `parse_enum_property` | 枚举属性 |
| `parse_text_property` | 文本属性 |
| `parse_delegate_property` | 委托属性 |

### 新增属性类型解析

| 符号 | 说明 |
|------|------|
| `parse_uint16_property` | UInt16 属性 |
| `parse_uint32_property` | UInt32 属性 |
| `parse_uint64_property` | UInt64 属性 |
| `parse_utf8_str_property` | UTF-8 字符串属性 |
| `parse_weak_object_property` | 弱对象属性 |
| `parse_lazy_object_property` | 惰性对象属性 |
| `parse_class_property` | 类属性 |
| `parse_soft_class_property` | 软类属性 |
| `parse_asset_object_property` | 资产对象属性 |
| `parse_multicast_delegate_property` | 多播委托属性 |
| `parse_multicast_inline_delegate_property` | 内联多播委托属性 |
| `parse_multicast_sparse_delegate_property` | 稀疏多播委托属性 |
| `parse_interface_property` | 接口属性 |
| `parse_field_path_property` | 字段路径属性 |
| `parse_optional_property` | 可选属性 |
| `parse_verse_string_property` | Verse 字符串属性 |
| `parse_verse_class_property` | Verse 类属性 |
| `parse_verse_function_property` | Verse 函数属性 |
| `parse_verse_dynamic_property` | Verse 动态属性 |
| `parse_verse_cell_property` | Verse Cell 属性 |
| `parse_verse_value_property` | Verse 值属性 |
| `parse_ansi_str_property` | ANSI 字符串属性 |
| `parse_double_property` | Double 属性 |
| `parse_guid_property` | GUID 属性 |

### CustomProperty 注册表

| 符号 | 说明 |
|------|------|
| `CUSTOM_PROPERTY_HANDLERS` | 自定义属性处理器注册表 |
| `CustomPropertyContext` | 自定义属性上下文 |
| `register_custom_property` | 注册自定义属性处理器 |
| `handle_custom_property` | 处理自定义属性 |

### 辅助函数

| 符号 | 说明 |
|------|------|
| `get_struct_size` | 获取结构体大小 |
| `_extract_struct_type_from_tag` | 从标签提取结构体类型 |
| `_extract_map_types_from_tag` | 从标签提取映射类型 |
| `_extract_set_type_from_tag` | 从标签提取集合类型 |
| `_extract_enum_type_from_tag` | 从标签提取枚举类型 |
| `resolve_name_from_index` | 从索引解析名称 |
| `read_validated_count` | 读取验证的计数 |
| `make_enum_value` | 创建枚举值 |
| `extract_inner_from_tag` | 从标签提取内部类型 |

### 蓝图辅助

| 符号 | 说明 |
|------|------|
| `parse_property_flags_to_labels` | 解析属性标志为标签 |
| `read_blueprint_variable` | 读取蓝图变量 |
| `parse_default_value` | 解析默认值 |
| `format_variable_type` | 格式化变量类型 |

## 蓝图模块 (blueprint)

| 符号 | 说明 |
|------|------|
| `extract_blueprint_variables` | 提取蓝图变量 |
| `parse_component_transform` | 解析组件变换 |
| `extract_blueprint_metadata` | 提取蓝图元数据 |
| `extract_components` | 提取组件 |
| `extract_component_transforms` | 提取组件变换列表 |
| `parse_vector_value` | 解析向量值 |
| `parse_rotator_value` | 解析旋转值 |
| `parse_scale_value` | 解析缩放值 |

## 主解析管线

| 符号 | 说明 |
|------|------|
| `parse_package` | 解析包入口 |
| `parse_uasset` | 解析 .uasset 入口 |
| `parse_uasset_with_linker` | 带 Linker 解析入口 |

## 包管理 (package)

| 符号 | 说明 |
|------|------|
| `PackageBundle` | 包束容器 |
| `PackageProvider` | 包提供者基类 |
| `FileSystemPackageProvider` | 文件系统包提供者 |
| `PakPackageProvider` | PAK 包提供者 |
| `IoStorePackageProvider` | IoStore 包提供者 |
| `open_package_bundle` | 打开包束 |

## 原始文件解析 (raw)

| 符号 | 说明 |
|------|------|
| `RawFileResult` | 原始文件解析结果 |
| `parse_raw_file` | 解析原始文件 |
| `parse_json_descriptor` | 解析 JSON 描述符 |
| `parse_ini_file` | 解析 INI 文件 |
| `parse_locres` | 解析 LocRes 本地化资源 |
| `parse_locmeta` | 解析 LocMeta 本地化元数据 |
| `parse_audio_metadata` | 解析音频元数据 |

## 图解析模块 (graph)

| 符号 | 说明 |
|------|------|
| `extract_blueprint_graphs` | 提取蓝图图数据 |
| `build_execution_flow_entries` | 构建执行流条目 |
| `build_data_flows` | 构建数据流 |
| `build_connections_map` | 构建连接映射 |
| `format_graphs_json` | 格式化图为 JSON |
| `build_execution_chains` | 构建执行链 |
| `format_pin_ref` | 格式化 Pin 引用 |
| `_derive_node_name` | 推导节点名称 |
| `build_function_graphs` | 构建函数图 |

## ~~格式化模块 (formatters)~~ — 已废弃

> [!WARNING] 已废弃
> `formatters/` 目录已清空，所有格式化功能已迁移到 `renderers/` 系统。
> 请使用 `parse_single(format="json")` 或 `parse_single(format="markdown")` 替代。

## Kismet 字节码模块 (kismet)

### 枚举

| 符号 | 说明 |
|------|------|
| `EExprToken` | 表达式令牌枚举 |
| `ECastToken` | 转换令牌枚举 |
| `EScriptInstrumentationType` | 脚本仪器化类型 |
| `EBlueprintTextLiteralType` | 蓝图文本字面量类型 |
| `EAutoRtfmStopTransactMode` | 自动 RTFM 停止事务模式 |

### 核心类型

| 符号 | 说明 |
|------|------|
| `KismetExpression` | Kismet 表达式基类 |
| `KismetExpressionT` | Kismet 表达式泛型 |
| `EXPR_CLASS_MAP` | 表达式类映射 |
| `FKismetPropertyPointer` | Kismet 属性指针 |
| `FFieldPath` | 字段路径 |
| `FKismetArchive` | Kismet 字节码 Archive |
| `USTRUCT_TYPES` | 结构体类型集合 |
| `reset_bpgc_cache` | 重置 BPGC 缓存 |

### 字节码提取

| 符号 | 说明 |
|------|------|
| `extract_bytecode_bytes` | 提取字节码字节 |
| `parse_bytecode_stream` | 解析字节码流 |
| `extract_and_parse` | 提取并解析 |

### 翻译器

| 符号 | 说明 |
|------|------|
| `KismetTranslator` | Kismet → C++ 翻译器 |
| `MathFunctionCleaner` | 数学函数清理器 |
| `TypeRegistry` | 类型注册表 |
| `line_cpp` | 生成 C++ 代码行 |
| `UE_TYPE_MAP` | UE 类型映射 |
| `FunctionBodyBuilder` | 函数体构建器 |
| `to_function_body` | 转换为函数体 |
| `StructuredControlFlow` | 结构化控制流 |
| `StructuredBlock` | 结构化块 |

### 反编译管线

| 符号 | 说明 |
|------|------|
| `KismetDecompiledResult` | 反编译结果 |
| `decompile_uasset` | 反编译整个 uasset |
| `decompile_single_function` | 反编译单个函数 |

## ~~已移除模块~~

> [!WARNING] 已移除
> 以下模块已在 0.4.1 整体删除，当前版本中不存在：
> - `agent/` — 请通过 `parse_single(format="cpp_skeleton")` 获取 C++ 输出
> - `n2c/` — N2C 中间格式不再提供
> - `exporter/` — 请使用 `parse_single()` + 渲染器系统
> - `formatters/` — 已清空，所有功能迁移到 `renderers/` 系统

## C++ 代码生成 (cpp_gen)

### IR 类型

| 符号 | 说明 |
|------|------|
| `CppProperty` | C++ 属性 IR |
| `CppHeaderMeta` | C++ 头文件元数据 |
| `CppClassIR` | C++ 类 IR |
| `CppMethodIR` | C++ 方法 IR |
| `CppCallParameter` | C++ 调用参数 |
| `CppCallStatement` | C++ 调用语句 |

### 格式化函数

| 符号 | 说明 |
|------|------|
| `format_cpp_class_json` | 格式化 C++ 类为 JSON |
| `format_cpp_header` | 格式化 C++ 头文件 |
| `format_cpp_call_statements` | 格式化 C++ 调用语句 |
| `format_cpp_default_value` | 格式化 C++ 默认值 |
| `format_cpp_transform` | 格式化 C++ 变换 |
| `format_cpp_component_init` | 格式化 C++ 组件初始化 |
| `format_cpp_input_action_load` | 格式化 C++ 输入动作加载 |
| `build_constructor_sections` | 构建构造函数段 |
| `format_cpp_constructor` | 格式化 C++ 构造函数 |
| `extract_cpp_class_skeleton` | 提取 C++ 类骨架 |
| `extract_cpp_constructor` | 提取 C++ 构造函数 |

### 类型映射

| 符号 | 说明 |
|------|------|
| `UE_TO_CPP_TYPE_MAP` | UE → C++ 类型映射 |
| `ENGINE_CLASS_PATHS` | 引擎类路径 |
| `ue_path_to_cpp_type` | UE 路径转 C++ 类型 |
| `ue_package_path_to_cpp_class` | UE 包路径转 C++ 类 |
| `CPF_TO_UPROPERTY_MAP` | CPF → UPROPERTY 映射 |
| `cpf_flags_to_uproperty_marks` | CPF 标志转 UPROPERTY 标记 |

## 版本管理 (versioning)

| 符号 | 说明 |
|------|------|
| `VersionContainer` | 版本容器 |
| `build_version_container` | 构建版本容器 |
| `EUEVersion` | UE 版本枚举 |

## 链接器模块 (link)

| 符号 | 说明 |
|------|------|
| `PackageLinker` | 包链接器（两阶段对象图重建） |
| `UObjectInstance` | UObject 实例 |
| `LinkerParseResult` | 链接器解析结果 |

## PAK 模块 (pak)

### 常量与标志

| 符号 | 说明 |
|------|------|
| `PAK_FILE_MAGIC` | PAK 文件魔数 |
| `PakFileVersion` | PAK 文件版本枚举 |
| `ECompressionFlags` | 压缩标志枚举 |
| `Flag_Encrypted` | 加密标志 |
| `Flag_Deleted` | 删除标志 |
| `MaxNumCompressionMethods` | 最大压缩方法数 |
| `PAK_INFO_SIZES` | PAK 信息大小常量 |

### 数据结构

| 符号 | 说明 |
|------|------|
| `FPakCompressedBlock` | 压缩块 |
| `FPakEntry` | PAK 条目 |
| `FPakInfo` | PAK 信息头 |
| `FPakDirectoryEntry` | PAK 目录条目 |

### 读取与解压

| 符号 | 说明 |
|------|------|
| `read_fstring` | 读取 FString |
| `decompress_block` | 解压块 |
| `decompress_entry` | 解压条目 |
| `PakFileReader` | PAK 文件读取器 |

## IoStore 模块 (iostore)

| 符号 | 说明 |
|------|------|
| `IoStoreReader` | IoStore 容器读取器 |
| `FIoChunkId` | Io Chunk ID 结构 |
| `FIoOffsetAndSize` | 偏移与大小结构 |

## Bulk Data 模块 (bulk)

| 符号 | 说明 |
|------|------|
| `FBulkDataHeader` | BulkData 头部结构 |
| `BulkDataFlags` | BulkData 标志枚举 |

## UObject 类型体系 (objects)

> [!WARNING] 已废弃
> `bulk/` 和 `objects/` 模块已废弃，0.3.6 已从公共 API 移除（保留向后兼容导出）。`parsers/asset_types/` 将在 0.4.0 移除。

| 符号 | 说明 |
|------|------|
| `UObject` | UObject 基类 |
| `ObjectTypeRegistry` | 对象类型注册表 |
| `UStaticMesh` | StaticMesh 导出类型 |
| `USkeletalMesh` | SkeletalMesh 导出类型 |
| `UTexture2D` | Texture2D 导出类型 |
| `UMaterial` | Material 导出类型 |
| `UMaterialInstance` | MaterialInstance 导出类型 |

## 废弃模块

| 模块 | 状态 | 说明 |
|------|------|------|
| `bulk/` | 已废弃 | 0.3.6 从公共 API 移除 |
| `objects/` | 已废弃 | 0.3.6 从公共 API 移除 |
| `parsers/asset_types/` | 已废弃 | 0.4.0 将移除 |
