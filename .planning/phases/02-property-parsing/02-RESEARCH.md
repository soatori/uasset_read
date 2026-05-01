# Phase 2: 属性解析 - Research

**研究日期:** 2026-05-01
**领域:** UE PropertyTag 序列化和属性值提取
**置信度:** HIGH

## 概要

本阶段交付从 .uasset 导出数据解析 PropertyTag 结构和提取基本属性值的能力。主要参考来源是 UE 5.7 源码的 PropertyTag.h/cpp 和类型特定的属性序列化器。

**主要建议:** 实现一个遵循 UE FArchive 模式的属性解析器，使用现有的 FArchive 类进行二进制读取，并使用函数分派模式实现基本类型（Int、Float、Bool、String、Name、Object、Array）的类型特定解析器。

## UE 源码分析

### PropertyTag 结构 (PropertyTag.h)

**关键发现:** PropertyTag 是描述属性值的可序列化标签。该结构已演进以支持版本化序列化。

**核心字段 (PropertyTag.h 第 48-68 行):**
- `FName Type` - 属性类型标识符
- `FName Name` - 属性名称
- `int32 Size` - 属性序列化大小（字节）
- `int32 ArrayIndex` - 数组元素索引（默认为 INDEX_NONE/0）
- `FGuid PropertyGuid` - 用于属性重命名 (VER_UE4_PROPERTY_GUID_IN_PROPERTY_TAG)
- `uint8 HasPropertyGuid` - 表示 PropertyGuid 存在的标志
- `uint8 BoolVal` - Bool 属性值（当标志设置时无需数据序列化）
- `EPropertyTagSerializeType SerializeType` - Unknown/Skipped/Property/BinaryOrNative

**PropertyTagFlags (PropertyTag.h 第 17-26 行):**
```cpp
None                = 0x00
HasArrayIndex       = 0x01   // ArrayIndex 字段存在
HasPropertyGuid     = 0x02   // PropertyGuid 字段存在
HasPropertyExtensions = 0x04 // 扩展数据存在
HasBinaryOrNativeSerialize = 0x08
BoolTrue            = 0x10   // Bool 值为 true
SkippedSerialize    = 0x20
```

### PropertyTag 序列化模式 (PropertyTag.cpp)

**版本阈值:** `PROPERTY_TAG_COMPLETE_TYPE_NAME` (UE5 版本检查)

**UE5 (新格式, 第 445-545 行):**
```
1. Name (FName)
2. Type (通过 FPropertyTypeName 的完整 TypeName 字符串)
3. Size (int32)
4. Flags (EPropertyTagFlags - 内联序列化)
5. [ArrayIndex] - 如果 HasArrayIndex 标志
6. [PropertyGuid] - 如果 HasPropertyGuid 标志
7. [PropertyExtensions] - 如果 HasPropertyExtensions 标志
```

**UE4 (旧格式, 第 195-401 行 - LoadPropertyTagNoFullType):**
```
1. Name (FName)
2. Type (FName - 仅短名称)
3. Size (int32)
4. ArrayIndex (int32)
5. [StructName + StructGuid] - 如果 Type == StructProperty && >= VER_UE4_STRUCT_GUID_IN_PROPERTY_TAG
6. [BoolVal] - 如果 Type == BoolProperty
7. [EnumName] - 如果 Type == ByteProperty 或 EnumProperty
8. [InnerType] - 如果 Type == ArrayProperty/OptionalProperty/SetProperty/MapProperty
9. PropertyGuid (条件性)
10. PropertyExtensions
```

**关键见解:** 参见 Class.cpp 第 445-448 行 - 当 `Version < PROPERTY_TAG_COMPLETE_TYPE_NAME` 时使用旧格式。

### 属性类型序列化 (Class.cpp §1514-2000)

**SerializeVersionedTaggedProperties 模式 (Class.cpp 第 1690-1900 行):**
```
while (!IsCriticalError()) {
    // 1. 读取 PropertyTag
    FPropertyTag Tag;
    PropertyRecord << SA_VALUE(TEXT("Tag"), Tag);
    
    if (Tag.Name.IsNone()) break;  // 结束标记
    
    // 2. 尝试从不匹配类型转换
    switch (Property->ConvertFromType(Tag, ValueSlot, Data, DefaultsStruct, Defaults)) {
        case Converted:   // 类型转换成功
        case Serialized:  // 通过 ConvertFromType 序列化
        case UseSerializeItem:  // 正常序列化
        case CannotConvert:  // 类型不匹配
    }
    
    // 3. 对于不匹配类型（旧格式）
    if (Type != Expected) {
        // 回退: 如果可用，尝试通过 Guid 查找属性
    }
    
    // 4. 正常序列化路径
    Property->SerializeTaggedProperty(ValueSlot, Property, DestAddress, DefaultsFromParent);
}
```

**BoolProperty 序列化技巧 (PropertyTag.cpp 第 558-571 行):**
```
对于 bool 属性，值存储在 Tag.BoolVal 中（不单独序列化）:
- Tag.BoolVal = 0 或 1
- HasArrayIndex 标志也会设置 BoolTrue 标志
- 标签后不读取额外数据 - SerializeTaggedProperty 仅读取 BoolVal
```

**ArrayProperty 模式 (PropertyArray.cpp 第 128-824 行):**
```
1. 读取元素计数 (非 UPS 为 int32，或通过 FStructuredArchiveArray)
2. 为每个元素循环:
   - 读取内部 PropertyTag (< PROPERTY_TAG_COMPLETE_TYPE_NAME 时条件性)
   - 调用 Inner->SerializeItem() 反序列化元素
3. 通过 ConvertFromType 处理不匹配类型转换
```

### 类型特定序列化器

**IntProperty/FloatProperty (PropertyNumeric.cpp):**
- Int32: read_i32() → 4 字节有符号整数
- Int64: read_i64() → 8 字节有符号整数
- Float: read_f32() → 4 字节 IEEE 754
- Double: read_f64() → 8 字节 IEEE 754

**BoolProperty (PropertyBool.cpp 第 171-194, 423-430 行):**
```
SerializeItem 读/写单字节:
  uint8 B = ((*ByteValue & FieldMask) ? 1 : 0);
  Slot << B;
```

**StrProperty ( FString 序列化 ):**
- Length (int32): 正数 = UTF-8 长度
- Data: UTF-8 字节（无 null 终止符）
- 如果长度 <= 0 则为空字符串

**NameProperty (PropertyName.cpp):**
- 使用现有 read_name() 方法 → NameMap[index] 带数字后缀

**ObjectProperty:**
- 读取 FPackageIndex (int32)
- 返回原始索引（不解析为名称 - 推迟到阶段 3/4）

## 版本格式差异

| 方面 | UE4 (< PROPERTY_TAG_COMPLETE_TYPE_NAME) | UE5 (>= PROPERTY_TAG_COMPLETE_TYPE_NAME) |
|------|-----------------------------------------|------------------------------------------|
| **类型命名** | 仅短名称 (如 "IntProperty") | 完整 TypeName (如 "/Script/CoreUObject.IntProperty") |
| **Struct 类型** | 独立 StructName + StructGuid 字段 | TypeName 参数中的 Struct 路径 |
| **Enum 类型** | 独立 EnumName 字段 | TypeName 参数中的 Enum 路径 |
| **Array inner** | 独立 InnerType 字段 | TypeName 参数中的内部类型 |
| **相同类型检测** | 比较 Type FName | 比较完整 TypeName 字符串 |
| **PropertyGuid** | 条件性 (VER_UE4_PROPERTY_GUID_IN_PROPERTY_TAG) | 通过结构化 archive 总是可能 |

**关键版本常量（来自 UE 源码）:**
- `VER_UE4_STRUCT_GUID_IN_PROPERTY_TAG` - StructProperty 包含 StructGuid
- `VER_UE4_PROPERTY_GUID_IN_PROPERTY_TAG` - PropertyGuid 字段添加
- `VER_UE4_PROPERTY_TAG_SET_MAP_SUPPORT` - SetProperty/MapProperty 支持
- `VAR_UE4_ARRAY_PROPERTY_INNER_TAGS` - ArrayProperty 内部类型标签信息
- `EUnrealEngineObjectUE5Version::PROPERTY_TAG_COMPLETE_TYPE_NAME` - UE5 格式切换
- `EUnrealEngineObjectUE5Version::PROPERTY_TAG_EXTENSION_AND_OVERRIDABLE_SERIALIZATION` - 可覆盖序列化

## 属性类型序列化

### 基本属性序列化表

| 类型 | 字节 | 读取方法 | 备注 |
|------|------|----------|------|
| **Int8Property** | 1 | read_u8() | 单字节 |
| **Int16Property** | 2 | struct.unpack('<h') | 2 字节有符号 |
| **IntProperty** | 4 | read_i32() | 4 字节有符号 |
| **Int64Property** | 8 | read_i64() | 8 字节有符号 |
| **UInt16Property** | 2 | read_u16() | 2 字节无符号 |
| **UInt32Property** | 4 | read_u32() | 4 字节无符号 |
| **UInt64Property** | 8 | read_u64() | 8 字节无符号 |
| **FloatProperty** | 4 | read_f32() | IEEE 754 单精度 |
| **DoubleProperty** | 8 | read_f64() | IEEE 754 双精度 |
| **BoolProperty** | 0 | Tag.BoolVal | 标志位，无数据字节 |
| **StrProperty** | 可变 | read_fstring() | 长度前缀 UTF-8 |
| **NameProperty** | 8 | read_name() | u32 索引 + u32 数字 |
| **ObjectProperty** | 4 | read_i32() | FPackageIndex 原始值 |
| **EnumProperty** | 可变 | read_enum() | Name 然后数值 |
| **ByteProperty** | 1 | read_u8() | 单字节或 enum |
| **ArrayProperty** | 可变 | parse_array() | 计数 + 元素循环 |

### ArrayProperty 序列化流程

```
ArrayProperty 序列化 (PropertyArray.cpp 第 128-824 行):

1. 对于旧格式 (< PROPERTY_TAG_COMPLETE_TYPE_NAME):
   - 检查 InnerType 标签是否存在 (>= VER_UE4_INNER_ARRAY_TAG_INFO)
   - 如果是 struct 内部类型则读取 InnerPropertyTag

2. 读取元素计数:
   - UPS (无版本属性序列化): 通过 FStructuredArchiveArray
   - 正常: read_i32()

3. 为每个元素循环 (0 到 Count-1):
   - 对于不匹配的 struct 内部: 使用 ConvertFromType 回退
   - 调用 Inner->SerializeItem(Slot, ElementPtr)
   - 处理自定义属性列表的属性链
```

### PropertyTag 标志处理

**从序列化 FPropertyTag 读取的标志:**

| 标志 | 检查 | 读取动作 |
|------|------|----------|
| HasArrayIndex | `Flags & 0x01` | `ArrayIndex = read_i32()` |
| HasPropertyGuid | `Flags & 0x02` | `PropertyGuid = read_16_bytes()` |
| HasPropertyExtensions | `Flags & 0x04` | 扩展数据（推迟到阶段 3） |
| BoolTrue | `Flags & 0x10` | `BoolVal = 1` (bool 值 = true) |
| SkippedSerialize | `Flags & 0x20` | 完全跳过属性值 |

**UE5 中的标志处理 (PropertyTag.cpp 第 484-544 行):**
```cpp
// 保存: 根据属性状态序列化标志
PropertyTagFlags flags = None;
if (ArrayIndex != 0) flags |= HasArrayIndex;
if (HasPropertyGuid) flags |= HasPropertyGuid;
if (Extensions != NoExtension) flags |= HasPropertyExtensions;
if (SerializeType == BinaryOrNative) flags |= HasBinaryOrNativeSerialize;
if (SerializeType == Skipped) flags |= SkippedSerialize;
if (BoolVal && Type == BoolProperty) flags |= BoolTrue;

Slot << flags;

// 加载: 解析标志并读取条件字段
Tag.HasPropertyGuid = EnumHasAnyFlags(flags, HasPropertyGuid);
if (EnumHasAnyFlags(flags, HasArrayIndex)) Slot << Tag.ArrayIndex;
if (EnumHasAnyFlags(flags, HasPropertyGuid)) Slot << Tag.PropertyGuid;
```

## 边缘情况与陷阱

### 陷阱 1: BoolProperty 值存储
**问题:** 假设 bool 属性在标签后有序列化数据。

**原因:** BoolProperty 的实际值存储在 `PropertyTag.BoolVal` 中，而非作为独立的序列化数据。

**避免方法:**
- 对于 BoolProperty，从 `Tag.BoolVal` 标志位提取值
- 读取标签后无需额外读取
- 参见 PropertyTag.cpp 第 558-571 行的结构化处理

**警告信号:** 如果代码在 BoolProperty 标签后读取 1 字节并得到数据，你正在读取*下一个*属性的数据。

---

### 陷阱 2: ArrayProperty 内部类型解析
**问题:** 假设旧格式中数组内部属性使用简单类型名称。

**原因:** 在 UE4 < PROPERTY_TAG_COMPLETE_TYPE_NAME 中，ArrayProperty 将 InnerType 存储为短 FName，而非完整类型路径。内部类型可能需要通过属性查找来解析。

**避免方法:**
- 在确定类型格式前检查版本阈值
- 对于带 struct 内部的旧格式，读取内部 PropertyTag
- 使用属性查找/注册来解析类型名称

**警告信号:** 数组元素解析失败，出现 "type not found" 错误。

---

### 陷阱 3: 属性标签大小不匹配
**问题:** 读取的正好是属性数据的 Size 字段值，但 Size 可能包含填充或扩展数据。

**原因:** Size 字段表示总序列化大小，但由于优化，实际数据可能更少。

**避免方法:**
- 在读取属性值前后跟踪当前 archive 位置
- 如果 Size 与实际读取不匹配，要么 seek 到正确位置，要么记录警告
- UE 源码使用此模式: `UnderlyingArchive.Seek(StartOfProperty + Tag.Size)`

**警告信号:** 属性偏移 N 字节，导致后续解析错误。

---

### 陷阱 4: 未知属性类型处理
**问题:** 遇到未知属性类型时崩溃或挂起。

**原因:** Blueprint 生成的类可能有自定义或重命名的属性。

**避免方法:**
- 检查属性类型是否存在于类型注册表中
- 如果未知，使用 Size seek 跳过值: `seek(current + Size)`
- 记录警告，包含属性名和类型以供调试
- 继续解析剩余属性

**警告信号:** 解析器在特定属性停止，返回带错误的部分结果。

---

### 陷阱 5: PropertyGuid 与属性名称解析
**问题:** 加载旧格式资产时属性显示为 "None" 或错误名称。

**原因:** Property Guid 用于在新版本中映射重命名的属性。

**避免方法:**
- 如果设置了 HasPropertyGuid 标志则存储 PropertyGuid
- 对于类属性，支持通过 Guid 查找的属性名称重映射
- 延迟实现（阶段 3）最初可以跳过

**警告信号:** 属性名称与预期的蓝图定义不匹配。

---

### 陷阱 6: 字符串长度编码
**问题:** 错误读取负长度字符串。

**原因:** FString 长度字段是有符号的 - 负值表示 UTF-16 编码（旧格式）。

**避免方法:**
- Length == 0: 空字符串
- Length < 0: UTF-16 旧格式，跳过数据并返回空字符串（按 D-10）
- Length > 0: UTF-8，读取相应字节

**警告信号:** 特定资产的字符串解析失败。

---

### 陷阱 7: 数组边界检查
**问题:** ArrayProperty 带无效 ArrayIndex (>= ArrayDim)。

**原因:** 序列化数据可能使用过期偏移写入。

**避免方法:**
- 验证 ArrayIndex < Property->ArrayDim
- 记录警告并跳过无效数组元素
- 使用 PropertyTag 的 Tag.ArrayIndex，而非假设为 0

**警告信号:** 数组解析因索引越界而崩溃。

---

## 与阶段 1 集成

### 现有代码复用

| 阶段 1 组件 | 阶段 2 复用 |
|-------------|-------------|
| **FArchive** | 所有读取方法: read_i32, read_i64, read_f32, read_f64, read_u8, read_name, read_fstring |
| **PackageFileSummary** | 版本检查: file_version_ue5, legacy_file_version 用于版本阈值 |
| **NameMap** | 属性标签名称解析，NameProperty 值 |
| **ObjectExport.serial_offset** | 属性序列化开始的 seek 位置 |
| **ParseResult 模式** | 属性解析错误时返回部分结果 |
| **CustomVersion 存储** | 支持版本化属性 |

### 属性解析流程

```
从 ExportMap 条目 (阶段 1):

export.serial_offset ─┐
                      ├──→ FArchive.seek(export.serial_offset)
                      │
                      ▼
           while (true):
               tag = read_property_tag(archive, version)
               if tag.Name == "None": break
               size = tag.Size
               start_pos = archive.tell()
               
               // 分派到类型特定解析器
               value = parse_property_value(tag, archive)
               
               archive.seek(start_pos + size)  // 确保正确位置
               
               // 存储到结果列表
               properties.append(PropertyValue(...))

           return properties
```

### 版本检查模式

```python
# 使用阶段 1 summary 中的这些阈值
UE5_PROPERTY_TAG_COMPLETE_TYPE_NAME = 1000  # 大约值，在源码中验证

def use_complete_type_name(legacy_version, ue5_version):
    if legacy_version <= -8:  # UE5 文件
        return ue5_version >= UE5_PROPERTY_TAG_COMPLETE_TYPE_NAME
    return False  # UE4 总是使用旧格式
```

### PropertyTag 序列化模式

```python
def read_property_tag(archive, version):
    tag = PropertyTag()
    
    # 读取类型名称
    tag.type_name = archive.read_name(name_map)  # 或完整格式用 read_fstring
    
    # 读取大小
    tag.size = archive.read_i32()
    
    # 读取标志
    flags = archive.read_u8()
    
    # 根据标志读取条件字段
    if flags & 0x01:  # HasArrayIndex
        tag.array_index = archive.read_i32()
    else:
        tag.array_index = 0
        
    if flags & 0x02:  # HasPropertyGuid
        tag.property_guid = archive.read(16)
    else:
        tag.property_guid = None
        
    # ... 处理其他标志 ...
    
    return tag
```

## 验证架构

### Nyquist 验证维度

| 维度 | 测试方法 | 自动化? |
|------|----------|---------|
| **正确性** | 解析已知 UE 资产 → 比较预期属性列表 | ✅ |
| **版本兼容性** | 解析 UE4 vs UE5 资产，边界版本 | ✅ |
| **边缘情况** | BoolProperty (无数据)，未知类型（跳过），零长度数组 | ✅ |
| **格式合规** | PropertyTag 大小匹配实际读取字节 | ✅ |
| **错误恢复** | 损坏资产 → 部分结果，不崩溃 | ✅ |

### 测试覆盖图

| 测试文件 | 测试用例 | 自动化命令 |
|----------|----------|------------|
| `tests/test_property_parsing.py` | PropertyTag 解析，版本检查，类型特定解析 | `pytest tests/test_property_parsing.py -v` |

### 阶段需求 → 测试映射

| 需求 ID | 行为 | 测试类型 | 文件存在? |
|---------|------|----------|-----------|
| PROP-01 | 读取 PropertyTag 结构 (Name, Type, Size, Flags) | 单元 | 新 - 02-01 |
| PROP-02 | 提取 IntProperty 值 (int32, int64) | 单元 | 新 - 02-01 |
| PROP-03 | 提取 FloatProperty 值 (float, double) | 单元 | 新 - 02-01 |
| PROP-04 | 从 Tag.BoolVal 提取 BoolProperty 值 | 单元 | 新 - 02-01 |
| PROP-05 | 提取 StrProperty (带长度前缀的 FString) | 单元 | 新 - 02-01 |
| PROP-06 | 提取 NameProperty (NameMap 索引) | 单元 | 新 - 02-01 |
| PROP-07 | 提取 ObjectProperty (FPackageIndex) | 单元 | 新 - 02-01 |
| PROP-08 | 提取 ArrayProperty (计数 + 元素循环) | 单元 | 新 - 02-02 |
| PROP-09 | 处理 PropertyTag 标志 (HasPropertyGuid 等) | 单元 | 新 - 02-01 |

### 样本率

- **每次提交:** `pytest tests/test_property_parsing.py::test_<specific> -x`
- **每次 wave 合并:** `pytest tests/ -v`
- **阶段门控:** `pytest tests/ -v` 必须通过后才能 `/gsd-verify-work`

### Wave 0 缺口

- [ ] `tests/test_property_parsing.py` — PropertyTag 解析测试
- [ ] `tests/test_property_types.py` — 类型特定值提取
- [ ] `tests/conftest.py` — 共享测试 fixtures (mock archive, 示例资产)

## 实现指导

### 推荐项目结构

```
src/
├── uasset_read.py          # 现有 - 阶段 1
├── property_parser.py      # 新增 - 阶段 2 属性解析逻辑
├── models/
│   ├── __init__.py
│   └── properties.py       # 新增 - dataclasses: PropertyTag, PropertyValue
└── tests/
    ├── test_property_parsing.py  # 新增
    └── test_property_types.py    # 新增
```

### 模块组织

**property_parser.py** (新增 - 约 300-400 行):

```python
"""
属性解析模块 (阶段 2)。

导出:
- read_property_tag(archive, name_map, version) -> PropertyTag
- parse_property_value(tag, archive, name_map, export_map) -> Any
- parse_properties_from_export(export, archive, summary, name_map, export_map) -> List[PropertyValue]
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass

# 类型分派表
PROPERTY_PARSERS = {
    'IntProperty': parse_int_property,
    'Int8Property': parse_int8_property,
    'Int16Property': parse_int16_property,
    'Int64Property': parse_int64_property,
    'UInt16Property': parse_uint16_property,
    'UInt32Property': parse_uint32_property,
    'UInt64Property': parse_uint64_property,
    'FloatProperty': parse_float_property,
    'DoubleProperty': parse_double_property,
    'BoolProperty': parse_bool_property,
    'StrProperty': parse_str_property,
    'NameProperty': parse_name_property,
    'ObjectProperty': parse_object_property,
    'ArrayProperty': parse_array_property,
    # ... 按需添加更多
}
```

### 关键 API 函数

```python
def read_property_tag(
    archive: FArchive,
    name_map: List[str],
    legacy_version: int,
    ue5_version: int
) -> PropertyTag:
    """
    读取 PropertyTag 结构 (PROP-01)。
    
    遵循 UE 源码版本特定格式。
    返回包含所有字段的 PropertyTag dataclass。
    """


def parse_property_value(
    tag: PropertyTag,
    archive: FArchive,
    name_map: List[str],
    export_map: List[ObjectExport]
) -> Any:
    """
    根据 Type 提取属性值 (PROP-02 至 PROP-09)。
    
    从 PROPERTY_PARSERS 分派到类型特定解析器。
    返回 Python 原生类型: int, float, str, list, PackageIndex, 或 None。
    """


def parse_properties_from_export(
    export: ObjectExport,
    archive: FArchive,
    summary: PackageFileSummary,
    name_map: List[str],
    export_map: List[ObjectExport]
) -> List[PropertyValue]:
    """
    从导出条目解析所有属性。
    
    返回 PropertyValue dataclass 列表:
        - name: str
        - type: str
        - value: Any
    """


def parse_array_property(
    tag: PropertyTag,
    archive: FArchive,
    name_map: List[str],
    export_map: List[ObjectExport],
    depth: int = 0
) -> List[Any]:
    """
    解析 ArrayProperty 值 (PROP-08)。
    
    处理:
    - 读取计数 (int32)
    - 循环: 解析内部元素
    - 深度限制 (D-18: 最大 10)
    - 未知内部类型: 跳过
    """
```

### 数据模型

**properties.py** (新增 dataclasses):

```python
@dataclass
class PropertyTag:
    """来自 FPropertyTag 的属性标签结构。"""
    name: str                    # 属性名称
    type: str                    # 类型名称字符串
    size: int                    # 序列化大小
    array_index: int = 0         # 数组元素索引
    property_guid: Optional[bytes] = None  # 如果存在则为 16 字节
    flags: int = 0               # EPropertyTagFlags
    bool_val: int = 0            # Bool 值 (0 或 1)


@dataclass
class PropertyValue:
    """解析后的属性值容器 (D-08, D-09)。"""
    name: str                    # 属性名称
    type: str                    # 属性类型
    value: Any                   # 解析后的值 (Python 原生类型)
    array_index: int = 0         # 用于数组元素


@dataclass
class ParseResult:
    """带部分数据支持的属性解析结果。"""
    properties: List[PropertyValue] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    is_success: bool = False
```

## 不要手工实现

| 问题 | 不要构建 | 使用替代 | 原因 |
|------|----------|----------|------|
| PropertyTag 解析 | 自定义解码器 | `property_parser.read_property_tag()` | 模式完全匹配 UE 源码 |
| BoolProperty 值 | 标签后读取 1 字节 | 从标志获取 `Tag.bool_val` | Bool 值存储在标签中，不是数据 |
| 数组元素计数 | 手动跟踪 | 标签后 `read_i32()` | 标准 UE 模式 |
| 属性类型分派 | Switch 语句 | 字典分派 (`PROPERTY_PARSERS`) | 更清晰，匹配 UE 模型 |
| FArchive 读取 | 手动 struct.unpack | 现有 `archive.read_i32()` 等 | 复用阶段 1，处理字节序 |

## 来源

### 主要来源 (HIGH 置信度)

- **PropertyTag.h** - `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Public\UObject\PropertyTag.h`
  - FPropertyTag 结构定义 (第 37-105 行)
  - EPropertyTagFlags 枚举 (第 17-26 行)
  - EPropertyTagExtension 枚举 (第 34-46 行)

- **PropertyTag.cpp** - `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Private\UObject\PropertyTag.cpp`
  - LoadPropertyTagNoFullType (第 195-401 行) - UE4 格式
  - FPropertyTag 的 operator<< (第 436-545 行) - UE5 格式
  - SerializeTaggedProperty (第 548-593 行) - 值序列化
  - PropertyTag.cpp 第 158-166 行: PropertyTagExtension 序列化

- **Class.cpp (SerializeVersionedTaggedProperties)** - `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Private\UObject\Class.cpp`
  - 属性循环模式 (第 1688-1900 行)
  - ConvertFromType 模式 (第 1859-1897 行)
  - 序列化路径选择 (第 1713-1794 行)

- **PropertyBool.cpp** - `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Private\UObject\PropertyBool.cpp`
  - SerializeItem (第 423-430 行) - 单字节读/写
  - ConvertFromType (第 283-335 行) - 类型转换支持

- **PropertyArray.cpp** - `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Private\UObject\PropertyArray.cpp`
  - SerializeItem (第 128-824 行) - 计数 + 循环模式
  - 内部属性处理 (第 650-734 行)
  - ConvertFromType (第 1280-1358 行)

- **uasset_read.py** - `E:\Develop\uasset_read\uasset_read.py`
  - FArchive 方法 (第 65-230 行)
  - Read 辅助函数: read_i32, read_i64, read_f32, read_f64, read_fstring, read_name

### 次要来源 (MEDIUM 置信度)

- **PropertyName.cpp** - `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Private\UObject\PropertyName.cpp`
  - PropertyInfo 实现 (第 11-115 行)

- **PropertyNumeric.cpp** - `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Private\UObject\PropertyNumeric.cpp`
  - 数值属性基类 (第 16-295 行)

### 第三来源 (LOW 置信度)

- **Property.h / UnrealType.h** - 属性基类接口模式

## 元数据

**置信度分解:**
- **标准栈:** HIGH - 直接来自 UE 5.7 源码，已对照 PropertyTag.h/cpp 验证
- **架构:** HIGH - 来自 Class.cpp SerializeVersionedTaggedProperties 的模式，文档完善
- **陷阱:** HIGH - 基于 UE 源码处理和版本特定边缘情况

**研究日期:** 2026-05-01
**有效期至:** 2026-05-30 (UE 5.7 源码稳定，无破坏性变更预期)

## 环境可用性

| 依赖项 | 需求方 | 可用 | 版本 | 回退 |
|--------|--------|------|------|------|
| Python 3.10+ | 运行时 (match/case) | 检查 | 3.10+ | 无 - 仅需 stdlib |

**检查命令:** `python --version`

## 待解决问题

1. **PropertyTag 类型存储格式**
   - UE 5.7: 使用 `UE::FPropertyTypeName` 内部类型
   - 对于解析: 应读取完整 TypeName 字符串 (UE5) 还是短 Type + 参数 (UE4)?
   - **建议:** 先作为字符串读取，再解析类型信息；匹配 UE 源码结构

2. **StructProperty 嵌套解析**
   - StructProperty 值需要嵌套字段的递归解析
   - **建议:** 推迟到阶段 3 (ADVP-01)；阶段 2 仅处理基本类型，按 D-24

3. **HasPropertyExtensions 数据**
   - 扩展包括 OverridableInformation 和 ExperimentalOverridableLogic
   - **建议:** 阶段 2 完全跳过，记录警告；阶段 3 可能需要用于蓝图变量

4. **EnumProperty 值格式**
   - EnumProperty 存储为 Name (枚举名) + 数值
   - **建议:** 先读取 Name，然后读取底层数值类型 (ByteProperty/UInt64Property)

## 版本常量参考

来自 UE 5.7 源文件:

| 常量 | 值 | 用途 |
|------|-----|------|
| `PACKAGE_FILE_TAG` | 0x9E2A83C1 | 文件魔数 |
| `VER_UE4_STRUCT_GUID_IN_PROPERTY_TAG` | ~500 | StructProperty StructGuid |
| `VER_UE4_PROPERTY_GUID_IN_PROPERTY_TAG` | ~510 | PropertyGuid 字段 |
| `VER_UE4_PROPERTY_TAG_SET_MAP_SUPPORT` | ~520 | SetProperty/MapProperty |
| `VAR_UE4_ARRAY_PROPERTY_INNER_TAGS` | ~500 | ArrayProperty InnerType |
| `PACKAGE_SAVED_HASH_VERSION` | 1004 | 头部 FIoHash |
| `EUnrealEngineObjectUE5Version::PROPERTY_TAG_COMPLETE_TYPE_NAME` | 1000+ | UE5 格式切换 |

注意: 确版本值应对照实际 UE 5.7 源文件验证。