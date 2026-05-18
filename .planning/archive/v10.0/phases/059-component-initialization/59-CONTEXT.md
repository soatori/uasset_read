# Phase 59 — 组件初始化代码：上下文决策

> 为 planner 提供实现决策，避免重复讨论。

## 上游依赖

- **Phase 56 已完成**：`CppClassIR` 包含 `properties` 和 `constructor` 字段
- **Phase 56 分析**：已识别蓝图组件（6 个）和系统变量（11 个）
- **v9.0 已完成**：组件数据从 `result.components` 和 `blueprint.variables` 提取

## 已做决策

### D-59-01：组件创建 — CreateDefaultSubobject 调用

**规则**：
1. 每个组件属性 → `CreateDefaultSubobject<T>()` 调用
2. 模板类型参数：从 `CppClassIR.properties[].cpp_type` 提取（去指针 `*`）
3. 组件名称：使用变量名（如 `"FirstPersonMesh"`, `"CameraComponent_0__CCE3C0B4"`）
4. 返回值赋值：`ComponentVar = CreateDefaultSubobject<...>(TEXT("Name"))`

**示例**：
```cpp
FirstPersonMesh = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("FirstPersonMesh"));
FirstPersonCameraComponent = CreateDefaultSubobject<UCameraComponent>(TEXT("FirstPersonCamera"));
```

### D-59-02：组件 attach — SetupAttachment 调用

**规则**：
1. 组件需要 attach 到父组件时生成
2. 从 `result.components` 中的 `AttachParent` 字段推导
3. 附件名称：从 `AttachSocketName` 提取（如 `"head"`）

**示例**：
```cpp
FirstPersonCameraComponent->SetupAttachment(FirstPersonMesh, FName("head"));
```

**注意**：从 Phase 56 分析的蓝图节点文本中，`FirstPersonCamera` Attach 到 `FirstPersonMesh` 的 `"head"` 插槽

### D-59-03：组件属性赋值 — 构造函数中的默认值

**规则**：
1. 从 `blueprint.variables` 的 `default_value` 提取
2. 尝试解析为常量（浮点、bool、字符串）
3. 类型后缀：`float` → `f`, `double` → 无后缀
4. 字符串：`FString` → `TEXT("value")`

**示例**（来自 Phase 56 分析）：
```cpp
GetCapsuleComponent()->InitCapsuleSize(55.f, 96.0f);
FirstPersonCameraComponent->SetRelativeLocationAndRotation(FVector(-2.8f, 5.89f, 0.0f), FRotator(0.0f, 90.0f, -90.0f));
FirstPersonCameraComponent->bUsePawnControlRotation = true;
GetCharacterMovement()->BrakingDecelerationFalling = 1500.0f;
```

### D-59-04：构造函数包装 — 从 IR 到 .cpp

**产物**：
- 构造函数 `.cpp` 文本，包含：
  1. 初始化列表（如果需要）
  2. `CreateDefaultSubobject` 调用
  3. `SetupAttachment` 调用
  4. 属性赋值语句

**格式**：
```cpp
AMyCharacter::AMyCharacter()
{
    // Component creation
    FirstPersonMesh = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("FirstPersonMesh"));
    FirstPersonCameraComponent = CreateDefaultSubobject<UCameraComponent>(TEXT("FirstPersonCamera"));

    // Setup attachments
    FirstPersonCameraComponent->SetupAttachment(FirstPersonMesh, FName("head"));

    // Property assignments
    FirstPersonCameraComponent->SetRelativeLocationAndRotation(FVector(-2.8f, 5.89f, 0.0f), FRotator(...));
}
```

### D-59-05：Super 构造函数调用

**规则**：
1. 构造函数第一行调用 `Super::AMyCharacter()`（如果基类有构造函数）
2. 对于 `ACharacter` 基类，这是必要的

**示例**：
```cpp
AMyCharacter::AMyCharacter()
    : Super::AMyCharacter()
{
    // ... 组件初始化
}
```

### D-59-06：Component Transform 赋值

**规则**：
1. `SetRelativeLocation(FVector(x, y, z))`
2. `SetRelativeRotation(FRotator(pitch, yaw, roll))`
3. `SetRelativeScale3D(FVector(sx, sy, sz))`

**示例**（来自 Phase 56 分析）：
```cpp
FirstPersonCameraComponent->SetRelativeLocationAndRotation(
    FVector(-2.8f, 5.89f, 0.0f),
    FRotator(0.0f, 90.0f, -90.0f)
);
```

## 范围外

| 想法 | 重定向到 | 原因 |
|------|---------|------|
| 函数声明 | Phase 57 | 已处理 |
| 函数体翻译 | Phase 58 | 已处理 |
| 运行时组件创建 | 不支持 | 只生成默认子对象创建代码 |

## 关键数据参考（来自 Phase 56 分析）

### 组件数据（BlueprintFirstPersonCharacter）

从 `BP_FirstPersonCharacter` 蓝图的 `Components` 数组（通过 `parse_uasset_with_linker`）：

| 组件名 | 类型 | 父组件 | 插槽名 | 位置/旋转 |
|-------|------|-------|--------|----------|
| FirstPersonMesh | SkeletalMeshComponent | Mesh | - | - |
| FirstPersonCamera | CameraComponent | FirstPersonMesh | head | (-2.8, 5.89, 0.0) / (0, 90, -90) |
| CollisionCylinder | CapsuleComponent | Root | - | - |
| CharMoveComp | CharacterMovementComponent | Root | - | - |

**注意**：某些组件（如 CameraComponent, CharacterMovementComponent）是继承自 `ACharacter` 的默认子对象，不需要在 Blueprint 中显式创建

### 属性赋值（来自 BlueprintFirstPersonCharacter C++ 参考实现）

```cpp
AFirstPersonCCharacter::AFirstPersonCCharacter()
{
    // 1. Capsule size
    GetCapsuleComponent()->InitCapsuleSize(55.f, 96.0f);

    // 2. FirstPersonMesh 创建
    FirstPersonMesh = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("First Person Mesh"));
    FirstPersonMesh->SetupAttachment(GetMesh());
    FirstPersonMesh->SetOnlyOwnerSee(true);
    FirstPersonMesh->FirstPersonPrimitiveType = EFirstPersonPrimitiveType::FirstPerson;
    FirstPersonMesh->SetCollisionProfileName(FName("NoCollision"));

    // 3. Camera 创建
    FirstPersonCameraComponent = CreateDefaultSubobject<UCameraComponent>(TEXT("First Person Camera"));
    FirstPersonCameraComponent->SetupAttachment(FirstPersonMesh, FName("head"));
    FirstPersonCameraComponent->SetRelativeLocationAndRotation(
        FVector(-2.8f, 5.89f, 0.0f), 
        FRotator(0.0f, 90.0f, -90.0f)
    );
    FirstPersonCameraComponent->bUsePawnControlRotation = true;
    FirstPersonCameraComponent->bEnableFirstPersonFieldOfView = true;
    FirstPersonCameraComponent->bEnableFirstPersonScale = true;
    FirstPersonCameraComponent->FirstPersonFieldOfView = 70.0f;
    FirstPersonCameraComponent->FirstPersonScale = 0.6f;

    // 4. CharacterMesh 设置
    GetMesh()->SetOwnerNoSee(true);
    GetMesh()->FirstPersonPrimitiveType = EFirstPersonPrimitiveType::WorldSpaceRepresentation;

    // 5. Capsule size (再次设置)
    GetCapsuleComponent()->SetCapsuleSize(34.0f, 96.0f);

    // 6. CharacterMovement 配置
    GetCharacterMovement()->BrakingDecelerationFalling = 1500.0f;
    GetCharacterMovement()->AirControl = 0.5f;
}
```

### InputAction 初始化（来自 Phase 56 分析的缺失项）

**问题**：蓝图中有 `InputAction` 变量（JumpAction, MoveAction, LookAction, MouseLookAction），它们的初始化：

**预期代码**：
```cpp
// 从 .uasset 中提取 InputAction 资源路径
JumpAction = CreateDefaultSubobject<UInputAction>(TEXT("JumpAction"));
JumpAction->AddOpcode(...);  // 或从外部加载

MoveAction = CreateDefaultSubobject<UInputAction>(TEXT("MoveAction"));
// ...
```

**注意**：UE5 的 Enhanced Input 系统通常不通过 `CreateDefaultSubobject` 创建 InputAction，而是在构造函数中通过 `F增强输入输入组件` 绑定。这需要特殊处理。

### Enhanced Input 绑定（Phase 59 关键补充）

**来自 Phase 56 分析的发现**：
- `SetupPlayerInputComponent` 函数中的 `EnhancedInputComponent->BindAction(...)`
- 这些绑定在 `AFirstPersonCCharacter::AFirstPersonCCharacter()` 中不直接出现，而是在 `SetupPlayerInputComponent` 中

**处理策略**：
- 不在 Phase 59 构造函数中生成 `BindAction` 调用
- 在 Phase 57/58 中生成 `SetupPlayerInputComponent` 函数实现
- `SetupPlayerInputComponent` 属于 Phase 58 的函数体翻译

## 增强 InputAction 处理补充

### 问题：InputAction 作为组件/属性

**Phase 56 分析发现**：
1. 蓝图中有 `InputAction` 类型的变量（`JumpAction`, `MoveAction`, `LookAction`, `MouseLookAction`）
2. 这些是 `UInputAction*` 类型指针
3. 在 C++ 中，它们需要：
   - 声明（作为 `UPROPERTY`）
   - 初始化（构造函数）
   - 绑定（`SetupPlayerInputComponent`）

### 处理策略

| 阶段 | 处理内容 |
|------|---------|
| Phase 56 | 类型映射扩展：`InputAction` → `UInputAction*` |
| Phase 57 | 变量声明：添加到 `CppClassIR.properties` |
| Phase 59 | 构造函数：生成 `CreateDefaultSubobject<UInputAction>` 调用（如果需要） |
| Phase 58 | `SetupPlayerInputComponent`：生成 `BindAction` 调用 |

### 常见错误

**错误做法**：
```cpp
// 不要这样：InputAction 通常不由用户代码创建
JumpAction = CreateDefaultSubobject<UInputAction>(TEXT("JumpAction"));
```

**正确做法**：
- InputAction 通常作为 **数据资产**（Data Asset）在项目设置中创建
- 或通过代码加载：`LoadObject<UInputAction>(nullptr, TEXT("/Game/Input/Actions/IA_Jump.IA_Jump"))`
- 或在 `UGameplayAbilitiesModule` 中注册

**Phase 59 建议**：
- 检测 `InputAction` 变量的 `default_value` 字段
- 如果是路径字符串，生成 `LoadObject` 调用
- 如果是空值，跳过初始化（读者需要配置）

## 关键数据流图

### 组件创建路径

```
CppClassIR.properties (component type)
  ↓
cpp_type (e.g., "USkeletalMeshComponent*")
  ↓
去掉 * → "USkeletalMeshComponent"
  ↓
CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("VariableName"))
  ↓
CppAssignmentStatement
  ↓
Append to constructor.body[]
```

### 组件 SetupAttachment 路径

```
Components[].attach_parent + attach_socket_name
  ↓
变量名推导（从 parent_component 属性）
  ↓
ParentVar->SetupAttachment(ChildVar, FName("SocketName"))
  ↓
CppMemberCallStatement
  ↓
Append to constructor.body[]
```

### 属性赋值路径

```
Properties[].default_value (from blueprint.variables)
  ↓
类型转换（float → 55.f, string → TEXT("value")）
  ↓
VarName.PropertyName = Value;
  ↓
CppAssignmentStatement
  ↓
Append to constructor.body[]
```

### Enhanced Input 绑定路径

```
Blueprint.variables (InputAction type)
  ↓
变量名（JumpAction, MoveAction, ...）
  ↓
LoadObject<UInputAction>(nullptr, "/Game/Input/Actions/IA_Jump.IA_Jump")
  ↓
VarName = LoadObject...
  ↓
CppAssignmentStatement
  ↓
Append to constructor.body[] (or separate initializer)
```

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | InputAction 作为数据资产存在，不需要 CreateDefaultSubobject | D-59-06 | 如果 InputAction 需要在构造函数中创建，Phase 59 需要扩展 |
| A2 | 组件的 `AttachParent` 字段足以确定 SetupAttachment 关系 | D-59-02 | 如果还有其他 attach 方式，需要额外处理 |
| A3 | `default_value` 字段包含可解析的常量 | D-59-03 | 如果 default_value 是引用或其他复杂结构，需要 fallback |
| A4 | 构造函数中的 `Super::` 调用可以自动推断 | D-59-05 | 如果需要手动指定，需要额外配置 |
| A5 | 相对变换数据（位置/旋转/缩放）在 `Components` 数组中 | D-59-06 | 如果在 `Variables` 中，需要额外提取逻辑 |
