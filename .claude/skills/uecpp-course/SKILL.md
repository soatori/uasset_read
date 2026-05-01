# uecpp-course

| 字段 | 值 |
|------|-----|
| Skill 名称 | uecpp-course |
| 版本 | UE 5.4 |
| 分类 | Unreal Engine C++ 开发实践 |
| 触发词 | UEC++、UE C++、虚幻C++、虚幻开发、UECpp |

---

## Skill 说明

### 能做什么

- 解释 UE C++ 中任意系统/API 的用法、位置和设计意图
- 指导在虚幻项目中添加新功能（容器选型、异步任务、HTTP/TCP/WebSocket 通信等）
- 对比不同方案的优缺点并给出选型建议（容器、异步模式、网络协议、配置方式等）
- 提供常用 API 的代码模板（含代码路径和行号参考）
- 分析跨系统调用链路（如：从 HTTP 请求到独立程序的完整路径）
- 诊断常见的开发陷阱（智能指针循环引用、TaskGraph 线程池阻塞、多线程竞态条件等）
- 代码原型以 `UnrealEngine` 源码为准

### 不能做什么

- **不覆盖所有 API 细节** — 聚焦核心开发实践，极端边缘情况请参考 UE 官方文档
- **不包含蓝图教程** — 仅关注 C++ 层开发
- **不包含完整项目部署指南** — 仅提供架构模式参考

---

## 课程全景

本课程从 UE C++ 基础起步到完整 GAS 网络游戏项目，覆盖 37 章、400+ 课时，核心代码 4 万+ 行。代码分布在 12+ 个 UE 项目和独立程序中。

### 章节结构总览

```
基础篇（Ch1-3）：环境部署 → 引擎架构 → 反射系统/UObject/CDO/GC
容器篇（Ch4-7）：TArray → TMap → TSet → 基础案例
进阶 API（Ch8-20）：定时器 → 委托 → 字符串 → Tag → 日志 → Subsystem
                      → 断言 → 配置 → 智能指针 → 多线程 → ControlFlows
                      → 插件开发 → 第三方库封装
实战案例（Ch21-36）：
  编解码：LibWebP 编码生成/展示
  桌面UI：Slate 独立程序
  数据：Json 读写
  网络通信：HTTP(3章) → WebSocket(2章) → WebSocketServer → TCP
  网络游戏：网络基础 → DSM 部署 → GAS 案例
```

### 源码工程结构

```
code/
├── 001_XGSampleDemo/             # 核心教学项目（基础API + 容器 + 通信 + 插件）
│   └── Plugins/
│       ├── XGSampleWebP/         # WebP 编解码插件
│       ├── XGSampleLink/         # 网络通信插件（HTTP/WebSocket/加密）
│       ├── XGSampleWSM/          # WebSocket 服务器管理插件
│       ├── XGSampleTool/         # 工具函数插件
│       └── XGSamplePicture/      # 图像处理插件
├── 002_XGSampleTemp/             # 插件写法示范项目
├── 003_XGFPS0Demo/               # 第一人称射击模板
├── 007_UEProgram1/               # Slate 独立程序
├── 008_UEProgram2/               # HTTP 独立程序
├── 010_XGMultiGame/              # 分布式游戏 Client
├── 011_XGMultiManage/            # 分布式游戏 Manage
├── 013_独立程序源码/              # 独立程序集合
├── 016_XGNetDemo/                # 网络游戏快速入门 Demo
└── 017_XGRPG/                    # GAS 网络游戏案例（12 案例终极产出）
```

---

## 核心知识体系

### 反射系统

UE 的反射系统是引擎的元数据基础设施，所有 UCLASS/USTRUCT/UENUM/UPROPERTY/UFUNCTION 依赖它实现序列化、GC、网络复制、蓝图可见性。

```
UCLASS(BlueprintType, Blueprintable)        → 可被 GC 管理的类
USTRUCT(BlueprintType)                      → 值类型、可被复制
UENUM(BlueprintType)                        → 枚举
UPROPERTY(EditAnywhere, BlueprintReadWrite) → 自动 GC、序列化
UFUNCTION(BlueprintCallable, BlueprintImplementableEvent) → 反射调用
UINTERFACE(BlueprintType, MinimalAPI)       → 可被蓝图实现的接口
```

### 容器三件套

| 容器 | 核心特征 | 适用场景 |
|------|---------|---------|
| TArray | 连续内存、随机访问 O(1)、末尾插入 O(1)、中间插入 O(n) | 默认选择，有序集合 |
| TMap | 哈希表、键值查找 O(1)、无序 | 键值映射、字典式查询 |
| TSet | 哈希集合、元素唯一、查找 O(1)、无序 | 去重集合、成员测试 |

### 网络通信演进

```
HTTP（Ch25-28）
  ├── HttpRequest + FHttpModule（Get/Post/Put/Delete）
  ├── 同步/异步回调模式
  ├── 上传文件（摄像头图像 Base64）
  └── 流式传输（大模型 SSE）
WebSocket（Ch29-30）
  ├── IWebSocket + FWebSocketsModule
  ├── 持久连接、双向通信
  ├── STT 语音识别（Subsystem 常驻 + FRunnable 音频采集）
  └── TTS 语音合成（AsyncAction 单次请求）
WebSocketServer（Ch31）
  ├── IWebSocketServer（来自 WebSocketNetworking 插件）
  ├── 自定义消息协议 + 连接容器管理
  └── Heartbeat + 状态机
TCP（Ch32）
  ├── FSocket + FTcpSocketBuilder
  ├── FRunnable 长连接 + SMTP 协议状态机
  └── 异步行动（UBlueprintAsyncActionBase）
```

### 异步执行模式

| 模式 | 线程模型 | 返回值 | 适用场景 |
|------|---------|--------|---------|
| FRunnable | OS 独立线程 | 无（通过共享变量回传） | 长周期后台任务 |
| Async() + TFuture | TaskGraph 线程池 | 有（TFuture.Get()） | 简单异步计算 |
| AsyncTask() | TaskGraph 线程池 | 无 | 火抛任务、线程跳转 |
| FGraphEvent | TaskGraph 线程池 DAG | 无 | 多任务依赖编排 |
| ParallelFor | TaskGraph 线程池并行 | 无 | 数据并行计算 |
| FControlFlow | 任意线程（顺序执行） | 无（Delegate 回传） | 异步步骤编排 |
| ManageTask | GameThread Tick（自定义） | 无（三阶段回调） | 并行子任务管理 |

### 配置与依赖注入

```
Subsystem（Ch13）
  ├── UGameInstanceSubsystem  → 单 GameInstance 生命周期
  ├── UWorldSubsystem         → 单 World 生命周期
  ├── UEditorSubsystem        → Editor 模式
  ├── ULocalPlayerSubsystem   → 单 Player 生命周期
  └── UEngineSubsystem        → 引擎全局

DeveloperSettings（Ch15）
  ├── UDeveloperSettings 基类
  ├── UPROPERTY(Config)  自动读/写 INI
  ├── GetMutableDefault<T>() → 写
  └── GetDefault<T>()        → 读

CDO（Ch3）
  ├── GetClassDefaultObject()
  ├── 所有 UClass 自动创建
  └── Subsystem 和 DeveloperSettings 共享此机制
```

---

## 关键类索引

### 反射与基础

| 类/宏 | 文件路径 | 职责 |
|-------|---------|------|
| UCLASS/USTRUCT/UENUM/UPROPERTY/UFUNCTION/UINTERFACE | code 下各项目 | 6 大反射宏体系 |
| UObject | 引擎内置 | GC 基类、所有反射类的根 |
| CDO (ClassDefaultObject) | 引擎内置 | 所有 UClass 实例共享的默认对象 |
| FAssetData | 引擎内置 | 资产数据，用于搜索/过滤 |

### 容器

| 类 | 文件路径 | 职责 |
|----|---------|------|
| TArray | 引擎内置 | 动态数组，连续内存 |
| TMap | 引擎内置 | 哈希键值映射 |
| TSet | 引擎内置 | 哈希集合 |
| TTuple | 引擎内置 | 元组 |
| TQueue、TStack | 引擎内置 | 队列/栈 |

### 委托

| 声明宏 | 说明 |
|--------|------|
| DECLARE_DELEGATE | 单播原生委托 |
| DECLARE_MULTICAST_DELEGATE | 多播原生委托 |
| DECLARE_DYNAMIC_DELEGATE | 单播动态委托（可序列化） |
| DECLARE_DYNAMIC_MULTICAST_DELEGATE | 多播动态委托（蓝图事件分发器） |
### 字符串处理

| 类/宏 | 文件路径 | 职责 |
|-------|---------|------|
| FString | --- | 可变字符串，Printf/Format/Parse 操作 |
| FName | 引擎内置 | 不可变原子字符串，资产引用/反射 |
| FText | 引擎内置 | 本地化文本，LOCTEXT/NSLOCTEXT |
| FTCHARToUTF8 / FUTF8ToTCHAR | 引擎内置 | TCHAR <-> UTF8 编码转换 |


### 子系统

| 类 | 文件路径 | 职责 |
|----|---------|------|
| UGameInstanceSubsystem | --- | GameInstance 生命周期 |
| UWorldSubsystem | --- | World 生命周期 |
| UDeveloperSettings | --- | 配置读取 |

### 多线程

| 类 | 文件路径 | 职责 |
|----|---------|------|
| FRunnable + FRunnableThread | --- | 独立线程任务 |
| Async() + TFuture | --- | TaskGraph 异步 |
| FGraphEvent + FFunctionGraphTask | --- | 任务 DAG |
| ParallelFor | 引擎内置 | 数据并行 @Line 336 |
| FControlFlow | --- | 异步步骤编排 |

### 智能指针

| 类 | 文件路径 | 职责 |
|----|---------|------|
| TSharedPtr | --- | 共享所有权，引用计数 |
| TSharedRef | --- | 非空共享引用，隐式转 TSharedPtr |
| TUniquePtr | --- | 独占所有权，MoveTemp 转移 |
| TWeakPtr | --- | 弱引用，Pin() 提升语义 |
| TSharedFromThis | --- | 安全获取自身 TSharedPtr |

### 日志与调试

| 类/宏 | 文件路径 | 职责 |
|-------|---------|------|
| UE_LOG | --- | 七级 Verbosity 日志输出 |
| DECLARE_LOG_CATEGORY_EXTERN | --- | 日志分类声明 |
| UE_LOGFMT | --- | 结构化日志语法 |
| check / verify / ensure | --- | 三种断言机制对比 |


### 网络通信

| 类 | 文件路径 | 职责 |
|----|---------|------|
| FHttpModule + FHttpRequest | --- | HTTP 客户端 |
| FHttpServerModule | XGSampleServer（独立程序） | HTTP 服务端 |
| FWebSocketsModule + IWebSocket | --- | WebSocket 客户端 |
| IWebSocketServer + FWebSocket | --- | WebSocket 服务端 |
| FSocket + FTcpSocketBuilder | --- | TCP 客户端（SMTP 邮件） |
| UBlueprintAsyncActionBase | --- | 异步行动基类 |

### 网络同步

| 类/宏 | 文件路径 | 职责 |
|-------|---------|------|
| ENetRole / GetLocalRole / GetRemoteRole | --- | 网络角色判定（Authority/AutonomousProxy/SimulatedProxy） |
| GetLifetimeReplicatedProps | 各 Actor 实现 | 属性同步注册 |
| DOREPLIFETIME / DOREPLIFETIME_CONDITION | 同上 | 属性复制注册与条件控制 |
| UFUNCTION(Server/Client/NetMulticast) | 各 GameMode/Character | RPC 远程调用 |
| UNetDriver / AGameSession | 引擎内置 | 网络驱动与会话管理 |


### Slate 独立程序

| 类 | 文件路径 | 职责 |
|----|---------|------|
| FSimpleUIApp | --- | Slate 主窗口管理 |
| SCompoundWidget 派生 | --- | 自定义 Slate 控件 |
| INT32_MAIN_ENTRY | --- | 独立程序入口点 |

### GAS

| 类 | 文件路径 | 职责 |
|----|---------|------|
| UAbilitySystemComponent | --- | 能力系统组件 |
| UAttributeSet | --- | 属性集（2 层继承） |
| UGameplayEffect | --- | 游戏效果 |
| UGameplayAbility | --- | 游戏能力 |
| UGameplayEffectExecutionCalculation | --- | 伤害计算公式 |

### 增强输入

| 类 | 文件路径 | 职责 |
|----|---------|------|
| UEnhancedInputLocalPlayerSubsystem | --- | 输入子系统，管理 IMC 注册 |
| UInputMappingContext | 资产文件 | 输入上下文，绑定 Action 到按键 |
| UInputAction | 资产文件 | 输入动作定义 |
| UEnhancedPlayerInput | 引擎内置 | 增强输入管理器 |


### 第三方库封装

| 类 | 文件路径 | 职责 |
|----|---------|------|
| XGWebPLoader / XGWebPHelper | --- | WebP 编解码 |
| XGXFLink / XGBDLink | --- | 第三方 API 封装 |

### GameplayTag 与定时器

| 类 | 文件路径 | 职责 |
|----|---------|------|
| FGameplayTag | --- | 层级标签标识符，支持父子匹配 |
| FGameplayTagContainer | ---W | 标签容器，支持网络复制 |
| FTimerHandle | --- | 定时器句柄 |
| FTimerManager | 引擎内置 | 全局定时器管理器 |


---

## 横向模式

以下横向模式总结贯穿多章的通用架构范式，详细文档见 references/ 目录。

| 模式 | 涉及章节 | 说明 | 参考文档 |
|------|----------|------|---------|
| 反射宏体系 | Ch2-3 | 6 大宏的选择树、声明位置、常见陷阱 | [反射系统总览.md](references/反射系统总览.md) |
| 容器选型 | Ch4-6 | TArray/TMap/TSet 对比、决策树 | [容器选型指南.md](references/容器选型指南.md) |
| 异步执行 | Ch17-18 | 6 种异步模式对比 + TaskGraph 陷阱 | [异步执行模式.md](references/异步执行模式.md) |
| 网络通信演进 | Ch25-32 | HTTP→WebSocket→TCP 演进链路 | [网络通信演进.md](references/网络通信演进.md) |
| 配置与 DI | Ch13-15 | Subsystem/DeveloperSettings/CDO 对比 | [配置与依赖注入.md](references/配置与依赖注入.md) |
| 多项目策略 | Ch21-36 | 12 个案例的组织方式演化 | 见课程章节 |

---

## 常见开发工作流

### 工作流一：添加一个新容器

```
1. 确认需求：
   - 需要有序？→ TArray
   - 需要键值映射？→ TMap
   - 需要唯一元素集合？→ TSet
   - 需要栈/队列操作？→ TQueue/TStack
2. 选择容器类型（见 容器选型指南.md）
3. 考虑元素类型（UObject* → TObjectPtr，值类型 → 直接元素）
4. 考虑复制语义（UPROPERTY 自动 GC 追踪）
5. 使用 Range-based for 或迭代器遍历
```

### 工作流二：发起 HTTP 请求

```cpp
// 1. 创建请求
FHttpRequestRef Request = FHttpModule::Get().CreateRequest();
Request->SetURL(TEXT("https://api.example.com/data"));
Request->SetVerb(TEXT("GET"));
Request->SetHeader(TEXT("Content-Type"), TEXT("application/json"));

// 2. 绑定回调
Request->OnProcessRequestComplete().BindLambda([](
    FHttpRequestPtr Req, FHttpResponsePtr Resp, bool bSuccess)
{
    if (bSuccess && Resp.IsValid())
    {
        FString ResponseStr = Resp->GetContentAsString();
        // 解析响应
    }
});

// 3. 发送
Request->ProcessRequest();
```

AsyncAction 模式（推荐用于蓝图暴露）：
```cpp
UCLASS()
class UXGAsyncHttpAction : public UBlueprintAsyncActionBase
{
    GENERATED_BODY()
public:
    UFUNCTION(BlueprintCallable, meta=(WorldContext="WorldContextObject"))
    static UXGAsyncHttpAction* AsyncHttpRequest(UObject* WorldContextObject);

    virtual void Activate() override;

    DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnResponse, int32, StatusCode, FString, Content);
    UPROPERTY(BlueprintAssignable) FOnResponse OnSuccess;
    UPROPERTY(BlueprintAssignable) FOnResponse OnFail;
};
```

### 工作流三：创建 WebSocket 连接

```cpp
// 1. 创建 WebSocket
TSharedPtr<IWebSocket> WebSocket = FWebSocketsModule::Get().CreateWebSocket(URL, Protocol);

// 2. 绑定回调
WebSocket->OnConnected().AddLambda([]() { UE_LOG(LogTemp, Log, TEXT("Connected")); });
WebSocket->OnConnectionError().AddLambda([](const FString& Error) { /* 处理错误 */ });
WebSocket->OnMessage().AddLambda([](const FString& Msg) { /* 收到消息 */ });
WebSocket->OnClosed().AddLambda([](int32 Code, const FString& Reason) { /* 连接关闭 */ });

// 3. 连接
WebSocket->Connect();

// 4. 发送
WebSocket->Send(Message);
```

### 工作流四：创建 FRunnable 后台线程

```cpp
class FXGSimpleRunnable : public FRunnable
{
    virtual bool Init() override;
    virtual uint32 Run() override;
    virtual void Exit() override;
    virtual void Stop() override;
    
    FThreadSafeBool bRunning = true;
};

// 启动
FRunnableThread::Create(ThreadObj, TEXT("ThreadName"));

// 停止（外部线程调用）
ThreadObj->Stop();  // 设置 bRunning = false
```

### 工作流五：添加新 Subsystem

```cpp
// .h
UCLASS()
class UXGMySubsystem : public UGameInstanceSubsystem
{
    GENERATED_BODY()
public:
    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void Deinitialize() override;
    
    UFUNCTION(BlueprintCallable)
    void MyFunction();
};

// 自动创建，无需手动注册
```

### 工作流六：创建 Slate 独立程序

```
1. INT32_MAIN_ENTRY 入口
2. FSimpleApplication 初始化
3. SCompoundWidget 派生自定义窗口
4. FSlateApplication::Get().AddWindow() 显示窗口
5. 消息循环
```

### 工作流七：封装第三方 C++ 库为插件

```
1. 创建空白插件（Editor 或手动）
2. 在 Build.cs 中配置第三方库路径和依赖
3. 在插件模块加载时初始化库
4. 封装为 UFUNCTION（String 参数而非 std::string）
5. 配置插件依赖：目标项目 .uproject 中添加插件
```

---

## 跨系统调用链路

### 链路一：HTTP 请求 → 解析 → 使用

```
脚本/用户 → UFUNCTION(C++/Blueprint) 
    → FHttpModule::CreateRequest()
    → FHttpRequest::ProcessRequest()
    → 异步（OnProcessRequestComplete Delegate）
    → FJsonObjectConverter::JsonObjectStringToUStruct()
    → UPROPERTY 数据成员
    → UI/其他系统消费
```

### 链路二：WebSocket 消息 → 解析 → 响应

```
服务器 → WebSocket 消息
    → IWebSocket::OnMessage Delegate（客户端收到）
    → FJsonObjectConverter::DeserializeJson（消息解析）
    → 消息类型判断（ActionType 枚举）
    → 分发到对应业务逻辑
    → IWebSocket::Send（可能需要回复）
```

### 链路三：AsyncAction → 多线程下载 → GameThread 回调

```
UBlueprintAsyncActionBase::Activate()
    → Async(EAsyncExecution::Thread, lambda) [后台线程]
    → 下载/计算完成
    → AsyncTask(ENamedThreads::GameThread, lambda) [GameThread]
    → Broadcast 结果到蓝图/UI
```

---

## 使用示例

| 问题 | 查阅路径 |
|------|---------|
| "如何选择容器？" | [容器选型指南.md](references/容器选型指南.md) |
| "怎么发起 HTTP 请求？" | [HTTP通信详解.md](references/HTTP通信详解.md) |
| "Subsystem 和 DeveloperSettings 什么区别？" | [配置与依赖注入.md](references/配置与依赖注入.md) |
| "如何在后台线程跑任务？" | [多线程详解.md](references/多线程详解.md) |
| "怎么把 C++ 库封装成插件？" | [第三方库封装指南.md](references/第三方库封装指南.md) |
| "如何用 WebSocket 做实时通信？" | [WebSocket通信详解.md](references/WebSocket通信详解.md) |
| "FControlFlow 和 FRunnable 什么关系？" | [异步执行模式.md](references/异步执行模式.md) |
| "GAS 怎么做伤害计算？" | [GAS体系详解.md](references/GAS体系详解.md) |
| "怎么用 Slate 写独立窗口程序？" | [Slate独立程序详解.md](references/Slate独立程序详解.md) |
| "UCLASS 和 USTRUCT 选哪个？" | [反射系统总览.md](references/反射系统总览.md) |
| "TCP 怎么做 SMTP 邮件发送？" | [TCP通信详解.md](references/TCP通信详解.md) |
| "FString/FName/FText 有什么区别？" | [字符串处理详解.md](references/字符串处理详解.md) |
| "怎么在 C++ 中使用 Enhanced Input？" | [增强输入系统.md](references/增强输入系统.md) |
| "UE 原生网络同步怎么用？" | [网络同步基础.md](references/网络同步基础.md) |
| "check/verify/ensure 该用哪个？" | [日志断言与调试.md](references/日志断言与调试.md) |
| "智能指针的循环引用怎么解决？" | [智能指针详解.md](references/智能指针详解.md) |
| "GameplayTag 和定时器怎么用？" | [GameplayTag与定时器.md](references/GameplayTag与定时器.md) |

---

## 参考文档索引

| 文档 | 说明 |
|------|------|
| [反射系统总览.md](references/反射系统总览.md) | 6 大反射宏选择树 + 声明位置 + 实战陷阱 |
| [容器选型指南.md](references/容器选型指南.md) | TArray/TMap/TSet 对比 + 性能特征 + 决策树 |
| [TArray详解.md](references/TArray详解.md) | TArray 完整 API + 内存模型 + 复制策略 |
| [委托体系详解.md](references/委托体系详解.md) | 4 种委托类型 + 绑定/广播 + 使用模式 |
| [多线程详解.md](references/多线程详解.md) | FRunnable/Async/FGraphEvent API + 陷阱 |
| [ControlFlows详解.md](references/ControlFlows详解.md) | FControlFlow + ManageTask 异步编排 |
| [网络通信演进.md](references/网络通信演进.md) | HTTP→WebSocket→TCP 逐层演进链路 |
| [HTTP通信详解.md](references/HTTP通信详解.md) | HTTP 客户端/服务端 + 上传文件 + 流式传输 |
| [WebSocket通信详解.md](references/WebSocket通信详解.md) | WebSocket 客户端 + STT/TTS + 鉴权 |
| [TCP通信详解.md](references/TCP通信详解.md) | TCP 连接 + SMTP 状态机 + 邮件发送 |
| [配置与依赖注入.md](references/配置与依赖注入.md) | Subsystem/DeveloperSettings/CDO 对比 |
| [异步执行模式.md](references/异步执行模式.md) | 6 种异步模式 + TaskGraph 线程池陷阱 |
| [GAS体系详解.md](references/GAS体系详解.md) | GAS 核心框架 + AttributeSet + GEEC + GameplayAbility |
| [Slate独立程序详解.md](references/Slate独立程序详解.md) | Slate 独立程序入口 + 窗口管理 + 控件体系 |
| [第三方库封装指南.md](references/第三方库封装指南.md) | 第三方库集成 + 插件封装 + 跨平台注意事项 |
| [字符串处理详解.md](references/字符串处理详解.md) | FString/FName/FText 三种字符串类型 + TCHAR 编码体系 + 本地化 |
| [增强输入系统.md](references/增强输入系统.md) | Enhanced Input 资产体系 + IMC 注册 + 绑定流程 + 武器切换实战 |
| [网络同步基础.md](references/网络同步基础.md) | 属性同步 + RPC + 网络角色 + DSM 三层部署 |
| [日志断言与调试.md](references/日志断言与调试.md) | UE_LOG 七级 Verbosity + check/verify/ensure 对比 + Dump 调试 |
| [智能指针详解.md](references/智能指针详解.md) | TSharedPtr/TSharedRef/TUniquePtr/TWeakPtr + 循环引用 + UE vs STL |
| [GameplayTag与定时器.md](references/GameplayTag与定时器.md) | FGameplayTag 层级匹配 + FTimerManager API + 生命周期管理 |
