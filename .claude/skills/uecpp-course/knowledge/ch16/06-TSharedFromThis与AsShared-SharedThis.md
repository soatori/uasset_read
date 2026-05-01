# TSharedFromThis 与 AsShared / SharedThis

`TSharedFromThis` 是一个 CRTP（奇异递归模板）基类，允许对象在被智能指针管理时获取指向自身的 `TSharedRef` 或 `TSharedPtr`。

## 继承方式

```cpp
struct FSmartPtrStruct : public TSharedFromThis<FSmartPtrStruct>
{
    int32 aa = 10;

    void PrintAA()
    {
        UE_LOG(LogTemp, Warning, TEXT("aa:%d"), aa);
    }

    FSmartPtrStruct()
    {
        UE_LOG(LogTemp, Warning, TEXT("创建 - FSmartPtrStruct"));
    }

    ~FSmartPtrStruct()
    {
        UE_LOG(LogTemp, Warning, TEXT("析构 - FSmartPtrStruct"));
    }
};
```

## AsShared

`AsShared()` 返回一个 `TSharedRef<Self>`。前提是对象已经被智能指针管理（即内部引用计数控制块已初始化）。

```cpp
class FMyBaseClass : public TSharedFromThis<FMyBaseClass>
{
public:
    TSharedRef<FMyBaseClass> AsSharedRef()
    {
        return AsShared();  // 返回指向自身的 TSharedRef
    }
};
```

## SharedThis

`SharedThis(this)` 是模板函数，等效于 `AsShared()`，但在派生类中使用时更清晰：

```cpp
class FMyDerivedClass : public FMyBaseClass
{
public:
    void DoSomething()
    {
        TSharedRef<FMyDerivedClass> SelfRef = SharedThis(this);
        // 在派生类中获取指向自身的 TSharedRef
    }
};
```

## AsShared vs SharedThis

| 维度 | AsShared() | SharedThis(this) |
|------|-----------|-----------------|
| 返回类型 | `TSharedRef<Self>` | `TSharedRef<Self>` |
| 用法 | 成员函数调用 | 模板函数调用 |
| 派生类 | 返回基类引用 | 返回派生类引用 |
| 适用 | 基类方法中获取自身 | 派生类方法中获取自身 |

**关键区别**：在派生类中，`AsShared()` 返回的是基类 `TSharedRef`，而 `SharedThis(this)` 通过模板推导返回派生类 `TSharedRef`。

## 注意事项

- 对象必须已经被 TSharedPtr 或 TSharedRef 管理，才能调用 AsShared / SharedThis
- 未被智能指针管理的栈对象或原始指针调用 AsShared 会导致未定义行为或崩溃
- `FSmartPtrStruct` 的结构体析构函数日志用于验证引用计数归零时的析构触发

## 代码引用

- [XGSmartPtrActor.h 第 10~42 行](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/019_SmartPointer/XGSmartPtrActor.h#L10-L42) — FSmartPtrStruct 定义及 TSharedFromThis 继承
