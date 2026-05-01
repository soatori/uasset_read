# 自定义 INI 配置系统

## 概述

XGSampleServer 使用了一套**手写的 INI 配置文件解析系统**，而不是使用 UE 内置的 `GConfig` 或 `DeveloperSettings`。这是因为独立程序没有 UEEditor 的配置层级支持，手写 INI 解析是最直接可靠的方案。

核心类：`FXGSampleServerConfigManage`（纯 C++ 单例，非 UObject）

路径：[XGSampleServerConfig.h](../code/013_独立程序源码/XGSampleServer/Private/Config/XGSampleServerConfig.h)，[XGSampleServerConfig.cpp](../code/013_独立程序源码/XGSampleServer/Private/Config/XGSampleServerConfig.cpp)

## 配置字段

INI 文件使用 `[XGLoginServerConfigManage]` Section 组织，包含以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `ServerVersion` | `FString` | 服务器版本号，硬编码在代码中做版本校验 |
| `Token` | `FString` | 通信令牌，客户端和服务端需一致 |
| `MD5Num` | `int32` | MD5 加密迭代次数 |
| `Port` | `int32` | HTTP 服务器监听端口 |

## 架构设计

```
┌─────────────────────────────────────────────────────────┐
│ FXGSampleServerConfigManage                              │
│  ┌─────────────────────────────────────────────────┐    │
│  │ 静态 Instance 指针                               │    │
│  │ (单例, 非UObject, 纯C++全局指针)                 │    │
│  ├─────────────────────────────────────────────────┤    │
│  │ Init()     → 读取 INI → 解析 → 版本验证          │    │
│  │ Destory()  → 释放单例                            │    │
│  │ GetInfo()  → 返回 FXGSampleServerConfigInfo     │    │
│  │ CreatDefult() → 创建默认配置文件                  │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

## 数据类

```cpp
USTRUCT()
struct FXGSampleServerConfigInfo
{
    GENERATED_BODY()
    FString ServerVersion = "1.0.0";
    FString Token;
    int32 MD5Num;
    int32 Port;
};
```

`ServerVersion` 在代码中硬编码为 `"1.0.0"`，作为版本校验的基准值。

## INI 解析实现

读取使用 `FFileHelper::LoadFileToStringArray`，逐行解析：

```cpp
void FXGSampleServerConfigManage::Init()
{
    FString ConfigFilePath = FPaths::ProjectDir() + TEXT("Config/XGSampleServerConfig.ini");
    TArray<FString> Content;
    FFileHelper::LoadFileToStringArray(Content, *ConfigFilePath);

    TMap<FString, FString> ConfigPairs;
    bool bInTargetSection = false;

    for (auto& Str : Content)
    {
        Str.TrimStartAndEndInline();
        if (Str.Equals(TEXT("[XGLoginServerConfigManage]")))
        {
            bInTargetSection = true;
            continue;
        }
        if (Str.StartsWith(TEXT("[")) && bInTargetSection) break;

        if (bInTargetSection)
        {
            FString Key, Value;
            if (Str.Split(TEXT("="), &Key, &Value))
            {
                ConfigPairs.Add(Key.TrimStartAndEnd(), Value.TrimStartAndEnd());
            }
        }
    }

    // 赋值
    ConfigInfo.Token = ConfigPairs["Token"];
    ConfigInfo.Port = FCString::Atoi(*ConfigPairs["Port"]);
    ConfigInfo.MD5Num = FCString::Atoi(*ConfigPairs["MD5Num"]);

    // 版本校验
    if (!ConfigInfo.ServerVersion.Equals(ConfigPairs["ServerVersion"]))
    {
        // 自动修复 INI
        WriteConfigToFile();
    }
}
```

## 版本校验与自动修复

当 INI 文件中的 `ServerVersion` 与代码中的硬编码版本不一致时，配置管理器会**自动用代码版本覆盖 INI 内容**并重写文件。这确保了 INI 格式和版本始终保持最新，防止手动修改 INI 引入兼容性问题。

```cpp
void FXGSampleServerConfigManage::WriteConfigToFile()
{
    TArray<FString> NewContent;
    NewContent.Add(TEXT("[XGLoginServerConfigManage]"));
    NewContent.Add(FString::Printf(TEXT("ServerVersion=%s"), *ConfigInfo.ServerVersion));
    NewContent.Add(FString::Printf(TEXT("Token=%s"), *ConfigInfo.Token));
    NewContent.Add(FString::Printf(TEXT("MD5Num=%i"), ConfigInfo.MD5Num));
    NewContent.Add(FString::Printf(TEXT("Port=%i"), ConfigInfo.Port));
    FFileHelper::SaveStringArrayToFile(NewContent, *ConfigFilePath);
}
```

## 默认配置文件创建

当 INI 文件不存在时，`CreatDefult()` 生成包含默认值的配置文件。

## 单例管理

```cpp
FXGSampleServerConfigManage* FXGSampleServerConfigManage::Instance = nullptr;

FXGSampleServerConfigManage* FXGSampleServerConfigManage::Get()
{
    if (!Instance) Instance = new FXGSampleServerConfigManage();
    return Instance;
}

void FXGSampleServerConfigManage::Destory()
{
    if (Instance) { delete Instance; Instance = nullptr; }
}
```

纯 C++ 单例模式，不需要 UObject 生命周期管理。在 `XGSampleServer.cpp` 入口的 PreInit 后调用 `Init()`，Exit 前调用 `Destory()`。

## 与第二十三章配置系统的对比

| 维度 | 第二十三章 (Slate) | 第二十六章 (HTTPServer) |
|------|-------------------|----------------------|
| 配置类 | `FXGSSPConfigManager` | `FXGSampleServerConfigManage` |
| 配置文件路径 | `Config/XGSSPConfig.ini` | `Config/XGSampleServerConfig.ini` |
| 解析方式 | 自定义格式解析 | 标准 INI Section + Key=Value 解析 |
| 单例类型 | 原生 C++ | 原生 C++ |
| 版本校验 | 无 | 有（版本不匹配时自动修复） |
