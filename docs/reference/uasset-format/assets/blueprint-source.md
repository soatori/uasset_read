# 蓝图源资产结构 (UBlueprint)

## 概述

UBlueprint 是蓝图资产的源数据类，存储蓝图编辑器中的视觉设计数据。蓝图在运行时编译为 UBlueprintGeneratedClass，实现从可视化设计到可执行类的转换。

蓝图资产通常包含以下核心组成部分：
- **类型定义**: BlueprintType 指定蓝图用途（普通类、接口、宏库等）
- **继承关系**: ParentClass 指定父类，GeneratedClass 存储编译产物
- **图表数据**: UbergraphPages、FunctionGraphs 等存储视觉节点图
- **成员定义**: NewVariables、ImplementedInterfaces 等定义类成员

## UBlueprint 核心字段表

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| BlueprintType | TEnumAsByte<EBlueprintType> | 蓝图类型枚举 | Blueprint.h:416 |
| ParentClass | TSubclassOf<UObject> | 父类引用 | Blueprint.h:412 |
| BlueprintSystemVersion | int32 | 蓝图系统版本号 | Blueprint.h:530 |
| SimpleConstructionScript | TObjectPtr<USimpleConstructionScript> | 简单构造脚本 | Blueprint.h:534 |
| ComponentTemplates | TArray<TObjectPtr<UActorComponent>> | 组件模板数组 | Blueprint.h:568 |
| Timelines | TArray<TObjectPtr<UTimelineTemplate>> | 时间轴模板数组 | Blueprint.h:572 |
| ComponentClassOverrides | TArray<FBPComponentClassOverride> | 组件类覆盖 | Blueprint.h:576 |
| InheritableComponentHandler | TObjectPtr<UInheritableComponentHandler> | 继承组件处理器 | Blueprint.h:580 |
| bRecompileOnLoad | uint8 (bool bitfield) | 加载时重新编译标志 | Blueprint.h:420 |
| bHasBeenRegenerated | uint8 (transient) | 已重新生成标志 | Blueprint.h:424 |
| bIsRegeneratingOnLoad | uint8 (transient) | 正在加载时重新生成 | Blueprint.h:428 |

## EBlueprintType 类型枚举

| 枚举值 | 说明 |
|--------|------|
| BPTYPE_Normal | 普通蓝图类 |
| BPTYPE_Const | 常量蓝图类（无状态图，方法不可修改成员变量） |
| BPTYPE_MacroLibrary | 蓝图宏库 |
| BPTYPE_Interface | 蓝图接口 |
| BPTYPE_LevelScript | 关卡蓝图 |
| BPTYPE_FunctionLibrary | 蓝图函数库 |

源码位置: Blueprint.h:61-77

## EBlueprintStatus 状态枚举

| 枚举值 | 说明 |
|--------|------|
| BS_Unknown | 未知状态 |
| BS_Dirty | 已修改但未重新编译 |
| BS_Error | 编译失败 |
| BS_UpToDate | 已编译且最新 |
| BS_BeingCreated | 正在首次创建 |
| BS_UpToDateWithWarnings | 已编译但有警告 |

源码位置: Blueprint.h:41-56

## 图表引用字段

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| UbergraphPages | TArray<TObjectPtr<UEdGraph>> | 主图表页面（EventGraph） | Blueprint.h:539 |
| FunctionGraphs | TArray<TObjectPtr<UEdGraph>> | 函数图表列表 | Blueprint.h:543 |
| DelegateSignatureGraphs | TArray<TObjectPtr<UEdGraph>> | 委托签名图表 | Blueprint.h:547 |
| MacroGraphs | TArray<TObjectPtr<UEdGraph>> | 宏图表列表 | Blueprint.h:551 |
| EventGraphs | TArray<TObjectPtr<UEdGraph>> (transient) | 事件图表（编译时生成） | Blueprint.h:559 |

注: 图表结构详情见 UE 源码 UEdGraph 定义，本文档不展开。图表字段仅在 `WITH_EDITORONLY_DATA` 宏定义下存在。

## 成员字段

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| NewVariables | TArray<FBPVariableDescription> | 新变量列表 | Blueprint.h:588 |
| GeneratedVariables | TArray<FBPVariableDescription> | 生成的变量列表 | Blueprint.h:592 |
| ImplementedInterfaces | TArray<FBPInterfaceDescription> | 实现的接口列表 | Blueprint.h:604 |
| CategorySorting | TArray<FName> | 分类排序数组 | Blueprint.h:596 |

注: 成员详细结构见 UE 源码 FBPVariableDescription、FBPInterfaceDescription 定义，本文档仅列出字段存在。

## FBPVariableDescription 结构

| 字段名 | 类型 | 用途 |
|--------|------|------|
| VarName | FName | 变量名称 |
| VarGuid | FGuid | 变量 GUID（名称变化时保持不变） |
| VarType | FEdGraphPinType | 变量类型 |
| FriendlyName | FString | 变量友好名称 |
| Category | FText | 变量分类 |
| PropertyFlags | uint64 | 属性标志位 |
| RepNotifyFunc | FName | 复制通知函数名 |
| ReplicationCondition | ELifetimeCondition | 复制条件 |
| MetaDataArray | TArray<FBPVariableMetaDataEntry> | 元数据数组 |
| DefaultValue | FString | 默认值字符串 |

源码位置: Blueprint.h:201-256

## FBPInterfaceDescription 结构

| 字段名 | 类型 | 用途 |
|--------|------|------|
| Interface | TSubclassOf<UInterface> | 接口类引用 |
| Graphs | TArray<TObjectPtr<UEdGraph>> | 接口函数图表 |

源码位置: Blueprint.h:260-277

## 编辑器专用字段

以下字段仅在 `WITH_EDITORONLY_DATA` 宏定义下存在，不参与运行时序列化：

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| Status | TEnumAsByte<EBlueprintStatus> (transient) | 当前编译状态 | Blueprint.h:504 |
| CompileMode | EBlueprintCompileMode | 编译模式 | Blueprint.h:500 |
| BlueprintDisplayName | FString | 编辑器显示名称 | Blueprint.h:508 |
| BlueprintDescription | FString | 内容浏览器提示文本 | Blueprint.h:512 |
| BlueprintNamespace | FString | 蓝图命名空间 | Blueprint.h:516 |
| BlueprintCategory | FString | 蓝图分类 | Blueprint.h:520 |
| HideCategories | TArray<FString> | 额外隐藏分类 | Blueprint.h:524 |
| bGenerateConstClass | uint8 (bool) | 生成常量类标志 | Blueprint.h:457 |
| bGenerateAbstractClass | uint8 (bool) | 生成抽象类标志 | Blueprint.h:461 |
| bDeprecate | uint8 (bool) | 标记已弃用 | Blueprint.h:469 |
| ThumbnailInfo | TObjectPtr<UThumbnailInfo> | 缩略图信息 | Blueprint.h:723 |
| LastEditedDocuments | TArray<FEditedDocumentInfo> | 最后编辑的文档 | Blueprint.h:608 |
| Bookmarks | TMap<FGuid, FEditedDocumentInfo> | 书签数据 | Blueprint.h:612 |
| ImportedNamespaces | TSet<FString> | 导入的命名空间 | Blueprint.h:600 |

## 源码引用

| 文件路径 | 说明 |
|----------|------|
| Runtime/Engine/Classes/Engine/Blueprint.h | UBlueprint 主类定义 |
| Runtime/Engine/Classes/Engine/BlueprintCore.h | 蓝图核心基类 |
| Runtime/CoreUObject/Public/UObject/Class.h | UClass 结构定义 |
| Runtime/Engine/Private/Blueprint.cpp | 蓝图编译机制实现 |
| Runtime/Engine/Classes/EdGraph/EdGraph.h | 图表结构定义 |

## 版本差异

### UE5 新增特性
- **ShouldCookPropertyGuidsValue**: 控制属性 GUID 是否在 Cooked 构建中保留（Blueprint.h:493）
- **更多蓝图类型**: 枚举值扩展支持更多蓝图用途
- **ImportedNamespaces**: 命名空间导入机制（Blueprint.h:600）

### UE4 版本控制
- **VER_UE4_BLUEPRINT 系列版本号**: 控制蓝图编译兼容性（见 ObjectVersion.h）
- **BlueprintSystemVersion**: 当前版本为 2（Blueprint.h:1096）

### 编辑器数据分离
- **WITH_EDITORONLY_DATA 宏**: 大量编辑器专用字段在 Cooked 版本中被剔除
- **transient 标志**: 编译状态、缓存数据等运行时不持久化

## 与其他资产的关联

| 关联类型 | 说明 |
|----------|------|
| UBlueprintGeneratedClass | 蓝图编译产物，由 GeneratedClass 字段引用 |
| UClass | 父类引用，由 ParentClass 字段指向 |
| USimpleConstructionScript | 构造脚本，组件实例化逻辑 |
| UEdGraph | 图表对象，存储节点连线数据 |

详见 [import-export-tables.md](../import-export-tables.md) 中 FPackageIndex 引用机制说明。

---
*Source: Runtime/Engine/Classes/Engine/Blueprint.h*
*Phase: 05-蓝图与动画资产*