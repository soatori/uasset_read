# 功能全景

**领域：** Unreal Engine .uasset 文件解析（面向 AI agent 消费）
**研究日期：** 2026-04-27

## 基础功能

用户期望的功能。缺失 = 产品不完整。

| 功能 | 期望原因 | 复杂度 | 备注 |
|------|----------|--------|------|
| **解析 .uasset 文件头** | 识别文件结构、版本和偏移的必要条件 | 低 | FPackageFileSummary 含魔术标签、版本信息、名称/导入/导出表偏移 |
| **提取名称表** | 所有对象/属性名称引用此表；解析任何数据的基础 | 低 | 文件头中 NameCount + NameOffset；名称条目为 FName 带数字索引 |
| **提取导出表** | 列出包内定义的所有对象（蓝图、图、节点） | 低 | FObjectExport：ObjectName、ClassIndex、OuterIndex、SerialOffset、SerialSize |
| **提取导入表** | 列出外部依赖（此资产引用的其他包） | 低 | FObjectImport：ObjectName、ClassName、ClassPackage —— 理解资产依赖的关键 |
| **识别资产类/类型** | 用户需知道读取的是何种资产 | 中 | 导出表中 ClassIndex 指向资产类（Blueprint、Material、Texture 等） |
| **提取基本属性值** | 资产含数据 —— 整数、浮点、字符串、布尔、数组必须可读 | 中 | FPropertyTag + FEdGraphPinType 定义值类型；DefaultValue 存为字符串 |
| **JSON 输出格式** | 程序化消费的标准结构化输出 | 低 | PROJECT.md 核心需求 |
| **人类可读文本输出** | 用户/AI 无需深入 UE 知识即可理解内容 | 中 | PROJECT.md 核心需求；语义描述，非原始数据 |
| **单文件解析** | 必须能读取单个 .uasset 而无需完整项目上下文 | 低 | PROJECT.md 约束；不依赖 UE 编辑器或 pak 提取 |
| **版本识别** | UE 版本不同；必须知道文件保存的版本 | 低 | 文件头中 FileVersionUE + FileVersionLicenseeUE；决定序列化格式 |

## 差异化功能

让产品脱颖更出的功能。非期望但有价值。

| 功能 | 价值主张 | 复杂度 | 备注 |
|------|----------|--------|------|
| **蓝图图提取** | AI agent 需理解蓝图逻辑 —— 节点、连接、流程 | 高 | UEdGraph 含 Nodes 数组；各 UK2Node 有 Pins 带 LinkedTo 连接。理解蓝图行为的关键。 |
| **变量定义提取** | 知道蓝图存储什么数据 —— 名称、类型、默认值、元数据 | 中 | 蓝图中 FBPVariableDescription：VarName、VarType（FEdGraphPinType）、DefaultValue、MetaDataArray、PropertyFlags |
| **函数定义提取** | 知道蓝图暴露什么函数 —— 名称、参数、返回类型 | 高 | 蓝图中 FunctionGraphs 数组；UEdGraph 含表示函数签名的节点 |
| **引用依赖图** | AI 需知道此资产使用/依赖哪些其他资产 | 中 | ImportMap + SoftObjectPathsCount；结合引用外部资产的属性值 |
| **属性类型解释** | AI 需语义理解类型（非仅 "IntProperty" 而是 "整数"） | 中 | FEdGraphPinType：PinCategory、PinSubCategory、ContainerType（Array/Set/Map）、bIsReference、bIsConst |
| **节点类型识别** | AI 需知道各蓝图节点做什么 | 高 | UK2Node 类层次 —— K2Node_CallFunction、K2Node_VariableGet、K2Node_Event 等。各具特定数据字段。 |
| **引脚连接映射** | AI 需追踪蓝图中数据流 | 中 | UEdGraphPin.LinkedTo 数组连接输出引脚到输入引脚；追踪执行/数据流 |
| **层级结构输出** | Package → Exports → Graphs → Nodes → Pins —— 清晰嵌套 JSON | 中 | 匹配 UE 对象层次；AI 可逻辑导航 |
| **错误恢复与部分解析** | 遇未知属性类型时继续解析并标记 | 高 | UE 有众多属性类型；部分版本特定或自定义。单未知类型不应导致整个解析失败。 |
| **语义节点描述** | 非原始节点类，输出人类可读描述（"调用函数 X"） | 高 | 需理解节点语义；如 K2Node_CallFunction 带 FunctionReference → "调用 [FunctionName]" |

## 反功能

明确不构建的功能。

| 反功能 | 避免原因 | 替代做法 |
|--------|----------|----------|
| **二进制资产导出** | 超出 PROJECT.md 范围；纹理/模型是复杂二进制格式需专门处理 | 专注结构化数据提取；让专用工具处理二进制导出 |
| **资产修改/写入** | 超出 PROJECT.md 范围；修改 .uasset 需理解序列化、cooking、依赖 —— 极其复杂 | 仅支持只读解析 |
| **蓝图字节码反编译** | 编译蓝图使用 Kismet VM 字节码；反编译极复杂，编辑器保存资产无需 | 专注提取编辑器时图数据（UEdGraph/UK2Node）从未 cooked 资产 |
| **Pak 文件提取** | 不同领域；.pak 是归档格式，非资产格式 | 用户提供提取的 .uasset；pak 提取是独立问题（u4pak 处理） |
| **实时解析/监控** | 超出 PROJECT.md 范围；增加复杂性而无核心价值 | 单文件解析带清晰输出 |
| **UE 编辑器集成** | 超出 PROJECT.md 范围；需运行 UE，非独立 Python | 独立 Python 工具，无 UE 依赖 |
| **资产预览/可视化** | 复杂 UI 工作；AI agent 无需视觉预览 | 仅结构化文本/JSON 输出 |
| **资产转换/转码** | 不同领域；转换 UE 资产到其他格式需理解目标格式 | 读取并输出结构，而非转换 |
| **Cooked 资产解析** | Cooked 资产已剥离编辑器数据；使用不同序列化格式 | 专注于未 cooked/编辑器保存的资产，含完整图数据 |
| **自定义属性类型处理器** | 游戏特定自定义属性类型需游戏特定知识 | 通用处理；标记未知类型而非尝试解释 |

## 功能依赖

```
解析文件头
  |-- 提取名称表（需文件头偏移）
  |-- 提取导出表（需文件头偏移）
  |-- 提取导入表（需文件头偏移）

提取导出表
  |-- 识别资产类（需通过导入/导出解析 ClassIndex）
  |-- 解析导出数据（需 SerialOffset + SerialSize）

解析导出数据
  |-- 提取属性（需属性类型知识）
  |-- 提取蓝图图（若资产是蓝图）
      |-- 提取节点（需 UEdGraph.Nodes）
          |-- 提取节点引脚（需 UK2Node.Pins）
              |-- 映射引脚连接（需 LinkedTo）

蓝图特定提取：
  |-- 变量（FBPVariableDescription）
  |-- 函数（FunctionGraphs）
  |-- 事件图（UbergraphPages）
  |-- 接口（ImplementedInterfaces）
```

## MVP 推荐

优先：
1. **解析 .uasset 文件头** —— 所有解析的入口
2. **提取名称/导入/导出表** —— 理解内容的基础
3. **识别资产类** —— 决定提取路径
4. **JSON 输出格式** —— 核心输出需求
5. **蓝图类型检测** —— 知晓文件是否含蓝图数据
6. **变量定义提取** —— 最有价值的蓝图数据，复杂度中等

推迟到阶段 2：
- **蓝图图提取** —— 复杂度高，需深入理解节点/引脚
- **函数定义** —— 复杂度高，需图解析基础
- **语义节点描述** —— 需节点类型目录

推迟到阶段 3：
- **错误恢复与部分解析** —— 需处理众多边缘情况
- **引脚连接映射** —— 需完整图解析

## 数据结构参考

UE 5.7 源码发现的关键结构：

### 包文件摘要（文件头）
- `FPackageFileSummary` 在 `PackageFileSummary.h`
- 含：Tag（魔术）、FileVersionUE、NameCount/Offset、ExportCount/Offset、ImportCount/Offset、PackageFlags

### 名称表条目
- 各名称：FName（字符串 + 数字索引用于区分）
- 所有对象/属性名称来自此表

### 导出表条目
- `FObjectExport`：ObjectName、ClassIndex、OuterIndex、SuperIndex、TemplateIndex、ObjectFlags、SerialSize、SerialOffset

### 导入表条目
- `FObjectImport`：ObjectName、ClassPackage、ClassName、OuterIndex

### 蓝图结构
- `UBlueprint` 在 `Blueprint.h`
- 关键字段：
  - `ParentClass` —— 此蓝图继承的类
  - `BlueprintType` —— BPTYPE_Normal、Interface、MacroLibrary 等
  - `NewVariables` —— TArray<FBPVariableDescription>
  - `FunctionGraphs` —— TArray<UEdGraph>
  - `UbergraphPages` —— TArray<UEdGraph>（事件图）
  - `ImplementedInterfaces` —— TArray<FBPInterfaceDescription>
  - `ComponentTemplates` —— TArray<UActorComponent>

### 变量定义
- `FBPVariableDescription`：VarName、VarGuid、VarType、FriendlyName、Category、PropertyFlags、DefaultValue、MetaDataArray

### 图结构
- `UEdGraph`：Schema、Nodes（TArray<UEdGraphNode>）、GraphGuid、bEditable
- `UEdGraphNode`：Pins、NodePosX/Y、NodeComment、NodeGuid、EnabledState

### 节点结构
- `UK2Node`（继承 UEdGraphNode）：所有蓝图节点基类
- 子类：K2Node_CallFunction、K2Node_VariableGet、K2Node_Event、K2Node_MacroInstance 等

### 引脚结构
- `UEdGraphPin`：PinId、PinName、Direction、PinType、DefaultValue、LinkedTo（连接）、SubPins、ParentPin
- `FEdGraphPinType`：PinCategory、PinSubCategory、ContainerType（None/Array/Set/Map）、bIsReference、bIsConst

### 属性类型（FPropertyTag.Type）
- BoolProperty、IntProperty、FloatProperty、StrProperty、NameProperty
- ObjectProperty、ClassProperty、StructProperty、ArrayProperty
- MapProperty、SetProperty、EnumProperty、ByteProperty
- DelegateProperty、MulticastDelegateProperty
- TextProperty、SoftObjectProperty、WeakObjectProperty

## 来源

- UE 5.7 源码：`D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/CoreUObject/Public/UObject/PackageFileSummary.h`
- UE 5.7 源码：`D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/CoreUObject/Public/UObject/ObjectResource.h`
- UE 5.7 源码：`D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/Engine/Classes/Engine/Blueprint.h`
- UE 5.7 源码：`D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/Engine/Classes/EdGraph/EdGraph.h`
- UE 5.7 源码：`D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/Engine/Classes/EdGraph/EdGraphNode.h`
- UE 5.7 源码：`D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/Engine/Classes/EdGraph/EdGraphPin.h`
- UE 5.7 源码：`D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Editor/BlueprintGraph/Classes/K2Node.h`
- UE 5.7 源码：`D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/CoreUObject/Public/UObject/PropertyTag.h`
- PROJECT.md：`E:\Develop\uasset_read\.planning\PROJECT.md`（需求背景）

## 置信度评估

| 区域 | 水平 | 原因 |
|------|------|------|
| 包结构 | 高 | 直接读取 UE 5.7 源码；权威 |
| 蓝图数据结构 | 高 | 直接读取 UE 5.7 源码；权威 |
| 图/节点/引脚结构 | 高 | 直接读取 UE 5.7 源码；权威 |
| 现有工具功能 | 中 | 网络搜索结果；FModel、UE Viewer 已确认 |
| AI-agent 友好输出模式 | 低 | 无 AI agent 消费模式直接研究；从需求推断 |

## 待解决缺口

- **蓝图字节码 vs 编辑器数据**：需明确目标资产是 cooked（字节码）还是未 cooked（编辑器图）。PROJECT.md 暗示未 cooked，因提及"蓝图节点"。
- **版本兼容矩阵**：UE 4.x 到 5.7 版本序列化不同；需确定初始支持哪些版本。
- **属性值反序列化**：理解如何实际读取属性值（非仅元数据）需更深序列化研究。
- **节点类型目录**：语义描述需所有 UK2Node 子类及其特定数据字段目录。
- **错误处理模式**：需研究常见解析失败及如何优雅恢复。