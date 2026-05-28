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
| Bindings | TArray<FDelegateEditorBinding> | 编辑器属性绑定数组 | WidgetBlueprint.h:228 |
| Animations | TArray<TObjectPtr<UWidgetAnimation>> | Widget 动画数组 | WidgetBlueprint.h:230 |
| WidgetVariableNameToGuidMap | TMap<FName, FGuid> | Widget/Animation 变量 GUID 映射，用于重命名追踪 | WidgetBlueprint.h:241 |
| PaletteCategory | FString | 调色板分类 (AssetRegistrySearchable) | WidgetBlueprint.h:248 |
| bCanCallInitializedWithoutPlayerContext | bool | 无 PlayerContext 初始化标记 | WidgetBlueprint.h:256 |
| TickFrequency | EWidgetTickFrequency | Tick 频率设置 (AssetRegistrySearchable) | WidgetBlueprint.h:348 |
| TickPrediction | EWidgetCompileTimeTickPrediction | 编译时 Tick 预测 (AssetRegistrySearchable) | WidgetBlueprint.h:355 |
| TickPredictionReason | FString | Tick 预测原因描述 (AssetRegistrySearchable) | WidgetBlueprint.h:361 |
| PropertyBindings | int32 | 属性绑定数量 (AssetRegistrySearchable) | WidgetBlueprint.h:369 |

注: WITH_EDITORONLY_DATA 宏控制字段可见性，非编辑器构建不包含这些字段。

### 特殊行为

| 方法/标志 | 用途 | 源码位置 |
|-----------|------|----------|
| AlwaysCompileOnLoad() | 总是编译加载，Widget Blueprint 不允许 Data-Only 模式 | WidgetBlueprint.h:305 |
| GetInheritedAvailableNamedSlots() | 获取父类可用 NamedSlot | WidgetBlueprint.h:328 |
| GetInheritedNamedSlotsWithContentInSameTree() | 获取父类已填充 NamedSlot | WidgetBlueprint.h:330 |

### Tick 预测枚举

| 枚举值 | 说明 | 源码位置 |
|--------|------|----------|
| WontTick | 无动画/延迟动作/脚本 Tick | WidgetBlueprint.h:206 |
| OnDemand | 有动画/延迟动作，无脚本 Tick | WidgetBlueprint.h:210 |
| WillTick | 有脚本 Tick 或 Native Tick | WidgetBlueprint.h:213 |

---

## Part B: FDelegateEditorBinding 结构

### 概述

FDelegateEditorBinding 是编辑器属性绑定结构，存储 Widget 属性与 Blueprint 函数/属性的绑定关系。编译时转换为 FDelegateRuntimeBinding。

### 字段表

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| ObjectName | FString | 目标 Widget 名称 | WidgetBlueprint.h:136 |
| PropertyName | FName | 绑定的 Widget 属性名 | WidgetBlueprint.h:139 |
| FunctionName | FName | 生成的 Getter 函数名 | WidgetBlueprint.h:142 |
| SourceProperty | FName | 源属性名 | WidgetBlueprint.h:145 |
| SourcePath | FEditorPropertyPath | 属性路径 (Segments 数组) | WidgetBlueprint.h:152 |
| MemberGuid | FGuid | 函数图 GUID，处理重命名 | WidgetBlueprint.h:155 |
| Kind | EBindingKind | 绑定类型 (Function/Property) | WidgetBlueprint.h:159 |

源码位置: WidgetBlueprint.h:130-176

### FEditorPropertyPath 结构

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| Segments | TArray<FEditorPropertyPathSegment> | 属性路径段数组 | WidgetBlueprint.h:126 |

### FEditorPropertyPathSegment 结构

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| Struct | TObjectPtr<UStruct> | 路径段所属结构 | WidgetBlueprint.h:73 |
| MemberName | FName | 成员名称 | WidgetBlueprint.h:77 |
| MemberGuid | FGuid | 成员 GUID，处理重命名 | WidgetBlueprint.h:82 |
| IsProperty | bool | true=属性，false=函数 | WidgetBlueprint.h:88 |

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
| WidgetTree | TObjectPtr<UWidgetTree> | WidgetTree 原型 (DuplicateTransient) | WidgetBlueprintGeneratedClass.h:91 |
| Extensions | TArray<TObjectPtr<UWidgetBlueprintGeneratedClassExtension>> | 扩展数组 | WidgetBlueprintGeneratedClass.h:95 |
| bClassRequiresNativeTick | uint32:1 | Native Tick 标记 | WidgetBlueprintGeneratedClass.h:99 |
| bCanCallInitializedWithoutPlayerContext | uint32:1 | 无 PlayerContext 初始化标记 | WidgetBlueprintGeneratedClass.h:114 |
| Bindings | TArray<FDelegateRuntimeBinding> | 运行时绑定数组 | WidgetBlueprintGeneratedClass.h:118 |
| Animations | TArray<TObjectPtr<UWidgetAnimation>> | 动画数组 | WidgetBlueprintGeneratedClass.h:121 |
| NamedSlots | TArray<FName> | 所有 NamedSlot 名称 | WidgetBlueprintGeneratedClass.h:127 |
| AvailableNamedSlots | TArray<FName> | 可用 NamedSlot (AssetRegistrySearchable) | WidgetBlueprintGeneratedClass.h:146 |
| InstanceNamedSlots | TArray<FName> | 实例 NamedSlot | WidgetBlueprintGeneratedClass.h:155 |

### 编辑器专用字段 (WITH_EDITORONLY_DATA)

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| bCanCallPreConstruct | uint32:1 | 可调用 PreConstruct 标记 (Transient) | WidgetBlueprintGeneratedClass.h:105 |
| NamedSlotsWithID | TMap<FName, FGuid> | NamedSlot GUID 映射 | WidgetBlueprintGeneratedClass.h:132 |
| NamedSlotsWithContentInSameTree | TSet<FName> | 已填充 NamedSlot (Transient) | WidgetBlueprintGeneratedClass.h:135 |
| NameClashingInHierarchy | TSet<FName> | 层级名称冲突 (Transient) | WidgetBlueprintGeneratedClass.h:138 |

### 核心方法

| 方法 | 用途 | 源码位置 |
|------|------|----------|
| InitializeWidget() | Widget 初始化时应用绑定和动画 | WidgetBlueprintGeneratedClass.h:186 |
| GetWidgetTreeArchetype() | 获取 WidgetTree 原型 | WidgetBlueprintGeneratedClass.h:159 |
| GetNamedSlotArchetypeContent() | 获取 NamedSlot 原型内容 | WidgetBlueprintGeneratedClass.h:162 |
| FindWidgetTreeOwningClass() | 查找 WidgetTree 所属类 | WidgetBlueprintGeneratedClass.h:165 |

---

## Part D: FDelegateRuntimeBinding 结构

### 概述

FDelegateRuntimeBinding 是运行时属性绑定结构，由 FDelegateEditorBinding 编译转换生成。

### 字段表

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| ObjectName | FString | 目标 Widget 名称 | WidgetBlueprintGeneratedClass.h:34 |
| PropertyName | FName | 绑定的 Widget 属性名 | WidgetBlueprintGeneratedClass.h:38 |
| FunctionName | FName | 函数/属性名 | WidgetBlueprintGeneratedClass.h:42 |
| SourcePath | FDynamicPropertyPath | 动态属性路径 | WidgetBlueprintGeneratedClass.h:46 |
| Kind | EBindingKind | 绑定类型 | WidgetBlueprintGeneratedClass.h:50 |

源码位置: WidgetBlueprintGeneratedClass.h:28-52

### EBindingKind 枚举

| 枚举值 | 说明 | 源码位置 |
|--------|------|----------|
| Function | 函数绑定 | WidgetBlueprintGeneratedClass.h:23 |
| Property | 属性绑定 | WidgetBlueprintGeneratedClass.h:24 |

---

## Part E: UWidgetTree 序列化

### 概述

UWidgetTree 是 Widget 层级容器，实现 INamedSlotInterface 接口，存储 Widget 设计原型。运行时通过 DuplicateAndInitializeFromWidgetTree() 复制到 UUserWidget 实例。

### 字段表

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| RootWidget | TObjectPtr<UWidget> (Instanced) | 根 Widget | WidgetTree.h:141 |
| NamedSlotBindings | TMap<FName, TObjectPtr<UWidget>> | NamedSlot 内容映射 | WidgetTree.h:149 |

### 编辑器专用字段 (WITH_EDITORONLY_DATA)

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| AllWidgets | TArray<TObjectPtr<UWidget>> (Instanced) | 所有 Widget 缓存 | WidgetTree.h:155 |

源码位置: WidgetTree.h:17-158

### INamedSlotInterface 实现

| 方法 | 用途 | 源码位置 |
|------|------|----------|
| GetSlotNames() | 获取所有 Slot 名称 | WidgetTree.h:124 |
| GetContentForSlot() | 获取 Slot 内容 | WidgetTree.h:127 |
| SetContentForSlot() | 设置 Slot 内容 | WidgetTree.h:130 |

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
| Editor/UMGEditor/Public/WidgetBlueprint.h | UWidgetBlueprint、FDelegateEditorBinding、FEditorPropertyPath 定义 |
| Runtime/UMG/Public/Blueprint/WidgetBlueprintGeneratedClass.h | UWidgetBlueprintGeneratedClass、FDelegateRuntimeBinding、EBindingKind 定义 |
| Runtime/UMG/Public/Blueprint/WidgetTree.h | UWidgetTree、INamedSlotInterface 实现 |
| Runtime/UMG/Public/Blueprint/UserWidget.h | UUserWidget、FNamedSlotBinding 定义 |
| Runtime/UMG/Public/Animation/WidgetAnimation.h | UWidgetAnimation 定义 |
| Runtime/UMG/Public/Components/NamedSlot.h | UNamedSlot 定义 |

---

## 版本差异

详见: [asset-widget.md](../version/asset-widget.md)

---
*文档创建: Phase 09-UI/UMG*
*源码路径: 相对引用 UE Engine 目录*