# Widget Blueprint 版本差异

## 概述

Widget Blueprint 资产 (UWidgetBlueprint/UWidgetBlueprintGeneratedClass) 在 UE4 到 UE5 演进过程中经历多项结构变更，涉及 Binding 结构演进、属性 GUID 机制、NamedSlot 继承系统、Tick 预测机制等。本文档汇总 UMG 相关关键版本差异，并描述 WidgetAnimation 序列化结构。

> **源码同步状态**: 基于 `ObjectVersion.h` EUnrealEngineObjectUE4Version 枚举。

---

## Part A: WidgetAnimation 序列化

### 继承关系

```
UObject
└── UMovieSceneSequence (MovieScene 序列基类)
    └── UWidgetAnimation (Widget 动画)
```

源码位置:
- WidgetAnimation.h:25 — `class UWidgetAnimation : public UMovieSceneSequence`

### 字段表

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| MovieScene | TObjectPtr<UMovieScene> | MovieScene 引用 | WidgetAnimation.h:142 |
| AnimationBindings | TArray<FWidgetAnimationBinding> | 动画绑定数组 | WidgetAnimation.h:147 |
| bLegacyFinishOnStop | bool | 停止时完成评估标记（旧版行为） | WidgetAnimation.h:152 |
| DisplayLabel | FString | 显示名称 | WidgetAnimation.h:155 |

### UMovieSceneSequence 引用关系

UWidgetAnimation 继承 UMovieSceneSequence，复用 MovieScene 的动画轨道系统：

| 继承方法 | 用途 | 源码位置 |
|----------|------|----------|
| GetMovieScene() | 返回 MovieScene 引用 | WidgetAnimation.h:99 |
| BindPossessableObject() | 绑定动画对象 | WidgetAnimation.h:97 |
| CanPossessObject() | 检查对象可动画性 | WidgetAnimation.h:98 |
| LocateBoundObjects() | 定位绑定对象 | WidgetAnimation.h:104 |

### FWidgetAnimationBinding 结构

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| WidgetName | FName | Widget 名称 | WidgetAnimationBinding.h:30 |
| SlotWidgetName | FName | Slot Widget 名称 | WidgetAnimationBinding.h:33 |
| AnimationGuid | FGuid | 动画 GUID | WidgetAnimationBinding.h:36 |
| bIsRootWidget | bool | 是否为根 Widget | WidgetAnimationBinding.h:39 |
| DynamicBinding | FMovieSceneDynamicBinding | 动态绑定信息 | WidgetAnimationBinding.h:42 |

源码位置: Runtime/UMG/Public/Animation/WidgetAnimationBinding.h:25-67

### MovieScene 格式说明

UMovieScene 完整格式超出本文档范围（MS-01 deferred），简要说明：

| 轨道类型 | 用途 |
|----------|------|
| FloatTrack | 浮点属性动画（位置、缩放、透明度等） |
| ColorTrack | 颜色属性动画 |
| VisibilityTrack | 可见性动画 |
| TransformTrack | 变换动画（位置、旋转、缩放组合） |

MovieScene 详细序列化格式将在后续 MovieScene 专项文档中描述。

---

## Part B: UE4 → UE5 UMG 版本差异

### Binding 结构演进

| 版本 | 结构 | 说明 |
|------|------|------|
| UE4 早期 | 简单 Binding | 仅 ObjectName + PropertyName + FunctionName |
| UE4 后期 | FEditorPropertyPath 引入 | SourcePath 支持深层属性路径 |
| UE5 | FDynamicPropertyPath 完善 | ToPropertyPath() 转换，运行时路径解析优化 |

**版本号控制：**

| 版本号 | 版本名 | 说明 |
|--------|--------|------|
| 486 | VER_UE4_DEPRECATE_UMG_STYLE_ASSETS | UMG 样式资产重构 |
| 527 | VER_UE4_RENAME_WIDGET_VISIBILITY | Widget 可见性重命名（Visiblity → Visibility） |
| 533 | VER_UE4_ADD_PIVOT_TO_WIDGET_COMPONENT | Widget 组件 Pivot 支持 |
| 577 | VER_UE4_DEPRECATE_UMG_STYLE_OVERRIDES | UMG 样式覆盖废弃 |
| 584 | VER_UE4_GRAPH_INTERACTIVE_COMMENTBUBBLES | 图表交互注释气泡 |

### 属性 GUID 机制演进

| 版本 | 字段 | 说明 |
|------|------|------|
| UE4 早期 | 无 GUID | Widget 重命名导致绑定失效 |
| UE4 后期 | WidgetVariableNameToGuidMap | Blueprint 级别 GUID 映射 |
| UE5 | MemberGuid/FEditorPropertyPathSegment.MemberGuid | Binding 级别 GUID 追踪 |

**WidgetVariableNameToGuidMap 用途：**

- 存储本 Blueprint 所有 Widget/Animation 变量的 GUID
- 用于外部引用重命名修复
- OnVariableRenamed() 方法维护映射

源码位置: WidgetBlueprint.h:240-241

### NamedSlot 继承系统演进

| 版本 | 字段/功能 | 说明 |
|------|-----------|------|
| UE4 早期 | NamedSlots 基础 | 仅存储 NamedSlot 名称列表 |
| UE4 后期 | AvailableNamedSlots | 区分可用和已填充 Slot |
| UE5 | bExposeOnInstanceOnly | 实例级别 Slot 暴露控制 |
| UE5 | NamedSlotsWithID | NamedSlot GUID 映射 |
| UE5 | NamedSlotsWithContentInSameTree | 父类已填充 Slot 追踪 |

**bExposeOnInstanceOnly 引入时机：**

UE5 新增字段，允许 NamedSlot 仅在实例级别暴露，不支持子 Blueprint 继承填充。适用于动态 UI 场景。

源码位置: NamedSlot.h:46

### AssetRegistrySearchable 标记引入

| 字段 | 引入版本 | 用途 |
|------|----------|------|
| AvailableNamedSlots | UE5 | Asset Registry 搜索支持 |
| PaletteCategory | UE4 后期 | 调色板分类搜索 |
| TickFrequency | UE5 | Tick 频率搜索 |
| TickPrediction | UE5 | Tick 预测搜索 |
| PropertyBindings | UE5 | 属性绑定数量搜索 |

**用途：**

AssetRegistrySearchable 标记使字段可被 Asset Registry 索引，支持编辑器过滤、搜索和统计。

### TickPrediction 演进

| 版本 | 字段/枚举 | 说明 |
|------|-----------|------|
| UE4 | TickFrequency 基础 | Never/Auto 两种模式 |
| UE5 | EWidgetCompileTimeTickPrediction | 编译时 Tick 预测（WontTick/OnDemand/WillTick） |
| UE5 | TickPredictionReason | 预测原因描述字符串 |

**EWidgetCompileTimeTickPrediction 枚举：**

| 枚举值 | 说明 |
|--------|------|
| WontTick | 无动画/延迟动作/脚本 Tick，性能最优 |
| OnDemand | 有动画/延迟动作，运行时按需启用 Tick |
| WillTick | 有脚本 Tick 或 Native Tick，总是启用 Tick |

源码位置: WidgetBlueprint.h:203-214

---

## Part C: UE5 新增特性

### 无 PlayerContext 初始化

| 字段 | 用途 |
|------|------|
| bCanCallInitializedWithoutPlayerContext | 允许无 PlayerController 上下文初始化 |

**引入背景：**

UE5 UMG Widget Preview 功能需要在无游戏运行环境下预览 Widget，该标记允许 Widget 在编辑器预览模式下初始化。

源码位置:
- WidgetBlueprint.h:256
- WidgetBlueprintGeneratedClass.h:114

### WidgetBlueprintGeneratedClassExtension

| 字段 | 用途 |
|------|------|
| Extensions | 扩展数组，支持自定义 WBPGC 扩展 |

**引入背景：**

UE5 提供扩展机制，允许插件/项目添加自定义 Widget Blueprint 编译产物，如额外的绑定类型、动画处理器等。

源码位置: WidgetBlueprintGeneratedClass.h:95-96

---

## Part D: 版本号汇总

### UMG 相关 ObjectVersion

| 版本号 | 版本名 | 说明 |
|--------|--------|------|
| 486 | VER_UE4_DEPRECATE_UMG_STYLE_ASSETS | UMG 样式资产废弃 |
| 527 | VER_UE4_RENAME_WIDGET_VISIBILITY | Widget 可见性重命名 |
| 533 | VER_UE4_ADD_PIVOT_TO_WIDGET_COMPONENT | Widget 组件 Pivot |
| 577 | VER_UE4_DEPRECATE_UMG_STYLE_OVERRIDES | UMG 样式覆盖废弃 |
| 584 | VER_UE4_GRAPH_INTERACTIVE_COMMENTBUBBLES | 图表交互注释气泡 |

### UE5 CustomVersion

| 版本 | 版本名 | 说明 |
|------|--------|------|
| 1012 | PROPERTY_TAG_COMPLETE_TYPE_NAME | 属性标签类型名系统（Binding 序列化影响） |
| 1011 | PROPERTY_TAG_EXTENSION_AND_OVERRIDABLE_SERIALIZATION | 属性扩展机制 |

---

## Part E: 交叉引用

### Blueprint 版本文档交叉引用

| 文档 | 相关内容 |
|------|----------|
| [asset-blueprint.md](asset-blueprint.md) | Blueprint 版本差异对比 |
| [ue4-evolution.md](ue4-evolution.md) | UE4 版本演进总览 |
| [ue5-evolution.md](ue5-evolution.md) | UE5 版本演进总览 |

### Material 版本文档交叉引用

| 文档 | 相关内容 |
|------|----------|
| [asset-material.md](asset-material.md) | Material 版本差异（Widget Material 引用） |

Widget 通过 UImage 引用 Material，Material 版本变更可能影响 Widget 渲染行为。

---

## 源码引用

| 文件路径 | 说明 |
|----------|------|
| Runtime/UMG/Public/Animation/WidgetAnimation.h | UWidgetAnimation 定义 |
| Runtime/UMG/Public/Animation/WidgetAnimationBinding.h | FWidgetAnimationBinding 定义 |
| Editor/UMGEditor/Public/WidgetBlueprint.h | UWidgetBlueprint 版本相关字段 |
| Runtime/UMG/Public/Blueprint/WidgetBlueprintGeneratedClass.h | WBPGC 版本相关字段 |
| Runtime/UMG/Public/Components/NamedSlot.h | UNamedSlot bExposeOnInstanceOnly |
| Runtime/Core/Public/UObject/ObjectVersion.h | 版本号定义 |

---

*文档创建: Phase 09-UI/UMG*
*源码路径: 相对引用 UE Engine 目录*
*Updated: 2026-06-01 — 基于 UE ObjectVersion.h 完整枚举同步 UMG 相关版本号与版本名*
