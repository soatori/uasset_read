# DS 动态创建与多 Target 打包部署

## DS 动态创建

### FPlatformProcess::CreateProc

DSM 通过 `FPlatformProcess::CreateProc` 在运行时动态拉起 DS 进程：

```cpp
void AXGMultiManageGameMode::CreateNewDSProcess(
    int32 InPort, const FString& InLevelName)
{
    FString ExePath = FPaths::ProjectDir() + TEXT("Server/XGMultiGame.exe");
    FString Params = FString::Printf(TEXT(" -log -port=%d"), InPort);

    FProcHandle DSProcHandle = FPlatformProcess::CreateProc(
        *ExePath,
        *Params,
        true,   // bLaunchDetached: 独立进程，不随父进程关闭
        false,  // bLaunchHidden: 不隐藏窗口
        false,  // bLaunchReallyHidden: 不真正隐藏
        nullptr,// ProcessID 输出指针（不需要）
        0,      // PriorityModifier: 默认优先级
        nullptr,// WorkingDirectory: 默认项目目录
        nullptr // PipeWrite: 不需要管道
    );
}
```

### 参数说明

| 参数 | 值 | 说明 |
|------|-----|------|
| `ExePath` | `ProjectDir/Server/XGMultiGame.exe` | 打包生成的 DS 可执行文件 |
| `Params` | `-log -port=XXXX` | `-log` 显示控制台窗口；`-port=` 指定服务端端口 |
| `bLaunchDetached` | `true` | 新进程独立运行，DSM 关闭后 DS 仍可运行 |

### 端口分配策略

字幕演示中使用手动递增策略：

```cpp
int32 NextAvailablePort = 7777;  // 起始端口

void AXGMultiManageGameMode::HandleReqPlayerCreateNewLevel(
    const FXGMultiMessage& MultiMessage, const FGuid& ConnectionID)
{
    CreateNewDSProcess(NextAvailablePort++, TEXT("ThirdPersonMap"));
    // ...
}
```

生产环境中应使用真正的端口分配策略（检测端口占用、端口池管理等），本章作为案例演示仅做最简实现。

## 多 Target 打包

### 背景

`010_XGMultiGame` 是一套代码需要打出两个不同角色的包：

| 包类型 | 用途 | 运行方式 | NetMode |
|--------|------|---------|---------|
| Client 包 | 玩家客户端 | 用户双击运行 | `NM_Client` |
| Server 包 | DS 服务器 | `.bat` 脚本启动（带 `-log` 参数） | `NM_DedicatedServer` |

### Target.cs 文件

#### 原始 Editor Target

```csharp
public class XGMultiGameEditorTarget : TargetRules
{
    public XGMultiGameEditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.V5;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_4;
        ExtraModuleNames.Add("XGMultiGame");
    }
}
```

#### Client Target（复制的 Editor Target，改为 Client）

```csharp
public class XGMultiGameClientTarget : TargetRules
{
    public XGMultiGameClientTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Client;   // ← 关键：从 Editor 改为 Client
        DefaultBuildSettings = BuildSettingsVersion.V5;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_4;
        ExtraModuleNames.Add("XGMultiGame");
    }
}
```

#### Server Target（复制的 Editor Target，改为 Server）

```csharp
public class XGMultiGameServerTarget : TargetRules
{
    public XGMultiGameServerTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Server;   // ← 关键：从 Editor 改为 Server
        DefaultBuildSettings = BuildSettingsVersion.V5;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_4;
        ExtraModuleNames.Add("XGMultiGame");
    }
}
```

### TargetType 说明

| `TargetType` | 用途 | 特性 |
|-------------|------|------|
| `Editor` | 编辑器开发 | 包含 Editor 模块、蓝图编译等 |
| `Client` | 玩家客户端 | 不包含 Editor 模块，含渲染/输入/UI |
| `Server` | 专用服务器 | 不包含 Editor 模块，不含渲染/输入/UI（无图形界面） |

## 打包流程

### 步骤 1：打包客户端

```
1. 在编辑器 File → Package Project → Build Configuration: Development
2. 选择打包目录（如 Desktop/MMOServer/NEW）
3. 平台选择：Windows
4. 等待打包完成（生成 Windows 目录，含 XGMultiGame.exe）
```

**关键配置**：
| 设置 | 值 |
|------|-----|
| Build Configuration | Development |
| Target | Client（在 Project → Package 中选择 XGMultiGameClient） |

**输出目录结构（Client 包）**：
```
Windows/
├── XGMultiGame/
│   ├── Binaries/
│   ├── Content/
│   ├── XGMultiGame.exe     ← 客户端可执行文件
│   └── ...
```

### 步骤 2：编译服务器二进制

```powershell
# 在引擎目录或通过编辑器编译 Server Target
# 方法 1：UBT 命令行
UE5.4\Engine\Binaries\DotNET\UnrealBuildTool.exe
    XGMultiGameServer Win64 Development
    -Project="path\to\XGMultiGame.uproject"

# 方法 2：编辑器 → Platforms → Windows → Build XGMultiGameServer (Development)
```

**编译产出**：
```
Binaries/Win64/
├── XGMultiGameServer.exe      ← 服务器可执行文件
├── XGMultiGameServer.pdb      ← 调试符号（可选删除）
└── ...
```

### 步骤 3：替换服务器二进制（手动操作）

```
1. 在 Client 包中创建 Server 目录
2. 将 XGMultiGameServer.exe 拷贝为 Server/XGMultiGame.exe（重命名）
3. 可选：在 Server/ 目录下创建 StartServer.bat
```

**最终目录结构**：
```
MMOServer/
├── Windows/                    ← 客户端包（完整目录）
│   ├── XGMultiGame/           ← 客户端目录
│   │   ├── Binaries/
│   │   ├── Content/
│   │   └── XGMultiGame.exe
│   └── ...
├── Server/                     ← 新建，放服务器二进制
│   ├── XGMultiGame.exe        ← 从 Server Build 拷贝重命名
│   ├── StartServer(7777).bat  ← 启动脚本（端口 7777）
│   ├── StartServer(8888).bat  ← 启动脚本（端口 8888）
│   └── StartServer(8889).bat  ← 启动脚本（端口 8889）
```

### 步骤 4：创建 .bat 启动脚本

```bat
@echo off
REM StartServer.bat
Start Server\XGMultiGame.exe -log -port=%1
pause
```

为不同端口创建专用脚本或使用参数化调用：

```bat
REM StartServer(7777).bat
Start Server\XGMultiGame.exe -log -port=7777
```

关键命令行参数：

| 参数 | 说明 |
|------|------|
| `-log` | 显示控制台日志窗口（DS 必须） |
| `-port=XXXX` | 指定监听端口（DSM 通过此参数告知 DS 使用哪个端口） |
| `-game` | (隐含) 以游戏模式运行 |

## 部署验证流程

### 测试场景 1：DS 自动注册

```
1. 启动 DSM：在编辑器中打开 XGMultiManage.uproject → PIE
   预期：DSM 日志显示 WebSocket Server 启动在 9033 端口
2. 启动 DS：双击 StartServer(7777).bat
   预期：DS 控制台显示连接 DSM 成功，发送 ReqInitDSRole 消息
          DSM 日志显示收到注册，返回 RespInitDSRole
3. 验证 DSList：DSM 断点查看 DSList 包含新注册的 DS 信息
```

### 测试场景 2：客户端获取 DS 列表

```
1. 已完成 场景 1（DSM + 至少一个 DS 正在运行）
2. 启动 Client：双击 Windows/XGMultiGame/XGMultiGame.exe
   预期：客户端自动连接 DSM，按 1 键触发 RequestAllDSInfo()
         屏幕显示已注册的 DS 列表（IP:端口 + 关卡名）
```

### 测试场景 3：动态创建 DS

```
1. 已完成 场景 2（客户端已连接并获取到 DS 列表）
2. 按 2 键触发 RequestCreateNewDS()
   预期：DSM 拉起新 DS 进程（新控制台窗口出现）
         DSM 回复 RespPlayerCreateNewLevel
3. 再次按 1 键：DS 列表应包含新创建的 DS
```

### 测试场景 4：连接断开处理

```
1. 关闭正在运行的 DS 进程（控制台窗口关闭）
2. DSM 日志：OnDisconnected 被触发
3. 断点验证：DSList 中对应的 DS 记录已被移除
```

### 测试场景 5：多 DS + 多客户端

```
1. 启动 DSM
2. 启动 DS 实例 1（端口 7777）
3. 启动 DS 实例 2（端口 8888）
4. 启动多个客户端（open 127.0.0.1:7777 / 8888）
5. 每个按 1 键查看 DS 列表应显示 2 个实例
```

## 完整启动顺序

```
1. 启动 DSM（编辑器或打包）
2. 启动第一个 DS（StartServer.bat 端口 7777）
   └→ 自动向 DSM 注册
3. 启动第二个 DS（StartServer.bat 端口 8888）
   └→ 自动向 DSM 注册
4. 启动客户端（双击 XGMultiGame.exe）
   └→ 自动连接 DSM → 注册身份
5. (可选) 按 1 查看 DS 列表 → 获取已注册的 7777 和 8888
6. (可选) 按 2 创建新 DS → DSM 分配新端口并拉起进程
7. (可选) 客户端 open 127.0.0.1:XXXX 进入指定 DS
```

## 已知限制

| 限制 | 说明 |
|------|------|
| 端口硬编码/手动递增 | 实际生产需端口池管理 |
| `.bat` 手动启动 DS | 生产环境应使用进程管理工具（如 Docker、Supervisor） |
| 无心跳检测 | DS 崩溃后 DSM 无法主动感知（仅依赖 WebSocket OnDisconnected） |
| 时序 BUG | LinkSocketServer 回调早于事件绑定，需延迟连接 |
| 同一代码工程 | DS 和 Client 是同一份代码，不能独立扩展 DS 专用逻辑 |
| 手动端口/关卡名参数化 | 不同 DS 加载不同关卡需要更完善的启动参数设计 |

## 工程配置参考

### .uproject 插件引用

```json
{
    "FileVersion": 3,
    "EngineAssociation": "5.4",
    "Category": "",
    "Description": "",
    "Modules": [
        {
            "Name": "XGMultiGame",
            "Type": "Runtime",
            "LoadingPhase": "Default"
        }
    ],
    "Plugins": [
        {
            "Name": "XGSampleWSM",
            "Enabled": true
        }
    ]
}
```

**注意**：`.uproject` 是 JSON 格式，**不能加注释**。

### Build.cs 模块引用

[XGMultiGame.Build.cs](../../code/010_XGMultiGame/Source/XGMultiGame/XGMultiGame.Build.cs)：

```csharp
PublicDependencyModuleNames.AddRange(new string[]
{
    "Core",
    "CoreUObject",
    "Engine",
    "InputCore",
    "EnhancedInput",
    "XGSampleWSM",
    "Json",
    "JsonUtilities"
});
```
