# Phase 9: 高级属性类型 - Context

**Gathered:** 2026-05-02
**Status:** Ready for planning

<domain>
## Phase Boundary

实现高级属性类型的完整解析（StructProperty、MapProperty、SetProperty、EnumProperty、TextProperty、DelegateProperty），扩展 Phase 2 的基本属性解析架构。此阶段交付高级属性解析能力，为蓝图变量默认值和图节点参数解析提供完整数据。

**交付能力：**
- StructProperty 嵌套结构体解析（递归深度限制 5）
- MapProperty 键值对数组（支持基本类型、枚举、Struct、Object 键）
- SetProperty 唯一元素集（解析为 List，不验证唯一性）
- EnumProperty 枚举值解析（返回枚举类型名 + 枚举值名）
- TextProperty FText 结构解析（Namespace、Key、SourceString）
- DelegateProperty 函数引用解析（ObjectRef + FunctionName）

**Requirements:** ADVP-01, ADVP-02, ADVP-03, ADVP-04, ADVP-05, ADVP-06

**固定范围（来自 ROADMAP.md）：**
- 解析器能提取 StructProperty 值（嵌套结构体解析，递归深度限制 5）
- 解析器能提取 MapProperty 值（键值对数组，支持基本类型键）
- 解析器能提取 SetProperty 值（唯一元素集）
- 解析器能提取 EnumProperty 值（枚举类型名 + 枚举值名）
- 解析器能提取 TextProperty 值（FText：Namespace、Key、SourceString）
- 解析器能提取 DelegateProperty 值（函数引用：对象 + 函数名）

</domain>

<decisions>
## Implementation Decisions

### StructProperty 解析策略
- **D-01:** 递归解析内部字段 —— 结构体字段作为嵌套 dict 返回，递归解析深度限制 5 层（ROADMAP ADVP-01 指定）
- **D-01a:** StructValue dataclass —— `{struct_type: str, fields: dict}` 格式存储
- **D-01b:** 未知结构体字段处理 —— 遇到未知字段时记录字段名 + 原始数据位置，继续解析其他字段
- **原因:** 递归解析满足 AI agent 理解蓝图逻辑需求；深度限制防止无限递归；未知字段处理保证解析继续

### MapProperty 键类型范围
- **D-02:** 全键类型支持 —— 基本类型键 + 枚举类型键 + StructProperty 键 + ObjectProperty 键
- **D-02a:** MapValue dataclass —— `{key_type: str, value_type: str, entries: List[{key: Any, value: Any}]}` 格式
- **D-02b:** 键解析分派 —— 根据键类型名分派到对应解析函数
- **原因:** 用户选择全支持；分派模式复用 Phase 2 type_dispatch 架构

### SetProperty 处理方式
- **D-03:** 解析为 List —— 与 ArrayProperty 输出格式一致，不验证唯一性
- **D-03a:** SetValue dataclass —— `{element_type: str, elements: List[Any]}` 格式
- **原因:** 实现简单；唯一性验证增加复杂度且对 AI agent 无额外价值

### EnumProperty 值格式
- **D-04:** 返回枚举值名 —— 返回枚举值名称字符串（如 'EWalletState::Active'）
- **D-04a:** EnumValue dataclass —— `{enum_type: str, value_name: str}` 格式
- **原因:** 值名便于 AI agent 理解语义；整数值需额外枚举定义映射

### TextProperty 本地化处理
- **D-05:** 完整结构返回 —— 返回 Namespace、Key、SourceString 三个字段
- **D-05a:** TextValue dataclass —— `{namespace: str, key: str, source_string: str}` 格式
- **原因:** 保留完整本地化信息；SourceString 仅返回丢失本地化元数据

### DelegateProperty 函数引用
- **D-06:** 原始引用格式 —— `{ObjectRef: FPackageIndex, FunctionName: str}`
- **D-06a:** DelegateValue dataclass —— `{object_ref: int, function_name: str}` 格式
- **D-06b:** 对象引用延迟解析 —— ObjectRef 保持原始 FPackageIndex 值，Phase 10 依赖分析时解析
- **原因:** 原始引用避免 ImportMap/ExportMap 查询复杂度；延迟解析保持解析器职责单一

### 数据类设计
- **D-07:** 专用 dataclass —— 为每种高级属性创建专用 dataclass（StructValue、MapValue、SetValue、EnumValue、TextValue、DelegateValue）
- **D-07a:** 统一继承基类 —— `AdvancedPropertyValue` 基类包含 `property_type: str` 字段
- **原因:** 结构清晰；类型信息明确；便于 JSON 输出序列化

### 版本支持
- **D-08:** UE4 + UE5 双支持 —— 使用 Phase 2 D-05/D-06 版本检查模式
- **D-08a:** 版本分支 —— `PROPERTY_TAG_COMPLETE_TYPE_NAME` 版本阈值检查（UE5 >= 该值用新格式）
- **原因:** 用户选择双支持；版本检查模式已验证有效

### 失败处理策略
- **D-09:** 跳过继续 —— Phase 2 D-25 模式：记录简短标记 + 跳过并继续下一个属性
- **D-09a:** 失败信息 —— 记录属性名、类型、失败原因、原始数据位置
- **原因:** 与 Phase 2 策略一致；最大化数据提取

### 性能考量
- **D-10:** 复用 Phase 5 SAFE-03 —— >50MB 自动 mmap，无需额外限制
- **D-10a:** 嵌套深度限制 —— StructProperty 递归深度 5，足够覆盖常见结构体
- **原因:** Phase 5 mmap 机制已验证；深度限制已覆盖

### JSON 输出位置
- **D-11:** 替换原始值 —— 高级属性解析结果直接替换 properties 列表中的原始字符串值
- **D-11a:** 输出格式 —— 保持 PropertyValue 格式 `{name: str, type: str, value: Any}`
- **原因:** Phase 8 OUT2-02 指定替换原始值；保持属性列表格式不变

### 测试资产来源
- **D-12:** Lyra + UE 示例 —— LyraStarterGame 资产 + UnrealEngine/Samples BP 示例
- **D-12a:** 资产选择策略 —— 搜索包含 Struct/Map/Set/Enum/Text/Delegate 的蓝图资产
- **原因:** Lyra 资产覆盖真实游戏场景；UE 示例项目提供多种版本对照

### Claude's Discretion
- 具体结构体类型字段解析顺序（需研究 UE 源码确定）
- EnumProperty 枚举值名生成格式（是否包含类型名前缀）
- TextProperty 空字段处理（Namespace/Key 为空时的默认值）
- 单元测试组织
- 具体测试资产文件选择

</decisions>

<specifics>
## Specific Ideas

- "StructProperty 递归解析" —— 用户确认递归解析深度 5 层
- "MapProperty 全键类型支持" —— 用户选择支持基本类型、枚举、Struct、Object 四种键类型
- "SetProperty 不验证唯一性" —— 用户确认解析为 List，与 ArrayProperty 格式一致
- "UE4 + UE5 双支持" —— 用户选择扩展版本支持范围

</specifics>

<canonical_refs>
## Canonical References

**下游 agent 必须在规划或实现前阅读这些。**

### UE 源码参考（核心）
- `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/CoreUObject/Private/UObject/PropertyStruct.cpp` —— StructProperty 序列化实现（ADVP-01）
- `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/CoreUObject/Private/UObject/PropertyMap.cpp` —— MapProperty 序列化实现（ADVP-02）
- `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/CoreUObject/Private/UObject/PropertySet.cpp` —— SetProperty 序列化实现（ADVP-03）
- `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/CoreUObject/Private/UObject/EnumProperty.cpp` —— EnumProperty 序列化实现（ADVP-04）
- `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/CoreUObject/Private/UObject/TextProperty.cpp` —— TextProperty 序列化实现（ADVP-05）
- `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/CoreUObject/Private/UObject/PropertyDelegate.cpp` —— DelegateProperty 序列化实现（ADVP-06）
- `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/CoreUObject/Public/UObject/PropertyTag.h` —— PropertyTag 结构定义、版本标志

### 项目现有代码
- `uasset_read.py` 第 3034-3054 行 —— `parse_property_value()` 类型分派字典（Phase 9 扩展）
- `uasset_read.py` 第 2844-2899 行 —— `parse_array_property()` 嵌套解析模式（StructProperty 参考）
- `uasset_read.py` 第 2873 行 —— `MAX_DEPTH = 10` 嵌套深度限制（StructProperty 改为 5）
- `uasset_read.py` 第 2650-2718 行 —— `read_property_tag()` 版本感知解析（Phase 2 D-05/D-06）
- `uasset_read.py` 第 1561-1640 行 —— `read_ed_graph_pin_type()` 版本检查模式参考

### 项目规划文档
- `.planning/PROJECT.md` —— 项目核心价值、约束（UE 5.x 标准，UTF-8 编码）
- `.planning/REQUIREMENTS.md` —— ADVP-01 至 ADVP-06 需求定义
- `.planning/ROADMAP.md` —— Phase 9 成功标准
- `.planning/phases/02-property-parsing/02-CONTEXT.md` —— Phase 2 决策（type_dispatch、版本检查、失败策略）
- `.planning/phases/05-optimization-security/05-CONTEXT.md` —— Phase 5 决策（mmap 机制、max_reasonable Size）
- `.planning/phases/07-blueprint-graph-core/07-CONTEXT.md` —— Phase 7 决策（图数据 dataclass 设计）

### 测试资产来源
- `LyraStarterGame/` —— Lyra 示例游戏资产（高级属性真实场景测试）
- `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/CoreUObject/Public/UObject/` —— UE 核心类型定义参考

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **parse_property_value() type_dispatch:** 字典分派模式可扩展，添加 StructProperty、MapProperty 等处理器
- **parse_array_property() 嵌套模式:** Count + 元素循环读取模式，Map/Set 可复用
- **read_property_tag() 版本检查:** PROPERTY_TAG_COMPLETE_TYPE_NAME 版本阈值检查模式
- **FArchive 类:** 所有读取方法（read_i32、read_fstring、read_name 等）可直接使用
- **Phase 5 mmap 机制:** FArchive 内部 mmap 分支，>50MB 自动切换

### Established Patterns
- **版本感知解析:** Phase 2 D-05/D-06 UE4/UE5 格式分支模式
- **嵌套深度限制:** Phase 2 D-18 MAX_DEPTH = 10 模式，StructProperty 改为 5
- **失败跳过策略:** Phase 2 D-25 记录简短标记 + 跳过并继续
- **dataclass 模型:** Phase 7 UEdGraph/UEdGraphNode dataclass 设计模式可复用

### Integration Points
- `parse_property_value()` 第 3034-3054 行 —— 添加高级属性类型处理器
- `PropertyValue` —— 高级属性值替换原始字符串值（Phase 8 OUT2-02）
- JSON 输出 —— format_json_full() 无需修改，dataclass 自动序列化

</code_context>

<deferred>
## Deferred Ideas

推迟到后续阶段的实现：

### Phase 10（依赖分析）
- DelegateProperty ObjectRef 解析为对象名
- ObjectProperty 键值解析为对象名

### v3（高级功能）
- 自定义结构体类型注册机制
- 结构体类型缓存（避免重复解析相同类型）
- 枚举定义提取（枚举类型 → 所有可能值列表）

None — discussion stayed within phase scope

</deferred>

---

*Phase: 09-advanced-properties*
*Context gathered: 2026-05-02*