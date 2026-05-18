# Phase 59 — 组件初始化代码：验证文档

> Golden-path 测试策略和验证清单，确保生成的构造函数代码与 BP_FirstPersonCharacter 参考实现匹配。

## 1. 验证策略

### Golden-Path 测试方法

使用 `BP_FirstPersonCharacter` 作为参考实现，将 `format_cpp_constructor()` 的输出与 59-CONTEXT.md 中的已知-good C++ 参考实现逐行对比。

**对比方法**：
1. 构建 BP_FirstPersonCharacter 的 `CppClassIR`（使用 Phase 56 的已知数据）
2. 调用 `format_cpp_constructor(ir)` 生成 C++ 构造函数文本
3. 将输出与参考 C++ 代码逐行对比

**容许差异**：
- 注释文本（不要求完全匹配）
- 空行数量（段间至少一行即可）
- 缩进风格（固定 4 空格）

**不容许差异**：
- 缺少任何 CreateDefaultSubobject 调用
- SetupAttachment 链不完整或顺序错误
- Transform 参数值不正确
- Property 默认值不正确或类型后缀错误
- Super 调用格式错误（必须是 `Super::ClassName()`，不是 `Super()`）
- InputAction 使用 CreateDefaultSubobject 而非 LoadObject

### 验证环境

```bash
pytest tests/test_cpp_gen/test_cpp_constructor_formatter.py -v
pytest tests/test_cpp_gen/test_cpp_constructor_integration.py -v
```

---

## 2. CreateDefaultSubobject 调用验证

**参考代码**：
```cpp
FirstPersonMesh = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("First Person Mesh"));
FirstPersonCameraComponent = CreateDefaultSubobject<UCameraComponent>(TEXT("First Person Camera"));
```

**检查清单**：

- [ ] `FirstPersonMesh = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("First Person Mesh"))` — 模板类型正确，组件名称匹配
- [ ] `FirstPersonCameraComponent = CreateDefaultSubobject<UCameraComponent>(TEXT("First Person Camera"))` — 模板类型正确，组件名称匹配
- [ ] UInputAction* 类型变量（JumpAction, MoveAction, LookAction, MouseLookAction）**不**出现在 CreateDefaultSubobject 调用中（D-59-06）
- [ ] 每个 CreateDefaultSubobject 调用使用 `TEXT("...")` 包裹组件名称
- [ ] 模板类型参数去掉了 `*`（如 `USkeletalMeshComponent*` → `USkeletalMeshComponent`）

---

## 3. SetupAttachment 链验证

**参考代码**：
```cpp
FirstPersonMesh->SetupAttachment(GetMesh());
FirstPersonCameraComponent->SetupAttachment(FirstPersonMesh, FName("head"));
```

**检查清单**：

- [ ] `FirstPersonMesh->SetupAttachment(GetMesh())`（或等价形式） — Mesh 组件 attach 到 GetMesh()
- [ ] `FirstPersonCameraComponent->SetupAttachment(FirstPersonMesh, FName("head"))` — Camera 组件 attach 到 FirstPersonMesh 的 "head" 插槽
- [ ] Attach 顺序：子组件的 SetupAttachment 调用在其父组件创建**之后**
- [ ] 有 socket_name 时使用 `FName("socket_name")` 参数
- [ ] 无 socket_name 时省略 FName 参数（双参数形式 vs 单参数形式）

---

## 4. Transform 赋值验证

**参考代码**：
```cpp
FirstPersonCameraComponent->SetRelativeLocationAndRotation(
    FVector(-2.8f, 5.89f, 0.0f),
    FRotator(0.0f, 90.0f, -90.0f)
);
```

**检查清单**：

- [ ] 使用 `SetRelativeLocationAndRotation` 方法（而非分开的 SetRelativeLocation + SetRelativeRotation）
- [ ] FVector 参数顺序：`(x, y, z)` — 值为 `(-2.8f, 5.89f, 0.0f)`
- [ ] FRotator 参数顺序：`(pitch, yaw, roll)` — 值为 `(0.0f, 90.0f, -90.0f)`
- [ ] float 值有 `f` 后缀（如 `5.89f`，`0.0f`）
- [ ] Transform 赋值在 SetupAttachment 调用**之后**（代码段顺序）

---

## 5. Property 默认值验证

**参考代码**：
```cpp
FirstPersonCameraComponent->bUsePawnControlRotation = true;
FirstPersonCameraComponent->EnableFirstPersonFieldOfView = true;
FirstPersonCameraComponent->EnableFirstPersonScale = true;
FirstPersonCameraComponent->FirstPersonFieldOfView = 70.0f;
FirstPersonCameraComponent->FirstPersonScale = 0.6f;
GetCharacterMovement()->BrakingDecelerationFalling = 1500.0f;
GetCharacterMovement()->AirControl = 0.5f;
```

**检查清单**：

- [ ] `FirstPersonCameraComponent->bUsePawnControlRotation = true` — bool 值为 `true`（不是 `1`）
- [ ] `GetCharacterMovement()->BrakingDecelerationFalling = 1500.0f` — float 值有 `f` 后缀
- [ ] `GetCharacterMovement()->AirControl = 0.5f` — float 值有 `f` 后缀
- [ ] `FirstPersonCameraComponent->FirstPersonFieldOfView = 70.0f` — float 值有 `f` 后缀
- [ ] `FirstPersonCameraComponent->FirstPersonScale = 0.6f` — float 值有 `f` 后缀
- [ ] float 值统一使用 `f` 后缀，bool 值统一使用 `true`/`false`
- [ ] Property 赋值在 Transform 赋值**之后**（代码段顺序）

---

## 6. InputAction LoadObject 验证

**参考代码**：
```cpp
JumpAction = LoadObject<UInputAction>(nullptr, TEXT("/Game/Input/Actions/IA_Jump.IA_Jump"));
MoveAction = LoadObject<UInputAction>(nullptr, TEXT("/Game/Input/Actions/IA_Move.IA_Move"));
LookAction = LoadObject<UInputAction>(nullptr, TEXT("/Game/Input/Actions/IA_Look.IA_Look"));
MouseLookAction = LoadObject<UInputAction>(nullptr, TEXT("/Game/Input/Actions/IA_MouseLook.IA_MouseLook"));
```

**检查清单**：

- [ ] JumpAction, MoveAction, LookAction, MouseLookAction 使用 `LoadObject<UInputAction>(nullptr, TEXT("/Game/..."))` 而非 CreateDefaultSubobject
- [ ] LoadObject 调用使用 `TEXT("...")` 包裹资源路径
- [ ] 资源路径格式为 `/Game/Input/Actions/IA_XXX.IA_XXX`
- [ ] 如果 asset_path 为空，**跳过**该 InputAction 初始化（不生成空 LoadObject 调用）
- [ ] InputAction LoadObject 调用在所有 Property 赋值**之后**（代码段顺序）
- [ ] 资产路径验证：路径必须匹配 `/Game/...` 模式，拒绝包含 `..`、`;` 或非字母数字字符（除 `/` 和 `_` 外）的路径（T-059-07 缓解措施）

---

## 7. Super 调用验证

**参考代码**：
```cpp
AFirstPersonCCharacter::AFirstPersonCCharacter()
    : Super::AFirstPersonCCharacter()
{
```

**检查清单**：

- [ ] 构造函数初始化列表包含 `: Super::ClassName()`（无条件，D-59-05）
- [ ] **不是** `: Super()` — 必须使用完整类名
- [ ] Super 调用在函数签名之后、花括号之前（初始化列表位置）
- [ ] 缩进为 4 空格，前导 `:` 对齐
- [ ] ClassName 与实际类名一致（如 `AFirstPersonCCharacter`）

---

## 8. 代码段顺序验证

**参考顺序**：
```
1. Super 调用（初始化列表）
2. Component creation（CreateDefaultSubobject）
3. Setup attachments（SetupAttachment）
4. Transform assignments（SetRelativeLocationAndRotation）
5. Property assignments（属性默认值）
6. InputAction loads（LoadObject）
```

**检查清单**：

- [ ] Super 调用在构造函数签名行（初始化列表），不在函数体内
- [ ] Component creation 段在函数体最前面
- [ ] SetupAttachment 段在 Component creation 之后
- [ ] Transform 赋值在 SetupAttachment 之后
- [ ] Property 赋值在 Transform 赋值之后
- [ ] InputAction LoadObject 在所有 Property 赋值之后
- [ ] 每段之间有注释标识（`// Component creation`，`// Setup attachments` 等）
- [ ] 空段（无内容）不输出空注释

---

## 9. 已知前提与限制

### extract_components 缺少 attach_parent 字段

**当前状态**：`extract_components` 当前不返回 `attach_parent` 字段。

**影响**：
- SetupAttachment 调用可能无法从现有数据中完整推导 attach 关系
- 如果 attach 关系无法从 `result.components` 获取，验证时应标注此为已知限制

**缓解措施**：
- Phase 56 分析的蓝图节点文本中已识别：FirstPersonCamera Attach 到 FirstPersonMesh 的 "head" 插槽
- 验证时可手动提供已知 attach 关系作为 golden case 输入

### InputAction 资源路径

**当前状态**：InputAction 变量（JumpAction, MoveAction, LookAction, MouseLookAction）的资源路径需要从蓝图数据中提取。

**影响**：
- 如果 asset_path 为空，生成代码应跳过该 InputAction 初始化
- 验证时需确认空路径跳过逻辑

### C++ 参考实现中的额外设置

参考 C++ 实现中包含以下可能不在蓝图数据中的设置：
- `FirstPersonMesh->SetOnlyOwnerSee(true)`
- `FirstPersonMesh->FirstPersonPrimitiveType = EFirstPersonPrimitiveType::FirstPerson`
- `FirstPersonMesh->SetCollisionProfileName(FName("NoCollision"))`
- `FirstPersonCameraComponent->EnableFirstPersonFieldOfView = true`
- `FirstPersonCameraComponent->EnableFirstPersonScale = true`
- `GetMesh()->SetOwnerNoSee(true)`
- `GetMesh()->FirstPersonPrimitiveType = EFirstPersonPrimitiveType::WorldSpaceRepresentation`
- `GetCapsuleComponent()->SetCapsuleSize(34.0f, 96.0f)`（第二次设置）

**验证策略**：这些设置如果存在于蓝图数据中，应在生成的代码中出现；如果不存在，不应凭空生成。

---

## 10. 与参考 C++ 实现的对比方法

### 对比步骤

1. **准备 golden case 输入**：
   - 使用 Phase 56 分析的 BP_FirstPersonCharacter 数据构建 `CppClassIR`
   - 确保 `constructor` 字典包含所有 component_creations、component_assignments、default_values

2. **生成输出**：
   - 调用 `format_cpp_constructor(ir)` 获取生成的 C++ 文本

3. **逐行对比**：
   - 忽略注释行差异（`// ...`）
   - 忽略纯空行数量差异
   - 对比所有代码行的语义等价性

4. **关键断言**：
   - 所有 CreateDefaultSubobject 调用存在且正确
   - 所有 SetupAttachment 调用存在且顺序正确
   - Transform 值完全匹配（包括 float 后缀）
   - Property 值完全匹配
   - Super 调用格式正确
   - 代码段顺序正确

### 自动化测试

```python
def test_golden_path_constructor():
    """Golden-path test: BP_FirstPersonCharacter constructor matches reference."""
    ir = build_golden_cpp_class_ir()  # Phase 56 known data
    output = format_cpp_constructor(ir)

    # Structural checks
    assert "Super::AFirstPersonCCharacter()" in output
    assert ": Super()" not in output  # Must use full class name
    assert "CreateDefaultSubobject<USkeletalMeshComponent>" in output
    assert "CreateDefaultSubobject<UCameraComponent>" in output
    assert "SetupAttachment" in output
    assert "SetRelativeLocationAndRotation" in output
    assert "FVector(-2.8f, 5.89f, 0.0f)" in output
    assert "FRotator(0.0f, 90.0f, -90.0f)" in output
    assert "bUsePawnControlRotation = true" in output
    assert "BrakingDecelerationFalling = 1500.0f" in output

    # Negative checks (InputAction should NOT use CreateDefaultSubobject)
    assert "CreateDefaultSubobject<UInputAction>" not in output

    # Section order checks
    creation_pos = output.find("// Component creation")
    attach_pos = output.find("// Setup attachments")
    transform_pos = output.find("// Transform assignments")
    property_pos = output.find("// Property assignments")
    assert creation_pos < attach_pos < transform_pos < property_pos
```
