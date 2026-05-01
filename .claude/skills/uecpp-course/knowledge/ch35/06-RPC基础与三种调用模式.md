# RPC 基础与三种调用模式

## 概述

RPC（Remote Procedure Call，远程过程调用）是 UE 中的行为同步机制，允许在一个终端调用函数，在另一个终端远程执行。属性同步处理"数据"的同步，RPC 处理"行为"的同步。

## 三种 RPC 类型

```cpp
// 客户端调用，服务器执行（需 Actor 归调用客户端所有）
UFUNCTION(Server, Reliable)
void Server_Function();

// 服务器调用，指定客户端执行（需 Actor 的 Owner 为该客户端的 PlayerController）
UFUNCTION(Client, Reliable)
void Client_Function();

// 服务器调用，所有终端执行
UFUNCTION(NetMulticast, Reliable)
void Multicast_Function();
```

### 调用规则

| RPC 类型 | 调用位置 | 执行位置 | 前置条件 |
|---------|---------|---------|---------|
| **Server** | 拥有 Actor 的客户端 | 服务器 | Actor 必须归调用客户端所有 |
| **Client** | 服务器 | 指定客户端 | Actor 的 Owner 必须是目标客户端的 PlayerController |
| **Multicast** | 服务器 | 所有终端（含服务器） | 无特殊所有权要求 |

### 关键约束

- RPC 必须从 Actor 上调用
- Actor 必须开启网络复制（`bReplicates = true`）
- Client 和 Multicast RPC 应在服务器调用，在客户端调用无效
- Server RPC 应在客户端调用，在服务器调用退化为普通函数调用

## 所有权与 RPC

所有权是 RPC 的核心前提：

- **Server RPC**：客户端只能在自己拥有的 Actor 上调用 Server RPC
- **Client RPC**：服务器通过 PlayerController 确定目标客户端
- PlayerController 负责网络的连接通道，所有权链以此为基础
- 拾取物品后修改所有权：`SetOwner(PlayerController)`——在服务器上调用

## 典型使用模式

### 客户端→服务器→所有客户端

```cpp
// 客户端调用
UFUNCTION(Server, Reliable)
void Server_AddHealth(int32 Amount);

// 服务器广播结果
UFUNCTION(NetMulticast, Reliable)
void Multicast_PlayEffect();
```

这是最常见的 RPC 使用模式：客户端发起请求→服务器处理→广播结果到所有客户端。

## 实操示例：XGRPC

代码位置：[027_RPC/XGRPC.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/027_RPC/XGRPC.h)

演示链路：Client → Server → Multicast → Client（仅 Owner）

```
玩家按键 → Server RPC → 服务器接收
                         → Multicast RPC → 所有客户端（含服务器）
                         → Client RPC → 仅 Owner 客户端
```

关键发现：
- Multicast 在服务器和所有客户端都执行
- Client RPC 仅发送给 Owner 对应的客户端
- `IsLocallyControlled()` 用于判断当前 Pawn 是否在本机控制

## RPC 蓝图中使用

Blueprint 中通过 Custom Event 的 Replicates 设置实现与 C++ 等效的 RPC 行为：

- Custom Event 属性中设置 Replicates = Server/Client/Multicast
- 在 Blueprint 中可直接调用这些事件
- 蓝图和 C++ 的 RPC 可混合使用

## 蓝图与 C++ 的等价对应

| C++ | Blueprint |
|-----|-----------|
| `UFUNCTION(Server, Reliable)` | Custom Event → Replicates = Server |
| `UFUNCTION(Client, Reliable)` | Custom Event → Replicates = Client |
| `UFUNCTION(NetMulticast, Reliable)` | Custom Event → Replicates = Multicast |
