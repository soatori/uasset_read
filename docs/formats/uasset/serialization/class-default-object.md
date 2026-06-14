# Class Default Object (CDO) 机制

> **UE 源码对照**: `Runtime/CoreUObject/Private/UObject/Class.cpp` (UClass::SerializeDefaultObject, L6290-6327), `Runtime/CoreUObject/Private/UObject/Obj.cpp` (UObject::SerializeScriptProperties, L1958-2036)
> **最后对齐**: UE 5.7 (2026-06)

## 概述

Class Default Object（CDO）是 UE 中每个 `UClass` 自动创建的实例，存储该类的**默认属性值**。所有实例在创建时从 CDO 复制属性值。CDO 在 .uasset 文件中作为独立 export 存在，具有特殊的序列化路径。

---

## CDO 的本质

### 创建时机

CDO 在类首次需要时创建（延迟初始化）：

```cpp
// Class.cpp L5055-5119
UObject* UClass::CreateDefaultObject()
{
    if (ClassDefaultObject == NULL)
    {
        // 1. 先确保父类 CDO 已创建
        UClass* ParentClass = GetSuperClass();
        if (ParentClass != NULL)
        {
            ParentDefaultObject = ParentClass->GetDefaultObject();
        }

        // 2. 分配 CDO（RF_ClassDefaultObject | RF_ArchetypeObject | RF_Public）
        UObject* NewClassDefaultObject = StaticAllocateObject(
            this,                           // Class
            GetOuter(),                     // Outer
            NAME_None,                      // Name
            EObjectFlags(RF_Public | RF_ClassDefaultObject | RF_ArchetypeObject)
        );
        ClassDefaultObject = NewClassDefaultObject;

        // 3. 初始化（构造函数、属性默认值）
        // ...
    }
    return ClassDefaultObject;
}
```

### 对象标志

| 标志 | 说明 |
|------|------|
| RF_ClassDefaultObject | 标记为类默认对象 |
| RF_ArchetypeObject | 标记为模板对象（传播给子对象） |
| RF_Public | 公开访问 |

### 命名约定

CDO 在 Import/Export 表中的名称：
- 原生类：`DEFAULT_OBJECT_PREFIX + ClassName`（如 `Default__MyActor`）
- 蓝图类：`DEFAULT_OBJECT_PREFIX + BlueprintName`（如 `Default__BP_MyActor_C`）

```cpp
// LinkerLoad.cpp L2263-2269
if (NewDefaultObjectName.StartsWith(DEFAULT_OBJECT_PREFIX))
{
    NewDefaultObjectName = DEFAULT_OBJECT_PREFIX;
    NewDefaultObjectName += NewClassName.ObjectName.ToString();
    Import->ObjectName = FName(*NewDefaultObjectName);
}
```

---

## CDO 序列化流程

### 序列化入口

CDO 使用专用序列化路径 `UClass::SerializeDefaultObject()`，而非通用的 `UObject::Serialize()`：

```cpp
// Class.cpp L6290-6327
void UClass::SerializeDefaultObject(UObject* Object, FStructuredArchive::FSlot Slot)
{
    UnderlyingArchive.MarkScriptSerializationStart(Object);
    UnderlyingArchive.StartSerializingDefaults();

    // 关键区别：DeltaStruct 使用 GetSuperClass()（父类），而非 ObjClass（本类）
    // 这意味着 CDO 只序列化与父类 CDO 不同的属性
    SerializeTaggedProperties(
        Slot,
        (uint8*)Object,           // 当前对象数据
        GetSuperClass(),          // ← DeltaStruct 是父类（非本类！）
        (uint8*)Object->GetArchetype()  // 原型（通常是父类 CDO）
    );

    UnderlyingArchive.StopSerializingDefaults();
    UnderlyingArchive.MarkScriptSerializationEnd(Object);
}
```

### 关键区别：DeltaStruct 参数

| 对象类型 | SerializeTaggedProperties 的 DefaultsStruct |
|---------|--------------------------------------------|
| 普通实例 | `ObjClass`（本类） |
| CDO | `GetSuperClass()`（**父类**） |

**原因**：CDO 存储的是**与父类默认值的差异**。序列化时仅写入与父类 CDO 不同的属性，减少数据量。

### 普通实例的序列化

```cpp
// Obj.cpp L1978-2021 (UObject::SerializeScriptProperties)
UClass *ObjClass = GetClass();

// 普通实例：DiffClass = ObjClass（本类），DeltaStruct = 本类
ObjClass->SerializeTaggedProperties(
    Slot,
    (uint8*)ThisObject,
    DiffClass,              // ← ObjClass（本类）
    (uint8*)DiffObject      // ← GetArchetype()（通常是 CDO）
);
```

---

## CDO 加载流程（LinkerLoad）

### Preload 阶段

CDO 在 LinkerLoad 的 Preload 阶段有特殊处理：

```cpp
// LinkerLoad.cpp L4849-4898
if (Object->HasAnyFlags(RF_ClassDefaultObject))
{
    // 循环依赖延迟处理（可选）
    if ((LoadFlags & LOAD_DeferDependencyLoads) != 0)
    {
        DeferredCDOIndex = ExportIndex;
        Object->SetFlags(RF_NeedLoad);
        Seek(SavedPos);
        return;  // 延迟到后续处理
    }

    // 标准路径：使用 SerializeDefaultObject
    Object->GetClass()->SerializeDefaultObject(Object, *this);
    Object->SetFlags(RF_LoadCompleted);
}
else
{
    // 普通对象：使用 UObject::Serialize
    Object->Serialize(ExportSlot.EnterRecord());
}
```

### 加载顺序

```
LinkerLoad::Preload(ExportIndex)
  ├─ ObjectFlags & RF_ClassDefaultObject?
  │   └─ YES → UClass::SerializeDefaultObject(Object, Archive)
  │               └─ SerializeTaggedProperties(Slot, Object, GetSuperClass(), Archetype)
  │                   └─ SerializeVersionedTaggedProperties(...)
  │                       └─ 读取 SerializationControlExtensions (UE5.0+)
  │                       └─ 循环读取 FPropertyTag + PropertyData
  │                       └─ 终止于 Name == NAME_None
  └─ NO → UObject::Serialize(Record)
              └─ SerializeScriptProperties(Slot)
                  └─ ObjClass->SerializeTaggedProperties(Slot, Object, ObjClass, Archetype)
```

---

## 属性值继承与覆盖

### 属性值来源优先级

```
实例属性值来源优先级（从高到低）：

1. 实例自身序列化数据（SerializeScriptProperties）
   ↓ 若无
2. CDO（Class Default Object）
   ↓ 若 CDO 中无
3. 父类 CDO（GetSuperClass()->GetDefaultObject()）
   ↓ 若无
4. 属性 C++ 默认值（构造函数中设置的值）
```

### Delta 序列化

CDO 的 Delta 序列化机制：

```
父类 CDO: [A=1, B=2, C=3]
本类 CDO: [A=1, B=5, C=3, D=10]
             ↑ 只存差异 ↑
序列化数据: [B=5, D=10]  ← 仅与父类不同的属性
```

### 实例与 CDO 的差异

```
CDO:     [A=1, B=5, C=3, D=10]
实例:    [A=1, B=5, C=3, D=10]  ← 未修改，全部继承
实例:    [A=1, B=99, C=3, D=10] ← 修改了 B
序列化:  [B=99]  ← 仅存储差异（与 CDO 比较）
```

---

## CDO 在 .uasset 中的位置

### Export 表中的 CDO

CDO 作为独立 export 存在于 .uasset 文件中：

```
Package Summary
├─ ExportMap
│   ├─ Export[0]: UClass "MyActor"           (类定义)
│   ├─ Export[1]: CDO "Default__MyActor"     (类默认对象) ← RF_ClassDefaultObject
│   ├─ Export[2]: Function "ExecuteUbergraph" (蓝图函数)
│   └─ ...
```

### 识别 CDO Export

| 判断条件 | 说明 |
|---------|------|
| `Export.ObjectFlags & RF_ClassDefaultObject` | 对象标志包含 CDO 标记 |
| `Export.ObjectName` 以 `Default__` 开头 | 命名约定 |
| `Export.ClassIndex` 指向对应 UClass | 对象类型 |

---

## 序列化控制扩展（UE5.0+）

### SerializationControlExtensions

CDO 和所有 UObject 在 UE5.0+ 中，属性序列化前会写入控制扩展字节：

```cpp
// Class.cpp L1625-1654
const bool bIsUClass = IsA<UClass>();
if (bIsUClass && UEVer >= PROPERTY_TAG_EXTENSION_AND_OVERRIDABLE_SERIALIZATION)
{
    EClassSerializationControlExtension SerializationControl = NoExtension;
    Slot << SA_ATTRIBUTE("SerializationControlExtensions", SerializationControl);

    if (SerializationControl & OverridableSerializationInformation)
    {
        Slot << SA_ATTRIBUTE("OverridableOperation", Operation);
    }
}
```

**重要**：`bIsUClass` 在此处始终为 `true`，因为 `SerializeVersionedTaggedProperties` 只在 `ObjClass->SerializeTaggedProperties()` 中被调用，而 `ObjClass` 始终是 `UClass*`。因此**所有 export 的属性序列化都会写入此字节**。

---

## 蓝图 CDO 特殊性

### 蓝图生成类（UBlueprintGeneratedClass）

蓝图类编译后生成 `UBlueprintGeneratedClass`，其 CDO 包含：

| 数据 | 说明 |
|------|------|
| 变量默认值 | 蓝图中定义的变量初始值 |
| 组件默认值 | 组件层级中各组件的默认属性 |
| 默认子对象 | 蓝图中的子对象（如组件实例） |

### PropertyGuid 机制

蓝图类使用 `PropertyGuid` 处理属性重命名：

```cpp
// Class.cpp L1714-1722
if (bArePropertyGuidsAvailable && Tag.HasPropertyGuid)
{
    FName Result = FindPropertyNameFromGuid(Tag.PropertyGuid);
    if (Result != NAME_None && Tag.Name != Result)
    {
        Tag.Name = Result;  // 通过 GUID 重定向到当前名称
    }
}
```

**流程**：
1. 蓝图变量重命名后，PropertyGuid 保持不变
2. 加载时通过 GUID 查找新名称
3. 用新名称替换 Tag.Name，确保正确反序列化

---

## 与解析器的对应关系

| UE 概念 | 解析器位置 | 说明 |
|---------|-----------|------|
| CDO 识别 | `ObjectFlags & RF_ClassDefaultObject` | 判断是否为 CDO |
| CDO 命名 | `Default__` 前缀 | Export 表中识别 |
| SerializeDefaultObject | `export.serial_offset ~ serial_offset + serial_size` | CDO 数据区域 |
| Delta 差异 | 属性序列化区域 | CDO 仅存储与父类差异 |
| PropertyGuid | `tag.property_guid` | 蓝图属性重命名处理 |
| SerializationControlExtensions | `export.transforms["serialization_control"]` | UE5.0+ 控制字节 |

---

## 常见陷阱

### 1. CDO 的 DeltaStruct 是父类

**错误**：假设 CDO 的 DefaultsStruct 是本类
**正确**：CDO 使用 `GetSuperClass()`，普通实例使用 `GetClass()`

### 2. CDO 始终需要 Preload

**错误**：延迟到 PostLoad 阶段处理 CDO
**正确**：CDO 必须在 Preload 阶段加载，因为实例依赖其默认值

### 3. 蓝图 CDO 的组件层级

**陷阱**：蓝图 CDO 包含 DefaultSubobjects（组件实例），这些子对象也有独立的 export
**处理**：需要先加载类定义，再加载 CDO，才能正确解析组件层级

### 4. Transient 属性在 CDO 中的特殊处理

**规则**：`CPF_Transient` 属性在普通对象中跳过序列化，但在蓝图 CDO 中**会被序列化**
**原因**：蓝图需要在编辑器中保存临时状态

---

## 源码引用

- `Runtime/CoreUObject/Private/UObject/Class.cpp:6290` — `UClass::SerializeDefaultObject`
- `Runtime/CoreUObject/Private/UObject/Class.cpp:5055` — `UClass::CreateDefaultObject`
- `Runtime/CoreUObject/Private/UObject/Obj.cpp:1958` — `UObject::SerializeScriptProperties`
- `Runtime/CoreUObject/Private/UObject/LinkerLoad.cpp:4849` — CDO Preload 处理
- `Runtime/CoreUObject/Public/UObject/ObjectMacros.h` — `RF_ClassDefaultObject` 定义
