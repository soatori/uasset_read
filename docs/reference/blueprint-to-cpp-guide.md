# 蓝图到 C++ 转换参考

> 合并自 QUICK_REFERENCE / JSON_AS_REFERENCE / DECISION_GUIDE / Blueprint_to_CPP_Feasibility
> 最后更新: 2026-05-26

## 核心结论

| 问题 | 答案 |
|------|------|
| 蓝图能否直接转换为可编译的 C++ 类？ | 不能 — 缺少函数实现体 |
| 蓝图能否生成 C++ 代码框架？ | 可以 — 约 50% 工作量可自动生成 |
| JSON 输出能否作为 C++ 参考？ | 可以 — 提供完整结构和配置信息 |

## 参考价值矩阵

| 蓝图数据 | 对应 C++ | 参考价值 |
|----------|----------|----------|
| `parent_class` | 基类继承 (`: public ACharacter`) | 100% |
| `variables[]` | `UPROPERTY` 成员声明 | 100% |
| `export_map[].properties[].value` | 构造函数中的属性赋值 | 100% |
| `export_map[].class_name` | 组件 `CreateDefaultSubobject` | 90% |
| `graphs[].nodes[].class_name` | `BindAction` / 事件绑定 | 80% |
| `graphs[].nodes[].pins[].pin_name` | 函数参数推断 | 80% |
| 节点连接关系 (EventGraph) | 函数实现体逻辑 | 0% — 需手动编写 |
| 头文件依赖 / include | `#include` 列表 | 0% — 需手动补充 |

## 可行性评分

| 项目 | 可行性 | 评分 |
|------|--------|------|
| 类定义 | 可自动生成 | 90% |
| 成员变量 | 可自动生成 | 85% |
| 函数声明 | 可自动生成 | 80% |
| 组件配置 | 可自动生成 | 95% |
| 函数实现体 | 不可自动生成 | 0% |
| 输入绑定 | 部分可生成 | 60% |
| **总体** | ~50% 自动化 | 3/5 |

## 快速示例

### 从 JSON 到 C++ 头文件

```json
{
  "blueprint": {
    "parent_class": {"type": "import", "object_name": "Character"},
    "variables": [
      {"var_name": "JumpAction", "var_type": {"pin_category": "Object", "pin_subcategory": "Class'/Script/Engine.InputAction'"}},
      {"var_name": "AirControl", "var_type": {"pin_category": "Float"}, "default_value": "0.5"}
    ]
  },
  "export_map": [
    {"class_name": "CameraComponent", "object_name": "CameraComponent_0", "properties": [{"name": "FirstPersonFieldOfView", "type": "FloatProperty", "value": 70.0}]}
  ]
}
```

```cpp
// MYCharacter.h
#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "InputAction.h"
#include "MYCharacter.generated.h"

UCLASS()
class AMYCharacter : public ACharacter  // ← blueprint.parent_class
{
    GENERATED_BODY()
public:
    AMYCharacter();

    // ← blueprint.variables
    UPROPERTY(EditAnywhere, Category = "Input")
    UInputAction* JumpAction;

    UPROPERTY(EditAnywhere, Category = "Input")
    float AirControl = 0.5f;  // ← default_value

    // ← export_map components
    UPROPERTY(VisibleAnywhere)
    UCameraComponent* CameraComponent_0;

protected:
    virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;
};
```

```cpp
// MYCharacter.cpp
#include "MYCharacter.h"
#include "Camera/CameraComponent.h"

AMYCharacter::AMYCharacter()
{
    // ← export_map properties
    CameraComponent_0 = CreateDefaultSubobject<UCameraComponent>(TEXT("CameraComponent_0"));
    CameraComponent_0->FirstPersonFieldOfView = 70.0f;  // ← value: 70.0
}
```

### 需手动编写的部分

```cpp
// 函数实现体无法从蓝图节点连接自动生成
void AMYCharacter::DoJumpStart()
{
    Jump();  // 需要手动理解蓝图逻辑
}
```

## 决策树

```
是否需要高性能？
├── 是 → 完全手写 C++
└── 否 → 保持蓝图

是否需要频繁迭代？
├── 是 → 保持蓝图
└── 否 → 考虑转换

团队是否熟悉 C++？
├── 是 → 部分自动化或完全手写
└── 否 → 保持蓝图
```

## 推荐方案

### 方案 A: 保持蓝图（推荐大多数场景）
- 适用：快速原型、功能简单、团队不熟悉 C++
- 工作量：0
- 优点：快速迭代、可视化编辑

### 方案 B: 部分自动化（有 C++ 经验的团队）
1. 从蓝图提取框架（自动）→ 类定义/变量/函数声明/组件配置 ~100%
2. 手动补充函数实现体（手动）→ ~100%
3. 创建 InputAction 等外部引用（手动）→ ~100%
- 总自动化率：~50%

### 方案 C: 完全手写（性能敏感场景）
- 手动查看蓝图逻辑 → 手动编写 C++ → 手动测试优化
- 优点：代码质量最高、性能最优
- 缺点：工作量最大

## 与 cpp_gen 模块的关系

本项目已内置 `cpp_gen/` 模块，支持从蓝图自动生成 C++ 骨架：

| 模块 | 功能 |
|------|------|
| `cpp_gen/cpp_type_mapper.py` | UE 属性类型 → C++ 类型映射 |
| `cpp_gen/cpp_uproperty_mapper.py` | CPF 标志 → UPROPERTY 修饰符映射 |
| `cpp_gen/cpp_default_value_formatter.py` | UE 默认值 → C++ 字面量 |
| `cpp_gen/cpp_constructor_ir_builder.py` | 从 BlueprintVariable 构建构造函数 IR |

> 使用方式：`parse_single(path, format="cpp_skeleton")`，通过渲染器系统输出。
