# HTTP 端口绑定与请求处理管线

## 概述

核心类 `UXGSampleServerHttpObject` 是一个 **UObject 单例**，负责整个服务端的 HTTP 通信生命周期：端口绑定、路由注册、请求处理、响应返回。

路径：[XGSampleServerHttpObject.h](../code/013_独立程序源码/XGSampleServer/Private/ServerObject/XGSampleServerHttpObject.h)，[XGSampleServerHttpObject.cpp](../code/013_独立程序源码/XGSampleServer/Private/ServerObject/XGSampleServerHttpObject.cpp)

## 初始化与销毁

```cpp
void UXGSampleServerHttpObject::Init()
{
    Server = &FHttpServerModule::Get();                              // 1. 获取 HTTP Server 模块
    FHttpPath HttpPath(TEXT("/Login"));                               // 2. 定义路由路径
    int32 ServerPort = FXGSampleServerConfigManage::Get()->GetInfo().Port; // 3. 读取配置端口

    Router = Server->GetHttpRouter(ServerPort);                       // 4. 获取路由表
    RequestHandler.BindUObject(this, &UXGSampleServerHttpObject::ProcessHttpRequest); // 5. 绑定处理函数
    RouteHandle = Router->BindRoute(HttpPath,                         // 6. 注册路由
        EHttpServerRequestVerbs::VERB_GET | EHttpServerRequestVerbs::VERB_POST,
        RequestHandler);
    Server->StartAllListeners();                                      // 7. 启动监听
}
```

初始化步骤：
1. 通过 `FHttpServerModule::Get()` 获取 HTTP Server 模块单例
2. 定义路由路径为 `/Login`（所有请求都通过此路径）
3. 从自定义 INI 配置读取端口号
4. 通过 `GetHttpRouter(Port)` 获取指定端口的路由表
5. 将 `ProcessHttpRequest` 绑定为请求回调
6. 注册路由到 `/Login`，同时接受 GET 和 POST
7. `StartAllListeners()` 正式启动所有端口的监听

销毁时调用 `Server->StopAllListeners()` 停止监听。

## 端口绑定机制

`FHttpServerModule::GetHttpRouter(Port)` 内部会创建或获取对应端口的 `IHttpRouter`。如果端口已被占用，绑定时会失败。端口号通过 INI 配置（`XGSampleServerConfig.ini` 的 `Port` 字段）控制，支持运行时修改。

## 请求处理管线

```
收到 HTTP 请求
    │
    ▼
ProcessHttpRequest()          ← 第一层：HTTP 级别的请求入口
    │
    ├── CheckHttpRequestToken()  ← Token 验证
    │       │
    │       └── 失败 → 返回 AuthFail 错误码
    │
    ├── JSON 反序列化            ← 解析请求体
    │       │
    │       └── 失败 → 返回 JsonAnalysisFail 错误码
    │
    ├── DispatchHttpRequest()    ← 路由分发
    │       │
    │       └── 枚举读取 EXGSampleRequestType
    │               ├── CheckVersionReq → HanldeCheckVersion()
    │               ├── RegisterReq    → HanldeRegister()
    │               └── LoginReq       → HanldeLogin()
    │
    └── 响应序列化 → 回调返回
```

### 第一层处理函数

```cpp
bool UXGSampleServerHttpObject::ProcessHttpRequest(
    const FHttpServerRequest& InRequest,
    const FHttpResultCallback& OnComplete)
{
    FXGSampleServerResponse ResponseData;

    // 1. Token 验证
    if (!CheckHttpRequestToken(InRequest))
    {
        ResponseData.Result = EXGSampleServerResult::AuthFail;
        // 序列化并返回
        ReturnResponse(ResponseData, OnComplete);
        return true;
    }

    // 2. JSON 解析
    FXGSampleServerRequest RequestData;
    FString JsonStr = FString(UTF8_TO_TCHAR(InRequest.Body.GetData()));
    if (!FJsonObjectConverter::JsonObjectStringToUStruct(JsonStr, &RequestData, 0, 0))
    {
        ResponseData.Result = EXGSampleServerResult::JsonAnalysisFail;
        ReturnResponse(ResponseData, OnComplete);
        return true;
    }

    // 3. 路由分发
    DispatchHttpRequest(RequestData, ResponseData);

    // 4. 序列化并返回
    ReturnResponse(ResponseData, OnComplete);
    return true;
}
```

### Token 验证

Token 通过 HTTP Header 的 `XGLoginServerToken` 字段传递，服务端比较请求头中的 Token 值与自身计算出的 Token 是否一致：

```cpp
bool UXGSampleServerHttpObject::CheckHttpRequestToken(const FHttpServerRequest& Request)
{
    if (auto Tokens = Request.Headers.Find(TEXT("XGLoginServerToken")))
    {
        FString ServerToken = GetCurrentToken();
        for (auto& Tmp : *Tokens)
            if (ServerToken.Equals(Tmp)) return true;
    }
    return false;
}
```

Token 通过 INI 中配置的密钥和 MD5 迭代次数计算生成（详见 MD5 令牌验证篇）。

### JSON 反序列化

请求体以原始字节形式接收，先转为 UTF8 字符串，再通过 `FJsonObjectConverter::JsonObjectStringToUStruct` 反射序列化为 `FXGSampleServerRequest` 结构体。

### 路由分发

```cpp
void UXGSampleServerHttpObject::DispatchHttpRequest(
    const FXGSampleServerRequest& InRequestData,
    FXGSampleServerResponse& OutResponse)
{
    switch (InRequestData.Type)
    {
    case EXGSampleRequestType::CheckVersionReq:
        OutResponse = HanldeCheckVersion(InRequestData.Data);
        break;
    case EXGSampleRequestType::RegisterReq:
        OutResponse = HanldeRegister(InRequestData.Data);
        break;
    case EXGSampleRequestType::LoginReq:
        OutResponse = HanldeLogin(InRequestData.Data);
        break;
    }
}
```

通过 `EXGSampleRequestType` 枚举值决定调用哪个业务处理函数。

### 响应返回

```cpp
void UXGSampleServerHttpObject::ReturnResponse(
    const FXGSampleServerResponse& InResponse,
    const FHttpResultCallback& OnComplete)
{
    FString ResponseJson;
    FJsonObjectConverter::UStructToJsonObjectString(InResponse, ResponseJson);

    auto Response = FHttpServerResponse::Create(UTF8_TO_TCHAR(*ResponseJson),
        TEXT("application/json"));
    OnComplete(MoveTemp(Response));
}
```

通过 `FHttpServerResponse::Create` 创建响应，Content-Type 为 `application/json`。

## 内置测试用户

服务端启动时初始化一个默认测试用户：

```cpp
void UXGSampleServerHttpObject::InitData()
{
    FXGSampleServerUserInfo& UserRef = UserList.AddDefaulted_GetRef();
    UserRef.UserID = 1;
    UserRef.UserName = TEXT("XiaoGang");
    UserRef.Password = FMD5::HashAnsiString(TEXT("123456"));
    UserRef.Phone = TEXT("12345678911");
    UserRef.Mail = TEXT("123456@qq.com");
}
```

使用 `AddDefaulted_GetRef()` 获取新添加元素的引用，避免了临时变量的拷贝构造。密码以 MD5 哈希形式存储，不保存明文。

## 成员变量一览

| 变量 | 类型 | 用途 |
|------|------|------|
| `Instance` | `static UXGSampleServerHttpObject*` | 单例指针 |
| `Server` | `FHttpServerModule*` | HTTP Server 模块实例 |
| `Router` | `TSharedPtr<IHttpRouter>` | 端口路由表 |
| `RequestHandler` | `FHttpRequestHandler` | 请求回调委托 |
| `RouteHandle` | `FHttpRouteHandle` | 路由句柄（解绑时使用） |
| `UserList` | `TArray<FXGSampleServerUserInfo>` | 内存用户列表 |
