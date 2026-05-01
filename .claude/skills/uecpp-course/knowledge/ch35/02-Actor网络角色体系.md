# Actor 网络角色体系

## 概述

Actor 开启网络复制（bReplicates=true）后获得网络身份。通过 ENetRole 枚举判断 Actor 在不同终端上的角色身份。

## ENetRole 枚举

```cpp
UENUM(BlueprintType)
enum ENetRole : int
{
    ROLE_None,              // 未参与网络复制
    ROLE_SimulatedProxy,    // 远程模拟代理
    ROLE_AutonomousProxy,   // 本地自主代理
    ROLE_Authority,         // 权威控制
    ROLE_MAX,
};
```

### 三种身份的含义

| 身份 | 说明 |
|------|------|
| **Authority** | 服务器端标记，表明当前 Actor 拥有复制权限，会将其信息复制到其他机器上的远程代理 |
| **AutonomousProxy** | 远程代理，能够本地执行部分功能，但会接收权威 Actor 的矫正。通常为玩家直接控制的 Pawn |
| **SimulatedProxy** | 远程代理，由另一台机器上的权威 Actor 完全控制。如拾取物、发射物等 |
| **None** | 网络复制未开启 |

## LocalRole 与 RemoteRole

```cpp
// 当前机端的身份
actor->GetLocalRole();
// 远端机端的身份
actor->GetRemoteRole();
```

### LocalRole 判定

| 终端 | ROLE_SimulatedProxy | ROLE_AutonomousProxy | ROLE_Authority |
|------|---------------------|---------------------|----------------|
| **服务器** | 不存在 | 不存在 | 服务器拥有复制权限 |
| **客户端** | 服务器在当前引擎实例中模拟的角色 | 当前引擎实例中真人操控的角色 | 不存在 |

### RemoteRole 判定

| 终端 | ROLE_SimulatedProxy | ROLE_AutonomousProxy | ROLE_Authority |
|------|---------------------|---------------------|----------------|
| **服务器** | 当前 Actor 在远端是模拟身份 | 当前 Actor 操控权在远端 | 不存在 |
| **客户端** | 不存在 | 不存在 | 拥有当前 Actor 复制权限的权威性 |

### 典型场景

| 场景 | LocalRole | RemoteRole |
|------|-----------|------------|
| Standalone（单人模式） | Authority | SimulatedProxy |
| 服务器上的所有 Actor | Authority | SimulatedProxy/AutonomousProxy |
| 客户端自身的 Pawn | AutonomousProxy | Authority |
| 客户端看到的其他 Pawn | SimulatedProxy | Authority |

## 所有权（Owner）

所有权决定 Actor 隶属于哪个客户端。关键原则：

- 所有权通过 `SetOwner()` 设置，必须在服务器上调用
- Owner 必须是一个 PlayerController
- PlayerController 负责网络的连接通道
- 所有权链：Pawn → 背包 → 武器（递归传递）
- 只有拥有所有权的客户端才能在对应 Actor 上调用 Server RPC

### 016_XGNetDemo 中的角色标识

[016_XGNetDemo](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/016_XGNetDemo/) 工程在多个框架角色上添加了标识名称：

| 类 | 文件 | 同步属性 |
|----|------|---------|
| XGNetCharacter | [XGNetDemoCharacter.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/016_XGNetDemo/Source/XGNetDemo/XGNetDemoCharacter.h) | FString CName |
| XGNetPlayerController | [XGNetDemoPlayerController.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/016_XGNetDemo/Source/XGNetDemo/XGNetDemoPlayerController.h) | FString PCName |
| XGNetPlayerState | [XGNetDemoPlayerState.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/016_XGNetDemo/Source/XGNetDemo/XGNetDemoPlayerState.h) | FString PSName |
| XGNetGameState | [XGNetGameState.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/016_XGNetDemo/Source/XGNetDemo/XGNetGameState.h) | FString GAName |

UI 展示层 [UI_XGNetType](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/016_XGNetDemo/Source/XGNetDemo/UI_XGNetType.h) 通过 ListView 展示这些角色的网络身份信息。

## Actor 相关性（Relevancy）

相关性决定客户端需要接收哪些 Actor 的复制数据：

- **AlwaysRelevant**：始终相关（如 GameState）
- **OnlyRelevantToOwner**：仅对 Owner 相关
- **距离判断**：默认 330m 范围内相关
- **自定义**：重写 `PreReplication()` 或 `IsNetRelevantFor()` 控制相关性

## 优先级（Priority）

当带宽有限时，高优先级的 Actor 先同步：

- 默认 Actor 优先级为 1.0
- Player Pawn 默认为 3.0
- 可通过 NetPriority 属性调整
