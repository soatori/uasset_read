# TSharedRef 共享引用

TSharedRef 是**不可为空**的共享引用，内部保证始终持有有效对象。与 TSharedPtr 相比，TSharedRef 在设计上消除了空指针检查负担。

## 与 TSharedPtr 的核心差异

| 维度 | TSharedRef | TSharedPtr |
|------|-----------|------------|
| 可为空 | **否** | 是 |
| 默认构造 | 不可编译 | 指向 nullptr |
| 赋值为 nullptr | 不可编译 | Reset 语义 |
| 空检查 | 不需要 | IsValid / operator bool |
| 引用计数 | 共享 | 共享 |

## 创建方式

```cpp
// 推荐
TSharedRef<FSmartPtrStruct> Ref = MakeShared<FSmartPtrStruct>();

// 错误：不能默认构造
// TSharedRef<FSmartPtrStruct> UnassignedRef;

// 错误：不能赋值为 nullptr
// TSharedRef<FSmartPtrStruct> NullRef = nullptr;
// TSharedRef<FSmartPtrStruct> NullRef = NULL;  // 编译但运行时断言
```

必须使用 `MakeShared` 或从已存在的 TSharedRef 复制创建。

## 隐式转换为 TSharedPtr

```cpp
TSharedRef<FSmartPtrStruct> Ref(new FSmartPtrStruct(456));
TSharedPtr<FSmartPtrStruct> Ptr = Ref;  // 隐式转换，引用计数 +1
```

TSharedRef **可以**隐式转换为 TSharedPtr，这是安全操作。

## 从 TSharedPtr 转换为 TSharedRef

```cpp
TSharedRef<FSmartPtrStruct> Ref(new FSmartPtrStruct(456));
TSharedPtr<FSmartPtrStruct> Ptr = Ref;

if (Ptr.IsValid())
{
    TSharedRef<FSmartPtrStruct> BackRef = Ptr.ToSharedRef();
}

Ptr.Reset();  // Ptr 变为 nullptr
// TSharedRef<FSmartPtrStruct> CrashRef = Ptr.ToSharedRef();  // 运行时会断言崩溃
```

从 TSharedPtr 到 TSharedRef 使用 `ToSharedRef()`，必须先确保 TSharedPtr 非空。若 TSharedPtr 已指向 nullptr 却调用 `ToSharedRef()`，运行时会断言崩溃。

## 赋值与重新赋值

```cpp
TSharedRef<FSmartPtrStruct> RefA = MakeShared<FSmartPtrStruct>();
TSharedRef<FSmartPtrStruct> RefB = MakeShared<FSmartPtrStruct>();

// 可以重新赋值指向另一个对象
RefB = RefA;  // RefB 现在指向 RefA 管理的对象
// 此时 RefB 原对象强引用 -1，RefA 所指对象强引用 +1
```

TSharedRef 不可重置，但可以重新赋值指向另一个已存在的共享引用。

## 相等性比较

```cpp
TSharedRef<FSmartPtrStruct> RefA = MakeShared<FSmartPtrStruct>();
TSharedRef<FSmartPtrStruct> RefB = RefA;

if (RefA == RefB) { UE_LOG(LogTemp, Warning, TEXT("相等")); }

TSharedRef<FSmartPtrStruct> RefC = MakeShared<FSmartPtrStruct>();
if (RefC != RefA) { UE_LOG(LogTemp, Warning, TEXT("不相等")); }
```

比较的也是指针地址。

## 适用场景

- 函数参数中要求对象一定存在时
- 类成员中持有确保不会为空的引用
- 工厂方法返回值保证非空

## 代码引用

- [XGSmartPtrActor.cpp 第 203~238 行 MyRef](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/019_SmartPointer/XGSmartPtrActor.cpp#L203-L238)
