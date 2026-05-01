# Slate 独立程序详解

## 概述

UE 独立程序脱离编辑器直接运行，不包含 Gameplay 框架，基于源码引擎编译。课程以 XGSlateSample 项目展示完整流程：引擎初始化、Slate 主循环、MVC 三层架构、分帧状态机和暴力打包。

## 独立程序分类

| 类型 | 入口宏 | GUI |
|------|--------|-----|
| BlankProgram | `IMPLEMENT_APPLICATION` | 纯控制台 |
| Slate 独立程序 | `IMPLEMENT_APPLICATION` + Slate 初始化 | 有 GUI |
| HTTP Server（控制台） | `INT32_MAIN_INT32_ARGC_TCHAR_ARGV` | 无 GUI |

## 工程配置

### Build.cs

```csharp
PrivateDependencyModuleNames.AddRange(new string[] {
    "Slate", "SlateCore", "StandaloneRenderer",
    "SlateReflector", "SourceCodeAccess", "DesktopPlatform",
});

bIsBuildingConsoleApplication = false;  // GUI 程序
```

### Target.cs

```csharp
Type = TargetType.Program;
LinkType = TargetLinkType.Modular;
bCompileAgainstEngine = false;         // 不编译引擎
bCompileAgainstCoreUObject = true;     // 需要 UObject
```

## 引擎初始化序列

固定顺序（不可颠倒）：

```cpp
#include "LaunchEngineLoop.h"

// 1. 任务标签范围
FTaskTagScope Scope(ETaskTag::EGameThread);

// 2. 引擎预初始化
GEngineLoop.PreInit(CmdLine);

// 3. 注册 U 类（必须调用）
ProcessNewlyLoadedUObjects();
FModuleManager::StartProcessingNewlyLoadedObjects();

// 4. 初始化 Slate 独立应用
FSlateApplication::InitializeAsStandaloneApplication(
    FSlateApplication::Get().GetRenderer());

// 5. 高 DPI 支持
FSlateApplication::InitHighDPI(true);
```

## 主循环框架

```cpp
double LastTime = FPlatformTime::Seconds();

while (!IsEngineExitRequested())
{
    double CurrentTime = FPlatformTime::Seconds();
    float DeltaTime = CurrentTime - LastTime;
    LastTime = CurrentTime;

    // 帧率限制
    float TargetDelta = 1.0f / 100.0f;
    if (DeltaTime < TargetDelta)
    {
        FPlatformProcess::Sleep(TargetDelta - DeltaTime);
        continue;
    }

    // 核心三件套
    FTSTicker::GetCoreTicker().Tick(DeltaTime);
    FSlateApplication::Get().PumpMessages();
    FSlateApplication::Get().Tick();

    // 增量 GC
    float RemainTime = FPlatformTime::Seconds() - CurrentTime;
    IncrementalPurgeGarbage(true, FMath::Max(0.002f, RemainTime));
}
```

## MVC 三层架构

| 层 | 目录 | 职责 |
|---|------|------|
| Slate 层 (S) | `Slate/SXGSSP*.h` | UI 布局、事件绑定 |
| Core 管理层 | `Core/XGSSPCore.h` | 单例管理、Tick 调度 |
| 业务逻辑层 (F) | `Core/XGSSPCountCode.h` | 分帧计算逻辑 |

### Core 单例

```cpp
struct FXGSSPCore
{
    static FXGSSPCore* Get();

    void Tick(float DeltaTime);
    void AddTickObject(TWeakPtr<FXGSSPTickObject> InTickObject);
    void RemoveTickObject(TWeakPtr<FXGSSPTickObject> InTickObject);
};
```

### TickObject 接口

```cpp
struct FXGSSPTickObject
{
    virtual void Tick(float DeltaTime) = 0;
};
```

弱指针管理：不干预生命周期，每帧前清理已失效对象。

## Slate 基础

### 类声明

```cpp
class SXGSSPModifyName : public SCompoundWidget
{
    SLATE_BEGIN_ARGS(SXGSSPModifyName) {}
    SLATE_END_ARGS()

    void Construct(const FArguments& InArgs);
};
```

### 常用控件

```cpp
// 容器
SNew(SVerticalBox)
+ SVerticalBox::Slot().FillHeight(0.1f) [ /* 上区域 */ ]
+ SVerticalBox::Slot().FillHeight(0.9f) [ /* 下区域 */ ]

// 按钮
SNew(SButton)
    .Text(LOCTEXT("Key", "Label"))
    .OnClicked(this, &Class::OnButtonClicked)

// 文本框
SNew(STextBlock).Text(FText::FromString(Str))
SNew(SEditableTextBox)

// 滚动框
SNew(SScrollBox)
SScrollBox->AddSlot() [ ... ]
```

### Tab 管理器

```cpp
FGlobalTabmanager::Get()->RegisterNomadTabSpawner(
    "ModifyName", FOnSpawnTab::CreateLambda([](const FSpawnTabArgs&)
    {
        return SNew(SDockTab).TabRole(ETabRole::NomadTab)
            [ SNew(SXGSSPModifyName) ];
    }));

TSharedRef<FTabManager::FLayout> Layout = FTabManager::NewLayout("Layout")
    ->AddArea(FTabManager::NewArea(1280, 720)
        ->SetWindow(FSlateRect(100, 100, 1380, 820), false)
        ->Split(FTabManager::NewStack()
            ->AddTab("ModifyName", ETabState::OpenedTab)
            ->AddTab("CountCode", ETabState::OpenedTab)
        ));

FGlobalTabmanager::Get()->RestoreFrom(Layout, nullptr);
```

## 分帧状态机设计

### 状态枚举

```cpp
enum class ECountCodeStatus : uint8
{
    Idle,
    SearchDirectroy,    // 阶段 1：广度优先遍历目录
    SearchFile,         // 阶段 2：筛选文件
    CountCode,          // 阶段 3：统计行数
    Finish,
    Max
};
```

### 分帧核心

```cpp
void FXGSSPCountCode::Tick(float DeltaTime)
{
    switch (CountCodeStatus)
    {
    case ECountCodeStatus::SearchDirectroy:
    {
        // 每帧只处理一个目录
        FString CurrentDir = SearchedDirectories[0];
        SearchedDirectories.RemoveAt(0);

        TArray<FString> SubDirs, Files;
        IFileManager::Get().FindFiles(SubDirs, *(CurrentDir / TEXT("*")), false, true);
        IFileManager::Get().FindFiles(Files, *(CurrentDir / TEXT("*")), true, false);

        SearchedDirectories.Append(SubDirs);
        for (auto& File : Files)
            SearchedFiles.Add(CurrentDir / File);

        if (SearchedDirectories.Num() == 0)
            CountCodeStatus = ECountCodeStatus::SearchFile;
        break;
    }
    case ECountCodeStatus::SearchFile:
    {
        // 每帧检查一个文件后缀
        FString File = SearchedFiles[0];
        SearchedFiles.RemoveAt(0);

        if (File.EndsWith(TEXT(".h")) || File.EndsWith(TEXT(".cpp")))
            if (!File.Contains(TEXT("/Intermediate/"))
                && !File.Contains(TEXT("/Binaries/")))
                ValidFiles.Add(File);

        if (SearchedFiles.Num() == 0)
            CountCodeStatus = ECountCodeStatus::CountCode;
        break;
    }
    // ...
    }
}
```

### UI 日志系统

```cpp
void PrintToDisplay(const FString& InStr)
{
    if (LogNum > 1000)
    {
        LogBox->ClearChildren();
        LogNum = 0;
    }
    LogBox->AddSlot() [ SNew(STextBlock).Text(FText::FromString(InStr)) ];
    LogBox->ScrollToEnd();
    LogNum++;
}
```

## 文件操作

### 打开文件夹对话框

```cpp
IDesktopPlatform* DesktopPlatform = FDesktopPlatformModule::Get();
void* ParentWindow = FSlateApplication::Get()
    .FindBestParentWindowHandleForDialogs(nullptr);

FString FolderName;
bool bOpened = DesktopPlatform->OpenDirectoryDialog(
    ParentWindow, TEXT("选择文件夹"), LastDirectory, FolderName);
```

### 文件遍历

```cpp
IFileManager::Get().FindFiles(FoundFiles, *(Path / TEXT("*")), true, false);
//                                                                找文件  不找文件夹
```

### 重命名

```cpp
IFileManager::Get().Move(*NewPath, *OldPath);
FString::RemoveFromStart(Prefix);  // 移除前缀
```

## 暴力打包

### 打包命令

```bash
Engine\Build\BatchFiles\RunUAT.bat BuildGraph
    -Script="Engine/Build/InstalledEngineBuild.xml"
    -Target="Make Installed Build Win64"
    -set:HostPlatformOnly=true
```

### 最小依赖清单

| 保留项目 | 说明 |
|---------|------|
| `Engine/Binaries/Win64/` | 程序 EXE + DLL |
| `Engine/Config/` | 配置文件 |
| `Engine/Content/Slate/` | Slate 图标/样式 |
| `Engine/Content/EditorSlate/` | 编辑器图标 |
| `Engine/Shaders/` | Standard Renderer Shader |
| `Engine/ThirdParty/CEF3/` | UE 5.4 新增 |
| `Engine/Content/Localization/` | 国际化资源 |

UE 5.4.2 相比 5.0.3 新增 CEF3 依赖，打包体积显著增大。

## 生命周期

```
Slate 控件持有 TSharedPtr<FXGSSPCountCode>
  → 控件析构时引用计数归零 → 自动释放
  → Core 管理器弱指针自动失效移除
```

## 代码入口

| 文件 | 说明 |
|------|------|
| [XGSlateSample.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/013_独立程序源码/XGSlateSample/Private/XGSlateSample.cpp) | 主入口 + 引擎初始化 |
| [XGSSPCore.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/013_独立程序源码/XGSlateSample/Private/Core/XGSSPCore.h) | Core 单例管理器 |
| [XGSSPCountCode.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/013_独立程序源码/XGSlateSample/Private/Core/XGSSPCountCode.h) | 分帧代码计数 |
| [SXGSSPModifyName.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/013_独立程序源码/XGSlateSample/Private/Slate/SXGSSPModifyName.h) | ModifyName 控件 |
| [SXGSSPCountCodeBox.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/013_独立程序源码/XGSlateSample/Private/Slate/SXGSSPCountCodeBox.h) | CountCode 控件 |
