# C++ Conversion - C++转换示例

本文档演示如何从蓝图解析结果推导 C++ 函数签名和类成员结构。

**API版本:** output_version: "3.0" (Phase 14冻结)

**重要说明:** skill提供参考级别信息，不生成完整C++代码。

---

## 1. 蓝图→C++转换流程

### 1.1 转换步骤

**步骤1：解析蓝图获取graphs_summary**
**步骤2：从function_name推导C++函数名**
**步骤3：从params推导函数签名**
**步骤4：从variables推导成员变量**

```python
from uasset_read import parse_uasset, format_json_summary

# 步骤1：解析蓝图
asset_path = "E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset"
result = parse_uasset(asset_path)
output = format_json_summary(result)

# 步骤2：从execution_flows推导函数
for flow in output["graphs_summary"]:
    if flow["graph_name"] == "EventGraph":
        for exec_flow in flow["execution_flows"]:
            func_name = exec_flow["function_name"]
            print(f"蓝图事件: {func_name}")
            print(f"  → C++函数: {derive_cpp_function(func_name)}")
```

---

## 2. EventGraph→C++函数对照

### 2.1 事件节点映射

| EventGraph节点 | C++函数签名 | 需override |
|-----------------|-------------|------------|
| `Event BeginPlay` | `virtual void BeginPlay() override` | ✓ |
| `Event Tick` | `virtual void Tick(float DeltaTime) override` | ✓ |
| `Event Destroyed` | `virtual void OnDestroyed() override` | ✓ |
| `Event Construction Script` | `virtual void OnConstruction(const FTransform& Transform) override` | ✓ |

### 2.2 从JSON推导C++函数

```python
def derive_cpp_function(func_name, params=None):
    """从蓝图函数名推导C++函数签名"""
    event_map = {
        "ReceiveBeginPlay": "void BeginPlay() override",
        "ReceiveTick": "void Tick(float DeltaTime) override",
        "ReceiveDestroyed": "void OnDestroyed() override",
        "ReceiveActorBeginOverlap": "void NotifyActorBeginOverlap(AActor* OtherActor) override",
        "ReceiveAnyDamage": "float TakeDamage(float Damage, FDamageEvent const& DamageEvent, AController* EventInstigator, AActor* DamageCauser) override",
    }

    if func_name in event_map:
        return event_map[func_name]

    # 通用推导
    if params:
        param_str = ", ".join([p["type"] for p in params])
        return f"void {func_name}({param_str})"

    return f"void {func_name}()"

# 使用示例
result = parse_uasset("BP_FirstPersonCharacter.uasset")
output = format_json_summary(result)

for flow in output["graphs_summary"][0]["execution_flows"]:
    cpp_sig = derive_cpp_function(flow["function_name"], flow["params"])
    print(f"蓝图: {flow['function_name']} → C++: {cpp_sig}")
```

---

## 3. 变量→UPROPERTY映射

### 3.1 类型映射表

| 蓝图类型 | C++类型 | UPROPERTY示例 |
|----------|---------|---------------|
| `FloatProperty` | `float` | `UPROPERTY(EditAnywhere) float Health;` |
| `IntProperty` | `int32` | `UPROPERTY(EditAnywhere) int32 Score;` |
| `BoolProperty` | `bool` | `UPROPERTY(EditAnywhere) bool bIsAlive;` |
| `StrProperty` | `FString` | `UPROPERTY(EditAnywhere) FString Name;` |
| `Vector` | `FVector` | `UPROPERTY(EditAnywhere) FVector Location;` |

### 3.2 从JSON推导UPROPERTY

```python
def derive_cpp_property(prop):
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
    value = prop.get("value")

    # 默认值
    default = ""
    if value is not None:
        if cpp_type == "float":
            default = f" = {value}f"
        elif cpp_type == "int32":
            default = f" = {value}"
        elif cpp_type == "bool":
            default = f" = {str(value).lower()}"
        elif cpp_type == "FString":
            default = f" = TEXT(\"{value}\")"

    return f"UPROPERTY(EditAnywhere, BlueprintReadWrite)\n{cpp_type} {name}{default};"

# 使用示例
for export in result.export_map:
    if "BlueprintGeneratedClass" in export.class_name:
        for prop in export.properties:
            if not prop.get("is_component"):
                cpp_prop = derive_cpp_property(prop)
                print(cpp_prop)
```

---

## 4. 组件→C++成员映射

### 4.1 组件类型映射

| 组件类型 | C++指针类型 | 头文件 |
|----------|-------------|--------|
| `SkeletalMeshComponent` | `USkeletalMeshComponent*` | Components/SkeletalMeshComponent.h |
| `CameraComponent` | `UCameraComponent*` | Components/CameraComponent.h |
| `CapsuleComponent` | `UCapsuleComponent*` | Components/CapsuleComponent.h |
| `CharacterMovementComponent` | `UCharacterMovementComponent*` | GameFramework/CharacterMovementComponent.h |

### 4.2 transforms→C++设置代码

```python
def derive_transform_code(comp_name, transforms):
    """从transforms推导C++变换设置代码"""
    code_lines = []

    loc = transforms.get("RelativeLocation")
    if loc:
        code_lines.append(
            f"{comp_name}->SetRelativeLocation(FVector({loc['X']}f, {loc['Y']}f, {loc['Z']}f));"
        )

    rot = transforms.get("RelativeRotation")
    if rot:
        code_lines.append(
            f"{comp_name}->SetRelativeRotation(FRotator({rot['Pitch']}f, {rot['Yaw']}f, {rot['Roll']}f));"
        )

    scale = transforms.get("RelativeScale3D")
    if scale and (scale['X'] != 1.0 or scale['Y'] != 1.0 or scale['Z'] != 1.0):
        code_lines.append(
            f"{comp_name}->SetRelativeScale3D(FVector({scale['X']}f, {scale['Y']}f, {scale['Z']}f));"
        )

    return code_lines

# 使用示例
for export in result.export_map:
    if "Component" in export.class_name and hasattr(export, 'transforms'):
        transform_code = derive_transform_code(export.object_name, export.transforms)
        for line in transform_code:
            print(line)
```

---

## 5. 完整转换示例

### 5.1 BP_FirstPersonCharacter转换对照

**蓝图解析结果：**

```python
result = parse_uasset("BP_FirstPersonCharacter.uasset")
output = format_json_summary(result)

print("=== 蓝图信息 ===")
print(f"父类: {output.get('parent_class', 'N/A')}")

print("\n=== 执行流程 ===")
for flow in output["graphs_summary"][0]["execution_flows"]:
    print(f"  {flow['function_name']}")

print("\n=== 组件 ===")
for comp in [e for e in result.export_map if "Component" in e.class_name]:
    print(f"  {comp.object_name}")
```

**推导C++结构：**

```cpp
// BP_FirstPersonCharacter.h
#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "BP_FirstPersonCharacter.generated.h"

UCLASS()
class FIRSTPERSON_API ABP_FirstPersonCharacter : public ACharacter
{
    GENERATED_BODY()

public:
    virtual void BeginPlay() override;

protected:
    // 组件
    UPROPERTY(VisibleAnywhere)
    USkeletalMeshComponent* CharacterMesh;

    UPROPERTY(VisibleAnywhere)
    UCameraComponent* FirstPersonCamera;

    // 变量（如有）
    // ...
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
    // EventGraph后续逻辑需手动补充
}
```

### 5.2 FirstPerson vs FirstPersonC对照

UE Samples 提供蓝图和C++对照版本，可用于验证转换：

```python
from uasset_read import parse_uasset

# 蓝图版
bp_result = parse_uasset("E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset")

# 获取父类名称（对应C++类）
for export in bp_result.export_map:
    if "BlueprintGeneratedClass" in export.class_name:
        parent = export.parent_class
        print(f"蓝图父类: {parent}")
        print(f"  → C++类名: A{parent}")
        print(f"  → C++文件: {parent}.h / {parent}.cpp")
```

---

## 6. 转换限制说明

### 6.1 skill不提供的信息

| 信息 | 原因 | 手动补充 |
|------|------|----------|
| 函数体实现 | 需完整执行流程分析 | 根据EventGraph逻辑编写 |
| 头文件包含 | 需模块依赖知识 | Build.cs + #include |
| 网络复制 | ReplicatedProperties | GetLifetimeReplicatedProps |
| 编辑器元数据 | 详细UPROPERTY宏 | Category、meta标签 |

### 6.2 建议工作流程

1. **使用skill获取参考** — 函数名、变量名、组件结构
2. **对照FirstPersonC** — UE Samples提供C++对照版本
3. **手动补充实现** — 函数体、头文件、元数据
4. **测试验证** — 编译运行确保功能一致

---

## 7. 参考链接

- **蓝图→C++转换理论:** [../knowledge/cpp-conversion.md](../knowledge/cpp-conversion.md)
- **蓝图语义:** [../knowledge/blueprint-semantics.md](../knowledge/blueprint-semantics.md)
- **节点类型:** [../knowledge/node-types.md](../knowledge/node-types.md)
- **测试资产:** FirstPerson模板 (UE Samples)

---

*API版本: output_version: "3.0"*
*Skill: uasset-read*
*最后更新: 2026-05-03*