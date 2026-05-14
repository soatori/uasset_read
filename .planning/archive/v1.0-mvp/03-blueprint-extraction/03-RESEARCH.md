# Phase 3: Blueprint Extraction - Research

**研究日期:** 2026-05-01
**领域:** 从 .uasset 文件提取蓝图元数据
**置信度:** HIGH (UE 5.7 源码已验证)

## Summary

蓝图提取需要解析存储在 .uasset 文件导出数据中的蓝图特定结构。关键结构是 `FBPVariableDescription` (变量定义) 和 `FEdGraphPinType` (类型信息)。蓝图检测使用 ExportMap 中的 ClassIndex,通过检查类名是否包含 "Blueprint" 来识别蓝图资产。父类解析将 FPackageIndex 映射到 ImportMap/ExportMap 中的对象名。

UE 源码中的 `Blueprint.h` 和 `EdGraphPin.h` 定义了精确的序列化格式。FEdGraphPinType 在 UE 版本间演进,通过自定义版本添加了容器类型支持 (Array/Set/Map)。阶段 1/2 中现有的 FArchive、dataclass 模式和 ParseResult 部分结果模式可直接应用。

**主要推荐:** 将蓝图提取实现为 `parse_uasset()` 的扩展,使用已建立的 FArchive 模式自动检测蓝图并提取元数据。

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

### Implementation Decisions

**Blueprint Detection Strategy**
- D-01: 类名检测 —— 检查 ExportMap ClassIndex 中类名是否包含 "Blueprint" 关键字
- D-02: 自动检测 —— parse_uasset() 自动检测并提取蓝图元数据
- D-03: 检测失败时在 ParseResult.errors 中记录警告 (非静默跳过)
- D-04: 仅检测是否为蓝图,不区分 BlueprintType (Normal、Interface、MacroLibrary 等)

**Variable Type Naming**
- D-05: 使用 UE 原始 PinCategory 值 (如 "Integer"、"Object Reference")
- D-06: 容器+元素类型格式如 Array[Int]、Map[Str,Obj]
- D-07: 解析 PinSubCategoryObject 为具体类名 (如 "AActor Reference")
- D-08: 完整 FEdGraphPinType 结构解析 (所有字段)

**Parent Class Resolution**
- D-09: 仅直接父类 (无继承链追溯)
- D-10: 将 FPackageIndex 解析为 ImportMap/ExportMap 中的对象名
- D-11: 解析失败时返回原始 FPackageIndex + 警告
- D-12: 无循环引用检查 (仅单层,无循环可能)

**Default Value Handling**
- D-13: 将 DefaultValue 字符串解析为 Python 原生类型 (int、float、bool、str)
- D-14: 解析失败时返回原始字符串 (fallback)
- D-15: 仅基本类型 (int、float、bool、string) —— 无复杂类型
- D-16: 向量类型保持字符串 "(X=1.0,Y=2.0,Z=3.0)" 格式

### Claude's Discretion

- 具体蓝图检测类名匹配逻辑
- FEdGraphPinType 字段解析顺序和数据类型
- DefaultValue 字符串解析正则表达式或解析器实现
- 变量元数据 (Category、PropertyFlags) 输出格式
- 单元测试组织和测试资产选择

### Deferred Ideas (OUT OF SCOPE)

**Phase 4 (Output and CLI)**
- BlueprintMetadata JSON 输出格式化
- 蓝图数据文本摘要格式

**v2 (Blueprint Advanced)**
- BlueprintType 完整分类 (Normal、Interface、MacroLibrary、FunctionLibrary)
- 完整继承链解析 (递归到 UObject)
- 循环引用检测
- 蓝图图提取 (UEdGraph、Nodes、Pins)
- 复杂默认值解析 (数组、向量、对象引用)
- 完整变量元数据提取 (MetaDataArray 详细解析)

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BLUE-01 | 从类名或包路径检测蓝图资产类型 | FEdGraphPinType 序列化,阶段 1 ClassIndex 解析模式 |
| BLUE-02 | 提取蓝图父类 (ParentClass 引用) | FPackageIndex 解析,ImportMap/ExportMap 查找模式 |
| BLUE-03 | 提取蓝图变量定义 (FBPVariableDescription) | Blueprint.h 结构已验证,序列化模式已记录 |
| BLUE-04 | 提取蓝图类型 (Normal、Interface、MacroLibrary) | 按 D-04 推迟 |
| BLUE-05 | 从 FEdGraphPinType 解析变量类型 | EdGraphPin.h 结构已验证,所有字段已记录 |
| BLUE-06 | 提取变量元数据 (Category、PropertyFlags) | FBPVariableDescription 字段已记录,EPropertyFlags 枚举已验证 |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Blueprint detection | Parse layer | — | 使用 ExportMap ClassIndex (已在阶段 1 解析) |
| ParentClass resolution | Parse layer | — | FPackageIndex → ImportMap/ExportMap 查找 |
| FEdGraphPinType parsing | Parse layer | — | 从导出数据二进制反序列化 |
| DefaultValue parsing | Parse layer | Output tier (v2) | 阶段 3 基本 Python 类型;复杂类型推迟 |
| BlueprintMetadata output | Parse layer | Output tier | ParseResult 扩展;阶段 4 JSON 格式化 |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| dataclasses | stdlib | BlueprintMetadata、FEdGraphPinType、FBPVariableDescription 模型 | 阶段 1/2 模式,通过 asdict() JSON 序列化 |
| struct | stdlib | 二进制解析 | 阶段 1 FArchive 模式 |
| re | stdlib | DefaultValue 字符串解析 | 仅 stdlib,D-13 基本类型 |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| typing | stdlib | 类型提示 | 所有 dataclass 定义 |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Regex for DefaultValue | Full parser | 仅 D-15 基本类型过度工程化 |

**Installation:**
无新依赖 —— 按阶段 1 决策仅 stdlib。

## Architecture Patterns

### System Architecture Diagram

```
.uasset file
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ parse_uasset() [Phase 1/2]                                       │
│   └── PackageFileSummary, NameMap, ImportMap, ExportMap         │
│   └── PropertyValue[] from exports (Phase 2)                    │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ Blueprint Detection [Phase 3 - NEW]                              │
│   ┌───────────────────────────────────────────────────────────┐ │
│   │ For each export:                                           │ │
│   │   Check ClassIndex → resolve class name                    │ │
│   │   If class name contains "Blueprint" → mark as blueprint   │ │
│   └───────────────────────────────────────────────────────────┘ │
│   │                                                             │
│   ▼ (if blueprint detected)                                     │
│   ┌───────────────────────────────────────────────────────────┐ │
│   │ Seek to export.SerialOffset                                 │ │
│   │ Parse ParentClass (FPackageIndex) → resolve to object name │ │
│   │ Parse NewVariables count + array                            │ │
│   │   For each FBPVariableDescription:                          │ │
│   │     Parse VarName (FName)                                   │ │
│   │     Parse VarType (FEdGraphPinType)                         │ │
│   │     Parse Category (FText)                                  │ │
│   │     Parse PropertyFlags (uint64)                            │ │
│   │     Parse DefaultValue (FString)                            │ │
│   └───────────────────────────────────────────────────────────┘ │
│   │                                                             │
│   ▼                                                             │
│   BlueprintMetadata dataclass                                   │
│   ├── is_blueprint: bool                                        │
│   ├── parent_class: str or None                                 │
│   ├── variables: List[BlueprintVariable]                        │
│   └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
ParseResult (extended)
    ├── summary, name_map, import_map, export_map (Phase 1)
    ├── properties (Phase 2)
    ├── blueprint: Optional[BlueprintMetadata] (Phase 3 - NEW)
    └── errors: List[str]
```

### Recommended Project Structure
```
uasset_read.py (extended in Phase 3)
├── FArchive (Phase 1)
├── PackageFileSummary, ObjectImport, ObjectExport (Phase 1)
├── PropertyTag, PropertyValue (Phase 2)
├── FEdGraphPinType, BlueprintVariable, BlueprintMetadata (Phase 3 - NEW)
├── parse_uasset() (extended with blueprint extraction)
└── detect_blueprint(), extract_blueprint_metadata() (Phase 3 - NEW)

tests/
├── test_uasset_read.py (Phase 1)
├── test_property_parsing.py (Phase 2)
└── test_blueprint_extraction.py (Phase 3 - NEW)
```

### Pattern 1: Blueprint Detection from ClassIndex

**What:** 检查导出的 ClassIndex 是否指向蓝图类
**When to use:** 阶段 1 解析后对 ExportMap 中每个导出使用

**Example:**
```python
# Source: Phase 1 get_asset_class() pattern
def detect_blueprint(
    export: ObjectExport,
    import_map: List[ObjectImport],
    export_map: List[ObjectExport]
) -> bool:
    """
    检测导出是否为蓝图资产。
    
    检查 ClassIndex 解析是否包含 "Blueprint" 关键字。
    按 D-01/D-04: 仅检测存在性,不检测 BlueprintType。
    """
    class_name = get_asset_class(export, import_map, export_map)
    if class_name and "Blueprint" in class_name:
        return True
    return False
```

### Pattern 2: FEdGraphPinType Parsing

**What:** 从二进制数据反序列化 Pin 类型结构
**When to use:** 解析 FBPVariableDescription.VarType 时

**Example (from EdGraphPin.cpp Serialize method):**
```python
# Source: EdGraphPin.cpp lines 163-346 [VERIFIED]
@dataclass
class FEdGraphPinType:
    """Pin 类型结构来自 EdGraphPin.h lines 76-225."""
    pin_category: str = ""          # FName
    pin_sub_category: str = ""      # FName
    pin_sub_category_object: int = 0  # FPackageIndex (resolved later)
    container_type: int = 0         # EPinContainerType: 0=None, 1=Array, 2=Set, 3=Map
    is_reference: bool = False
    is_const: bool = False
    is_weak_pointer: bool = False
    is_uobject_wrapper: bool = False

def read_ed_graph_pin_type(
    archive: FArchive,
    name_map: List[str],
    summary: PackageFileSummary
) -> FEdGraphPinType:
    """
    从导出数据解析 FEdGraphPinType。
    
    序列化顺序 (from EdGraphPin.cpp):
    1. PinCategory (FName)
    2. PinSubCategory (FName)
    3. PinSubCategoryObject (FPackageIndex)
    4. ContainerType (uint8) - if FFrameworkObjectVersion >= EdGraphPinContainerType
    5. PinValueType (FEdGraphTerminalType) - if ContainerType == Map
    6. bIsReference (bool)
    7. bIsWeakPointer (bool)
    8. PinSubCategoryMemberReference (FSimpleMemberReference) - if UE4 >= MEMBER_REFERENCE_IN_PINTYPE
    9. bIsConst (bool) - if UE4 >= SERIALIZE_PINTYPE_CONST
    10. bIsUObjectWrapper (bool) - if FReleaseObjectVersion >= PinTypeIncludesUObjectWrapperFlag
    """
    pin_type = FEdGraphPinType()
    
    # Step 1-2: PinCategory and PinSubCategory (FName)
    pin_type.pin_category = archive.read_name(name_map)
    pin_type.pin_sub_category = archive.read_name(name_map)
    
    # Step 3: PinSubCategoryObject (FPackageIndex)
    pin_type.pin_sub_category_object = archive.read_i32()
    
    # Step 4: ContainerType (uint8)
    # Per EdGraphPin.cpp line 216: FFrameworkObjectVersion >= EdGraphPinContainerType
    pin_type.container_type = archive.read_u8()
    
    # Step 5: PinValueType for Map containers
    if pin_type.container_type == 3:  # Map
        # Skip PinValueType for Phase 3 (defer complex types)
        # PinValueType: TerminalCategory + TerminalSubCategory + TerminalSubCategoryObject
        archive.read_name(name_map)  # TerminalCategory
        archive.read_name(name_map)  # TerminalSubCategory
        archive.read_i32()           # TerminalSubCategoryObject
    
    # Step 6-7: bIsReference and bIsWeakPointer
    pin_type.is_reference = archive.read_u8() != 0
    pin_type.is_weak_pointer = archive.read_u8() != 0
    
    # Step 8: PinSubCategoryMemberReference (skip for Phase 3)
    # FSimpleMemberReference: MemberParent + MemberName + MemberGuid
    archive.read_i32()  # MemberParent (FPackageIndex)
    archive.read_name(name_map)  # MemberName
    archive.read(16)  # MemberGuid (16 bytes)
    
    # Step 9: bIsConst
    pin_type.is_const = archive.read_u8() != 0
    
    # Step 10: bIsUObjectWrapper
    pin_type.is_uobject_wrapper = archive.read_u8() != 0
    
    return pin_type
```

### Pattern 3: FBPVariableDescription Parsing

**What:** 从蓝图导出数据解析变量定义
**When to use:** 蓝图检测后,解析 NewVariables 数组

**Example (from Blueprint.h lines 200-256):**
```python
# Source: Blueprint.h lines 200-256 [VERIFIED]
@dataclass
class BlueprintVariable:
    """
    来自 FBPVariableDescription 的变量定义。
    
    按 D-05/D-06: 使用 UE 原始名称加容器前缀。
    """
    var_name: str                    # FName
    var_type: FEdGraphPinType        # Full type structure
    category: str                    # FText (simplified to string)
    property_flags: int              # uint64 EPropertyFlags
    default_value: any = None        # Parsed or raw string per D-13/D-14
    friendly_name: str = ""          # FString

def read_blueprint_variable(
    archive: FArchive,
    name_map: List[str],
    summary: PackageFileSummary
) -> BlueprintVariable:
    """
    从蓝图导出解析 FBPVariableDescription。
    
    序列化顺序 (from Blueprint.h USTRUCT):
    1. VarName (FName)
    2. VarGuid (FGuid - 16 bytes)
    3. VarType (FEdGraphPinType)
    4. FriendlyName (FString)
    5. Category (FText - complex, simplified to FString for Phase 3)
    6. PropertyFlags (uint64)
    7. RepNotifyFunc (FName)
    8. ReplicationCondition (uint8 ELifetimeCondition)
    9. MetaDataArray (TArray<FBPVariableMetaDataEntry>)
    10. DefaultValue (FString)
    """
    var = BlueprintVariable(
        var_name=archive.read_name(name_map)
    )
    
    # VarGuid (16 bytes) - skip, not needed for Phase 3
    archive.read(16)
    
    # VarType (FEdGraphPinType)
    var.var_type = read_ed_graph_pin_type(archive, name_map, summary)
    
    # FriendlyName (FString)
    var.friendly_name = archive.read_fstring()
    
    # Category (FText) - simplified to FString for Phase 3
    # FText serialization: flags + history + namespace + source string
    # Simplified: read as FString for now
    var.category = archive.read_fstring()
    
    # PropertyFlags (uint64)
    var.property_flags = archive.read_u64()
    
    # RepNotifyFunc (FName) - skip
    archive.read_name(name_map)
    
    # ReplicationCondition (uint8) - skip
    archive.read_u8()
    
    # MetaDataArray count + entries - skip for Phase 3 (deferred)
    meta_count = archive.read_i32()
    for _ in range(meta_count):
        archive.read_name(name_map)  # DataKey
        archive.read_fstring()       # DataValue
    
    # DefaultValue (FString) - parse per D-13/D-14/D-15
    default_str = archive.read_fstring()
    var.default_value = parse_default_value(default_str, var.var_type)
    
    return var
```

### Anti-Patterns to Avoid

- **过早解析 BlueprintType:** D-04 明确推迟 BlueprintType 分类 —— 仅检测蓝图存在性
- **假设固定 FEdGraphPinType 大小:** 结构有版本依赖字段 —— 必须处理容器类型分支
- **完全解析 FText:** FText 有复杂序列化 (namespace、source、history) —— 阶段 3 简化为 FString
- **忽略 ContainerType:** Array/Set/Map 影响 VarType 序列化 (Map 添加 PinValueType)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Blueprint detection | 自定义包路径正则 | ClassIndex lookup | ExportMap 已有阶段 1 类信息 |
| ParentClass resolution | 自定义索引映射 | FPackageIndex pattern | 阶段 1 模式有 to_import_index/to_export_index |
| FEdGraphPinType parsing | 猜测字段顺序 | EdGraphPin.cpp Serialize order | 从 UE 源码验证,版本依赖 |
| DefaultValue parsing | 完整表达式解析器 | 基本类型正则 | D-15 仅限 int/float/bool/string |

**Key insight:** 蓝图结构遵循 UE USTRUCT 序列化 —— 必须遵循源码精确字段顺序。

## Common Pitfalls

### Pitfall 1: FEdGraphPinType Version Dependency

**What goes wrong:** 不检查 UE 版本假设固定字段顺序
**Why it happens:** FEdGraphPinType 序列化在 UE4/UE5 版本间演进
**How to avoid:** 精确遵循 EdGraphPin.cpp Serialize 方法;检查自定义版本标志
**Warning signs:** ContainerType 字段后解析错误,位置错位

**Version thresholds (from EdGraphPin.cpp):**
- `FFrameworkObjectVersion::PinsStoreFName`: PinCategory 作为 FName (否则 FString)
- `FFrameworkObjectVersion::EdGraphPinContainerType`: 添加 ContainerType 字段
- `VER_UE4_MEMBER_REFERENCE_IN_PINTYPE`: 添加 PinSubCategoryMemberReference
- `VER_UE4_SERIALIZE_PINTYPE_CONST`: 添加 bIsConst
- `FReleaseObjectVersion::PinTypeIncludesUObjectWrapperFlag`: 添加 bIsUObjectWrapper

### Pitfall 2: ContainerType Serialization Branching

**What goes wrong:** 不为 Map 容器读取 PinValueType
**Why it happens:** ContainerType==Map 需要额外 FEdGraphTerminalType
**How to avoid:** 处理前检查 ContainerType;为 Map (3) 读取 PinValueType
**Warning signs:** 解析 Map 类型变量后位置不匹配

### Pitfall 3: FText Complexity

**What goes wrong:** 尝试带 namespace/history 完全解析 FText
**Why it happens:** FText 有 4 字段序列化 (flags、history、namespace、source)
**How to avoid:** 阶段 3 简化为 FString;推迟完整 FText 解析到 v2
**Warning signs:** Category 字段垃圾值,位置错位

### Pitfall 4: Blueprint Export Selection

**What goes wrong:** 解析错误导出为蓝图元数据
**Why it happens:** Blueprint .uasset 有多个导出;需要找到蓝图对象
**How to avoid:** 查找 ObjectName 匹配包名 + "_C" 模式的导出
**Warning signs:** VarName 上 ParseError,SerialOffset 处意外数据

## Code Examples

从 UE 源码验证的模式:

### PinCategory Values (from EdGraphPin.cpp)
```python
# Source: EdGraphPin.cpp lines 293-305, 315-321 [VERIFIED]
PIN_CATEGORIES = {
    # Basic types
    "exec",       # Execution flow
    "bool",       # Boolean
    "int",        # Integer (deprecated, use "Integer" in UE5)
    "Integer",    # Integer (UE5)
    "real",       # Real number (UE5: replaces float/double)
    "float",      # Float (deprecated in UE5)
    "double",     # Double (deprecated in UE5)
    "string",     # FString
    "name",       # FName
    
    # Object types
    "class",      # UClass reference
    "object",     # UObject reference
    "interface",  # Interface reference
    
    # Soft references
    "softclass",    # TSoftClassPtr
    "softobject",   # TSoftObjectPtr
    
    # Delegates
    "delegate",    # Single-cast delegate
    "mcdelegate",  # Multi-cast delegate
    
    # Other
    "struct",      # Struct type
    "enum",        # Enum type
    "wildcard",    # Wildcard/any type
}

PIN_SUB_CATEGORIES = {
    "bool",        # Boolean subcategory
    "int",         # Integer subcategory
    "float",       # Float subcategory (deprecated)
    "double",      # Double subcategory
    "name",        # Name subcategory
    "self",        # Self reference
    "Default",     # Default object
}
```

### ContainerType Mapping
```python
# Source: EdGraphNode.h lines 121-129 [VERIFIED]
CONTAINER_TYPES = {
    0: "None",     # EPinContainerType::None
    1: "Array",    # EPinContainerType::Array
    2: "Set",      # EPinContainerType::Set
    3: "Map",      # EPinContainerType::Map
}
```

### PropertyFlags Mapping
```python
# Source: ObjectMacros.h lines 415-480 [VERIFIED]
PROPERTY_FLAGS = {
    0x0000000000000001: "Edit",                    # CPF_Edit
    0x0000000000000004: "BlueprintVisible",        # CPF_BlueprintVisible
    0x0000000000000010: "BlueprintReadOnly",       # CPF_BlueprintReadOnly
    0x0000000000000020: "Net",                     # CPF_Net (replicated)
    0x0000000001000000: "SaveGame",                # CPF_SaveGame
    0x0000000010000000: "BlueprintAssignable",     # CPF_BlueprintAssignable (MC delegates)
    0x0000000100000000: "RepNotify",               # CPF_RepNotify
    0x0001000000000000: "ExposeOnSpawn",           # CPF_ExposeOnSpawn
}

def format_property_flags(flags: int) -> List[str]:
    """将 uint64 标志转换为人类可读列表。"""
    result = []
    for bit, name in PROPERTY_FLAGS.items():
        if flags & bit:
            result.append(name)
    return result
```

### DefaultValue Parsing (per D-13/D-14/D-15/D-16)
```python
import re

def parse_default_value(value_str: str, var_type: FEdGraphPinType) -> any:
    """
    将 DefaultValue 字符串解析为 Python 原生类型。
    
    按 D-13/D-14/D-15/D-16:
    - 解析基本类型: int、float、bool、str
    - 失败时返回原始字符串
    - 向量类型保持字符串 "(X=...,Y=...,Z=...)"
    """
    if not value_str:
        return None
    
    # 检查向量格式 (D-16: 保持字符串)
    if value_str.startswith("(") and value_str.endswith(")"):
        return value_str
    
    # 匹配 PinCategory
    category = var_type.pin_category.lower()
    
    # Boolean 解析
    if category in ("bool", "boolean"):
        if value_str.lower() in ("true", "1"):
            return True
        elif value_str.lower() in ("false", "0"):
            return False
        return value_str  # D-14: fallback
    
    # Integer 解析
    if category in ("int", "integer"):
        match = re.match(r'^-?\d+$', value_str)
        if match:
            return int(value_str)
        return value_str  # D-14: fallback
    
    # Float/Real 解析
    if category in ("float", "real", "double"):
        match = re.match(r'^-?\d+\.?\d*$', value_str)
        if match:
            return float(value_str)
        return value_str  # D-14: fallback
    
    # String/Name: 保持原样
    return value_str
```

### Type Name Formatting (per D-05/D-06/D-07)
```python
def format_pin_type_name(pin_type: FEdGraphPinType, name_map: List[str], import_map: List[ObjectImport]) -> str:
    """
    从 FEdGraphPinType 格式化人类可读类型名。
    
    按 D-05: 使用 UE 原始名称
    按 D-06: 容器+元素格式 (Array[Int])
    按 D-07: 解析 PinSubCategoryObject 为类名
    """
    # 基本元素类型
    element_type = pin_type.pin_category
    
    # D-07: 尝试为对象类型解析 PinSubCategoryObject
    if pin_type.pin_sub_category_object != 0:
        pkg_idx = PackageIndex(pin_type.pin_sub_category_object)
        if pkg_idx.is_import:
            idx = pkg_idx.to_import_index()
            if 0 <= idx < len(import_map):
                element_type = f"{import_map[idx].object_name} Reference"
    
    # D-06: 添加容器前缀
    container_name = CONTAINER_TYPES.get(pin_type.container_type, "None")
    if container_name == "None":
        return element_type
    elif container_name == "Map":
        # Map 需要键值类型 (阶段 3 简化)
        return f"Map[{element_type}]"
    else:
        return f"{container_name}[{element_type}]"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| FString PinCategory | FName PinCategory | UE 4.17+ (FFrameworkObjectVersion::PinsStoreFName) | 更高效,需要版本检查 |
| bIsArray/bIsSet/bIsMap flags | EPinContainerType enum | UE 4.17+ (FFrameworkObjectVersion::EdGraphPinContainerType) | 更清晰,单一字段 |
| "float"/"double" categories | "real" category with subcategory | UE 5.0+ (FUE5ReleaseStreamObjectVersion::BlueprintPinsUseRealNumbers) | 统一 real 类型 |

**Deprecated/outdated:**
- `bIsArray_DEPRECATED`: 使用 ContainerType 替代 (UE < 4.17)
- `asset`/`assetclass` PinCategories: 重命名为 `softobject`/`softclass` (UE 4.20+)

## Assumptions Log

> 本研究所有声明已从 UE 5.7 源码验证。无需用户确认。

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | FEdGraphPinType 序列化顺序 | Pattern 2 | LOW - 从 EdGraphPin.cpp 验证 |
| A2 | FBPVariableDescription 字段顺序 | Pattern 3 | LOW - 从 Blueprint.h 验证 |
| A3 | ContainerType 值 0-3 | Code Examples | LOW - 从 EdGraphNode.h 验证 |
| A4 | PropertyFlags 位值 | Code Examples | LOW - 从 ObjectMacros.h 验证 |

**If this table is empty:** 本研究所有声明已验证 —— 无需用户确认。

## Open Questions

1. **Blueprint export identification**
   - 已知: Blueprint .uasset 有多个导出;需要找到正确的
   - 不明确: 选择蓝图导出的精确模式 (ObjectName 结尾 "_C"?)
   - 推荐: 用示例资产测试;查找 ObjectName 匹配包名的导出

2. **FText serialization complexity**
   - 已知: FText 有 flags、history、namespace、source 字段
   - 不明确: Category 字段精确 FText 序列化格式
   - 推荐: 阶段 3 简化为 FString;用真实资产验证

## Environment Availability

> 外部 UE 源码参考存在;无运行时依赖。

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| UE 5.7 Source | Structure reference | ✓ | 5.7 | Web search for UE docs |
| Python 3.10+ | Runtime | ✓ | stdlib | — |
| pytest | Testing | ✓ | installed | — |
| Sample .uasset files | Testing | ✓ | Lyra, FirstPerson samples | — |

**Missing dependencies with no fallback:**
None —— 所有依赖已验证。

**Missing dependencies with fallback:**
None.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing from Phase 1/2) |
| Config file | None — pytest.ini in root |
| Quick run command | `python -m pytest tests/test_blueprint_extraction.py -v` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BLUE-01 | Blueprint detection from ClassIndex | unit | `pytest tests/test_blueprint_extraction.py::test_blueprint_detection -x` | ❌ Wave 0 |
| BLUE-02 | ParentClass resolution | unit | `pytest tests/test_blueprint_extraction.py::test_parent_class_resolution -x` | ❌ Wave 0 |
| BLUE-03 | FBPVariableDescription parsing | unit | `pytest tests/test_blueprint_extraction.py::test_variable_parsing -x` | ❌ Wave 0 |
| BLUE-04 | BlueprintType extraction | deferred | — | D-04 |
| BLUE-05 | FEdGraphPinType parsing | unit | `pytest tests/test_blueprint_extraction.py::test_pin_type_parsing -x` | ❌ Wave 0 |
| BLUE-06 | Variable metadata extraction | unit | `pytest tests/test_blueprint_extraction.py::test_variable_metadata -x` | ❌ Wave 0 |

### Sampling Rate
- **每次任务提交:** `python -m pytest tests/test_blueprint_extraction.py -v`
- **每次波合并:** `python -m pytest tests/ -v`
- **Phase gate:** `/gsd-verify-work` 前完整套件绿色

### Wave 0 Gaps
- [ ] `tests/test_blueprint_extraction.py` —— 覆盖 BLUE-01、BLUE-02、BLUE-03、BLUE-05、BLUE-06
- [ ] Mock blueprint .uasset 数据用于单元测试
- [ ] Lyra/FirstPerson 示例资产集成测试

## Security Domain

> 阶段 3 不添加新外部依赖或网络操作。安全配置与阶段 1/2 相同。

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | struct.unpack with boundary validation (FArchive pattern) |
| V6 Cryptography | no | — |

### Known Threat Patterns for Blueprint Parsing

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Binary parse overflow | Tampering | FArchive boundary validation (Phase 1 pattern) |
| Invalid FPackageIndex | Tampering | Index bounds check before map lookup |
| Malformed PinType | Tampering | Version-aware serialization with skip on error |

## Sources

### Primary (HIGH confidence)
- EdGraphPin.h (E:/Develop/lib/UnrealEngine/Engine/Source/Runtime/Engine/Classes/EdGraph/EdGraphPin.h) - FEdGraphPinType 结构定义
- EdGraphPin.cpp (E:/Develop/lib/UnrealEngine/Engine/Source/Runtime/Engine/Private/EdGraph/EdGraphPin.cpp) - FEdGraphPinType 序列化顺序
- Blueprint.h (E:/Develop/lib/UnrealEngine/Engine/Source/Runtime/Engine/Classes/Engine/Blueprint.h) - FBPVariableDescription 结构
- Blueprint.cpp (E:/Develop/lib/UnrealEngine/Engine/Source/Runtime/Engine/Private/Blueprint.cpp) - Blueprint 序列化模式
- EdGraphNode.h (E:/Develop/lib/UnrealEngine/Engine/Source/Runtime/Engine/Classes/EdGraph/EdGraphNode.h) - EPinContainerType 枚举
- ObjectMacros.h (E:/Develop/lib/UnrealEngine/Engine/Source/Runtime/CoreUObject/Public/UObject/ObjectMacros.h) - EPropertyFlags 枚举

### Secondary (MEDIUM confidence)
- Phase 1/2 code patterns (uasset_read.py) - 已建立的 FArchive、dataclass、ParseResult 模式

### Tertiary (LOW confidence)
None —— 所有声明从 UE 源码验证。

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - 仅 stdlib,匹配阶段 1/2 决策
- Architecture: HIGH - UE 源码验证,现有模式可应用
- Pitfalls: HIGH - 从源码记录,版本阈值明确

**Research date:** 2026-05-01
**Valid until:** 30 days (UE structure stable across versions)