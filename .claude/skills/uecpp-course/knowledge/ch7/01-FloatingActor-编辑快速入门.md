# FloatingActor — 编辑快速入门

## 概述

通过两个 Actor 子类（`AFloatingActor` / `AFloatingActorModify`）演示 UE C++ 编辑与运行时数据驱动的基本模式。代码位于 `007_QuickStart/` 目录。

## AFloatingActor — 硬编码实现

### 头文件

```cpp
UCLASS()
class XGSAMPLEDEMO_API AFloatingActor : public AActor
{
    GENERATED_BODY()

public:
    AFloatingActor();

    UPROPERTY(VisibleAnywhere)
    UStaticMeshComponent* VisualMesh;

protected:
    virtual void BeginPlay() override;

public:
    virtual void Tick(float DeltaTime) override;
};
```

### 构造函数

```cpp
AFloatingActor::AFloatingActor()
{
    PrimaryActorTick.bCanEverTick = true;

    VisualMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Mesh"));
    VisualMesh->SetupAttachment(RootComponent);

    static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeVisualAsset(
        TEXT("/Game/StarterContent/Shapes/Shape_Cone.Shape_Cone"));

    if (CubeVisualAsset.Succeeded())
    {
        VisualMesh->SetStaticMesh(CubeVisualAsset.Object);
        VisualMesh->SetRelativeLocation(FVector(0.0f, 0.0f, 0.0f));
    }
}
```

### Tick 逻辑

```cpp
void AFloatingActor::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);

    // Z 轴正弦浮动
    float RunningTime = GetGameTimeSinceCreation();
    float DeltaHeight = (FMath::Sin(RunningTime + DeltaTime) - FMath::Sin(RunningTime));
    NewLocation.Z += DeltaHeight * 20.0f;

    // Yaw 轴连续旋转
    float DeltaRotation = DeltaTime * 20.0f;
    NewRotation.Yaw += DeltaRotation;

    SetActorLocationAndRotation(NewLocation, NewRotation);
}
```

- `GetGameTimeSinceCreation()` 获取 Actor 从生成开始到当前的时间
- 用 `FMath::Sin` 前后帧差值实现帧率无关的平滑浮动
- `SetActorLocationAndRotation` 同时设置位置和旋转

## AFloatingActorModify — 数据驱动改进

### 暴露的属性

```cpp
UPROPERTY(VisibleAnywhere)
UStaticMeshComponent* VisualMesh;

UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = "XG")
UStaticMesh* NewMesh;

UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "FloatingActor")
float FloatSpeed = 20.0f;

UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "FloatingActor")
float RotationSpeed = 20.0f;
```

### 构造函数 vs BeginPlay

```cpp
AFloatingActorModify::AFloatingActorModify()
{
    PrimaryActorTick.bCanEverTick = true;
    VisualMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Mesh"));
    VisualMesh->SetupAttachment(RootComponent);
    // 不在构造函数中设置 Mesh —— 让蓝图在 BeginPlay 前赋值
}

void AFloatingActorModify::BeginPlay()
{
    Super::BeginPlay();

    if (NewMesh)
    {
        VisualMesh->SetStaticMesh(NewMesh);
    }
}
```

### 数据驱动 Tick

```cpp
void AFloatingActorModify::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);

    float RunningTime = GetGameTimeSinceCreation();
    float DeltaHeight = (FMath::Sin(RunningTime + DeltaTime) - FMath::Sin(RunningTime));
    NewLocation.Z += DeltaHeight * FloatSpeed;  // 使用暴露属性

    float DeltaRotation = DeltaTime * RotationSpeed;
    NewRotation.Yaw += DeltaRotation;

    SetActorLocationAndRotation(NewLocation, NewRotation);
}
```

## 核心设计模式

### 构造函数 vs BeginPlay 的选择

| 时机 | 适用场景 |
|------|---------|
| **构造函数** | 创建组件、设置默认值、加载硬编码资源 |
| **BeginPlay** | 依赖 Blueprint 赋值后生效的逻辑（如动态 Mesh 切换） |

Blueprint 属性赋值发生在构造函数之后、BeginPlay 之前。因此依赖 `EditAnywhere` 属性做决策的逻辑必须在 BeginPlay 中执行。

### 代码位置

| 文件 | 说明 |
|------|------|
| [FloatingActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/007_QuickStart/FloatingActor.h) | 硬编码浮动 Actor 头文件 |
| [FloatingActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/007_QuickStart/FloatingActor.cpp) | 硬编码实现 |
| [FloatingActorModify.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/007_QuickStart/FloatingActorModify.h) | 数据驱动版本头文件 |
| [FloatingActorModify.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/007_QuickStart/FloatingActorModify.cpp) | 数据驱动版本实现 |
