# ComponentAndCollision — 组件碰撞与自定义移动

## 概述

通过 `XGCollidingPawn` + 自定义 `UXGCollidingPawnMovementComponent` 演示 UE 碰撞系统与可复用移动组件的架构模式。

代码位于 `010_ComponentAndCollision/` 目录。

## 架构概览

```
XGCollidingPawn (APawn)
  ├─ SphereComponent          ← 根组件/RootComponent（碰撞根）
  │    ├─ StaticMeshComponent  ← 视觉表示（附着于根）
  │    │    └─ ParticleSystem  ← 粒子特效
  │    ├─ SpringArmComponent   ← 弹簧臂
  │    │    └─ CameraComponent ← 摄像机
  │    └─ (无场景附着)
  └─ UXGCollidingPawnMovementComponent ← 逻辑组件，不附着场景
       └─ UpdatedComponent = RootComponent
```

## 自定义 PawnMovementComponent

### 头文件

```cpp
UCLASS()
class XGSAMPLEDEMO_API UXGCollidingPawnMovementComponent
    : public UPawnMovementComponent
{
    GENERATED_BODY()

public:
    virtual void TickComponent(float DeltaTime, ELevelTick TickType,
        FActorComponentTickFunction* ThisTickFunction) override;
};
```

### 实现

```cpp
void UXGCollidingPawnMovementComponent::TickComponent(
    float DeltaTime, ELevelTick TickType,
    FActorComponentTickFunction* ThisTickFunction)
{
    Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

    if (!PawnOwner || !UpdatedComponent || ShouldSkipUpdate(DeltaTime))
        return;

    FVector DesiredMovementThisFrame =
        ConsumeInputVector().GetClampedToMaxSize(1.0f) * DeltaTime * 150.0f;

    if (!DesiredMovementThisFrame.IsNearlyZero())
    {
        FHitResult Hit;
        SafeMoveUpdatedComponent(
            DesiredMovementThisFrame,
            UpdatedComponent->GetComponentRotation(),
            true, Hit);

        if (Hit.IsValidBlockingHit())
        {
            SlideAlongSurface(
                DesiredMovementThisFrame, 1.f - Hit.Time, Hit.Normal, Hit);
        }
    }
}
```

### 移动组件核心 API

| 函数 | 说明 |
|------|------|
| `ConsumeInputVector()` | 获取并清除当前帧的输入向量 |
| `GetClampedToMaxSize(1.0f)` | 限制输入向量最大长度 1 |
| `SafeMoveUpdatedComponent()` | 带碰撞检测的移动，返回 `FHitResult` |
| `SlideAlongSurface()` | 沿碰撞表面滑动，实现贴墙走效果 |
| `ShouldSkipUpdate(DeltaTime)` | 跳过无效更新（如暂停帧） |

### 逻辑组件的关键特征

`UPawnMovementComponent` 是**逻辑组件**，不是场景组件：

- **无场景附着** — 不需要 `SetupAttachment`，不参与场景变换层级
- **直接设置 `UpdatedComponent`** — `OurMovementComponent->UpdatedComponent = RootComponent`
- **职责单一** — 只负责移动逻辑计算，不关心渲染或输入
- **可复用** — 移动逻辑从 Pawn 类中解耦，可被不同 Pawn 共用

## XGCollidingPawn

### 构造函数

```cpp
AXGCollidingPawn::AXGCollidingPawn()
{
    PrimaryActorTick.bCanEverTick = true;

    // 根组件 —— SphereComponent 作为碰撞根
    USphereComponent* SphereComponent =
        CreateDefaultSubobject<USphereComponent>(TEXT("RootComponent"));
    RootComponent = SphereComponent;
    SphereComponent->InitSphereRadius(40.0f);
    SphereComponent->SetCollisionProfileName(TEXT("Pawn"));

    // 视觉网格体
    UStaticMeshComponent* SphereVisual =
        CreateDefaultSubobject<UStaticMeshComponent>(TEXT("VisualRepresentation"));
    SphereVisual->SetupAttachment(RootComponent);

    static ConstructorHelpers::FObjectFinder<UStaticMesh> SphereVisualAsset(
        TEXT("/Game/StarterContent/Shapes/Shape_Sphere.Shape_Sphere"));
    if (SphereVisualAsset.Succeeded())
    {
        SphereVisual->SetStaticMesh(SphereVisualAsset.Object);
        SphereVisual->SetRelativeLocation(FVector(0.0f, 0.0f, -40.0f));
        SphereVisual->SetWorldScale3D(FVector(0.8f));
    }

    // 粒子系统
    OurParticleSystem = CreateDefaultSubobject<UParticleSystemComponent>(
        TEXT("MovementParticles"));
    OurParticleSystem->SetupAttachment(SphereVisual);
    OurParticleSystem->bAutoActivate = false;
    OurParticleSystem->SetRelativeLocation(FVector(-20.0f, 0.0f, 20.0f));

    static ConstructorHelpers::FObjectFinder<UParticleSystem> ParticleAsset(
        TEXT("/Game/StarterContent/Particles/P_Fire.P_Fire"));
    if (ParticleAsset.Succeeded())
        OurParticleSystem->SetTemplate(ParticleAsset.Object);

    // SpringArm + Camera
    USpringArmComponent* SpringArm =
        CreateDefaultSubobject<USpringArmComponent>(TEXT("CameraAttachmentArm"));
    SpringArm->SetupAttachment(RootComponent);
    SpringArm->SetRelativeRotation(FRotator(-45.f, 0.f, 0.f));
    SpringArm->TargetArmLength = 400.0f;
    SpringArm->bEnableCameraLag = true;
    SpringArm->CameraLagSpeed = 3.0f;

    UCameraComponent* Camera =
        CreateDefaultSubobject<UCameraComponent>(TEXT("ActualCamera"));
    Camera->SetupAttachment(SpringArm, USpringArmComponent::SocketName);

    // 自定义移动组件 —— 逻辑组件，不 SetupAttachment
    OurMovementComponent =
        CreateDefaultSubobject<UXGCollidingPawnMovementComponent>(
            TEXT("CustomMovementComponent"));
    OurMovementComponent->UpdatedComponent = RootComponent;

    AutoPossessPlayer = EAutoReceiveInput::Player0;
}
```

### 输入转发模式

```cpp
void AXGCollidingPawn::SetupPlayerInputComponent(
    UInputComponent* PlayerInputComponent)
{
    Super::SetupPlayerInputComponent(PlayerInputComponent);

    PlayerInputComponent->BindAction(
        "ParticleToggle", IE_Pressed, this, &AXGCollidingPawn::ParticleToggle);

    PlayerInputComponent->BindAxis(
        "MoveForward", this, &AXGCollidingPawn::MoveForward);
    PlayerInputComponent->BindAxis(
        "MoveRight", this, &AXGCollidingPawn::MoveRight);
    PlayerInputComponent->BindAxis(
        "Turn", this, &AXGCollidingPawn::Turn);
}
```

### 输入转发到移动组件

```cpp
void AXGCollidingPawn::MoveForward(float AxisValue)
{
    if (OurMovementComponent &&
        (OurMovementComponent->UpdatedComponent == RootComponent))
    {
        OurMovementComponent->AddInputVector(
            GetActorForwardVector() * AxisValue);
    }
}

void AXGCollidingPawn::MoveRight(float AxisValue)
{
    if (OurMovementComponent &&
        (OurMovementComponent->UpdatedComponent == RootComponent))
    {
        OurMovementComponent->AddInputVector(
            GetActorRightVector() * AxisValue);
    }
}

void AXGCollidingPawn::Turn(float AxisValue)
{
    FRotator NewRotation = GetActorRotation();
    NewRotation.Yaw += AxisValue;
    SetActorRotation(NewRotation);
}

void AXGCollidingPawn::ParticleToggle()
{
    if (OurParticleSystem && OurParticleSystem->Template)
    {
        OurParticleSystem->ToggleActive();
    }
}
```

### GetMovementComponent 重写

```cpp
UPawnMovementComponent* AXGCollidingPawn::GetMovementComponent() const
{
    return OurMovementComponent;
}
```

重写父类方法，让引擎标准的移动相关查询能正确返回自定义移动组件。

## 关键设计模式

### 输入转发模式

Pawn 的输入处理函数不直接执行移动逻辑，而是将输入**转发**给 MovementComponent：

```
Input Axis → Pawn.MoveForward → PawnMovementComponent.AddInputVector
                                  → TickComponent.ConsumeInputVector
                                  → SafeMoveUpdatedComponent
```

这种解耦允许：
1. **移动逻辑集中在 MovementComponent**，多个 Pawn 复用
2. **Pawn 只负责输入方向**，不关心移动物理细节
3. **MovementComponent 可单独测试**

### 逻辑组件 vs 场景组件

| 特性 | 场景组件（SceneComponent） | 逻辑组件（MovementComponent） |
|------|---------------------------|-------------------------------|
| 场景附着 | `SetupAttachment` | 不需要 |
| 变换层级 | 参与 | 不参与 |
| 位置数据 | 有 | 无 |
| 典型用途 | Camera、Mesh、Light | Movement、AI、Audio |

### 碰撞设置要点

```cpp
// 1. 指定碰撞体形状
SphereComponent->InitSphereRadius(40.0f);

// 2. 指定碰撞预设
SphereComponent->SetCollisionProfileName(TEXT("Pawn"));

// 3. 使用 SafeMoveUpdatedComponent 而非直接 SetActorLocation
//     引擎自动处理碰撞响应
SafeMoveUpdatedComponent(MoveDelta, Rotation, true, Hit);

// 4. 碰撞后沿表面滑动
if (Hit.IsValidBlockingHit())
    SlideAlongSurface(MoveDelta, 1.f - Hit.Time, Hit.Normal, Hit);
```

### 代码位置

| 文件 | 说明 |
|------|------|
| [XGCollidingPawn.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/010_ComponentAndCollision/XGCollidingPawn.h) | Pawn 头文件 |
| [XGCollidingPawn.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/010_ComponentAndCollision/XGCollidingPawn.cpp) | Pawn 实现 |
| [XGCollidingPawnMovementComponent.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/010_ComponentAndCollision/XGCollidingPawnMovementComponent.h) | 移动组件头文件 |
| [XGCollidingPawnMovementComponent.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/010_ComponentAndCollision/XGCollidingPawnMovementComponent.cpp) | 移动组件实现 |
