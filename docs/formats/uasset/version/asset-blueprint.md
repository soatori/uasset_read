# 蓝图资产版本差异

## 概述

蓝图资产 (UBlueprint/UBlueprintGeneratedClass) 在 UE4 至 UE5 演进过程中经历多项格式变更，涉及 Blueprint 变量限制变更、Skeleton 类处理、蓝图编译机制、节点引用机制等变更。本文档汇总蓝图相关关键版本差异。

> **源码同步状态**: 基于 `ObjectVersion.h` EUnrealEngineObjectUE4Version 枚举和 `BlueprintsObjectVersion.h` FBlueprintsObjectVersion 自定义版本。

## UE4 版本差异表格

| 版本号 | 版本名 | 变更描述 | 影响字段/结构 |
|-------|--------|----------|---------------|
| 216 | VER_UE4_BLUEPRINT_VARS_NOT_READ_ONLY | Blueprint 变量不再强制只读 | 变量访问控制 |
| 225 | VER_UE4_BLUEPRINT_SKEL_TEMPORARY_TRANSIENT | Blueprint Skeleton 类临时瞬态化 | SkeletonClass 生命周期 |
| 227 | VER_UE4_BLUEPRINT_SKEL_SERIALIZED_AGAIN | Blueprint Skeleton 类重新序列化 | SkeletonClass 序列化 |
| 229 | VER_UE4_BLUEPRINT_SETS_REPLICATION | Blueprint 设置复制 | ReplicationSettings |
| 250 | VER_UE4_ADDED_SKELETON_ARCHIVER_REMOVAL | Blueprint Skeleton Archiver 移除 | Skeleton 引用移除 |
| 253 | VER_UE4_ADDED_SKELETON_ARCHIVER_REMOVAL_SECOND_TIME | Blueprint Skeleton Archiver 移除第二次 | Skeleton 引用处理 |
| 256 | VER_UE4_BLUEPRINT_SKEL_CLASS_TRANSIENT_AGAIN | Blueprint Skeleton 类瞬态化 | SkeletonClassTransient |
| 323 | VER_UE4_BLUEPRINT_INPUT_BINDING_OVERRIDES | Blueprint 输入绑定覆盖 | InputBindingOverrides |
| 349 | VER_UE4_BP_ACTOR_VARIABLE_DEFAULT_PREVENTING | Blueprint Actor 变量默认值阻止 | ActorVariableDefault |
| 364 | VER_UE4_MEMBERREFERENCE_IN_PINTYPE | PinType 中添加 MemberReference | PinSubCategoryMemberReference |
| 406 | VER_UE4_FIX_BLUEPRINT_VARIABLE_FLAGS | Blueprint 变量标志修复 | VariableFlags |
| 430 | VER_UE4_POST_DUPLICATE_NODE_GUID | Blueprint 复制后节点 Guid 重新生成 | PostDuplicateNodeGuid |
| 466 | VER_UE4_BLUEPRINT_GENERATED_CLASS_COMPONENT_TEMPLATES_PUBLIC | Blueprint 生成类组件模板公开 | ComponentTemplatesPublic |
| 477 | VER_UE4_ACTOR_COMPONENT_CREATION_METHOD | Blueprint Actor 组件创建方法 | ActorComponentCreationMethod |
| 521 | VER_UE4_K2NODE_EVENT_MEMBER_REFERENCE | Blueprint 事件节点成员引用 | K2Node_Event MemberReference |
| 533 | VER_UE4_BLUEPRINT_CUSTOM_EVENT_CONST_INPUT | Blueprint 自定义事件 Const 输入 | CustomEventConstInput |
| 547 | VER_UE4_DISABLED_SCRIPT_LIMIT_BYTECODE | Blueprint 脚本字节码限制禁用 | ScriptBytecodeLimit |
| 563 | VER_UE4_K2NODE_VAR_REFERENCEGUIDS | Blueprint 变量引用 Guid | VariableReferenceGuid |
| 621 | VER_UE4_SCS_STORES_ALLNODES_ARRAY | Blueprint SCS 存储 AllNodes 数组 | SCS AllNodes |
| 634 | VER_UE4_BLUEPRINT_ENFORCE_CONST_IN_FUNCTION_OVERRIDES | Blueprint 常函数覆盖 Const | ConstFunctionOverrides |
| 669 | VER_UE4_INJECT_BLUEPRINT_STRUCT_PIN_CONVERSION_NODES | Blueprint 函数调参数转换注入 | StructPinConversionNodes |

## UE5 蓝图变更

| 特性 | 版本 | 说明 |
|------|------|------|
| Script Serialization Offset | 1010 | Export 表添加脚本序列化偏移字段 |
| Property Tag Extension | 1011 | 属性标签扩展支持 |
| OS Sub Object Shadow Serialization | 1017 | 子对象阴影序列化 |

## FBlueprintsObjectVersion 自定义版本

> 定义位置: `Runtime/Core/Public/UObject/BlueprintsObjectVersion.h`

| 版本值 | 版本名 | 说明 |
|-------|--------|------|
| 0 | BeforeCustomVersionWasAdded | 初始版本 |
| 1 | OverridenEventReferenceFixup | 覆盖事件引用修复 |
| 2 | CleanBlueprintFunctionFlags | 蓝图函数标志清理 |
| 3 | ArrayGetByRefUpgrade | 数组 Get 按引用升级 |
| 4 | EdGraphPinOptimized | EdGraphPin 优化 |
| 5 | AllowDeletionConformed | 允许删除一致性 |
| 6 | AdvancedContainerSupport | 高级容器支持 |
| 7 | SCSHasComponentTemplateClass | SCS 组件模板类支持 |
| 8 | ComponentTemplateClassSupport | 组件模板类支持 |
| 9 | ArrayGetFuncsReplacedByCustomNode | 数组 Get 函数替换为自定义节点 |
| 10 | DisallowObjectConfigVars | 禁止对象配置变量 |

## 关键变更详细说明

### Skeleton 类生命周期变更 (225, 227, 250, 253, 256)

Skeleton 类在多个版本中经历多次变更：
- VER_UE4_BLUEPRINT_SKEL_TEMPORARY_TRANSIENT (225)：Skeleton 类变为临时瞬态
- VER_UE4_BLUEPRINT_SKEL_SERIALIZED_AGAIN (227)：重新序列化 Skeleton 类
- VER_UE4_ADDED_SKELETON_ARCHIVER_REMOVAL (250)：移除 Skeleton Archiver
- VER_UE4_ADDED_SKELETON_ARCHIVER_REMOVAL_SECOND_TIME (253)：第二次移除
- VER_UE4_BLUEPRINT_SKEL_CLASS_TRANSIENT_AGAIN (256)：再次变为瞬态

### VER_UE4_POST_DUPLICATE_NODE_GUID (430)

蓝图复制后重新生成 NodeGuid：
- 版本 < 430：复制节点保留原 Guid
- 版本 >= 430：复制后自动生成新 Guid

### VER_UE4_K2NODE_EVENT_MEMBER_REFERENCE (521)

K2Node_Event 使用 FMemberReference：
- 版本 < 521：事件节点直接存储函数名
- 版本 >= 521：使用 FMemberReference 结构，支持引用追踪

### VER_UE4_SCS_STORES_ALLNODES_ARRAY (621)

SCS 存储 AllNodes 数组：
- 版本 < 621：递归构建节点层次
- 版本 >= 621：直接存储 AllNodes 数组，避免递归构建

## 源码引用

| 文件 | 路径 | 说明 |
|------|------|------|
| ObjectVersion.h | Runtime/Core/Public/UObject/ | 版本枚举定义 |
| BlueprintsObjectVersion.h | Runtime/Core/Public/UObject/ | 蓝图 CustomVersion |
| Blueprint.h | Runtime/Engine/Classes/Engine/ | 蓝图类定义 |
| BlueprintGeneratedClass.h | Runtime/Engine/Classes/Engine/ | 蓝图生成类定义 |

---

*详见版本演进主文档：[ue4-evolution.md](ue4-evolution.md)、[ue5-evolution.md](ue5-evolution.md)*
*Updated: 2026-06-01 — 基于 UE ObjectVersion.h + BlueprintsObjectVersion.h 完整枚举同步版本号与版本名*
