# TMap 排序与运算符

TMap 本身是无序容器。排序操作用于在特定场景下（如调试输出）临时获得有序视图。

## KeySort() — 按键排序

`KeySort()` 使用二元谓词（Binary Predicate）对键排序。排序后可通过遍历获得键的有序序列：

```cpp
TMap<int32, FString> FruitMap1;
FruitMap1.Add(7, TEXT("Pineapple"));
FruitMap1.Add(5, TEXT("Mango2"));
FruitMap1.Add(10, TEXT("Grapefruit"));
FruitMap1.Add(1, TEXT("Apple"));

FruitMap1.KeySort([](int32 A, int32 B)
{
    return A > B;  // 按键降序
});
```

## ValueSort() — 按值排序

`ValueSort()` 根据值的内容进行排序：

```cpp
FruitMap1.ValueSort([](const FString& A, const FString& B)
{
    return A.Len() < B.Len();  // 按字符串长度升序
});
```

## 排序特性

**不稳定排序**：排序后相等的元素之间的相对顺序不保证：

```cpp
// 如果有两个元素的值长度相同，它们的相对位置可能变化
// ValueSort 按字符串长度排序后，等长元素的顺序不确定
```

## 指针/引用失效

排序操作会重新排列容器内部元素，导致**排序前获取的所有指针和引用失效**：

```cpp
FString* MyFruit = FruitMap1.Find(10);
if (MyFruit)
{
    *MyFruit += TEXT("M1");   // 排序前安全
}

FruitMap1.KeySort([](int32 A, int32 B) { return A > B; });
// MyFruit 此时已失效 —— 指向的位置已经改变

// *MyFruit += TEXT("M2");   // 未定义行为！
```

排序后需要重新通过 Find() 或 operator[] 获取引用。

## 复制赋值（=）

`=` 运算符对 TMap 执行**深拷贝**。两个 Map 完全独立，互不影响：

```cpp
TMap<int32, FString> FruitMap;
FruitMap.Add(7, TEXT("Pineapple"));
FruitMap.Add(5, TEXT("Mango2"));
FruitMap.Add(1, TEXT("Apple"));

TMap<int32, FString> NewMap = FruitMap;  // 深拷贝

NewMap[5] = TEXT("Apple");    // 只影响 NewMap
NewMap.Remove(1);              // 只影响 NewMap
// FruitMap 保持不变
```

## MoveTemp() — 移动语义

`MoveTemp()` 将源 Map 的内存所有权转移到目标 Map，源 Map 变为空：

```cpp
TMap<int32, FString> NewMap2 = MoveTemp(FruitMap);
// FruitMap 现在为空
// NewMap2 拥有之前 FruitMap 的所有元素
```

## UObject 指针的复制语义

Map 中存储的 `AActor*` 等 UObject 指针，复制时复制的是**指针值**，两个 Map 指向同一个对象：

```cpp
TMap<int32, AActor*> MyActorPtrs;
MyActorPtrs.Add(1, this);
MyActorPtrs.Add(2, nullptr);

TMap<int32, AActor*> MyAnotherActorPtrs = MyActorPtrs;
// 两个 Map 的 Key 1 都指向同一个 Actor

MyAnotherActorPtrs[1]->SetActorLocation(FVector::ZeroVector);
MyActorPtrs[1]->SetActorLocation(FVector::ZeroVector);
// 操作的是同一个 Actor

bool bEqual = MyAnotherActorPtrs[1] == MyActorPtrs[1];
// bEqual == true
```

> **代码位置**：[MapActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/005_Map/MapActor.cpp) — `SortMap()`, `OperateMap()` 函数
