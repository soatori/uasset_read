# 蓝图 JSON → C++ 类 - 快速参考

**生成时间:** 2026-05-13  
**用途:** 快速参考指南

---

## ✅ 是的！JSON 可以作为参考依据

| JSON 数据 | 转换为 C++ | 参考价值 |
|-----------|------------|----------|
| `parent_class: "Character"` | `: public ACharacter` | ✅ 100% |
| `variables[0].var_name: "JumpAction"` | `UInputAction* JumpAction;` | ✅ 100% |
| `export_map[].properties[].value: 70.0` | `FOV = 70.0f;` | ✅ 100% |
| `graphs[].nodes[].class_name: "K2Node_EnhancedInputAction"` | `BindAction(...)` | ✅ 80% |
| `graph_name: "EventGraph"` | `SetupPlayerInputComponent` | ✅ 90% |

---

## 📋 完整示例

### 1. 解析蓝图得到 JSON

```json
{
  "summary": {
    "package_name": "/Game/FirstPerson/Blueprints/BP_FirstPersonCharacter"
  },
  "blueprint": {
    "parent_class": {
      "type": "import",
      "object_name": "Character"
    },
    "variables": [
      {
        "var_name": "JumpAction",
        "var_type": {
          "pin_category": "Object",
          "pin_subcategory": "Class'/Script/Engine.InputAction'"
        }
      },
      {
        "var_name": "MoveAction",
        "var_type": {
          "pin_category": "Object",
          "pin_subcategory": "Class'/Script/Engine.InputAction'"
        }
      },
      {
        "var_name": "AirControl",
        "var_type": {
          "pin_category": "Float"
        },
        "default_value": "0.5"
      }
    ]
  },
  "export_map": [
    {
      "class_name": "CameraComponent",
      "object_name": "CameraComponent_0__CCE3C0B4",
      "properties": [
        {
          "name": "FirstPersonFieldOfView",
          "type": "FloatProperty",
          "value": 70.0
        }
      ]
    },
    {
      "class_name": "CharacterMovementComponent",
      "object_name": "CharMoveComp",
      "properties": [
        {
          "name": "AirControl",
          "type": "FloatProperty",
          "value": 0.5
        }
      ]
    }
  ],
  "graphs": [
    {
      "graph_name": "EventGraph",
      "nodes": [
        {
          "class_name": "K2Node_EnhancedInputAction",
          "pins": [
            {"pin_name": "Triggered"}
          ]
        }
      ]
    }
  ]
}
```

---

### 2. 参考 JSON 创建 C++ 类

```cpp
// ✅ 头文件 (MYCharacter.h)
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "InputAction.h"
#include "MYCharacter.generated.h"

UCLASS()
class AMYCharacter : public ACharacter  // ← 参考 blueprint.parent_class
{
	GENERATED_BODY()

public:
	// 参考 blueprint.variables
	UPROPERTY(EditAnywhere, Category = "Input")
	UInputAction* JumpAction;  // ← var_name: "JumpAction"

	UPROPERTY(EditAnywhere, Category = "Input")
	UInputAction* MoveAction;  // ← var_name: "MoveAction"

	// 参考 export_map
	UPROPERTY(VisibleAnywhere)
	UCameraComponent* CameraComponent_0__CCE3C0B4;  // ← object_name

	UPROPERTY(VisibleAnywhere)
	UCharacterMovementComponent* CharMoveComp;  // ← object_name

public:
	AMyCharacter();

protected:
	virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;

public:
	// 参考 graphs: EventGraph 中的事件
	UFUNCTION(BlueprintCallable, Category = "Input")
	virtual void DoJumpStart();

	UFUNCTION(BlueprintCallable, Category = "Input")
	virtual void DoMove(float Right, float Forward);
};
```

```cpp
// ✅ 源文件 (MYCharacter.cpp)
#include "MYCharacter.h"
#include "Camera/CameraComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "EnhancedInputComponent.h"
#include "InputActionValue.h"

AMYCharacter::AMYCharacter()
{
	// 参考 export_map 的属性配置
	GetCapsuleComponent()->SetCapsuleSize(34.0f, 96.0f);

	// 创建组件 (参考 export_map 中的组件)
	CameraComponent_0__CCE3C0B4 = CreateDefaultSubobject<UCameraComponent>(TEXT("CameraComponent_0__CCE3C0B4"));
	CameraComponent_0__CCE3C0B4->FirstPersonFieldOfView = 70.0f;  // ← value: 70.0

	CharMoveComp = GetCharacterMovement();
	CharMoveComp->AirControl = 0.5f;  // ← value: 0.5
}

void AMYCharacter::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
	Super::SetupPlayerInputComponent(PlayerInputComponent);

	// 参考 graphs: EventGraph 中的 K2Node_EnhancedInputAction
	if (UEnhancedInputComponent* EnhancedInputComponent = Cast<UEnhancedInputComponent>(PlayerInputComponent))
	{
		// ← 从 JSON 推断出需要绑定
		EnhancedInputComponent->BindAction(JumpAction, ETriggerEvent::Started, this, &AMYCharacter::DoJumpStart);
		EnhancedInputComponent->BindAction(MoveAction, ETriggerEvent::Triggered, this, &AMYCharacter::DoMove);
	}
}
```

---

### 3. 手动编写函数实现

```cpp
// ⚠️ JSON 无法提供，需要手动编写

void AMYCharacter::DoJumpStart()
{
	Jump();
}

void AMYCharacter::DoMove(float Right, float Forward)
{
	if (GetController())
	{
		AddMovementInput(GetActorRightVector(), Right);
		AddMovementInput(GetActorForwardVector(), Forward);
	}
}
```

---

## 📊 参考价值总结

| 项目 | 参考价值 | 说明 |
|------|----------|------|
| **类名** | ✅ 100% | `parent_class` |
| **成员变量** | ✅ 100% | `variables` |
| **组件创建** | ✅ 90% | `export_map[].class_name` |
| **组件配置** | ✅ 100% | `export_map[].properties[].value` |
| **输入绑定** | ✅ 80% | `graphs[].nodes[].class_name` |
| **函数声明** | ✅ 90% | `graphs[].nodes[].pins[].pin_name` |
| **函数实现** | ❌ 0% | 需要手动编写 |
| **注释** | ❌ 0% | 需要手动添加 |

---

## 💡 使用建议

### 推荐做法

```
1. 解析蓝图得到 JSON
   ↓
2. 打开 JSON 和 IDE
   ↓
3. 参考 JSON 创建 C++ 框架
   ├─ 头文件: 90% 自动
   └─ 源文件: 50% 自动
   ↓
4. 手动编写函数实现
   ↓
5. 编译测试
```

---

## 🎯 关键点

| 关键点 | 说明 |
|--------|------|
| **✅ 可以参考** | JSON 提供完整的结构和配置信息 |
| **❌ 不是源代码** | JSON 不包含函数实现逻辑 |
| **需要手动** | 函数实现体、注释、代码格式 |
| **参考价值** | 75% (结构 100%, 实现 0%) |

---

**快速参考完成时间:** 2026-05-13
