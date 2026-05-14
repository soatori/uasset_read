# Phase 2: 属性解析 - Context

**Gathered:** 2026-05-01
**Status:** Ready for planning

<domain>
## Phase Boundary

解析 PropertyTag 结构并从导出数据中提取基本属性值。此阶段交付属性解析能力，为后续蓝图提取和输出格式化奠定基础。

**交付能力：**
- 读取 PropertyTag（Name、Type、Size、ArrayIndex、Flags）
- 提取基本类型属性值（Int、Float、Bool、String、Name、Object、Array）
- 处理 PropertyTag 标志（HasPropertyGuid、HasArrayIndex）
- 版本感知解析（UE4/UE5 格式差异）

**Requirements:** PROP-01, PROP-02, PROP-03, PROP-04, PROP-05, PROP-06, PROP-07, PROP-08, PROP-09

**固定范围（来自 ROADMAP.md）：**
- PropertyTag 解析（名称、类型、大小、标志）
- IntProperty 解析（int32、int64）
- FloatProperty 解析（float、double）
- BoolProperty 解析（内联 bool 字节）
- StrProperty 解析（带长度前缀的 FString）
- NameProperty 解析（从 NameMap 解析的 FName）
- ObjectProperty 解析（FPackageIndex 引用）
- ArrayProperty 解析（计数 + 元素循环）
- PropertyTag 标志处理（HasPropertyGuid、HasPropertyExtensions）

</domain>

<decisions>
## Implementation Decisions

### 解析架构设计
- **D-01:** ExportReader 类 —— 创建专门的导出解析器，先读取统一 UObject 头，再进入属性循环
- **D-02:** 统一导出头结构 —— 所有导出统一读取固定头（ObjectFlags、ClassRef 等），再进入属性循环
- **原因:** 用户确认导出数据有统一头结构，而非直接进入属性循环

### 属性类型处理
- **D-03:** 函数分派模式 —— 为每种属性类型创建独立解析函数（parse_int_property、parse_float_property 等）
- **D-04:** 属性类型注册 —— 用字典映射类型名到解析函数（`{'IntProperty': parse_int_property}`）
- **原因:** 清晰易测试，匹配 UE 源码结构（每种属性类型有独立 SerializeItem）

### 版本支持
- **D-05:** 版本分支解析 —— 使用 PROPERTY_TAG_COMPLETE_TYPE_NAME 版本检查（UE5 版本号 >= 该值用新格式）
- **D-06:** UE4/UE5 双格式支持 —— 新版本用完整 TypeName，旧版本分字段读取（StructName、EnumName、InnerType）
- **原因:** 用户选择版本分支，需覆盖 UE4/UE5 边界版本测试

### 数据模型
- **D-07:** Python 原生类型值 —— int、float、str、list、dict 等，直接 JSON 输出兼容
- **D-08:** PropertyTag dataclass —— 存储解析后的 PropertyTag 结构
- **D-09:** PropertyValue 容器 —— 统一属性值容器 `{name: str, type: str, value: Any}`
- **原因:** 用户选择原生类型，简化阶段 4 JSON 输出

### 基本属性解析
- **D-10:** IntProperty —— 直接 read_i32() 或 read_i64()（根据 Type 名称判断）
- **D-11:** FloatProperty —— read_f32() 或 read_f64()
- **D-12:** BoolProperty —— 从 PropertyTag.BoolVal 读取（标志位 BoolTrue），无额外数据
- **D-13:** StrProperty —— 使用现有 read_fstring() 方法
- **D-14:** NameProperty —— 使用现有 read_name() 方法（u32 NameIndex + u32 Number）
- **D-15:** ObjectProperty —— 读取 FPackageIndex（int32），返回原始索引（延迟解析）
- **原因:** BoolProperty 从 Tag.BoolVal 标志位读取，匹配 UE 源码 PropertyTag.cpp；ObjectProperty 原始索引供阶段 3/4 解析

### 数组属性解析
- **D-16:** ArrayProperty 格式 —— 先读取元素数量（int32），再循环读取各元素值
- **D-17:** 数组元素类型 —— 从 PropertyTag.InnerType 或 TypeName 参数获取
- **D-18:** 嵌套深度限制 —— 最大 10 层，超出时跳过并标记
- **原因:** 用户确认 Count + 循环读取格式；嵌套深度限制防止无限递归

### PropertyTag 标志处理
- **D-19:** HasArrayIndex —— 读取额外的 int32 ArrayIndex（默认 0）
- **D-20:** HasPropertyGuid —— 读取 16 bytes GUID，存储但不使用
- **D-21:** HasPropertyExtensions —— 跳过扩展数据，推迟到阶段 3
- **D-22:** BoolTrue 标志 —— BoolProperty 值为 true 时设置
- **原因:** PropertyGuid 读取但不使用（阶段 3 可能需要）；Extensions 推迟到阶段 3

### 蓝图属性处理
- **D-23:** 蓝图特定属性推迟 —— ParentClass、NewVariables、FunctionGraphs 推迟到阶段 3
- **D-24:** 阶段 2 仅基本类型 —— Int、Float、Bool、String、Name、Object、Array
- **原因:** 用户选择推迟蓝图结构到阶段 3，阶段 2 专注基本属性解析

### 错误处理
- **D-25:** 单属性失败策略 —— 记录简短标记，跳过并继续下一个属性
- **D-26:** 跳过未知类型 —— 使用 PropertyTag.Size 定位到下一个属性（`seek(start + size)`）
- **D-27:** 参考UE源码加载方式 —— 不建议直接字节读取，遵循UE编辑器源码的属性加载模式
- **原因:** 用户强调参考 UE 源码加载方式；跳过策略匹配阶段 1 D-15 部分结果模式

### 测试策略
- **D-28:** 测试资产来源 —— FirstPerson（BP）+ FirstPersonC（C++对照）→ UE源码示例 → Lyra
- **D-29:** 版本覆盖 —— 边界版本测试（UE4 4.20、4.26、UE5 5.0、5.1）
- **D-30:** 组合方案 —— 合成数据单元测试 + 真实资产集成测试
- **原因:** 用户指定测试来源顺序；边界版本确保关键版本标志正确处理

### Claude 自行决定
- 具体 PropertyTag 字段解析顺序
- 嵌套深度限制实现方式（计数器或 Size 验证）
- 错误标记格式和详细程度
- 单元测试组织

</decisions>

<canonical_refs>
## Canonical References

**下游 agent 必须在规划或实现前阅读这些。**

### UE 源码参考（核心）
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Public\UObject\PropertyTag.h` —— FPropertyTag 结构定义、EPropertyTagFlags、EPropertyTagExtension
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Private\UObject\PropertyTag.cpp` —— PropertyTag 序列化逻辑、SerializeTaggedProperty
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Private\UObject\Class.cpp` §1514-1660 —— SerializeVersionedTaggedProperties 属性循环模式
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Private\UObject\LinkerLoad.h` §1112-1136 —— FName 序列化格式（NameIndex + Number）
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Private\UObject\PropertyBool.cpp` —— BoolProperty 序列化
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Private\UObject\PropertyArray.cpp` —— ArrayProperty 序列化
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Private\UObject\PropertyNumeric.cpp` —— IntProperty/FloatProperty 序列化
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Private\UObject\PropertyName.cpp` —— NameProperty 序列化

### 项目现有代码
- `uasset_read.py` —— FArchive 类、read_name()、read_fstring()、PackageIndex dataclass
- `tests/test_uasset_read.py` —— 阶段 1 测试模式参考

### 项目规划文档
- `.planning/PROJECT.md` —— 项目核心价值、约束（专注于未 cooked 资产）
- `.planning/REQUIREMENTS.md` —— PROP-01 至 PROP-09 需求定义
- `.planning/ROADMAP.md` —— 阶段 2 成功标准、主要工作、风险
- `.planning/phases/01-core-parsing/01-CONTEXT.md` —— 阶段 1 决策（FArchive、dataclasses、UTF-8、部分结果）

### 测试资产来源
- `E:\Develop\lib\UnrealEngine\Samples\FirstPerson` —— BP 示例项目（阶段 2 主要测试）
- `E:\Develop\lib\UnrealEngine\Samples\FirstPersonC` —— C++ 对照项目（BP vs C++ 比较）
- `LyraStarterGame/` —— Lyra 示例（最终验证）
- `E:\Develop\lib\UnrealEngine\Samples` —— UE 源码示例项目（多版本覆盖）

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **FArchive 类:** 所有读取方法可直接用于属性值解析（read_i32、read_f32、read_fstring、read_name）
- **PackageIndex dataclass:** ObjectProperty 值存储
- **ParseResult 模式:** 属性解析失败时返回部分结果 + 错误列表

### Established Patterns
- **版本感知解析:** 阶段 1 已实现版本检查模式（UE5 >= PACKAGE_SAVED_HASH_VERSION）
- **部分结果模式:** D-15/D-14 优雅降级，属性解析失败时继续
- **dataclasses 模型:** D-06 所有结构用 dataclass

### Integration Points
- 阶段 1 ExportMap: `ObjectExport.serial_offset` → 属性解析起始位置
- 阶段 1 NameMap: 属性名解析、NameProperty 值解析
- 阶段 3 蓝图提取: 需阶段 2 属性值作为蓝图变量默认值
- 阶段 4 JSON 输出: 需阶段 2 PropertyValue 结构

</code_context>

<specifics>
## Specific Ideas

- "不建议直接使用字节读取法，请参考 UE 编辑器源码中的加载方式" —— 用户强调遵循 UE 源码模式
- FirstPerson（BP）与 FirstPersonC（C++）对照测试 —— 验证 BP 属性解析正确性
- 边界版本测试（UE4 4.20、4.26、UE5 5.0、5.1）—— 确保关键版本标志正确处理

</specifics>

<deferred>
## Deferred Ideas

推迟到后续阶段的实现：

### 阶段 3（蓝图提取）
- ParentClass 解析为父类名
- NewVariables 提取变量定义
- FunctionGraphs 解析
- HasPropertyExtensions 数据解析（OverridableInformation）
- PropertyGuid 用于蓝图重命名属性匹配

### 阶段 4（输出与 CLI）
- ObjectProperty 索引解析为对象名
- PropertyValue JSON 输出格式化

### v2（高级属性）
- StructProperty 解析（嵌套结构）
- MapProperty 解析（键值对）
- SetProperty 解析（唯一元素集）
- EnumProperty 解析（枚举名 + 值）
- TextProperty 解析（带区域设置的 FText）

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-property-parsing*
*Context gathered: 2026-05-01*