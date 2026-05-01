# TArray 详解

## 基本声明

```cpp
TArray<int32> IntArray;
TArray<FString> StrArray;
TArray<TSharedPtr<FMyType>> PtrArray;
```

## 创建与初始化

```cpp
TArray<int32> Arr = {1, 2, 3, 4};       // 初始值设定项列表
Arr.Init(0, 10);                          // 填充 10 个 0
TArray<int32> Arr2(Arr);                 // 拷贝构造
```

## 添加元素

| API | 说明 | 性能 |
|-----|------|------|
| `Add(Val)` | 拷贝/移动元素到末尾 | O(1) |
| `Emplace(Args...)` | 原地构造（避免拷贝） | O(1)，推荐 |
| `Append(Others)` | 合并另一个容器 | O(n) |
| `Insert(Val, Index)` | 插入到指定位置 | O(n) |
| `AddUnique(Val)` | 不重复时添加 | O(n) |
| `AddDefaulted(N)` | 添加 N 个默认构造元素 | O(n) |

```cpp
// Add vs Emplace 对比
Arr.Add(FString(TEXT("hello")));      // 临时构造 + 拷贝/移动
Arr.Emplace(TEXT("hello"));            // 直接原地构造
```

## 访问元素

```cpp
int32 Val = Arr[0];           // 直接索引（越界崩溃）
int32 Val = Arr.Last();       // 末尾元素
int32 Val = Arr.Top();        // 同 Last
int32* Data = Arr.GetData();  // 底层指针
int32 Num = Arr.Num();        // 当前元素数量
```

## 查找

```cpp
bool bContains = Arr.Contains(42);
int32 Index = Arr.Find(42);               // 返回索引，未找到为 INDEX_NONE
int32* Ptr = Arr.FindByPredicate(Pred);   // 返回指针
TArray<int32> Filtered = Arr.FilterByPredicate(Pred);
```

## 排序

```cpp
Arr.Sort();                    // 默认升序（需 operator<）
Arr.Sort(Pred);                // 自定义比较器
Arr.HeapSort();                // 堆排序
Arr.StableSort();              // 稳定排序（相等元素保持原序）
```

## 移除

```cpp
Arr.Remove(Val);               // 移除所有等于 Val 的元素
Arr.RemoveSingle(Val);         // 仅移除第一个
Arr.RemoveAt(Index);           // 按索引移除
Arr.RemoveAll(Pred);           // 按谓词移除
Arr.RemoveAtSwap(Index);       // 与末尾交换后移除（不保序，O(1)）
Arr.Empty();                   // 清空并释放内存
Arr.Reset();                   // 清空但不释放内存
Arr.Shrink();                  // 释放多余容量
```

## 迭代中安全移除

```cpp
// 方法一：反向遍历
for (int32 i = Arr.Num() - 1; i >= 0; i--)
{
    if (Arr[i] == 42) Arr.RemoveAt(i);
}

// 方法二：谓词移除
Arr.RemoveAll([](int32 Val) { return Val == 42; });
```

## 内存模型

```
容量 = Num() + Slack()
首次扩容: 4 个元素
之后每次扩容: +16 个元素
```

| API | 行为 |
|-----|------|
| `Max()` | 当前已分配容量 |
| `Slack()` | 未使用的容量 |
| `Reserve(N)` | 预分配 N 个元素空间 |
| `Empty()` | 设 Num=0，释放内存 |
| `Reset()` | 设 Num=0，保留内存 |
| `Shrink()` | 缩减到实际大小 |

```cpp
Arr.Reserve(100);        // 预分配 100 个元素
Arr.AddDefaulted(100);   // 不触发重新分配
```

## 堆操作

```cpp
Arr.Heapify();            // 构建最大堆
Arr.HeapPush(Val);        // 入堆
Arr.HeapPop();            // 弹出最大元素
Arr.HeapRemoveTop();      // 移除堆顶
int32 Top = Arr.HeapTop();// 查看堆顶
```

## 运算符

```cpp
TArray<int32> B = Arr;        // 拷贝赋值
Arr += {5, 6, 7};             // 连接
bool bEqual = (Arr == B);     // 逐元素比较
```

## `operator==` 重载要求

用于 TArray 容器的自定义类型必须重载 `operator==`：

```cpp
FMyStruct& operator==(const FMyStruct& Other) const
{
    return ID == Other.ID && Name == Other.Name;
}
```

## 性能建议

| 场景 | 建议 |
|------|------|
| 已知大小 | 用 `Reserve()` 预分配 |
| 频繁末尾添加 | Add/Emplace（O(1)） |
| 频繁中间插入 | 考虑反向操作 + Add，或换容器 |
| 大量元素查找 | 排序后二分查找，或换 TMap/TSet |
| 反复 Clear | 用 `Reset()` 而非 `Empty()` 避免反复分配 |
| 传递参数 | 用 `const TArray<T>&` 而非值传递 |

## 代码入口

[004_Array/XGArrayActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/004_Array/XGArrayActor.h)
[004_Array/XGArrayActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/004_Array/XGArrayActor.cpp)
