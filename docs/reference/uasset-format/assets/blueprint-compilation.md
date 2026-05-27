# 蓝图编译机制 (Blueprint Compilation)

## 概述

蓝图编译是将 UBlueprint 源数据转换为 UBlueprintGeneratedClass 可执行类的过程。编译器将可视化图表节点转换为可执行字节码，并生成类定义、属性绑定和函数实现。

## 编译流程

蓝图编译流程包含以下核心步骤：

1. **收集阶段**: 遍历 UbergraphPages、FunctionGraphs 等图表，收集节点、变量、函数定义
2. **验证阶段**: 检查节点连接完整性、类型兼容性，确保编译正确性
3. **生成阶段**: 创建 UBlueprintGeneratedClass，生成属性定义、函数字节码和构造脚本

编译产物存储在 GeneratedClass 字段中，运行时通过该类实例化蓝图对象。

## 编译触发时机

| 触发条件 | 说明 |
|----------|------|
| 编辑器保存 | 用户保存蓝图资产时自动触发编译 |
| 运行时加载 | 加载未编译或需要重新编译的蓝图时触发 |
| 热重载 | Hot Reload 时重新编译修改的蓝图 |
| 首次加载 | bRecompileOnLoad 为 true 时首次加载重新编译 |

## 编译状态字段

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| bRecompileOnLoad | uint8 | 加载时是否重新编译 | Blueprint.h:420 |
| bHasBeenRegenerated | uint8 (transient) | 是否已完成重新生成 | Blueprint.h:424 |
| bIsRegeneratingOnLoad | uint8 (transient) | 是否正在加载时重新生成 | Blueprint.h:428 |
| bBeingCompiled | uint8 (transient) | 是否正在编译中 | Blueprint.h:434 |
| bQueuedForCompilation | uint8 (transient) | 是否排队等待编译 | Blueprint.h:445 |
| Status | TEnumAsByte<EBlueprintStatus> | 当前编译状态 | Blueprint.h:504 |
| CompileMode | EBlueprintCompileMode | 编译模式设置 | Blueprint.h:500 |

注: transient 标志的字段不参与序列化，仅在运行时有效。

## 编译产物字段

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| GeneratedClass | TSubclassOf<UObject> | 编译生成的完整类 | BlueprintCore.h:25 |
| SkeletonGeneratedClass | TSubclassOf<UObject> (transient) | 骨架类（用于编辑器预览） | BlueprintCore.h:21 |

GeneratedClass 存储完整编译产物，包含所有属性、函数和字节码。SkeletonGeneratedClass 是轻量级骨架类，用于编辑器快速预览成员变化。

## 编译类型枚举

| 枚举值 | 说明 | 源码位置 |
|--------|------|----------|
| SkeletonOnly | 仅生成骨架类 | Blueprint.h:85 |
| Full | 完整编译 | Blueprint.h:86 |
| StubAfterFailure | 编译失败后生成桩 | Blueprint.h:87 |
| BytecodeOnly | 仅生成字节码 | Blueprint.h:88 |

源码位置: EKismetCompileType (Blueprint.h:81-91)

## 编译模式枚举

| 枚举值 | 说明 | 源码位置 |
|--------|------|----------|
| Default | 使用默认设置 | Blueprint.h:105 |
| Development | 开发模式编译 | Blueprint.h:106 |
| FinalRelease | 最终发布模式编译 | Blueprint.h:107 |

源码位置: EBlueprintCompileMode (Blueprint.h:103-108)

## 编译版本控制

蓝图编译受 UE 版本号控制，确保向后兼容性。主要版本号定义于 ObjectVersion.h:

| 版本号 | 说明 |
|--------|------|
| VER_UE4_BLUEPRINT_VARS_NOT_READ_ONLY | 蓝图变量不再默认只读 |
| VER_UE4_BLUEPRINT_SKEL_CLASS_TRANSIENT_AGAIN | 骨架类标记为 transient |
| VER_UE4_FIX_BLUEPRINT_VARIABLE_FLAGS | 修复蓝图变量标志 |
| VER_UE4_BLUEPRINT_GENERATED_CLASS_COMPONENT_TEMPLATES_PUBLIC | 组件模板公开访问 |

源码位置: Runtime/Core/Public/UObject/ObjectVersion.h

## 源码引用

| 文件路径 | 说明 |
|----------|------|
| Runtime/Engine/Private/Blueprint.cpp | 编译机制实现、RegenerateClass 函数 |
| Runtime/Engine/Classes/Engine/Blueprint.h | UBlueprint 类定义、编译状态字段 |
| Runtime/Engine/Classes/Engine/BlueprintCore.h | UBlueprintCore 基类、GeneratedClass 字段 |
| Runtime/Core/Public/UObject/ObjectVersion.h | 编译版本号定义 |

## 版本差异

### UE5 改进
- **增量编译**: 改进的增量编译性能
- **编译缓存**: 更高效的编译缓存机制
- **属性 GUID**: ShouldCookPropertyGuids 控制是否在 Cooked 构建中保留属性 GUID (Blueprint.h:493)

### UE4 版本
- 基础编译流程
- VER_UE4_BLUEPRINT 系列版本号控制兼容性

## 与其他资产的关联

| 关联类型 | 说明 |
|----------|------|
| UBlueprintGeneratedClass | 编译产物，存储可执行字节码 |
| UEdGraph | 图表源数据，编译输入 |
| USimpleConstructionScript | 构造脚本，组件实例化逻辑 |

详见 [blueprint-source.md](blueprint-source.md) 中 UBlueprint 源资产结构说明。

---
*Source: Runtime/Engine/Classes/Engine/Blueprint.h, Runtime/Engine/Private/Blueprint.cpp*
*Phase: 05-蓝图与动画资产*