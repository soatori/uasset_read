# 第三方库封装标准结构与 Build 配置

## 概述

`XGThirdPartyLibrary` 插件是本章的核心案例，演示了在 UE 插件中集成外部原生库（C/C++ DLL）的标准做法。其核心是将第三方代码隔离在 **External 模块**中，避免引擎编译系统直接处理第三方源码。

---

## 第三方库插件目录结构

```
XGThirdPartyLibrary/
├── XGThirdPartyLibrary.uplugin
├── Resources/Icon128.png
└── Source/
    ├── XGThirdPartyLibrary/             ← Internal 模块（使用第三方库的代码）
    │   ├── XGThirdPartyLibrary.Build.cs
    │   ├── Public/
    │   │   ├── XGThirdPartyLibrary.h
    │   │   └── XGThirtyPartyBPLibrary.h
    │   └── Private/
    │       ├── XGThirdPartyLibrary.cpp
    │       └── XGThirtyPartyBPLibrary.cpp
    └── ThirdParty/
        └── XGThirdPartyLibraryLibrary/  ← External 模块（第三方库本身）
            ├── XGThirdPartyLibraryLibrary.Build.cs
            ├── Public/XGThirdPartyLibraryLibrary/
            │   └── ExampleLibrary.h      ← 头文件
            └── x64/Release/
                └── ExampleLibrary.lib    ← 导入库（静态链接用）
```

### .uplugin 配置

[XGThirdPartyLibrary.uplugin](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/002_XGSampleTemp/Plugins/XGThirdPartyLibrary/XGThirdPartyLibrary.uplugin)：

```json
{
    "Modules": [
        {
            "Name": "XGThirdPartyLibrary",
            "Type": "Runtime",
            "LoadingPhase": "Default",
            "PlatformAllowList": ["Win64"]
        }
    ]
}
```

仅声明 `XGThirdPartyLibrary` 模块，`XGThirdPartyLibraryLibrary`（External 模块）作为依赖被自动发现。

---

## External 模块 vs Internal 模块

| 概念 | 说明 | Build.cs Type |
|------|------|--------------|
| **External** | 告知引擎**不要查找或编译源码**，只链接预编译的产物（.lib/.dll） | `Type = ModuleType.External` |
| **Internal** | 正常编译源码，通过 `PublicDependencyModuleNames` 引用 External 模块 | 默认（Runtime） |

### External 模块 Build.cs

[XGThirdPartyLibraryLibrary.Build.cs](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/002_XGSampleTemp/Plugins/XGThirdPartyLibrary/Source/ThirdParty/XGThirdPartyLibraryLibrary/XGThirdPartyLibraryLibrary.Build.cs)：

```csharp
public class XGThirdPartyLibraryLibrary : ModuleRules
{
    public XGThirdPartyLibraryLibrary(ReadOnlyTargetRules Target) : base(Target)
    {
        Type = ModuleType.External;

        // 添加头文件搜索路径
        PublicSystemIncludePaths.Add("$(ModuleDir)/Public");

        if (Target.Platform == UnrealTargetPlatform.Win64)
        {
            // 链接 .lib 导入库
            PublicAdditionalLibraries.Add(
                Path.Combine(ModuleDirectory, "x64", "Release", "ExampleLibrary.lib"));

            // 延迟加载 DLL
            PublicDelayLoadDLLs.Add("ExampleLibrary.dll");
        }
    }
}
```

| 配置项 | 用途 |
|--------|------|
| `Type = ModuleType.External` | 标记为外部模块，不编译源码 |
| `PublicSystemIncludePaths` | 头文件搜索路径 |
| `PublicAdditionalLibraries` | 链接静态库（.lib） |
| `PublicDelayLoadDLLs` | 延迟加载 DLL（直到程序调用相关函数时才加载） |
| `Platform == UnrealTargetPlatform.Win64` | 仅限 Win64 平台 |

### Internal 模块 Build.cs

[XGThirdPartyLibrary.Build.cs](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/002_XGSampleTemp/Plugins/XGThirdPartyLibrary/Source/XGThirdPartyLibrary/XGThirdPartyLibrary.Build.cs)：

```csharp
PublicDependencyModuleNames.AddRange(
    new string[]
    {
        "Core",
        "CoreUObject",
        "XGThirdPartyLibraryLibrary",   // 引用 External 模块
        "Projects"
    });
```

Internal 模块通过 `PublicDependencyModuleNames` 引用 External 模块，即可使用第三方库的头文件和链接符号。

---

## 第三方库目录命名规范

标准第三方库目录结构：

```
ThirdParty/<LibraryName>/
├── <LibraryName>.Build.cs
├── Public/<LibraryName>/
│   └── 头文件
├── bin/   (可选)  ← DLL 文件
└── lib/   (可选)  ← .lib 静态库
```

课程示例使用 `x64/Release/` 子目录存放编译好的库文件，这是根据不同平台/配置划分的常见做法。

---

## 代码对应关系

| 文件 | 角色 |
|------|------|
| [XGThirdPartyLibraryLibrary.Build.cs](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/002_XGSampleTemp/Plugins/XGThirdPartyLibrary/Source/ThirdParty/XGThirdPartyLibraryLibrary/XGThirdPartyLibraryLibrary.Build.cs) | External 模块构建配置 |
| [XGThirdPartyLibrary.Build.cs](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/002_XGSampleTemp/Plugins/XGThirdPartyLibrary/Source/XGThirdPartyLibrary/XGThirdPartyLibrary.Build.cs) | Internal 模块构建配置 |
| [ExampleLibrary.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/002_XGSampleTemp/Plugins/XGThirdPartyLibrary/Source/ThirdParty/XGThirdPartyLibraryLibrary/Public/XGThirdPartyLibraryLibrary/ExampleLibrary.h) | 第三方库头文件（dllimport 声明） |
| [ExampleLibrary.lib](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/002_XGSampleTemp/Plugins/XGThirdPartyLibrary/Source/ThirdParty/XGThirdPartyLibraryLibrary/x64/Release/ExampleLibrary.lib) | 预编译的导入库 |
