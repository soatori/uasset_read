# 结构体相等性判断

## 问题

调用 `Contains()`、`Find()`、`IndexOfByKey()` 时，如果数组元素是自定义结构体，会报错。

## 原因

上述函数依赖 `operator==` 来比较元素是否相等。自定义结构体默认没有此运算符。

## 解决方案

在结构体中重载 `operator==`：

```cpp
USTRUCT(BlueprintType)
struct FMyStruct
{
    GENERATED_BODY()

    UPROPERTY()
    int32 ID;

    UPROPERTY()
    FString Name;

    bool operator==(const FMyStruct& Other) const
    {
        return ID == Other.ID && Name == Other.Name;
    }
};
```

之后 `Contains()`、`Find()`、`IndexOfByKey()` 等依赖相等比较的函数才能正常工作。

## 跨类型 operator==

当需要用一个不同类型的 Key 来查找元素时（如用 int32 ID 查找结构体），可以定义跨类型的 `operator==`：

```cpp
USTRUCT()
struct FMyStruct
{
    int32 ID;
    int32 Money;

    // 成员函数版本：左边是结构体，右边是 int32
    inline bool operator==(const int32& InID)
    {
        return ID == InID;
    }
};

// 全局函数版本：左边是 int32，右边是结构体
inline bool operator==(const int32& InID, const FMyStruct& InStruct)
{
    return InStruct.ID == InID;
}
```

这样 `IndexOfByKey(4)`（用 int32 查找 `TArray<FMyStruct>`）就能正常工作。

## 影响范围

需要 `operator==` 的场景：
- `Contains()`
- `Find()` / `FindLast()`
- `IndexOfByKey()`（当 Key 类型和元素类型相同，或跨类型有重载时）
- `Remove()`（移除所有匹配元素）
- `AddUnique()`（判断元素是否已存在）
- `==` / `!=`（数组整体比较）
- `FindByKey()`（当 Key 类型和元素类型不同但有跨类型 operator== 时）

不需要 `operator==` 的场景：
- `ContainsByPredicate()` / `FindByPredicate()`（使用 Lambda 谓词）
- `RemoveAll()` / `RemoveAllSwap()`（使用谓词）
- `IndexOfByPredicate()`（使用谓词）
- `Sort()` / `HeapSort()` / `StableSort()`（使用 `operator<` 或谓词）

> **代码位置**：[XGArrayActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/004_Array/XGArrayActor.h) — 结构体 `FXGEqualStructInfo`、`FXGFindStructInfo`
