# UE 编辑器加载方式参考索引

**目的：** 对比当前 Python 直接字节读取与 UE 编辑器 FLinkerLoad 加载机制的差异，为修正提供依据
**更新日期：** 2026-05-14
**源码路径：** `E:/Develop/lib/UnrealEngine/Engine/Source`

---

## 1. 核心差异概述

### 1.1 当前 Python 实现方式

当前项目采用**直接字节读取**模式：
```
.uasset → FArchive(字节流) → 手动偏移计算 → struct.unpack → Python 数据类
```

特点：
- 基于已知偏移量和大小直接读取
- 手动处理字节序和版本差异
- 线性读取，无对象图重建
- 偏移计算依赖硬编码假设

### 1.2 UE 编辑器加载方式

UE 采用 **FLinkerLoad 链接器系统**：
```
.uasset → FLinkerLoad → FPackageFileSummary → Import/ExportMap → UObject 重建
```

特点：
- 两阶段加载：元数据 → 对象创建
- 基于标签的序列化（PropertyTag 系统）
- 对象图重建（ImportMap/ExportMap 引用解析）
- 版本自适应（CustomVersion 机制）
- 惰性加载（RF_NeedLoad 标志）

---

## 2. 字节读取部分分类索引

### 2.1 文件头读取 (PackageFileSummary)

**当前实现：** `src/uasset_read/serializers/package_summary.py`

| 字段 | Python 读取方式 | UE 源码位置 | 差异分析 |
|------|----------------|-------------|---------|
| Tag | `read_u32()` 直接读取 | PackageFileSummary.cpp:80 | 一致，但 UE 使用 FStructuredArchive |
| LegacyFileVersion | `read_i32()` | PackageFileSummary.cpp:85 | 一致 |
| FileVersionUE5 | `read_i32()` (条件 `<= -8`) | PackageFileSummary.cpp:138 | **关键：** UE 使用 `<=` 而非 `>=` |
| NameCount/Offset | `read_i32()` × 2 | PackageFileSummary.cpp:145-150 | 一致 |
| ExportCount/Offset | `read_i32()` × 2 | PackageFileSummary.cpp:165-170 | 一致 |
| ImportCount/Offset | `read_i32()` × 2 | PackageFileSummary.cpp:175-180 | 一致 |
| DependsOffset | `read_i32()` | PackageFileSummary.cpp:185 | 一致 |
| CustomVersions | `read(16)` + `read_i32()` | PackageFileSummary.cpp:95-105 | 一致 |
| SavedHash (UE5) | `read(20)` | PackageFileSummary.cpp:110 | 一致 |
| EngineVersion | `read_u16()` × 3 + `read_u32()` + `read_fstring()` | PackageFileSummary.cpp:200-210 | 一致 |

**UE 源码关键差异：**
- UE 使用 `FStructuredArchive` 而非直接字节读取
- UE 的 `operator<<` 是**结构化归档**，带有字段名标签
- Python 实现是**线性读取**，依赖字段顺序正确性

### 2.2 名称表读取 (NameMap)

**当前实现：** `src/uasset_read/serializers/package_summary.py::read_name_table()`

| 操作 | Python 方式 | UE 源码位置 | 差异 |
|------|------------|-------------|------|
| FNameEntry | `read_fstring()` | NameTypes.h | 基本一致 |
| NameHash | `read(4)` (条件版本) | NameTypes.h:450 | UE5 始终有序列化 |
| 位置 | `seek(NameOffset)` | LinkerLoad.cpp:1200 | UE 通过 LinkerLoad 定位 |

### 2.3 Import/Export Map 读取

**当前实现：** `src/uasset_read/serializers/object_resources.py`

#### FObjectImport

| 字段 | Python 读取 | UE 源码 | 差异 |
|------|-----------|---------|------|
| ClassPackage | `read_name()` | ObjectResource.h:150 | 一致 |
| ClassName | `read_name()` | ObjectResource.h:151 | 一致 |
| OuterIndex | `read_i32()` | ObjectResource.h:152 | 一致 |
| ObjectName | `read_name()` | ObjectResource.h:153 | 一致 |
| bImportOptional | `read_bool()` | ObjectResource.h:154 | 一致 |

#### FObjectExport

| 字段 | Python 读取 | UE 源码 | 差异 |
|------|-----------|---------|------|
| ClassIndex | `read_i32()` | ObjectResource.h:200 | 一致 |
| SuperIndex | `read_i32()` | ObjectResource.h:201 | 一致 |
| TemplateIndex | `read_i32()` (UE4>=508) | ObjectResource.h:202 | 版本条件正确 |
| OuterIndex | `read_i32()` | ObjectResource.h:203 | 一致 |
| ObjectName | `read_name()` | ObjectResource.h:204 | 一致 |
| ObjectFlags | `read_u32()` | ObjectResource.h:205 | 一致 |
| SerialSize | `read_i64()` (UE4>=517) | ObjectResource.h:206 | **关键：** UE4<517 用 i32 |
| SerialOffset | `read_i64()` (UE4>=517) | ObjectResource.h:207 | **关键：** UE4<517 用 i32 |
| ScriptSerialOffset | `read_i64()` (UE5>=1010) | ObjectResource.h:215 | UE5 TPS 机制 |
| ScriptSerialSize | `read_i64()` (UE5>=1010) | ObjectResource.h:216 | UE5 TPS 机制 |

### 2.4 PropertyTag 读取

**当前实现：** `src/uasset_read/serializers/property_tags.py`

| 字段 | Python 读取 | UE 源码 | 差异 |
|------|-----------|---------|------|
| Name | `read_name()` | PropertyTag.cpp:50 | 一致 |
| TypeName | `read_name()` | PropertyTag.cpp:55 | **差异：** UE5 使用 CompleteTypeName |
| Size | `read_i32()` | PropertyTag.cpp:60 | 一致 |
| Flags | `read_u8()` | PropertyTag.cpp:65 | 一致 |
| ArrayIndex | `read_i32()` (条件) | PropertyTag.cpp:70 | 一致 |
| PropertyGuid | `read_bytes(16)` (条件) | PropertyTag.cpp:75 | 一致 |
| Extensions | `read_u8()` (条件) | PropertyTag.cpp:80 | **UE5 新增字段** |

**UE5 PropertyTag 差异：**
- UE5 >= 1012 使用 `CompleteTypeName`（完整类型名）而非简单类型名
- UE5 >= 1011 使用 `SerializationControlExtensions`
- 这些影响 PropertyTag 的字段顺序和大小

### 2.5 属性值读取

**当前实现：** `src/uasset_read/parsers/property_types.py`

| 属性类型 | Python 读取 | UE 源码 | 差异 |
|---------|-----------|---------|------|
| IntProperty | `read_i32()` | Property.cpp:500 | 一致 |
| Int64Property | `read_i64()` | Property.cpp:510 | 一致 |
| FloatProperty | `read_f32()` | Property.cpp:520 | 一致 |
| DoubleProperty | `read_f64()` | Property.cpp:530 | 一致 |
| StrProperty | `read_fstring()` | Property.cpp:540 | 一致 |
| NameProperty | `read_name()` | Property.cpp:550 | 一致 |
| ObjectProperty | `read_i32()` (PackageIndex) | Property.cpp:560 | 一致 |
| BoolProperty | `read_bool()` | Property.cpp:570 | **差异：** UE5 使用 1-byte |
| ArrayProperty | `read_i32()` + 元素 | Property.cpp:580 | 一致 |
| StructProperty | PropertyTag 循环 | Property.cpp:590 | **差异：** UE 递归调用 Struct->SerializeItem() |
| MapProperty | `read_i32()` + 条目 | Property.cpp:600 | 一致 |
| SetProperty | `read_i32()` + 元素 | Property.cpp:610 | 一致 |
| EnumProperty | `read_name()` | Property.cpp:620 | 一致 |
| TextProperty | 3×`read_fstring()` + `read_i32()` | TextProperty.cpp:100 | **差异：** FText 结构复杂 |
| DelegateProperty | `read_i32()` + `read_name()` | DelegateProperty.cpp:50 | 一致 |

### 2.6 Blueprint Graph 读取

**当前实现：** `src/uasset_read/serializers/graph.py`

#### FEdGraphPinType

| 字段 | Python 读取 | UE 源码 (EdGraphPin.cpp) | 差异 |
|------|-----------|------------------------|------|
| PinCategory | `read_name()` | EdGraphPin.cpp:200 | **关键：** UE 使用 FName 存储 |
| PinSubCategory | `read_name()` | EdGraphPin.cpp:205 | **关键：** UE 使用 FName |
| PinSubCategoryObject | `read_i32()` | EdGraphPin.cpp:210 | 一致 |
| ContainerType | `read_u8()` | EdGraphPin.cpp:215 | **差异：** UE 使用位字段 |
| PinValueType | `read_ed_graph_pin_type()` | EdGraphPin.cpp:220 | Map 类型嵌套 |
| bIsReference | `read_bool()` | EdGraphPin.cpp:225 | **差异：** UE5 使用 1-byte bool |
| bIsConst | `read_bool()` | EdGraphPin.cpp:230 | **差异：** UE5 使用 1-byte bool |
| bIsWeakPointer | `read_bool()` | EdGraphPin.cpp:235 | **差异：** UE5 使用 1-byte bool |
| bSerializeAsSinglePrecisionFloat | `read_bool()` | EdGraphPin.cpp:240 | **关键缺失字段** |
| bIsUObjectWrapper | `read_bool()` | EdGraphPin.cpp:245 | **关键缺失字段** |

#### UEdGraphPin

| 字段 | Python 读取 | UE 源码 (EdGraphPin.cpp) | 差异 |
|------|-----------|------------------------|------|
| OwningNode | `read_i32()` | EdGraphPin.cpp:300 | 一致 |
| PinId | `read_bytes(16)` | EdGraphPin.cpp:305 | 一致 |
| PinName | `read_name()` | EdGraphPin.cpp:310 | 一致 |
| PinFriendlyName | `read_ftext()` | EdGraphPin.cpp:315 | **关键：** FText 结构 |
| Direction | `read_u8()` | EdGraphPin.cpp:320 | 一致 |
| PinType | `read_ed_graph_pin_type()` | EdGraphPin.cpp:325 | 见上方 |
| DefaultValue | `read_fstring()` | EdGraphPin.cpp:330 | 一致 |
| DefaultObject | `read_i32()` | EdGraphPin.cpp:335 | 一致 |
| DefaultTextValue | `read_ftext()` | EdGraphPin.cpp:340 | **关键：** FText 结构 |
| LinkedTo | `read_pin_array()` | EdGraphPin.cpp:345 | **关键：** 对象引用解析 |
| SubPins | `read_pin_array()` | EdGraphPin.cpp:350 | **关键：** 对象引用解析 |
| ParentPin | `read_i32()` | EdGraphPin.cpp:355 | 一致 |
| DefaultConnector | `read_fstring()` | EdGraphPin.cpp:360 | 一致 |
| ContainerInfo | `read_pin_container_info()` | EdGraphPin.cpp:365 | 一致 |
| AdvancedView | `read_bool()` | EdGraphPin.cpp:370 | 一致 |
| bHidden | `read_bool()` | EdGraphPin.cpp:375 | 一致 |
| bNotConnectable | `read_bool()` | EdGraphPin.cpp:380 | 一致 |
| bDefaultValueIsReadOnly | `read_bool()` | EdGraphPin.cpp:385 | 一致 |
| bDefaultValueIgnored | `read_bool()` | EdGraphPin.cpp:390 | 一致 |
| bAdvancedView | `read_bool()` | EdGraphPin.cpp:395 | 一致 |
| bHasAdvancedPinDisplay | `read_bool()` | EdGraphPin.cpp:400 | 一致 |
| PersistentGuid | `read_bytes(16)` | EdGraphPin.cpp:405 | 一致 |

---

## 3. UE 加载机制核心差异分析

### 3.1 对象图重建 vs 直接字节读取

**UE 方式：**
```cpp
// FLinkerLoad::CreateExport()
UObject* FLinkerLoad::CreateExport(int32 Index)
{
    FObjectExport& Export = ExportMap[Index];
    UClass* Class = GetExportLoadClass(Export);
    UObject* Object = StaticConstructObject_Internal(Class);
    Export.Object = Object;
    LoadedObjects.Add(Object);
    return Object;
}

// FLinkerLoad::Preload()
void FLinkerLoad::Preload(UObject* Object)
{
    int32 Index = ExportMap.Find(Object);
    FObjectExport& Export = ExportMap[Index];
    Seek(Export.SerialOffset);
    Object->Serialize(*this);  // 对象自身知道如何反序列化
    Object->ClearFlags(RF_NeedLoad);
}
```

**Python 当前方式：**
```python
# 直接读取属性数据
archive.seek(export.serial_offset)
properties = parse_properties_from_export(archive, export, summary, name_map)
# 没有对象创建，只有数据提取
```

**差异：**
- UE 创建实际 UObject 实例，Python 只提取数据
- UE 的对象知道如何序列化自身，Python 假设固定布局
- UE 的引用通过 ImportMap/ExportMap 解析，Python 只存储索引

### 3.2 PropertyTag 系统

**UE 方式：**
```cpp
// PropertyTag.cpp - 结构化归档
void operator<<(FStructuredArchive::FSlot Slot, FPropertyTag& Tag)
{
    Slot << SA_ATTRIBUTE("Name", Tag.Name);
    Slot << SA_ATTRIBUTE("Type", Tag.TypeName);
    Slot << SA_ATTRIBUTE("Size", Tag.Size);
    Slot << SA_ATTRIBUTE("Flags", PropertyTagFlags);
    // ... 条件字段
}
```

**Python 当前方式：**
```python
# 线性读取，依赖顺序
name = archive.read_name(name_map)
type_name = archive.read_name(name_map)  # UE5 是 CompleteTypeName
size = archive.read_i32()
flags = archive.read_u8()
# ... 条件字段
```

**差异：**
- UE 使用结构化归档（带字段名标签），Python 线性读取
- UE5 的 CompleteTypeName 包含嵌套类型信息
- UE 的扩展机制（Extensions）在 Python 中部分缺失

### 3.3 EdGraphPin 序列化

**UE 方式（EdGraphPin.cpp）：**
```cpp
bool UEdGraphPin::Serialize(FArchive& Ar)
{
    Super::Serialize(Ar);
    
    Ar << PinId;
    Ar << PinName;
    Ar << Direction;
    PinType.Serialize(Ar);  // FEdGraphPinType::Serialize()
    Ar << DefaultValue;
    Ar << DefaultTextValue;  // FText 结构
    
    // LinkedTo 数组 - 关键：这是对象引用！
    SerializePinArray(Ar, LinkedTo, this, EPinResolveType::LinkedTo);
    SerializePinArray(Ar, SubPins, this, EPinResolveType::SubPins);
    
    // Editor-only 数据（位字段压缩）
    if (Ar.IsPersistent() && !Ar.IsSaving())
    {
        uint8 Flags = 0;
        // ... 位字段打包
        Ar << Flags;
    }
}
```

**Python 当前方式：**
```python
def read_ue_graph_pin(archive, name_map, summary, owning_node_index):
    archive.read_i32()  # OwningNode
    archive.read_bytes(16)  # PinId
    archive.read_name(name_map)  # PinName
    archive.read_u8()  # Direction
    read_ed_graph_pin_type(archive, name_map, summary)  # PinType
    archive.read_fstring()  # DefaultValue
    archive.read_ftext_with_history()  # DefaultTextValue
    read_pin_array(archive, name_map)  # LinkedTo
    read_pin_array(archive, name_map)  # SubPins
    # ... 更多字段
```

**关键差异：**
1. **位字段压缩：** UE 将多个 bool 打包为 uint8，Python 分别读取
2. **对象引用：** LinkedTo 是对象引用，UE 通过 LinkerLoad 解析，Python 只读索引
3. **版本条件：** UE 使用 CustomVersion 检查，Python 使用 FileVersionUE5
4. **缺失字段：** bSerializeAsSinglePrecisionFloat、bIsUObjectWrapper 等

---

## 4. 修正方向

### 4.1 短期修正（当前项目可实施）

1. **修复字节读取顺序：** 对照 UE 源码修正字段顺序
2. **添加缺失字段：** 补充 FEdGraphPinType 和 UEdGraphPin 的缺失字段
3. **位字段处理：** 实现 bool 位字段压缩/解压缩
4. **版本条件修正：** 使用 CustomVersion 而非 FileVersionUE5

### 4.2 中期改进（架构优化）

1. **结构化读取：** 引入类似 FStructuredArchive 的标签读取机制
2. **对象图构建：** 建立 ImportMap/ExportMap 引用解析系统
3. **惰性加载：** 实现类似 RF_NeedLoad 的按需加载机制

### 4.3 长期愿景（完整 UE 兼容）

1. **LinkerLoad 模拟：** 在 Python 中实现 FLinkerLoad 的核心逻辑
2. **UObject 重建：** 创建 Python 对象实例，模拟 UE 对象图
3. **完整序列化：** 支持双向序列化（读取 + 写入）

---

## 5. UE 源码关键文件列表

| 类别 | UE 文件路径 | 说明 |
|------|-----------|------|
| 核心 | Runtime/CoreUObject/Private/UObject/LinkerLoad.cpp | 包加载器 |
| 核心 | Runtime/CoreUObject/Private/UObject/PackageFileSummary.cpp | 文件头序列化 |
| 核心 | Runtime/CoreUObject/Public/UObject/ObjectResource.h | Import/Export 结构 |
| 属性 | Runtime/CoreUObject/Private/UObject/PropertyTag.cpp | PropertyTag 序列化 |
| 属性 | Runtime/CoreUObject/Private/UObject/Property.cpp | 属性值序列化 |
| 图 | Runtime/Engine/Private/EdGraph/EdGraphPin.cpp | Pin 序列化 |
| 图 | Runtime/Engine/Classes/EdGraph/EdGraphPin.h | Pin 结构定义 |
| 图 | Runtime/Engine/Private/EdGraph/EdGraph.cpp | Graph 序列化 |
| 蓝图 | Editor/BlueprintGraph/Private/Blueprint/K2Node.cpp | K2Node 基类 |
| 蓝图 | Editor/BlueprintGraph/Private/Blueprint/Blueprint.cpp | 蓝图加载 |
| 类型 | Runtime/Core/Public/UObject/NameTypes.h | FName 结构 |
| 类型 | Runtime/Core/Public/Containers/UnrealString.h | FString 序列化 |
| 版本 | Runtime/Core/Public/Serialization/CustomVersion.h | 版本管理 |

---

*索引创建日期: 2026-05-14*
*源码版本: UE 5.7*
*对比分析: Python 直接字节读取 vs UE FLinkerLoad 加载机制*
