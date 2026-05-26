# CUE4Parse ↔ uasset_read 对照索引

> CUE4Parse（C#）与 uasset_read（Python）模块级一一对照。
> 用于一比一对应翻译重构参考，通过对照修复 Linker 等遗留问题。
>
> **生成日期:** 2026-05-26 | **uasset_read 版本:** v13.0 (1463 tests)

---

## 对照图例

| 标记 | 含义 |
|------|------|
| ✅ 已实现 | 功能等价，可直接参考 |
| ⚠️ 部分实现 | 有基础但 incomplete，需对齐 |
| ❌ 缺失 | 完全未实现，需从头编写 |
| 🔧 需修复 | 有代码但行为不正确 |

---

## 1. 核心层（UE/Readers → 序列化）

### 1.1 FArchive — 字节流读取

| CUE4Parse | uasset_read | 状态 | 差异说明 |
|-----------|-------------|------|---------|
| `FArchive` (基类) | `archive.py` — `FArchive` 类 | ✅ 已实现 | 基础二进制读取一致 |
| `Read<T>()` 泛型读取 | `read_u8/i16/u16/i32/u64/f32/f64/bool` | ✅ 已实现 | Python struct 替代 C# Unsafe |
| `ReadFString()` | `read_fstring()` | ⚠️ 部分 | null 终止检测已修复，但 FName 专用路径缺失 |
| `ReadFName()` | `read_name()` | ✅ 已实现 | NameMap 索引查表 |
| `ReadObject<T>()` | `read_import_map/read_export_map` | ⚠️ 部分 | 缺少泛型 UObject 引用解析 |
| `Serialize()` raw bytes | `stream.read(n)` | ✅ 已实现 | mmap 大文件映射 |
| `Position` 属性 | `tell()/seek()` | ✅ 已实现 | Python 风格 |
| `ArrayPool<byte>` 零分配 | 无 | ❌ 缺失 | Python 无法零分配，每次产生新 bytes |
| `MemoryMappedFile` | `mmap.mmap()` | ✅ 已实现 | ≥16MB 自动启用 |
| 大端/字节序切换 | `set_byte_swapping()` | ✅ 已实现 | 通过魔数自动检测 |

### 1.2 FAssetArchive — 资产级封装

| CUE4Parse | uasset_read | 状态 | 差异说明 |
|-----------|-------------|------|---------|
| `FAssetArchive` (装饰器) | 无直接对应 | ❌ 缺失 | 未实现资产级序列化上下文封装 |
| `ReadAssetPackageSummary()` | `read_package_summary()` | ✅ 已实现 | 逐字段读取 |
| `ReadNameList()` | `read_name_table()` | ✅ 已实现 | 批量 FName 列表 |
| `ReadImportMap()` | `read_import_map()` | ✅ 已实现 | 循环 ObjectImport |
| `ReadExportMap()` | `read_export_map()` | ✅ 已实现 | 循环 ObjectExport |
| `Lazy<UObject>[]` 延迟反序列化 | `PackageLinker.preload()` | ⚠️ 部分 | 手动 seek 而非 Lazy<T> 自动触发 |
| `VersionContainer` | `constants.py` 版本常量 | ⚠️ 部分 | 常量分散，未统一管理 |
| `FCustomVersion` | 无 | ❌ 缺失 | 自定义版本 GUID 体系未实现 |

### 1.3 PackageIndex 解析

| CUE4Parse | uasset_read | 状态 | 差异说明 |
|-----------|-------------|------|---------|
| `PackageIndex` (有符号) | `serializers/__init__.py` — `PackageIndex` | ✅ 已实现 | 正数 Export / 负数 Import / 零 Null |
| `ResolvePackageIndex()` | `linker.resolve_package_index()` | ✅ 已实现 | 两阶段加载器中 |
| `GetImport()` / `GetExport()` | 无直接快捷方法 | ❌ 缺失 | 需手动查 `_imports`/`_exports` dict |

---

## 2. 对象模型（UObject）

### 2.1 UObject 基类

| CUE4Parse | uasset_read | 状态 | 差异说明 |
|-----------|-------------|------|---------|
| `UObject` (基类) | `UObjectInstance` (link/object_instance.py) | ⚠️ 部分 | 仅有外壳元数据，无序列化数据容器 |
| `Serialize()` | `parse_properties_from_export()` | ✅ 已实现 | 属性解析在外部函数中 |
| `GetFullName()` | `UObjectInstance.get_full_name()` | ✅ 已实现 | Outer 链拼接 |
| `GetPathName()` | `UObjectInstance.get_path_name()` | ✅ 已实现 | 完整路径名 |
| `Outer` 层级 | `UObjectInstance.outer` + `build_outer_tree()` | ✅ 已实现 | Phase 72 已修复 |
| `Class` 引用 | `UObjectInstance.object_class` | ✅ 已实现 | 导入时记录 |
| `SuperField` 链 | 无 | ❌ 缺失 | UStruct → UClass → UScriptStruct 继承链未建立 |
| `Lazy<>` 按需加载 | `_preloaded` flag + `preload()` | ⚠️ 部分 | 手动控制而非自动延迟 |

### 2.2 UObject 继承树

| CUE4Parse | uasset_read | 状态 | 差异说明 |
|-----------|-------------|------|---------|
| `UField` → `UEnum` | 无 | ❌ 缺失 | 枚举类型未解析 |
| `UField` → `UStruct` → `UClass` | 无 | ❌ 缺失 | 类结构未解析 |
| `UField` → `UStruct` → `UScriptStruct` | 无 | ❌ 缺失 | 脚本结构体未解析 |
| `UField` → `UFunction` | ⚠️ 间接 | Blueprint 元数据有 functions[] | 但无独立 UFunction 对象 |
| `UTexture2D` | 无 | ❌ 缺失 | 纹理导出 |
| `UStaticMesh` | 无 | ❌ 缺失 | 网格导出 |
| `USkeletalMesh` | 无 | ❌ 缺失 | 骨骼网格导出 |
| `USoundWave` | 无 | ❌ 缺失 | 音频导出 |
| `UMaterial` | 无 | ❌ 缺失 | 材质导出 |
| `UAnimSequence` | 无 | ❌ 缺失 | 动画导出 |

---

## 3. 属性解析（FProperty）

### 3.1 基础类型

| CUE4Parse | uasset_read | 状态 | 差异说明 |
|-----------|-------------|------|---------|
| `BoolProperty` | `parse_bool_property` | ✅ 已实现 | |
| `ByteProperty` | `parse_byte_property` (property_types.py) | ✅ 已实现 | |
| `IntProperty` | `parse_int_property` | ✅ 已实现 | |
| `FloatProperty` | `parse_float_property` | ✅ 已实现 | |
| `StrProperty` | `parse_str_property` | ✅ 已实现 | |
| `NameProperty` | `parse_name_property` | ✅ 已实现 | |
| `ObjectProperty` | `parse_object_property` | ✅ 已实现 | |
| `SoftObjectProperty` | `parse_soft_object_property` | ✅ 已实现 | |

### 3.2 复合类型

| CUE4Parse | uasset_read | 状态 | 差异说明 |
|-----------|-------------|------|---------|
| `ArrayProperty` | `parse_array_property` | ⚠️ 部分 | InnerType 递归正确，但复杂 InnerType 可能失败 |
| `StructProperty` | `parse_struct_property` | 🔧 需修复 | 复杂结构体（FVector/FRotator/FBodyInstance）内部字段解析不正确 |
| `MapProperty` | `parse_map_property` | ✅ 已实现 | Key/Value 类型分离 |
| `SetProperty` | `parse_set_property` | ✅ 已实现 | |
| `EnumProperty` | `parse_enum_property` | ✅ 已实现 | |
| `TextProperty` | `parse_text_property` | ⚠️ 部分 | FText HistoryType/Flags 已处理，bHasCultureInvariantString 修复中 |
| `DelegateProperty` | `parse_delegate_property` | ✅ 已实现 | |

### 3.3 UE5 特有

| CUE4Parse | uasset_read | 状态 | 差异说明 |
|-----------|-------------|------|---------|
| `PropertyTag` UE5 格式分支 | `read_property_tag()` — UE5.4+ 分支 | ✅ 已实现 | Phase 67 已修复 PropertyTypeNameNode |
| `FPropertyTypeNameNode` 链式 | `serializers/property_tags.py` | ✅ 已实现 | 递归读取 FName+InnerCount |
| `PropertyTagFlags` 扩展 | 常量定义 | ✅ 已实现 | PROP_TAG_* 系列常量 |
| `UnversionedProperties` | 常量定义 | ✅ 已实现 | PKG_UnversionedProperties |

---

## 4. 蓝图/Kismet

### 4.1 图解析

| CUE4Parse | uasset_read | 状态 | 差异说明 |
|-----------|-------------|------|---------|
| UEdGraph 识别 | `graph/parser.py` — `extract_blueprint_graphs()` | ✅ 已实现 | |
| UEdGraphNode 读取 | `serializers/graph.py` — `read_ue_graph_node()` | ✅ 已实现 | |
| UEdGraphPin 读取 | `serializers/graph.py` — `read_ue_graph_pin()` | ✅ 已实现 | Phase 74 PinReference 对齐 |
| PinType 解析 | `models/core.py` — `FEdGraphPinType` | ✅ 已实现 | |
| PinReference 布局 | Phase 74 修复 | ✅ 已实现 | 4B null + 24B non-null |
| ParentPin | Phase 74 修复 | ✅ 已实现 | 复用 `read_pin_reference()` |
| 连接映射 | `flow_builder.build_connections_map()` | ✅ 已实现 | 双向归一化 |
| 执行流追踪 | `flow_builder.build_execution_flows()` | ✅ 已实现 | START_EVENT_TYPES 开始 |
| 数据流提取 | `flow_builder.build_data_flows()` | ✅ 已实现 | 非 exec pin |
| 链式表达 | `chain_builder.build_execution_chains()` | ✅ 已实现 | Phase 71 |
| Knot 穿透 | `_resolve_knot_chain()` | ✅ 已实现 | 循环检测 |
| 数据源追踪 | `_trace_data_source()` | ✅ 已实现 | 反向追踪 |
| FunctionEntry 函数图 | `build_function_graphs()` | ✅ 已实现 | |
| N2C Processor Registry | `n2c/processors/` — 9 个处理器 | ✅ 已实现 | Phase 69 |

### 4.2 Kismet 字节码

| CUE4Parse | uasset_read | 状态 | 差异说明 |
|-----------|-------------|------|---------|
| `EExprToken` 枚举 | `kismet/tokens.py` — 60+ 种 | ⚠️ 部分 | CUE4Parse 有 100+ 种 |
| `FKismetArchive` | `kismet/archive.py` | ✅ 已实现 | 字节流读取 |
| 字节码提取 | `kismet/bytecode_extractor.py` | ✅ 已实现 | |
| BPGC Fallback | `kismet/bpgc_bytecode.py` | ✅ 已实现 | Phase 72-C |
| 表达式树构建 | `kismet/expressions/` — 16 种子类 | ⚠️ 部分 | EXPR_CLASS_MAP 覆盖不完整 |
| `FExpressionEvaluator` 求值 | 无 | ❌ 缺失 | 运行时表达式求值 |
| C++ 翻译 | `kismet/translator.py` — `KismetTranslator` | ✅ 已实现 | |
| 结构化控制流 | `kismet/structured_flow.py` | ✅ 已实现 | If/While/For/Switch |
| 函数体构建 | `kismet/body_builder.py` | ✅ 已实现 | |
| 反编译管线 | `kismet/pipeline.py` — `decompile_uasset()` | ✅ 已实现 | |
| FKismetPropertyPointer | `kismet/property_pointer.py` | ✅ 已实现 | |
| `FFieldPath` (UE5) | `kismet/property_pointer.py` | ✅ 已实现 | |

### 4.3 表达式类型覆盖

| EExprToken 类别 | CUE4Parse | uasset_read | 状态 |
|-----------------|-----------|-------------|------|
| 变量访问 (Local/Instance/Default) | ✅ | ✅ `variables.py` | ✅ |
| 函数调用 (CallFunction/Delegate/Interface) | ✅ | ✅ `functions.py` | ✅ |
| 字面量 (Int/NoObject/SkipOffset/Self) | ✅ | ✅ `literals.py` | ⚠️ 覆盖不全 |
| 类型转换 (DynamicCast/CrossInterface) | ✅ | ✅ `casts.py` | ✅ |
| 控制流 (Return/Jump/JumpIfNot/ComputedJump) | ✅ | ✅ `control_flow.py` | ✅ |
| 赋值 (Let/LetObj/LetWeakObjPtr/LetBool) | ✅ | ✅ `assignments.py` | ✅ |
| 字符串 (UnicodeText/StringConst/NameConst) | ✅ | ✅ `string_consts.py` | ✅ |
| 向量 (Vector/Rotation/TransformConst) | ✅ | ✅ `vector_consts.py` | ✅ |
| 容器 (SetArray/ArrayConst/MapConst/SetConst) | ✅ | ✅ `containers.py` | ✅ |
| 结构体 (StructConst/MemberGet/MemberSet) | ✅ | ✅ `structs.py` | ✅ |
| 委托 (DelegateSet/Get/AddMulticast) | ✅ | ✅ `delegates.py` | ✅ |
| RTFM (AutoRtfmStopTransact) | ✅ | ✅ `rtfm.py` | ✅ |
| 特殊 (Breakpoint/Instrumentation/WireTracepoint) | ✅ | ✅ `special.py` | ✅ |
| Context (Self/ObjectConstReference) | ✅ | ✅ `context.py` | ✅ |
| PushExecutionFlow | ✅ | ✅ `variables.py` | ✅ |
| **缺失类型 (~40 种)** | ✅ | ❌ | ❌ 需补充 |

---

## 5. 链接器（FLinkerLoad）

| CUE4Parse | uasset_read | 状态 | 差异说明 |
|-----------|-------------|------|---------|
| `FLinkerLoad` 两阶段加载 | `PackageLinker` (link/linker.py) | ✅ 已实现 | Phase 7 架构 |
| Phase 1: 创建外壳 | `link()` — `_create_import/export_instances()` | ✅ 已实现 | |
| Phase 2: 按需加载 | `preload(index)` | ✅ 已实现 | 手动 seek + 解析 + 恢复 |
| `BuildOuterTree()` | `build_outer_tree()` | ✅ 已实现 | |
| `CollectRootObjects()` | `_collect_root_objects()` | ✅ 已实现 | |
| `ResolvePackageIndex()` | `resolve_package_index()` | ✅ 已实现 | 正数查 export / 负数查 import |
| `GetChildren()` | `get_children()` | ✅ 已实现 | |
| `Lazy<UObject>` 自动触发 | 手动 `_preloaded` flag | ⚠️ 部分 | Python 无 Lazy<T> 等价物 |
| 导入/导出懒加载 | `preload()` 按需 | ⚠️ 部分 | 未与图解析管线集成 |
| 缓存隔离 | `reset_bpgc_cache()` | ✅ 已实现 | Phase 72-F |
| BPGC FuncMap 提取 | `kismet/bpgc_bytecode.py` | ✅ 已实现 | Phase 72-C |

---

## 6. N2C 中间格式

| CUE4Parse | uasset_read | 状态 | 差异说明 |
|-----------|-------------|------|---------|
| (无直接对应) | `n2c/schema.py` — N2CStruct/Graph/Node/Pin | ✅ 已实现 | Phase 70 |
| (无直接对应) | `n2c/serializer.py` — to_n2c_json/from_n2c_json | ✅ 已实现 | |
| (无直接对应) | `n2c/validation.py` — JSON Schema 校验 | ✅ 已实现 | |
| (无直接对应) | `n2c/type_registry.py` — N2CNodeTypeRegistry | ✅ 已实现 | Phase 68 |
| (无直接对应) | `n2c/node_types.py` — N2CNodeType 枚举 | ✅ 已实现 | |
| (无直接对应) | `n2c/processors/` — 9 个处理器 | ✅ 已实现 | Phase 69 |
| (无直接对应) | `n2c/flow_extractor.py` — 数据流映射 | ✅ 已实现 | |
| (无直接对应) | `n2c/id_mapper.py` — ID 映射 | ✅ 已实现 | |
| (无直接对应) | `n2c/compat.py` — 兼容层 | ✅ 已实现 | |
| `FN2CStruct` / `FN2CEnum` | `n2c/schema.py` — 无 N2CEnum | ⚠️ 部分 | 枚举提取缺失 |
| `TraceConnectionThroughKnots()` | `_resolve_knot_chain()` | ✅ 已实现 | |
| `CurrentDepth` / `ParentDepth` | 无 | ❌ 缺失 | 遍历深度控制 |
| `ReferenceSourceFilePaths` | 无 | ❌ 缺失 | 参考代码注入 |
| `EN2CCodeLanguage` 多语言 | C++ only | ⚠️ 部分 | 仅 C++ 输出 |

---

## 7. C++ 生成

| CUE4Parse | uasset_read | 状态 | 差异说明 |
|-----------|-------------|------|---------|
| (无直接对应) | `cpp_gen/cpp_type_mapper.py` — UE→C++ 类型映射 | ✅ 已实现 | |
| (无直接对应) | `cpp_gen/cpp_uproperty_mapper.py` — CPF→UPROPERTY | ✅ 已实现 | |
| (无直接对应) | `cpp_gen/cpp_default_value_formatter.py` | ✅ 已实现 | |
| (无直接对应) | `cpp_gen/cpp_constructor_ir_builder.py` | ✅ 已实现 | |
| (无直接对应) | `cpp_gen/cpp_constructor_formatter.py` | ✅ 已实现 | |
| (无直接对应) | `cpp_gen/formatters/cpp_header_formatter.py` | ✅ 已实现 | |
| (无直接对应) | `cpp_gen/formatters/cpp_function_body_formatter.py` | ✅ 已实现 | |
| (无直接对应) | `cpp_gen/formatters/cpp_json_ir.py` | ✅ 已实现 | |
| (无直接对应) | `cpp_gen/extractors/cpp_function_body_extractor.py` | ✅ 已实现 | |
| (无直接对应) | `cpp_gen/extract_cpp_skeleton.py` — C++ 参考提取 | ✅ 已实现 | |
| `CodeGen_*.md` prompts | Agent system prompt | ⚠️ 部分 | 仅 C++ prompt |

---

## 8. 压缩/加密（❌ 全部缺失）

| CUE4Parse | uasset_read | 状态 | 差异说明 |
|-----------|-------------|------|---------|
| `ZlibHelper` | 无 | ❌ 缺失 | |
| Oodle (`Oodle.NET`) | 无 | ❌ 缺失 | C 原生绑定 |
| LZ4 (`LZ4Codec`) | 无 | ❌ 缺失 | 纯 Python 或原生 |
| Zstd (`ZstdSharp`) | 无 | ❌ 缺失 | |
| AES-ECB/CBC | 无 | ❌ 缺失 | 需要 `cryptography` 或标准库 |
| XOR / Lua 加密 | 无 | ❌ 缺失 | 游戏特定 |

---

## 9. Pak/IoStore（❌ 全部缺失）

| CUE4Parse | uasset_read | 状态 | 差异说明 |
|-----------|-------------|------|---------|
| `FPakFileReader` | 无 | ❌ 缺失 | .pak 文件解析 |
| `FIoStoreReader` | 无 | ❌ 缺失 | UE5 IoStore (.utoc/.ucas) |
| `IVfsReader` 抽象 | 无 | ❌ 缺失 | 虚拟文件系统 |
| Pak 加密处理 | 无 | ❌ 缺失 | AES 解密 |
| IoStore 分块索引 | 无 | ❌ 缺失 | Toc/ucas 映射 |
| 虚拟路径映射 | 无 | ❌ 缺失 | `VirtualPaths` |

---

## 10. 资源导出（❌ 全部缺失）

### 10.1 纹理

| CUE4Parse | uasset_read | 状态 | 差异说明 |
|-----------|-------------|------|---------|
| DXT1/3/5 | 无 | ❌ 缺失 | |
| BC4/5/6H/7 | 无 | ❌ 缺失 | |
| ASTC 全系列 | 无 | ❌ 缺失 | |
| ETC1/ETC2 | 无 | ❌ 缺失 | |
| 原始格式 (A8R8G8B8/FloatRGBA) | 无 | ❌ 缺失 | |
| Deswizzle/解交错 | 无 | ❌ 缺失 | 平台相关解包 |
| 虚拟纹理 (Morton 编码) | 无 | ❌ 缺失 | |
| 纹理数组 | 无 | ❌ 缺失 | |

### 10.2 网格

| CUE4Parse | uasset_read | 状态 | 差异说明 |
|-----------|-------------|------|---------|
| ActorX (.psk/.pskx) | 无 | ❌ 缺失 | |
| glTF (.glb) | 无 | ❌ 缺失 | |
| OBJ (.obj) | 无 | ❌ 缺失 | |
| UEFormat (.uemodel) | 无 | ❌ 缺失 | |
| Nanite (ZOrder 曲线) | 无 | ❌ 缺失 | UE5 特有 |

### 10.3 音频

| CUE4Parse | uasset_read | 状态 | 差异说明 |
|-----------|-------------|------|---------|
| Wwise (.wem/.akm) | 无 | ❌ 缺失 | |
| OGG/Vorbis | 无 | ❌ 缺失 | |
| ADPCM | 无 | ❌ 缺失 | |
| BINK Audio | 无 | ❌ 缺失 | |
| OPUS | 无 | ❌ 缺失 | |
| PS5 AT9 | 无 | ❌ 缺失 | |

### 10.4 动画

| CUE4Parse | uasset_read | 状态 | 差异说明 |
|-----------|-------------|------|---------|
| ActorX (.psa) | 无 | ❌ 缺失 | |
| ACL 压缩 | 无 | ❌ 缺失 | |
| PoseAsset 导出 | 无 | ❌ 缺失 | |

---

## 11. 游戏特定适配

| CUE4Parse | uasset_read | 状态 | 差异说明 |
|-----------|-------------|------|---------|
| `VersionContainer` | 分散的常量 | ⚠️ 部分 | 需要统一管理 |
| 70+ 游戏覆盖 | 无 | ❌ 缺失 | |
| `GameTypes` 分支 | 无 | ❌ 缺失 | |
| `CustomEncryptionDelegate` | 无 | ❌ 缺失 | |
| 属性类型覆盖 | 无 | ❌ 缺失 | |
| 版本行为差异 | 无 | ❌ 缺失 | |

---

## 12. 文件提供者（❌ 全部缺失）

| CUE4Parse | uasset_read | 状态 | 差异说明 |
|-----------|-------------|------|---------|
| `IFileProvider` 接口 | 无 | ❌ 缺失 | 文件发现/路径映射 |
| `DefaultFileProvider` | 无 | ❌ 缺失 | 默认实现 |
| 懒加载 `ExportsLazy` | `preload()` 手动 | ⚠️ 部分 | |
| 依赖注入 | 无 | ❌ 缺失 | IFileProvider 注入到反序列化 |

---

## 统计摘要

| 类别 | CUE4Parse 模块数 | uasset_read 已实现 | 部分实现 | 缺失 | 需修复 |
|------|-----------------|-------------------|---------|------|--------|
| 核心层 (FArchive) | ~15 | 10 | 3 | 1 | 1 |
| 对象模型 (UObject) | ~12 | 5 | 2 | 5 | 0 |
| 属性解析 (FProperty) | ~18 | 14 | 3 | 0 | 1 |
| 蓝图/Kismet | ~20 | 16 | 2 | 1 | 0 |
| 链接器 (FLinkerLoad) | ~10 | 7 | 2 | 0 | 0 |
| N2C 中间格式 | ~8 | 7 | 1 | 2 | 0 |
| C++ 生成 | ~9 | 9 | 1 | 0 | 0 |
| 压缩/加密 | ~6 | 0 | 0 | 6 | 0 |
| Pak/IoStore | ~6 | 0 | 0 | 6 | 0 |
| 资源导出 | ~20 | 0 | 0 | 20 | 0 |
| 游戏适配 | ~6 | 0 | 1 | 5 | 0 |
| 文件提供者 | ~4 | 0 | 1 | 3 | 0 |
| **总计** | **~134** | **68** | **16** | **49** | **2** |

**完成度:** 50.7% (68/134) | **部分完成:** 11.9% (16/134) | **待实现:** 36.6% (49/134) | **待修复:** 1.5% (2/134)

---

## 修复优先级

### P0 — 阻塞性修复（Linker/序列化核心）

| 问题 | CUE4Parse 参考 | uasset_read 位置 | 修复方向 |
|------|---------------|-----------------|---------|
| PackageLinker 懒加载未集成 | `Lazy<UObject>[]` | `link/linker.py` | 将 preload() 集成到图解析管线 |
| FAssetArchive 资产级封装缺失 | `FAssetArchive` 装饰器 | 新模块 `serializers/asset_archive.py` | 包装 FArchive + 类型工厂 |
| VersionContainer 分散 | `VersionContainer` | `constants.py` | 统一管理 + 游戏分支 |

### P1 — 功能完整性

| 问题 | CUE4Parse 参考 | uasset_read 位置 | 修复方向 |
|------|---------------|-----------------|---------|
| Kismet 表达式 ~40 种缺失 | 100+ 表达式类型 | `kismet/expressions/` | 补齐 EXPR_CLASS_MAP |
| FExpressionEvaluator 求值器缺失 | `FExpressionEvaluator` | 新模块 `kismet/evaluator.py` | 运行时表达式求值 |
| FCustomVersion 体系缺失 | `FCustomVersion` | 新模块 `serializers/custom_version.py` | GUID + 版本映射 |
| UObject 继承树缺失 | `UObject` → `UField` → ... | 新模块 `models/uobject.py` | 类层次结构 |

### P2 — 新增模块（按依赖排序）

1. **压缩层** (Oodle/LZ4/Zstd) → Pak 解析依赖
2. **加密层** (AES) → Pak 加密依赖
3. **Pak 解析** → 游戏目录发现依赖
4. **IoStore** (UE5) → 独立于 Pak
5. **纹理导出** (DXT/BC/ASTC) → 独立模块
6. **网格导出** (psk/glb) → 独立模块
7. **音频导出** (wav/ogg) → 独立模块
8. **游戏适配** (VersionContainer + GameTypes) → 全局依赖

---

*Updated: 2026-05-26*
