# PlayerCamera — 玩家控制的摄像机

## 概述

通过 `XGPawnWithCamera` 实现一个可自由移动、旋转、缩放的 Pawn。演示 `USceneComponent` → `UStaticMeshComponent` → `USpringArmComponent` → `UCameraComponent` 的组件链组装方式。

代码位于 `009_PlayerCamera/` 目录。

## 组件结构

```
Root (USceneComponent)
  └─ StaticMeshComp (UStaticMeshComponent)   ← 视觉表示
       └─ SpringArmComp (USpringArmComponent)  ← 弹簧臂
            └─ CameraComp (UCameraComponent)    ← 摄像机
```

## 头文件

```cpp
UCLASS()
class XGSAMPLEDEMO_API AXGPawnWithCamera : public APawn
{
    GENERATED_BODY()

protected:
    UPROPERTY(EditAnywhere)
    class USpringArmComponent* SpringArmComp;

    UPROPERTY(EditAnywhere)
    class UCameraComponent* CameraComp;

    UPROPERTY(EditAnywhere)
    class UStaticMeshComponent* StaticMeshComp;

    FVector2D MovementInput;
    FVector2D CameraInput;
    float ZoomFactor = 1.0f;
    bool bZoomingIn = false;

    void MoveForward(float AxisValue);
    void MoveRight(float AxisValue);
    void PitchCamera(float AxisValue);
    void YawCamera(float AxisValue);
    void ZoomIn();
    void ZoomOut();

public:
    virtual void Tick(float DeltaTime) override;
    virtual void SetupPlayerInputComponent(
        class UInputComponent* PlayerInputComponent) override;
};
```

## 构造函数 — 组件创建与绑定

```cpp
AXGPawnWithCamera::AXGPawnWithCamera()
{
    PrimaryActorTick.bCanEverTick = true;

    RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("RootComponent"));
    StaticMeshComp = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("MeshComponent"));
    SpringArmComp = CreateDefaultSubobject<USpringArmComponent>(TEXT("SpringArmComponent"));
    CameraComp = CreateDefaultSubobject<UCameraComponent>(TEXT("CameraComponent"));

    // 组件层级绑定
    StaticMeshComp->SetupAttachment(RootComponent);
    SpringArmComp->SetupAttachment(StaticMeshComp);
    CameraComp->SetupAttachment(SpringArmComp, USpringArmComponent::SocketName);

    // SpringArm 参数
    SpringArmComp->SetRelativeLocationAndRotation(
        FVector(0.0f, 0.0f, 50.0f), FRotator(-60.0f, 0.0f, 0.0f));
    SpringArmComp->TargetArmLength = 400.f;
    SpringArmComp->bEnableCameraLag = true;
    SpringArmComp->CameraLagSpeed = 3.0f;

    AutoPossessPlayer = EAutoReceiveInput::Player0;
}
```

## PlayerInput — 输入绑定

```cpp
void AXGPawnWithCamera::SetupPlayerInputComponent(
    UInputComponent* PlayerInputComponent)
{
    Super::SetupPlayerInputComponent(PlayerInputComponent);

    // Action 绑定（按键事件）
    InputComponent->BindAction("ZoomIn", IE_Pressed, this, &AXGPawnWithCamera::ZoomIn);
    InputComponent->BindAction("ZoomIn", IE_Released, this, &AXGPawnWithCamera::ZoomOut);

    // Axis 绑定（持续输入）
    InputComponent->BindAxis("MoveForward", this, &AXGPawnWithCamera::MoveForward);
    InputComponent->BindAxis("MoveRight", this, &AXGPawnWithCamera::MoveRight);
    InputComponent->BindAxis("CameraPitch", this, &AXGPawnWithCamera::PitchCamera);
    InputComponent->BindAxis("CameraYaw", this, &AXGPawnWithCamera::YawCamera);
}
```

### 输入处理函数

```cpp
// 将输入值存入中间变量，Tick 中统一处理
void AXGPawnWithCamera::MoveForward(float AxisValue)
{
    MovementInput.X = FMath::Clamp<float>(AxisValue, -1.0f, 1.0f);
}

void AXGPawnWithCamera::MoveRight(float AxisValue)
{
    MovementInput.Y = FMath::Clamp<float>(AxisValue, -1.0f, 1.0f);
}

void AXGPawnWithCamera::PitchCamera(float AxisValue)
{
    CameraInput.Y = AxisValue;
}

void AXGPawnWithCamera::YawCamera(float AxisValue)
{
    CameraInput.X = AxisValue;
}

void AXGPawnWithCamera::ZoomIn()  { bZoomingIn = true; }
void AXGPawnWithCamera::ZoomOut() { bZoomingIn = false; }
```

## Tick — 每帧逻辑

```cpp
void AXGPawnWithCamera::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);

    // 1. 缩放 —— 基于时间插值
    if (bZoomingIn)
        ZoomFactor += DeltaTime / 0.5f;      // 0.5 秒放大
    else
        ZoomFactor -= DeltaTime / 0.25f;     // 0.25 秒缩小

    ZoomFactor = FMath::Clamp<float>(ZoomFactor, 0.0f, 1.0f);

    // 2. 应用缩放
    CameraComp->FieldOfView = FMath::Lerp<float>(90.0f, 60.0f, ZoomFactor);
    SpringArmComp->TargetArmLength = FMath::Lerp<float>(400.0f, 300.0f, ZoomFactor);

    // 3. 旋转 —— 绕 Actor Yaw
    {
        FRotator NewRotation = GetActorRotation();
        NewRotation.Yaw += CameraInput.X;
        SetActorRotation(NewRotation);
    }

    // 4. 俯仰 —— 限制旋转范围
    {
        FRotator NewRotation = SpringArmComp->GetComponentRotation();
        NewRotation.Pitch = FMath::Clamp(
            NewRotation.Pitch + CameraInput.Y, -80.0f, -15.0f);
        SpringArmComp->SetWorldRotation(NewRotation);
    }

    // 5. 移动
    if (!MovementInput.IsZero())
    {
        MovementInput = MovementInput.GetSafeNormal() * 100.0f;
        FVector NewLocation = GetActorLocation();
        NewLocation += GetActorForwardVector() * MovementInput.X * DeltaTime;
        NewLocation += GetActorRightVector() * MovementInput.Y * DeltaTime;
        SetActorLocation(NewLocation);
    }
}
```

## 关键设计模式

### 组件分离架构

| 组件 | 类型 | 作用 |
|------|------|------|
| `RootComponent` | `USceneComponent` | 根节点，不渲染 |
| `StaticMeshComp` | `UStaticMeshComponent` | 视觉表示 |
| `SpringArmComp` | `USpringArmComponent` | 缓冲跟随、碰撞避让 |
| `CameraComp` | `UCameraComponent` | 视口渲染 |

### 输入中间变量模式

输入处理函数不直接执行业务逻辑，而是**存储到中间变量**（`MovementInput`、`CameraInput`），在 Tick 中统一处理。好处：

1. **帧率独立** — Tick 中乘以 DeltaTime，与输入频率解耦
2. **逻辑集中** — 所有业务逻辑在 Tick 一处维护
3. **避免重复计算** — 多次同帧输入只计算一次

### SpringArm 参数

| 参数 | 作用 |
|------|------|
| `TargetArmLength` | 弹簧臂长度（摄像机距离） |
| `bEnableCameraLag` | 启用滞后跟随，产生平滑感 |
| `CameraLagSpeed` | 滞后速度，值越小越"拖尾" |

### 自动 Possess

```cpp
AutoPossessPlayer = EAutoReceiveInput::Player0;
```

在构造函数中设置，游戏启动时自动将 Pawn 分配给 Player 0 控制，无需手动拖入。

### 代码位置

| 文件 | 说明 |
|------|------|
| [XGPawnWithCamera.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/009_PlayerCamera/XGPawnWithCamera.h) | Pawn 头文件 |
| [XGPawnWithCamera.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/009_PlayerCamera/XGPawnWithCamera.cpp) | Pawn 实现 |
