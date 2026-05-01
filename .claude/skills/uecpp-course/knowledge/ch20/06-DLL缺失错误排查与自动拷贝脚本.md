# DLL 缺失错误排查与自动拷贝脚本

## 概述

第三方库 DLL 在开发、运行和打包阶段都可能出现缺失问题。本章演示了三种典型错误场景及其解决方案，并实现了一个 UBT 预构建 C# 脚本来自动化拷贝 DLL 到目标位置。

---

## 典型错误场景

### 场景一：删除 Intermediate/Binaries 后崩溃

**现象**：清理项目后，编辑器启动时弹出错误对话框：

> "Failed to load example third party library"

随后编辑器崩溃。

**原因**：`StartupModule()` 调用 `FPlatformProcess::GetDllHandle()` 加载 DLL，DLL 不存在时返回空句柄，触发 `FMessageDialog::Open` 并导致致命错误。

**解决**：重新编译插件，确保 DLL 被拷贝到 `Binaries/ThirdParty/` 目录。

### 场景二：打包失败 — DLL 未包含

**现象**：执行 Package Project 时，打包过程在拷贝阶段失败并报错 `failed copy`。

**原因**：未在 Build.cs 中配置 `RuntimeDependencies`，打包系统不知道需要包含 DLL 到发布产物中。

**解决**：在 External 模块的 Build.cs 中添加：

```csharp
RuntimeDependencies.Add("$(PluginDir)/Binaries/ThirdParty/XGThirdPartyLibraryLibrary/Win64/ExampleLibrary.dll");
```

### 场景三：运行时崩溃 — Dump 文件分析

**现象**：打包后的程序运行时崩溃，生成 `.dmp`（dump）文件。

**调试方法**：

1. 双击 `.dmp` 文件，在 Visual Studio 中打开
2. 选择 **Debug Native Only**（仅调试本机代码）
3. 查看调用堆栈，定位到 `ThirdPartyTest` 函数附近
4. 观察到崩溃原因是 DLL 中的函数无法解析

---

## 方案对比：三种修复方式

| 方案 | 操作 | 评价 |
|------|------|------|
| **修改 .gitignore** | 添加规则包含二进制 DLL 文件 | 不推荐，违背源码管理原则 |
| **自动拷贝（推荐）** | UBT 预构建 C# 脚本自动复制 | 最可靠，全自动 |
| **手动拷贝** | 每次更新 DLL 后手动复制到目标位置 | 容易遗漏 |

---

## UBT 预构建 C# 脚本

### 核心概念

UBT（Unreal Build Tool）允许在 Build.cs 中编写 C# 代码，在编译前后执行自定义操作。

### 三个路径概念

| 路径 | 说明 |
|------|------|
| **Source 路径** | 第三方库原始文件位置：`Plugin/ThirdParty/<Library>/x64/Release/ExampleLibrary.dll` |
| **Pre-build 目标** | 开发运行时的 DLL 位置：`Plugin/Binaries/ThirdParty/<Library>/Win64/` |
| **Post-build 目标** | 打包后的 DLL 位置：由 `RuntimeDependencies` 控制 |

### 自动拷贝函数实现

在 [XGThirdPartyLibraryLibrary.Build.cs](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/002_XGSampleTemp/Plugins/XGThirdPartyLibrary/Source/ThirdParty/XGThirdPartyLibraryLibrary/XGThirdPartyLibraryLibrary.Build.cs) 中：

```csharp
private void CopyDllToPluginBinaries(string InFilePath, ReadOnlyTargetRules Target)
{
    // 目标目录：Plugin/Binaries/ThirdParty/XGThirdPartyLibraryLibrary/Win64/
    string TargetDirectory = Path.GetFullPath(
        Path.Combine(PluginDirectory, "Binaries/ThirdParty",
                     "XGThirdPartyLibraryLibrary", "Win64"));

    string FileName = Path.GetFileName(InFilePath);

    if (!Directory.Exists(TargetDirectory))
    {
        Directory.CreateDirectory(TargetDirectory);
    }

    string TargetFilePath = Path.Combine(TargetDirectory, FileName);

    if (!File.Exists(TargetFilePath))
    {
        File.Copy(InFilePath, TargetFilePath, true);
    }

    // 确保 DLL 在打包时被包含
    RuntimeDependencies.Add(
        "$(PluginDir)/Binaries/ThirdParty/XGThirdPartyLibraryLibrary/Win64/ExampleLibrary.dll");
}
```

### 脚本调用时机

在 Build.cs 构造函数中调用：

```csharp
public XGThirdPartyLibraryLibrary(ReadOnlyTargetRules Target) : base(Target)
{
    Type = ModuleType.External;
    // ... 其他配置 ...

    if (Target.Platform == UnrealTargetPlatform.Win64)
    {
        PublicAdditionalLibraries.Add(...);
        PublicDelayLoadDLLs.Add("ExampleLibrary.dll");

        // 在编译时自动拷贝 DLL
        CopyDllToPluginBinaries(
            Path.Combine(ModuleDirectory, "x64", "Release", "ExampleLibrary.dll"),
            Target);
    }
}
```

### `PluginDirectory` 属性

`PluginDirectory` 是 `ModuleRules` 的内置属性，指向插件根目录，无需手动拼接。

---

## 插件资源

### 插件图标

- 尺寸：**128×128 像素**
- 格式：PNG
- 位置：`Resources/Icon128.png`
- 在编辑器的 Plugin Manager 中显示

### Config 文件

插件可以包含自定义配置文件，放在 `Config/` 目录下，引擎会自动加载。

---

## 平台白名单

在 `.uplugin` 中通过 `PlatformAllowList` 限制支持的平台：

```json
"PlatformAllowList": ["Win64"]
```

也可在 Build.cs 中用条件编译：

```csharp
if (Target.Platform == UnrealTargetPlatform.Win64)
{
    // Windows 专属配置
}
```

---

## 代码对应关系

| 文件 | 说明 |
|------|------|
| [XGThirdPartyLibraryLibrary.Build.cs](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/002_XGSampleTemp/Plugins/XGThirdPartyLibrary/Source/ThirdParty/XGThirdPartyLibraryLibrary/XGThirdPartyLibraryLibrary.Build.cs) | 自动拷贝脚本 + RuntimeDependencies |
| [XGThirdPartyLibrary.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/002_XGSampleTemp/Plugins/XGThirdPartyLibrary/Source/XGThirdPartyLibrary/Private/XGThirdPartyLibrary.cpp) | 显式加载 DLL + 错误提示 |
