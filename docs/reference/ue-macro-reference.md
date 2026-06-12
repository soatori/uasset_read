# Unreal Engine 蓝图宏（Macro）参考文档

> 基于 UE5 源码完整调查 | 适用于 uasset_read 解析器开发

---

## 目录

- [1. 概述](#1-概述)
  - [1.1 宏的本质](#11-宏的本质)
  - [1.2 宏 vs 函数](#12-宏-vs-函数)
  - [1.3 宏 vs 折叠图](#13-宏-vs-折叠图)
- [2. 数据结构](#2-数据结构)
  - [2.1 FGraphReference](#21-fgraphreference)
  - [2.2 EGraphType](#22-egraphtype)
  - [2.3 UK2Node_MacroInstance](#23-uk2node_macroinstance)
  - [2.4 UK2Node_Tunnel](#24-uk2node_tunnel)
  - [2.5 FKismetUserDeclaredFunctionMetadata](#25-fkismetuserdeclaredfunctionmetadata)
- [3. 序列化格式](#3-序列化格式)
  - [3.1 .uasset 中的宏实例属性](#31-uasset-中的宏实例属性)
  - [3.2 MacroGraphReference 结构](#32-macrographreference-结构)
  - [3.3 GraphGuid 生成规则](#33-graphguid-生成规则)
- [4. 核心类关系](#4-核心类关系)
  - [4.1 类继承树](#41-继承树)
  - [4.2 运行时关系图](#42-运行时关系图)
  - [4.3 序列化关系图](#43-序列化关系图)
- [5. 编译期展开](#5-编译期展开)
  - [5.1 展开流程](#51-展开流程)
  - [5.2 循环检测](#52-循环检测)
  - [5.3 引脚映射](#53-引脚映射)
  - [5.4 Tunnel 重连](#54-tunnel-重连)
  - [5.5 中间节点插入](#55-中间节点插入)
- [6. Wildcard 类型推断](#6-wildcard-类型推断)
  - [6.1 简单模式](#61-简单模式)
  - [6.2 智能模式](#62-智能模式)
  - [6.3 推断传播算法](#63-推断传播算法)
- [7. 标准宏库](#7-标准宏库)
  - [7.1 内置宏列表](#71-内置宏列表)
  - [7.2 自定义宏库](#72-自定义宏库)
- [8. 解析器实现指南](#8-解析器实现指南)
  - [8.1 当前状态](#81-当前状态)
  - [8.2 完整展开方案](#82-完整展开方案)
  - [8.3 数据结构设计](#83-数据结构设计)
  - [8.4 递归展开算法](#84-递归展开算法)
  - [8.5 执行链穿透](#85-执行链穿透)
  - [8.6 边界情况处理](#86-边界情况处理)
- [9. 关键源码索引](#9-关键源码索引)
  - [9.1 核心文件](#91-核心文件)
  - [9.2 关键函数](#92-关键函数)
  - [9.3 相关类型](#93-相关类型)

---

## 1. 概述

### 1.1 宏的本质

蓝图宏（Blueprint Macro）是 Unreal Engine 中一种**可复用的子图**。它允许开发者将一组节点和连线封装成一个可调用的节点实例，实现逻辑复用。

```
┌──────────────────────────────────────────────┐
│                  宏图 (Macro Graph)            │
│                                              │
│  [Entry Tunnel] ──▶ [节点 A] ──▶ [节点 B]    │
│                                   │          │
│                              [节点 C] ──▶ [Exit Tunnel]
│                                              │
└──────────────────────────────────────────────┘
              ↕ 引用
┌─────────────────────────────┐
│     MacroInstance 节点       │  ← 在调用方蓝图中出现
│  引脚 = Tunnel 定义的端口    │
└─────────────────────────────┘
```

**核心特征**：
- 宏在**编译期展开**（inline expansion），运行时不存在宏实例
- 未烘焙（Unbaked）资产保留 `MacroGraphReference`，解析器可据此展开
- 已烘焙（Cooked）资产中宏已被内联，所有节点直接存在于图中
- 宏可以**嵌套**——宏图内部可包含另一个 MacroInstance

### 1.2 宏 vs 函数

| 对比项 | 宏（Macro） | 函数（Function） |
|--------|------------|-----------------|
| **图类型** | `GT_Macro` | `GT_Function` |
| **执行入口** | Tunnel 节点（可多个入口） | K2Node_FunctionEntry（单一入口） |
| **返回机制** | Tunnel 节点（可多个出口） | K2Node_FunctionResult（单一/无返回） |
| **编译期** | 内联展开到调用处 | 编译为独立字节码函数 |
| **运行时** | 节点直接存在于调用方图 | 独立存在，通过 `ExecuteUbergraph` 调用 |
| **执行流** | 与调用方在同一执行链中 | 跨执行链跳转 |
| **局部变量** | 使用调用方的变量空间 | 拥有独立的局部变量 |
| **Latent 动作** | 可在函数图中使用（如果宏本身不含 Latent） | 可在函数中使用 |
| **Latent 限制** | 含 Latent 的宏**不可**放入函数图 | 无此限制 |

**执行流差异示意**：

```
宏的执行流（内联）：
  BeginPlay → [前置节点] → [宏内部节点A] → [宏内部节点B] → [后续节点]
  整个流程在同一个执行链中

函数的执行流（跳转）：
  BeginPlay → [前置节点] → CallFunction节点 → [后续节点]
                           ↓
                    跳转到函数图的字节码执行
```

### 1.3 宏 vs 折叠图

| 对比项 | 宏（Macro） | 折叠图（Collapsed Graph / Composite） |
|--------|------------|-------------------------------------|
| **节点类** | `UK2Node_MacroInstance` | `UK2Node_Composite` |
| **复用性** | 可被多个蓝图引用 | 仅在当前图内有效 |
| **存储位置** | 可在 MacroLibrary 蓝图中 | 存储在当前 UEdGraph 的 Nodes 数组中 |
| **展开时机** | 编译期展开 | 编译期展开 |
| **图引用** | `FGraphReference` 跨资产引用 | 通过 `ChildGraph` 关联 |
| **图标** | 专用宏图标 | 与普通节点相同 |

**UE 源码关键区别**：

```cpp
// K2Node_MacroInstance.cpp:130-133
// 只找精确的 UK2Node_Tunnel，排除 Composite 和 MacroInstance 子类
if (TunnelNode->GetClass() == UK2Node_Tunnel::StaticClass())
{
    // 处理引脚...
}

// KismetCompiler.cpp:4385-4389
// 宏展开时遇到 Composite 节点：不做处理
if (const UK2Node_Composite* const CompositeNode = Cast<const UK2Node_Composite>(DuplicatedNode))
{
    continue;  // 子折叠图已在内部，无需额外操作
}
```

---

## 2. 数据结构

### 2.1 FGraphReference

**文件**：`Engine/Source/Runtime/Engine/Classes/EdGraph/EdGraph.h:21-50`

```cpp
USTRUCT()
struct FGraphReference
{
    GENERATED_USTRUCT_BODY()

protected:
    // 指向实际的图对象
    UPROPERTY()
    mutable TObjectPtr<class UEdGraph> MacroGraph;

    // 图所属的蓝图
    UPROPERTY()
    TObjectPtr<class UBlueprint> GraphBlueprint;

    // 图的 GUID，用于重命名后重新查找
    UPROPERTY()
    FGuid GraphGuid;

public:
    // 序列化支持
    friend FArchive& operator<<(FArchive& Ar, FGraphReference& Ref);

    // 访问器
    UEdGraph* GetGraph() const { return MacroGraph; }
    void SetGraph(UEdGraph* InGraph);
    UBlueprint* GetBlueprint() const { return GraphBlueprint; }
};
```

**序列化字段**（在 .uasset 中）：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `MacroGraph` | ObjectReference | 图的直接引用（旧格式，VER_UE4_K2NODE_REFERENCEGUIDS 之前） |
| `GraphBlueprint` | ObjectReference | 宏所在蓝图 |
| `GraphGuid` | Guid (16 bytes) | 图的唯一标识，用于循环检测和跨版本兼容 |

### 2.2 EGraphType

**文件**：`Engine/Source/Runtime/Engine/Classes/EdGraph/EdGraphSchema.h:23-32`

```cpp
/** Distinguishes between different graph types.
 *  Graphs can have different properties; for example:
 *  functions have one entry point, ubergraphs can have multiples. */
UENUM()
enum EGraphType : int
{
    GT_Function,      // 函数图 — 单一入口（FunctionEntry），单一/无返回
    GT_Ubergraph,     // 超级图 — 多入口（多个 Event 节点）
    GT_Macro,         // 宏图 — 通过 Tunnel 定义入口/出口
    GT_Animation,     // 动画状态机图
    GT_StateMachine,  // 状态机图
    GT_MAX,
};
```

**获取图类型**：

```cpp
const UEdGraph* Graph = ...;
EGraphType Type = Graph->GetSchema()->GetGraphType(Graph);
```

### 2.3 UK2Node_MacroInstance

**文件**：
- 头文件：`Engine/Source/Editor/BlueprintGraph/Classes/K2Node_MacroInstance.h`
- 实现：`Engine/Source/Editor/BlueprintGraph/Private/K2Node_MacroInstance.cpp`

```cpp
UCLASS(MinimalAPI)
class UK2Node_MacroInstance : public UK2Node_Tunnel
{
    GENERATED_UCLASS_BODY()

private:
    // 宏图的引用（核心数据）
    UPROPERTY()
    TObjectPtr<class UEdGraph> MacroGraph_DEPRECATED;  // 旧格式

    UPROPERTY()
    FGraphReference MacroGraphReference;               // 新格式

public:
    // 通配符引脚类型信息
    UPROPERTY()
    struct FEdGraphPinType ResolvedWildcardType;

    // 引脚变化后是否需要重建节点
    bool bReconstructNode;

    // 访问器
    void SetMacroGraph(UEdGraph* Graph);
    UEdGraph* GetMacroGraph() const;
    UBlueprint* GetSourceBlueprint() const;

    // 通配符类型推断
    void InferWildcards(const TArray<UEdGraphNode*>& InNodes) const;

    // 获取关联的宏图元数据
    static FKismetUserDeclaredFunctionMetadata* GetAssociatedGraphMetadata(
        const UEdGraph* AssociatedMacroGraph);

    //~ Begin UEdGraphNode Interface
    virtual void AllocateDefaultPins() override;           // 从 Tunnel 引脚创建实例引脚
    virtual FText GetNodeTitle(ENodeTitleType::Type) const override;
    virtual FLinearColor GetNodeTitleColor() const override;
    virtual FSlateIcon GetIconAndTint(FLinearColor& OutColor) const override;
    virtual FText GetCompactNodeTitle() const override;
    virtual bool ShouldDrawCompact() const override;
    virtual bool CanPasteHere(const UEdGraph* TargetGraph) const override;
    //~ End UEdGraphNode Interface

    //~ Begin UK2Node Interface
    virtual void NotifyPinConnectionListChanged(UEdGraphPin* Pin) override;
    virtual void PostReconstructNode() override;
    virtual FBlueprintNodeSignature GetSignature() const override;
    virtual bool HasExternalDependencies(TArray<UStruct*>*) const override;
    //~ End UK2Node Interface
};
```

**关键属性详解**：

| 属性 | 类型 | 说明 |
|------|------|------|
| `MacroGraphReference` | FGraphReference | 宏图的完整引用信息 |
| `ResolvedWildcardType` | FEdGraphPinType | 通配符引脚解析后的实际类型 |
| `bReconstructNode` | bool | 标记节点是否需要重建（引脚变化后） |
| `CachedTooltip` | FNodeTextCache | 缓存的提示文本 |

### 2.4 UK2Node_Tunnel

**文件**：`Engine/Source/Editor/BlueprintGraph/Classes/K2Node_Tunnel.h`

```cpp
UCLASS(MinimalAPI)
class UK2Node_Tunnel : public UK2Node_EditablePinBase
{
    GENERATED_UCLASS_BODY()

    // 指向关系（展开后重连用）
    UPROPERTY()
    TObjectPtr<UK2Node_Tunnel> OutputSourceNode;  // 输出引脚的来源

    UPROPERTY()
    TObjectPtr<UK2Node_Tunnel> InputSinkNode;     // 输入引脚的去向

    // 能力标志
    UPROPERTY()
    uint32 bCanHaveInputs:1;    // 是否允许有输入引脚
    UPROPERTY()
    uint32 bCanHaveOutputs:1;   // 是否允许有输出引脚

    // 元数据（仅入口 Tunnel 使用）
    UPROPERTY()
    struct FKismetUserDeclaredFunctionMetadata MetaData;

    // 通配符引脚缓存
    TArray<UEdGraphPin*> WildcardPins;

protected:
    virtual void PostFixupAllWildcardPins(bool bInAllWildcardPinsUnlinked);
    static bool ShouldDoSmartWildcardInference();
    void CacheWildcardPins();
};
```

**Tunnel 类型判别**：

```cpp
// 入口 Tunnel — 定义宏的输入引脚
bCanHaveOutputs = true;   // 有输出 → 数据流向宏内部
bCanHaveInputs = false;   // 无输入

// 出口 Tunnel — 定义宏的输出引脚
bCanHaveInputs = true;    // 有输入 → 数据从宏内部流出
bCanHaveOutputs = false;  // 无输出
```

### 2.5 FKismetUserDeclaredFunctionMetadata

**文件**：`Engine/Source/Editor/BlueprintGraph/Classes/KismetUserDeclaredFunctionMetadata.h`（通过间接引用查找）

```cpp
USTRUCT()
struct FKismetUserDeclaredFunctionMetadata
{
    GENERATED_USTRUCT_BODY()

    UPROPERTY()
    FName FunctionName;           // 函数/宏名称

    UPROPERTY()
    FText ToolTip;                // 提示文本

    UPROPERTY()
    FText Keywords;               // 搜索关键词

    UPROPERTY()
    FText Category;               // 菜单分类

    UPROPERTY()
    FText CompactNodeTitle;       // 紧凑显示名称

    UPROPERTY()
    FLinearColor InstanceTitleColor;  // 节点标题颜色
};
```

**获取方式**：

```cpp
// 从宏图关联的入口 Tunnel 获取元数据
FKismetUserDeclaredFunctionMetadata* UK2Node_MacroInstance::GetAssociatedGraphMetadata(
    const UEdGraph* AssociatedMacroGraph)
{
    if (AssociatedMacroGraph)
    {
        TArray<UK2Node_Tunnel*> TunnelNodes;
        AssociatedMacroGraph->GetNodesOfClass(TunnelNodes);
        for (UK2Node_Tunnel* Node : TunnelNodes)
        {
            if (Node->IsEditable() && Node->bCanHaveOutputs)
            {
                return &(Node->MetaData);  // 入口 Tunnel 的 MetaData
            }
        }
    }
    return nullptr;
}
```

---

## 3. 序列化格式

### 3.1 .uasset 中的宏实例属性

在 `.uasset` 文件中，`K2Node_MacroInstance` 节点的序列化属性包括：

```
K2Node_MacroInstance
├── NodeGuid               : Guid          (16 bytes)
├── NodePosX               : Int32
├── NodePosY               : Int32
├── bCommentBubbleVisible  : BoolProperty
├── MacroGraphReference    : StructProperty (FGraphReference)
│   ├── GraphBlueprint     : ObjectReference
│   ├── GraphName          : NameProperty
│   └── GraphGuid          : Guid (16 bytes)
├── ResolvedWildcardType   : StructProperty (FEdGraphPinType)
│   ├── PinCategory        : NameProperty
│   ├── PinSubCategory     : NameProperty
│   └── PinSubCategoryObject : ObjectReference
├── Pins                   : ArrayProperty (UEdGraphPin[])
│   ├── PinName            : NameProperty
│   ├── PinType            : StructProperty
│   ├── DefaultValue       : StrProperty
│   ├── LinkedTo           : ArrayProperty (PackageIndex[])
│   └── SubPins            : ArrayProperty (PackageIndex[])
└── MetaData               : StructProperty (FKismetUserDeclaredFunctionMetadata)
    ├── FunctionName       : NameProperty
    ├── ToolTip            : TextProperty
    └── ...
```

### 3.2 MacroGraphReference 结构

**序列化格式**（在 .uasset 中的二进制表示）：

```
FGraphReference:
  [4 bytes]  PackageIndex → 指向 UBlueprint 对象
  [16 bytes] GraphGuid (UUID)
  [Name]     GraphName (FName 索引)
```

**PackageIndex 解析**：
- 正值 → 指向本地 ExportTable 中的导出
- 负值 → 指向 ImportTable 中的导入（通常是外部蓝图引用）
- 零值 → 空引用

**解析器注意事项**：
```python
def read_macro_graph_reference(archive, reader):
    # 1. 读取蓝图引用
    blueprint_idx = archive.read_int32()  # PackageIndex
    blueprint = reader.resolve_package_index(blueprint_idx)

    # 2. 读取 GraphGuid
    graph_guid = archive.read_guid()  # 16 bytes

    # 3. 读取 GraphName
    graph_name_idx = archive.read_int32()
    graph_name = reader.name_table[graph_name_idx]

    return {
        "blueprint_index": blueprint_idx,
        "blueprint": blueprint,
        "graph_guid": str(graph_guid),
        "graph_name": graph_name,
    }
```

### 3.3 GraphGuid 生成规则

`GraphGuid` 由 UE 编辑器在创建图时生成：

```cpp
// UEdGraph::PostInitProperties()
void UEdGraph::PostInitProperties()
{
    Super::PostInitProperties();
    if (!GraphGuid.IsValid())
    {
        GraphGuid = FGuid::NewGuid();  // 随机生成 UUID v4
    }
}
```

**重要**：GraphGuid 是**图级别的唯一标识**，不随图重命名而改变。循环检测依赖此 GUID。

---

## 4. 核心类关系

### 4.1 继承树

```
UObject
  └─ UEdGraphNode
       └─ UK2Node
            └─ UK2Node_EditablePinBase
                 ├─ UK2Node_Tunnel
                 │    ├─ UK2Node_Composite        (折叠图)
                 │    └─ UK2Node_MacroInstance    (宏实例)
                 │
                 ├─ UK2Node_FunctionEntry          (函数入口)
                 ├─ UK2Node_FunctionResult         (函数返回)
                 ├─ UK2Node_VariableGet            (变量读取)
                 ├─ UK2Node_VariableSet            (变量设置)
                 ├─ UK2Node_CallFunction           (函数调用)
                 ├─ UK2Node_Event                  (事件)
                 ├─ UK2Node_CustomEvent            (自定义事件)
                 ├─ UK2Node_IfThenElse             (分支)
                 ├─ UK2Node_Switch*                (Switch 系列)
                 ├─ UK2Node_Knot                   (重路由)
                 └─ ... (40+ 其他 K2Node 子类)
```

### 4.2 运行时关系图

```
┌─ UBlueprint ───────────────────────────┐
│                                        │
│  GeneratedClass  : UBlueprintGeneratedClass │
│  FunctionGraphs  : UEdGraph[]          │
│    ├─ GT_Function (函数图)              │
│    ├─ GT_Ubergraph (事件图)             │
│    └─ GT_Macro (宏图)                   │
│         │                              │
│         └─ Nodes: UEdGraphNode[]       │
│              ├─ UK2Node_Tunnel (入口)   │
│              ├─ UK2Node_Tunnel (出口)   │
│              └─ ... 内部节点            │
│                                        │
│  UberGraph       : UEdGraph            │
│    └─ Nodes: UEdGraphNode[]            │
│         ├─ UK2Node_Event               │
│         ├─ UK2Node_MacroInstance ────┐ │
│         └─ UK2Node_CallFunction      │ │
│                                      │ │
│  MacroGraphs     : UEdGraph[] ────────┘ │
│    (如果蓝图包含宏库)                   │
└────────────────────────────────────────┘

引用关系:
  MacroInstance.MacroGraphReference.GraphBlueprint → 包含宏图的 UBlueprint
  MacroInstance.MacroGraphReference.GraphGuid → 宏图的唯一标识
```

### 4.3 序列化关系图

```
.uasset 文件结构:

  [Name Table]
    [0] "MyMacro"              ← 宏图名称索引
    [1] "BeginPlay"
    [2] "exec"
    ...

  [Import Table]
    [-1] → "/Game/MacroLib.MyMacroLib" ← 外部宏库蓝图引用

  [Export Table]
    [1] → UEdGraph "UberGraph"
    [2] → UEdGraph "MyFunction"
    ...

  [Export Data - Export 1 (UberGraph)]
    Nodes:
      [K2Node_Event]
        NodeGuid: {A1B2...}
        Pins: [exec → K2Node_MacroInstance]

      [K2Node_MacroInstance]
        NodeGuid: {C3D4...}
        MacroGraphReference:
          GraphBlueprint: Import[-1]  ← 指向外部蓝图
          GraphGuid: {E5F6...}
          GraphName: "MyMacro"        ← Name[0]
        Pins:
          exec (Input)  ← linked_to → Event.exec
          Completed (Output) ← linked_to → K2Node_CallFunction.Then

      [K2Node_CallFunction]
        ...
```

---

## 5. 编译期展开

### 5.1 展开流程

**核心方法**：`FKismetCompilerContext::ExpandTunnelsAndMacros()` (`KismetCompiler.cpp:4234-4415`)

```
┌─────────────────────────────────────────────────────────────┐
│  ExpandTunnelsAndMacros(UEdGraph* SourceGraph)              │
│                                                             │
│  1. 循环检测                                                │
│     FindAndReportMacroCycles(SourceGraph, MessageLog)       │
│     → 如有循环，记录错误并返回                              │
│                                                             │
│  2. 遍历图中每个节点                                         │
│     for (Node : SourceGraph->Nodes)                         │
│                                                             │
│     2a. 如果是 UK2Node_MacroInstance:                       │
│         ┌───────────────────────────────────────────┐       │
│         │ a. 获取宏图                                │       │
│         │    MacroGraph = MacroInstance->GetMacroGraph()   │
│         │    if (null) { Error; continue; }          │       │
│         │                                           │       │
│         │ b. 克隆宏图                                │       │
│         │    ClonedGraph = FEdGraphUtilities::CloneGraph( │
│         │        MacroGraph, nullptr, &MessageLog, true)  │       │
│         │                                           │       │
│         │ c. 记录节点来源                            │       │
│         │    for (Node : ClonedGraph->Nodes)         │       │
│         │        MacroGeneratedNodes.Add(Node, CurrentNode)│
│         │                                           │       │
│         │ d. 处理特殊引脚                            │       │
│         │    - 未连接数组引脚 → MakeArray             │       │
│         │    - 未连接枚举引脚 → EnumLiteral           │       │
│         │    - 拆分结构体引脚 → ExpandSplitPin        │       │
│         │                                           │       │
│         │ e. 合并到原图                              │       │
│         │    ClonedGraph->MoveNodesToAnotherGraph(SourceGraph)│
│         │    MergeChildrenGraphsIn(SourceGraph, ClonedGraph)  │
│         │                                           │       │
│         │ f. 类型推断                                │       │
│         │    MacroInstance->InferWildcards(MacroNodes)      │
│         │                                           │       │
│         │ g. Tunnel 重连                             │       │
│         │    Input Tunnel → MacroInstance             │       │
│         │    Output Tunnel → MacroInstance            │       │
│         └───────────────────────────────────────────┘       │
│                                                             │
│     2b. 如果是 UK2Node_Tunnel:                              │
│         处理普通 Tunnel 展开                                │
│                                                             │
│  3. 后续处理                                                │
│     PruneInner()  ← 清理孤立节点                            │
│     Expand Knot Nodes                                       │
│     Expand All K2Node                                       │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 循环检测

**算法**：DFS 递归遍历，使用 GraphGuid 去重

```cpp
bool FindMacroCycle(const UK2Node_MacroInstance* RootNode,
                    TSet<FGuid>& VisitedMacroGraphs,
                    TArray<const UK2Node_MacroInstance*>& CurrentPath)
{
    check(RootNode);
    if (UEdGraph* MacroGraph = RootNode->GetMacroGraph())
    {
        VisitedMacroGraphs.Add(MacroGraph->GraphGuid);
        CurrentPath.Push(RootNode);

        for (const UEdGraphNode* ChildNode : MacroGraph->Nodes)
        {
            if (const UK2Node_MacroInstance* MacroInstanceNode =
                Cast<const UK2Node_MacroInstance>(ChildNode))
            {
                UEdGraph* InnerMacroGraph = MacroInstanceNode->GetMacroGraph();
                if (InnerMacroGraph && VisitedMacroGraphs.Contains(InnerMacroGraph->GraphGuid))
                {
                    return true;  // 循环！
                }
                else if (InnerMacroGraph)
                {
                    if (FindMacroCycle(MacroInstanceNode, VisitedMacroGraphs, CurrentPath))
                        return true;
                }
            }
        }
        CurrentPath.Pop();
    }
    return false;
}
```

**错误报告格式**：

```
Macro cycle detected in @@! Cycle path:
    @@
    @@
    @@
```

其中 `@@` 会被替换为节点引用，在 IDE 中点击可跳转到对应节点。

### 5.3 引脚映射

**规则**：MacroInstance 的引脚名 = Tunnel 的引脚名，方向取反

```
宏图内部:
  [Entry Tunnel]
    ├── exec (Output) ──→ 宏内部执行流
    ├── Target (Output) ──→ 宏内部数据流
    └── Damage (Output) ──→ 宏内部数据流

  [Exit Tunnel]
    ├── Then (Input) ←─ 来自宏内部执行流
    └── Result (Input) ←─ 来自宏内部数据流

MacroInstance 节点上:
    ├── exec (Input)  ← 对应 Entry Tunnel.exec (Output→Input 取反)
    ├── Target (Input) ← 对应 Entry Tunnel.Target (Output→Input 取反)
    ├── Damage (Input) ← 对应 Entry Tunnel.Damage (Output→Input 取反)
    ├── Then (Output)  ← 对应 Exit Tunnel.Then (Input→Output 取反)
    └── Result (Output) ← 对应 Exit Tunnel.Result (Input→Output 取反)
```

**解析器实现伪代码**：

```python
def build_pin_mapping(macro_graph):
    """构建 Tunnel 引脚到 Instance 引脚的映射"""
    mapping = {}
    for node in macro_graph.nodes:
        if node.node_type == "K2Node_Tunnel":
            # 只处理精确的 Tunnel，排除子类
            if node.exact_class == "UK2Node_Tunnel":
                for pin in node.pins:
                    if pin.parent_pin is None:  # 顶层引脚
                        # 方向取反
                        instance_dir = opposite(pin.direction)
                        mapping[pin.pin_name] = {
                            "instance_direction": instance_dir,
                            "pin_type": pin.pin_type,
                            "default_value": pin.default_value,
                        }
    return mapping


def opposite(direction):
    if direction == "EGPD_Output":
        return "EGPD_Input"
    elif direction == "EGPD_Input":
        return "EGPD_Output"
    return direction
```

### 5.4 Tunnel 重连

展开后，Tunnel 节点需要与 MacroInstance 建立指向关系：

```cpp
// KismetCompiler.cpp:4392-4411

// 入口 Tunnel（有输出引脚 → 定义宏输入）
if (DuplicatedTunnelNode->bCanHaveInputs)
{
    check(!DuplicatedTunnelNode->bCanHaveOutputs);
    check(!DuplicatedTunnelNode->InputSinkNode);
    DuplicatedTunnelNode->InputSinkNode = MacroInstanceNode;
    MacroInstanceNode->OutputSourceNode = DuplicatedTunnelNode;
}

// 出口 Tunnel（有输入引脚 → 定义宏输出）
else if (DuplicatedTunnelNode->bCanHaveOutputs)
{
    check(!DuplicatedTunnelNode->OutputSourceNode);
    DuplicatedTunnelNode->OutputSourceNode = MacroInstanceNode;
    MacroInstanceNode->InputSinkNode = DuplicatedTunnelNode;
}
```

**重连后的数据结构**：

```
展开后的图:

  [调用方前置节点] .exec ──→ [Entry Tunnel] .exec
                                    │
                                    │ InputSinkNode
                                    ▼
                            [MacroInstance 节点]
                                    │
                                    │ OutputSourceNode
                                    │
  [后续节点] .Then ←─ [Exit Tunnel] .Then
                            │
                            │ 内部执行流:
                            │   [节点A] → [节点B] → [节点C]
                            │
  [Entry Tunnel] 和 [Exit Tunnel] 之间的所有节点
  都是从克隆图移入的宏内部节点
```

### 5.5 中间节点插入

UE 编译器在展开时会自动插入一些中间节点：

#### 未连接数组输入 → MakeArray

```cpp
// KismetCompiler.cpp:4312-4322
if (Pin->PinType.IsArray()
    && Pin->Direction == EGPD_Input
    && Pin->LinkedTo.Num() == 0)
{
    UK2Node_MakeArray* MakeArrayNode = SpawnIntermediateNode<UK2Node_MakeArray>(...);
    MakeArrayNode->NumInputs = 0;  // 生成空数组
    MakeArrayNode->AllocateDefaultPins();
    MakeArrayOut->MakeLinkTo(Pin);
}
```

#### 未连接枚举输入 → EnumLiteral

```cpp
// KismetCompiler.cpp:4324-4339
if (Pin->LinkedTo.Num() == 0
    && Pin->Direction == EGPD_Input
    && Pin->DefaultValue != FString()
    && Pin->PinType.PinCategory == PC_Byte
    && Pin->PinType.PinSubCategoryObject->IsA<UEnum>())
{
    UK2Node_EnumLiteral* EnumLiteralNode = SpawnIntermediateNode<UK2Node_EnumLiteral>(...);
    EnumLiteralNode->Enum = CastChecked<UEnum>(Pin->PinType.PinSubCategoryObject.Get());
    EnumLiteralNode->AllocateDefaultPins();
    EnumLiteralNode->FindPinChecked(PN_ReturnValue)->MakeLinkTo(Pin);
    InPin->DefaultValue = Pin->DefaultValue;
}
```

#### 拆分结构体引脚 → ExpandSplitPin

```cpp
// KismetCompiler.cpp:4342-4344
if (Pin->SubPins.Num() > 0)
{
    MacroInstanceNode->ExpandSplitPin(this, SourceGraph, Pin);
}
```

**解析器注意事项**：
- 展开后的图中可能出现 `K2Node_MakeArray`、`K2Node_EnumLiteral` 等中间节点
- 这些节点是编译器插入的，不是用户原始放置的
- 解析器应能识别这些中间节点并标记其来源

---

## 6. Wildcard 类型推断

### 6.1 简单模式

**条件**：`bUseSimpleWildcardInference = true`（配置文件 `[Blueprints] bUseSimpleWildcardInference`）

```cpp
// K2Node_MacroInstance.cpp:323-335
// 第一个连接的非 Wildcard 类型覆盖所有 Wildcard
for (Pin : Pins) {
    if (IsWildcardPin(Pin)) {
        Pin->PinType.PinCategory = LinkedPinType.PinCategory;
        Pin->PinType.PinSubCategory = LinkedPinType.PinSubCategory;
        Pin->PinType.PinSubCategoryObject = LinkedPinType.PinSubCategoryObject;
    }
}
ResolvedWildcardType = LinkedPinType;
```

**行为**：
- 第一个连接的具体类型**统一**应用到所有 Wildcard 引脚
- 简单快速，但不支持混合类型

### 6.2 智能模式

**条件**：`bUseSimpleWildcardInference = false`（默认）

`SmartInferWildcardsImpl()` (`K2Node_MacroInstance.cpp:730-913`)：

```
步骤 1: 收集 Tunnel Wildcard
    遍历 MacroGraph 中所有 UK2Node_Tunnel 的 Wildcard 引脚

步骤 2: 播种已知类型
    如果 MacroInstance 的引脚已连接具体类型:
        → 写入对应 Tunnel Wildcard
        → 将连接的节点加入 DirtyNodePins

步骤 3: 迭代传播
    while (DirtyNodePins not empty):
        for each DirtyPin in DirtyNodePins:
            调用 NotifyPinConnectionListChanged(DirtyPin)
            → 节点尝试传播类型到其所有 Wildcard 引脚

        for each WildcardNode:
            if Wildcard 计数变化 (说明有传播发生):
                将其连接的节点加入 DirtyNodePins

步骤 4: 验证
    比较迭代前后的 ConnectionCounts
    → 确保不破坏图拓扑

步骤 5: 回写
    将 Tunnel Wildcard 的最终类型回写到 MacroInstance 引脚
```

### 6.3 推断传播算法

```cpp
// K2Node_MacroInstance.cpp:713-726
static void InferLinkedPinsImpl(UEdGraphPin* Pin, const FEdGraphPinType& Type,
    TArray<TPair<UEdGraphNode*, UEdGraphPin*>>& OutDirtyNodePins,
    TSet<UEdGraphPin*>& ProcessedPins)
{
    // 推断当前引脚类型
    FWildcardNodeUtils::InferType(Pin, Type);
    OutDirtyNodePins.AddUnique({Pin->GetOwningNode(), Pin});
    ProcessedPins.Add(Pin);

    // 递归推断所有连接的 Wildcard 引脚
    for (UEdGraphPin* LinkedPin : Pin->LinkedTo)
    {
        if (!ProcessedPins.Contains(LinkedPin) && FWildcardNodeUtils::IsWildcardPin(LinkedPin))
        {
            InferLinkedPinsImpl(LinkedPin, Type, OutDirtyNodePins, ProcessedPins);
        }
    }
}
```

**传播规则**：
1. 类型从**已知**引脚向**未知**（Wildcard）引脚传播
2. 传播方向跟随引脚连接（`LinkedTo`）
3. 使用 `ProcessedPins` 集合防止循环传播
4. 使用 `DirtyNodePins` 队列记录需要重建的节点
5. 传播终止条件：所有引脚类型稳定（无新推断发生）

---

## 7. 标准宏库

### 7.1 内置宏列表

UE 引擎提供以下内置宏，存储在名为 `StandardMacros` 的蓝图中：

| 宏名 | 图标 | 入口引脚 | 出口引脚 | 说明 |
|------|------|----------|----------|------|
| `ForLoop` | Loop | Entry (exec), LastIndex (int) | Loop Body (exec), Completed (exec), Loop Counter (int) | 标准 For 循环 |
| `ForLoopWithBreak` | Loop | 同上 + Break (exec) | 同上 | 可中断 For 循环 |
| `WhileLoop` | Loop | Entry (exec), Condition (bool) | Loop Body (exec), Completed (exec) | While 循环 |
| `Gate` | Gate | Enter (exec), Open (exec), Close (exec), Toggle (exec) | Exit (exec) | 门控节点 |
| `Do N` | DoN | Enter (exec), N (int) | Exit (exec), Completed (exec) | 执行 N 次 |
| `DoOnce` | DoOnce | Enter (exec), Reset (exec) | Exit (exec) | 仅执行一次 |
| `IsValid` | IsValid | Input (Object) | Valid (exec), Invalid (exec) | 有效性检查 |
| `FlipFlop` | FlipFlop | A (exec) | A (exec), B (exec), IsA (bool) | 交替切换 |
| `ForEachLoop` | ForEach | Entry (exec), Array (T[]) | Loop Body (exec), Completed (exec), Array Element (T), Array Index (int) | 数组遍历 |
| `ForEachLoopWithBreak` | ForEach | 同上 + Break (exec) | 同上 | 可中断数组遍历 |

**识别代码**（`K2Node_MacroInstance.cpp:458-494`）：

```cpp
FSlateIcon UK2Node_MacroInstance::GetIconAndTint(FLinearColor& OutColor) const
{
    const char* IconName = "GraphEditor.Macro_16x";

    UEdGraph* MacroGraph = MacroGraphReference.GetGraph();
    if (MacroGraph != nullptr && MacroGraph->GetOuter()->GetName() == TEXT("StandardMacros"))
    {
        FName MacroName = FName(*MacroGraph->GetName());
        if (MacroName == TEXT("ForLoop") ||
            MacroName == TEXT("ForLoopWithBreak") ||
            MacroName == TEXT("WhileLoop"))
        {
            IconName = "GraphEditor.Macro.Loop_16x";
        }
        else if (MacroName == TEXT("Gate")) {
            IconName = "GraphEditor.Macro.Gate_16x";
        }
        // ... 其他宏 ...
    }
    return FSlateIcon(FAppStyle::GetAppStyleSetName(), IconName);
}
```

### 7.2 自定义宏库

用户可创建自定义宏库蓝图：

```
创建步骤（UE 编辑器）:
  1. 新建蓝图 → 类型选择 "宏库" (MacroLibrary)
  2. 添加新图 → 图类型选 "宏" (Macro)
  3. 在图中放置 Entry/Exit Tunnel 节点
  4. 在 Tunnel 之间放置逻辑节点
  5. 其他蓝图可引用此宏库中的宏
```

**跨蓝图引用限制**（`K2Node_MacroInstance.cpp:514-537`）：

```cpp
bool UK2Node_MacroInstance::CanPasteHere(const UEdGraph* TargetGraph) const
{
    UBlueprint* MacroBlueprint  = GetSourceBlueprint();
    UBlueprint* TargetBlueprint = FBlueprintEditorUtils::FindBlueprintForGraph(TargetGraph);

    if (MacroBlueprint && TargetBlueprint)
    {
        // 只允许:
        // 1. 本地宏（同一蓝图内）
        // 2. 来自宏库蓝图，且目标蓝图的父类是宏库父类的子类
        bCanPaste = (MacroBlueprint == TargetBlueprint) ||
                    (MacroBlueprint->BlueprintType == BPTYPE_MacroLibrary &&
                     TargetBlueprint->ParentClass->IsChildOf(MacroBlueprint->ParentClass));
    }

    // 不允许在自身图中使用
    bCanPaste &= (GetMacroGraph() != TargetGraph);

    // 函数图中不允许含 Latent 的宏
    bCanPaste &= (!bIsTargetFuncGraph || !FBlueprintEditorUtils::CheckIfGraphHasLatentFunctions(MacroGraph));

    return bCanPaste;
}
```

**约束规则**：
1. 宏库蓝图（`BPTYPE_MacroLibrary`）可被其他蓝图引用
2. 普通蓝图中的宏只能被同一蓝图使用
3. 含 Latent 动作的宏**不可**放入函数图
4. 宏**不可**在自身图中使用（防止无限嵌套）

---

## 8. 解析器实现指南

### 8.1 当前状态

| 模块 | 文件 | 状态 | 说明 |
|------|------|------|------|
| 节点读取 | `serializers/graph.py` `read_k2node_macro_instance()` | 🟡 部分 | 读取宏引用属性但不递归解析宏图 |
| 常量定义 | `constants.py` `CONTROL_FLOW_NODES` | 🔴 终止 | `K2Node_MacroInstance` 被标记为控制流终止节点 |
| 执行链追踪 | `graph/flow_builder.py` | 🔴 终止 | 遇到 MacroInstance 标记 `stopped_at` 后停止 |
| 链构建 | `graph/chain_builder.py` | 🔴 终止 | MacroInstance 后的节点不进入执行链 |
| 数据流 | `graph/pin_trace.py` | 🟢 可用 | 引脚连接追踪不受 MacroInstance 影响 |

### 8.2 完整展开方案

#### 设计目标

1. **保留原始信息** — 不修改已解析的图数据，展开为独立视图
2. **循环检测** — 防止嵌套宏导致的无限递归
3. **引脚映射** — 正确映射 Tunnel ↔ Instance 的引脚关系
4. **执行链穿透** — 执行流能从调用方穿越到宏内部
5. **嵌套宏支持** — 宏内部的 MacroInstance 同样展开

#### 展开时机

```
解析流程:

  parse_single(asset_path)
    └─ parse_uasset_with_linker(asset_path)
         └─ deserialize_exports()
              └─ deserialize_graph()
                   └─ deserialize_graph_nodes()
                        └─ create_node_from_archive()
                             └─ read_k2node_macro_instance()
                                  │
                                  ├─ 当前: 仅读取属性，返回节点字典
                                  └─ 目标: 标记需展开，延迟处理
                         │
                         └─ build_execution_flows(graph)
                              │
                              ├─ 当前: 遇到 MacroInstance → stopped_at
                              └─ 目标: 展开宏 → 穿透执行链
```

**建议采用延迟展开策略**：
1. 解析阶段只读取宏引用属性
2. 在执行链构建阶段按需展开
3. 避免不必要的递归解析

### 8.3 数据结构设计

```python
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MacroExpansionContext:
    """宏展开的上下文信息"""
    macro_name: str                    # 宏名称
    macro_guid: str                    # 宏图 GUID
    macro_graph_ref: dict              # MacroGraphReference 原始数据
    blueprint_ref: Optional[str]       # 蓝图引用路径


@dataclass
class MacroExpansion:
    """宏展开结果"""
    context: MacroExpansionContext
    expanded_nodes: list[dict]         # 展开后的节点列表
    pin_mapping: dict[str, dict]       # Tunnel Pin → Instance Pin 映射
    entry_tunnel: Optional[dict]       # 入口 Tunnel 节点
    exit_tunnels: list[dict]           # 出口 Tunnel 节点列表
    internal_flows: list[dict]         # 宏内部执行流
    nested_expansions: list["MacroExpansion"] = field(default_factory=list)


@dataclass
class MacroCycleError(Exception):
    """宏循环检测异常"""
    cycle_path: list[str]              # 循环路径（宏名称列表）

    def __init__(self, cycle_path: list[str]):
        self.cycle_path = cycle_path
        names = [ctx.macro_name for ctx in cycle_path]
        message = f"宏循环检测: {' → '.join(names)} → {names[0]}"
        super().__init__(message)
```

### 8.4 递归展开算法

```python
class MacroExpander:
    """宏展开器"""

    def __init__(self, asset_context):
        self.asset_context = asset_context
        self.visited_guids: set[str] = set()
        self.expansion_stack: list[MacroExpansionContext] = []

    def expand_macro_instance(self, instance_node: dict) -> MacroExpansion:
        """展开单个宏实例"""
        # 1. 获取宏引用信息
        macro_ref = instance_node.get("macro_graph_reference", {})
        graph_guid = macro_ref.get("graph_guid")
        graph_name = macro_ref.get("graph_name")

        # 2. 循环检测
        if graph_guid in self.visited_guids:
            raise MacroCycleError(self.expansion_stack.copy() + [
                MacroExpansionContext(
                    macro_name=graph_name,
                    macro_guid=graph_guid,
                    macro_graph_ref=macro_ref,
                    blueprint_ref=None,
                )
            ])

        # 3. 查找宏图
        macro_graph = self._find_macro_graph(macro_ref)
        if macro_graph is None:
            return self._create_unresolved_expansion(instance_node, macro_ref)

        # 4. 递归展开
        self.visited_guids.add(graph_guid)
        ctx = MacroExpansionContext(
            macro_name=graph_name,
            macro_guid=graph_guid,
            macro_graph_ref=macro_ref,
            blueprint_ref=None,
        )
        self.expansion_stack.append(ctx)

        try:
            expansion = self._expand_graph(macro_graph, ctx)
            return expansion
        finally:
            self.expansion_stack.pop()
            self.visited_guids.discard(graph_guid)

    def _find_macro_graph(self, macro_ref: dict) -> Optional[dict]:
        """在资产中查找宏图"""
        graph_guid = macro_ref.get("graph_guid")
        graph_name = macro_ref.get("graph_name")

        # 1. 在当前资产的所有 Graph 中查找
        for graph in self.asset_context.get("graphs", []):
            if graph.get("guid") == graph_guid:
                return graph
            if graph.get("name") == graph_name:
                return graph

        # 2. 在 resolved_parent_assets 中查找（跨蓝图引用）
        for parent_asset in self.asset_context.get("resolved_parent_assets", []):
            for graph in parent_asset.get("graphs", []):
                if graph.get("guid") == graph_guid:
                    return graph

        # 3. 在标准宏库中查找（StandardMacros）
        #    这需要引擎内置资源的支持
        return None

    def _expand_graph(self, macro_graph: dict, ctx: MacroExpansionContext) -> MacroExpansion:
        """展开宏图"""
        nodes = macro_graph.get("nodes", [])

        # 分离 Tunnel 节点和普通节点
        entry_tunnels = []
        exit_tunnels = []
        internal_nodes = []

        for node in nodes:
            if node.get("node_type") == "K2Node_Tunnel":
                if node.get("exact_class") == "UK2Node_Tunnel":
                    if node.get("b_can_have_outputs"):
                        exit_tunnels.append(node)
                    if node.get("b_can_have_inputs"):
                        entry_tunnels.append(node)
                    continue  # Tunnel 不进入内部节点列表
            internal_nodes.append(node)

        # 构建引脚映射
        pin_mapping = self._build_pin_mapping(entry_tunnels, exit_tunnels)

        # 递归展开内部嵌套宏
        nested_expansions = []
        for node in internal_nodes:
            if node.get("node_type") == "K2Node_MacroInstance":
                nested = self.expand_macro_instance(node)
                nested_expansions.append(nested)

        # 构建宏内部执行流
        internal_flows = self._build_internal_flows(entry_tunnels, internal_nodes, exit_tunnels)

        return MacroExpansion(
            context=ctx,
            expanded_nodes=internal_nodes,
            pin_mapping=pin_mapping,
            entry_tunnel=entry_tunnels[0] if entry_tunnels else None,
            exit_tunnels=exit_tunnels,
            internal_flows=internal_flows,
            nested_expansions=nested_expansions,
        )

    def _build_pin_mapping(self, entry_tunnels: list[dict], exit_tunnels: list[dict]) -> dict[str, dict]:
        """构建 Tunnel 引脚到 Instance 引脚的映射"""
        mapping = {}

        for tunnel in entry_tunnels + exit_tunnels:
            for pin in tunnel.get("pins", []):
                if pin.get("parent_pin") is None:  # 顶层引脚
                    direction = pin.get("direction", "")
                    instance_dir = "EGPD_Input" if direction == "EGPD_Output" else "EGPD_Output"
                    mapping[pin["pin_name"]] = {
                        "instance_direction": instance_dir,
                        "pin_type": pin.get("pin_type", {}),
                        "default_value": pin.get("default_value", ""),
                        "tunnel_type": "entry" if tunnel in entry_tunnels else "exit",
                    }

        return mapping

    def _build_internal_flows(self, entry_tunnels, internal_nodes, exit_tunnels) -> list[dict]:
        """构建宏内部执行流"""
        # 复用 flow_builder 的逻辑，从入口 Tunnel 开始追踪
        flows = []
        for tunnel in entry_tunnels:
            flow = self._trace_from_node(tunnel, internal_nodes, exit_tunnels)
            if flow:
                flows.append(flow)
        return flows

    def _trace_from_node(self, start_node, all_nodes, exit_tunnels):
        """从节点开始追踪执行流（复用 flow_builder 逻辑）"""
        # ... 与 flow_builder 中的 _trace_execution_from_event 类似 ...
        pass

    def _create_unresolved_expansion(self, instance_node, macro_ref):
        """创建未解析的展开结果（宏图未找到）"""
        return MacroExpansion(
            context=MacroExpansionContext(
                macro_name=macro_ref.get("graph_name", "Unknown"),
                macro_guid=macro_ref.get("graph_guid", ""),
                macro_graph_ref=macro_ref,
                blueprint_ref=None,
            ),
            expanded_nodes=[],
            pin_mapping={},
            entry_tunnel=None,
            exit_tunnels=[],
            internal_flows=[],
        )
```

### 8.5 执行链穿透

**目标**：将执行链从调用方穿透到宏内部

```python
def trace_through_macro(expander: MacroExpander, instance_node: dict, current_chain: list[dict]) -> list[dict]:
    """穿透宏实例继续追踪执行链"""

    # 1. 展开宏
    expansion = expander.expand_macro_instance(instance_node)

    if not expansion.expanded_nodes:
        # 宏图未找到，返回当前链 + 宏实例标记
        return current_chain + [{
            "node_guid": instance_node.get("guid"),
            "node_type": "K2Node_MacroInstance",
            "macro_name": expansion.context.macro_name,
            "unresolved": True,
        }]

    # 2. 从入口 Tunnel 开始追踪内部执行流
    internal_chains = []
    for entry_tunnel_node in [expansion.entry_tunnel] if expansion.entry_tunnel else []:
        chain = _trace_execution_from_tunnel(
            entry_tunnel_node,
            expansion.expanded_nodes,
            expansion.exit_tunnels,
            expansion,
        )
        internal_chains.append(chain)

    # 3. 合并调用方链和内部链
    result = []
    for internal_chain in internal_chains:
        merged = current_chain + internal_chain
        result.append(merged)

    return result


def _trace_execution_from_tunnel(entry_tunnel, internal_nodes, exit_tunnels, expansion):
    """从入口 Tunnel 开始追踪执行流"""
    chain = []
    visited = set()

    current = entry_tunnel
    while current is not None:
        guid = current.get("guid")
        if guid in visited:
            chain.append({
                "node_guid": guid,
                "node_type": current.get("node_type"),
                "cycle_detected": True,
            })
            break

        visited.add(guid)
        chain.append({
            "node_guid": guid,
            "node_type": current.get("node_type"),
        })

        # 如果是控制流节点，停止
        if current.get("node_type") in CONTROL_FLOW_NODES:
            chain[-1]["stopped_at"] = "control_flow_node"
            break

        # 如果是出口 Tunnel，停止
        if current in exit_tunnels:
            break

        # 如果是嵌套宏，递归展开
        if current.get("node_type") == "K2Node_MacroInstance":
            nested = expansion.nested_expansions
            # ... 处理嵌套宏 ...
            pass

        # 找到下一个执行节点
        current = _find_next_exec_node(current, internal_nodes)

    return chain
```

### 8.6 边界情况处理

#### 情况 1：宏图不存在

```python
# 可能原因:
# 1. 蓝图引用了外部宏库但宏库未包含在解析范围内
# 2. 宏图 GUID 与资产中的 GUID 不匹配
# 3. 资产损坏

# 处理方式:
# - 记录警告但不中断解析
# - 在展开结果中标记 unresolved=True
# - 执行链中保留 MacroInstance 节点
```

#### 情况 2：宏循环

```python
# 检测方式:
# - 使用 GraphGuid 集合追踪已访问的宏图
# - 展开栈记录当前展开路径

# 处理方式:
# - 抛出 MacroCycleError
# - 记录循环路径
# - 不展开循环中的宏
```

#### 情况 3：多入口/多出口 Tunnel

```python
# 一个宏图可以有:
# - 多个入口 Tunnel (如 ForLoop 的 Entry 和 Break)
# - 多个出口 Tunnel (如 ForLoop 的 LoopBody 和 Completed)

# 处理方式:
# - 执行链追踪时，根据调用方的 exec 引脚名称选择入口
# - 出口 Tunnel 可能有多个执行流出口
# - 在 internal_flows 中记录所有可能的路径
```

#### 情况 4：标准宏的特殊处理

```python
# StandardMacros 中的内置宏 (ForLoop, WhileLoop 等)
# 不在用户资产中，需要单独处理

# 方式 1: 内置定义
#   - 在解析器中硬编码标准宏的引脚定义
#   - 不展开内部节点，只记录宏名称和引脚映射

# 方式 2: 引擎资源加载
#   - 从引擎的 StandardMacros 蓝图中加载宏定义
#   - 需要访问引擎资源目录

# 推荐方式 1，因为标准宏数量有限且定义稳定
STANDARD_MACROS = {
    "ForLoop": {
        "inputs": ["Entry", "LastIndex", "FirstIndex", "Increment"],
        "outputs": ["Loop Body", "Completed", "Loop Counter"],
        "is_loop": True,
    },
    "WhileLoop": {
        "inputs": ["Entry", "Condition"],
        "outputs": ["Loop Body", "Completed"],
        "is_loop": True,
    },
    # ... 其他标准宏 ...
}
```

#### 情况 5：Wildcard 引脚类型

```python
# Wildcard 引脚在序列化后可能有:
# 1. ResolvedWildcardType 已解析为具体类型
# 2. 仍然是 PC_Wildcard 未解析

# 处理方式:
# - 使用 ResolvedWildcardType 作为实际类型
# - 如果仍为 Wildcard，标记为 "unresolved_wildcard"
# - 在 pin_mapping 中记录推断状态
```

---

## 9. 关键源码索引

### 9.1 核心文件

| 文件路径 | 说明 |
|----------|------|
| `Engine/Source/Editor/BlueprintGraph/Classes/K2Node_MacroInstance.h` | 宏实例类定义 |
| `Engine/Source/Editor/BlueprintGraph/Private/K2Node_MacroInstance.cpp` | 宏实例实现（引脚分配、通配符推断等） |
| `Engine/Source/Editor/BlueprintGraph/Classes/K2Node_Tunnel.h` | Tunnel 节点类定义 |
| `Engine/Source/Editor/BlueprintGraph/Private/K2Node_Tunnel.cpp` | Tunnel 节点实现 |
| `Engine/Source/Editor/KismetCompiler/Private/KismetCompiler.cpp` | 编译器上下文（宏展开主逻辑） |
| `Engine/Source/Runtime/Engine/Classes/EdGraph/EdGraph.h` | FGraphReference 结构体 |
| `Engine/Source/Runtime/Engine/Classes/EdGraph/EdGraphSchema.h` | EGraphType 枚举 |
| `Engine/Source/Editor/BlueprintGraph/Classes/KismetUserDeclaredFunctionMetadata.h` | 宏元数据结构 |

### 9.2 关键函数

| 文件 | 行号 | 函数 | 说明 |
|------|------|------|------|
| `K2Node_MacroInstance.cpp` | 40-44 | 构造函数 | 初始化 bReconstructNode |
| `K2Node_MacroInstance.cpp` | 46-54 | `Serialize()` | 旧格式兼容（VER_UE4_K2NODE_REFERENCEGUIDS） |
| `K2Node_MacroInstance.cpp` | 109-152 | `AllocateDefaultPins()` | 从 Tunnel 引脚创建实例引脚 |
| `K2Node_MacroInstance.cpp` | 197-211 | `GetNodeTitle()` | 获取节点显示名称 |
| `K2Node_MacroInstance.cpp` | 241-263 | `GetAssociatedGraphMetadata()` | 获取宏图元数据 |
| `K2Node_MacroInstance.cpp` | 458-497 | `GetIconAndTint()` | 标准宏图标识别 |
| `K2Node_MacroInstance.cpp` | 514-537 | `CanPasteHere()` | 粘贴合法性检查（跨蓝图限制） |
| `K2Node_MacroInstance.cpp` | 661-681 | `InferWildcards()` | 简单类型推断 |
| `K2Node_MacroInstance.cpp` | 730-913 | `SmartInferWildcardsImpl()` | 智能类型推断 |
| `KismetCompiler.cpp` | 470-496 | `FindMacroCycle()` | 宏循环检测 |
| `KismetCompiler.cpp` | 498-529 | `FindAndReportMacroCycles()` | 入口级循环检测 |
| `KismetCompiler.cpp` | 4234-4415 | `ExpandTunnelsAndMacros()` | 宏展开主逻辑 |

### 9.3 相关类型

| 类型 | 文件 | 说明 |
|------|------|------|
| `UK2Node_Composite` | `BlueprintGraph/Classes/K2Node_Composite.h` | 折叠图节点 |
| `UK2Node_Knot` | `BlueprintGraph/Classes/K2Node_Knot.h` | 重路由节点 |
| `UK2Node_MakeArray` | `BlueprintGraph/Classes/K2Node_MakeArray.h` | 数组构建节点（编译器插入） |
| `UK2Node_EnumLiteral` | `BlueprintGraph/Classes/K2Node_EnumLiteral.h` | 枚举字面量节点（编译器插入） |
| `UK2Node_TemporaryVariable` | `BlueprintGraph/Classes/K2Node_TemporaryVariable.h` | 临时变量节点 |
| `FEdGraphPinType` | `Engine/Classes/EdGraph/EdGraphPin.h` | 引脚类型结构体 |
| `FCompilerResultsLog` | `KismetCompiler/Public/KismetCompiler.h` | 编译日志 |
| `FEdGraphUtilities` | `Editor/UnrealEd/Public/EdGraphUtilities.h` | 图工具集（CloneGraph 等） |
