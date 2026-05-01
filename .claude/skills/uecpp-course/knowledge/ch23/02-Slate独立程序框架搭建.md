# Slate 独立程序框架搭建

## 概述

从 BlankProgram 到 Slate 独立程序的升级，核心变化是：主函数从简单的命令行执行变为带窗口消息循环的独立应用。搭建过程涉及 Build.cs/Target.cs 配置、引擎预初始化链、SlateApplication 初始化、主循环框架和帧率控制。

## Build.cs 配置

Slate 独立程序需要引入大量 Slate 相关模块（参照引擎 SlateViewer 模板）：

```csharp
// 关键模块依赖
PrivateDependencyModuleNames.AddRange(new string[] {
    "Slate", "SlateCore", "StandaloneRenderer",
    "SlateReflector",           // Slate 调试工具
    "SourceCodeAccess",         // 源码访问模块
    "DesktopPlatform",          // 桌面平台 API（文件对话框等）
});
```

- `StandaloneRenderer`：独立渲染器，非编辑器模式下的渲染支持
- `SlateReflector`：可选，用于 Slate Widget 调试反射
- `bBuildDeveloperTools = false`：独立程序不需要开发者工具
- `bIsBuildingConsoleApplication = false`：Slate 程序是 GUI 程序，非控制台

## Target.cs 配置

Target 文件指定编译目标和产物路径：

```csharp
public class XGSlateSampleTarget : TargetRules
{
    public XGSlateSampleTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Program;
        LinkType = TargetLinkType.Modular;
        LaunchModuleName = "XGSlateSample";  // 启动模块名

        // 产物输出路径
        SolutionDirectory = "Programs/XG Slate Programs";

        // 关键开关
        bBuildDeveloperTools = false;
        bCompileAgainstEngine = false;
        bCompileAgainstCoreUObject = true;   // 需要 UObject 支持
        bCompileICU = true;                   // 国际化支持
    }
}
```

## 引擎初始化序列

Slate 独立程序的主入口 `WinMain`，初始化序列固定且不可省略：

```
1. FTaskTagScope           ← 标记当前为 GameThread
2. GEngineLoop.PreInit()   ← 引擎预初始化（解析命令行参数）
3. ProcessNewlyLoadedUObjects()  ← 注册所有 U 类 & 初始化默认属性
4. FModuleManager::StartProcessingNewlyLoadedObjects() ← 模块可处理新 U 类
5. FSlateApplication::InitializeAsStandaloneApplication() ← 初始化 Slate 应用
6. FSlateApplication::InitHighDPI(true)  ← 高 DPI 支持
```

**`ProcessNewlyLoadedUObjects()` 是必须调用的** — 文档注释明确指出：当模块被添加后，如果包含 U 类，必须执行此函数。漏调会导致 U 类未注册。

配套代码详见 [XGSlateSample.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/013_独立程序源码/XGSlateSample/Private/XGSlateSample.cpp#L33-L51)。

## 主循环框架 (外循环)

独立程序的"外循环"是引擎层级的 `while (!IsEngineExitRequested())`：

```cpp
while (!IsEngineExitRequested())
{
    BeginExitIfRequested();  // 检查退出命令

    // 帧内需要执行的核心操作
    FTSTicker::GetCoreTicker().Tick(DeltaTime);     // CoreTicker 推进
    FSlateApplication::Get().PumpMessages();         // 处理 Windows 消息
    FSlateApplication::Get().Tick();                 // Slate 自身 Tick

    GFrameCounter++;                                  // 帧数计数

    // 增量垃圾回收
    IncrementalPurgeGarbage(true, ...);
    // 帧率控制 Sleep
    FPlatformProcess::Sleep(...);
}
```

外循环结束后执行：引擎预退出 → SlateApplication 关闭 → 卸载模块 → 引擎退出。

配套代码详见 [XGSlateSample.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/013_独立程序源码/XGSlateSample/Private/XGSlateSample.cpp#L139-L181)。

## 内循环与帧率控制

"内循环"是开发者自己添加的业务代码，放置在外循环的 while 体内。典型的帧率控制模式：

```cpp
double LastTime = FPlatformTime::Seconds();
const float IdealFrameTime = 1.0f / 100;  // 目标100帧

while (!IsEngineExitRequested())
{
    double CurrentTime = FPlatformTime::Seconds();
    double DeltaTime = CurrentTime - LastTime;

    // --- 内循环业务代码 ---

    LastTime = CurrentTime;

    // 帧率限制：如果本帧耗时少于目标帧时间，Sleep 差值
    float SleepTime = FMath::Max(0.0f,
        IdealFrameTime - (FPlatformTime::Seconds() - CurrentTime));
    FPlatformProcess::Sleep(SleepTime);
}
```

**帧率数据**：
- 空白独立程序（无 Slate）：约 8000~10000 帧/秒
- 带 Slate UI 框架：约 1000 帧/秒
- 限制到 100 帧时正常稳定运行

**增量垃圾回收**：`IncrementalPurgeGarbage(true, FMath::Max(0.002f, RemainTime))` 利用帧剩余时间跑 GC，避免单帧卡顿。

## 配套代码

| 文件 | 路径 |
|------|------|
| XGSlateSample.cpp (主入口) | [code/013_独立程序源码/XGSlateSample/Private/XGSlateSample.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/013_独立程序源码/XGSlateSample/Private/XGSlateSample.cpp) |
| XGSlateSample.Build.cs | [code/013_独立程序源码/XGSlateSample/XGSlateSample.Build.cs](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/013_独立程序源码/XGSlateSample/XGSlateSample.Build.cs) |
| XGSlateSample.Target.cs | [code/013_独立程序源码/XGSlateSample/XGSlateSample.Target.cs](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/013_独立程序源码/XGSlateSample/XGSlateSample.Target.cs) |
