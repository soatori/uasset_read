# RPC 验证与安全

## 概述

RPC WithValidation 是 UE 提供的安全检查机制。通过在 Server RPC 上添加 `WithValidation` 标记，引擎自动生成对应的 `_Validate` 方法。当验证失败时，RPC 调用被丢弃，且客户端连接会被断开。

> 千万不能信任客户端的数据。客户端的数据都在客户端内存中，作弊软件可以任意修改。所有关键逻辑必须在服务器验证。

## 声明方式

```cpp
UFUNCTION(Server, Reliable, WithValidation)
void Server_AddMoney(int32 InAddMoney);
```

引擎自动生成验证方法：

```cpp
bool Server_AddMoney_Validate(int32 InAddMoney)
{
    // 验证逻辑：返回 false 时丢弃调用
    return InAddMoney > 5;
}
```

## 演示示例：XGRPC2

代码位置：[027_RPC/XGRPC2.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/027_RPC/XGRPC2.h)

### 关键逻辑

```cpp
UPROPERTY(ReplicatedUsing = OnRep_Money)
int32 Money;

UFUNCTION(Server, Reliable, WithValidation)
void Server_AddMoney(int32 InAddMoney);

bool Server_AddMoney_Validate(int32 InAddMoney)
{
    return InAddMoney > 5;  // InAddMoney <= 5 时验证失败
}
```

### 行为演示

| 输入 | 验证结果 | 表现 |
|------|---------|------|
| 按 1 → 加 1 | 失败（1 <= 5） | RPC 被丢弃，提示"your connection to the host has been lost" |
| 按 2 → 加 10 | 成功（10 > 5） | Money 增加，通过 OnRep_Money 通知客户端 |

### C++ 中的 OnRep 调用注意

由于 OnRep 在服务器修改属性时不自动触发，需要在 `_Implementation` 中手动调用显示逻辑：

```cpp
void XGRPC2::Server_AddMoney_Implementation(int32 InAddMoney)
{
    int32 OldMoney = Money;
    Money += InAddMoney;
    // 手动调用 OnRep（因为服务器不自动触发）
    OnRep_Money(OldMoney);
}
```

## 验证失败的行为

验证函数返回 `false` 时：

1. RPC 调用被丢弃（不在服务器执行）
2. 客户端连接自动断开
3. 客户端显示"your connection to the host has been lost"

这是 UE 的安全机制：阻止恶意客户端发送非法数据，验证失败视为不可信客户端，直接断开连接。

## 使用建议

| 场景 | 是否需要 WithValidation |
|------|----------------------|
| 关键数据修改（血量、金钱、物品） | 必需 |
| 非关键操作（播放特效、请求信息） | 可选 |
| 参数来自 UI 输入 | 必需 |
| 参数在客户端不可信 | 必需 |
| 参数在服务器已能自行计算 | 不需要 |

## 完整模式

```cpp
// .h 声明
UFUNCTION(Server, Reliable, WithValidation)
void Server_SendCommand(int32 CommandID, const FString& Param);

// .cpp 验证
bool ASomeActor::Server_SendCommand_Validate(int32 CommandID, const FString& Param)
{
    return CommandID >= 0 && Param.Len() <= 128;
}

// .cpp 实现
void ASomeActor::Server_SendCommand_Implementation(int32 CommandID, const FString& Param)
{
    // 安全执行逻辑
}
```
