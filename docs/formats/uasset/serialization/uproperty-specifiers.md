# UPROPERTY 说明符与属性标志

> **UE 源码对照**: `Runtime/CoreUObject/Public/UObject/ObjectMacros.h`, `Runtime/CoreUObject/Public/UObject/Field.h`
> **最后对齐**: UE 5.7 (2026-06)

## 概述

UPROPERTY 是 UE 反射系统的核心宏，用于声明可被引擎识别、序列化、编辑器显示和蓝图访问的属性。每个 UPROPERTY 可附带多种**说明符**（specifiers），控制属性的行为。说明符最终编译为 `CPF_*` 标志位存储在 `FProperty::PropertyFlags` 中。

---

## 属性标志（CPF_*）完整表

### 编辑器与显示控制

| 标志 | 值 | UPROPERTY 说明符 | 说明 |
|------|------|-----------------|------|
| CPF_Edit | 0x01 | `EditAnywhere`, `EditInstanceOnly`, `EditDefaultsOnly` | 属性可在编辑器中编辑 |
| CPF_EditConst | 0x20000 | (无直接说明符) | 属性在编辑器中只读 |
| CPF_EditFixedSize | 0x40 | (数组固定大小) | 数组元素可修改但大小不可变 |
| CPF_DisableEditOnTemplate | 0x800 | (蓝图相关) | 禁用在 archetype/子蓝图上编辑 |
| CPF_DisableEditOnInstance | 0x10000 | (蓝图相关) | 禁用在类实例上编辑 |
| CPF_NoClear | 0x2000000 | `NoClear` | 隐藏清除按钮（对象引用） |
| CPF_NonTransactional | 0x400000000 | `NonTransactional` | 属性变更不参与事务（撤销/重做） |
| CPF_EditorOnly | 0x800000000 | `EditorOnly` | 仅编辑器加载，运行时不加载 |
| CPF_InstancedReference | 0x80000 | `Instanced` | 组件引用，自动实例化 |

### 蓝图可见性

| 标志 | 值 | UPROPERTY 说明符 | 说明 |
|------|------|-----------------|------|
| CPF_BlueprintVisible | 0x04 | `BlueprintReadWrite`, `BlueprintReadOnly` | 蓝图可读 |
| CPF_BlueprintReadOnly | 0x10 | `BlueprintReadOnly` | 蓝图只读（不可写） |
| CPF_BlueprintAssignable | 0x10000000 | `BlueprintAssignable` | 多播委托可在蓝图中绑定 |

### 序列化控制

| 标志 | 值 | UPROPERTY 说明符 | 说明 |
|------|------|-----------------|------|
| CPF_Transient | 0x2000 | `Transient` | 不保存/加载（蓝图 CDO 除外） |
| CPF_Config | 0x4000 | `Config` | 作为配置属性保存/加载 |
| CPF_GlobalConfig | 0x40000 | `GlobalConfig` | 从基类加载配置，子类不覆盖 |
| CPF_SaveGame | 0x1000000 | `SaveGame` | 存档序列化（仅 ArIsSaveGame） |
| CPF_DuplicateTransient | 0x200000 | `DuplicateTransient` | 复制时重置为默认值 |
| CPF_Deprecated | 0x20000000 | `Deprecated` | 已废弃，读取但不保存 |
| CPF_IsPlainOldData | 0x40000000 | (编译器自动) | 可 memcpy 替代深拷贝 |
| CPF_ZeroConstructor | 0x200 | (编译器自动) | memset(0) 即可构造 |

### 网络复制

| 标志 | 值 | UPROPERTY 说明符 | 说明 |
|------|------|-----------------|------|
| CPF_Net | 0x20 | `Replicated`, `ReplicatedUsing` | 属性参与网络复制 |
| CPF_RepNotify | 0x100000000 | `ReplicatedUsing` | 复制后触发通知回调 |
| CPF_RepSkip | 0x80000000 | (结构体内非复制属性) | 在已复制结构体中跳过此属性 |
| CPF_Interp | 0x2000000000 | `Interp` | 可插值（过场动画用） |

### 函数参数

| 标志 | 值 | UPROPERTY 说明符 | 说明 |
|------|------|-----------------|------|
| CPF_Parm | 0x80 | (函数参数) | 函数/调用参数 |
| CPF_OutParm | 0x100 | `ref` (C++) | 函数调用后复制出 |
| CPF_ReturnParm | 0x400 | (返回值) | 函数返回值 |
| CPF_ReferenceParm | 0x8000000 | `ref` (C++) | 按引用传递 |
| CPF_ConstParm | 0x02 | `const` (C++) | 常量函数参数 |
| CPF_RequiredParm | 0x8000 | (蓝图中强制连接) | 蓝图必须显式连接 |

### 对象与引用

| 标志 | 值 | UPROPERTY 说明符 | 说明 |
|------|------|-----------------|------|
| CPF_ExportObject | 0x08 | `Export` | 对象可随 Actor 导出 |
| CPF_NonNullable | 0x1000 | `NoAuto` 相关 | 对象引用不可为 null |
| CPF_AutoWeak | 0x4000000000 | (弱指针自动) | 弱指针导出类型自动标记 |
| CPF_Virtual | 0x4000000 | (接口属性) | 接口定义属性，无有效偏移 |
| CPF_ExperimentalExternalObjects | 0x100000 | (实验性) | 对象保存在独立文件 |
| CPF_NoDestructor | 0x1000000000 | (内部) | 无析构函数 |

---

## UPROPERTY 说明符语义对照

### 编辑器可见性组合

| 说明符 | CPF 标志组合 | 说明 |
|--------|-------------|------|
| `EditAnywhere` | CPF_Edit | 默认值和实例均可编辑 |
| `EditDefaultsOnly` | CPF_Edit + CPF_DisableEditOnInstance | 仅类默认值可编辑 |
| `EditInstanceOnly` | CPF_Edit + CPF_DisableEditOnTemplate | 仅实例可编辑 |
| `VisibleAnywhere` | CPF_BlueprintVisible | 仅显示，不可编辑 |
| `VisibleDefaultsOnly` | CPF_BlueprintVisible + CPF_DisableEditOnInstance | 仅默认值可见 |
| `VisibleInstanceOnly` | CPF_BlueprintVisible + CPF_DisableEditOnTemplate | 仅实例可见 |

### 蓝图访问组合

| 说明符 | CPF 标志组合 | 说明 |
|--------|-------------|------|
| `BlueprintReadWrite` | CPF_BlueprintVisible | 蓝图可读写 |
| `BlueprintReadOnly` | CPF_BlueprintVisible + CPF_BlueprintReadOnly | 蓝图只读 |
| `BlueprintGetter` | (元数据) | 自定义 getter 函数 |
| `BlueprintSetter` | (元数据) | 自定义 setter 函数 |

### 网络复制

| 说明符 | CPF 标志组合 | 说明 |
|--------|-------------|------|
| `Replicated` | CPF_Net | 属性自动复制 |
| `ReplicatedUsing=FuncName` | CPF_Net + CPF_RepNotify | 复制后调用 `FuncName()` |
| (结构体内无标记) | CPF_RepSkip | 已复制结构体中跳过 |

### 序列化控制

| 说明符 | CPF 标志组合 | 说明 |
|--------|-------------|------|
| `Transient` | CPF_Transient | 不序列化（CDO 除外） |
| `Config` | CPF_Config | 配置文件序列化 |
| `GlobalConfig` | CPF_GlobalConfig | 全局配置（不继承覆盖） |
| `SaveGame` | CPF_SaveGame | 存档序列化 |
| `DuplicateTransient` | CPF_DuplicateTransient | 复制时重置 |
| `NonTransactional` | CPF_NonTransactional | 不参与事务 |

---

## 元数据说明符（Metadata Specifiers）

元数据不生成 CPF 标志，而是存储在属性的 `MetaData` 字典中，供编辑器和蓝图系统使用。

### 常用元数据

| 元数据 | 值类型 | 说明 |
|--------|--------|------|
| `Category="..."` | string | 编辑器属性分类（显示分组） |
| `DisplayName="..."` | string | 编辑器中显示的名称 |
| `ToolTip="..."` | string | 工具提示文本 |
| `ClampMin="..."` | float/int | 数值最小值 |
| `ClampMax="..."` | float/int | 数值最大值 |
| `UIMin="..."` | float/int | 编辑器 UI 最小值 |
| `UIMax="..."` | float/int | 编辑器 UI 最大值 |
| `Units="..."` | string | 显示单位（如 "cm", "kg"） |
| `MakeStructureDefaultValue="..."` | string | 结构体默认值（通配符 pin） |

### 蓝图相关元数据

| 元数据 | 说明 |
|--------|------|
| `BlueprintGetter="FuncName"` | 自定义 getter 函数名 |
| `BlueprintSetter="FuncName"` | 自定义 setter 函数名 |
| `AllowPrivateAccess` | 允许蓝图访问 private 属性 |
| `ExposeOnSpawn` | 生成时暴露为参数 |
| `DeprecatedNode` | 标记为废弃，蓝图打开时显示警告 |
| `DeprecationMessage="..."` | 废弃提示信息 |
| `HideInDetailView` | 在细节面板隐藏 |

### 数组/容器相关元数据

| 元数据 | 说明 |
|--------|------|
| `EditFixedSize` | 数组大小不可编辑 |
| `TitleProperty` | 数组元素的显示标题属性 |
| `MaxElementCount` | 编辑器中最大元素数 |
| `AllowedClasses="..."` | 可选对象类型的类名列表 |
| `DisallowedClasses="..."` | 排除的对象类型 |
| `GetOptions="FuncName"` | 提供下拉选项的函数名 |

### 组件/对象引用元数据

| 元数据 | 说明 |
|--------|------|
| `ShowOnlyInnerProperties` | 显示子对象的属性而非折叠 |
| `FullyExpand` | 编辑器中完全展开 |
| `CollapseEditOverlay` | 隐藏编辑覆盖按钮 |
| `NoElementDuplicate` | 数组中禁止重复元素 |
| `AllowAnyActor` | 对象选择器允许任何 Actor |

---

## 属性标志与序列化行为

### 影响序列化的标志

| 标志 | 序列化影响 |
|------|-----------|
| CPF_Transient | 跳过序列化（CDO 例外） |
| CPF_Config | 写入配置文件而非 .uasset |
| CPF_SaveGame | 仅在 `ArIsSaveGame` 时序列化 |
| CPF_Net | 在网络复制序列化路径中处理 |
| CPF_Deprecated | 读取但保存时跳过 |
| CPF_EditorOnly | 运行时加载跳过 |

### 序列化路径选择

```
属性序列化决策流程:
  CPF_Transient? → 跳过（CDO 除外）
  CPF_Deprecated? → 读取但不保存
  ArIsSaveGame && !CPF_SaveGame? → 跳过
  CPF_Config? → 配置序列化路径
  CPF_Net? → 网络复制序列化路径
  其他 → 标准 tagged property 序列化
```

---

## 与解析器的对应关系

解析器在以下场景使用属性标志信息：

| 场景 | 标志 | 解析器行为 |
|------|------|-----------|
| 蓝图变量提取 | CPF_BlueprintVisible | 判断是否为蓝图可见变量 |
| 网络标记 | CPF_Net, CPF_RepNotify | 标记网络复制属性 |
| Transient 跳过 | CPF_Transient | 某些类跳过 Transient 属性 |
| 编辑器分类 | (元数据 Category) | 输出中保留分类信息 |

---

## 源码引用

- `Runtime/CoreUObject/Public/UObject/ObjectMacros.h` — CPF_* 标志定义（L417-470）
- `Runtime/CoreUObject/Public/UObject/Field.h` — FProperty 基类
- `Runtime/CoreUObject/Public/UObject/UnrealType.h` — 各属性类型定义
- `Runtime/CoreUObject/Private/UObject/Class.cpp` — SerializeTaggedProperties 中标志使用
