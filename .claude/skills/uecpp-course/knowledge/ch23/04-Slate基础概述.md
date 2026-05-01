# Slate 基础概述

## 概述

Slate 是 UE 的底层 UI 框架，UMG 的底层就是 Slate。Slate 使用纯 C++ 声明式语法构建 UI，通过**链式编程**和**槽位系统**组织控件层级。

## Slate 类声明

所有 Slate 控件类必须以 `S` 前缀命名，继承自相应的基类：

```cpp
class SXGSSPModifyName : public SCompoundWidget
{
public:
    SLATE_BEGIN_ARGS(SXGSSPModifyName) {}
    SLATE_END_ARGS()

    void Construct(const FArguments& InArgs);
};
```

- `SLATE_BEGIN_ARGS` / `SLATE_END_ARGS`：声明 Slate 类的构造参数槽，宏自动生成 `FArguments` 内部类
- `Construct(const FArguments& InArgs)`：构造函数入口，在这里构建 UI 布局

## Widget 层级体系

| 基类 | 说明 | 可嵌套子控件数 |
|------|------|--------------|
| `SCompoundWidget` | 组合控件基类，有一个 `ChildSlot` | 1 个 |
| `SPanel` | 面板基类，可容纳多个子控件 | 多个 |
| `SLeafWidget` | 叶子控件基类，不能再嵌套子控件 | 0 个 |

### 常用容器控件

| 控件 | 继承链 | 用途 |
|------|--------|------|
| `SCanvas` | `SPanel` | 任意位置放置控件 |
| `SVerticalBox` | `SPanel` | 垂直排列子控件 |
| `SHorizontalBox` | `SPanel` | 水平排列子控件 |
| `SBorder` | `SCompoundWidget` | 单子控件 + 边框 |
| `SScrollBox` | `SPanel` | 可滚动列表 |

### 常用叶子控件

| 控件 | 用途 |
|------|------|
| `STextBlock` | 显示文本 |
| `SEditableTextBox` | 可编辑文本输入框 |
| `SButton` | 按钮，绑定点击事件 |
| `SImage` | 显示图片 |

## 链式编程 (Chain-style Programming)

Slate 控件的属性和层级关系通过链式调用设置：

```cpp
SNew(SButton)
    .Text(LOCTEXT("BtnLabel", "打开指定文件夹"))
    .HAlign(HAlign_Center)
    .VAlign(VAlign_Center)
    .OnClicked(this, &MyClass::OnButtonClicked);
```

每个属性设置方法返回自身引用，允许连续 `.` 调用。这是 Slate 最核心的编程范式。

### SNew vs SAssignNew

| 宏 | 用途 | 返回值 |
|---|------|--------|
| `SNew(WidgetType)` | 创建控件，不持有智能指针 | 直接用于链式嵌套 |
| `SAssignNew(PtrVar, WidgetType)` | 创建控件并赋值给智能指针变量 | 可后续在代码中引用该控件 |

```cpp
// 创建并持有引用，便于后续修改
TSharedPtr<STextBlock> FileDirectory;
SAssignNew(FileDirectory, STextBlock)
    .Text(FText::FromString(TEXT("C:\\")));

// 创建后丢弃，在链式嵌套中使用
SNew(STextBlock).Text(FText::FromString(TEXT("Hello")));
```

## 槽位系统 (Slot System)

Slate 通过嵌套的槽位定义控件层级。每个容器控件有不同的槽位机制：

### 单子控件：ChildSlot

`SCompoundWidget` 只有一个 `ChildSlot`：

```cpp
ChildSlot
[
    SNew(SVerticalBox)
    + SVerticalBox::Slot()
    .FillHeight(0.1f)   // 高度占比10%
    [
        SNew(STextBlock).Text(...)
    ]
    + SVerticalBox::Slot()
    .FillHeight(0.9f)
    [
        SNew(SScrollBox)
    ]
];
```

### 多面板：+ 添加 Slot

```cpp
SNew(SVerticalBox)
    + SVerticalBox::Slot().FillHeight(0.2f)
    [
        SNew(SHorizontalBox)
        + SHorizontalBox::Slot().FillWidth(0.8f)  // 80% 宽度
        [
            SNew(SButton)
        ]
        + SHorizontalBox::Slot().FillWidth(0.2f)
        [
            SNew(STextBlock)
        ]
    ]
    + SVerticalBox::Slot().FillHeight(0.8f)
    [
        SNew(SScrollBox)
    ];
```

## Button 事件绑定

SButton 的点击事件通过 `OnClicked` 绑定，函数签名固定为：

```cpp
FReply OnButtonClicked();  // 无参，返回 FReply::Handled()
```

绑定方式有三种：

| 方式 | 示例 |
|------|------|
| Lambda 绑定 | `.OnClicked_Lambda([this]() { return FReply::Handled(); })` |
| 成员函数绑定 | `.OnClicked(this, &SMyWidget::OnClick)` |
| 智能指针绑定 | `.OnClicked_SP(SharedPtr, &FMyStruct::OnClick)` |

### Lambda 绑定示例

```cpp
auto OnOpenFolder = [this]() -> FReply
{
    // 打开文件夹对话框的逻辑
    return FReply::Handled();
};

SNew(SButton)
    .OnClicked_Lambda(OnOpenFolder);
```

**注意**：Lambda 必须返回 `FReply::Handled()`，不能有"不返回"的代码路径。

## 布局系统

### Tab 管理系统

独立程序使用 `FGlobalTabmanager` 管理多个 Dock Tab：

```cpp
// 注册 Tab
FGlobalTabmanager::Get()->RegisterNomadTabSpawner("ModifyNameTab", 
    FOnSpawnTab::CreateLambda(SpawnModifyNameBox))
    .SetDisplayName(LOCTEXT("ModifyNameTab", "ModifyName"));

// 定义布局
TSharedRef<FTabManager::FLayout> Layout = FTabManager::NewLayout("MyLayout")
    ->AddArea(
        FTabManager::NewArea(1280, 720)
        ->SetWindow(FVector2D(420, 10), false)  // 窗口位置
        ->Split(FTabManager::NewStack()
            ->AddTab("ModifyNameTab", ETabState::OpenedTab)
            ->AddTab("CountCodeTab", ETabState::OpenedTab)
            ->SetForegroundTab(FName("CountCodeTab"))
        )
    );

FGlobalTabmanager::Get()->RestoreFrom(Layout, TSharedPtr<SWindow>());
```

`SetWindow(FVector2D, bool)` 参数：(屏幕位置, 是否最大化)。

配套代码详见 [XGSlateSample.cpp:L74-L128](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/013_独立程序源码/XGSlateSample/Private/XGSlateSample.cpp#L74-L128)。

## 配套代码

| 文件 | 路径 |
|------|------|
| SXGSSPModifyName.h | [code/013_独立程序源码/XGSlateSample/Private/Slate/SXGSSPModifyName.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/013_独立程序源码/XGSlateSample/Private/Slate/SXGSSPModifyName.h) |
| SXGSSPCountCodeBox.h | [code/013_独立程序源码/XGSlateSample/Private/Slate/SXGSSPCountCodeBox.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/013_独立程序源码/XGSlateSample/Private/Slate/SXGSSPCountCodeBox.h) |
