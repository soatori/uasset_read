# 蓝图生成类 (Blueprint Generated Class)

## 概述

UBlueprintGeneratedClass 是蓝图编译后生成的可执行类，继承自 UClass 并实现 IBlueprintPropertyGuidProvider 接口。它存储编译产物，包括字节码、组件模板、时间线模板和动态绑定对象。

生成类是蓝图资产的运行时表现形式，实例化蓝图对象时使用该类的 ClassDefaultObject (CDO) 作为原型。

## 继承关系

```
UObject
└── UField (字段基类)
    └── UStruct (结构基类)
        └── UClass (类定义基类)
            └── UBlueprintGeneratedClass (蓝图生成类)
                ├── 继承 UClass 所有功能
                ├── 实现 IBlueprintPropertyGuidProvider 接口
                ├── 添加蓝图特有属性
                └── 存储编译后的字节码和调试数据
```

源码位置:
- BlueprintGeneratedClass.h:432 — `class UBlueprintGeneratedClass : public UClass, public IBlueprintPropertyGuidProvider`
- Class.h:3792 — `class UClass : public UStruct`

## UClass 核心字段 (继承)

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| ClassFlags | EClassFlags | 类标志位 (CLASS_Native, CLASS_Abstract 等) | Class.h:3823 |
| ClassCastFlags | EClassCastFlags | Cast 标志位，加速动态类型检查 | Class.h:3826 |
| ClassWithin | TObjectPtr<UClass> | 类作用域限制，实例 Outer 类型要求 | Class.h:3830 |
| ClassConfigName | FName | 配置文件名 (.ini 文件) | Class.h:3856 |
| ClassDefaultObject | TObjectPtr<UObject> | 类默认对象 (CDO) | Class.h:3928 |
| ClassReps | TArray<FRepRecord> | 复制记录列表 | Class.h:3868 |
| FuncMap | TMap<FName, TObjectPtr<UFunction>> | 函数名到 UFunction 映射 | Class.h:3992 |
| Interfaces | TArray<FImplementedInterface> | 实现的接口列表 | Class.h:4010 |
| ClassGeneratedBy | TObjectPtr<UObject> | 生成此类的蓝图 (编辑器专用) | Class.h:3835 |
| SparseClassData | void* | 稀疏类数据 | Class.h:3936 |
| SparseClassDataStruct | TObjectPtr<UScriptStruct> | 稀疏类数据结构 | Class.h:3939 |

注: ClassDefaultObject 存储类默认属性值，实例化时复制到新对象。SparseClassData 提供类级别数据存储。

## UBlueprintGeneratedClass 特有字段

### 运行时字段

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| NumReplicatedProperties | int32 | 复制属性数量 (AssetRegistrySearchable) | BlueprintGeneratedClass.h:439 |
| bHasCookedComponentInstancingData | uint8 | 是否有 Cooked 组件实例化数据 | BlueprintGeneratedClass.h:443 |
| bSupportsDynamicInstancedReference | uint8 | 是否支持动态实例化引用 | BlueprintGeneratedClass.h:450 |
| bCustomPropertyListForPostConstructionInitialized | uint8 (private) | 自定义属性列表是否已初始化 | BlueprintGeneratedClass.h:460 |
| DynamicBindingObjects | TArray<TObjectPtr<UDynamicBlueprintBinding>> | 动态绑定对象数组 | BlueprintGeneratedClass.h:465 |
| ComponentTemplates | TArray<TObjectPtr<UActorComponent>> | 组件模板数组 | BlueprintGeneratedClass.h:469 |
| Timelines | TArray<TObjectPtr<UTimelineTemplate>> | 时间线模板数组 | BlueprintGeneratedClass.h:473 |
| ComponentClassOverrides | TArray<FBPComponentClassOverride> | 组件类覆盖数组 | BlueprintGeneratedClass.h:477 |
| FieldNotifies | TArray<FFieldNotificationId> | 字段通知数组 | BlueprintGeneratedClass.h:481 |
| FieldNotifiesStartBitNumber | int32 | 字段通知起始位号 | BlueprintGeneratedClass.h:483 |
| SimpleConstructionScript | TObjectPtr<USimpleConstructionScript> | 简单构造脚本 | BlueprintGeneratedClass.h:487 |
| InheritableComponentHandler | TObjectPtr<UInheritableComponentHandler> | 可继承组件处理器 | BlueprintGeneratedClass.h:491 |
| UberGraphFramePointerProperty | FStructProperty* | UberGraph 帧指针属性 | BlueprintGeneratedClass.h:493 |
| UberGraphFunction | TObjectPtr<UFunction> | UberGraph 函数 | BlueprintGeneratedClass.h:496 |
| CookedPropertyGuids | TMap<FName, FGuid> | Cooked 属性 GUID 映射 | BlueprintGeneratedClass.h:523 |
| CookedComponentInstancingData | TMap<FName, FBlueprintCookedComponentInstancingData> | Cooked 组件实例化数据 | BlueprintGeneratedClass.h:528 |

### 编辑器专用字段 (WITH_EDITORONLY_DATA)

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| bIsSparseClassDataSerializable | uint8 | 稀疏类数据是否可序列化 | BlueprintGeneratedClass.h:455 |
| FastCallPairs_DEPRECATED | TArray<FEventGraphFastCallPair> | 快速调用对 (已弃用，VER_UE4_SERIALIZE_BLUEPRINT_EVENTGRAPH_FASTCALLS_IN_UFUNCTION 之前使用) | BlueprintGeneratedClass.h:506 |
| OverridenArchetypeForCDO | TObjectPtr<UObject> (Transient) | CDO 覆盖原型 | BlueprintGeneratedClass.h:511 |
| PropertyGuids | TMap<FName, FGuid> | 属性 GUID 映射 | BlueprintGeneratedClass.h:515 |
| CalledFunctions | TArray<TObjectPtr<UFunction>> (Transient) | 被调用函数列表 | BlueprintGeneratedClass.h:518 |
| DebugData | FBlueprintDebugData | 调试数据 | BlueprintGeneratedClass.h:697 |

## 字段用途说明

### 组件实例化

| 字段组合 | 用途 |
|----------|------|
| ComponentTemplates + SimpleConstructionScript | AddComponent 节点使用的组件模板和构造脚本 |
| InheritableComponentHandler | 子蓝图覆盖父蓝图组件的处理器 |
| CookedComponentInstancingData | Cooked 构建时优化的组件实例化数据 |
| bHasCookedComponentInstancingData | 标记是否使用快速路径实例化 |
| bSupportsDynamicInstancedReference | 支持动态子对象实例化（实验性功能） |

### UberGraph 机制

| 字段组合 | 用途 |
|----------|------|
| UberGraphFunction + UberGraphFramePointerProperty | 持久化 UberGraph 帧，存储事件图表局部变量 |
| UsePersistentUberGraphFrame() | 控制是否使用持久化帧 (静态方法) |
| FPointerToUberGraphFrame | UberGraph 帧指针结构（BlueprintGeneratedClass.h:85-110） |

### 属性 GUID

| 字段组合 | 用途 |
|----------|------|
| PropertyGuids (编辑器) | 编辑时属性 GUID 映射 |
| CookedPropertyGuids (Cooked) | Cooked 构建时保留的属性 GUID |
| FindBlueprintPropertyNameFromGuid() | GUID 到属性名查询接口 |
| FindBlueprintPropertyGuidFromName() | 属性名到 GUID 查询接口 |
| ArePropertyGuidsAvailable() | 检查属性 GUID 是否可用 |

注: ShouldCookPropertyGuids 控制是否在 Cooked 构建中保留属性 GUID。

## FBlueprintDebugData 调试数据结构

FBlueprintDebugData 存储编辑器调试信息，支持断点、节点追踪等功能。

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| DebugNodesAllocatedUniqueIDsMap | TMap<int32, TWeakObjectPtr<UEdGraphNode>> | UUID 到节点映射 | BlueprintGeneratedClass.h:215 |
| DebugNodeIndexLookup | TMultiMap<TWeakObjectPtr<UEdGraphNode>, int32> | 节点到调试索引映射 | BlueprintGeneratedClass.h:218 |
| DebugNodeLineNumbers | TArray<FNodeToCodeAssociation> | 节点到字节码偏移关联 | BlueprintGeneratedClass.h:223 |
| EntryPoints | TMap<int32, FName> | Ubergraph 入口点 | BlueprintGeneratedClass.h:226 |
| PerFunctionLineNumbers | TMap<TWeakObjectPtr<UFunction>, FDebuggingInfoForSingleFunction> | 每函数调试信息 | BlueprintGeneratedClass.h:229 |
| DebugObjectToPropertyMap | TMap<TWeakObjectPtr<UObject>, TFieldPath<FProperty>> | 对象到属性映射 | BlueprintGeneratedClass.h:232 |
| DebugPinToPropertyMap | TMap<FEdGraphPinReference, TFieldPath<FProperty>> | 引脚到属性映射 | BlueprintGeneratedClass.h:235 |

### FDebuggingInfoForSingleFunction 结构

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| LineNumberToSourceNodeMap | TMap<int32, TWeakObjectPtr<UEdGraphNode>> | 代码偏移到源节点反向映射 | BlueprintGeneratedClass.h:63 |
| LineNumberToSourcePinMap | TMap<int32, FEdGraphPinReference> | 代码偏移到源引脚反向映射 | BlueprintGeneratedClass.h:66 |
| SourcePinToLineNumbersMap | TMultiMap<FEdGraphPinReference, int32> | 源引脚到代码偏移映射 | BlueprintGeneratedClass.h:69 |
| PureNodeScriptCodeRangeMap | TMap<TWeakObjectPtr<UEdGraphNode>, FInt32Range> | 纯节点脚本代码范围 | BlueprintGeneratedClass.h:72 |
| LineNumberToTunnelInstanceSourceNodesMap | TMap<int32, TArray<TWeakObjectPtr<UEdGraphNode>>> | 代码偏移到隧道实例源节点 | BlueprintGeneratedClass.h:75 |

### FNodeToCodeAssociation 结构

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| Node | TWeakObjectPtr<UEdGraphNode> | 节点引用 | BlueprintGeneratedClass.h:36 |
| Scope | TWeakObjectPtr<UFunction> | 函数作用域 | BlueprintGeneratedClass.h:37 |
| Offset | int32 | 字节码偏移 | BlueprintGeneratedClass.h:38 |

注: WITH_EDITORONLY_DATA 宏控制，非编辑器构建不包含调试数据。

## 与 UClass 关系

蓝图生成类与普通 C++ 类的主要差异：

| 方面 | UClass (C++) | UBlueprintGeneratedClass (蓝图) |
|------|--------------|--------------------------------|
| 类定义来源 | C++ 编译时静态定义 | 蓝图编译时动态生成 |
| ClassGeneratedBy | nullptr | 指向源蓝图 UBlueprint |
| 函数实现 | Native 函数指针 | 字节码 (Script) |
| 属性定义 | 静态反射数据 | 编译时生成 UProperty |
| 组件模板 | 无 | ComponentTemplates 数组 |
| 调试数据 | 无 | DebugData (编辑器) |
| 热重载 | 需重启 | 支持运行时重新编译 |
| 字段通知 | 无 | FieldNotifies 数组 |

源码位置:
- Class.h:3835 — `ClassGeneratedBy` 字段定义
- BlueprintGeneratedClass.h:432 — 生成类继承关系

## 源码引用

| 文件路径 | 说明 |
|----------|------|
| Runtime/Engine/Classes/Engine/BlueprintGeneratedClass.h | UBlueprintGeneratedClass 定义、字段声明 |
| Runtime/Engine/Private/BlueprintGeneratedClass.cpp | 生成类实现、Serialize、PostLoad |
| Runtime/CoreUObject/Public/UObject/Class.h | UClass 基类定义 |
| Runtime/CoreUObject/Public/UObject/Object.h | UObject 基类定义 |
| Runtime/Engine/Classes/Engine/Blueprint.h | UBlueprint 源资产定义 |
| Runtime/Engine/Private/Blueprint.cpp | 蓝图编译、RegenerateClass |

## 版本差异

### UE5 改进

| 特性 | 说明 |
|------|------|
| 稀疏类数据序列化 | bIsSparseClassDataSerializable 控制稀疏数据序列化 |
| 属性 GUID Cook | ShouldCookPropertyGuids 控制是否保留 GUID |
| 动态实例化 | bSupportsDynamicInstancedReference 支持动态子对象实例化（实验性） |
| 快速路径 | CookedComponentInstancingData 优化组件实例化性能 |
| Cooked 元数据 | UClassCookedMetaData 存储 Cooked 构建元数据 |
| FieldNotifies | 字段通知系统，支持属性变化事件 |
| GetGeneratedClassesHierarchy | 获取蓝图生成类继承层次的静态方法 |

### UE4 版本

| 特性 | 说明 |
|------|------|
| FastCallPairs | VER_UE4_SERIALIZE_BLUEPRINT_EVENTGRAPH_FASTCALLS_IN_UFUNCTION 前使用 (已弃用) |
| 基础 UberGraph | UberGraphFunction 和 UberGraphFramePointerProperty 基础结构 |
| 组件模板 | ComponentTemplates 和 SimpleConstructionScript 基础结构 |

### 版本号控制

| 版本号 | 说明 | 源码位置 |
|--------|------|----------|
| VER_UE4_BLUEPRINT_GENERATED_CLASS_COMPONENT_TEMPLATES_PUBLIC | 组件模板公开访问 | ObjectVersion.h |
| VER_UE4_SERIALIZE_BLUEPRINT_EVENTGRAPH_FASTCALLS_IN_UFUNCTION | 快速调用序列化迁移 | ObjectVersion.h |

## 与其他资产的关联

| 关联类型 | 说明 |
|----------|------|
| UBlueprint | ClassGeneratedBy 指向源蓝图，GeneratedClass 反向引用 |
| USimpleConstructionScript | 构造脚本，组件实例化逻辑 |
| UTimelineTemplate | 时间线模板，运行时创建 UTimelineComponent |
| UDynamicBlueprintBinding | 动态委托绑定 |

详见:
- [blueprint-source.md](blueprint-source.md) — UBlueprint 源资产结构
- [blueprint-compilation.md](blueprint-compilation.md) — 蓝图编译机制

---
*Source: Runtime/Engine/Classes/Engine/BlueprintGeneratedClass.h, Runtime/CoreUObject/Public/UObject/Class.h (UE5 源码验证)*
*Phase: 05-蓝图与动画资产*
