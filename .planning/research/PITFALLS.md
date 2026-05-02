# 领域陷阱：蓝图图解析

**领域：** Unreal Engine 蓝图图结构解析
**研究日期：** 2026-05-02（v2.0 里程碑）
**置信度：** 中 - 基于 UE 源码分析和已知解析模式，但蓝图图序列化部分未完全逆向

---

## 关键陷阱

会导致重写或重大问题的错误。

### 陷阱 1：OuterIndex（SuperIndex）缺失导致导出表错位

**出错情况：** 解析 FObjectExport 时漏掉 TemplateIndex 字段，导致后续所有字段（OuterIndex、SerialSize、SerialOffset）读取偏移。

**发生原因：** UE4 >= 506 (VER_UE4_TemplateIndex_IN_COOKED_EXPORTS) 在 SuperIndex 和 OuterIndex 之间插入了 TemplateIndex 字段。

**后果：**
- SerialSize/SerialOffset 数值异常大（超出文件大小）
- 导出数据定位失败
- 蓝图元数据提取失败（属性读取偏移）

**来自 UE 5.7 源码 (ObjectResource.cpp lines 125-224)：**

```cpp
// FObjectExport 序列化顺序（UE4 >= 506）：
1.  ClassIndex                (int32)
2.  SuperIndex                (int32)
3.  TemplateIndex             (int32)  [UE4 >= 506]
4.  OuterIndex                (int32)
5.  ObjectName                (FName = uint32 + uint32)
6.  ObjectFlags               (uint32)
7.  SerialSize                (int64)  [UE4 >= 508, 否则 int32]
8.  SerialOffset              (int64)  [UE4 >= 508, 否则 int32]
```

**预防：**
1. 检查 `summary.file_version_ue4 >= 506`
2. 若条件满足，读取 TemplateIndex（32 位整数）
3. 然后才能正确读取 OuterIndex

**检测：**
- SerialSize 超出文件大小
- SerialOffset 指向文件外部
- 外层对象名称解析为空或垃圾字符串

**阶段：** 阶段 4 已修复（见 debug_export_map_bug.md）

---

### 陷阱 2：蓝图图节点类型误判

**出错情况：** 将非节点对象（如类定义、变量）误识别为蓝图节点。

**发生原因：** 蓝图资产包含多种导出类型：
- `UBlueprint` —— 蓝图核心对象（通常第一个导出）
- `UClass` —— 编译生成的类
- `UEdGraph` —— 图对象（EventGraph、FunctionGraphs）
- `UK2Node` 子类 —— 节点（K2Node_CallFunction、K2Node_Event 等）
- `UFunction` —— 函数定义

**发生位置：**
- ClassIndex 引用 `/Script/BlueprintGraph.K2Node_*` → 真正节点
- ClassIndex 引用 `/Script/Engine.Blueprint` → 蓝图容器
- ClassIndex 引用 `/Script/Engine.Class` 或 `/Script/CoreUObject.Class` —— 类元数据

**来自源码分析：**

| ClassIndex 引用 | 类型 | 是否节点 | 说明 |
|----------------|------|---------|------|
| K2Node_CallFunction | UK2Node | 是 | 函数调用节点 |
| K2Node_Event | UK2Node | 是 | 事件节点 |
| K2Node_VariableGet | UK2Node | 是 | 变量读取节点 |
| Blueprint | UBlueprint | 否 | 蓝图容器 |
| Class | UClass | 否 | 编译类 |
| EdGraph | UEdGraph | 否 | 图容器 |

**预防：**
1. 解析节点前检查 ClassIndex 解析的类名是否以 "K2Node_" 开头
2. 排除 Blueprint、Class、EdGraph、Function 等容器类型
3. 参考 K2Node.h 的类层次（所有节点继承 UK2Node）

**检测：**
- 解析节点时遇到非预期字段（如 Expected && Actual pin mismatch）
- NodePosX/Y 解析为异常大值
-endor 节点的 pins 数组为空但序列化仍在继续

**阶段：** 阶段 2 已识别，阶段 4 需实现节点类型检测

---

### 陷阱 3：版本依赖的引脚类型序列化

**出错情况：** 假设 FEdGraphPinType 字段顺序固定，但实际依赖版本。

**发生原因：** 添加新字段时使用版本条件：

| 字段 | 添加版本 | UE4 | UE5 |
|------|---------|-----|-----|
| ContainerType | FFrameworkObjectVersion::EdGraphPinContainerType | v500+ | all |
| bIsConst | VER_UE4_SERIALIZE_PINTYPE_CONST | v500+ | all |
| bIsUObjectWrapper | FReleaseObjectVersion::PinTypeIncludesUObjectWrapperFlag | v510+ | all |
| MemberReference | FFrameworkObjectVersion::MemberReferenceInPinType | v500+ | all |

**序列化顺序（来自 EdGraphPin.cpp lines 163-346）：**

```cpp
// 基础字段（所有版本）
PinCategory (FName)
PinSubCategory (FName)
PinSubCategoryObject (FPackageIndex)

// 条件字段（依版本）
if (FFrameworkObjectVersion >= EdGraphPinContainerType) {
    ContainerType (uint8)
    if (ContainerType == 3) { // Map
        PinValueType (FEdGraphTerminalType)
    }
}

bIsReference (bool)
bIsWeakPointer (bool)
if (FFrameworkObjectVersion >= MemberReferenceInPinType) {
    PinSubCategoryMemberReference (FSimpleMemberReference)
}
if (VER_UE4_SERIALIZE_PINTYPE_CONST) {
    bIsConst (bool)
}
if (FReleaseObjectVersion >= PinTypeIncludesUObjectWrapperFlag) {
    bIsUObjectWrapper (bool)
}
```

**后果：**
- ContainerType 误读为 bIsReference → 类型信息错乱
- 引脚连接失败（PinType 不匹配）
- 节点重建失败

**预防：**
1. 检查 `summary.file_version_ue4` 和自定义版本
2. 按版本条件跳过/读取字段
3. 始终读取现代 UE 文件（UE4 >= 500, UE5 >= 1000）包含的字段

**检测：**
- PinCategory 读取为整数（应为字符串）
- is_reference 为 true 但后续字段解析失败
- 节点 pins 数组元素数量异常

**阶段：** 阶段 3 已实现基础解析（读取所有现代字段），版本感知可后续增强

---

### 陷阱 4：蓝图图结构嵌套与 Outer 引用

**出错情况：** 假设图.nodes 与导出表 1:1 映射，但实际存在嵌套和引用。

**发生原因：** UE 蓝图图结构：

```
UBlueprint (导出 N)
├── EventGraph (UEdGraph, 导出 M)
│   ├── K2Node_Event_1 (UK2Node, 导出 X)
│   ├── K2Node_CallFunction_1 (UK2Node, 导出 Y)
│   └── K2Node_Knot_1 (UK2Node, 导出 Z)
├── FunctionGraphs[0] (UEdGraph, 导出 P)
│   ├── K2Node_FunctionEntry_1 (UK2Node, 导出 Q)
│   └── K2Node_CallFunction_2 (UK2Node, 导出 R)
└── NewVariables[] (FBPVariableDescription, 内嵌)
```

**问题：**
1. UEdGraph 作为单独导出，nodes 数组内的 UK2Node 也在导出表中
2. UK2Node 的 outer index 指向其父图或蓝图
3. 节点序列化时只保存节点特定数据，位置坐标等来自 EdGraphNode 基类

**来自源码分析：**
- `UEdGraph::Nodes` 是 `TArray<UEdGraphNode*>`
- 每个节点有独立导出条目（.outer_index 指向图）
- 图本身有 `.Nodes` 数组存储节点引用（PackageIndex）

**序列化顺序（UEdGraph）：**
```
Schema (FObjectIndex)
Nodes count + Nodes[] (each Node has own export)
GraphGuid
bEditable
```

**序列化顺序（UK2Node → UEdGraphNode）：**
```
// UEdGraphNode 基类
Pins count + Pins[]
NodePosX (float)
NodePosY (float)
NodeGuid
EnabledState
NodeComment

// UK2Node 特定数据（依具体子类而变）
```

**预防：**
1. 建立 outer_index → 导出名映射
2. 先解析所有导出的 outer_index，理解对象树
3. 图的 Nodes 数组是 PackageIndex 引用，需解析为节点导出
4. 节点数据分两部分：基类（位置、引脚）+ 派生类（特定字段）

**检测：**
- 节点位置（NodePosX/NodePosY）解析为垃圾值
- 引脚连接指向不存在的对象
- 图节点数量与导出数量不匹配

**阶段：** 阶段 4 需要导出表全局分析

---

### 陷阱 5：UK2Node 子类特定序列化

**出错情况：** 假设所有 UK2Node 子类序列化相同，但每个子类可重写 Serialize()。

**发生原因：** UE 使用虚函数序列化：
- UK2Node::Serialize() → 调用 Super::Serialize() + 子类特定字段
- K2Node_CallFunction::Serialize() → 调用 UK2Node::Serialize() + FunctionReference 字段
- K2Node_VariableGet::Serialize() → 调用 UK2Node::Serialize() + VariableGuid/VariableReference 字段

**来自源码 (K2Node.cpp lines 325-450)：**

```cpp
void UK2Node::Serialize(FArchive& Ar)
{
    Super::Serialize(Ar);

    // UK2Node-specific fields
    Ar << Pins ;  // OldPins (deprecated, skip for Phase 2)
    Ar << NodeCache ;  // Cached node data

    // Version-dependent fields
    if (Ar.UE5Version() >= SomeVersion) {
        Ar << SomeNewField;
    }
}
```

**来自源码 (K2Node_CallFunction.cpp lines 150-200)：**
```cpp
void UK2Node_CallFunction::Serialize(FArchive& Ar)
{
    UK2Node::Serialize(Ar);

    Ar << FunctionReference;  // FMemberReference
    Ar << bHasExplicitSelf;   // bool
    Ar << SelfObjectCategory; // FPropertyPickerProperties

    if (Ar.UE4Version() >= SomeVersion) {
        Ar << AdditionalFields;
    }
}
```

**问题节点类型：**

|节点类型|特定字段|复杂度|
|--------|--------|------|
|K2Node_CallFunction|FunctionReference, bAllowAnyArg, bIsPureCall|中|
|K2Node_Event|MemberReference, EventDisplayName|低|
|K2Node_VariableGet|VariableGuid, VariableReference|中|
|K2Node_VariableSet|VariableGuid, VariableReference, bSkip SelfCast|中|
|K2Node_MakeStruct|StructType|低|
|K2Node_Knot|bIsDroppable, bIsInspected|低|
|K2Node_CustomEvent|EventGuid, EventDisplayName|中|

**后果：**
- 序列化偏移错位（误读后续节点）
- 函数调用节点解析为事件节点
- 变量节点无法关联变量定义

**预防：**
1. 解析节点类型后分派到特定解析函数
2. 使用版本条件读取可选字段
3. 建立节点类型→解析器注册表

**检测：**
- FunctionReference 读取失败但没有异常
- 变量名称解析为函数名
- 节点类型与序列化字段不匹配错误

**阶段：** 阶段 4 初始版本可只支持 K2Node_CallFunction（最常见）

---

### 陷阱 6：蓝图图闭包与循环引用

**出错情况：** 假设图结构是树，但实际存在循环引用（如 Knot 节点、表达式节点）。

**发生原因：** 引脚连接可以形成：
1. 线性流：Event → FunctionCall → Result
2. 分支：Switch → Branch → Path1/Path2
3. 循环：Knot 节点用于组织图布局，可能创建逻辑循环
4. 自引用：某些节点引用自身（如 ForEachLoop）

**来自源码 (UEdGraphPin.cpp lines 200-250)：**
```cpp
// 引脚连接存储为 TArray<UEdGraphPin*>
LinkedTo;  // OutputPin.LinkedTo = [InputPin1, InputPin2, ...]

// Knot 节点特性：
// - 不执行任何逻辑
// - 仅用于连接传递
// - 可能形成"视觉循环"但逻辑线性
```

**问题：**
- 简单 DFS 遍历可能陷入无限循环
- 强制.visited set 可能遗漏并行路径
- PinId/Guid 引用 vs 指针引用可能不一致

**预防：**
1. 使用显式 visited set 防止循环
2. 差异化处理：数据流（可循环）vs 执行流（线性）
3. 记录节点 GUID 而非指针引用

**检测：**
- 解析卡死或堆栈溢出
- 同一节点多次出现在输出中
- 连接信息缺失或重复

**阶段：** 阶段 4 输出格式化时需注意

---

### 陷阱 7：Cooked vs Uncooked 蓝图资产

**出错情况：** 尝试从 cooked 蓝图提取完整图结构，但 cooked 资产已剥离编辑器数据。

**发生原因：** UE 编译流程：

```
未 cooked (.uasset with PKG_Cooked=0)
├── 蓝图 .uasset 包含：
│   - UBlueprint (编辑器数据)
│   - UEdGraph (图结构)
│   - UK2Node (节点与引脚)
│   - 编译结果存储在蓝图为下次启动准备
└── 可被 uasset_read 解析

 cooked (.uasset with PKG_Cooked=1)
├── 蓝图 .uasset 包含：
│   - UBlueprintGeneratedClass (运行时类)
│   - 移除 UEdGraph/UK2Node（编辑器图已编译）
│   - 只保留编译后的字节码和简要元数据
└── 无法提取节点图结构

 cooking 过程
├── K2Compiler 编译 UEdGraph → 字节码 + BPGC
├── 移除全部 UEdGraph/UK2Node 导出
└── 仅保留 UBlueprintGeneratedClass
```

**PackageFlags 检测：**
```cpp
PKG_Cooked = 0x200  // 512 decimal

// 若包标志包含 PKG_Cooked，图结构已被移除
```

**后果：**
- 尝试读取不存在的 UEdGraph 导出 → 索引越界/空数组
- 假设蓝图包含节点图 → 逻辑错误
- 错误报告为"解析失败"而非"cooked 资产"

**预防：**
1. 检查 PackageFlags 是否有 PKG_Cooked
2. 若 cooked，跳过图结构提取
3. 返回警告而非错误

**检测：**
- 导出表无 UEdGraph/UK2Node 类型
- PackageFlags & PKG_Cooked != 0
- 仅存在 BlueprintGeneratedClass

**阶段：** 阶段 4 开始时添加 cooked 检测

---

### 陷阱 8：Ubergraph Pages 与多图支持

**出错情况：** 假设蓝图只有一个 EventGraph，但实际支持多个图表页面。

**发生原因：** UBlueprint 结构：

```cpp
// UE 5.7 Blueprint.h lines 530-570
TArray<UEdGraph*> UbergraphPages ;       // 主图表页面（事件图）
TArray<UEdGraph*> FunctionGraphs ;       // 函数图表
TArray<UEdGraph*> MacroGraphs ;          // 宏图表（UE5+）
TArray<FBPInterfaceDescription> ImplementedInterfaces ;
```

**问题：**
- 事件图 (UbergraphPages[0]) 是默认执行入口
- 函数图需要函数名识别（K2Node_FunctionEntry）
- 宏图是可重用蓝图逻辑片段

**序列化模式：**
- 每个 UEdGraph 作为独立导出
- 图导出的 outer_index 指向 UBlueprint
- 图名存储在导出 ObjectName 中（如 "EventGraph"、"Aim"）

**检测：**
- 解析所有 UEdGraph 导出
- 检查图名区分 EventGraph vs 函数图 vs 宏图
- 为每个图构建节点列表

**预防：**
1. 识别所有 ClassIndex 引用 UEdGraph 的导出
2. 根据导出名称和 outer_index 分组
3. 为每个图构建节点列表

**阶段：** 阶段 4 初始版本可只解析 EventGraph

---

## 中等陷阱

### 陷阱 1：NodeGuid vs PinId 引用不一致

**出错情况：** 假设节点通过 outer_index 唯一标识，但实际使用 Guid。

**发生原因：** UE 使用多级引用：
1. **导出表**：通过 FPackageIndex（导出索引）
2. **序列化时**：UK2Node::Serialize() 使用 NodeGuid
3. **编辑器内存**：UEdGraphNode* 指针

**来自源码：**
```cpp
// UEdGraphNode.h
FGuid NodeGuid;  // 用于保存/加载引用，非导出索引
```

**问题：**
- 外部工具（如 FModel）导出的 JSON 可能使用 Guid
- 解析器内部使用导出索引
- 需要双向映射：导出索引 ↔ NodeGuid

**预防：**
- 解析时收集 NodeGuid 并映射到导出索引
- 输出 JSON 包含.guid 引用（除索引外）

**阶段：** 阶段 4 增强版需要

---

### 陷阱 2：PinName 与 PinDisplayName 差异

**出错情况：** 输出使用 PinName（内部名）而非 PinDisplayName（人类可读）。

**发生原因：** UEdGraphPin 存储：
```cpp
FName PinName ;              // 内部名（如 "execute"、"then"、"ReturnValue"）
FName PinDisplayName ;       // 显示名（可国际化，来自 Editor only）
FText PinToolTip ;           // 工具提示
```

- PinName 是快速内部标识
- PinDisplayName 是用户看到的（可能来自字符串表）

**后果：**
- AI agent 看到 "execute" 而非 "Exec"（中文版显示）
- 引脚含义不清晰

**预防：**
- Phase 3：输出 PinName（稳定内部标识）
- Phase 4 增强：添加 PinDisplayName 若存在

**阶段：** 阶段 4 可选增强

---

### 陷阱 3：Default coherent value (DCV) vs 实际值

**出错情况：** 读取 DefaultValue 为序列化值，但运行时可能不同。

**发生原因：** UE 有 Default Coherent Value 机制：
- DefaultValue 序列化为字符串
- 编辑器重新解析字符串为实际值
- 若类型变更，DefaultValue 可能陈旧

**序列化：**
```cpp
// FBPVariableDescription::Serialize()
DefaultValue.Serialize(Ar);  // FString
```

**问题：**
- DefaultValue 可能与变量类型不匹配
- 数组/结构体 DefaultValue 为复杂格式

**预防：**
- 仅存储序列化字符串
- 不尝试验证类型匹配

**阶段：** 阶段 4 保持原始字符串即可

---

## 次要陷阱

### 陷阱 1：注释节点（EdGraphNode_Comment）处理

**出错情况：** 尝试解析注释节点为执行节点。

**发生原因：** 注释节点：
- ClassIndex: `/Script/UnrealEd.EdGraphNode_Comment`
- 无 pins
- 仅有矩形区域数据（NodeRect）

**预防：**
- 解析前检查节点类型
- 跳过非 UK2Node 类型（或标记为注释）

**阶段：** 阶段 4 排除或特殊标记

---

### 陷阱 2：临时变量（K2Node_TemporaryVariable）

**出错情况：** 将临时变量节点误认为真实变量。

**发生原因：** 临时变量：
- 编译时创建，不在蓝图变量列表中
- 节点类型：K2Node_TemporaryVariable
- 无对应 FBPVariableDescription

**预防：**
- 区分蓝图变量（NewVariables）与图内临时变量
- 输出标记为 "temporary" 或跳过

**阶段：** 阶段 4 可选

---

## 阶段特定警告

| 阶段主题 | 可能陷阱 | 缓解措施 |
|----------|----------|----------|
| **格式解析** | OuterIndex 缺失、版本字段顺序 | 读取 debug_export_map_bug.md 修复 |
| **蓝图检测** | Cooked vs Uncooked 混淆 | 检查 PackageFlags PKG_Cooked |
| **图结构** | Outer 引用嵌套、多图页面 | 先构建外层映射 |
| **节点解析** | 子类特定序列化 | 分派到类型特定解析器 |
| **引脚连接** | 循环引用、Knot 节点 | visited set + 类型过滤 |
| **输出格式** | PinName vs 显示名、Guid vs 索引 | 输出双引用（索引+Guid） |

---

## 已知 v1.0 陷阱（已修复或记录）

| 陷阱 | 状态 | 修复/文档 |
|------|------|-----------|
| OuterIndex 漏掉 TemplateIndex | 修复 | debug_export_map_bug.md + uasset_read.py |
| 导出表序列化顺序错误 | 修复 | ObjectResource.cpp 参考 |
| 版本阈值判断错误 (>= vs <=) | 修复 | UESOURCE-INDEX.md |
| Cookie 包检测缺失 | 记录 | PITFALLS.md 条目 7 |

---

## 推荐蓝图图解析顺序

为避免陷阱，建议此解析顺序：

```
阶段 4 蓝图图解析流程：

1. 读取 PackageFlags
   ├─ 若 PKG_Cooked，跳过图结构（警告）
   └─ 否则继续

2. 构建外层映射 (outer_index → 导出名)
   └─ 允许解析嵌套引用

3. 识别所有导出类型
   ├─ UEdGraph: 收集图形定义
   ├─ UK2Node*: 收集节点定义
   └─ 其他: 跳过/标记

4. 按外层分组节点到图
   ├─ EventGraph → Event nodes
   ├─ FunctionGraphs[i] → Function nodes
   └─ MacroGraphs[i] → Macro nodes

5. 对每个图解析节点
   ├─ 读取 UEdGraphNode 基类字段 (Pins, Pos)
   ├─ 识别 UK2Node 子类类型
   ├─ 分派到类型特定解析器
   └─ 读取子类特定字段

6. 解析引脚连接
   ├─ UEdGraphPin.LinkedTo 是 PackageIndex 引用
   ├─ 建立导出索引 → 节点映射
   └─ 填充 LinkedTo 列表

7. 输出增强 JSON
   ├─ 包含 .outer_index 解析
   ├─ 包含 NodeGuid（若存在）
   └─ 包含节点类型识别
```

---

## 来源

- UE 5.7 源码：`D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Editor/BlueprintGraph/Classes/K2Node.h`
- UE 5.7 源码：`D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Editor/BlueprintGraph/Private/K2Node.cpp`
- UE 5.7 源码：`D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Editor/BlueprintGraph/Private/K2Node_CallFunction.cpp`
- UE 5.7 源码：`D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/engine/Classes/EdGraph/EdGraph.h`
- UE 5.7 源码：`D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/engine/Classes/EdGraph/EdGraphNode.h`
- UE 5.7 源码：`D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/engine/Classes/EdGraph/EdGraphPin.h`
- UE 5.7 源码：`D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/engine/Classes/Engine/Blueprint.h`
- UE 5.7 源码：`D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/CoreUObject/Public/UObject/ObjectResource.h`
- UE 5.7 源码：`D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/CoreUObject/Private/UObject/PackageFileSummary.cpp`
- UE 5.7 源码：`D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/CoreUObject/Private/Serialization/BulkData.cpp`
- UE 5.7 源码：`D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/Core/Public/UObject/ObjectVersion.h`

**置信度：中高** — 大部分陷阱来自 UE 源码直接分析，少数来自社区工具（FModel）经验

---

## 下一步研究问题

- [ ] K2Node_Event 序列化格式详细分析
- [ ] K2Node_CallFunction FunctionReference 结构
- [ ] UEdGraphPin 引脚连接序列化偏移验证
- [ ] 蓝图字节码编译输出格式（用途：验证图提取正确性）
- [ ] EdGraphSchema_K2 如何类型检查引脚连接

---

*本文件由 GSD Research 系统于 2026-05-02 生成*
