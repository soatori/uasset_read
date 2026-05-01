# FPS — 发射物系统

## 概述

发射物（Projectile）是 UE 中常见的游戏实体，特点是生成后在场景中飞行一段时间后自行销毁。通过 `AXGFPSProjectile` 演示发射物的完整实现：SphereComponent 碰撞体 + ProjectileMovementComponent 物理驱动 + OnHit 碰撞响应 + HUD 十字准星。

代码位于 `003_XGFPS0Demo` 项目。

## 发射物类（AXGFPSProjectile）

### 头文件

```cpp
UCLASS()
class XGFPS0DEMO_API AXGFPSProjectile : public AActor
{
    GENERATED_BODY()

public:
    AXGFPSProjectile();

    UPROPERTY(VisibleDefaultsOnly, Category = XG)
    USphereComponent* CollisionComponent;

    UPROPERTY(VisibleAnywhere, Category = XG)
    UProjectileMovementComponent* ProjectileMovementComponent;

    UPROPERTY(VisibleDefaultsOnly, Category = XG)
    UStaticMeshComponent* ProjectileMeshComponent;

    UPROPERTY(VisibleDefaultsOnly, Category = XG)
    UMaterialInstanceDynamic* ProjectileMaterialInstance;

    void FireInDirection(const FVector& ShootDirection);

    UFUNCTION()
    void OnHit(UPrimitiveComponent* HitComponent, AActor* OtherActor,
               UPrimitiveComponent* OtherComponent, FVector NormalImpulse,
               const FHitResult& Hit);
};
```

### 构造函数

```cpp
AXGFPSProjectile::AXGFPSProjectile()
{
    PrimaryActorTick.bCanEverTick = true;

    // 1. SphereComponent 作为根（碰撞根）
    CollisionComponent =
        CreateDefaultSubobject<USphereComponent>(TEXT("SphereComponent"));
    CollisionComponent->InitSphereRadius(15.0f);
    RootComponent = CollisionComponent;
    CollisionComponent->BodyInstance.SetCollisionProfileName(TEXT("ProjectileFile"));

    // 2. ProjectileMovementComponent
    ProjectileMovementComponent =
        CreateDefaultSubobject<UProjectileMovementComponent>(
            TEXT("ProjectileMovementComponent"));
    ProjectileMovementComponent->SetUpdatedComponent(CollisionComponent);
    ProjectileMovementComponent->InitialSpeed = 3000.0f;
    ProjectileMovementComponent->MaxSpeed = 3000.0f;
    ProjectileMovementComponent->bRotationFollowsVelocity = true;
    ProjectileMovementComponent->bShouldBounce = true;
    ProjectileMovementComponent->Bounciness = 0.3f;
    ProjectileMovementComponent->ProjectileGravityScale = 0.0f;

    // 3. 网格体
    ProjectileMeshComponent =
        CreateDefaultSubobject<UStaticMeshComponent>(TEXT("ProjectileMeshComponent"));
    // ... ConstructorHelpers 加载 Mesh 和 Material ...

    // 4. 生命周期
    InitialLifeSpan = 3.0f;

    // 5. 碰撞事件绑定
    CollisionComponent->OnComponentHit.AddDynamic(
        this, &AXGFPSProjectile::OnHit);
}
```

### FireInDirection

```cpp
void AXGFPSProjectile::FireInDirection(const FVector& ShootDirection)
{
    ProjectileMovementComponent->Velocity =
        ShootDirection * ProjectileMovementComponent->InitialSpeed;
}
```

### OnHit 碰撞回调

```cpp
void AXGFPSProjectile::OnHit(
    UPrimitiveComponent* HitComponent,
    AActor* OtherActor,
    UPrimitiveComponent* OtherComponent,
    FVector NormalImpulse,
    const FHitResult& Hit)
{
    if (OtherActor != this && OtherComponent->IsSimulatingPhysics())
    {
        OtherComponent->AddImpulseAtLocation(
            ProjectileMovementComponent->Velocity * 100.0f, Hit.ImpactPoint);
    }

    Destroy();
}
```

## 碰撞系统

### 碰撞预设配置

1. 在 Project Settings → Engine → Collision 创建自定义碰撞通道（如 `Projectile`）
2. 创建碰撞预设（Preset），指定与各通道的响应关系
3. 在 C++ 中应用：

```cpp
CollisionComponent->BodyInstance.SetCollisionProfileName(TEXT("ProjectileFile"));
```

或者使用蓝图级的方法：

```cpp
CollisionComponent->SetCollisionProfileName(TEXT("Projectile"));
```

### OnComponentHit 事件绑定

```cpp
CollisionComponent->OnComponentHit.AddDynamic(
    this, &AXGFPSProjectile::OnHit);
```

`OnHit` 函数签名必须严格匹配 `FComponentHitSignature`：

```cpp
UFUNCTION()
void OnHit(UPrimitiveComponent* HitComponent,
           AActor* OtherActor,
           UPrimitiveComponent* OtherComponent,
           FVector NormalImpulse,
           const FHitResult& Hit);
```

| 参数 | 说明 |
|------|------|
| `HitComponent` | 被碰撞的组件（本对象） |
| `OtherActor` | 碰撞到的其他 Actor |
| `OtherComponent` | 碰撞到的其他组件 |
| `NormalImpulse` | 法线冲量 |
| `Hit` | 详细碰撞结果（含 ImpactPoint 等） |

### 生命周期管理

```cpp
InitialLifeSpan = 3.0f;
```

引擎在 3 秒后自动销毁该 Actor。注意 UE 文档提示"InitialLifeSpan should not be modified once play"，因此应在构造函数中设置，不要在运行时修改。

## HUD — 十字准星

### 头文件

```cpp
UCLASS()
class XGFPS0DEMO_API AXGFPSHUD : public AHUD
{
    GENERATED_BODY()

public:
    virtual void DrawHUD() override;

protected:
    UPROPERTY(EditDefaultsOnly)
    class UTexture2D* CrosshairTexture;
};
```

### DrawHUD 实现

```cpp
void AXGFPSHUD::DrawHUD()
{
    Super::DrawHUD();

    if (CrosshairTexture)
    {
        FVector2D Center(
            Canvas->ClipX * 0.5f, Canvas->ClipY * 0.5f);

        FVector2D CrossHairDrawPosition(
            Center.X - (CrosshairTexture->GetSurfaceWidth() * 0.5f),
            Center.Y - (CrosshairTexture->GetSurfaceHeight() * 0.5f));

        FCanvasTileItem TileItem(
            CrossHairDrawPosition,
            CrosshairTexture->GetResource(),
            FLinearColor::White);
        TileItem.BlendMode = SE_BLEND_Translucent;
        Canvas->DrawItem(TileItem);
    }
}
```

### HUD 关键点

- HUD 只存在于**客户端**，不存在于服务器
- `DrawHUD` 每帧调用，使用 `UCanvas*` 进行绘制
- `DrawItem` 接受 `FCanvasTileItem` 绘制纹理
- HUD 类需要在 GameMode 中指定（Blueprint 或 C++）
- 当使用 `FTextureReference` 或特定纹理操作时，需要在 `Build.cs` 中添加 `RenderCore` 模块：

```csharp
PublicDependencyModuleNames.AddRange(
    new string[] { "Core", "CoreUObject", "Engine", "InputCore", "RenderCore" });
```

## 关键设计模式

### Actor vs Pawn/Character 的选择

| 类型 | 说明 | 适用场景 |
|------|------|---------|
| `AActor` | 最基础的 Actor | 发射物、静态物体、触发器 |
| `APawn` | 可被 Controller 控制的 Actor | 玩家/AI 实体 |
| `ACharacter` | 含 CharacterMovementComponent 的 Pawn | 需要标准移动的角色 |

发射物使用 `AActor` 而非 Pawn/Character，因为它**不接收玩家输入**，由 ProjectileMovementComponent 物理驱动。

### SpawnActor 参数

```cpp
FActorSpawnParameters SpawnParams;
SpawnParams.Owner = this;
SpawnParams.Instigator = GetInstigator();
// CollisionHandlingOverride 可选

World->SpawnActor<AXGFPSProjectile>(
    ProjectileClass, MuzzleLocation, MuzzleRotation, SpawnParams);

// 生成后设置运动方向
Projectile->FireInDirection(LaunchDirection);
```

| SpawnParams 字段 | 说明 |
|------------------|------|
| `Owner` | 拥有者 |
| `Instigator` | 引发者（用于伤害归因等） |
| `CollisionHandlingOverride` | 可选，指定生成时碰撞处理方式（如 `ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButAlwaysSpawn`） |

### 代码位置

| 文件 | 说明 |
|------|------|
| [XGFPSProjectile.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/003_XGFPS0Demo/Source/XGFPS0Demo/XGFPSProjectile.h) | 发射物头文件 |
| [XGFPSProjectile.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/003_XGFPS0Demo/Source/XGFPS0Demo/XGFPSProjectile.cpp) | 发射物实现 |
| [XGFPSHUD.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/003_XGFPS0Demo/Source/XGFPS0Demo/XGFPSHUD.h) | HUD 头文件 |
| [XGFPSHUD.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/003_XGFPS0Demo/Source/XGFPS0Demo/XGFPSHUD.cpp) | HUD 实现 |
| [XGFPS0Demo.Build.cs](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/003_XGFPS0Demo/Source/XGFPS0Demo/XGFPS0Demo.Build.cs) | 模块配置（含 RenderCore 依赖） |
