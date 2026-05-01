# TArray 排序

## 三种排序方法

| 函数 | 算法 | 稳定性 | 特点 |
|------|------|--------|------|
| `Sort()` / `QuickSort()` | QuickSort | 不稳定 | 默认排序，速度最快 |
| `HeapSort()` | HeapSort | 不稳定 | 基于堆排序 |
| `StableSort()` | MergeSort | **稳定** | 相等元素保持原顺序 |

## 基本使用

```cpp
TArray<int32> Arr = {5, 3, 1, 4, 2};

Arr.Sort();          // {1, 2, 3, 4, 5}
Arr.HeapSort();      // {1, 2, 3, 4, 5}
Arr.StableSort();    // {1, 2, 3, 4, 5}
```

## 默认比较行为

- 使用 `operator<` 进行升序排列
- 对于 `FString`，使用**字典序**比较（非长度比较）
- 对于**原始指针**，自动解引用后比较（不需要手动解引用）

```cpp
TArray<FString> StrArr = {TEXT("Banana"), TEXT("Apple"), TEXT("Cherry")};
StrArr.Sort();  // {Apple, Banana, Cherry}——字典序

TArray<FString> StrArr2 = {TEXT("A"), TEXT("B"), TEXT("AA")};
StrArr2.Sort();  // {A, AA, B}——字典序，非长度序
```

## 结构体默认排序

结构体定义了 `operator<` 后，可以直接使用无参数的 `Sort()`：

```cpp
USTRUCT()
struct FMyStruct
{
    int32 ID;
    int32 Money;

    bool operator<(const FMyStruct& Other) const
    {
        return ID < Other.ID;  // 按 ID 升序
    }
};

TArray<FMyStruct> Arr;
Arr.Sort();  // 使用 operator< 排序
```

没有 `operator<` 的结构体必须传入二元谓词。

## 自定义排序

自定义排序（升序/降序/按特定字段）使用二元谓词，见 [predicate.md](predicate.md)。

常见的自定义排序——按字符串长度排列：

```cpp
StrArr.Sort([](const FString& A, const FString& B)
{
    return A.Len() < B.Len();  // 按长度升序
});
```

> **代码位置**：[XGArrayActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/004_Array/XGArrayActor.h) — 结构体 `FXGSortStructInfo`（含 `operator<`）；[XGArrayActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/004_Array/XGArrayActor.cpp) — 函数 `XGSortArray1~4()`
