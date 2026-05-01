# TSharedPtr 共享指针

TSharedPtr 是 UE 最常用的共享所有权智能指针，通过强引用计数管理对象生命周期。

## 创建方式

### MakeShared（推荐）

```cpp
TSharedPtr<FSmartPtrStruct> Ptr = MakeShared<FSmartPtrStruct>();
// 带构造参数
TSharedPtr<FSmartPtrStruct> PtrWithArgs = MakeShared<FSmartPtrStruct>(123);
```

一次分配，控制块和数据对象在同一内存块。性能优于 `new + MakeShareable`。

### MakeShareable

```cpp
TSharedPtr<FSmartPtrStruct> Ptr = MakeShareable(new FSmartPtrStruct());
// 带构造参数
TSharedPtr<FSmartPtrStruct> PtrWithArgs = MakeShareable(new FSmartPtrStruct(123));
```

两次分配，先 `new` 对象再包装智能指针。

### 空声明

```cpp
TSharedPtr<FSmartPtrStruct> EmptyPointer;  // 引用 nullptr
```

## 引用计数操作

```cpp
TSharedPtr<FSmartPtrStruct> PtrA = MakeShared<FSmartPtrStruct>(123);
TSharedPtr<FSmartPtrStruct> PtrB = PtrA;  // 复制，强引用 +1
```

复制操作增加强引用计数，超出作用域时析构函数减少强引用计数。

## Reset 操作

```cpp
TSharedPtr<FSmartPtrStruct> Ptr(new FSmartPtrStruct(1111));
Ptr.Reset();              // 释放引用，强引用 -1
// 等效
Ptr = nullptr;             // 也是释放引用
```

Reset 后若强引用计数归零，对象立即析构。

## Move 操作

```cpp
TSharedPtr<FSmartPtrStruct> PtrA(new FSmartPtrStruct(1111));
TSharedPtr<FSmartPtrStruct> PtrB;

PtrB = MoveTemp(PtrA);              // 转移所有权，PtrA 变为 nullptr
PtrA = MoveTempIfPossible(PtrB);    // 条件转移
```

`MoveTemp` 无条件转移所有权，源指针指向 nullptr。
`MoveTempIfPossible` 在目标支持移动时转移。

## 相等性比较

```cpp
TSharedPtr<FSmartPtrStruct> NodeA, NodeB;

if (NodeA == NodeB) { /* 指向同一对象 */ }
```

比较的是指针值（地址），而非对象内容。

## 空检查的三种方式

```cpp
if (NodeA.IsValid())    { /* 检查内部指针是否为 nullptr */ }
if (NodeA)              { /* operator bool，等效于 IsValid */ }
if (NodeA.Get() != nullptr) { /* Get() 返回原始指针 */ }
```

三种方式语义等价，`operator bool` 写法最简洁。

## 解引用方式

```cpp
if (NodeB)
{
    NodeB->PrintAA();     // operator->
    NodeB.Get()->PrintAA(); // Get() → 原始指针 →
    (*NodeB).PrintAA();   // operator*
}
```

三种方式等效，`->` 最常用。

## 自定义删除器

```cpp
TSharedPtr<FSmartPtrStruct> Ptr(
    new FSmartPtrStruct(),
    [](FSmartPtrStruct* Obj) {
        UE_LOG(LogTemp, Warning, TEXT("自定义删除器"));
        Obj->aa = 559;
    }
);
```

自定义删除器在对象析构时调用，可用于资源清理、日志记录等扩展操作。注意：自定义删除器只能用 lambda 或函数对象，不能用 `auto` 变量间接传入（UE 智能指针的模板参数不支持类型推导的 lambda 变量）。

## 线程安全模式

```cpp
TSharedPtr<FSmartPtrStruct, ESPMode::ThreadSafe> SafePtr =
    MakeShared<FSmartPtrStruct, ESPMode::ThreadSafe>(998);
```

跨线程共享时使用 `ESPMode::ThreadSafe`。默认 `NotThreadSafe` 性能更高。

## 代码引用

- [XGSmartPtrActor.h 第 45~54 行](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/019_SmartPointer/XGSmartPtrActor.h#L45-L54) — 函数声明
- [XGSmartPtrActor.cpp 第 12~349 行](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/019_SmartPointer/XGSmartPtrActor.cpp#L12-L349) — 完整实现
