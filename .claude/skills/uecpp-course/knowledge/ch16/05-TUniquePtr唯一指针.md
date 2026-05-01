# TUniquePtr 唯一指针

TUniquePtr 是**独占所有权**智能指针，不支持复制，只能移动。性能最优（无引用计数开销）。

## 创建方式

```cpp
TUniquePtr<FSmartPtrStruct> Ptr = MakeUnique<FSmartPtrStruct>();
```

`MakeUnique` 是推荐的创建方式。

## 核心特性

### 不能复制

```cpp
TUniquePtr<FSmartPtrStruct> Ptr = MakeUnique<FSmartPtrStruct>();
// TUniquePtr<FSmartPtrStruct> Copy = Ptr;  // 编译错误
```

复制操作被删除（`= delete`），编译期防止误用。

### 可以移动转移所有权

```cpp
TUniquePtr<FSmartPtrStruct> Ptr = MakeUnique<FSmartPtrStruct>();
TUniquePtr<FSmartPtrStruct> Moved = MoveTemp(Ptr);
// MoveTemp 后 Ptr 为 nullptr，Moved 持有所有权
```

转移后源指针指向 nullptr，所有权完全转移给目标。

### Reset / Get 方法

```cpp
Ptr.Reset();     // 释放对象
FSmartPtrStruct* Raw = Ptr.Get();  // 获取原始指针（不转移所有权）
```

## 用途

- 单个资源独占（如文件句柄、内存缓冲区）
- 类内部成员管理
- 不需要共享的临时对象

## 与 TSharedPtr 对比

| 维度 | TUniquePtr | TSharedPtr |
|------|-----------|------------|
| 所有权 | 独占 | 共享 |
| 复制 | 禁止 | 允许 |
| 移动 | 允许 | 允许 |
| 引用计数 | 无 | 有（强引用） |
| 性能 | 最优，无开销 | 有计数开销 |
| 使用场景 | 无需共享的资源 | 需要共享生命周期的对象 |

## 代码引用

- [XGSmartPtrActor.cpp 第 341~349 行 MyUniquePtr](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/019_SmartPointer/XGSmartPtrActor.cpp#L341-L349)
