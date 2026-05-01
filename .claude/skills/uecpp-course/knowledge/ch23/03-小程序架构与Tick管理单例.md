# 小程序架构与Tick管理单例

## 概述

本章 Slate 独立程序采用类似 MVC 的三层架构，并通过自实现的单例管理器 + TickObject 接口模式来管理业务对象的每帧更新。

## 三层架构

讲师用"皮肉骨"比喻程序的三层：

| 层 | 比喻 | 目录 | 职责 |
|---|------|------|------|
| Slate 层 (S) | 皮 | `Slate/SXGSSP*.h` | UI 布局、用户交互、事件绑定 |
| 核心管理层 (Core) | 肉 | `Core/XGSSPCore.h` | 单例管理、Tick 调度、中转协调 |
| 业务逻辑层 (F) | 骨 | `Core/XGSSPCountCode.h` | 实际计算逻辑、文件操作、数据状态 |

### Slate 层

- 继承 `SCompoundWidget`
- 只负责 UI 布局和事件绑定
- 不直接写业务逻辑（好的实践是绑定到中间层）

### 核心管理层 — FXGSSPCore

单例模式的管理器，模拟了 GameInstanceSubsystem 的功能（独立程序无法使用 Engine 模块的 Subsystem）：

```cpp
struct FXGSSPCore
{
    static FXGSSPCore* Get();     // 单例获取（主线程安全）
    static void Destory();        // 单例销毁
    void Init();                  // 初始化
    void Tick(float DeltaTime);   // 每帧 Tick

    void AddTickObject(TWeakPtr<FXGSSPTickObject> InTickObject);
    void RemoveTickObject(TWeakPtr<FXGSSPTickObject> InTickObject);

private:
    TArray<TWeakPtr<FXGSSPTickObject>> SlateProgramTickObjects;
    static FXGSSPCore* XGSSPCoreInstance;
};
```

配套代码详见 [XGSSPCore.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/013_独立程序源码/XGSlateSample/Private/Core/XGSSPCore.h) 和 [XGSSPCore.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/013_独立程序源码/XGSlateSample/Private/Core/XGSSPCore.cpp)。

### 生命周期

```
外层 while 循环
  ├── Setup 阶段: FXGSSPCore::Get() → Init()
  ├── Loop 阶段:   FXGSSPCore::Get()->Tick(DeltaTime)
  └── Teardown 阶段: FXGSSPCore::Destory()
```

## TickObject 接口设计

### FXGSSPTickObject — 纯虚接口

```cpp
struct FXGSSPTickObject
{
    virtual void Tick(float DeltaTime) = 0;
};
```

所有需要每帧更新的业务类继承此接口并实现 `Tick` 方法。

### 注册/反注册机制

使用 `TWeakPtr` 管理 TickObject 的生命周期：

```cpp
void FXGSSPCore::AddTickObject(TWeakPtr<FXGSSPTickObject> InTickObject)
{
    if (InTickObject.IsValid())
        SlateProgramTickObjects.AddUnique(InTickObject);
}
```

**使用弱指针的原因**：TickObject 的实际持有者是 Slate 控件（`SXGSSPCoundCodeBox`），Slate 销毁时自动释放 TickObject。Core 管理器不应干预其生命周期——它仅在对象仍然有效时才调用 Tick。

### Tick 循环中的清理

每帧首先移除已失效的弱指针：

```cpp
void FXGSSPCore::Tick(float DeltaTime)
{
    // 移除已无效的 TickObject（其持有者已被销毁）
    SlateProgramTickObjects.RemoveAll([](TWeakPtr<FXGSSPTickObject> Ptr) {
        return !Ptr.IsValid();
    });

    // 依次 Tick 所有有效对象
    for (auto& Tmp : SlateProgramTickObjects)
    {
        if (Tmp.IsValid())
            Tmp.Pin().Get()->Tick(DeltaTime);
    }
}
```

## 业务对象注册示例

当 Slate 控件构造时，创建业务对象并注册到 Core：

```cpp
// 在 SXGSSPCoundCodeBox 中
CountCode = MakeShareable(new FXGSSPCountCode(InFileDirectory, InLogBox));
CountCode->AddToManage();  // 内部调用 FXGSSPCore::Get()->AddTickObject(...)
```

`AddToManage` 通过 `TSharedFromThis` 将自身作为弱指针注册：

```cpp
void FXGSSPCountCode::AddToManage()
{
    FXGSSPCore::Get()->AddTickObject(this->AsShared());
}
```

## Util 工具类

`FXGSSPUtil` 提供通用的路径持久化功能，独立于具体业务：

```cpp
struct FXGSSPUtil
{
    static FString GetLastUsedCheckDirectory();
    static bool SetLastUsedCheckDirectory(const FString&);
    static FString GetLastModifyNameDirectory();
    static bool SetLastModifyNameDirectory(const FString&);
    static FString GetLastCountCodeDirectory();
    static bool SetLastCountCodeDirectory(const FString&);
};
```

配套代码详见 [XGSSPUtil.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/013_独立程序源码/XGSlateSample/Private/Util/XGSSPUtil.h)。

## 与前序章节的关联

| 知识点 | 先修章节 |
|--------|----------|
| 智能指针 TSharedPtr/TWeakPtr/TSharedFromThis | 第16章 智能指针 |
| 单例模式、Subsystem | 第13章 编程子系统 |
| ControlFlows 任务管理模式 | 第18章 ControlFlows |
