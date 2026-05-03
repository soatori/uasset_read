# C++ Conversion - 蓝图→C++转换参考

本文档提供蓝图解析结果到 C++ 代码的转换参考，帮助 AI 从 JSON 输出推导 C++ 函数签名和成员结构。

**API版本:** output_version: "3.0" (Phase 14冻结)

**重要说明:** 本 skill 提供参考级别信息，不生成完整 C++ 代码。需要手动补充实现细节。

---

## 1. 蓝图→C++转换概述

### 1.1 转换流程

从 `parse_uasset()` 输出推导 C++ 结构的流程：

```
蓝图.uasset → parse_uasset() → JSON输出 → C++推导
                                   ↓
                           graphs_summary → 函数签名
                           exports → 类成员
                           properties → UPROPERTY
                           transforms → 组件变换
```

### 1.2 skill提供的信息范围

| 信息类型 | skill提供 | 需手动补充 |
|----------|-----------|------------|
| 函数签名 | ✓ 函数名+参数类型 | 函数体实现 |
| 类继承 | ✓ parent_class | 头文件包含 |
| 成员变量 | ✓ 名称+类型+默认值 | 完整UPROPERTY宏 |
| 组件引用 | ✓ 类型+名称 | CreateDefaultSubobjects调用 |
| 组件变换 | ✓ Location/Rotation/Scale | 精确的设置代码 |

---

## 2. EventGraph→C++函数映射

### 2.1 事件节点映射表

| EventGraph节点 | C++函数签名 | 调用时机 |
|-----------------|-------------|----------|
| `Event BeginPlay` | `virtual void BeginPlay() override` | 游戏开始 |
| `Event Tick` | `virtual void Tick(float DeltaTime) override` | 每帧 |
| `Event Destroyed` | `virtual void OnDestroyed() override` | 销毁时 |
| `Event Construction Script` | `virtual void OnConstruction(const FTransform& Transform) override` | 构造时 |
| `Event ActorBeginOverlap` | `virtual void NotifyActorBeginOverlap(AActor* OtherActor) override` | 碰撞开始 |
| `Event ActorEndOverlap` | `virtual void NotifyActorEndOverlap(AActor* OtherActor) override` | 碰撞结束 |
| `Event AnyDamage` | `virtual float TakeDamage(float DamageAmount, ...) override` | 受伤害 |

### 2.2 从JSON推导函数签名

```python
from uasset_read import parse_uasset, format_json_summary

result = parse_uasset("BP_FirstPersonCharacter.uasset")
output = format_json_summary(result)

# 遍历执行流程
for flow in output.get("graphs_summary", []):
    if flow["graph_name"] == "EventGraph":
        for exec_flow in flow["execution_flows"]:
            func_name = exec_flow["function_name"]
            params = exec_flow["params"]

            # 推导C++签名
            cpp_signature = derive_cpp_signature(func_name, params)
            print(f"蓝图: {func_name} → C++: {cpp_signature}")

def derive_cpp_signature(func_name: str, params: list) -> str:
    """从函数名和参数推导C++签名"""
    # 常见事件映射
    event_map = {
        "ReceiveBeginPlay": "void BeginPlay() override",
        "ReceiveTick": "void Tick(float DeltaTime) override",
        "ReceiveDestroyed": "void OnDestroyed() override",
        "ReceiveActorBeginOverlap": "void NotifyActorBeginOverlap(AActor* OtherActor) override",
    }

    if func_name in event_map:
        return event_map[func_name]

    # 通用推导
    param_str = ", ".join([p["type"] for p in params])
    return f"void {func_name}({param_str})"
```

### 2.3 C++实现模板

**蓝图EventGraph:**
```
Event BeginPlay
  → Get Player Controller
  → Print String ("Hello")
```

**对应C++:**
```cpp
// MyCharacter.h
class AMyCharacter : public ACharacter
{
    virtual void BeginPlay() override;
};

// MyCharacter.cpp
void AMyCharacter::BeginPlay()
{
    Super::BeginPlay();

    APlayerController* PC = Cast<APlayerController>(GetController());
    if (PC)
    {
        UKismetSystemLibrary::PrintString(
            this,
            FString("Hello"),
            true,
            false,
            FName("None")
        );
    }
}
```

---

## 3. 函数签名推导

### 3.1 function_name字段

`graphs_summary[].execution_flows[].function_name` 提供函数名：

| function_name | C++函数 | 需override |
|---------------|---------|------------|
| `ReceiveBeginPlay` | `BeginPlay()` | ✓ |
| `ReceiveTick` | `Tick(float)` | ✓ |
| `ReceiveDestroyed` | `OnDestroyed()` | ✓ |
| `GetActorLocation` | `GetActorLocation()` | ✗ (已有) |
| `SetActorLocation` | `SetActorLocation(...)` | ✗ |
| `PrintString` | `UKismetSystemLibrary::PrintString(...)` | ✗ |

### 3.2 params字段

`params` 数组提供参数类型列表：

```json
{
  "function_name": "ReceiveTick",
  "params": [{"type": "float"}]
}
```

**推导：** `void Tick(float DeltaTime) override`

### 3.3 常见蓝图函数→C++映射

| 蓝图函数 | C++调用 | 头文件 |
|----------|---------|--------|
| `Print String` | `UKismetSystemLibrary::PrintString(...)` | KismetSystemLibrary |
| `Get Actor Location` | `AActor::GetActorLocation()` | Actor.h |
| `Set Actor Location` | `AActor::SetActorLocation(...)` | Actor.h |
| `Spawn Actor` | `UGameplayStatics::BeginDeferredActorSpawnFromClass(...)` | GameplayStatics |
| `Get Game Instance` | `UWorld::GetGameInstance()` | World.h |
| `Get World` | `UObject::GetWorld()` | UObject.h |
| `Destroy Actor` | `AActor::Destroy()` | Actor.h |
| `Set Timer` | `UKismetSystemLibrary::K2_SetTimer(...)` | KismetSystemLibrary |

---

## 4. 变量→C++成员映射

### 4.1 BlueprintVariable→UPROPERTY

蓝图变量对应 C++ 的 `UPROPERTY` 成员：

**蓝图变量JSON:**
```json
{
  "name": "Health",
  "type": "FloatProperty",
  "value": 100.0,
  "is_component": false,
  "metadata": {
    "Category": "Stats",
    "BlueprintReadWrite": "true",
    "EditAnywhere": "true"
  }
}
```

**对应C++:**
```cpp
UPROPERTY(Category = "Stats", BlueprintReadWrite, EditAnywhere)
float Health = 100.0f;
```

### 4.2 类型映射表

| 蓝图类型 | C++类型 | 默认值示例 |
|----------|---------|------------|
| `BoolProperty` | `bool` | `bool bIsAlive = true;` |
| `IntProperty` | `int32` | `int32 Score = 0;` |
| `FloatProperty` | `float` | `float Health = 100.0f;` |
| `StrProperty` | `FString` | `FString PlayerName = "Player";` |
| `NameProperty` | `FName` | `FName MyName = FName("MyName");` |
| `Vector` | `FVector` | `FVector Location = FVector(0,0,0);` |
| `Rotator` | `FRotator` | `FRotator Rotation = FRotator(0,0,0);` |
| `ObjectProperty` | `UObject*` | `UObject* MyObject = nullptr;` |
| `SoftObjectProperty` | `TSoftObjectPtr<UObject>` | `TSoftObjectPtr<UObject> AssetRef;` |

### 4.3 元数据→UPROPERTY宏

| 元数据标签 | UPROPERTY宏 |
|------------|-------------|
| `Category` | `Category = "..."` |
| `BlueprintReadWrite` | `BlueprintReadWrite` |
| `BlueprintReadOnly` | `BlueprintReadOnly` |
| `EditAnywhere` | `EditAnywhere` |
| `EditDefaultsOnly` | `EditDefaultsOnly` |
| `EditInstanceOnly` | `EditInstanceOnly` |
| `VisibleAnywhere` | `VisibleAnywhere` |
| `VisibleDefaultsOnly` | `VisibleDefaultsOnly` |
| `Transient` | `Transient` |
| `Replicated` | `ReplicatedUsing = OnRep_...` |

### 4.4 从JSON推导成员变量

```python
def derive_cpp_property(prop: dict) -> str:
    """从JSON属性推导C++ UPROPERTY"""
    type_map = {
        "FloatProperty": "float",
        "IntProperty": "int32",
        "BoolProperty": "bool",
        "StrProperty": "FString",
        "ObjectProperty": "UObject*",
    }

    cpp_type = type_map.get(prop["type"], "UObject*")
    name = prop["name"]
    value = prop.get("value", "")

    # 构建UPROPERTY宏
    meta = prop.get("metadata", {})
    uprop_parts = []

    if "Category" in meta:
        uprop_parts.append(f"Category = \"{meta['Category']}\"")
    if meta.get("BlueprintReadWrite"):
        uprop_parts.append("BlueprintReadWrite")
    if meta.get("EditAnywhere"):
        uprop_parts.append("EditAnywhere")

    uprop = "UPROPERTY(" + ", ".join(uprop_parts) + ")"

    # 构建声明
    default = ""
    if value is not None:
        if cpp_type == "float":
            default = f" = {value}f"
        elif cpp_type == "int32":
            default = f" = {value}"
        elif cpp_type == "bool":
            default = f" = {str(value).lower()}"
        elif cpp_type == "FString":
            default = f" = FString(\"{value}\")"

    return f"{uprop}\n{cpp_type} {name}{default};"
```

---

## 5. 组件→C++成员映射

### 5.1 is_component字段

当 `is_component: true`，变量是组件引用：

**JSON示例:**
```json
{
  "name": "CharacterMesh",
  "type": "ObjectProperty",
  "value": "SkeletalMeshComponent",
  "is_component": true
}
```

**对应C++:**
```cpp
UPROPERTY(VisibleAnywhere)
USkeletalMeshComponent* CharacterMesh;
```

### 5.2 组件类型映射

| 组件类型 | C++类型 | 头文件 |
|----------|---------|--------|
| `SkeletalMeshComponent` | `USkeletalMeshComponent*` | SkeletalMeshComponent |
| `StaticMeshComponent` | `UStaticMeshComponent*` | StaticMeshComponent |
| `CameraComponent` | `UCameraComponent*` | CameraComponent |
| `CapsuleComponent` | `UCapsuleComponent*` | CapsuleComponent |
| `CharacterMovementComponent` | `UCharacterMovementComponent*` | CharacterMovementComponent |
| `AudioComponent` | `UAudioComponent*` | AudioComponent |
| `SceneComponent` | `USceneComponent*` | SceneComponent |

### 5.3 transforms字段

组件变换属性对应 C++ 设置代码：

**JSON示例:**
```json
{
  "transforms": {
    "RelativeLocation": {"X": 0, "Y": 0, "Z": -90},
    "RelativeRotation": {"Roll": 0, "Pitch": 0, "Yaw": 0},
    "RelativeScale3D": {"X": 1.0, "Y": 1.0, "Z": 1.0}
  }
}
```

**对应C++:**
```cpp
CharacterMesh->SetRelativeLocation(FVector(0.0f, 0.0f, -90.0f));
CharacterMesh->SetRelativeRotation(FRotator(0.0f, 0.0f, 0.0f));
CharacterMesh->SetRelativeScale3D(FVector(1.0f, 1.0f, 1.0f));
```

### 5.4 组件初始化

蓝图组件在 C++ 中通过 `CreateDefaultSubobject` 创建：

```cpp
// 构造函数中
AMyCharacter::AMyCharacter()
{
    CharacterMesh = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("CharacterMesh"));
    CharacterMesh->SetupAttachment(GetCapsuleComponent());
    CharacterMesh->SetRelativeLocation(FVector(0.0f, 0.0f, -90.0f));

    FirstPersonCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("FirstPersonCamera"));
    FirstPersonCamera->SetupAttachment(GetCapsuleComponent());
    FirstPersonCamera->SetRelativeLocation(FVector(0.0f, 0.0f, 64.0f));
}
```

---

## 6. 完整转换示例

### 6.1 BP_FirstPersonCharacter → C++对照

**蓝图解析结果:**
```json
{
  "exports": [
    {
      "name": "BP_FirstPersonCharacter_C",
      "class": "BlueprintGeneratedClass",
      "parent_class": "FirstPersonCharacter",
      "properties": [
        {"name": "CharacterMesh", "type": "ObjectProperty", "is_component": true},
        {"name": "FirstPersonCamera", "type": "ObjectProperty", "is_component": true}
      ],
      "transforms": {
        "CharacterMesh": {"RelativeLocation": {"X": 0, "Y": 0, "Z": -90}},
        "FirstPersonCamera": {"RelativeLocation": {"X": 0, "Y": 0, "Z": 64}}
      }
    }
  ],
  "graphs_summary": [
    {
      "graph_name": "EventGraph",
      "execution_flows": [
        {"function_name": "ReceiveBeginPlay", "params": []}
      ]
    }
  ]
}
```

**推导C++结构:**
```cpp
// BP_FirstPersonCharacter.h
#pragma once
#include "CoreMinimal.h"
#include "FirstPersonCharacter.h"
#include "BP_FirstPersonCharacter.generated.h"

UCLASS()
class ABP_FirstPersonCharacter : public AFirstPersonCharacter
{
    GENERATED_BODY()

public:
    virtual void BeginPlay() override;

protected:
    UPROPERTY(VisibleAnywhere)
    USkeletalMeshComponent* CharacterMesh;

    UPROPERTY(VisibleAnywhere)
    UCameraComponent* FirstPersonCamera;
};

// BP_FirstPersonCharacter.cpp
#include "BP_FirstPersonCharacter.h"

ABP_FirstPersonCharacter::ABP_FirstPersonCharacter()
{
    CharacterMesh = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("CharacterMesh"));
    CharacterMesh->SetupAttachment(GetCapsuleComponent());
    CharacterMesh->SetRelativeLocation(FVector(0.0f, 0.0f, -90.0f));

    FirstPersonCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("FirstPersonCamera"));
    FirstPersonCamera->SetupAttachment(GetCapsuleComponent());
    FirstPersonCamera->SetRelativeLocation(FVector(0.0f, 0.0f, 64.0f));
}

void ABP_FirstPersonCharacter::BeginPlay()
{
    Super::BeginPlay();
    // EventGraph中的后续逻辑需要手动补充
}
```

### 6.2 FirstPerson vs FirstPersonC对照

UE Samples 提供蓝图和 C++ 对照版本：

| 版本 | 资产路径 |
|------|----------|
| 蓝图版 | `Samples/FirstPerson/Content/FirstPerson/Blueprints/` |
| C++版 | `Samples/FirstPersonC/Source/FirstPersonC/` |

**对照学习：**
```python
from uasset_read import parse_uasset

# 解析蓝图版
bp_result = parse_uasset("E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset")

# 获取父类名称
for export in bp_result.export_map:
    if "BlueprintGeneratedClass" in export.class_name:
        parent = export.parent_class
        print(f"蓝图父类: {parent}")
        print(f"  → C++类名: A{parent}")
```

---

## 7. 转换限制说明

### 7.1 skill不提供的信息

| 信息类型 | 原因 |
|----------|------|
| 函数体实现 | 需要理解完整执行流程，超出解析范围 |
| 头文件包含 | 需要知道依赖模块 |
| 完整UPROPERTY宏 | 元数据可能不完整 |
| 网络复制代码 | 需要RepNotify函数 |
| 构造函数完整代码 | 需要组件依赖关系 |

### 7.2 需要手动补充

- **函数体** — EventGraph执行流程转代码逻辑
- **模块依赖** — Build.cs 中的 PublicDependencyModuleNames
- **头文件** — 包含正确的 UE 头文件
- **网络复制** — GetLifetimeReplicatedProps 设置
- **初始化顺序** — 组件创建和附加顺序

---

## 8. 参考链接

- **蓝图语义:** [blueprint-semantics.md](blueprint-semantics.md)
- **节点类型:** [node-types.md](node-types.md)
- **常见模式:** [common-patterns.md](common-patterns.md)
- **测试资产:** FirstPerson模板 (UE Samples)

---

*API版本: output_version: "3.0"*
*Skill: uasset-read*
*最后更新: 2026-05-03*