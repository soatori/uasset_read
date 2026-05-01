# TWeakPtr 弱指针与循环引用

TWeakPtr 是**非拥有型**观察指针，不增加强引用计数，不阻止被观察对象析构。核心用途是打破 TSharedPtr/TSharedRef 之间的循环引用。

## Pin 与 IsValid 的区别

```cpp
TSharedRef<FSmartPtrStruct> OwnerRef = MakeShared<FSmartPtrStruct>();
TWeakPtr<FSmartPtrStruct> Observer(OwnerRef);

// IsValid：检查当前时刻对象是否存活
if (Observer.IsValid())
{
    // 即使这里 IsValid 返回 true，也不能保证在下一行执行时对象还存活
}

// Pin：转换为 TSharedPtr，在作用域内保证对象存活性
if (TSharedPtr<FSmartPtrStruct> Locked = Observer.Pin())
{
    // Pin 返回的 TSharedPtr 增加了强引用计数
    // 在此作用域内，对象一定不会被析构
    Locked->PrintAA();
}
```

**Pin()** 返回一个 TSharedPtr，在持有期间强引用 +1，确保对象不会被释放。
**IsValid()** 只做快照检查，不保证后续操作时对象仍存活。

## 使用方式

```cpp
TSharedRef<FSmartPtrStruct> OwnerRef = MakeShared<FSmartPtrStruct>();
TWeakPtr<FSmartPtrStruct> Observer(OwnerRef);

// 拷贝
TWeakPtr<FSmartPtrStruct> Another = Observer;

// 重置
Another = nullptr;     // 赋 nullptr 释放弱引用
Another.Reset();       // 等效

// 有效期内的安全访问
if (TSharedPtr<FSmartPtrStruct> Locked = Observer.Pin())
{
    Locked->PrintAA();
}
```

## 循环引用问题

### 错误写法：TSharedRef 互相引用

```cpp
void AXGSmartPtrActor::MyLoopPtr()
{
    TSharedRef<FSmartPtrStruct> A = MakeShared<FSmartPtrStruct>();
    TSharedRef<FSmartPtrStruct> B = MakeShared<FSmartPtrStruct>();

    A->MyHoldPtr = B;   // 错误：TSharedPtr 互相持有
    B->MyHoldPtr = A;
    // 函数结束后，A 和 B 都不会被析构（内存泄漏）
}
```

结构体定义中的错误写法：

```cpp
// FSmartPtrStruct 内部
TSharedPtr<FSmartPtrStruct> MyHoldPtr = nullptr;  // 错误
```

A 持有 B 的强引用，B 持有 A 的强引用 → 强引用计数永不归零 → 对象永不析构。

### 正确写法：TWeakPtr 打破循环

```cpp
void AXGSmartPtrActor::MyLoopPtr2()
{
    TSharedRef<FSmartPtrStruct> A = MakeShared<FSmartPtrStruct>();
    TSharedRef<FSmartPtrStruct> B = MakeShared<FSmartPtrStruct>();

    A->MyHoldWeakPtr = B;  // 使用 TWeakPtr
    B->MyHoldWeakPtr = A;
}
```

结构体定义中的正确写法：

```cpp
TWeakPtr<FSmartPtrStruct> MyHoldWeakPtr = nullptr;  // 正确
```

A 持有 B 的弱引用，B 持有 A 的弱引用 → 访问时通过 Pin() 临时提升为强引用。

## 注意事项：不能用作 TMap/TSet 的 Key

TWeakPtr 不适合作为 TMap 或 TSet 的键。因为当弱指针所指向的对象被释放后，弱指针变为无效，会影响哈希计算的稳定性。

## 引用计数变化演示

| 操作 | SharedCount（强引用） | WeakCount（弱引用） |
|------|---------------------|-------------------|
| 创建 TSharedRef A | 1 | 0 |
| 创建 TWeakPtr B(A) | 1 | 1 |
| A 析构 | 0 | 1（对象析构，控制块保留） |
| B 析构 | 0 | 0（控制块释放） |

## 代码引用

- [XGSmartPtrActor.cpp 第 240~338 行](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/019_SmartPointer/XGSmartPtrActor.cpp#L240-L338) — TWeakPtr 演示函数
- [XGSmartPtrActor.h 第 27~28 行](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/019_SmartPointer/XGSmartPtrActor.h#L27-L28) — MyHoldPtr 错误与 MyHoldWeakPtr 正确的结构体定义
