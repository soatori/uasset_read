# Widget Blueprint 资产文档

Widget Blueprint 资产类型 (UWidgetBlueprint/UWidgetBlueprintGeneratedClass) 相关文档导航。

## 概述

UMG (Unreal Motion Graphics) 是 Unreal Engine 的 UI 框架，通过 Widget Blueprint 实现可视化 UI 设计。Widget Blueprint 采用与普通 Blueprint 相似的编辑器/运行时分离模式：

- **UWidgetBlueprint** (Editor) — 编辑器资产，存储 WidgetTree 设计、属性绑定和动画定义
- **UWidgetBlueprintGeneratedClass** (Runtime) — 运行时生成类，存储编译后的 WidgetTree 原型、运行时绑定和动画引用

该分离模式与普通 Blueprint 的 UBlueprint/UBlueprintGeneratedClass 分离模式类似，但增加了 WidgetTree 和 NamedSlot 继承等 UMG 特有机制。

## 继承链

```
Blueprint:
UBlueprint → UBlueprintGeneratedClass

Widget Blueprint:
UBlueprint → UUserWidgetBlueprint → UBaseWidgetBlueprint → UWidgetBlueprint → UWidgetBlueprintGeneratedClass
```

- **UUserWidgetBlueprint** (Runtime/UMG/Public/Blueprint/UserWidgetBlueprint.h) — UBlueprint 的直接子类，提供 UMG 特有虚函数（AllowEditorWidget、ShouldAutomaticallyRegisterInputOnConstruction）
- **UBaseWidgetBlueprint** (Editor/UnrealEd/Public/BaseWidgetBlueprint.h) — 编辑器基类，持有编辑器用 WidgetTree（WITH_EDITORONLY_DATA）
- **UWidgetBlueprint** (Editor/UMGEditor/Public/WidgetBlueprint.h) — 编辑器 Widget Blueprint，持有 Bindings、Animations 等
- **UWidgetBlueprintGeneratedClass** (Runtime/UMG/Public/Blueprint/WidgetBlueprintGeneratedClass.h) — 运行时生成类，继承 UBlueprintGeneratedClass

WidgetBlueprintGeneratedClass 直接继承 BlueprintGeneratedClass，复用其字节码、组件模板等机制，并添加 WidgetTree、Bindings、NamedSlots 等 UMG 特有字段。

---

## Part A: 编辑器结构 (UWidgetBlueprint)

### 继承关系

```
UObject
└── UBlueprint (蓝图基类)
    └── UUserWidgetBlueprint (UMG 蓝图基类)
        └── UBaseWidgetBlueprint (Widget Blueprint 编辑器基类)
            └── UWidgetBlueprint (编辑器 Widget Blueprint)
```

源码位置:
- UserWidgetBlueprint.h — `class UUserWidgetBlueprint : public UBlueprint`
- BaseWidgetBlueprint.h — `class UBaseWidgetBlueprint : public UUserWidgetBlueprint`
- WidgetBlueprint.h:220 — `class UWidgetBlueprint : public UBaseWidgetBlueprint`

### 字段表

| 字段名 | 类型 | 用途 | 宏保护 | 源码位置 |
|--------|------|------|--------|----------|
| Bindings | TArray<FDelegateEditorBinding> | 编辑器属性绑定数组 | WITH_EDITORONLY_DATA | WidgetBlueprint.h:228 |
| Animations | TArray<TObjectPtr<UWidgetAnimation>> | Widget 动画数组 | WITH_EDITORONLY_DATA | WidgetBlueprint.h:231 |
| WidgetVariableNameToGuidMap | TMap<FName, FGuid> | Widget/Animation 变量 GUID 映射，用于重命名追踪 | WITH_EDITORONLY_DATA | WidgetBlueprint.h:241 |
| PaletteCategory | FString | 调色板分类 (AssetRegistrySearchable)。注意：UUserWidget 中同名字段类型为 FText | WITH_EDITORONLY_DATA | WidgetBlueprint.h:249 |
| bCanCallInitializedWithoutPlayerContext | bool | 无 PlayerContext 初始化标记 | WITH_EDITORONLY_DATA | WidgetBlueprint.h:257 |
| TickFrequency | EWidgetTickFrequency | Tick 频率设置 (AssetRegistrySearchable) | private | WidgetBlueprint.h:349 |
| TickPrediction | EWidgetCompileTimeTickPrediction | 编译时 Tick 预测 (AssetRegistrySearchable) | private | WidgetBlueprint.h:356 |
| TickPredictionReason | FString | Tick 预测原因描述 (AssetRegistrySearchable) | private | WidgetBlueprint.h:362 |
| PropertyBindings | int32 | 属性绑定数量 (AssetRegistrySearchable) | public | WidgetBlueprint.h:370 |
| ThumbnailSizeMode | EThumbnailPreviewSizeMode | 缩略图预览尺寸模式 | public | WidgetBlueprint.h:373 |
| ThumbnailCustomSize | FVector2D | 缩略图自定义尺寸 | public | WidgetBlueprint.h:376 |
| ThumbnailImage | TObjectPtr<UTexture2D> | 缩略图自定义图片 | public | WidgetBlueprint.h:379 |

### 特殊行为

| 方法/标志 | 用途 | 源码位置 |
|-----------|------|----------|
| AlwaysCompileOnLoad() | 总是编译加载，Widget Blueprint 不允许 Data-Only 模式 | WidgetBlueprint.h:305 |
| GetInheritedAvailableNamedSlots() | 获取父类可用 NamedSlot | WidgetBlueprint.h:328 |
| GetInheritedNamedSlotsWithContentInSameTree() | 获取父类已填充 NamedSlot | WidgetBlueprint.h:331 |

### 新增枚举

| 枚举 | 值 | 说明 | 源码位置 |
|------|-----|------|----------|
| EWidgetSupportsDynamicCreation | Default, Yes, No | Widget 动态创建支持 | WidgetBlueprint.h:179-184 |
| EThumbnailPreviewSizeMode | MatchDesignerMode, FillScreen, Custom, Desired | 缩略图预览尺寸模式 | WidgetBlueprint.h:188-194 |
| EWidgetCompileTimeTickPrediction | WontTick, OnDemand, WillTick | 编译时 Tick 预测 | WidgetBlueprint.h:204-214 |

---

## Part B: FDelegateEditorBinding 结构

### 概述

FDelegateEditorBinding 是编辑器属性绑定结构，存储 Widget 属性与 Blueprint 函数/属性的绑定关系。编译时转换为 FDelegateRuntimeBinding。

### 字段表

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| ObjectName | FString | 目标 Widget 名称 | WidgetBlueprint.h:137 |
| PropertyName | FName | 绑定的 Widget 属性名 | WidgetBlueprint.h:141 |
| FunctionName | FName | 生成的 Getter 函数名 | WidgetBlueprint.h:145 |
| SourceProperty | FName | 源属性名 | WidgetBlueprint.h:149 |
| SourcePath | FEditorPropertyPath | 属性路径 (Segments 数组) | WidgetBlueprint.h:153 |
| MemberGuid | FGuid | 函数图 GUID，处理重命名 | WidgetBlueprint.h:157 |
| Kind | EBindingKind | 绑定类型 (Function/Property)，默认 Property | WidgetBlueprint.h:160 |

源码位置: WidgetBlueprint.h:130-176

### FEditorPropertyPath 结构

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| Segments | TArray<FEditorPropertyPathSegment> | 属性路径段数组 | WidgetBlueprint.h:126 |

### FEditorPropertyPathSegment 结构

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| Struct | TObjectPtr<UStruct> | 路径段所属结构 | WidgetBlueprint.h:74 |
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
| WidgetTree | TObjectPtr<UWidgetTree> | WidgetTree 原型 (DuplicateTransient) | WidgetBlueprintGeneratedClass.h:92 |
| Extensions | TArray<TObjectPtr<UWidgetBlueprintGeneratedClassExtension>> | 扩展数组 | WidgetBlueprintGeneratedClass.h:96 |
| bClassRequiresNativeTick | uint32:1 | Native Tick 标记 | WidgetBlueprintGeneratedClass.h:100 |
| bCanCallInitializedWithoutPlayerContext | uint32:1 | 无 PlayerContext 初始化标记 | WidgetBlueprintGeneratedClass.h:115 |
| Bindings | TArray<FDelegateRuntimeBinding> | 运行时绑定数组 | WidgetBlueprintGeneratedClass.h:118 |
| Animations | TArray<TObjectPtr<UWidgetAnimation>> | 动画数组 | WidgetBlueprintGeneratedClass.h:121 |
| NamedSlots | TArray<FName> | 所有 NamedSlot 名称 | WidgetBlueprintGeneratedClass.h:128 |
| AvailableNamedSlots | TArray<FName> | 可用 NamedSlot (AssetRegistrySearchable) | WidgetBlueprintGeneratedClass.h:147 |
| InstanceNamedSlots | TArray<FName> | 实例 NamedSlot | WidgetBlueprintGeneratedClass.h:156 |

### 编辑器专用字段 (WITH_EDITORONLY_DATA)

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| bCanCallPreConstruct | uint32:1 | 可调用 PreConstruct 标记 (Transient) | WidgetBlueprintGeneratedClass.h:105 |
| NamedSlotsWithID | TMap<FName, FGuid> | NamedSlot GUID 映射 | WidgetBlueprintGeneratedClass.h:133 |
| NamedSlotsWithContentInSameTree | TSet<FName> | 已填充 NamedSlot (Transient) | WidgetBlueprintGeneratedClass.h:136 |
| NameClashingInHierarchy | TSet<FName> | 层级名称冲突 (Transient) | WidgetBlueprintGeneratedClass.h:139 |

### 核心方法

| 方法 | 用途 | 源码位置 |
|------|------|----------|
| InitializeWidget() | Widget 初始化时应用绑定和动画 | WidgetBlueprintGeneratedClass.h:186 |
| InitializeWidgetStatic() | 静态版本，接受分离的参数 | WidgetBlueprintGeneratedClass.h:188 |
| GetWidgetTreeArchetype() | 获取 WidgetTree 原型 | WidgetBlueprintGeneratedClass.h:159 |
| SetWidgetTreeArchetype() | 设置 WidgetTree 原型 | WidgetBlueprintGeneratedClass.h:160 |
| GetNamedSlotArchetypeContent() | 获取 NamedSlot 原型内容 | WidgetBlueprintGeneratedClass.h:162 |
| FindWidgetTreeOwningClass() | 查找 WidgetTree 所属类 | WidgetBlueprintGeneratedClass.h:165 |
| ClassRequiresNativeTick() | 查询是否需要 Native Tick | WidgetBlueprintGeneratedClass.h:195 |
| GetExtension() | 查找指定类型的扩展 | WidgetBlueprintGeneratedClass.h:203 |
| GetExtensions() | 查找所有指定类型的扩展 | WidgetBlueprintGeneratedClass.h:212 |
| ForEachExtension() | 遍历所有扩展（含父类） | WidgetBlueprintGeneratedClass.h:215 |

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
| SourcePath | FDynamicPropertyPath | 动态属性路径（继承自 FCachedPropertyPath） | WidgetBlueprintGeneratedClass.h:47 |
| Kind | EBindingKind | 绑定类型，默认 Property | WidgetBlueprintGeneratedClass.h:51 |

源码位置: WidgetBlueprintGeneratedClass.h:28-52

### FDynamicPropertyPath 结构

FDynamicPropertyPath 继承自 FCachedPropertyPath（Binding/DynamicPropertyPath.h:18），提供模板方法 GetValue<T>() 用于运行时属性值获取。

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
| RootWidget | TObjectPtr<UWidget> (Instanced) | 根 Widget | WidgetTree.h:142 |
| NamedSlotBindings | TMap<FName, TObjectPtr<UWidget>> | NamedSlot 内容映射 | WidgetTree.h:150 |

### 编辑器专用字段 (WITH_EDITORONLY_DATA)

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| AllWidgets | TArray<TObjectPtr<UWidget>> (Instanced) | 所有 Widget 缓存 | WidgetTree.h:156 |

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

## Part F: UUserWidget 运行时结构

### 概述

UUserWidget 是用户可扩展的 Widget 基类，通过 Widget Blueprint 创建实例。实现 INamedSlotInterface 接口，管理动画播放、输入处理、NamedSlot 绑定等运行时行为。

### 继承关系

```
UObject
└── UVisual
    └── UWidget
        └── UUserWidget (实现 INamedSlotInterface)
```

源码位置:
- UserWidget.h:283 — `class UUserWidget : public UWidget, public INamedSlotInterface`

### 核心字段表

| 字段名 | 类型 | 用途 | 宏保护/弃用 | 源码位置 |
|--------|------|------|-------------|----------|
| ColorAndOpacity | FLinearColor | 颜色和透明度，影响所有子 Widget | 已弃用 5.2，改用 Getter/Setter | UserWidget.h:999 |
| ColorAndOpacityDelegate | FGetLinearColor | 颜色绑定委托 | — | UserWidget.h:1002 |
| ForegroundColor | FSlateColor | 前景色，被子 Widget 继承 | 已弃用 5.2，改用 Getter/Setter | UserWidget.h:1010 |
| ForegroundColorDelegate | FGetSlateColor | 前景色绑定委托 | — | UserWidget.h:1013 |
| OnVisibilityChanged | FOnVisibilityChangedEvent | 可见性变化事件 | — | UserWidget.h:1017 |
| Padding | FMargin | 内容周围填充 | 已弃用 5.2，改用 Getter/Setter | UserWidget.h:1027 |
| Priority | int32 | 输入动作优先级 | 已弃用 5.2，改用 Getter/Setter | UserWidget.h:1031 |
| bIsFocusable | uint8:1 | 是否可接受焦点 | 已弃用 5.2，改用 Getter/Setter | UserWidget.h:1036 |
| bStopAction | uint8:1 | 输入动作是否阻塞 | 已弃用 5.2，改用 Getter/Setter | UserWidget.h:1040 |
| bAutomaticallyRegisterInputOnConstruction | uint8:1 | 构造时自动注册输入组件（编译时设置） | — | UserWidget.h:1049 |
| QueuedWidgetAnimationTransitions | TArray<FQueuedWidgetAnimationTransition> | 动画队列转换（Transient） | — | UserWidget.h:1481 |
| ActiveSequencePlayers | TArray<TObjectPtr<UUMGSequencePlayer>> | 活动序列播放器（Transient） | 已弃用 5.6，替代为 ActiveAnimations | UserWidget.h:1485 |
| AnimationTickManager | TObjectPtr<UUMGSequenceTickManager> | 动画 Tick 管理器（Transient） | — | UserWidget.h:1489 |
| StoppedSequencePlayers | TArray<TObjectPtr<UUMGSequencePlayer>> | 已停止序列播放器（Transient） | 已弃用 5.6，替代为 ActiveAnimations | UserWidget.h:1493 |
| NamedSlotBindings | TArray<FNamedSlotBinding> | NamedSlot 绑定数组 | private | UserWidget.h:1507 |
| Extensions | TArray<TObjectPtr<UUserWidgetExtension>> | UserWidget 扩展数组 | private | UserWidget.h:1511 |
| WidgetTree | TObjectPtr<UWidgetTree> | Widget 树（Transient, DuplicateTransient, TextExportTransient） | public | UserWidget.h:1516 |
| bHasScriptImplementedTick | uint8:1 | 是否有蓝图 Tick 实现 | — | UserWidget.h:1544 |
| bHasScriptImplementedPaint | uint8:1 | 是否有蓝图 Paint 实现 | — | UserWidget.h:1548 |
| TickFrequency | EWidgetTickFrequency | Tick 频率（Never/Auto） | private, EditDefaultsOnly | UserWidget.h:1717 |
| DesiredFocusWidget | FWidgetChild | 期望焦点 Widget | private, EditDefaultsOnly | UserWidget.h:1720 |
| InputComponent | TObjectPtr<UInputComponent> | 输入组件（Transient, DuplicateTransient） | protected | UserWidget.h:1756 |
| AnimationCallbacks | TArray<FAnimationEventBinding> | 动画事件回调（Transient, DuplicateTransient） | protected | UserWidget.h:1767 |
| PlayerContext | FLocalPlayerContext | 关联的玩家上下文 | private, 非 UPROPERTY | UserWidget.h:1773 |
| MinimumDesiredSize | FVector2D | 最小期望尺寸 | private, 非 UPROPERTY | UserWidget.h:1709 |
| CachedWorld | TWeakObjectPtr<UWorld> | 缓存的 World 引用 | private, 非 UPROPERTY | UserWidget.h:1776 |

### 编辑器专用字段 (WITH_EDITORONLY_DATA)

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| DesignTimeSize | FVector2D | 设计时尺寸 | UserWidget.h:1524 |
| DesignSizeMode | EDesignPreviewSizeMode | 设计预览尺寸模式 | UserWidget.h:1527 |
| PaletteCategory | FText | 调色板分类（注意：类型为 FText，与 UWidgetBlueprint 的 FString 不同） | UserWidget.h:1531 |
| PreviewBackground | TObjectPtr<UTexture2D> | 预览背景图 | UserWidget.h:1538 |

### EWidgetTickFrequency 枚举

| 枚举值 | 说明 | 源码位置 |
|--------|------|----------|
| Never | Widget 永不 Tick | UserWidget.h:123 |
| Auto | 有蓝图 Tick/延迟动作/动画时自动 Tick，继承非 UserWidget 类时也 Tick（可通过 meta=(DisableNativeTick) 禁用） | UserWidget.h:130 |

### EDesignPreviewSizeMode 枚举 (WITH_EDITORONLY_DATA)

| 枚举值 | 说明 | 源码位置 |
|--------|------|----------|
| FillScreen | 填充屏幕 | UserWidget.h:251 |
| Custom | 自定义尺寸 | UserWidget.h:253 |
| CustomOnScreen | 屏幕上自定义尺寸 | UserWidget.h:254 |
| Desired | 期望尺寸 | UserWidget.h:255 |
| DesiredOnScreen | 屏幕上期望尺寸 | UserWidget.h:256 |

### FQueuedWidgetAnimationTransition 结构

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| WidgetAnimation | TObjectPtr<UWidgetAnimation> | 队列中的动画（Transient） | UserWidget.h:89 |
| TransitionMode | EQueuedWidgetAnimationMode | 转换模式（Play/PlayTo/Forward/Reverse/Stop/Pause/None） | UserWidget.h:92 |
| StartAtTime | TOptional<float> | 开始时间 | UserWidget.h:95 |
| EndAtTime | TOptional<float> | 结束时间 | UserWidget.h:98 |
| NumLoopsToPlay | TOptional<int32> | 循环次数 | UserWidget.h:101 |
| PlayMode | TOptional<EUMGSequencePlayMode::Type> | 播放模式 | UserWidget.h:104 |
| PlaybackSpeed | TOptional<float> | 播放速度 | UserWidget.h:107 |
| bRestoreState | TOptional<bool> | 停止时恢复状态 | UserWidget.h:110 |

### FNamedSlotBinding 结构

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| Name | FName | Slot 名称 | UserWidget.h:234 |
| Guid | FGuid | NamedSlot GUID（WITH_EDITORONLY_DATA） | UserWidget.h:239 |
| Content | TObjectPtr<UWidget> (Instanced) | Slot 内容 Widget | UserWidget.h:243 |

### FAnimationEventBinding 结构

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| Animation | TObjectPtr<UWidgetAnimation> | 目标动画 | UserWidget.h:159 |
| Delegate | FWidgetAnimationDynamicEvent | 回调委托 | UserWidget.h:163 |
| AnimationEvent | EWidgetAnimationEvent | 事件类型（Started/Finished） | UserWidget.h:167 |
| UserTag | FName | 用户标签，用于过滤特定动画运行 | UserWidget.h:171 |

---

## Part G: Widget 类型目录

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
| UNamedSlot | 命名插槽 (继承机制核心)，含 bExposeOnInstanceOnly 和 SlotGuid 编辑器字段 | Runtime/UMG/Public/Components/NamedSlot.h |
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

## Part H: UWidgetAnimation 结构

### 概述

UWidgetAnimation 继承自 UMovieSceneSequence，存储 Widget 动画的 MovieScene 数据和动画绑定信息。

### 继承关系

```
UObject
└── UMovieSceneSequence
    └── UWidgetAnimation
```

源码位置: WidgetAnimation.h:25 — `class UWidgetAnimation : public UMovieSceneSequence`

### 字段表

| 字段名 | 类型 | 用途 | 宏保护 | 源码位置 |
|--------|------|------|--------|----------|
| MovieScene | TObjectPtr<UMovieScene> | 控制此动画的 MovieScene 指针 | — | WidgetAnimation.h:143 |
| AnimationBindings | TArray<FWidgetAnimationBinding> | 动画绑定数组 | — | WidgetAnimation.h:147 |
| bLegacyFinishOnStop | bool | 停止时是否完成评估（遗留行为兼容） | private | WidgetAnimation.h:153 |
| DisplayLabel | FString | 设计器中显示的友好名称 | WITH_EDITOR, private | WidgetAnimation.h:157 |

### 核心方法

| 方法 | 用途 | 源码位置 |
|------|------|----------|
| GetBindings() | 获取动画绑定数组 | WidgetAnimation.h:124 |
| GetStartTime() | 获取动画开始时间 | WidgetAnimation.h:59 |
| GetEndTime() | 获取动画结束时间 | WidgetAnimation.h:68 |
| RemoveBinding() | 移除动画绑定 | WidgetAnimation.h:127-128 |
| GetLegacyFinishOnStop() | 获取遗留停止行为 | WidgetAnimation.h:132 |

---

## Part I: 交叉引用

### Blueprint 文档交叉引用

Widget Blueprint 继承 Blueprint 的编辑器/运行时分离模式：

| 特性 | Blueprint | Widget Blueprint |
|------|-----------|------------------|
| 编辑器类 | UBlueprint | UWidgetBlueprint |
| 运行时类 | UBlueprintGeneratedClass | UWidgetBlueprintGeneratedClass |
| 编译产物 | 字节码 + 组件模板 | WidgetTree + Bindings + 动画 |
| 继承机制 | 父类 Blueprint 合并 | 父类 WidgetTree + NamedSlot 合并 |
| 中间基类 | — | UUserWidgetBlueprint → UBaseWidgetBlueprint |

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

注意：FSlateBrush 的 ResourceObject 可通过多种路径引用 UMaterialInterface/UMaterialInstanceDynamic，包括直接 Brush 属性和 WidgetStyle.Brush 两种方式。

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
| Runtime/UMG/Public/Blueprint/UserWidgetBlueprint.h | UUserWidgetBlueprint 定义（UBlueprint 子类） |
| Editor/UnrealEd/Public/BaseWidgetBlueprint.h | UBaseWidgetBlueprint 定义（UUserWidgetBlueprint 子类，编辑器基类） |
| Editor/UMGEditor/Public/WidgetBlueprint.h | UWidgetBlueprint、FDelegateEditorBinding、FEditorPropertyPath 定义 |
| Runtime/UMG/Public/Blueprint/WidgetBlueprintGeneratedClass.h | UWidgetBlueprintGeneratedClass、FDelegateRuntimeBinding、EBindingKind 定义 |
| Runtime/UMG/Public/Blueprint/WidgetTree.h | UWidgetTree、INamedSlotInterface 实现 |
| Runtime/UMG/Public/Blueprint/UserWidget.h | UUserWidget、FNamedSlotBinding、FAnimationEventBinding、FQueuedWidgetAnimationTransition 定义 |
| Runtime/UMG/Public/Animation/WidgetAnimation.h | UWidgetAnimation 定义 |
| Runtime/UMG/Public/Components/NamedSlot.h | UNamedSlot 定义（含 bExposeOnInstanceOnly、SlotGuid） |
| Runtime/UMG/Public/Binding/DynamicPropertyPath.h | FDynamicPropertyPath 定义（继承 FCachedPropertyPath） |

---

## 版本差异

详见: [asset-widget.md](../version/asset-widget.md)

### 已知弃用标记

| 弃用项 | 版本 | 替代方案 | 源码位置 |
|--------|------|----------|----------|
| UUserWidget::ColorAndOpacity 直接访问 | 5.2 | 使用 SetColorAndOpacity/GetColorAndOpacity | UserWidget.h:996 |
| UUserWidget::ForegroundColor 直接访问 | 5.2 | 使用 SetForegroundColor/GetForegroundColor | UserWidget.h:1004 |
| UUserWidget::Padding 直接访问 | 5.2 | 使用 SetPadding/GetPadding | UserWidget.h:1024 |
| UUserWidget::Priority 直接访问 | 5.2 | 使用 SetInputActionPriority/GetInputActionPriority | UserWidget.h:1029 |
| UUserWidget::bIsFocusable 直接访问 | 5.2 | 使用 IsFocusable/SetIsFocusable | UserWidget.h:1033 |
| UUserWidget::bStopAction 直接访问 | 5.2 | 使用 IsInputActionBlocking/SetInputActionBlocking | UserWidget.h:1038 |
| UUserWidget::ActiveSequencePlayers | 5.6 | 使用 ActiveAnimations | UserWidget.h:1483 |
| UUserWidget::StoppedSequencePlayers | 5.6 | 使用 ActiveAnimations | UserWidget.h:1491 |
| UUserWidget::InitializeInputComponent() | 5.7 | 由 bAutomaticallyRegisterInputOnConstruction 自动处理 | UserWidget.h:1705 |
| FWidgetBlueprintDelegates::GetAssetTags | 5.4 | 使用 GetAssetTagsWithContext | WidgetBlueprint.h:43 |

---
*文档创建: Phase 09-UI/UMG*
*源码路径: 相对引用 UE Engine 目录*
*更新: 补充 UUserWidgetBlueprint 继承链、UUserWidget 完整字段表、UWidgetAnimation 字段表、UNamedSlot 编辑器字段、弃用标记*