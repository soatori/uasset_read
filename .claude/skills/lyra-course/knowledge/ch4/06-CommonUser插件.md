# CommonUser 插件

## 概述

CommonUser 插件（`Plugins/CommonUser`）是 Lyra 用户管理的基础设施，提供用户初始化、登录、权限检查等功能。它位于 UE 官方插件层，被 Lyra 项目直接使用。

## 核心类

### UCommonUserSubsystem

- **头文件**：[CommonUserSubsystem.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Plugins/CommonUser/Source/CommonUser/Public/CommonUserSubsystem.h)
- **继承链**：`UGameInstanceSubsystem` → `UCommonUserSubsystem`
- **职责**：管理用户初始化、登录和权限检查

### UCommonUserInfo

- **头文件**：同上文件
- **继承链**：`UObject` → `UCommonUserInfo`
- **职责**：存储单个用户的初始化信息和状态

### FCommonUserInitializeParams

- **头文件**：同上文件
- **职责**：用户初始化参数结构

## 枚举类型

### ECommonUserInitializationState

定义于 [CommonUserTypes.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Plugins/CommonUser/Source/CommonUser/Public/CommonUserTypes.h)

```
Unknown → DoingInitialLogin → DoingNetworkLogin
  → LoggedInOnline (成功)
  → LoggedInLocalOnly (仅本地)
  → FailedToLogin (失败)
```

### ECommonUserPrivilege

| 值 | 说明 |
|----|------|
| CanPlay | 可以游玩 |
| CanPlayOnline | 可以在线游玩 |
| CanCommunicateViaTextOnline | 在线文字交流 |
| CanCommunicateViaVoiceOnline | 在线语音交流 |
| CanUseUserGeneratedContent | 使用用户生成内容 |
| CanUseCrossPlay | 跨平台游玩 |

### ECommonUserAvailability

- **Unknown**：未知
- **NowAvailable**：现在可用
- **PossiblyAvailable**：可能可用
- **CurrentlyUnavailable**：当前不可用
- **AlwaysUnavailable**：始终不可用

### ECommonUserPrivilegeResult

- **Unknown** / **Available** / **UserNotLoggedIn** / **LicenseInvalid** / **VersionOutdated** / **NetworkConnectionUnavailable** / **AgeRestricted** / **AccountTypeRestricted** / **AccountUseRestricted** / **PlatformFailure**

### ECommonUserOnlineContext

- **Game**：游戏上下文
- **Default**：默认
- **Service** / **ServiceOrDefault**：服务上下文
- **Platform** / **PlatformOrDefault**：平台上下文
- **Invalid**：无效

## 初始化流程

### 主要 API

| API | 说明 |
|-----|------|
| `TryToInitializeForLocalPlay` | 本地游玩初始化 |
| `TryToLoginForOnlinePlay` | 在线登录 |
| `TryToInitializeUser` | 完整用户初始化 |
| `ListenForLoginKeyInput` | 监听登录按键 |
| `CancelUserInitialization` | 取消初始化 |
| `TryToLogOutUser` | 登出 |
| `ResetUserState` | 重置状态 |

### FUserLoginRequest 内部状态机

```
TransferPlatformAuthState
  → AutoLoginState (自动登录)
    → LoginUIState (登录 UI)
      → PrivilegeCheckState (权限检查)
```

每个状态使用 `ECommonUserAsyncTaskState`：
- **NotStarted** → **InProgress** → **Done** / **Failed**

### FCommonUserInitializeParams 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| LocalPlayerIndex | 0 | 本地玩家索引 |
| ControllerId | -1 | 控制器 ID |
| PrimaryInputDevice | - | 主要输入设备 |
| RequestedPrivilege | CanPlay | 请求的权限级别 |
| OnlineContext | Game | 在线上下文 |
| bCanCreateNewLocalPlayer | false | 是否可创建新 LocalPlayer |
| bCanUseGuestLogin | false | 是否可使用访客登录 |
| bSuppressLoginErrors | false | 是否抑制登录错误 |
| OnUserInitializeComplete | - | 初始化完成回调 |

## 回调事件

- `HandleIdentityLoginStatusChanged`：身份登录状态变化
- `HandleUserLoginCompleted`：用户登录完成
- `HandleControllerPairingChanged`：控制器配对变化
- `HandleNetworkConnectionStatusChanged`：网络连接状态变化
- `HandleOnLoginUIClosed`：登录 UI 关闭
- `HandleCheckPrivilegesComplete`：权限检查完成

## 在线上下文缓存

CommonUser 子系统维护三个在线上下文缓存：
- **DefaultContextInternal**：默认上下文
- **ServiceContextInternal**：服务上下文
- **PlatformContextInternal**：平台上下文

## 相关文件

- [CommonUserSubsystem.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Plugins/CommonUser/Source/CommonUser/Public/CommonUserSubsystem.h)
- [CommonUserTypes.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Plugins/CommonUser/Source/CommonUser/Public/CommonUserTypes.h)
