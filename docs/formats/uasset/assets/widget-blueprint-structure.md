# Widget Blueprint 结构 (编辑器 + 运行时)

## 概述

本文档详细描述 UWidgetBlueprint 编辑器结构和 UWidgetBlueprintGeneratedClass 运行时结构，以及相关辅助结构 FDelegateEditorBinding、FDelegateRuntimeBinding、UWidgetTree 等。

---

## Part A: 编辑器结构 (UWidgetBlueprint)

### 继承关系

```
UObject
└── UBlueprint (蓝图基类)
    └── UBaseWidgetBlueprint (Widget Blueprint 基类)
        └── UWidgetBlueprint (编辑器 Widget Blueprint)
```

源码位置:
- WidgetBlueprint.h:220 — `class UWidgetBlueprint : public UBaseWidgetBlueprint`

### 字段表

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| Bindings | TArray&lt;FDelegateEditorBinding&gt; | 编辑器属性绑定数组 | WidgetBlueprint.h:228 |
| Animations | TArray&lt;TObjectPtr&lt;UWidgetAnimation&gt;&gt; | Widget 动画数组 | WidgetBlueprint.h:231 |
| WidgetVariableNameToGuidMap | TMap&lt;FName, FGuid&gt; | Widget/Animation 变量 GUID 映射，用于重命名追踪 | WidgetBlueprint.h:241 |
| PaletteCategory | FString (AssetRegistrySearchable) | 调色板分类 | WidgetBlueprint.h:248 |
| bCanCallInitializedWithoutPlayerContext | bool | 无 PlayerContext 初始化标记 | WidgetBlueprint.h:257 |
| TickFrequency | EWidgetTickFrequency (AssetRegistrySearchable) | Tick 频率设置 | WidgetBlueprint.h:349 |
| TickPrediction | EWidgetCompileTimeTickPrediction (AssetRegistrySearchable) | 编译时 Tick 预测 | WidgetBlueprint.h:356 |
| TickPredictionReason | FString (AssetRegistrySearchable) | Tick 预测原因描述 | WidgetBlueprint.h:362 |
| PropertyBindings | int32 (AssetRegistrySearchable) | 属性绑定数量 | WidgetBlueprint.h:370 |
| ThumbnailSizeMode | EThumbnailPreviewSizeMode | 缩略图大小模式 | WidgetBlueprint.h:373 |
| ThumbnailCustomSize | FVector2D | 自定义缩略图尺寸 | WidgetBlueprint.h:376 |
| ThumbnailImage | TObjectPtr&lt;UTexture2D&gt; | 缩略图图像 | WidgetBlueprint.h:379 |

注: Bindings、Animations、WidgetVariableNameToGuidMap、PaletteCategory、bCanCallInitializedWithoutPlayerContext 受 `WITH_EDITORONLY_DATA` 宏控制。TickFrequency、TickPrediction、TickPredictionReason、PropertyBindings 在 private 段，非编辑器构建仍包含。

### EWidgetCompileTimeTickPrediction 枚举

编译时计算出的 Widget Tick 能力预测：

| 枚举值 | 说明 | 源码位置 |
|--------|------|----------|
| WontTick | 手动设置为不 Tick，或未检测到动画/延迟动作/脚本 Tick/Native Tick | WidgetBlueprint.h:207 |
| OnDemand | 自动 Tick，检测到动画/延迟动作，但无脚本或 Native Tick | WidgetBlueprint.h:210 |
| WillTick | 已实现脚本 Tick 或 Native Tick | WidgetBlueprint.h:213 |

注: `EWidgetTickFrequency` 在头文件中仅为前向声明 (`enum class EWidgetTickFrequency : uint8`)，实际定义在其它头文件中。

### EThumbnailPreviewSizeMode 枚举

| 枚举值 | 说明 |
|--------|------|
| MatchDesignerMode | 匹配设计器模式 |
| FillScreen | 填充屏幕 |
| Custom | 自定义 |
| Desired | 期望尺寸 |

### FWidgetBlueprintDelegates 代理结构

| 代理 | 用途 | 源码位置 |
|------|------|----------|
| FGetAssetTagsWithContext | 生成资产注册表标签（带上下文） | WidgetBlueprint.h:38 |
| FGetAssetTags | 生成资产注册表标签（5.4 已废弃，订阅 GetAssetTagsWithContext 代替） | WidgetBlueprint.h:39-44 |

### 特殊行为

| 方法/标志 | 用途 | 源码位置 |
|-----------|------|----------|
| AlwaysCompileOnLoad() | 总是编译加载，Widget Blueprint 不允许 Data-Only 模式 | WidgetBlueprint.h:305 |
| GetInheritedAvailableNamedSlots() | 获取父类可用 NamedSlot | WidgetBlueprint.h:328 |
| GetInheritedNamedSlotsWithContentInSameTree() | 获取父类已填充 NamedSlot | WidgetBlueprint.h:331 |
| OnVariableAdded(VariableName) | 变量添加时更新 GUID 映射 | WidgetBlueprint.h:259 |
| OnVariableRenamed(OldName, NewName) | 变量重命名时更新 GUID 映射 | WidgetBlueprint.h:260 |
| OnVariableRemoved(VariableName) | 变量移除时更新 GUID 映射 | WidgetBlueprint.h:261 |
| UpdateTickabilityStats() | 更新 Tick 能力统计 | WidgetBlueprint.h:323 |
| HasCircularReferences() | 检查循环引用 | WidgetBlueprint.h:314 |
| HasConflictingWidgetNamesFromInheritance() | 检查继承名称冲突 | WidgetBlueprint.h:316 |

---

## Part B: FDelegateEditorBinding 结构

### 概述

FDelegateEditorBinding 是编辑器属性绑定结构，存储 Widget 属性与 Blueprint 函数/属性的绑定关系。编译时通过 `ToRuntimeBinding()` 转换为 FDelegateRuntimeBinding。

### 字段表

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| ObjectName | FString | 目标 Widget 名称（必须是 UUserWidget 的直接变量） | WidgetBlueprint.h:137 |
| PropertyName | FName | 绑定的 Widget 属性名 | WidgetBlueprint.h:141 |
| FunctionName | FName | 生成的 Getter 函数名 | WidgetBlueprint.h:145 |
| SourceProperty | FName | 源属性名（直接绑定到源对象） | WidgetBlueprint.h:149 |
| SourcePath | FEditorPropertyPath | 属性路径（Segments 数组） | WidgetBlueprint.h:153 |
| MemberGuid | FGuid | 函数图 GUID，处理重命名 | WidgetBlueprint.h:157 |
| Kind | EBindingKind | 绑定类型（Function/Property），默认 Property | WidgetBlueprint.h:160 |

源码位置: WidgetBlueprint.h:130-176

### FEditorPropertyPath 结构

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| Segments | TArray&lt;FEditorPropertyPathSegment&gt; | 属性路径段数组 | WidgetBlueprint.h:126 |

### FEditorPropertyPathSegment 结构

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| Struct | TObjectPtr&lt;UStruct&gt; | 路径段所属结构 | WidgetBlueprint.h:74 |
| MemberName | FName | 成员名称 | WidgetBlueprint.h:78 |
| MemberGuid | FGuid | 成员 GUID，处理重命名 | WidgetBlueprint.h:85 |
| IsProperty | bool | true=属性，false=函数 | WidgetBlueprint.h:89 |

源码位置: WidgetBlueprint.h:49-90

---

## Part C: 运行时结构 (UWidgetBlueprintGeneratedClass)

### 继承关系

```
UObject
└── UField
    └── UStruct
        └── UClass
            └── UBlueprintGeneratedClass (蓝图生成类)
                └── UWidgetBlueprintGeneratedClass (Widget 生成类)
```

源码位置:
- WidgetBlueprintGeneratedClass.h:80 — `class UWidgetBlueprintGeneratedClass : public UBlueprintGeneratedClass`

### 字段表

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| WidgetTree | TObjectPtr&lt;UWidgetTree&gt; (DuplicateTransient) | WidgetTree 原型 | WidgetBlueprintGeneratedClass.h:92 |
| Extensions | TArray&lt;TObjectPtr&lt;UWidgetBlueprintGeneratedClassExtension&gt;&gt; | 扩展数组 | WidgetBlueprintGeneratedClass.h:96 |
| bClassRequiresNativeTick | uint32:1 | Native Tick 标记 | WidgetBlueprintGeneratedClass.h:100 |
| bCanCallInitializedWithoutPlayerContext | uint32:1 | 无 PlayerContext 初始化标记 | WidgetBlueprintGeneratedClass.h:115 |
| Bindings | TArray&lt;FDelegateRuntimeBinding&gt; | 运行时绑定数组 | WidgetBlueprintGeneratedClass.h:118 |
| Animations | TArray&lt;TObjectPtr&lt;UWidgetAnimation&gt;&gt; | 动画数组 | WidgetBlueprintGeneratedClass.h:121 |
| NamedSlots | TArray&lt;FName&gt; | 所有 NamedSlot 名称（含已被父类填充的） | WidgetBlueprintGeneratedClass.h:128 |
| AvailableNamedSlots | TArray&lt;FName&gt; (AssetRegistrySearchable) | 可用 NamedSlot（排除已被父类填充的） | WidgetBlueprintGeneratedClass.h:147 |
| InstanceNamedSlots | TArray&lt;FName&gt; | 实例 NamedSlot（含 bExposeOnInstanceOnly 的继承槽） | WidgetBlueprintGeneratedClass.h:156 |

### 编辑器专用字段 (WITH_EDITORONLY_DATA)

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| bCanCallPreConstruct | uint32:1 (Transient) | 可调用 PreConstruct 标记 | WidgetBlueprintGeneratedClass.h:105 |
| NamedSlotsWithID | TMap&lt;FName, FGuid&gt; | NamedSlot GUID 映射 | WidgetBlueprintGeneratedClass.h:133 |
| NamedSlotsWithContentInSameTree | TSet&lt;FName&gt; (Transient) | 已填充 NamedSlot | WidgetBlueprintGeneratedClass.h:136 |
| NameClashingInHierarchy | TSet&lt;FName&gt; (Transient) | 层级名称冲突 | WidgetBlueprintGeneratedClass.h:139 |

### FWidgetBlueprintGeneratedClassDelegates 代理结构 (WITH_EDITOR)

| 代理 | 用途 | 源码位置 |
|------|------|----------|
| FGetAssetTagsWithContext | 生成资产注册表标签 | WidgetBlueprintGeneratedClass.h:60 |
| FCollectSaveOverrides | 收集保存覆盖 | WidgetBlueprintGeneratedClass.h:62 |
| FGetAssetTags | 旧版标签代理（5.4 已废弃） | WidgetBlueprintGeneratedClass.h:69 |

### 核心方法

| 方法 | 用途 | 源码位置 |
|------|------|----------|
| InitializeWidget() | Widget 初始化时应用绑定和动画 | WidgetBlueprintGeneratedClass.h:186 |
| InitializeWidgetStatic() | 静态版本：初始化 Widget（支持外部传入参数） | WidgetBlueprintGeneratedClass.h:188-193 |
| GetWidgetTreeArchetype() | 获取 WidgetTree 原型 | WidgetBlueprintGeneratedClass.h:159 |
| SetWidgetTreeArchetype() | 设置 WidgetTree 原型 | WidgetBlueprintGeneratedClass.h:160 |
| GetNamedSlotArchetypeContent() | 获取 NamedSlot 原型内容 | WidgetBlueprintGeneratedClass.h:162 |
| FindWidgetTreeOwningClass() | 查找 WidgetTree 所属类 | WidgetBlueprintGeneratedClass.h:165 |
| GetExtension&lt;T&gt;() | 获取指定类型的扩展 | WidgetBlueprintGeneratedClass.h:202-209 |
| ForEachExtension() | 遍历所有扩展（含父类） | WidgetBlueprintGeneratedClass.h:214-229 |
| ClassRequiresNativeTick() | 查询是否需要 Native Tick | WidgetBlueprintGeneratedClass.h:195 |

---

## Part D: FDelegateRuntimeBinding 结构

### 概述

FDelegateRuntimeBinding 是运行时属性绑定结构，由 FDelegateEditorBinding 编译转换生成。

### 字段表

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| ObjectName | FString | 目标 Widget 名称 | WidgetBlueprintGeneratedClass.h:35 |
| PropertyName | FName | 绑定的 Widget 属性名 | WidgetBlueprintGeneratedClass.h:39 |
| FunctionName | FName | 函数/属性名 | WidgetBlueprintGeneratedClass.h:43 |
| SourcePath | FDynamicPropertyPath | 动态属性路径 | WidgetBlueprintGeneratedClass.h:47 |
| Kind | EBindingKind | 绑定类型，默认 Property | WidgetBlueprintGeneratedClass.h:51 |

源码位置: WidgetBlueprintGeneratedClass.h:28-52

### EBindingKind 枚举

| 枚举值 | 说明 | 源码位置 |
|--------|------|----------|
| Function | 函数绑定 | WidgetBlueprintGeneratedClass.h:24 |
| Property | 属性绑定（默认值） | WidgetBlueprintGeneratedClass.h:25 |

---

## Part E: UWidgetTree 序列化

### 概述

UWidgetTree 是 Widget 层级容器，继承自 UObject 并实现 INamedSlotInterface 接口，存储 Widget 设计原型。运行时通过 DuplicateAndInitializeFromWidgetTree() 复制到 UUserWidget 实例。

### 字段表

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| RootWidget | TObjectPtr&lt;UWidget&gt; (Instanced) | 根 Widget | WidgetTree.h:142 |
| NamedSlotBindings | TMap&lt;FName, TObjectPtr&lt;UWidget&gt;&gt; | NamedSlot 内容映射 | WidgetTree.h:150 |

### 编辑器专用字段 (WITH_EDITORONLY_DATA)

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| AllWidgets | TArray&lt;TObjectPtr&lt;UWidget&gt;&gt; (Instanced) | 所有 Widget 缓存 | WidgetTree.h:156 |

源码位置: WidgetTree.h:17-158

### INamedSlotInterface 实现

| 方法 | 用途 | 源码位置 |
|------|------|----------|
| GetSlotNames() | 获取所有 Slot 名称 | WidgetTree.h:124 |
| GetContentForSlot() | 获取 Slot 内容 | WidgetTree.h:127 |
| SetContentForSlot() | 设置 Slot 内容 | WidgetTree.h:130 |

### 核心工具方法

| 方法 | 用途 | 源码位置 |
|------|------|----------|
| FindWidget(Name) | 按名称查找 Widget | WidgetTree.h:30 |
| FindWidget(SWidget) | 按原生 Widget 查找 | WidgetTree.h:33 |
| RemoveWidget() | 从层级中移除 Widget | WidgetTree.h:43 |
| FindWidgetParent() | 查找父 Widget | WidgetTree.h:46 |
| FindWidgetChild() | 递归查找子 Widget | WidgetTree.h:52 |
| FindChildIndex() | 确定子 Widget 索引 | WidgetTree.h:58 |
| GetAllWidgets() | 递归收集所有 Widget | WidgetTree.h:61 |
| GetChildWidgets() | 收集子 Widget | WidgetTree.h:64 |
| TryMoveWidgetToNewTree() | 移动 Widget 到新树 | WidgetTree.h:67 |
| ForEachWidget() | 遍历所有 Widget（含 NamedSlot） | WidgetTree.h:74 |
| ForEachWidgetAndDescendants() | 遍历所有 Widget（含外部 WidgetTree） | WidgetTree.h:80 |
| ConstructWidget&lt;T&gt;() | 构造 Widget 并添加到树 | WidgetTree.h:102-118 |

### Widget 属性序列化

WidgetTree 中的 Widget 使用标准 UPROPERTY 标签系统序列化，详见 [property-tag.md](../serialization/property-tag.md)。Instanced 标记确保子对象作为内嵌对象序列化。

---

## Part F: Widget 类型目录

### 基础 Widget

| 类名 | 说明 | 源码路径 |
|------|------|----------|
| UWidget | Widget 基类 | Runtime/UMG/Public/Components/Widget.h |
| UUserWidget | 用户 Widget (Blueprint 可继承) | Runtime/UMG/Public/Blueprint/UserWidget.h |
| UVisual | Visual 基类 (无交互) | Runtime/UMG/Public/Components/Visual.h |

### 容器 Widget (UPanelWidget 子类)

| 类名 | 说明 | 源码路径 |
|------|------|----------|
| UPanelWidget | 面板基类 | Runtime/UMG/Public/Components/PanelWidget.h |
| UCanvasPanel | 画布面板 (自由定位) | Runtime/UMG/Public/Components/CanvasPanel.h |
| UHorizontalBox | 水平盒子 | Runtime/UMG/Public/Components/HorizontalBox.h |
| UVerticalBox | 垂直盒子 | Runtime/UMG/Public/Components/VerticalBox.h |
| UGridPanel | 网格面板 | Runtime/UMG/Public/Components/GridPanel.h |
| UOverlay | 重叠层 | Runtime/UMG/Public/Components/Overlay.h |
| UBorder | 边框 | Runtime/UMG/Public/Components/Border.h |
| UNamedSlot | 命名插槽 (继承机制核心) | Runtime/UMG/Public/Components/NamedSlot.h |
| USizeBox | 尺寸盒子 | Runtime/UMG/Public/Components/SizeBox.h |
| UScaleBox | 缩放盒子 | Runtime/UMG/Public/Components/ScaleBox.h |

### 交互 Widget

| 类名 | 说明 | 源码路径 |
|------|------|----------|
| UButton | 按钮 | Runtime/UMG/Public/Components/Button.h |
| UCheckBox | 复选框 | Runtime/UMG/Public/Components/CheckBox.h |
| UComboBox | 组合框基类 | Runtime/UMG/Public/Components/ComboBox.h |
| UComboBoxString | 字符串组合框 | Runtime/UMG/Public/Components/ComboBoxString.h |
| UEditableText | 可编辑文本 | Runtime/UMG/Public/Components/EditableText.h |
| UEditableTextBox | 可编辑文本框 | Runtime/UMG/Public/Components/EditableTextBox.h |
| UMultiLineEditableText | 多行可编辑文本 | Runtime/UMG/Public/Components/MultiLineEditableText.h |
| USlider | 滑块 | Runtime/UMG/Public/Components/Slider.h |
| USpinBox | 数值框 | Runtime/UMG/Public/Components/SpinBox.h |

### 显示 Widget

| 类名 | 说明 | 源码路径 |
|------|------|----------|
| UImage | 图片 (可引用 Material) | Runtime/UMG/Public/Components/Image.h |
| UTextBlock | 文本块 | Runtime/UMG/Public/Components/TextBlock.h |
| URichTextBlock | 富文本块 | Runtime/UMG/Public/Components/RichTextBlock.h |
| UProgressBar | 进度条 | Runtime/UMG/Public/Components/ProgressBar.h |
| UCircularThrobber | 圆形加载指示器 | Runtime/UMG/Public/Components/CircularThrobber.h |
| USpacer | 空白间隔 | Runtime/UMG/Public/Components/Spacer.h |
| UExpandableArea | 可展开区域 | Runtime/UMG/Public/Components/ExpandableArea.h |

### 高级 Widget

| 类名 | 说明 | 源码路径 |
|------|------|----------|
| UListView | 列表视图 | Runtime/UMG/Public/Components/ListView.h |
| UDynamicEntryBox | 动态条目盒 | Runtime/UMG/Public/Components/DynamicEntryBox.h |
| UInvalidationBox | 无效化盒 (性能优化) | Runtime/UMG/Public/Components/InvalidationBox.h |
| URetainerBox | 保持盒 (渲染缓存) | Runtime/UMG/Public/Components/RetainerBox.h |
| UBackgroundBlur | 背景模糊 | Runtime/UMG/Public/Components/BackgroundBlur.h |
| UWrapBox | 自动换行盒 | Runtime/UMG/Public/Components/WrapBox.h |

---

## Part G: 交叉引用

### Blueprint 文档交叉引用

Widget Blueprint 继承 Blueprint 的编辑器/运行时分离模式：

| 特性 | Blueprint | Widget Blueprint |
|------|-----------|------------------|
| 编辑器类 | UBlueprint | UWidgetBlueprint |
| 运行时类 | UBlueprintGeneratedClass | UWidgetBlueprintGeneratedClass |
| 编译产物 | 字节码 + 组件模板 | WidgetTree + Bindings + 动画 |
| 继承机制 | 父类 Blueprint 合并 | 父类 WidgetTree + NamedSlot 合并 |

详见:
- [blueprint.md](blueprint.md) — Blueprint 导航文档
- [blueprint-generated-class.md](blueprint-generated-class.md) — Blueprint 生成类结构

### Material 文档交叉引用

Widget 通过 UImage 引用 Material：

| 字段路径 | 说明 |
|----------|------|
| UImage.WidgetStyle.Brush | FSlateBrush 画刷结构 |
| FSlateBrush.ResourceObject | UObject 资源引用 |
| ResourceObject → UMaterial/UMaterialInstance | 材质引用 |

详见: [material.md](material.md)

### 序列化基础设施交叉引用

| 文档 | 用途 |
|------|------|
| [property-tag.md](../serialization/property-tag.md) | Widget 属性标签序列化 |
| [linker-load.md](../serialization/linker-load.md) | WidgetTree 加载流程 |
| [bulkdata.md](../serialization/bulkdata.md) | 大型 WidgetTree 嵌入数据 |

---

## 源码引用

| 文件路径 | 说明 |
|----------|------|
| Editor/UMGEditor/Public/WidgetBlueprint.h | UWidgetBlueprint、FDelegateEditorBinding、FEditorPropertyPath、FEditorPropertyPathSegment、FWidgetBlueprintDelegates 定义 |
| Runtime/UMG/Public/Blueprint/WidgetBlueprintGeneratedClass.h | UWidgetBlueprintGeneratedClass、FDelegateRuntimeBinding、EBindingKind、FWidgetBlueprintGeneratedClassDelegates 定义 |
| Runtime/UMG/Public/Blueprint/WidgetTree.h | UWidgetTree、INamedSlotInterface 实现 |
| Runtime/UMG/Public/Blueprint/UserWidget.h | UUserWidget、FNamedSlotBinding 定义 |
| Runtime/UMG/Public/Animation/WidgetAnimation.h | UWidgetAnimation 定义 |
| Runtime/UMG/Public/Components/NamedSlot.h | UNamedSlot 定义 |
| Runtime/UMG/Public/Binding/DynamicPropertyPath.h | FDynamicPropertyPath 定义 |

---

## 版本差异

详见: [asset-widget.md](../version/asset-widget.md)

---
*文档创建: Phase 09-UI/UMG*
*文档版本: v1.2 | 最后更新: 2026-06-01 | 源码验证: UE5 源码 (WidgetBlueprint.h / WidgetBlueprintGeneratedClass.h / WidgetTree.h)*
*源码路径: 相对引用 UE Engine 目录*
