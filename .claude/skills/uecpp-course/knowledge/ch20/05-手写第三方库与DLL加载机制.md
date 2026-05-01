# 手写第三方库与 DLL 加载机制

## 概述

本部分讲解如何创建一个自定义 C++ DLL 作为 UE 的"第三方库"，并在插件中通过蓝图函数库调用其函数。核心演示了 DLL **封装隔离**的价值——函数实现细节对 UE 项目完全不可见。

---

## DLL 封装隔离演示

### XGAdd 函数行为

自定义 DLL 中的 `XGOneOneTwo` 函数执行 `InA + InB + 10`（人为加 10 的偏移量）：

```cpp
// ExampleLibrary.h — DLL 导出声明
EXAMPLELIBRARY_IMPORT int XGOneOneTwo(int InA, int InB);
```

调用 `1 + 1` 得到结果 **12**，因为 DLL 内部执行了 `1 + 1 + 10`。这个 +10 的偏移量在 UE 代码中完全不可见，体现了 DLL 的封装优势。

### 蓝图调用

[UXGThirtyPartyBPLibrary](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/002_XGSampleTemp/Plugins/XGThirdPartyLibrary/Source/XGThirdPartyLibrary/Public/XGThirtyPartyBPLibrary.h) 通过 `UFUNCTION(BlueprintCallable)` 暴露给蓝图：

```cpp
UCLASS()
class UXGThirtyPartyBPLibrary : public UObject
{
    GENERATED_BODY()

    UFUNCTION(BlueprintCallable,
        meta = (DisplayName = "XGThirtyPartyTest",
                Keywords = "XGBlueprintLibrary sample test"),
        Category = "XG")
    static int32 XGThirtyPartyTest(int32 InA, int32 InB);
};
```

实现中调用 DLL 函数：

```cpp
#include "XGThirdPartyLibraryLibrary/ExampleLibrary.h"

int32 UXGThirtyPartyBPLibrary::XGThirtyPartyTest(int32 InA, int32 InB)
{
    return XGOneOneTwo(InA, InB);
}
```

---

## 两种 DLL 加载方式

### 隐式加载

| 步骤 | 说明 |
|------|------|
| 1. 链接 .lib | `PublicAdditionalLibraries.Add("ExampleLibrary.lib")` |
| 2. 声明延迟加载 | `PublicDelayLoadDLLs.Add("ExampleLibrary.dll")` |
| 3. 系统自动加载 | 程序启动时，操作系统根据 PE 导入表自动加载 DLL |

隐式加载时，DLL 需要位于系统搜索路径中（如 exe 同目录、系统 PATH、插件 Binaries 目录）。

### 显式加载

在 `StartupModule()` 中手动加载 DLL，适合需要控制加载时机的场景：

```cpp
// 获取插件基目录
FString BaseDir = IPluginManager::Get()
    .FindPlugin("XGThirdPartyLibrary")->GetBaseDir();

// 拼接 DLL 路径
FString LibraryPath = FPaths::Combine(
    *BaseDir, TEXT("Binaries/ThirdParty/XGThirdPartyLibraryLibrary/Win64/ExampleLibrary.dll"));

// 手动加载 DLL
void* ExampleLibraryHandle = FPlatformProcess::GetDllHandle(*LibraryPath);

if (ExampleLibraryHandle)
{
    ExampleLibraryFunction();  // 调用 DLL 中的函数
}
else
{
    FMessageDialog::Open(EAppMsgType::Ok,
        LOCTEXT("ThirdPartyLibraryError",
            "Failed to load example third party library"));
}
```

### 两种方式对比

| 特性 | 隐式加载 | 显式加载 |
|------|---------|---------|
| 配置复杂度 | 简单（Build.cs 配置） | 中等（需手写加载代码） |
| 加载时机 | 进程启动时自动加载 | 可控制在任意时机 |
| 加载失败处理 | 进程直接崩溃 | 可捕获并显示友好错误 |
| 适用场景 | 简单的第三方库 | 需要优雅处理缺失的情况 |

课程采用**同时使用两种方式**的策略：隐式加载确保函数符号可解析，显式加载在模块启动时验证 DLL 可访问并提供错误提示。

---

## RuntimeDependencies 配置

为了确保 DLL 在**打包后**也能被正确包含，需要在 Build.cs 中添加 `RuntimeDependencies`：

```csharp
RuntimeDependencies.Add(
    "$(PluginDir)/Binaries/ThirdParty/XGThirdPartyLibraryLibrary/Win64/ExampleLibrary.dll");
```

`$(PluginDir)` 在构建时自动展开为插件根目录路径。

---

## 完整启动/关闭流程

![模块生命周期](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/002_XGSampleTemp/Plugins/XGThirdPartyLibrary/Source/XGThirdPartyLibrary/Private/XGThirdPartyLibrary.cpp)

```cpp
// Startup — 显式加载 DLL
void FXGThirdPartyLibraryModule::StartupModule()
{
    // ... 获取路径，调用 GetDllHandle
    ExampleLibraryHandle = FPlatformProcess::GetDllHandle(*LibraryPath);
    if (ExampleLibraryHandle)
    {
        ExampleLibraryFunction();
    }
}

// Shutdown — 释放 DLL 句柄
void FXGThirdPartyLibraryModule::ShutdownModule()
{
    FPlatformProcess::FreeDllHandle(ExampleLibraryHandle);
    ExampleLibraryHandle = nullptr;
}
```

---

## 头文件声明宏

DLL 导出声明兼容多平台：

```cpp
#if defined _WIN32 || defined _WIN64
#define EXAMPLELIBRARY_IMPORT __declspec(dllimport)
#elif defined __linux__
#define EXAMPLELIBRARY_IMPORT __attribute__((visibility("default")))
#else
#define EXAMPLELIBRARY_IMPORT
#endif

EXAMPLELIBRARY_IMPORT void ExampleLibraryFunction();
EXAMPLELIBRARY_IMPORT int XGOneOneTwo(int InA, int InB);
```

---

## 代码对应关系

| 文件 | 说明 |
|------|------|
| [XGThirdPartyLibrary.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/002_XGSampleTemp/Plugins/XGThirdPartyLibrary/Source/XGThirdPartyLibrary/Private/XGThirdPartyLibrary.cpp) | 模块启动/关闭 + 显式 DLL 加载 |
| [XGThirtyPartyBPLibrary.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/002_XGSampleTemp/Plugins/XGThirdPartyLibrary/Source/XGThirdPartyLibrary/Public/XGThirtyPartyBPLibrary.h) | 蓝图可调用的包装函数 |
| [XGThirtyPartyBPLibrary.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/002_XGSampleTemp/Plugins/XGThirdPartyLibrary/Source/XGThirdPartyLibrary/Private/XGThirtyPartyBPLibrary.cpp) | 调用 DLL 函数 XGOneOneTwo |
| [ExampleLibrary.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/002_XGSampleTemp/Plugins/XGThirdPartyLibrary/Source/ThirdParty/XGThirdPartyLibraryLibrary/Public/XGThirdPartyLibraryLibrary/ExampleLibrary.h) | DLL 导出函数声明 |
