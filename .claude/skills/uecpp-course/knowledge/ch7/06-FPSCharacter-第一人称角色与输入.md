# FPS — 第一人称角色与输入

## 概述

通过 `AXGFPSCharacter` + 动画蓝图演示第一人称项目中 ACharacter 的使用方式。包括：输入绑定、Camera-to-World 空间变换、发射物生成（跨系统调用），以及动画蓝图的状态机设置。

代码位于 `003_XGFPS0Demo` 项目。

## XGFPSCharacter

### 头文件

```cpp
UCLASS()
class XGFPS0DEMO_API AXGFPSCharacter : public ACharacter
{
    GENERATED_BODY()

public:
    AXGFPSCharacter();

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = XG)
    UCameraComponent* FPSCameraComponent;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = XG)
    USkeletalMeshComponent* FPSMesh;

    UPROPERTY(EditDefaultsOnly, Category = XG)
    TSubclassOf<AXGFPSProjectile> ProjectileClass;

    UPROPERTY(EditDefaultsOnly, Category = XG)
    FVector GunOffset = FVector(100.0f, 0.0f, 10.0f);

protected:
    void MoveForward(float Value);
    void MoveRight(float Value);
    void Turn(float Value);
    void LookUp(float Value);
    void StartJump();
    void StopJump();
    void Fire();

    virtual void SetupPlayerInputComponent(
        UInputComponent* PlayerInputComponent) override;
};
```

### 构造函数

```cpp
AXGFPSCharacter::AXGFPSCharacter()
{
    PrimaryActorTick.bCanEverTick = true;

    // 1. 第一人称 Camera 附着在胶囊体上（头部位置）
    FPSCameraComponent =
        CreateDefaultSubobject<UCameraComponent>(TEXT("FPSCamera"));
    FPSCameraComponent->SetupAttachment(
        GetCapsuleComponent(), FName("head"));
    FPSCameraComponent->bUsePawnControlRotation = true;

    // 2. 第一人称手臂 Mesh（仅自己可见）
    FPSMesh = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("FPSMesh"));
    FPSMesh->SetOnlyOwnerSee(true);
    FPSMesh->SetupAttachment(FPSCameraComponent);

    // 3. 主身体 Mesh（仅他人可见）
    GetMesh()->SetOwnerNoSee(true);

    // 4. 自动 Possess
    AutoPossessPlayer = EAutoReceiveInput::Player0;
}
```

### 输入绑定

```cpp
void AXGFPSCharacter::SetupPlayerInputComponent(
    UInputComponent* PlayerInputComponent)
{
    Super::SetupPlayerInputComponent(PlayerInputComponent);

    // 移动
    PlayerInputComponent->BindAxis(
        "MoveForward", this, &AXGFPSCharacter::MoveForward);
    PlayerInputComponent->BindAxis(
        "MoveRight", this, &AXGFPSCharacter::MoveRight);

    // 视角
    PlayerInputComponent->BindAxis(
        "Turn", this, &AXGFPSCharacter::Turn);
    PlayerInputComponent->BindAxis(
        "LookUp", this, &AXGFPSCharacter::LookUp);

    // 跳跃（Action）
    PlayerInputComponent->BindAction(
        "Jump", IE_Pressed, this, &AXGFPSCharacter::StartJump);
    PlayerInputComponent->BindAction(
        "Jump", IE_Released, this, &AXGFPSCharacter::StopJump);

    // 开火（Action）
    PlayerInputComponent->BindAction(
        "Fire", IE_Pressed, this, &AXGFPSCharacter::Fire);
}
```

### 移动与视角

```cpp
void AXGFPSCharacter::MoveForward(float Value)
{
    if (Controller && Value != 0.0f)
    {
        // 基于控制器的前方向（非 Actor 前方向）
        FRotationMatrix RotationMatrix(Controller->GetControlRotation());
        FVector Direction = RotationMatrix.GetScaledAxis(EAxis::X);
        AddMovementInput(Direction, Value);
    }
}

void AXGFPSCharacter::MoveRight(float Value)
{
    if (Controller && Value != 0.0f)
    {
        FRotationMatrix RotationMatrix(Controller->GetControlRotation());
        FVector Direction = RotationMatrix.GetScaledAxis(EAxis::Y);
        AddMovementInput(Direction, Value);
    }
}

void AXGFPSCharacter::Turn(float Value)
{
    AddControllerYawInput(Value);
}

void AXGFPSCharacter::LookUp(float Value)
{
    AddControllerPitchInput(Value);
}

void AXGFPSCharacter::StartJump()
{
    bPressedJump = true;
}

void AXGFPSCharacter::StopJump()
{
    bPressedJump = false;
}
```

### Camera-to-World 空间变换

```cpp
void AXGFPSCharacter::Fire()
{
    if (!ProjectileClass) return;

    UCameraComponent* Camera = FPSCameraComponent;
    if (!Camera) return;

    // 1. 获取摄像机位置和旋转
    FVector CameraLocation;
    FRotator CameraRotation;
    GetActorEyesViewPoint(CameraLocation, CameraRotation);

    // 2. GunOffset 从 Camera 空间转换到世界空间
    FVector MuzzleLocation = CameraLocation +
        FTransform(CameraRotation).TransformPosition(GunOffset);

    // 3. 略微向上偏移发射方向
    FRotator MuzzleRotation = CameraRotation;
    MuzzleRotation.Pitch += 5.0f;

    // 4. 生成发射物
    UWorld* World = GetWorld();
    if (World)
    {
        FActorSpawnParameters SpawnParams;
        SpawnParams.Owner = this;
        SpawnParams.Instigator = GetInstigator();

        AXGFPSProjectile* Projectile =
            World->SpawnActor<AXGFPSProjectile>(
                ProjectileClass, MuzzleLocation, MuzzleRotation, SpawnParams);

        if (Projectile)
        {
            FVector LaunchDirection = MuzzleRotation.Vector();
            Projectile->FireInDirection(LaunchDirection);
        }
    }
}
```

### 关键空间运算

```
GunOffset (Camera 空间) → FTransform(CameraRotation) → 世界空间偏移 → + CameraLocation → 最终生成位置
```

- `GetActorEyesViewPoint` 获取控制器的眼睛位置（对玩家来说是摄像机位置）
- `FTransform(Rotation).TransformPosition(Offset)` 将偏移从旋转空间变换到世界空间
- 发射方向使用 `MuzzleRotation.Vector()` 而非 Camera forward，因为包含了 Pitch 微调

## 发射物生成链路

```
Player Input (Fire)
  → Character::Fire()
    → GetActorEyesViewPoint (获取摄像机位置+旋转)
    → GunOffset 从 Camera 空间 → World 空间
    → SpawnActor<AXGFPSProjectile> (World, Class, Location, Rotation, SpawnParams)
    → Projectile->FireInDirection (设初始速度方向)
```

## 动画蓝图

### 状态机结构

```
[Idle] ←→ [Run]    ← Speed > 0 / Speed == 0
  ↓          ↓
[Jump_Start]        ← IsFalling == true
  ↓
[Jump_Loop]         ← Jump_Start 播放完毕且仍 IsFalling
  ↓
[Jump_Land]         ← IsFalling == false
  ↓
[Idle]              ← Jump_Land 播放完毕
```

### Event Graph 逻辑

```
Event BlueprintUpdateAnimation
  → Get Owning Actor
  → Cast to AXGFPSCharacter
  → Get Character Movement Component
  → Set IsFalling = CharacterMovement->IsFalling()
  → Set Speed = CharacterMovement->Velocity.Size()
```

### 状态机变量

| 变量 | 类型 | 用途 |
|------|------|------|
| `IsFalling` | bool | 控制 Idle/Run → Jump 的转换 |
| `Speed` | float | 控制 Idle ↔ Run 的转换 |

### 动画过渡条件

| 过渡 | 条件 |
|------|------|
| Idle → Run | Speed > 0 |
| Run → Idle | Speed == 0 |
| Idle/Run → Jump_Start | IsFalling == true |
| Jump_Start → Jump_Loop | 完成时（Remaining Time == 0）且 IsFalling == true |
| Jump_Loop → Jump_Land | IsFalling == false |
| Jump_Land → Idle | 完成时 |

### 动画蓝图绑定

1. 创建 Animation Blueprint，指定 Skeleton
2. 在 Event Graph 中更新 `IsFalling` 和 `Speed`
3. 在 Anim Graph 中创建 State Machine，设置状态和过渡
4. 在 Character Blueprint 中将该 Animation Blueprint 指定给 Skeletal Mesh

## 关键设计模式

### TSubclassOf 类型安全

```cpp
UPROPERTY(EditDefaultsOnly, Category = XG)
TSubclassOf<AXGFPSProjectile> ProjectileClass;
```

- `TSubclassOf` 限制只能选择 `AXGFPSProjectile` 及其子类
- 在蓝图中显示为紫色类选择框
- 蓝图子类可以重载发射物的属性（速度、网格体等）

### ACharacter 的内置组件

ACharacter 已包含的组件：
- `GetCapsuleComponent()` — 胶囊碰撞体
- `GetMesh()` — 第三人称骨骼网格
- `GetCharacterMovement()` — 标准角色移动组件

第一人称额外添加：
- `FPSCameraComponent` — 第一人称摄像机
- `FPSMesh` — 第一人称手臂网格（仅自己可见）

### OwnerNoSee / OnlyOwnerSee

```cpp
FPSMesh->SetOnlyOwnerSee(true);       // 仅自己可见
GetMesh()->SetOwnerNoSee(true);       // 对他人不可见
```

第一人称时，玩家自己的视角看到手臂 Mesh，第三人称视角看到身体 Mesh。

### bUsePawnControlRotation

```cpp
FPSCameraComponent->bUsePawnControlRotation = true;
```

摄像机跟随控制器的旋转，实现"鼠标移动 → 视口转动"的标准 FPS 控制。

### bPressedJump

```cpp
void StartJump() { bPressedJump = true; }
void StopJump()  { bPressedJump = false; }
```

`bPressedJump` 是 `ACharacter` 内置的标志位，`CharacterMovementComponent` 会在 Movement 更新循环中自动读取并触发跳跃。

### 代码位置

| 文件 | 说明 |
|------|------|
| [XGFPSCharacter.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/003_XGFPS0Demo/Source/XGFPS0Demo/XGFPSCharacter.h) | 角色头文件 |
| [XGFPSCharacter.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/003_XGFPS0Demo/Source/XGFPS0Demo/XGFPSCharacter.cpp) | 角色实现 |
| [XGFPSGameMode.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/003_XGFPS0Demo/Source/XGFPS0Demo/XGFPSGameMode.h) | GameMode 头文件 |
| [XGFPSGameMode.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/003_XGFPS0Demo/Source/XGFPS0Demo/XGFPSGameMode.cpp) | GameMode 实现 |
