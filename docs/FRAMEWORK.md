# uasset-read 项目框架索引

> Unreal Engine .uasset 文件解析器 — 让 AI 代理在不依赖 UE 编辑器的情况下读取蓝图内容。
> Python 3.10+，零运行时依赖，setuptools + pytest。
>
> 详细英文架构文档见 [ARCHITECTURE.md](ARCHITECTURE.md)（分层架构、设计决策、扩展指南）。

## 模块索引

### 核心层（基础 IO / 序列化）

| 模块 | 文件 | 详细功能 |
|------|------|----------|
| **FArchive** | `archive.py` | 镜像 UE FArchive 的二进制读取器。支持：① mmap 大文件映射（≥MMAP_THRESHOLD 自动启用，fallback 到标准文件 IO） ② 字节序检测与交换（`set_byte_swapping()`） ③ 全偏移验证（`validate_offset` / `validate_size`） ④ 类型读取：`read_u8/i16/u16/i32/u32/i64/u64/f32/f64/bool/bool_1byte` ⑤ `read_fstring()` — UTF-8/UTF-16 长度前缀字符串，null-terminated，内部 null 截断检测，指针回退保护 ⑥ `read_name()` — FName 索引+实例编号查名称表 ⑦ `peek_i32()` — 不移动位置的预读 |
| **Serializers** | `serializers/` | UE Package 序列化结构读取。包含：`read_package_summary()` — 解析 PackageFileSummary 头（版本 / ImportMap 偏移 / ExportMap 偏移 / 标志等）；`read_name_table()` — FName 名称表；`read_import_map()` / `read_export_map()` — 导入导出表；`PackageIndex` — 有符号索引区分 Import(-N) / Export(+N) / Null(0)；`detect_blueprint()` / `detect_blueprint_generated_class()` — 通过 ObjectExport ClassIndex 判断是否为蓝图资产；`resolve_class_name()` — PackageIndex → 类名解析；`find_main_blueprint_generated_class()` — 定位主 BPGC 导出；`read_ue_graph()` / `read_ue_graph_node()` / `read_ue_graph_pin()` — 图 / 节点 / Pin 序列化读取；`read_k2node_*` — 6 种特定节点类型专用读取器（CallFunction / Event / Knot / EnhancedInput / FunctionEntry / Comment） |
| **Constants** | `constants.py` | UE 引擎常量：① 文件魔数 `PACKAGE_FILE_TAG` / 字节序检测 ② 版本阈值 `UE5_VERSION_MIN` / `UE5_LEGACY_VERSION` ③ 数量上限 `MAX_NAME_COUNT` / `MAX_IMPORT_COUNT` / `MAX_EXPORT_COUNT` ④ mmap 阈值 `MMAP_THRESHOLD` ⑤ PropertyTag 标志位（`PROP_TAG_HAS_ARRAY_INDEX` / `PROP_TAG_HAS_PROPERTY_GUID` / `PROP_TAG_HAS_EXTENSIONS` / `PROP_TAG_HAS_BINARY_OR_NATIVE` 等） ⑥ Package Flags（`PKG_Cooked` / `PKG_UnversionedProperties` / `PKG_FilterEditorOnly`） ⑦ UE5 序列化版本偏移和特性标志（SCRIPT_SERIALIZATION_OFFSET / PROPERTY_TAG_EXTENSION / LARGE_WORLD_COORDINATES 等 20+ 标志） ⑧ Framework/UE5MainStream/Release Version GUID 和特性标志 ⑨ 控制流节点类型集合 `CONTROL_FLOW_NODES` / 起始事件类型 `START_EVENT_TYPES` / 分支映射 `BRANCH_TYPE_MAP` ⑩ CPF 属性标志（CPF_Edit / CPF_BlueprintVisible / CPF_InstancedReference 等 9 个） ⑪ 图解析边界常量（MAX_PINS_PER_NODE / MAX_NODES_PER_GRAPH / MAX_LINKEDTO_PER_PIN） ⑫ FString 长度上限 `MAX_FSTRING_LENGTH` |
| **Exceptions** | `exceptions.py` | 异常体系：`UAssetError`（基类） → `VersionError`（版本不匹配） / `ParseError`（解析失败，支持 `partial_result` 优雅降级） / `ErrorContext`（错误上下文包装） |

### 数据模型层

| 模块 | 文件 | 详细功能 |
|------|------|----------|
| **Core Models** | `models/core.py` | UE 蓝图核心数据结构（dataclass）。`FEdGraphPinType` — Pin 类型（pin_category / subcategory / container_type / is_map_key/value / is_reference / is_weak_pointer / is_const / is_uobject_wrapper）；`UEdGraphPin` — 完整 Pin 结构（基础信息 + PinType + 默认值 + 连接引用 linked_to_raw + 显示属性 + owning_node_index + source_index + persistent_guid），支持 linker 模式下的 `linked_to_objects` 解析后引用；`UEdGraphNode` — 节点基类（node_guid / pos_x/y / comment / pins[] / class_name / node_data），提供 `from_archive()` 和 `from_archive_with_linker()` 两种构造入口；`UEdGraph` — 图容器（graph_name / graph_class / schema / nodes[] / graph_guid / b_editable）；`FMemberReference` — 成员引用（member_parent / member_name / member_guid / b_self_context） |
| **Node Types** | `models/node_types.py` | 6 种特定 K2 节点类型 dataclass。`K2NodeCallFunction` — function_reference(FMemberReference) + bDefaultsToPure + parameters；`K2NodeEvent` — event_reference + delegate_reference + bOverrideFunction；`K2NodeKnot` — 无额外字段，用于数据流穿透；`K2NodeEnhancedInputAction` — input_action_path / b_trigger_on_pressed / b_trigger_on_released；`K2NodeFunctionEntry` — function_reference；`EdGraphNodeComment` — comment_text |
| **Properties** | `models/properties.py` | 属性数据模型。`PropertyTag` — 属性标签（name / type / flags / array_index / property_guid / extensions）；`PropertyValue` — 基础属性值；`AdvancedPropertyValue` — 高级属性值包装；`StructValue` / `MapValue` / `SetValue` / `EnumValue` / `TextValue` / `DelegateValue` — 对应 6 种复合/特殊属性类型的值容器 |
| **Blueprint** | `models/blueprint.py` | 蓝图元数据模型。`BlueprintMetadata` — 蓝图总览（parent_class / variables[] / functions[] / events[] / components[] / graphs[]）；`BlueprintVariable` — 变量（name / type / default_value / flags / tooltip / category）；`BlueprintFunction` — 函数（name / return_type / parameters[] / b_is_static / b_is_virtual）；`BlueprintEvent` — 事件（name / delegate_type / parameters[]）；`FunctionParameter` — 函数参数（name / param_type / is_input / default_value）；`MulticastDelegate` — 多播委托 |
| **Transforms** | `models/transforms.py` | 变换值类。`VectorValue` / `RotatorValue` / `ScaleValue` — X/Y/Z 三分量 dataclass；`format_transform_value()` — 统一格式化为可读字符串 |
| **Result** | `models/result.py` | `ParseResult` — 主解析结果（summary / name_map / import_map / export_map / graphs[] / blueprint / errors / warnings / is_success / mmap_used / mmap_warning / decompiled_functions / components / imports / soft_references / circular_deps）；`StatusInfo` — 状态信息 |

### 解析层

| 模块 | 文件 | 详细功能 |
|------|------|----------|
| **Property Parser** | `parsers/property_parser.py` | 属性解析分派器。`parse_properties_from_export()` — 从 Export 中循环读取 PropertyTag → 按 type 分派到对应解析器 → 返回 PropertyValue 列表；`parse_property_value()` — 单属性分派入口，根据 PropertyTag.type 选择 Bool/Byte/Int/Float/Str/Name/Object/SoftObject/Array/Struct/Map/Set/Enum/Text/Delegate 共 14 种解析路径 |
| **Property Types** | `parsers/property_types.py` | 14 种具体属性类型解析器：`parse_bool_property` / `parse_int_property` / `parse_float_property` / `parse_str_property` / `parse_name_property` / `parse_object_property` / `parse_soft_object_property` / `parse_array_property`（递归解析 InnerType）/ `parse_struct_property`（读取 InnerType 后递归）/ `parse_map_property`（Key/Value 类型分离解析）/ `parse_set_property` / `parse_enum_property` / `parse_text_property`（FText 三要素：HistoryType/Text/Flags）/ `parse_delegate_property`。以及 `parse_default_value()` — Pin 默认值解析，`format_variable_type()` — PinType → 人类可读类型字符串 |

### 蓝图层

| 模块 | 文件 | 详细功能 |
|------|------|----------|
| **Variable Extractor** | `blueprint/variable_extractor.py` | `extract_blueprint_variables()` — 遍历 ExportMap 中 UStruct 类型的 properties，提取 BlueprintVariable 列表；`read_blueprint_variable()` — 从单个 property 解析变量名/类型/默认值/CPF 标志；`parse_property_flags_to_labels()` — CPF 标志位 → 人类可读标签列表（如 CPF_Edit + CPF_BlueprintVisible → ["Edit", "BlueprintVisible"]）；`extract_blueprint_metadata()` — 提取蓝图总览：parent_class（通过 BPGC 的 SuperField 链）/ variables / functions / events，支持 linker 模式下的精确类名解析，接受 graphs 参数填充函数签名 |
| **Transform Parser** | `blueprint/transform_parser.py` | `extract_component_transforms()` — 从 properties 中查找 RelativeLocation/RelativeRotation/RelativeScale3D 等变换属性，解析为 VectorValue/RotatorValue/ScaleValue；`parse_vector_value()` / `parse_rotator_value()` / `parse_scale_value()` — 从 StructValue 中提取 XYZ 分量；`format_transform_value()` — 格式化为 "(X, Y, Z)" 字符串 |
| **Component Extractor** | `blueprint/component_extractor.py` | `extract_components()` — 从 ExportMap 中提取 SceneComponent 和 ActorComponent 实例列表，构建组件层级关系 |

### 图解析层（Graph）

| 模块 | 文件 | 详细功能 |
|------|------|----------|
| **Parser** | `graph/parser.py` | `extract_blueprint_graphs()` — 从 ExportMap 中识别 UEdGraph 类型导出，逐个调用 `UEdGraph.from_archive()` 反序列化，返回 UEdGraph 列表。跳过非图类型和空图 |
| **Flow Builder** | `graph/flow_builder.py` | 图流构建核心。① `build_connections_map()` — 从所有 Pin 的 linked_to_raw 构建连接映射，normalize 双向引用（input/output 两端都可能出现），输出 `{from: {node, pin}, to: {node, pin}}` 格式，支持 name/guid 两种模式 ② `build_execution_flows()` — 从 START_EVENT_TYPES 节点（Event / EnhancedInputAction / VariableSet / CustomEvent）开始，沿 exec pin 追踪执行路径，返回 `{start_event, nodes[]}` 列表，支持 EnhancedInputAction 多触发时机（Started/Triggered/Completed）独立追踪 ③ `build_data_flows()` — 从非 exec pin 提取数据传递关系，返回 `{source, target}` 列表 ④ `build_graphs_summary()` — 综合执行流 / 连接 / 数据流构建图摘要 ⑤ `format_graphs_json()` — 完整 JSON 格式化（nodes / connections / execution_chains / data_flows） ⑥ `format_node_dict()` — 单节点 JSON 格式化，集成 N2C Processor Registry 提取语义信息 ⑦ `build_function_graphs()` — 为 FunctionEntry 节点构建函数级执行流 + 签名 + 数据流内嵌标注 ⑧ `_trace_data_source()` — 反向数据源追踪：从 CallFunction input pin 穿透 Knot 链，找到数据源（Pure 函数 / FunctionEntry 参数 / self 引用 / 边界节点） ⑨ `_resolve_knot_chain()` — Knot 链穿透，循环检测 ⑩ `is_function_graph()` — 判断图是否为函数图（含 FunctionEntry → 函数图，含 Event → 事件图） ⑪ `is_boundary_node()` — 数据流边界节点检测（DATA_BOUNDARY_NODES + self 检测） ⑫ 字符串 sanitization（null / 控制字符清理） |
| **Chain Builder** | `graph/chain_builder.py` | `build_execution_chains()` — Phase 71 执行流链式表达：将 build_execution_flows() 的逐节点序列压缩为链式结构 `{start_event, chains: [{chain_id, nodes: [...]}]}`，减少冗余；`build_execution_chains_from_flows()` — N2C 兼容版本，从外部 flows 输入构建链 |
| **Pin Trace** | `graph/pin_trace.py` | `write_pin_trace_report()` — 生成 Pin 连接追踪诊断报告；`write_phase75_diagnostic()` — Phase 75 字段级诊断基线 |

### 链接器层（Link）

| 模块 | 文件 | 详细功能 |
|------|------|----------|
| **Linker** | `link/linker.py` | `PackageLinker` — 镜像 UE FLinkerLoad 的两阶段加载器。Phase 1 `link()`：① `_create_import_instances()` — 为每个 ImportMap 条目创建 UObjectInstance（PackageIndex = -(N+1)） ② `_create_export_instances()` — 为每个 ExportMap 条目创建 UObjectInstance（PackageIndex = N+1，含 serial_offset/serial_size） ③ `build_outer_tree()` — 解析 OuterIndex → 构建父子层级 ④ `_collect_root_objects()` — 收集无 Outer 的根对象。Phase 2 `preload(index)` — 按需反序列化：seek 到 serial_offset → 调用 `parse_properties_from_export()` → 缓存到 `instance.serialized_properties`。`resolve_package_index()` — PackageIndex → UObjectInstance 解析（正数查 export / 负数查 import）；`get_children()` — 获取指定对象的所有子对象 |
| **Object Instance** | `link/object_instance.py` | `UObjectInstance` — 对象实例 dataclass。字段：package_index / object_name / object_class / class_package / outer_index / outer（resolved）/ is_import / serial_offset / serial_size / _preloaded / serialized_properties / linker 引用。`get_full_name()` — 拼接 Outer 链生成 "PackageName.ObjectName" 格式；`get_path_name()` — 完整路径名 |
| **Result** | `link/result.py` | `LinkerParseResult` — 带 linker 的解析结果（继承 ParseResult 字段 + linker / all_objects / root_objects） |

### Kismet 字节码层

| 模块 | 文件 | 详细功能 |
|------|------|----------|
| **Tokens** | `kismet/tokens.py` | Kismet 字节码 Token 枚举。`EExprToken` — 表达式 Token（EX_LocalVariable / EX_InstanceVariable / EX_DefaultVariable / EX_CallFunction / EX_Return / EX_Jump / EX_JumpIfNot / EX_CallMulticastDelegate 等 60+ 种）；`ECastToken` — 类型转换 Token；`EScriptInstrumentationType` — 脚本插装类型；`EBlueprintTextLiteralType` — FText 字面量类型；`EAutoRtfmStopTransactMode` — RTFM 事务模式 |
| **Archive** | `kismet/archive.py` | `FKismetArchive` — Kismet 专用字节流读取器。从 UStruct 的 ScriptBytecode 偏移开始读取，支持 Token 流式解析、跳转偏移计算、表达式树构建 |
| **Bytecode Extractor** | `kismet/bytecode_extractor.py` | `extract_bytecode_bytes()` — 从 UStruct Export 中提取 ScriptBytecode 原始字节流；`parse_bytecode_stream()` — 将字节流解析为 EExprToken 序列；`extract_and_parse()` — 一键提取 + 解析；`USTRUCT_TYPES` — 包含字节码的 UStruct 类型集合（Ubergraph / Function / Macro 等）；`reset_bpgc_cache()` — BPGC fallback 缓存重置 |
| **BPGC Bytecode** | `kismet/bpgc_bytecode.py` | BPGC（BlueprintGeneratedClass）fallback 字节码提取。当标准 UStruct 路径不可用时，从 BPGC 的 FuncMap / SignatureMap 中提取函数字节码 |
| **Property Pointer** | `kismet/property_pointer.py` | `FKismetPropertyPointer` — Kismet 中属性指针（Legacy 和 New 两种格式）；`FFieldPath` — 字段路径（用于 UE5 的属性引用） |
| **Expressions** | `kismet/expressions/` | 16 种子表达式类型实现（每个文件一个类别）。`base.py` — `KismetExpression` 基类（token / value / children / to_cpp() 抽象方法）；`context.py` — 上下文表达式（EX_Self / EX_ObjectConstReference）；`variables.py` — 变量访问（EX_LocalVariable / EX_InstanceVariable / EX_DefaultVariable / EX_PushExecutionFlow）；`functions.py` — 函数调用（EX_CallFunction / EX_CallMulticastDelegate / EX_InterfaceCall）；`literals.py` — 字面量（EX_IntOne / EX_NoObject / EX_SkipOffsetConst / EX_Self）；`casts.py` — 类型转换（EX_DynamicCast / EX_CrossInterfaceCast / EX_InterfaceToObjectCast）；`control_flow.py` — 控制流（EX_Return / EX_Jump / EX_JumpIfNot / EX_ComputedJump）；`assignments.py` — 赋值（EX_Let / EX_LetObj / EX_LetWeakObjPtr / EX_LetBool）；`string_consts.py` — 字符串常量（EX_UnicodeTextConst / EX_StringConst / EX_NameConst）；`vector_consts.py` — 向量常量（EX_Vector / EX_Rotation / EX_TransformConst）；`containers.py` — 容器（EX_SetArray / EX_ArrayConst / EX_MapConst / EX_SetConst）；`structs.py` — 结构体（EX_StructConst / EX_StructMemberGet / EX_StructMemberSet）；`delegates.py` — 委托（EX_DelegateSet / EX_DelegateGet / EX_AddMulticastDelegate）；`rtfm.py` — RTFM 事务（EX_AutoRtfmStopTransact）；`special.py` — 特殊表达式（EX_Breakpoint / EX_Instrumentation / EX_WireTracepoint）；`__init__.py` — `EXPR_CLASS_MAP` — EExprToken → KismetExpression 子类映射表 |
| **Translator** | `kismet/translator.py` | Kismet → C++ 伪代码翻译器。`KismetTranslator` — 遍历表达式树，调用每个 Expression.to_cpp() 拼接 C++ 代码；`MathFunctionCleaner` — 清理 UE 数学函数名（如 "K2_Atan2" → "FMath::Atan2"）；`TypeRegistry` — UE 类型名 → C++ 类型名映射注册表；`line_cpp()` — 单行 C++ 代码格式化；`UE_TYPE_MAP` — 预定义 UE 类型映射 |
| **Body Builder** | `kismet/body_builder.py` | `FunctionBodyBuilder` — 从 Kismet 表达式序列构建 C++ 函数体。处理变量声明、返回值、控制流块嵌套；`to_function_body()` — 便捷函数，输入表达式列表 → 输出 C++ 函数体字符串 |
| **Structured Flow** | `kismet/structured_flow.py` | 控制流结构化。`StructuredControlFlow` — 将扁平的 Kismet Token 序列（含 Jump/JumpIfNot）转换为结构化控制流（if/else/while/for/do-while/switch）；`StructuredBlock` — 结构化块基类（SequenceBlock / IfBlock / WhileBlock / DoWhileBlock / ForBlock / SwitchBlock） |
| **Result** | `kismet/result.py` | `KismetDecompiledResult` — 反编译结果（function_name / parameters[] / return_type / body_cpp / warnings / bytecode_hex / expression_tree[] / structured_flow） |
| **Pipeline** | `kismet/pipeline.py` | `decompile_uasset()` — 完整反编译管线：定位 UStruct → 提取字节码 → 解析表达式 → 翻译 C++；`decompile_single_function()` — 单个 UStruct 的反编译入口，tolerant 模式（失败不阻断主管线） |
| **Kismet Init** | `kismet/__init__.py` | 统一导出所有 Kismet 符号：Token 枚举 / 表达式类 / 映射表 / 提取器 / 翻译器 / 管线 |

### N2C 中间格式层

| 模块 | 文件 | 详细功能 |
|------|------|----------|
| **Schema** | `n2c/schema.py` | N2C（Node-to-Code）中间格式 dataclass。`N2CStruct` — 顶级结构（graphs[]）；`N2CGraph` — 图（name / type / nodes[]）；`N2CNode` — 节点（id / type / pins[] / definition）；`N2CPin` — Pin（id / name / direction / type / default_value） |
| **Serializer** | `n2c/serializer.py` | `to_n2c_json()` — N2CStruct → JSON 序列化（含 token 计数估算）；`from_n2c_json()` — JSON → N2CStruct 反序列化；`_estimate_token_count()` — 估算 JSON 的 LLM token 数量 |
| **Validation** | `n2c/validation.py` | `N2C_JSON_SCHEMA` — JSON Schema 定义（用于验证 N2C 输出）；`validate_n2c_json()` — JSON 校验，返回错误列表 |
| **Type System** | `n2c/type_registry.py`, `n2c/type_data.py` | `N2CNodeTypeRegistry` — 节点类型注册表（UE class_name → N2CNodeType 映射）；N2C 类型数据定义 |
| **Node Types** | `n2c/node_types.py` | `N2CNodeType` — 节点类型枚举（CALL_FUNCTION / EVENT / KNOT / FLOW_CONTROL / VARIABLE / CAST / FUNCTION_ENTRY / FALLBACK 等） |
| **Processors** | `n2c/processors/` | 节点处理器架构（Processor 模式）。`__init__.py` — `register_all_processors()` 注册所有处理器；`call_function.py` — K2Node_CallFunction → 提取函数名 / 参数列表 / Pure 标志；`event.py` — K2Node_Event → 提取事件名 / Delegate 类型；`flow_control.py` — 控制流节点（Branch / Sequence / DoOnce / ForLoop / ForEachLoop / Switch 等）→ 提取分支类型 / 控制参数；`variable.py` — 变量节点 → 提取变量名 / 类型 / 操作类型（Get/Set）；`cast.py` — 类型转换节点 → 提取源/目标类型；`function_entry.py` — 函数入口 → 提取函数签名；`fallback.py` — 未匹配节点类型的回退处理器（提取 class_name / pins 基本信息）。`processor_base.py` — `N2CNodeProcessor` 抽象基类（`process_node()` 接口）；`processor_registry.py` — `N2CProcessorRegistry` — 单例注册表，`register()` / `get_processor()` / `process_node()` 分派 |
| **Flow Extractor** | `n2c/flow_extractor.py` | `extract_data_flow_map()` — 从 N2C 图结构提取数据流映射 |
| **ID Mapper** | `n2c/id_mapper.py` | `N2CIdMapper` — 节点/ Pin ID 映射和转换 |
| **Compat** | `n2c/compat.py` | N2C 兼容性层。`definition_to_node_dict()` — N2CNodeDefinition → OUT-01 格式 dict；`definition_to_trace_node_info()` — N2CNodeDefinition → trace 节点信息 |

### Agent / C++ 生成层

| 模块 | 文件 | 详细功能 |
|------|------|----------|
| **Agent Translator** | `agent/translator.py` | `AgentTranslationPipeline` — 整合管线：接收 ParseResult → 提取蓝图元数据 / 图 / Kismet → 生成 CppClassIR；`translate_blueprint_to_cpp()` — 便捷函数 |
| **Cpp Writer** | `agent/writer.py` | `CppFileWriter` — 将 CppClassIR 写入 .h / .cpp 文件；`write_cpp_class_files()` — 便捷函数，输入 CppClassIR → 输出 .h + .cpp 文件对 |
| **Extract CPP Skeleton** | `cpp_gen/extract_cpp_skeleton.py` | 从 C++ 参考源码中提取 UPROPERTY / UFUNCTION 骨架，用于类型映射和验证 |
| **Type Mapper** | `cpp_gen/cpp_type_mapper.py` | UE 属性类型 → C++ 类型映射（如 "FloatProperty" → "float"，"NameProperty" → "FName"，"SoftObjectProperty" → "TSoftObjectPtr<UObject>"） |
| **UProperty Mapper** | `cpp_gen/cpp_uproperty_mapper.py` | CPF 标志 → UPROPERTY 修饰符映射（如 CPF_Edit + CPF_BlueprintVisible → "UPROPERTY(EditAnywhere, BlueprintReadWrite)"） |
| **Default Value Formatter** | `cpp_gen/cpp_default_value_formatter.py` | UE 默认值 → C++ 字面量格式化（如 FString → TEXT("...")，FVector → FVector(x,y,z)） |
| **Constructor IR Builder** | `cpp_gen/cpp_constructor_ir_builder.py` | 从 BlueprintVariable 的 default_value 构建 C++ 构造函数 IR（中间表示） |
| **Constructor Formatter** | `cpp_gen/cpp_constructor_formatter.py` | 将构造函数 IR 格式化为 C++ 构造函数代码 |
| **Header Formatter** | `cpp_gen/formatters/cpp_header_formatter.py` | 生成 C++ 头文件（#pragma once / #include / UCLASS() / UPROPERTY() / UFUNCTION() 声明） |
| **Function Body Formatter** | `cpp_gen/formatters/cpp_function_body_formatter.py` | 格式化 Kismet 翻译后的 C++ 函数体 |
| **JSON IR** | `cpp_gen/formatters/cpp_json_ir.py` | CppClassIR JSON 序列化 / 反序列化 |
| **Function Body Extractor** | `cpp_gen/extractors/cpp_function_body_extractor.py` | 从 Kismet 表达式列表提取 C++ 函数体片段 |

### 格式化输出层

| 模块 | 文件 | 详细功能 |
|------|------|----------|
| **JSON Formatter** | `formatters/json_formatter.py` | `format_json_full()` — 完整 JSON 输出（summary + exports + properties + blueprint + graphs + Kismet + status）；`format_json_summary()` — 精简摘要（summary + export 列表 + 错误）；`format_exports_list()` — 仅 Export 列表；`format_properties_list()` — 仅属性列表；`format_blueprint_dict()` — 蓝图元数据字典；`_extract_call_function_parameters()` — 从 CallFunction 节点提取参数（name / type / default_value / data_source） |
| **Text Formatter** | `formatters/text_formatter.py` | `format_text_full()` — 完整文本输出（人类可读格式）；`format_text_summary()` — 精简文本摘要 |
| **Markdown Formatter** | `formatters/markdown_formatter.py` | `format_markdown()` — Markdown 格式输出（表格 + 列表）；`_build_mermaid_flowchart()` — 执行流 → Mermaid flowchart 图表代码 |
| **Blueprint Text Formatter** | `formatters/blueprint_text_formatter.py` | `format_blueprint_translation_text()` — Phase 74 蓝图翻译参考文本生成，为 AI Agent 提供蓝图语义的文本化描述 |
| **Helpers** | `formatters/helpers.py` | `build_status_info()` — 构建解析状态信息（文件信息 + 统计）；`build_schema_info()` — 构建 Package Schema 信息（版本 / 标志 / CustomVersion）；`resolve_fpackage_index()` — PackageIndex 解析为可读字符串 |

## 数据流详解

### parse_uasset() 完整流程

```
1. FArchive(path)              → 打开文件，初始化 mmap
2. read_package_summary()      → 解析 PackageFileSummary（版本/偏移/标志）
3. read_name_table()           → 读取 FName 名称表
4. read_import_map()           → 读取 ImportMap（外部包引用）
5. read_export_map()           → 读取 ExportMap（内部对象导出）
6. for export in export_map:   → 遍历每个导出对象
     parse_properties_from_export()  → 读取 PropertyTag 循环，分派解析
     extract_component_transforms()  → 提取组件变换（Location/Rotation/Scale）
7. _post_process()             → 共享后处理
     extract_blueprint_graphs()      → 图提取（UEdGraph[]）
     extract_blueprint_metadata()    → 蓝图元数据（parent/variables/functions/events）
     decompile_uasset()              → Kismet 反编译（字节码 → C++）
     extract_components()            → 组件提取
     build_imports_list()            → 依赖分析（imports/soft_refs/circular_deps）
8. return ParseResult          → 返回完整解析结果
```

### parse_uasset_with_linker() 差异

在步骤 5 之后插入：
```
5a. PackageLinker.link()       → Phase 1: 创建 UObjectInstance shells
     _create_import_instances()    → ImportMap → UObjectInstance
     _create_export_instances()    → ExportMap → UObjectInstance
     build_outer_tree()            → OuterIndex → 父子层级
     _collect_root_objects()       → 收集根对象
5b. preload(index) [optional]  → Phase 2: 按需反序列化属性
```

### Kismet 反编译管线

```
1. extract_bytecode_bytes()    → 从 UStruct ScriptBytecode 偏移读取原始字节
2. parse_bytecode_stream()     → 字节 → EExprToken 序列
3. 表达式树构建                  → Token 序列 → KismetExpression 树（递归子表达式）
4. KismetTranslator            → 遍历表达式树 → C++ 伪代码
5. StructuredControlFlow       → 扁平控制流 → 结构化（if/else/while/for）
6. FunctionBodyBuilder         → 组装 C++ 函数体
```

## 公共 API 导出

所有公开符号通过 `src/uasset_read/__init__.py` 的 `__all__` 控制，支持 `from uasset_read import X` 导入。共 ~150 个导出符号，覆盖：

- 常量（基础 / 图解析边界 / PropertyTag 标志 / 控制流 / Package Flags / UE5 版本 / CPF）
- 异常类
- 序列化模型
- 核心数据模型
- 解析器
- 蓝图元数据
- 图解析
- 格式化输出
- Kismet 字节码与反编译
- Agent 翻译与 C++ 生成
- N2C 中间格式

## 目录结构

```
src/uasset_read/    # 源码（~100 个 .py 文件）
tests/              # 测试（~1300+ tests）
.planning/          # 规划文档（ROADMAP / STATE / phases / milestones）
temp/               # 缓存 / 临时生成文件（.gitignore 排除）
docs/               # 用户文档
```

详细目录结构见 [ARCHITECTURE.md](ARCHITECTURE.md#file-organization)（源码文件级）和 `CLAUDE.md`（顶层概览）。

## 版本历史

项目版本信息请参考 git 标签和发布说明。
