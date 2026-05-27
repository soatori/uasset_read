# Widget Blueprint 资产文档

Widget Blueprint 资产类型 (UWidgetBlueprint/UWidgetBlueprintGeneratedClass) 相关文档导航。

## 概述

UMG (Unreal Motion Graphics) 是 Unreal Engine 的 UI 框架，通过 Widget Blueprint 实现可视化 UI 设计。Widget Blueprint 采用与普通 Blueprint 相似的编辑器/运行时分离模式：

- **UWidgetBlueprint** (Editor) — 编辑器资产，存储 WidgetTree 设计、属性绑定和动画定义
- **UWidgetBlueprintGeneratedClass** (Runtime) — 运行时生成类，存储编译后的 WidgetTree 原型、运行时绑定和动画引用

该分离模式与普通 Blueprint 的 UBlueprint/UBlueprintGeneratedClass 分离模式类似，但增加了 WidgetTree 和 NamedSlot 继承等 UMG 特有机制。

## 子文档

| 文档 | 内容 | 说明 |
|------|------|------|
| [widget-blueprint-structure.md](widget-blueprint-structure.md) | 编辑器 + 运行时结构 | UWidgetBlueprint 和 UWidgetBlueprintGeneratedClass 核心字段 |
| [widget-binding.md](widget-binding.md) | Binding 转换流程 | EditorBinding 到 RuntimeBinding 的编译转换 |
| [widget-namedslot.md](widget-namedslot.md) | NamedSlot 继承机制 | WidgetTree 合并和 GUID 追踪机制 |

## 核心源码

### Editor 模块 (UMGEditor)

| 文件 | 路径 | 说明 |
|------|------|------|
| WidgetBlueprint.h | Editor/UMGEditor/Public/ | UWidgetBlueprint 编辑器类定义 |
| WidgetBlueprint.cpp | Editor/UMGEditor/Private/ | 编译、Binding 转换实现 |
| BaseWidgetBlueprint.h | Editor/UMGEditor/Public/ | UWidgetBlueprint 基类定义 |

### Runtime 模块 (UMG)

| 文件 | 路径 | 说明 |
|------|------|------|
| WidgetBlueprintGeneratedClass.h | Runtime/UMG/Public/Blueprint/ | 运行时生成类定义 |
| WidgetTree.h | Runtime/UMG/Public/Blueprint/ | WidgetTree 容器结构 |
| UserWidget.h | Runtime/UMG/Public/Blueprint/ | UUserWidget 运行时类 |
| WidgetAnimation.h | Runtime/UMG/Public/Animation/ | Widget 动画结构 |
| NamedSlot.h | Runtime/UMG/Public/Components/ | NamedSlot Widget 定义 |
| DynamicPropertyPath.h | Runtime/UMG/Public/Binding/ | 动态属性路径结构 |

## 与 Blueprint 文档交叉引用

Widget Blueprint 继承自普通 Blueprint 的编辑器/运行时分离模式，核心机制与 v1.0 Blueprint 文档类似：

| Blueprint 文档 | Widget Blueprint 对应 |
|----------------|----------------------|
| [blueprint.md](blueprint.md) | 本文档（导航结构相同） |
| [blueprint-generated-class.md](blueprint-generated-class.md) | UWidgetBlueprintGeneratedClass 继承 UBlueprintGeneratedClass |
| [blueprint-compilation.md](blueprint-compilation.md) | Widget 编译流程额外包含 WidgetTree 处理 |
| [blueprint-source.md](blueprint-source.md) | UWidgetBlueprint 继承 UBaseWidgetBlueprint |

**继承链对比：**

```
Blueprint:
UBlueprint → UBlueprintGeneratedClass

Widget Blueprint:
UBaseWidgetBlueprint → UWidgetBlueprint → UWidgetBlueprintGeneratedClass
```

WidgetBlueprintGeneratedClass 直接继承 BlueprintGeneratedClass，复用其字节码、组件模板等机制，并添加 WidgetTree、Bindings、NamedSlots 等 UMG 特有字段。

## 与 Material 文档交叉引用

Widget 可引用 Material 用于 UI 渲染，主要通过 UImage Widget 的 Brush 属性：

| Material 文档 | Widget 引用方式 |
|---------------|-----------------|
| [material.md](material.md) | UImage.WidgetStyle.Brush.ResourceObject 引用 UMaterial |
| [material-instance.md](material-instance.md) | 动态材质实例用于 UI 动态效果 |

**材质引用路径：**
- UImage.WidgetStyle.Brush.ResourceObject → UMaterialInterface
- UImage.WidgetStyle.Brush.ResourceObject → UMaterialInstanceDynamic (动态材质)

## 相关文档

- [Import/Export 表结构](../import-export-tables.md) — Widget 对象引用机制
- [属性序列化](../serialization/property-tag.md) — Widget 属性存储结构
- [蓝图版本差异](../version/asset-blueprint.md) — Blueprint 版本演进参考
- [Widget 版本差异](../version/asset-widget.md) — UMG 版本演进

---
*文档创建: Phase 09-UI/UMG*
*源码路径: 相对引用 UE Engine 目录*