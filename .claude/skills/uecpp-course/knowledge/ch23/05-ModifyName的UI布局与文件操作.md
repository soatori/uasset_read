# ModifyName — UI 布局与文件操作

## 概述

ModifyName Tab 是一个文件批量重命名工具，功能包括：选择文件夹、显示文件列表、添加/移除文件名前缀。本章演示了 Slate 独立程序中 UI 布局、平台对话框、文件遍历和文件移动操作的完整实现。

## UI 布局结构

```
SXGSSPModifyName (SCompoundWidget)
└── SVerticalBox
    ├── Slot(0.1) — 水平框
    │   ├── SButton: "打开指定文件夹"
    │   └── STextBlock: 当前文件夹路径
    └── Slot(0.9) — 水平框
        ├── Slot(0.2) — 垂直框
        │   ├── SEditableTextBox: 输入前缀名
        │   ├── SButton: "添加前缀"
        │   └── SButton: "移除前缀"
        └── Slot(0.8) — SScrollBox: 文件列表显示
```

## 打开文件夹对话框

使用 `FDesktopPlatformModule` 打开系统原生文件夹选择对话框：

### 前提条件

- 在 `Build.cs` 中添加 `"DesktopPlatform"` 依赖
- 包含头文件：`#include "IDesktopPlatform.h"` 和 `#include "DesktopPlatformModule.h"`

### 核心代码

```cpp
IDesktopPlatform* DesktopPlatform = FDesktopPlatformModule::Get();
if (DesktopPlatform)
{
    // 记录上次打开路径，方便下次使用
    FString LastDirectory = FXGSSPUtil::GetLastModifyNameDirectory();

    // 获取父窗口句柄
    void* ParentWindowHandle = FSlateApplication::Get()
        .FindBestParentWindowHandleForDialogs(nullptr);

    // 阻塞式调用系统文件夹对话框
    FString FolderName;
    bool bOpened = DesktopPlatform->OpenDirectoryDialog(
        ParentWindowHandle,       // 父窗口句柄
        TEXT("选择文件夹"),        // 对话框标题
        LastDirectory,            // 默认打开路径
        FolderName                // [输出] 选择的路径
    );

    if (bOpened)
    {
        // 更新 UI 和刷新文件列表
    }
}
```

**关键点**：
- `OpenDirectoryDialog` 是阻塞调用，会卡住当前帧
- `FolderName` 是输出参数（引用传递）
- 使用 `FPaths::GetPath()` 截取路径或通过 `/` 运算符拼接

### 平台抽象层

`FDesktopPlatformModule` 封装了跨平台的桌面 API（Windows/macOS/Linux），不直接调用 Win32 API。头文件路径可能随引擎版本变动：

- 旧版：`Developer/DesktopPlatform/Public/IDesktopPlatform.h`
- 新版（UE 5.4+）：`Developer/DesktopPlatform/Public/DesktopPlatformModule.h`

## 文件遍历

使用 `IFileManager::Get().FindFiles()` 遍历文件夹找文件列表：

```cpp
TArray<FString> FoundFiles;
IFileManager::Get().FindFiles(FoundFiles, *(FolderPath / TEXT("*")), true, false);
//                              输出数组    路径+通配符           找文件  不找文件夹
```

**参数**：
| 参数 | 说明 |
|------|------|
| `*FoundFiles` | 输出：文件名数组 |
| `*(Path / TEXT("*"))` | 搜索路径 + 通配符 |
| `true` | 查找文件 |
| `false` | 不查找文件夹 |

### 刷新 UI 文件列表

打开文件夹后清空旧列表，遍历新文件创建文本框：

```cpp
// 清空滚动槽
FileScrollBox->ClearChildren();

// 遍历文件列表，创建 STextBlock 添加到滚动槽
for (const FString& FileName : FoundFiles)
{
    FileScrollBox->AddSlot()
    [
        SNew(STextBlock).Text(FText::FromString(FileName))
    ];
}
```

`SScrollBox` 的 `AddSlot()` 返回 slot 引用，用于设置槽属性；`ClearChildren()` 清空所有子控件。

## 添加/移除前缀

### 添加前缀

通过 `IFileManager::Get().Move()` 实现文件重命名：

```cpp
// 遍历文件
for (const FString& FileName : FoundFiles)
{
    FString OldPath = FolderPath / FileName;
    FString NewFileName = Prefix + FileName;   // 新文件名 = 前缀 + 原文件名
    FString NewPath = FolderPath / NewFileName;

    bool bMoved = IFileManager::Get().Move(*NewPath, *OldPath);
}
```

`FPaths` 的 `/` 运算符被重载，自动拼接路径。

### 移除前缀

使用 `FString::RemoveFromStart()` 检查并移除前缀：

```cpp
FString NewName = FileName;
if (NewName.RemoveFromStart(Prefix))  // 返回 true 说明成功移除
{
    FString NewPath = FolderPath / NewName;
    IFileManager::Get().Move(*NewPath, *OldPath);
}
```

**注意事项**：
- 所有逻辑写在了 UI 层的构造函数中，导致单一函数过长（>100 行）
- 生产环境应提取到独立业务类，通过 Lambda/代理绑定
- 文件操作在当前帧阻塞执行（非分帧），大量文件时会卡 UI

## 路径持久化

使用 `FXGSSPUtil` 实现"记住上次打开的路径"，采用了 **INI 层级覆盖** 的思路：

```
通用路径 (LastUsedCheckDirectory)
  ├── ModifyName 专用路径 (GetLastModifyNameDirectory) ← 优先使用
  └── CountCode 专用路径 (GetLastCountCodeDirectory)   ← 优先使用
```

**优先级**：子功能路径 > 通用路径 > 默认项目路径。这与引擎的 INI 配置覆盖机制相同。

配套代码详见 [XGSSPUtil.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/013_独立程序源码/XGSlateSample/Private/Util/XGSSPUtil.h)。

## 配套代码

| 文件 | 路径 |
|------|------|
| SXGSSPModifyName.h | [code/013_独立程序源码/XGSlateSample/Private/Slate/SXGSSPModifyName.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/013_独立程序源码/XGSlateSample/Private/Slate/SXGSSPModifyName.h) |
| SXGSSPModifyName.cpp | [code/013_独立程序源码/XGSlateSample/Private/Slate/SXGSSPModifyName.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/013_独立程序源码/XGSlateSample/Private/Slate/SXGSSPModifyName.cpp) |
| XGSSPUtil.h | [code/013_独立程序源码/XGSlateSample/Private/Util/XGSSPUtil.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/013_独立程序源码/XGSlateSample/Private/Util/XGSSPUtil.h) |
