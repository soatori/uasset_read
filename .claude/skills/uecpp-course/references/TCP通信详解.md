# TCP 通信详解

## 概述

UE 的 TCP 通信基于 FSocket（底层 Socket 抽象）和 FRunnable（多线程运行环境）。课程以 SMTP 邮件发送协议为案例，展示了完整的 TCP 客户端实现：Socket 创建连接、多线程收发、SMTP 状态机、Base64 认证。

## FSocket 基础

### 依赖配置

```csharp
PublicDependencyModuleNames.Add("Sockets");
```

### 创建与连接

```cpp
#include "Sockets.h"
#include "SocketSubsystem.h"

// 创建 TCP Socket
FSocket* Socket = ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)
    ->CreateSocket(NAME_Stream, TEXT("XGEmailSocket"), false);

// 域名解析
TSharedPtr<FInternetAddr> Addr = ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)
    ->GetAddressFromString(TEXT("smtp.qq.com"));

Addr->SetPort(25);

// 连接
bool bConnected = Socket->Connect(*Addr);
```

### 收发数据

```cpp
// 发送
int32 BytesSent = 0;
Socket->Send((uint8*)TCHAR_TO_UTF8(*Command), Command.Len(), BytesSent);

// 接收（阻塞模式）
TArray<uint8> Buffer;
Buffer.SetNum(1024);
int32 BytesRead = 0;
Socket->Recv(Buffer.GetData(), Buffer.Num(), BytesRead);
```

## FRunnable TCP 线程

### 线程架构

```cpp
class FXGSampleEMailRunnable : public FRunnable
{
    FSocket* Socket;
    TArray<uint8> RecvBuffer;
    FOnEmailRunnableReceive OnMessage;

    virtual bool Init() override
    {
        Socket = CreateAndConnect();
        return Socket != nullptr;
    }

    virtual uint32 Run() override
    {
        while (!bStop)
        {
            if (Socket->HasPendingData(RecvBuffer.Num()))
            {
                int32 Read = 0;
                Socket->Recv(RecvBuffer.GetData(), RecvBuffer.Num(), Read);

                if (Read > 0)
                {
                    FString Response = UTF8_TO_TCHAR(
                        reinterpret_cast<const ANSICHAR*>(RecvBuffer.GetData()));

                    // 线程安全回调
                    OnMessage.ExecuteIfBound(Response);
                }
            }

            FPlatformProcess::Sleep(0.01f);
        }
        return 0;
    }

    virtual void Stop() override
    {
        bStop = true;
    }

    virtual void Exit() override
    {
        if (Socket)
        {
            Socket->Close();
            ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->DestroySocket(Socket);
            Socket = nullptr;
        }
    }
};
```

## SMTP 协议状态机

### 状态枚举

```cpp
UENUM()
enum class EXGSampleEMailStatus : uint8
{
    Init,
    Connected,         // 等待 220
    EHLO,              // 等待 250
    AuthLogin,         // 发送 AUTH LOGIN
    AuthLogin_UserName,// 等待 334 → 发送 Base64 用户名
    AuthLogin_PassWord,// 等待 334 → 发送 Base64 密码
    LoginSuccess,      // 等待 235
    MailFrom,          // 等待 250
    RcptTo,            // 等待 250
    Data,              // 等待 354
    SendContent,       // 发送正文 → 等待 250
    Quit,              // 等待 221
    Finished
};
```

### 状态机驱动

```cpp
void OnMessage(const FString& Response)
{
    switch (CurrentStatus)
    {
    case EXGSampleEMailStatus::Connected:
        if (Response.Contains(TEXT("220")))
        {
            Send(TEXT("EHLO XGSample\r\n"));
            CurrentStatus = EXGSampleEMailStatus::EHLO;
        }
        break;

    case EXGSampleEMailStatus::EHLO:
        if (Response.Contains(TEXT("250")))
        {
            Send(TEXT("AUTH LOGIN\r\n"));
            CurrentStatus = EXGSampleEMailStatus::AuthLogin;
        }
        break;

    case EXGSampleEMailStatus::AuthLogin:
        if (Response.Contains(TEXT("334")))
        {
            Send(FBase64::Encode(Username) + TEXT("\r\n"));
            CurrentStatus = EXGSampleEMailStatus::AuthLogin_UserName;
        }
        break;

    // ... 后续状态依次推进

    case EXGSampleEMailStatus::Quit:
        if (Response.Contains(TEXT("221")))
        {
            CurrentStatus = EXGSampleEMailStatus::Finished;
            OnSuccess.Broadcast();
        }
        break;
    }
}
```

### 完整 SMTP 流程

```
Connected → 220 → EHLO → 250 → AUTH LOGIN
→ 334(用户名) → Base64(UserName) → 334(密码)
→ Base64(Password) → 235 → MAIL FROM → 250
→ RCPT TO → 250 → DATA → 354 → 邮件内容\r\n.\r\n
→ 250 → QUIT → 221 → Finished
```

## 邮件内容格式

```text
From: =?UTF-8?B?{Base64(FromName)}?= <{FromEmail}>
To: =?UTF-8?B?{Base64(ToName)}?= <{ToEmail}>
Subject: =?UTF-8?B?{Base64(Subject)}?=
Content-Type: text/plain;charset="utf-8"

{Body}
\r\n.\r\n
```

## 安全关闭流程

```cpp
void Shutdown()
{
    if (Runnable)
    {
        Runnable->Stop();          // 设置停止标志
        Thread->Kill(true);        // 等待线程退出
        delete Runnable;           // 释放 Runnable
        Runnable = nullptr;
        Thread = nullptr;
    }
}
```

## 插件架构

```
AsyncAction(TSharedFromThis, 脱离UObject生命周期)
  → 持有 FRunnable 引用
  → Subsystem(C++ 单例) 管理 AsyncAction
  → BPLibrary 蓝图入口
```

## 代码入口

| 文件 | 说明 |
|------|------|
| [XGSampleEMailType.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleEMail/Source/XGSampleEMail/Public/Type/XGSampleEMailType.h) | SMTP 状态枚举 + 邮件结构体 |
| [XGSampleEMailAsyncAction.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleEMail/Source/XGSampleEMail/Private/AsyncAction/XGSampleEMailAsyncAction.cpp) | OnMessage 状态机实现 |
