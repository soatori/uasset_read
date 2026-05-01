# GameInstance 与登录流程

## ULyraGameInstance

[ULyraGameInstance](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/System/LyraGameInstance.h) 继承自 `UCommonGameInstance`，是跨地图持久化的全局状态管理器。

### 职责

1. **用户登录管理** — 处理外部账户登录、平台身份认证
2. **Experience 生命周期** — 与 `ULyraExperienceManagerComponent` 协同
3. **会话管理** — 创建/销毁游戏会话
4. **跨地图持久数据** — 玩家设置、调试控制台变量

## 用户登录流程

```
ULyraGameInstance::BeginLoginAttempt()
  → 检查是否需要在线子系统认证
  → 如果不需要，直接完成本地用户创建
  → 如果需要，调用 OnlineSubsystem 进行登录
  → 登录完成后回调 OnUserLoginComplete()
  → 创建/绑定 ULyraLocalPlayer
  → 准备进入游戏世界
```

## 令牌验证流程

Lyra 使用令牌（Token）验证用户身份，流程如下：

1. **客户端请求令牌** — 客户端向在线服务请求身份令牌
2. **服务器验证令牌** — 服务器收到令牌后向在线服务验证
3. **验证通过** — 服务器允许客户端加入游戏会话
4. **验证失败** — 服务器拒绝连接

令牌类型：
- **身份令牌（Identity Token）** — 标识用户身份的凭证
- **会话令牌（Session Token）** — 标识游戏会话的凭证
- **验证令牌（Validation Token）** — 用于服务器间验证的凭证

## DTLS 概念

DTLS（Datagram Transport Layer Security）是 UDP 上的 TLS 加密协议，Lyra 用于保护网络传输。

### 在 Lyra 中的使用

- 在 `DTLSHandlerComponent` 模块中实现
- 用于多人游戏中的加密通信
- 防止中间人攻击和数据篡改

### DTLS 与 TCP/UDP 的关系

| 特性 | TLS (TCP) | DTLS (UDP) |
|------|-----------|-------------|
| 传输层 | TCP（可靠） | UDP（不可靠） |
| 加密 | 支持 | 支持 |
| 丢包处理 | 自动重传 | 由上层处理 |
| 延迟 | 较高（握手 1-RTT） | 较低（0-RTT 可选） |

## ULyraGameInstance 调试技巧

通过控制台命令查看当前 GameInstance：

```
showdebug GameInstance
```

常用调试命令：

```
// 切换 Experience 重新加载
ce Experience.Unload
ce Experience.Load {ExperienceName}
```
