# 初始化状态机与 PawnExtension

## 概述

`ULyraPawnExtensionComponent` 是角色初始化的中枢组件，基于 `IGameFrameworkInitStateInterface` 实现 4 态初始化链，协调各个子系统的初始化时序。

## 父类体系

```
UGameFrameworkComponent
  └── UPawnComponent
        ├── GetPawn()
        ├── GetPlayerState()
        ├── GetController()
        └── ...
              └── ULyraPawnExtensionComponent : IGameFrameworkInitStateInterface
```

- `UPawnComponent` —— 提供 Pawn/PlayerState/Controller 访问
- `UGameFrameworkComponent` —— 提供 GameInstance/HasAuthority/Timer 访问
- `IGameFrameworkInitStateInterface` —— 初始化状态机接口

## 初始化状态机（IGameFrameworkInitStateInterface）

### 状态链

```
Spawned → DataAvailable → DataInitialized → GameplayReady
```

| 状态 | 含义 | 进入条件 |
|------|------|---------|
| Spawned | 已生成，组件可用 | 有效的 Pawn |
| DataAvailable | PawnData 已加载 | 需要 PawnData 设置 + 服务端/本地需要 Controller |
| DataInitialized | 所有组件均达到 DataAvailable | Manager->HaveAllFeaturesReachedInitState(DataAvailable) |
| GameplayReady | 游戏逻辑可运行 | 始终 true |

### 核心接口方法

| 方法 | 职责 |
|------|------|
| `GetFeatureName()` | 返回 `"PawnExtension"`（`NAME_ActorFeatureName`） |
| `RegisterInitStateFeature()` | 向 ComponentManager 注册自身 |
| `UnregisterInitStateFeature()` | 从 ComponentManager 注销 |
| `CanChangeInitState()` | 检查状态迁移是否可达 |
| `HandleChangeInitState()` | 执行状态迁移时的逻辑（目前 DataInitialized 为 no-op） |
| `CheckDefaultInitialization()` | 尝试沿状态链前进 |
| `ContinueInitStateChain()` | 遍历状态链逐级推进 |
| `BindOnActorInitStateChanged()` | 监听其他 feature 的状态变化 |

### 触发时机

PawnExtension 的状态推进由以下事件触发：

1. **BeginPlay** — 绑定监听全部 feature，尝试推进至 Spawned
2. **其他组件状态变化** — `OnActorInitStateChanged` 监听到其他 feature 到达 DataAvailable 时重试
3. **PawnData 设置** — 服务端 `SetPawnData` 触发 ForceNetUpdate 并调用 CheckDefaultInitialization
4. **ControllerChanged** — Controller 可用时推进
5. **PlayerStateReplicated** — 客户端收到 PlayerState 后推进
6. **SetupPlayerInputComponent** — Input 可用时推进

### CanChangeInitState 逻辑

```
None → Spawned:
  验证 Pawn 有效

Spawned → DataAvailable:
  需要 PawnData != nullptr
  服务端或本地控制端：需要 Controller != nullptr

DataAvailable → DataInitialized:
  Manager->HaveAllFeaturesReachedInitState(Pawn, DataAvailable)
  // 等待所有 feature（HeroComponent、CameraComponent 等）到达 DataAvailable

DataInitialized → GameplayReady:
  始终返回 true
```

## PawnData 管理

- `SetPawnData(InPawnData)`：服务端专用，只能设置一次，触发 `ForceNetUpdate` 并调用 `CheckDefaultInitialization()`
- `OnRep_PawnData`：客户端收到复制后调用 `CheckDefaultInitialization()`
- PawnData 包含：`AbilitySets`（GA/GES/AttributeSet 列表）、`TagRelationshipMapping`（Tag 关系数据资产）、`CameraMode` 等配置

## ASC 管理

### InitializeAbilitySystem

```cpp
void ULyraPawnExtensionComponent::InitializeAbilitySystem(
    ULyraAbilitySystemComponent* InASC, AActor* InOwnerActor)
```

1. **Avatar 冲突处理**：如果当前 ASC 已有不同 avatar，通过 `OtherExtensionComponent->UninitializeAbilitySystem()` 驱逐旧的
2. `InASC->InitAbilityActorInfo(InOwnerActor, Pawn)` — 设置 OwnerActor 和 AvatarActor
3. `InASC->SetTagRelationshipMapping(PawnData->TagRelationshipMapping)` — 设置 Tag 关系
4. `OnAbilitySystemInitialized.Broadcast()` — 广播初始化完成事件

### UninitializeAbilitySystem

- 清理 ASC 绑定
- 广播 `OnAbilitySystemUninitialized`

### RegisterAndCall 模式

```cpp
void OnAbilitySystemInitialized_RegisterAndCall(FOnAbilitySystemInitialized::FDelegate Delegate);
void OnAbilitySystemUninitialized_Register(FOnAbilitySystemUninitialized::FDelegate Delegate);
```

- `_RegisterAndCall` — 注册委托，如果已经初始化则立即调用
- `_Register` — 仅注册，不立即调用

## 健康组件绑定

`ALyraCharacter` 构造函数中按以下顺序绑定：

1. `PawnExtComponent->OnAbilitySystemInitialized_RegisterAndCall(...)`
   - 回调中调用 `HealthComponent->InitializeWithAbilitySystem(ASC)`
   - `InitializeGameplayTags()` 设置初始 GameplayTags
2. `PawnExtComponent->OnAbilitySystemUninitialized_Register(...)`
   - 回调中调用 `HealthComponent->UninitializeFromAbilitySystem()`

## 整体流程

```
Actor 生成
  → OnRegister: RegisterInitStateFeature
  → BeginPlay: BindOnActorInitStateChanged, TryToChangeInitState(Spawned), CheckDefaultInitialization
  → PawnData 设置: CheckDefaultInitialization
  → Controller 接入: CheckDefaultInitialization
  → 所有 feature 到达 DataAvailable: CheckDefaultInitialization
  → GameplayReady: 系统就绪
```

## 代码引用

| 类/文件 | 路径 |
|---------|------|
| `ULyraPawnExtensionComponent` | [LyraPawnExtensionComponent.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/Character/LyraPawnExtensionComponent.h) |
| `ULyraPawnData` | [LyraPawnData.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/Character/LyraPawnData.h) |
| `ULyraAbilityTagRelationshipMapping` | [LyraPawnExtensionComponent.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/Character/LyraPawnExtensionComponent.h) |
| `IGameFrameworkInitStateInterface` | GameFramework 插件 |
