# GameCamera — 游戏摄像机切换

## 概述

通过两个 Actor 子类实现在多个摄像机之间切换的摄像机导演系统。`XAGCameraDirector` 是手动指定两个摄像头的简单版本，`XGCameraDirectorModify` 是自动检测场景摄像头的 TArray + USTRUCT 版本。

代码位于 `008_GameCamera/` 目录。

## XAGCameraDirector — 硬编码双摄像头切换

### 头文件

```cpp
UCLASS()
class XGSAMPLEDEMO_API AXAGCameraDirector : public AActor
{
    GENERATED_BODY()

public:
    AXAGCameraDirector();

protected:
    virtual void BeginPlay() override;

public:
    virtual void Tick(float DeltaTime) override;

    UPROPERTY(EditAnywhere, Category = "XG")
    AActor* CameraOne;

    UPROPERTY(EditAnywhere, Category = "XG")
    AActor* CameraTwo;

    float TimeToNextCameraChange = 0.f;
};
```

### Tick 切换逻辑

```cpp
void AXAGCameraDirector::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);

    const float TimeBetweenCameraChanges = 2.0f;
    const float SmoothBlendTime = 0.75f;

    TimeToNextCameraChange -= DeltaTime;

    if (TimeToNextCameraChange <= 0.0f)
    {
        TimeToNextCameraChange += TimeBetweenCameraChanges;

        APlayerController* OurPlayerController =
            UGameplayStatics::GetPlayerController(this, 0);

        if (OurPlayerController)
        {
            if ((OurPlayerController->GetViewTarget() != CameraOne) &&
                (CameraOne != nullptr))
            {
                OurPlayerController->SetViewTarget(CameraOne);
            }
            else if ((OurPlayerController->GetViewTarget() != CameraTwo) &&
                     (CameraTwo != nullptr))
            {
                OurPlayerController->SetViewTargetWithBlend(CameraTwo, SmoothBlendTime);
            }
        }
    }
}
```

### 关键 API

| 函数 | 说明 |
|------|------|
| `UGameplayStatics::GetPlayerController(World, PlayerIndex)` | 获取玩家控制器 |
| `GetViewTarget()` | 获取当前观察目标 |
| `SetViewTarget(Target)` | 立即切换到目标 |
| `SetViewTargetWithBlend(Target, BlendTime)` | 平滑混合切换到目标 |

## XGCameraDirectorModify — 数据驱动 + TArray

### USTRUCT 定义

```cpp
USTRUCT()
struct FXGToggleCamerInfo
{
    GENERATED_BODY()

public:
    UPROPERTY(EditAnywhere, Category = "XG")
    AActor* CameraOne = nullptr;

    UPROPERTY(EditAnywhere, Category = "XG")
    float CameraBlendTime = 0.2f;
};
```

- `USTRUCT()` + `GENERATED_BODY()` 使结构体支持 UE 反射
- `UPROPERTY()` 确保成员在蓝图中可见

### 类定义

```cpp
UCLASS()
class XGSAMPLEDEMO_API AXGCameraDirectorModify : public AActor
{
    GENERATED_BODY()

private:
    UPROPERTY(VisibleAnywhere, Category = "XG")
    TArray<FXGToggleCamerInfo> CamerInfoList;

    float TimeToNextCameraChange = 0.f;
    int32 CamerIndex = -1;
};
```

### BeginPlay 自动检测

```cpp
void AXGCameraDirectorModify::BeginPlay()
{
    Super::BeginPlay();

    TArray<AActor*> MyCamerActors;
    UGameplayStatics::GetAllActorsOfClass(
        this, ACameraActor::StaticClass(), MyCamerActors);

    CamerInfoList.Empty();

    check(MyCamerActors.Num() > 1);

    for (int32 Index = 0; Index < MyCamerActors.Num(); Index++)
    {
        FXGToggleCamerInfo& CamerInfo = CamerInfoList.AddDefaulted_GetRef();
        CamerInfo.CameraOne = MyCamerActors[Index];
        CamerInfo.CameraBlendTime += Index / 4.f;
    }

    CamerIndex = 0;
}
```

### Tick 循环切换

```cpp
void AXGCameraDirectorModify::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);

    const float TimeBetweenCameraChanges = 2.0f;
    TimeToNextCameraChange -= DeltaTime;

    if (TimeToNextCameraChange <= 0.0f)
    {
        TimeToNextCameraChange += TimeBetweenCameraChanges;
        ++CamerIndex;

        if (CamerIndex > CamerInfoList.Num() - 1)
        {
            CamerIndex = 0;
        }

        APlayerController* OurPlayerController =
            UGameplayStatics::GetPlayerController(this, 0);

        AActor* NextCamera = CamerInfoList[CamerIndex].CameraOne;
        float NextBlentTime = CamerInfoList[CamerIndex].CameraBlendTime;

        if (OurPlayerController && NextCamera)
        {
            OurPlayerController->SetViewTargetWithBlend(
                NextCamera, NextBlentTime);
        }
    }
}
```

## 关键设计模式

### GetAllActorsOfClass

```cpp
TArray<AActor*> FoundActors;
UGameplayStatics::GetAllActorsOfClass(World, ACameraActor::StaticClass(), FoundActors);
```

- 通过 TArray 输出参数返回结果
- 是**慢操作**（遍历全场景），只适合在 BeginPlay 等初始化时机调用
- 前提：场景中已放置了 `ACameraActor` 实例

### USTRUCT + TArray 的灵活配置

`XGCameraDirectorModify` 比 `XAGCameraDirector` 的改进：

1. **Struct 封装** — 每个摄像头有自己的 blend time，不再全局统一
2. **TArray 动态扩展** — 不限制摄像头数量，运行时自动检测
3. **check() 校验** — `check(CamerInfoList.Num() > 1)` 在编辑器中断言，避免后续越界
4. **循环索引** — `CamerIndex` 自增 + 回卷实现循环切换

### check() vs 条件判断

| 方式 | 行为 | 适用场景 |
|------|------|---------|
| `check(Condition)` | 条件不满足时触发断言中断（仅 Debug/Editor） | 开发者错误、不应发生的状态 |
| `if (Condition)` | 运行时安全处理 | 外部输入、运行时可预见的边界 |

### 代码位置

| 文件 | 说明 |
|------|------|
| [XAGCameraDirector.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/008_GameCamera/XAGCameraDirector.h) | 基础版头文件 |
| [XAGCameraDirector.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/008_GameCamera/XAGCameraDirector.cpp) | 基础版实现 |
| [XGCameraDirectorModify.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/008_GameCamera/XGCameraDirectorModify.h) | 灵活版头文件 |
| [XGCameraDirectorModify.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/008_GameCamera/XGCameraDirectorModify.cpp) | 灵活版实现 |
