# UE 反射系统对比分析报告

> 生成时间：2026-06-10  
> 对比对象：Unreal Engine 反射系统 vs uasset_read 项目实现  
> 版本：v0.5.0

---

## 目录

1. [UE 反射系统概述](#1-ue-反射系统概述)
2. [项目当前实现状态](#2-项目当前实现状态)
3. [对比分析](#3-对比分析)
4. [差距识别](#4-差距识别)
5. [改进建议](#5-改进建议)
6. [优先级排序](#6-优先级排序)

---

## 1. UE 反射系统概述

### 1.1 核心架构

Unreal Engine 的反射系统通过 UHT（Unreal Header Tool）在编译期生成反射数据，运行时通过以下类层次结构提供元数据访问：

```
UObject
└── UField (反射字段基类)
    ├── UStruct (结构体基类)
    │   ├── UClass (类定义)
    │   │   └── UBlueprintGeneratedClass (蓝图生成类)
    │   ├── UScriptStruct (脚本结构体)
    │   └── UFunction (函数定义)
    ├── UEnum (枚举定义)
    └── UProperty / FProperty (属性定义)
```

### 1.2 核心宏系统

| 宏 | 用途 | 生成的反射数据 |
|---|---|---|
| `UCLASS()` | 标记 UObject 派生类 | UClass 实例，包含类标志、属性列表、函数映射 |
| `USTRUCT()` | 标记结构体 | UScriptStruct 实例，包含字段列表 |
| `UENUM()` | 标记枚举 | UEnum 实例，包含枚举值名称和数值 |
| `UFUNCTION()` | 标记函数 | UFunction 实例，包含参数列表、返回类型、函数标志 |
| `UPROPERTY()` | 标记属性 | FProperty 实例，包含属性类型、标志、元数据 |
| `UINTERFACE()` | 标记接口 | UClass 实例（特殊），包含接口函数列表 |

### 1.3 标志位枚举

#### EClassFlags（类标志）

```cpp
enum EClassFlags : uint32 {
    CLASS_None                  = 0x00000000u,
    CLASS_Abstract              = 0x00000001u,  // 抽象类，不可实例化
    CLASS_CompiledFromBlueprint = 0x00000002u,  // 从蓝图编译而来
    CLASS_DefaultConfig         = 0x00000004u,  // 默认配置类
    CLASS_Config                = 0x00000008u,  // 配置类
    CLASS_Transient             = 0x00000010u,  // 瞬态类
    CLASS_Parsed                = 0x00000020u,  // 已解析
    CLASS_OptimizedMCast        = 0x00000040u,  // 优化强制转换
    CLASS_RequiredAPI           = 0x00000080u,  // 需要导出 API
    CLASS_DefaultToSelf         = 0x00000100u,  // 默认 Self 上下文
    CLASS_HasInstancedReference = 0x00000200u,  // 包含实例引用
    CLASS_Hidden                = 0x00000400u,  // 隐藏类
    CLASS_Deprecated            = 0x00000800u,  // 已弃用
    CLASS_HideDropDown          = 0x00001000u,  // 隐藏下拉
    CLASS_EditInlineNew         = 0x00002000u,  // 可内联编辑
    CLASS_Collide               = 0x00004000u,  // 可碰撞
    CLASS_ShouldShowInEditor    = 0x00008000u,  // 编辑器显示
    // ... 更多标志
};
```

#### EFunctionFlags（函数标志）

```cpp
enum EFunctionFlags : uint32 {
    FUNC_None                   = 0x00000000,
    FUNC_Final                  = 0x00000001,  // 最终函数，不可覆盖
    FUNC_RequiredAPI            = 0x00000002,  // 需要导出 API
    FUNC_BlueprintAuthorityOnly = 0x00000004,  // 仅蓝图权威访问
    FUNC_BlueprintCosmetic      = 0x00000008,  // 蓝图装饰函数
    FUNC_Net                    = 0x00000040,  // 网络函数
    FUNC_NetReliable            = 0x00000080,  // 可靠网络传输
    FUNC_NetRequest             = 0x00000100,  // 网络请求
    FUNC_Event                  = 0x00000200,  // 事件函数
    FUNC_NetResponse            = 0x00000400,  // 网络响应
    FUNC_Static                 = 0x00000800,  // 静态函数
    FUNC_NetMulticast           = 0x00001000,  // 多播函数
    FUNC_UbergraphFunction      = 0x00002000,  // UberGraph 函数
    FUNC_BlueprintCallable      = 0x00004000,  // 蓝图可调用
    FUNC_BlueprintEvent         = 0x00008000,  // 蓝图事件
    FUNC_BlueprintPure          = 0x00010000,  // 纯函数（无副作用）
    FUNC_EditorOnly             = 0x00020000,  // 仅编辑器
    FUNC_Const                  = 0x00040000,  // const 函数
    FUNC_NetValidate            = 0x00080000,  // 网络验证
    // ... 更多标志
};
```

#### EPropertyFlags（属性标志）

项目已完整实现（见 `constants.py` 第 315-376 行），包含 50+ 个 CPF_* 常量。

### 1.4 FProperty 类型层次

UE5 使用 FProperty 替代 UProperty，主要类型：

| FProperty 类型 | C++ 类型 | Blueprint Pin Category |
|---|---|---|
| FIntProperty | int32 | int |
| FInt8Property | int8 | int8 |
| FInt16Property | int16 | int16 |
| FInt64Property | int64 | int64 |
| FUInt16Property | uint16 | uint16 |
| FUInt32Property | uint32 | uint32 |
| FUInt64Property | uint64 | uint64 |
| FFloatProperty | float | float/real |
| FDoubleProperty | double | double |
| FBoolProperty | bool | bool |
| FByteProperty | uint8 | byte |
| FStrProperty | FString | string |
| FNameProperty | FName | name |
| FTextProperty | FText | text |
| FObjectProperty | UObject* | object |
| FClassProperty | UClass* | class |
| FSoftObjectProperty | TSoftObjectPtr | softobject |
| FSoftClassProperty | TSoftClassPtr | softclass |
| FWeakObjectProperty | TWeakObjectPtr | weakobject |
| FInterfaceProperty | TScriptInterface | interface |
| FStructProperty | UScriptStruct* | struct |
| FArrayProperty | TArray | array |
| FMapProperty | TMap | map |
| FSetProperty | TSet | set |
| FEnumProperty | UEnum* | byte (with enum) |
| FDelegateProperty | FScriptDelegate | delegate |
| FMulticastDelegateProperty | FMulticastScriptDelegate | multicastdelegate |
| FFieldPathProperty | FFieldPath | fieldpath |

### 1.5 蓝图反射数据流

```
蓝图编辑器
    ↓ UHT 处理
UBlueprint (源资产)
    ├── FunctionGraphs (函数图)
    ├── UberGraph (事件图)
    ├── MacroGraphs (宏图)
    └── NewVariables (FBPVariableDescription[])
    ↓ 编译
UBlueprintGeneratedClass (生成类)
    ├── FuncMap (函数映射)
    ├── ClassFlags (类标志)
    ├── Interfaces (接口列表)
    ├── ComponentTemplates (组件模板)
    ├── UberGraphFunction (UberGraph 函数)
    └── PropertyGuids (属性 GUID)
    ↓ 序列化
.uasset 文件
```

---

## 2. 项目当前实现状态

### 2.1 已实现功能

#### ✅ PropertyTag 解析（完整）

**位置**：`serializers/property_tags.py`, `parsers/property_parser.py`

- UE4 格式：传统 FName 类型 + 类型特定字段
- UE5 格式：FPropertyTypeName 递归树结构
- 版本门控：PropertyGuid、StructGuid 等字段
- 防御性检查：异常 count 值处理

#### ✅ 属性类型处理（40+ 类型）

**位置**：`parsers/property_types/__init__.py`

| 类别 | 已实现类型 |
|---|---|
| 标量 | Bool, Int8/16/32/64, UInt16/32/64, Byte, Float, Double, Str, Name, Guid |
| 对象引用 | Object, SoftObject, WeakObject, LazyObject, Class, SoftClass, Interface |
| 容器 | Array, Map, Set, Optional |
| 复杂 | Struct, Text, Enum, Delegate, MulticastDelegate |
| UE5/Verse | VerseString, VerseClass, VerseFunction, VerseDynamic, VerseCell, VerseValue, FieldPath |

#### ✅ CPF_* 属性标志位（完整）

**位置**：`constants.py` 第 315-376 行

50+ 个 CPF_* 常量，包括：
- 编辑标志：CPF_Edit, CPF_EditAnywhere, CPF_EditConst
- 蓝图可见性：CPF_BlueprintVisible, CPF_BlueprintReadWrite, CPF_BlueprintReadOnly
- 网络复制：CPF_Net, CPF_RepNotify, CPF_RepRetry
- 其他：CPF_Transient, CPF_SaveGame, CPF_Config, CPF_InstancedReference

#### ✅ UClass 原生字段解析

**位置**：`parsers/asset_types/uclass.py`

按 UE 序列化顺序解析：
1. UStruct 层：SuperStruct, Children, PropertiesSize, MinAlignment
2. UClass 层：FuncMap, ClassFlags, ClassWithin, ClassConfigName, Interfaces, ClassGeneratedBy, ClassDefaultObject

#### ✅ 蓝图变量提取

**位置**：`blueprint/variable_extractor.py`

- FBPVariableDescription 解析：VarName, VarGuid, VarType, Category, PropertyFlags
- CPF 标志到 UPROPERTY 说明符转换
- Pin Category 到 C++ 类型映射
- 组件检测（名称/标志）

#### ✅ Kismet 字节码属性处理

**位置**：`kismet/property_pointer.py`, `kismet/expressions/`

- FFieldPath：路径 + ResolvedOwner
- FKismetPropertyPointer：新旧格式兼容
- 变量引用表达式：EX_LocalVariable, EX_InstanceVariable, EX_DefaultVariable 等
- 赋值表达式：EX_Let, EX_LetBool, EX_LetObj 等

#### ✅ 类型映射系统

**位置**：`blueprint/variable_extractor.py`, `cpp_gen/cpp_type_mapper.py`, `kismet/translator.py`

- Pin Category → C++ 类型（20+ 映射）
- UE 路径 → C++ 类型（100+ 映射）
- Engine 类路径（A/U 前缀推断）
- Property 类型 → C++ 类型（30+ 映射）

### 2.2 未实现功能

#### ❌ EClassFlags 枚举常量

**现状**：ClassFlags 读取为 uint32，但未定义命名常量  
**影响**：无法解读类标志位含义（Abstract, Blueprintable, Transient 等）

#### ❌ EFunctionFlags 枚举常量

**现状**：FunctionFlags 存储为整数，但未定义命名常量  
**影响**：无法解读函数标志位含义（Final, BlueprintCallable, Static, Event 等）

#### ❌ UFunction 完整解析

**现状**：仅解析 FuncMap（函数名到引用映射），未解析函数内部结构  
**缺失**：
- 参数 FProperty 列表
- 返回属性
- FunctionFlags 详细标志
- 函数签名元数据

#### ❌ UEnum 导出解析

**现状**：仅从变量类型引用枚举，未解析枚举定义导出  
**缺失**：
- 枚举值名称和数值
- CppType 字段
- EnumFlags
- 枚举元数据

#### ❌ UScriptStruct 导出解析

**现状**：仅解析 StructProperty 值，未解析结构体定义导出  
**缺失**：
- 结构体属性布局（FProperty 链）
- StructFlags
- 大小/对齐元数据

#### ❌ FProperty 链解析

**现状**：仅通过 PropertyTag 解析属性值，未解析 UClass/UStruct 的原生属性链  
**缺失**：
- Children 字段指向的 FProperty 链表
- 属性偏移（内存布局）
- 属性元数据字典

#### ❌ 元数据字典完整提取

**现状**：部分提取 Category, Tooltip  
**缺失**：
- UCLASS/USTRUCT/UENUM 元数据键
- DisplayName, Documentation
- 自定义元数据

#### ❌ 接口函数追踪

**现状**：FImplementedInterface 解析但 PointerOffset 未使用  
**缺失**：
- 接口函数列表
- 接口实现追踪

#### ❌ 模板类型完整处理

**现状**：有限处理 TSubclassOf, TSoftObjectPtr  
**缺失**：
- TArray/Map/Set 容器类型参数
- Kismet 中的模板类型推断

---

## 3. 对比分析

### 3.1 反射类层次覆盖

| UE 反射类 | 项目实现状态 | 说明 |
|---|---|---|
| UObject | ✅ 部分 | 基础对象序列化 |
| UField | ⚠️ 隐式 | 通过 UStruct/UClass 间接处理 |
| UStruct | ✅ 部分 | SuperStruct, Children, PropertiesSize |
| UClass | ✅ 完整 | 原生字段 + PropertyTag |
| UBlueprintGeneratedClass | ✅ 完整 | 特有字段（ComponentTemplates 等） |
| UScriptStruct | ❌ 缺失 | 未解析结构体定义导出 |
| UFunction | ⚠️ 部分 | FuncMap 已解析，参数/返回未解析 |
| UEnum | ❌ 缺失 | 未解析枚举定义导出 |
| FProperty | ✅ 完整 | PropertyTag 解析 |

### 3.2 标志位枚举覆盖

| 枚举 | 项目实现 | 覆盖率 |
|---|---|---|
| EPropertyFlags (CPF_*) | ✅ 完整 | 50+ 常量 |
| EClassFlags (CLASS_*) | ❌ 缺失 | 0% |
| EFunctionFlags (FUNC_*) | ❌ 缺失 | 0% |
| EStructFlags | ❌ 缺失 | 0% |
| EEnumFlags | ❌ 缺失 | 0% |

### 3.3 FProperty 类型覆盖

| 类型 | 项目实现 | 说明 |
|---|---|---|
| 标量类型 | ✅ 完整 | Int/Float/Bool/String 等 |
| 对象引用 | ✅ 完整 | Object/SoftObject/WeakObject 等 |
| 容器类型 | ✅ 完整 | Array/Map/Set |
| 复杂类型 | ✅ 完整 | Struct/Enum/Text/Delegate |
| UE5 新增 | ✅ 完整 | Verse 类型、FieldPath、Optional |

### 3.4 蓝图反射数据流覆盖

| 阶段 | 项目实现 | 说明 |
|---|---|---|
| UBlueprint 源资产 | ✅ 完整 | NewVariables, FunctionGraphs, UberGraph |
| FBPVariableDescription | ✅ 完整 | 变量名、类型、标志、元数据 |
| UBlueprintGeneratedClass | ✅ 完整 | FuncMap, ClassFlags, ComponentTemplates |
| UClass 原生字段 | ✅ 完整 | 按 UE 序列化顺序解析 |
| UFunction 参数列表 | ❌ 缺失 | 仅函数引用，未解析参数 |
| UEnum 定义 | ❌ 缺失 | 仅引用，未解析定义 |
| UScriptStruct 定义 | ❌ 缺失 | 仅引用，未解析定义 |

---

## 4. 差距识别

### 4.1 高优先级差距

#### 4.1.1 EClassFlags 枚举常量缺失

**影响**：
- 无法判断类是否 Abstract（不可实例化）
- 无法判断类是否 Blueprintable（可作为蓝图基类）
- 无法判断类是否 Transient（瞬态）
- 无法判断类是否 Deprecated（已弃用）

**建议**：
```python
# constants.py 新增
CLASS_Abstract = 0x00000001
CLASS_CompiledFromBlueprint = 0x00000002
CLASS_DefaultConfig = 0x00000004
CLASS_Config = 0x00000008
CLASS_Transient = 0x00000010
# ... 完整定义
```

#### 4.1.2 EFunctionFlags 枚举常量缺失

**影响**：
- 无法判断函数是否 Final（不可覆盖）
- 无法判断函数是否 BlueprintCallable（蓝图可调用）
- 无法判断函数是否 BlueprintPure（纯函数）
- 无法判断函数是否 Static（静态函数）
- 无法判断函数是否 Event（事件函数）

**建议**：
```python
# constants.py 新增
FUNC_Final = 0x00000001
FUNC_RequiredAPI = 0x00000002
FUNC_BlueprintAuthorityOnly = 0x00000004
FUNC_BlueprintCosmetic = 0x00000008
FUNC_Net = 0x00000040
FUNC_Event = 0x00000200
FUNC_Static = 0x00000800
FUNC_BlueprintCallable = 0x00004000
FUNC_BlueprintEvent = 0x00008000
FUNC_BlueprintPure = 0x00010000
# ... 完整定义
```

### 4.2 中优先级差距

#### 4.2.1 UFunction 参数列表未解析

**影响**：
- 无法获取函数签名（参数类型、返回类型）
- 无法生成完整的 C++ 函数声明
- 无法验证蓝图函数调用的参数匹配

**建议**：
- 解析 UFunction 导出的 Children 字段（FProperty 链表）
- 提取 ReturnParm（CPF_ReturnParm 标志）
- 提取参数列表（CPF_Parm 标志，排除 CPF_ReturnParm）

#### 4.2.2 UEnum 导出未解析

**影响**：
- 无法获取枚举值名称和数值
- 无法在输出中显示枚举的完整定义
- 无法验证枚举值的合法性

**建议**：
- 解析 UEnum 导出的 Names 数组（TArray<TPair<FName, int64>>）
- 提取 CppType 字段
- 提取 EnumFlags

#### 4.2.3 UScriptStruct 导出未解析

**影响**：
- 无法获取结构体的字段布局
- 无法在输出中显示结构体的完整定义
- 无法验证结构体字段的存在性

**建议**：
- 解析 UScriptStruct 导出的 Children 字段（FProperty 链表）
- 提取 StructFlags
- 提取 Size/Alignment

### 4.3 低优先级差距

#### 4.3.1 FProperty 链解析

**现状**：通过 PropertyTag 解析属性值已足够大多数场景  
**建议**：仅在需要原生属性布局时实现（如内存分析工具）

#### 4.3.2 元数据字典完整提取

**现状**：Category, Tooltip 已提取  
**建议**：按需扩展，优先处理常用元数据（DisplayName, EditCondition 等）

#### 4.3.3 接口函数追踪

**现状**：FImplementedInterface 已解析  
**建议**：仅在需要接口函数调用分析时实现

---

## 5. 改进建议

### 5.1 短期改进（1-2 周）

#### 5.1.1 添加 EClassFlags 常量

**文件**：`constants.py`  
**工作量**：0.5 天  
**收益**：高

```python
# ============================================================================
# CLASS_* 类标志位常量（EClassFlags）
# 参考 UE 源码 Class.h
# ============================================================================

CLASS_Abstract = 0x00000001
CLASS_CompiledFromBlueprint = 0x00000002
CLASS_DefaultConfig = 0x00000004
CLASS_Config = 0x00000008
CLASS_Transient = 0x00000010
CLASS_Parsed = 0x00000020
CLASS_OptimizedMCast = 0x00000040
CLASS_RequiredAPI = 0x00000080
CLASS_DefaultToSelf = 0x00000100
CLASS_HasInstancedReference = 0x00000200
CLASS_Hidden = 0x00000400
CLASS_Deprecated = 0x00000800
CLASS_HideDropDown = 0x00001000
CLASS_EditInlineNew = 0x00002000
CLASS_Collide = 0x00004000
CLASS_ShouldShowInEditor = 0x00008000
CLASS_NotPlaceable = 0x00010000
CLASS_PerObjectConfig = 0x00020000
CLASS_ReplicationDataIsSetUp = 0x00040000
CLASS_EditInlineNew = 0x00080000
CLASS_Native = 0x00100000
CLASS_Constructed = 0x00200000
CLASS_LoadForClient = 0x00400000
CLASS_LoadForServer = 0x00800000
CLASS_CustomConstructor = 0x01000000
CLASS_Const = 0x02000000
CLASS_LayoutChanging = 0x04000000
CLASS_MatchedSerializers = 0x08000000
CLASS_ProjectUserConfig = 0x10000000
CLASS_NeedsDeferredDependencyLoading = 0x20000000
CLASS_ClassGroup = 0x40000000
CLASS_HasDefaults = 0x80000000
```

#### 5.1.2 添加 EFunctionFlags 常量

**文件**：`constants.py`  
**工作量**：0.5 天  
**收益**：高

```python
# ============================================================================
# FUNC_* 函数标志位常量（EFunctionFlags）
# 参考 UE 源码 Class.h
# ============================================================================

FUNC_None = 0x00000000
FUNC_Final = 0x00000001
FUNC_RequiredAPI = 0x00000002
FUNC_BlueprintAuthorityOnly = 0x00000004
FUNC_BlueprintCosmetic = 0x00000008
FUNC_Net = 0x00000040
FUNC_NetReliable = 0x00000080
FUNC_NetRequest = 0x00000100
FUNC_Event = 0x00000200
FUNC_NetResponse = 0x00000400
FUNC_Static = 0x00000800
FUNC_NetMulticast = 0x00001000
FUNC_UbergraphFunction = 0x00002000
FUNC_BlueprintCallable = 0x00004000
FUNC_BlueprintEvent = 0x00008000
FUNC_BlueprintPure = 0x00010000
FUNC_EditorOnly = 0x00020000
FUNC_Const = 0x00040000
FUNC_NetValidate = 0x00080000
```

#### 5.1.3 在 UClass 解析中使用标志常量

**文件**：`parsers/asset_types/uclass.py`  
**工作量**：0.5 天  
**收益**：中

```python
from uasset_read.constants import CLASS_Abstract, CLASS_CompiledFromBlueprint, ...

def _decode_class_flags(flags: uint32) -> List[str]:
    """解码类标志位为可读列表"""
    result = []
    if flags & CLASS_Abstract:
        result.append("Abstract")
    if flags & CLASS_CompiledFromBlueprint:
        result.append("CompiledFromBlueprint")
    # ... 其他标志
    return result
```

### 5.2 中期改进（2-4 周）

#### 5.2.1 UFunction 参数列表解析

**文件**：新增 `parsers/asset_types/ufunction.py`  
**工作量**：2 天  
**收益**：高

**实现步骤**：
1. 解析 UFunction 导出的 UStruct 层字段（SuperStruct, Children, PropertiesSize）
2. 遍历 Children FProperty 链表
3. 提取 ReturnParm（CPF_ReturnParm）
4. 提取参数列表（CPF_Parm，排除 CPF_ReturnParm）
5. 解析 FunctionFlags（uint32）

**输出结构**：
```python
{
    "function_name": "MyFunction",
    "function_flags": 0x00004001,  # FUNC_Final | FUNC_BlueprintCallable
    "flags_decoded": ["Final", "BlueprintCallable"],
    "return_type": {
        "name": "ReturnValue",
        "type": "IntProperty",
        "cpp_type": "int32",
    },
    "parameters": [
        {
            "name": "Param1",
            "type": "FloatProperty",
            "cpp_type": "float",
            "flags": ["CPF_Edit", "CPF_BlueprintVisible"],
        },
        # ...
    ],
}
```

#### 5.2.2 UEnum 导出解析

**文件**：新增 `parsers/asset_types/uenum.py`  
**工作量**：1 天  
**收益**：中

**实现步骤**：
1. 识别 UEnum 导出（通过 Class 名称或 ExportFlags）
2. 解析 Names 数组（TArray<TPair<FName, int64>>）
3. 解析 CppType（FName）
4. 解析 EnumFlags（uint32）

**输出结构**：
```python
{
    "enum_name": "EMyEnum",
    "cpp_type": "uint8",
    "values": [
        {"name": "Value1", "value": 0},
        {"name": "Value2", "value": 1},
        {"name": "Value3", "value": 2},
    ],
    "flags": 0,
}
```

#### 5.2.3 UScriptStruct 导出解析

**文件**：新增 `parsers/asset_types/uscriptstruct.py`  
**工作量**：1.5 天  
**收益**：中

**实现步骤**：
1. 识别 UScriptStruct 导出
2. 解析 UStruct 层字段（SuperStruct, Children, PropertiesSize）
3. 遍历 Children FProperty 链表
4. 提取字段列表

**输出结构**：
```python
{
    "struct_name": "FMyStruct",
    "size": 16,
    "alignment": 4,
    "fields": [
        {
            "name": "Field1",
            "type": "IntProperty",
            "offset": 0,
            "size": 4,
        },
        {
            "name": "Field2",
            "type": "FloatProperty",
            "offset": 4,
            "size": 4,
        },
    ],
}
```

### 5.3 长期改进（1-2 月）

#### 5.3.1 FProperty 链解析器

**文件**：新增 `parsers/property_chain.py`  
**工作量**：3 天  
**收益**：低（仅在需要原生布局时使用）

**实现步骤**：
1. 从 Children FPackageIndex 开始
2. 遍历 FProperty 链表（Next 字段）
3. 解析每个 FProperty 的类型特定字段
4. 计算属性偏移

#### 5.3.2 完整元数据提取

**文件**：增强 `parsers/property_parser.py`  
**工作量**：2 天  
**收益**：低

**实现步骤**：
1. 识别 Metadata 字典序列化位置
2. 提取所有键值对
3. 按 UCLASS/USTRUCT/UFUNCTION/UPROPERTY 分类

---

## 6. 优先级排序

### 6.1 实施优先级矩阵

| 改进项 | 影响 | 工作量 | 优先级 | 建议时间 |
|---|---|---|---|---|
| EClassFlags 常量 | 高 | 0.5 天 | P0 | 立即 |
| EFunctionFlags 常量 | 高 | 0.5 天 | P0 | 立即 |
| UClass 标志解码 | 中 | 0.5 天 | P1 | 1 周内 |
| UFunction 参数解析 | 高 | 2 天 | P1 | 2 周内 |
| UEnum 导出解析 | 中 | 1 天 | P2 | 3 周内 |
| UScriptStruct 导出解析 | 中 | 1.5 天 | P2 | 3 周内 |
| FProperty 链解析 | 低 | 3 天 | P3 | 按需 |
| 完整元数据提取 | 低 | 2 天 | P3 | 按需 |

### 6.2 实施路线图

```
第 1 周：EClassFlags + EFunctionFlags 常量定义
第 2 周：UClass 标志解码 + UFunction 参数解析
第 3 周：UEnum 导出解析 + UScriptStruct 导出解析
第 4 周：集成测试 + 文档更新
```

### 6.3 预期收益

完成 P0-P2 改进后：
- ✅ 可完整解读类标志（Abstract, Blueprintable 等）
- ✅ 可完整解读函数标志（BlueprintCallable, Static 等）
- ✅ 可生成完整的函数签名（参数 + 返回类型）
- ✅ 可输出完整的枚举定义（值名称 + 数值）
- ✅ 可输出完整的结构体定义（字段列表）

这将使项目的蓝图解析能力达到 **95%+** 的 UE 反射系统覆盖率。

---

## 附录

### A. UE 源码参考

| 文件 | 内容 |
|---|---|
| `Runtime/CoreUObject/Public/UObject/Class.h` | UClass, UStruct, UFunction 定义 |
| `Runtime/CoreUObject/Public/UObject/Field.h` | UField 基类 |
| `Runtime/CoreUObject/Public/UObject/UnrealType.h` | FProperty 类型层次 |
| `Runtime/CoreUObject/Public/UObject/PropertyFlags.h` | EPropertyFlags 定义 |
| `Runtime/Engine/Classes/Engine/BlueprintGeneratedClass.h` | UBlueprintGeneratedClass 定义 |

### B. 项目文件索引

| 文件 | 功能 |
|---|---|
| `constants.py` | CPF_* 常量定义 |
| `parsers/asset_types/uclass.py` | UClass 原生字段解析 |
| `parsers/property_parser.py` | PropertyTag 解析 |
| `parsers/property_types/__init__.py` | 属性类型处理 |
| `blueprint/variable_extractor.py` | 蓝图变量提取 |
| `kismet/translator.py` | 类型映射 |
| `cpp_gen/cpp_type_mapper.py` | UE 路径到 C++ 类型映射 |

### C. 术语表

| 术语 | 说明 |
|---|---|
| UHT | Unreal Header Tool，UE 头文件处理工具 |
| BPGC | BlueprintGeneratedClass，蓝图生成类 |
| FProperty | UE5 属性类，替代 UE4 的 UProperty |
| CPF | Class Property Flags，属性标志位 |
| FUNC | Function Flags，函数标志位 |
| CLASS | Class Flags，类标志位 |

---

*报告结束*
