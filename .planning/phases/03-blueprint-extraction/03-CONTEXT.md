# Phase 3: Blueprint Extraction - Context

**Gathered:** 2026-05-01
**Status:** Ready for planning

<domain>
## Phase Boundary

检测蓝图资产并提取蓝图特定元数据（父类、蓝图类型、变量定义、类型信息）。此阶段交付蓝图提取能力，为后续输出格式化提供蓝图专用数据。

**交付能力：**
- 蓝图资产检测（类名检测）
- 父类解析（ParentClass FPackageIndex → 对象名）
- 变量定义提取（FBPVariableDescription）
- 变量类型解析（FEdGraphPinType → 人类可读类型名）
- 默认值处理（字符串 → Python 原生类型）

**Requirements:** BLUE-01, BLUE-02, BLUE-03, BLUE-04, BLUE-05, BLUE-06

**固定范围（来自 ROADMAP.md）：**
- 蓝图类型检测（类名包含 "Blueprint" 或包路径模式）
- 父类解析（ParentClass FPackageIndex → ImportMap 或 ExportMap）
- 蓝图类型提取（BlueprintType 枚举）
- 变量定义解析（FBPVariableDescription 数组）
- FEdGraphPinType 解释（PinCategory、PinSubCategory、ContainerType）
- 变量元数据提取（Category、PropertyFlags、MetaDataArray）

</domain>

<decisions>
## Implementation Decisions

### 蓝图检测策略
- **D-01:** 类名检测 —— 检查 ExportMap 中导出的 ClassIndex 指向的类名包含 "Blueprint" 关键字
- **D-02:** 自动检测 —— parse_uasset() 解析后自动检测并提取蓝图元数据（非按需触发）
- **D-03:** 记录警告 —— 检测失败时在 ParseResult.errors 中添加警告信息（非静默跳过）
- **D-04:** 仅蓝图标志 —— 仅识别是否为蓝图，不区分 BlueprintType（Normal、Interface、MacroLibrary 等）
- **原因:** 用户选择自动检测配警告记录；BlueprintType 分类推迟到需要时

### 变量类型命名
- **D-05:** UE 原始名称 —— 使用 PinCategory 原始值如 "Integer"、"Object Reference"
- **D-06:** 容器+元素类型 —— 复合类型输出如 Array[Int]、Map[Str,Obj]（容器名+元素类型）
- **D-07:** 具体类引用 —— 尝试解析 PinSubCategoryObject 获取具体类名如 "AActor Reference"
- **D-08:** 完整结构解析 —— FEdGraphPinType 所有字段完整解析（PinCategory、PinSubCategory、PinSubCategoryObject、ContainerType 等）
- **原因:** UE 原始名称与源码一致；容器+元素类型提供完整信息；具体类引用帮助 AI agent 理解对象类型

### 父类解析深度
- **D-09:** 仅直接父类 —— 仅解析 ParentClass FPackageIndex 指向的直接父类，不追溯继承链
- **D-10:** 解析为对象名 —— FPackageIndex 解析为 ImportMap/ExportMap 中的对象名（非原始索引）
- **D-11:** 返回原始索引+警告 —— 父类引用缺失或解析失败时返回原始 FPackageIndex 值加警告
- **D-12:** 仅直接父类无循环风险 —— 不检测循环引用（仅一层解析无循环可能）
- **原因:** 仅直接父类满足基本继承信息需求；解析失败时有原始数据参考；循环检测推迟到完整继承链实现

### 默认值处理
- **D-13:** 解析为 Python 类型 —— 尝试解析 DefaultValue 字符串为 Python 原生类型（int、float、bool、str）
- **D-14:** 返回原始字符串 —— 类型解析失败时 fallback 输出原始字符串值
- **D-15:** 基本类型解析 —— 仅解析基本类型（int、float、bool、string），不尝试数组、对象引用等复杂类型
- **D-16:** 向量保持字符串 —— 向量类型默认值如 "(X=1.0,Y=2.0,Z=3.0)" 保持原始字符串格式
- **原因:** 基本类型解析覆盖常见情况且安全；失败 fallback 保证原始数据不丢失；复杂格式推迟到需要时

### Claude's Discretion
- 具体蓝图检测的类名匹配逻辑（包含 "Blueprint" 还是精确匹配）
- FEdGraphPinType 各字段的具体解析顺序和数据类型
- DefaultValue 字符串解析的正则表达式或解析器实现
- 变量元数据（Category、PropertyFlags）的输出格式
- 单元测试组织和测试资产选择

</decisions>

<canonical_refs>
## Canonical References

**下游 agent 必须在规划或实现前阅读这些。**

### UE 源码参考（蓝图结构）
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Public\UObject\Blueprint.h` —— 蓝图结构定义、BlueprintType、父类、变量数组
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Public\UObject\EdGraphPin.h` —— FEdGraphPinType 结构、PinCategory、PinSubCategory
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Private\UObject\Blueprint.cpp` —— 蓝图序列化逻辑、变量定义解析
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Private\UObject\EdGraphPin.cpp` —— PinType 序列化、类型解析

### 项目现有代码
- `uasset_read.py` —— FArchive 类、read_name()、read_fstring()、PackageIndex dataclass、ParseResult 模式
- `tests/test_uasset_read.py` —— 阶段 1/2 测试模式参考

### 项目规划文档
- `.planning/PROJECT.md` —— 项目核心价值、约束（专注于未 cooked 资产）
- `.planning/REQUIREMENTS.md` —— BLUE-01 至 BLUE-06 需求定义
- `.planning/ROADMAP.md` —— 阶段 3 成功标准、主要工作、风险
- `.planning/phases/01-core-parsing/01-CONTEXT.md` —— 阶段 1 决策（FArchive、dataclasses、UTF-8、部分结果）
- `.planning/phases/02-property-parsing/02-CONTEXT.md` —— 阶段 2 决策（ExportReader、PropertyTag、属性解析）

### 测试资产来源
- `E:\Develop\lib\UnrealEngine\Samples\FirstPerson` —— BP 示例项目（蓝图检测测试）
- `LyraStarterGame/` —— Lyra 示例（复杂蓝图验证）
- `E:\Develop\lib\UnrealEngine\Samples` —— UE 源码示例项目（多类型蓝图）

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **FArchive 类:** 所有读取方法可直接用于蓝图元数据解析（read_i32、read_fstring、read_name）
- **PackageIndex dataclass:** ParentClass 值存储和解析
- **ParseResult 模式:** 蓝图检测失败时返回部分结果 + 警告列表
- **ExportReader 类（阶段 2）:** 导出头解析 + 属性循环模式可复用

### Established Patterns
- **版本感知解析:** 阶段 1 已实现版本检查模式（UE5 >= PACKAGE_SAVED_HASH_VERSION）
- **部分结果模式:** D-15/D-14 优雅降级，检测/解析失败时继续
- **dataclasses 模型:** D-06 所有结构用 dataclass（FEdGraphPinType、FBPVariableDescription 等）
- **警告记录模式:** 阶段 2 D-25 单属性失败策略，蓝图检测失败配警告

### Integration Points
- 阶段 1 ExportMap: 导出 ClassIndex → 蓝图检测依据
- 阶段 1 ImportMap: ParentClass FPackageIndex 解析 → 父类名
- 阶段 1 NameMap: 变量名解析、PinSubCategoryObject 类名解析
- 阶段 2 PropertyValue: 变量默认值继承阶段 2 解析结果
- 阶段 4 JSON 输出: 需阶段 3 BlueprintMetadata 结构

</code_context>

<specifics>
## Specific Ideas

- "自动检测并提取蓝图元数据" —— 用户选择全自动模式，parse_uasset() 返回即包含蓝图数据
- "仅直接父类无循环风险" —— 用户确认仅一层解析，简化实现
- "向量类型保持字符串" —— (X=...,Y=...,Z=...) 格式暂不解析，推迟到需要时
- DefaultValue 基本类型解析 —— int、float、bool、str 覆盖常见情况

</specifics>

<deferred>
## Deferred Ideas

推迟到后续阶段的实现：

### 阶段 4（输出与 CLI）
- BlueprintMetadata JSON 输出格式化
- 蓝图数据文本摘要格式

### v2（蓝图高级功能）
- BlueprintType 完整分类（Normal、Interface、MacroLibrary、FunctionLibrary）
- 完整继承链解析（递归到 UObject）
- 循环引用检测
- 蓝图图提取（UEdGraph、Nodes、Pins）
- 复杂默认值解析（数组、向量、对象引用）
- 变量元数据完整提取（MetaDataArray 详细解析）

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-blueprint-extraction*
*Context gathered: 2026-05-01*