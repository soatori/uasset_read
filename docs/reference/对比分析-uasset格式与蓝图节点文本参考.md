# BP_FirstPersonCharacter — uasset-format 参考 vs 蓝图节点文本参考 对比

> 生成时间: 2026-05-25
> 源文件:
> - `references/uasset-format/references/assets/blueprint-source.md` — uasset 格式参考（UBlueprint 结构）
> - `references/蓝图节点文本参考.md` — 蓝图节点文本序列化参考（Begin Object / End Object 格式）

---

## 1. 文档定位差异

| 维度 | uasset-format 参考 | 蓝图节点文本参考 |
|------|-------------------|-----------------|
| **层次** | 二进制资产结构层（FArchive 反序列化后的对象模型） | UE 编辑器文本序列化层（.uasset 中图表节点的文本表示） |
| **目标** | 定义 UBlueprint 类的字段、类型、源码位置 | 记录 EventGraph/FunctionGraph 中节点的文本序列化格式 |
| **受众** | 解析器开发者（反序列化逻辑） | 节点解析开发者（图表/引脚提取逻辑） |
| **格式** | Markdown 表格 + 源码引用 | Begin Object ... End Object 原始文本块 |

## 2. 内容覆盖范围对比

### 2.1 uasset-format 参考覆盖

| 覆盖区域 | 具体内容 |
|----------|---------|
| UBlueprint 核心字段 | BlueprintType, ParentClass, GeneratedClass, BlueprintSystemVersion 等 25+ 字段 |
| EBlueprintType 枚举 | Normal/Const/MacroLibrary/Interface/LevelScript/FunctionLibrary |
| EBlueprintStatus 枚举 | Unknown/Dirty/Error/UpToDate/BeingCreated/UpToDateWithWarnings |
| 图表引用字段 | UbergraphPages, FunctionGraphs, DelegateSignatureGraphs, MacroGraphs, EventGraphs |
| 成员字段 | NewVariables, GeneratedVariables, ImplementedInterfaces, CategorySorting |
| FBPVariableDescription | VarName, VarGuid, VarType, FriendlyName, Category, PropertyFlags 等 |
| FBPInterfaceDescription | Interface, Graphs |
| 编辑器专用字段 | Status, CompileMode, BlueprintDescription, ThumbnailInfo, LastEditedDocuments 等 |
| 版本差异 | UE5 新增特性, UE4 版本控制, WITH_EDITORONLY_DATA 分离 |

### 2.2 蓝图节点文本参考覆盖

| 覆盖区域 | 具体内容 |
|----------|---------|
| 节点类型 | K2Node_CallFunction, K2Node_EnhancedInputAction, K2Node_Event, K2Node_FunctionEntry, EdGraphNode_Comment, K2Node_Knot |
| 节点字段 | FunctionReference, InputAction, NodePosX/Y, NodeGuid, ErrorType |
| 引脚格式 | CustomProperties Pin (PinId, PinName, PinType.PinCategory, PinType.PinSubCategory, PinType.PinSubCategoryObject, LinkedTo, Direction, PersistentGuid, bHidden 等 20+ 属性) |
| SubPin 结构 | ActionValue_X/Y 分拆引脚, ParentPin 关系 |
| 实际示例 | EventGraph 中 14 个节点 + Move 函数 12 个节点的完整文本 |

## 3. 交叉验证：两者如何对应

### 3.1 UBlueprint → 图表 → 节点 映射链

```
UBlueprint (uasset-format 参考)
├── UbergraphPages → EventGraph (蓝图文本参考中的 EventGraph 区域)
│   ├── K2Node_EnhancedInputAction (IA_Look, IA_Move, IA_Jump, IA_MouseLook)
│   ├── K2Node_CallFunction (Jump, StopJumping, Move, Aim)
│   ├── K2Node_Event (Primary Thumbstick, Secondary Thumbstick, Touch Jump Start/End)
│   └── EdGraphNode_Comment (Camera Input, Movement Input, Jump Input)
├── FunctionGraphs → Aim / Move / UserConstructionScript (蓝图文本参考中的独立函数图)
│   ├── K2Node_FunctionEntry (函数入口)
│   ├── K2Node_CallFunction (AddMovementInput, GetActorForwardVector/RightVector)
│   └── K2Node_Knot (连线转接)
└── NewVariables → 蓝图文本参考未覆盖（变量定义不在图表节点中）
```

### 3.2 字段对应关系

| uasset-format 参考字段 | 蓝图文本参考对应 | 说明 |
|------------------------|-----------------|------|
| `UbergraphPages` | `EventGraph` 区域的所有 Begin Object 块 | UbergraphPages 数组引用的 UEdGraph 对象 |
| `FunctionGraphs` | `Move` / `Aim` 区域的 Begin Object 块 | FunctionGraphs 数组引用的 UEdGraph 对象 |
| `ParentClass` | `K2Node_CallFunction` 的 `PinType.PinSubCategoryObject="/Script/CoreUObject.Class'/Script/Engine.Character'"` | 父类在引脚类型中的体现 |
| `BlueprintDescription` | 不在节点文本中，在 Blueprint 导出属性中 | 编辑器专用字段，序列化在 Blueprint 对象上 |
| `NewVariables` | 不在节点文本中 | 变量定义在 FBPVariableDescription 结构中序列化 |
| 节点 `NodeGuid` | 对应 UEdGraphNode.NodeGuid 字段 | 文本格式与二进制反序列化后一致 |
| `CustomProperties Pin` | 对应 UEdGraphPin 的序列化文本表示 | 引脚结构，包含 PinId, PinType, LinkedTo 等 |

## 4. 解析器视角的差异

### 4.1 uasset-format 参考指导的解析路径

```
FArchive → PackageSummary → ImportMap/ExportMap
  → Export[1] (Blueprint 对象)
    → 反序列化属性: ParentClass, UbergraphPages, FunctionGraphs, NewVariables...
  → Export[9] (UEdGraph 对象 — UbergraphPage)
    → 反序列化 Nodes 数组 → 指向各个 UEdGraphNode 导出
  → Export[X] (UEdGraphNode 对象)
    → 反序列化 Pins 数组, NodePosX/Y, NodeGuid...
```

### 4.2 蓝图节点文本参考指导的解析目标

解析器在成功反序列化后，节点应输出为以下文本格式：

```
Begin Object Class=/Script/BlueprintGraph.K2Node_CallFunction Name="K2Node_CallFunction_X"
   FunctionReference=(MemberName="Jump",bSelfContext=True)
   NodePosX=3136
   NodePosY=-1040
   NodeGuid=XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
   CustomProperties Pin (PinId=XXX,PinName="execute",PinType.PinCategory="exec",...,LinkedTo=(...),...)
   CustomProperties Pin (PinId=XXX,PinName="then",Direction="EGPD_Output",PinType.PinCategory="exec",...)
End Object
```

**关键点**：这是 UE 编辑器在 .uasset 文本表示中的格式，不是解析器内部 JSON 格式。解析器的任务是：
1. 从二进制中还原出等价的节点结构
2. 验证还原结果与文本参考中的引脚连接、类型、GUID 一致

## 5. 已知解析差距

### 5.1 Pin 连接序列化问题（Phase 72-E）

| 问题 | uasset-format 参考 | 蓝图文本参考 | 解析器现状 |
|------|-------------------|-------------|-----------|
| LinkedTo 数组 | 未详细说明二进制结构 | `LinkedTo=(K2Node_EnhancedInputAction_5 6412140B...,)` | Pin 连接 count 字段读取为垃圾值，触发 P73-SUBPINS 恢复 |
| SubPins | 未涉及 | `SubPins=(K2Node_EnhancedInputAction_2 19CFB869...,)` | 部分 SubPin 恢复成功，部分失败 |
| PinType.PinSubCategoryObject | 未涉及 | 完整路径如 `/Script/CoreUObject.Class'/Script/Engine.Character'` | 部分解析为 None 或乱码 |

### 5.2 未覆盖区域

| 区域 | uasset-format 参考 | 蓝图文本参考 | 备注 |
|------|-------------------|-------------|------|
| BPGC 字节码 | 未涉及 | 未涉及 | 函数体逻辑在 Kismet 字节码中，需 Phase 61-64 解析 |
| SimpleConstructionScript | 字段存在 | 未涉及 | 组件层次结构在 SCS 中，不在图表节点中 |
| Timeline 模板 | 字段存在 | 未涉及 | 此蓝图无 Timeline |
| ComponentTemplates | 字段存在 | 未涉及 | 组件默认值在 BPGC CDO 中 |

## 6. 总结

| 维度 | 结论 |
|------|------|
| **互补性** | 两份文档互补：uasset-format 定义"对象有什么"，蓝图文本参考定义"节点长什么样" |
| **解析器对齐** | 解析器需要同时参考两者：先用 uasset-format 指导二进制结构解析，再用蓝图文本参考验证节点/引脚输出 |
| **当前差距** | Pin 连接序列化是主要差距 — uasset-format 未详细说明 LinkedTo 二进制格式，蓝图文本参考提供了完整格式但无法直接映射到二进制偏移 |
| **建议补充** | uasset-format 应增加 Pin 连接二进制序列化格式说明；蓝图文本参考可增加节点与 ExportMap 索引的映射关系 |
