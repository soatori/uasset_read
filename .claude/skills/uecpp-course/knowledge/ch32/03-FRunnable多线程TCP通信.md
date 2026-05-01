# 第三十二章·案例 11：FRunnable 多线程 TCP 通信

## 概述

TCP 通信必须运行在独立线程上，避免阻塞游戏主线程。本章使用 FRunnable 作为线程主体，AsyncAction 作为业务调度层，通过回调代理实现线程间通信。

## 线程架构

```
Game Thread                          TCP Thread
    │                                    │
    │  CreateRunnable()                  │
    │  ──► MakeShared<Runnable>(IP,port) │
    │  ──► 绑定回调到 Runnable           │
    │  ──► FRunnableThread::Create       │
    │  ──► SetStatus(Connected)          │
    │                                    │
    │                               Init()
    │                               Run() ← while(不停止)
    │                                    │
    │  ◄── OnReceived (回调)─── Recv()   │
    │  ◄── OnDisconnected (回调) ── Close │
    │                                    │
    │  CloseRunnable()                   │
    │  ──► Stop() ──► bShouldStop=true   │
    │  ──► WaitForCompletion()           │
    │  ──► EmailThread = nullptr         │
```

## FRunnable 生命周期

```cpp
class XGSampleEMailRunnable : public FRunnable
```

### Init（初始化阶段）

- 设置线程运行标志 `bRunning = true`
- 回调 `InitDelegate`

### Run（运行阶段）

1. **Socket 创建**：使用 `FTcpSocketBuilder` 创建 TCP Socket
   ```cpp
   FSocket* Socket = FTcpSocketBuilder(TEXT("XGEmailSocket"))
       .AsBlocking()      // 阻塞模式
       .WithReceiveBufferSize(1024 * 1024)
       .Build();
   ```
   - 阻塞模式与后续 `HasPendingConnection` / `HasPendingData` 配合使用
   - `FTcpSocketBuilder` 失败返回 `nullptr`

2. **域名解析**：通过 `ISocketSubsystem` 将域名转为 IP
   ```cpp
   ISocketSubsystem* SocketSubsystem = ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM);
   TSharedPtr<FInternetAddr> Addr = SocketSubsystem->GetAddressFromString(Host);
   Addr->SetPort(Port);
   ```
   - 域名解析是阻塞操作，但因在独立线程中执行不会影响主线程
   - 同一子系统实例可用于后续 Socket 销毁

3. **连接**：调用 `Socket->Connect(*Addr)`，成功后设置 `bConnected = true`

4. **主循环**：`while (!bShouldStop)` 循环
   ```
   while (!bShouldStop)
   ├── Socket->HasPendingConnection(FTimespan::FromSeconds(1))
   │    等待连接建立（最多 1 秒超时）
   │
   ├── if (!bConnected && 连接完成) → 回调 OnConnected
   │    设置 bConnected = true
   │
   ├── Socket->HasPendingData(HasData) → 检查是否有可读数据
   │
   ├── if (HasData) → Recv 接收数据
   │    ├── uint8 缓冲区接收
   │    ├── ANSI→TCHAR 转换
   │    └── 回调 OnReceived(TCHAR 字符串)
   │
   └── if (bConnected && 有数据待发送)
         → 从发送队列取数据 → Socket->Send → 回调 OnSent
   ```
   - `HasPendingConnection` 有 1 秒超时，防止无限阻塞
   - `HasPendingData` 非阻塞检查
   - 接收到的 ANSI 字节需转换为 TCHAR 再回调

### Stop（停止信号）

- 设置 `bShouldStop = true`，主循环退出
- 设置 `bRunning = false`

### Exit（清理阶段）

- 关闭 Socket：`Socket->Close()`（如有必要）
- 销毁 Socket：`SocketSubsystem->DestroySocket(Socket)`，然后置 `nullptr`
- 回调 `CloseDelegate`

## 消息发送机制

AsyncAction 的 `SendMessage` 方法：

```
SendMessage(FString Message)
  ├── 访问 Runnable 的 SendDelegate
  ├── SendDelegate 将消息加入发送队列
  └── Run() 主循环检测到队列有数据 → Socket->Send
```

- `TCHAR→ANSI` 转换：`FTCHARToUTF8`（或 `FTCHARToUTF8`）
- 发送失败时检查原因：对方关闭、网络断开、Socket 错误码

## 回调线程安全

Runnable 线程中不能直接操作跨线程对象，需要异步执行：

```cpp
// Runnable 中的回调通过拷贝存储
TArray<TDelegate<void()>> Delegates;

// AsyncAction 绑定回调时使用 AsyncTask
void BindCallback() {
    // Runnable 在 TCP 线程调用此回调
    // AsyncAction 将逻辑异步回游戏线程执行
}
```

关键线程安全设计：
- 回调作为 `TDelegate` 值拷贝存储，不跨线程传递引用
- `ExecuteDelegate()` 在 AsyncAction 中将逻辑分发到游戏线程
- Runnable 只持有 `FSocket*` 原始指针——Socket 生命周期由 Runnable 自己管理

## 资源关闭流程

### 正常关闭（发送完成）

```
AsyncAction::StageClose / CloseRunnable
  ├── XGEmailRunnable->bStop = true
  ├── XGEmailRunnable->bClose = true
  ├── Socket ⇢ Close() / Destroy()
  ├── 回调 OnDisconnected（最终状态 Finished）
  └── AsyncAction::Shutdown()
        └── Subsystem::RemoveAction(GUID)
```

### 异常关闭（协议错误）

```
阶段出错 → StageClose
  ├── 关闭 Socket
  ├── 回调 OnDisconnected（附带错误信息+当前状态名）
  └── Shutdown → Subsystem 移除
```

### 关键 Bug 修复（字幕 010）

**问题**：在 `CloseEmailRunnable()` 中直接调用 `XGEmailRunnable.Reset()` 导致野指针崩溃。

**原因**：`FRunnableThread::Stop()` 内部会访问 Runnable 对象调用其 `Stop()` 方法。如果先 `Reset()` 了 shared_ptr（引用计数归零，Runnable 对象被析构），`Stop()` 此时访问的就是已释放内存。

**正确顺序**：
```
CloseEmailRunnable()
  ├── EmailThread->Stop()           // 先触发 Stop → bShouldStop = true
  ├── EmailThread->WaitForCompletion() // 等待 Exit() 完成
  ├── delete EmailThread           // 删除线程对象
  ├── EmailThread = nullptr
  └── XGEmailRunnable.Reset()      // 最后释放 Runnable（此时线程已不会访问它）
```

**`Exit()` 与 `Stop()` 的调用顺序**：`Stop()` 先调用 → 设置停止标志 → 主循环退出 → 自动调用 `Exit()`。因此 `Reset()` 必须在 `WaitForCompletion`（确保 Exit 已完成）之后。

## 设计要点总结

| 要点 | 说明 |
|------|------|
| 阻塞模式 + 超时检查 | `AsBlocking()` + `HasPendingConnection(FTimespan)` 避免死等 |
| 独立线程 | FRunnable 跑在独立 TCP 线程，不阻塞主线程 |
| 业务与通信分离 | Runnable 只收发字节流，不关心 SMTP 协议 |
| 回调异步 | 线程回调通过 AsyncTask 回到游戏线程执行 |
| 智能指针管理 | Runnable 由 AsyncAction 的 shared_ptr 持有 |
| 资源安全 | 先 Stop 线程、后释放 Runnable，防野指针 |

## 文件索引

| 文件路径 | 说明 |
|----------|------|
| [XGSampleEMailRunnable.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleEMail/Source/XGSampleEMail/Public/Thread/XGSampleEMailRunnable.h) | Runnable 头文件（回调代理声明） |
| [XGSampleEMailRunnable.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleEMail/Source/XGSampleEMail/Private/Thread/XGSampleEMailRunnable.cpp) | Runnable 实现（Socket 创建/连接/循环/关闭） |
| [XGSampleEMailAsyncAction.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleEMail/Source/XGSampleEMail/Private/AsyncAction/XGSampleEMailAsyncAction.cpp) | AsyncAction 实现（CreateRunnable/CloseRunnable/Shutdown） |
