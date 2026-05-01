# CountCode — 分帧状态机设计

## 概述

CountCode 是本章的核心案例，演示了如何将一个**大规模任务（遍历整个代码库统计行数）**通过**分帧状态机**拆分为每帧执行一个子任务，从而避免 UI 卡死。这是独立程序效率优化的关键模式。

## 状态机枚举

```cpp
UENUM()
enum class ECountCodeStatus : uint8
{
    Idle,              // 空闲（等待激活）
    SearchDirectroy,   // 阶段1：逐帧遍历目录
    SearchFile,        // 阶段2：逐帧筛选文件
    CountCode,         // 阶段3：逐帧读取文件行数
    Finish,            // 汇总完成
    Max,               // 保留字段
};
```

## 类继承关系

```
FXGSSPTickObject (抽象接口：virtual Tick)
    ↑
FXGSSPCountCode : public FXGSSPTickObject, public TSharedFromThis<FXGSSPCountCode>
```

- 继承 `FXGSSPTickObject` → 可被 Core 管理器 Tick
- 继承 `TSharedFromThis` → 可生成弱指针注册到管理器

## 构造函数设计

```cpp
FXGSSPCountCode(
    TSharedRef<STextBlock> InFileDirectory,   // 路径显示控件（UI）
    TSharedRef<SScrollBox> InLogBox            // 日志滚动槽（UI）
);
```

构造函数接收两个 Slate 控件引用，以便在计算过程中实时更新 UI（显示当前处理路径、输出日志）。

### 关键成员变量

| 变量 | 类型 | 用途 |
|------|------|------|
| `CountCodeStatus` | `ECountCodeStatus` | 当前阶段状态 |
| `SearchedDirectories` | `TArray<FString>` | 一阶段待遍历的目录队列 |
| `SearchedFiles` | `TArray<FString>` | 二阶段待筛选的文件队列 |
| `CountedFiles` | `TArray<FString>` | 三阶段待计数的文件队列 |
| `CodeNum` | `int32` | 累计代码行数 |
| `StartTime` / `*Time` | `FDateTime` | 各阶段时间统计 |

## 激活入口

按钮点击触发 `CountCodes()`：

```cpp
FReply FXGSSPCountCode::CountCodes()
{
    // 防止重复激活：如果已在工作中，打印警告
    if (CountCodeStatus != ECountCodeStatus::Idle)
    {
        PrintToWarning(FString::Printf(TEXT("CountCode is Working, Status: %s"),
            *StaticEnum<ECountCodeStatus>()->GetNameStringByValue(
                (int64)CountCodeStatus)));
        return FReply::Handled();
    }

    // 打开文件夹对话框 → 初始化 → 进入 SearchDirectroy 状态
    // ...
    CountCodeStatus = ECountCodeStatus::SearchDirectroy;
    StartTime = FDateTime::Now();
    CodeNum = 0;
    SearchedDirectories.Add(SelectedFolderPath);
}
```

**`StaticEnum<>()->GetNameStringByValue()`**：利用 UE 反射将枚举值转为字符串，用于日志输出。

## UI 日志输出

CountCode 不使用 `UE_LOG`，而是将日志输出到 Slate UI 的滚动框中：

```cpp
void FXGSSPCountCode::PrintToDisplay(const FString& InStr)
{
    // 如果日志超过 1000 条，清空重新开始
    if (LogNum > 1000)
    {
        LogBox->ClearChildren();
        LogNum = 0;
    }

    // 创建文本控件添加到日志滚动框
    LogBox->AddSlot()
    [
        SNew(STextBlock).Text(FText::FromString(InStr))
    ];

    LogNum++;
    LogBox->ScrollToEnd();  // 自动滚到底部
}
```

**PrintToWarning** 与 PrintToDisplay 类似，但将文本颜色设为红色以示警告。

## 生命周期管理

```
SXGSSPCoundCodeBox (Slate控件)
    ├── 持有: TSharedPtr<FXGSSPCountCode> CountCode
    └── 构造时: CountCode = MakeShareable(new FXGSSPCountCode(...));
         CountCode->AddToManage();  // 注册到 FXGSSPCore

当 Slate Tab 关闭时:
    → SXGSSPCoundCodeBox 析构
    → CountCode 智能指针引用计数归零 → 析构
    → Core 管理器的 Tick 中检测弱指针失效 → 自动移除
```

## 配套代码

| 文件 | 路径 |
|------|------|
| XGSSPCountCode.h | [code/013_独立程序源码/XGSlateSample/Private/Core/XGSSPCountCode.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/013_独立程序源码/XGSlateSample/Private/Core/XGSSPCountCode.h) |
| SXGSSPCountCodeBox.h | [code/013_独立程序源码/XGSlateSample/Private/Slate/SXGSSPCountCodeBox.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/013_独立程序源码/XGSlateSample/Private/Slate/SXGSSPCountCodeBox.h) |
