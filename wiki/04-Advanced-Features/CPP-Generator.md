---
title: C++ 代码生成
section: cpp-gen
---

# C++ 代码生成

C++ 代码生成模块（Phase 56-66）负责将 UE 蓝图数据转换为 C++ 骨架代码，提供从 `.uasset` 解析结果到标准 UE C++ 头文件的完整映射。

## 模块结构

| 子模块 | 路径 | 职责 |
|--------|------|------|
| 类型映射 | `cpp_gen/cpp_type_mapper.py` | UE 类型路径 → C++ 类型名 |
| 属性映射 | `cpp_gen/cpp_uproperty_mapper.py` | CPF 标志 → UPROPERTY 标记 |
| 骨架提取 | `cpp_gen/extract_cpp_skeleton.py` | LinkerParseResult → CppClassIR |
| JSON IR | `cpp_gen/formatters/cpp_json_ir.py` | C++ 类骨架数据模型 |
| 头文件生成 | `cpp_gen/formatters/cpp_header_formatter.py` | CppClassIR → .h 文本 |
| 默认值格式化 | `cpp_gen/cpp_default_value_formatter.py` | 默认值/Transform/组件初始化 |
| 构造函数IR | `cpp_gen/cpp_constructor_ir_builder.py` | 构造函数 IR 构建 |
| 构造函数格式化 | `cpp_gen/cpp_constructor_formatter.py` | 构造函数文本生成 |

## 公共 API

```python
# 类型映射
UE_TO_CPP_TYPE_MAP: Dict[str, str]          # UE 类型路径 → C++ 类型名字典
ENGINE_CLASS_PATHS: Dict[str, str]          # Engine 类路径 → C++ 类名字典
ue_path_to_cpp_type(ue_type: str) -> str    # UE 类型路径 → C++ 类型名
ue_package_path_to_cpp_class(path: str) -> str  # 包路径 → C++ 类名

# 属性映射
CPF_TO_UPROPERTY_MAP: List[Tuple]           # CPF 标志 → UPROPERTY 标记映射规则
cpf_flags_to_uproperty_marks(flags, is_component=False) -> List[str]

# 骨架提取
extract_cpp_class_skeleton(result) -> CppClassIR  # LinkerParseResult → CppClassIR

# JSON IR 格式化
CppProperty       # 单个 C++ UPROPERTY 声明数据模型
CppHeaderMeta     # 头文件元数据模型
CppClassIR        # 完整 C++ 类骨架 IR 数据模型
CppMethodIR       # 蓝图函数 → C++ 方法声明
CppCallParameter  # 函数参数数据模型
CppCallStatement  # 调用语句参考数据模型
format_cpp_class_json(ir) -> Dict  # JSON IR 格式化函数

# .h 头文件生成
format_cpp_header(ir) -> str         # CppClassIR → .h 文本转换
format_cpp_call_statements(stmts) -> str  # 调用语句列表 → .cpp 文本

# 构造函数提取
extract_cpp_constructor(ir) -> str   # 生成完整构造函数文本
build_constructor_sections(ir) -> Dict  # 构建构造函数各节
format_cpp_constructor(ir) -> str    # 格式化构造函数文本

# 默认值格式化（Phase 59）
format_cpp_default_value(...)        # 格式化默认值
format_cpp_transform(...)            # 格式化 Transform 赋值
format_cpp_component_init(...)       # 格式化组件初始化
format_cpp_input_action_load(...)    # 格式化输入动作加载
```

## 数据模型

### CppProperty

单个 C++ UPROPERTY 声明。

| 属性 | 类型 | 说明 |
|------|------|------|
| `cpp_type` | `str` | C++ 类型名（如 `"USceneComponent*"`, `"FVector"`, `"float"`） |
| `name` | `str` | 属性名（如 `"DefaultSceneRoot"`, `"MoveSpeed"`） |
| `uproperty_marks` | `List[str]` | UPROPERTY 标记列表 |
| `category` | `str` | 属性类别（`"component"` 或 `"variable"`） |
| `default_value` | `Any` | 默认值（组件为 `None`） |
| `cpp_comment` | `str` | 可选注释（原 UE 类型参考） |

### CppHeaderMeta

头文件元数据。

| 属性 | 类型 | 说明 |
|------|------|------|
| `pragma_once` | `bool` | 是否包含 `#pragma once`（默认 `True`） |
| `includes` | `List[str]` | 包含的头文件列表 |
| `forward_declarations` | `List[str]` | 前向声明列表 |
| `generated_include` | `str` | `.generated.h` 包含路径（必须为最后一个 include） |

### CppClassIR

完整 C++ 类骨架 IR。

| 属性 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | C++ 类名（如 `"ABP_FirstPersonCharacter"`） |
| `parent_class` | `str` | 父类名（如 `"ACharacter"`） |
| `header_meta` | `CppHeaderMeta` | 头文件元数据 |
| `properties` | `List[CppProperty]` | 属性列表（组件 + 变量） |
| `methods` | `List[CppMethodIR]` | 方法列表（Phase 57 填充） |
| `constructor` | `Dict` | 构造函数数据（Phase 59 填充） |

### CppMethodIR

蓝图函数 → C++ 方法声明（Phase 57）。

| 属性 | 类型 | 说明 |
|------|------|------|
| `cpp_name` | `str` | C++ 函数名（已清理） |
| `return_type` | `str` | C++ 返回类型（默认 `"void"`） |
| `parameters` | `List[CppCallParameter]` | 参数列表 |
| `ufunction_specifiers` | `List[str]` | UFUNCTION 宏标记 |
| `is_override` | `bool` | 是否为 `bOverrideFunction` |
| `is_const` | `bool` | `const` 方法修饰符 |
| `is_static` | `bool` | `static` 方法修饰符 |
| `is_pure` | `bool` | 纯函数（无副作用） |
| `is_event` | `bool` | 事件函数 |
| `access_modifier` | `str` | 访问修饰符（`public`/`protected`/`private`） |
| `body_text` | `str` | Kismet 反编译函数体文本（Phase 66） |

## 使用示例

```python
from uasset_read import parse_uasset_with_linker
from uasset_read.cpp_gen import (
    extract_cpp_class_skeleton,
    format_cpp_header,
    format_cpp_class_json,
)

# 1. 解析蓝图资产
result = parse_uasset_with_linker("path/to/BP_Character.uasset")

# 2. 提取 C++ 类骨架
class_ir = extract_cpp_class_skeleton(result)

# 3. 生成 .h 头文件文本
header_text = format_cpp_header(class_ir)
print(header_text)

# 4. 生成 JSON IR 输出
json_output = format_cpp_class_json(class_ir)
```

## UE 类型映射

### 核心类型映射表

| UE 类型路径 | C++ 类型 |
|-------------|----------|
| `/Script/CoreUObject.Vector` | `FVector` |
| `/Script/CoreUObject.Rotator` | `FRotator` |
| `/Script/CoreUObject.Transform` | `FTransform` |
| `/Script/CoreUObject.Vector2D` | `FVector2D` |
| `/Script/CoreUObject.LinearColor` | `FLinearColor` |
| `/Script/CoreUObject.Name` | `FName` |
| `/Script/CoreUObject.Text` | `FText` |
| `/Script/CoreUObject.String` | `FString` |
| `/Script/CoreUObject.Guid` | `FGuid` |
| `/Script/Engine.HitResult` | `FHitResult` |
| `/Script/Engine.TimerHandle` | `FTimerHandle` |
| `/Script/Engine.GameplayTag` | `FGameplayTag` |

### Actor 类型

| UE 类型路径 | C++ 类型 |
|-------------|----------|
| `/Script/Engine.Actor` | `AActor` |
| `/Script/Engine.Pawn` | `APawn` |
| `/Script/Engine.Character` | `ACharacter` |
| `/Script/Engine.Controller` | `AController` |
| `/Script/Engine.PlayerController` | `APlayerController` |
| `/Script/Engine.GameModeBase` | `AGameModeBase` |

### Component 类型

| UE 类型路径 | C++ 类型 |
|-------------|----------|
| `/Script/Engine.SceneComponent` | `USceneComponent` |
| `/Script/Engine.ActorComponent` | `UActorComponent` |
| `/Script/Engine.StaticMeshComponent` | `UStaticMeshComponent` |
| `/Script/Engine.SkeletalMeshComponent` | `USkeletalMeshComponent` |
| `/Script/Engine.CameraComponent` | `UCameraComponent` |
| `/Script/Engine.SpringArmComponent` | `USpringArmComponent` |
| `/Script/Engine.CapsuleComponent` | `UCapsuleComponent` |
| `/Script/Engine.ArrowComponent` | `UArrowComponent` |

### 基本类型

| UE 类型 | C++ 类型 |
|---------|----------|
| `float` | `float` |
| `double` | `double` |
| `bool` | `bool` |
| `int` / `int32` | `int32` |
| `int64` | `int64` |
| `byte` | `uint8` |
| `name` | `FName` |
| `text` | `FText` |
| `string` | `FString` |

### 类型推导启发式

对于未知类型路径，系统使用以下启发式规则：

- **Actor 后缀**（`Actor`, `Pawn`, `Character`, `Controller`, `GameMode` 等）→ `A` 前缀
- **Component 后缀** → `U` 前缀
- **默认** → `U` 前缀（UObject）

## CPF → UPROPERTY 映射

| CPF 标志 | UPROPERTY 标记 |
|----------|----------------|
| `CPF_Edit` + `CPF_BlueprintVisible` | `EditAnywhere, BlueprintReadWrite` |
| `CPF_EditAnywhere` | `EditAnywhere` |
| `CPF_EditInstanceOnly` | `EditInstanceOnly` |
| `CPF_BlueprintReadOnly` | `BlueprintReadOnly` |
| `CPF_BlueprintReadWrite` | `BlueprintReadWrite` |
| `CPF_InstancedReference` | `Instanced` |
| `CPF_BlueprintAssignable` | `BlueprintAssignable` |
| `CPF_BlueprintCallable` | `BlueprintCallable` |
| `CPF_Replicated` | `Replicated` |
| `CPF_Net`（无 Replicated 时） | `Net` |
| `CPF_Transient` | `Transient` |
| `CPF_DuplicateTransient` | `DuplicateTransient` |
| `CPF_Config` | `Config` |
| `CPF_SaveGame` | `SaveGame` |
| `CPF_NoClear` | `NoClear` |
| `CPF_ExposeOnSpawn` | `ExposeOnSpawn` |
| `CPF_Interp` | `Interp` |
| `CPF_RepNotify` | `RepNotify` |
| `CPF_Protected` | `Protected` |
| `CPF_AdvancedDisplay` | `AdvancedDisplay` |

### 组件默认标记

对于组件属性（`is_component=True`），如果未设置明确的可见性/编辑标志，自动添加：
- `VisibleAnywhere`
- `BlueprintReadOnly`

## 函数标志位（UFunctionFlags）

| 标志 | 值 | 说明 |
|------|-----|------|
| `FUNC_Final` | `0x00000001` | 最终函数（不可重写） |
| `FUNC_BlueprintAuthorityOnly` | `0x00000004` | 仅权威端执行 |
| `FUNC_BlueprintCosmetic` | `0x00000008` | 仅 cosmetic 执行 |
| `FUNC_Exec` | `0x00000100` | 控制台命令 |
| `FUNC_Native` | `0x00000200` | 原生函数 |
| `FUNC_Event` | `0x00000400` | 事件函数 |
| `FUNC_UbergraphFunction` | `0x00001000` | Ubergraph 函数 |
| `FUNC_Static` | `0x00002000` | 静态函数 |
| `FUNC_BlueprintCallable` | `0x00040000` | 蓝图可调用 |
| `FUNC_BlueprintPure` | `0x00080000` | 纯函数（无副作用） |
| `FUNC_Const` | `0x00200000` | const 函数 |
| `FUNC_BlueprintEvent` | `0x08000000` | 蓝图事件 |

## 头文件生成模板

生成的 `.h` 文件遵循 UE 标准格式：

```cpp
#pragma once

#include "CoreMinimal.h"
#include "Engine/GameFramework/Character.h"
#include "ABP_FirstPersonCharacter.generated.h"

UCLASS(Blueprintable)
class ABP_FirstPersonCharacter : public ACharacter
{
    GENERATED_BODY()

public:
    ABP_FirstPersonCharacter();

protected:
    // Components
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Instanced, Category = "Components", meta = (AllowPrivateAccess = "true"))
    USceneComponent* DefaultSceneRoot;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Instanced, Category = "Components", meta = (AllowPrivateAccess = "true"))
    USkeletalMeshComponent* FirstPersonMesh;

    // Variables
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Movement")
    float MoveSpeed = 100.0f;

public:
    // Blueprint Functions
    UFUNCTION(BlueprintCallable)
    void Move(double LeftRight, double ForwardBackward);

    void PrimaryThumbstick(double Axis_X, double Axis_Y) override;
};
```

## JSON IR 输出格式

```json
{
  "cpp_class": {
    "name": "ABP_FirstPersonCharacter",
    "parent_class": "ACharacter",
    "header_meta": {
      "pragma_once": true,
      "includes": ["\"Engine/GameFramework/Character.h\""],
      "forward_declarations": [],
      "generated_include": "\"ABP_FirstPersonCharacter.generated.h\""
    },
    "properties": [
      {
        "cpp_type": "USceneComponent*",
        "name": "DefaultSceneRoot",
        "uproperty_marks": ["VisibleAnywhere", "BlueprintReadOnly", "Instanced"],
        "category": "component"
      }
    ],
    "methods": [],
    "constructor": {
      "component_creations": [],
      "component_assignments": [],
      "default_values": []
    }
  },
  "output_version": "1.0"
}
```

## 名称清理规则

### 组件名称清理

系统会移除以下 UE 内部后缀：

| 模式 | 示例 | 结果 |
|------|------|------|
| `_GEN_VARIABLE$` | `FirstPersonMesh_GEN_VARIABLE` | `FirstPersonMesh` |
| `_\d+__[A-F0-9]+$` | `CameraComponent_0__CCE3C0B4` | `CameraComponent` |
| `_\d+$` | `Arrow_1` | `Arrow` |

### 类名简化

| 输入 | 输出 |
|------|------|
| `/Game/FirstPerson/Blueprints/BP_FirstPersonCharacter` | `BP_FirstPersonCharacter` |
| `Game_FirstPerson_Blueprints_BP_FirstPersonCharacter` | `BP_FirstPersonCharacter` |

### C++ 标识符清理

| 输入 | 输出 |
|------|------|
| `Left / Right` | `LeftRight` |
| `Primary Thumbstick` | `PrimaryThumbstick` |
| `2DValue` | `_2DValue` |

## 蓝图元数据过滤

以下蓝图内部元数据属性**不会**作为 C++ 成员变量输出：

| 类别 | 属性名 |
|------|--------|
| 蓝图系统 | `BlueprintSystemVersion`, `BlueprintGuid`, `bLegacyNeedToPurgeSkelRefs` |
| 构造脚本 | `SimpleConstructionScript` |
| 图相关 | `UbergraphPages`, `FunctionGraphs`, `NewVariables`, `CategorySorting` |
| 类引用 | `ThumbnailInfo`, `GeneratedClass`, `PropertyGuids` |
| Ubergraph | `UbergraphFunction`, `UbergraphFrame` |

## 输入动作变量提取（P2）

从 `K2Node_EnhancedInputAction` 节点自动提取输入动作引用，生成 `UInputAction*` 成员变量：

```cpp
UPROPERTY(EditAnywhere, Category = "Input")
UInputAction* IA_Jump;  // Input Action: /Game/Input/IA_Jump.IA_Jump
```

## 函数体注入（Phase 66）

Kismet 反编译的 `cpp_code` 会自动注入到 `CppMethodIR.body_text`，匹配逻辑：

1. **精确匹配**：`function_name == cpp_name`
2. **清理后匹配**：`function_name` 清理后 == `cpp_name`
3. **大小写不敏感匹配**

## 相关章节

- [[Kismet]] — Kismet 字节码反编译
- [[Blueprint]] — 蓝图变量/组件/元数据提取
- [[Linker]] — 对象链接器与 PackageLinker
- [[渲染器系统]] — 渲染器与输出格式
