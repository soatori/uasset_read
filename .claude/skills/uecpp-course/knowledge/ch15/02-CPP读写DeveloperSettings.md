# C++ 中读取与修改 DeveloperSettings

## 获取 Settings 实例

DeveloperSettings 是一个 CDO（Class Default Object），通过 `GetMutableDefault<T>()` 获取：

```cpp
static UXGSampleSettings* GetXGXunFeiCoreSettings()
{
    UXGSampleSettings* Settings = GetMutableDefault<UXGSampleSettings>();
    return Settings;
}
```

`GetMutableDefault` 是模板函数，返回类的 CDO 指针。由于返回的是 Mutable（可修改的）引用，可以读取和写入属性。

## 读取 Settings 属性

```cpp
bool AXGConfigActor::GetMyAppKey(FString& OutMyAppKey)
{
    UXGSampleSettings* XGSampleSettings = UXGSampleSettings::GetXGXunFeiCoreSettings();

    if (XGSampleSettings)
    {
        OutMyAppKey = XGSampleSettings->XGAppKey;
        return true;
    }

    OutMyAppKey = TEXT("None");
    return false;
}
```

- 通过静态工厂函数获取 Settings
- 判空后再读取属性
- 如果获取失败返回兜底值

## 修改 Settings 属性并持久化

```cpp
void AXGConfigActor::SetMyAppKey(const FString& InMyAppKey)
{
    UXGSampleSettings* XGSampleSettings = UXGSampleSettings::GetXGXunFeiCoreSettings();

    if (XGSampleSettings)
    {
        XGSampleSettings->XGAppKey = InMyAppKey;

        XGSampleSettings->Modify();

        FString ConfigPath = FPaths::ConvertRelativePathToFull(
            FPaths::ProjectConfigDir() / TEXT("DefaultXGSampleSettings.ini"));

        XGSampleSettings->SaveConfig(CPF_Config, *ConfigPath);
    }
}
```

### 修改流程

| 步骤 | 代码 | 说明 |
|------|------|------|
| 1. 获取 | `GetXGXunFeiCoreSettings()` | 获取 CDO 实例 |
| 2. 赋值 | `XGSampleSettings->XGAppKey = InMyAppKey` | 修改属性 |
| 3. 标记 | `Modify()` | 标记对象为已修改（脏标记），确保后续保存生效 |
| 4. 写路径 | `FPaths::ProjectConfigDir() / "DefaultXGSampleSettings.ini"` | 构造目标 INI 文件路径 |
| 5. 保存 | `SaveConfig(CPF_Config, *ConfigPath)` | 将属性写回 INI 文件 |

### FPaths 路径工具

| 函数 | 返回值示例 | 说明 |
|------|----------|------|
| `FPaths::ProjectConfigDir()` | `../../../ProjectName/Config/` | 工程 Config 目录（相对路径） |
| `FPaths::ConvertRelativePathToFull()` | `D:/Projects/.../Config/` | 相对路径转绝对路径 |
| `FPaths::SourceConfigDir()` | `D:/Projects/.../Config/` | Source Config 目录（绝对路径，旧版） |

路径拼接使用 `/` 运算符：`FPaths::ProjectConfigDir() / TEXT("DefaultXGSampleSettings.ini")`

## Blueprint 中访问

对应函数标记为 `BlueprintPure` 或 `BlueprintCallable` 后，蓝图可以直接调用：

- `GetMyAppKey` — `BlueprintPure`，返回 AppKey
- `SetMyAppKey` — `BlueprintCallable`，修改 AppKey

## INI 文件结构

修改后的值最终写入 `DefaultXGSampleSettings.ini`：

```ini
[/Script/XGSampleDemo.XGSampleSettings]
ProjectSimpleName="1.0.0"
XGAppID="None"
XGAppKey="None"
```

- 段名由 UCLASS 的 `Config = XGSampleSettings` 决定：`[/Script/{ModuleName}.{ClassName}]`
- 键名对应 `UPROPERTY(Config)` 的属性名
- 段名中的 ModuleName 是 `.Build.cs` 中定义的模块名

## 配套代码

- [XGConfigActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/018_Config/XGConfigActor.h) — GetMyAppKey/SetMyAppKey 声明
- [XGConfigActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/018_Config/XGConfigActor.cpp) — 读取和修改 Settings 的完整实现
- [XGSampleSettings.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/018_Config/XGSampleSettings.cpp) — GetXGXunFeiCoreSettings 工厂方法
