# TSet 迭代与查询

## 迭代

TSet 的迭代方式与 TArray/TMap 类似，但迭代返回的是**元素引用**（而非键值对）。

### for-range 迭代

```cpp
TSet<FString> FruitSet;
FruitSet.Add(TEXT("Banana"));
FruitSet.Add(TEXT("Grapefruit"));
FruitSet.Add(TEXT("Pineapple"));

// auto& — 可读写
for (auto& Elem : FruitSet)
{
    Elem += TEXT("1");
    FPlatformMisc::LocalPrint(*FString::Printf(TEXT(" \"%s\"\n"), *Elem));
}

// 显式类型 — 可读写
for (FString& Elem : FruitSet)
{
    Elem += TEXT("2");
    FPlatformMisc::LocalPrint(*FString::Printf(TEXT(" \"%s\"\n"), *Elem));
}
```

### CreateIterator — 可变迭代器

```cpp
for (auto It = FruitSet.CreateIterator(); It; ++It)
{
    (*It) += TEXT("3");
    FPlatformMisc::LocalPrint(*FString::Printf(TEXT("(%s)\n"), *(*It)));
}
```

### CreateConstIterator — 只读迭代器

```cpp
for (auto It = FruitSet.CreateConstIterator(); It; ++It)
{
    FPlatformMisc::LocalPrint(*FString::Printf(TEXT("(%s)\n"), *(*It)));
}
```

### UE_LOG 输出注意

FString 输出到 UE_LOG 需要 `*FString` 转换：

```cpp
UE_LOG(LogTemp, Warning, TEXT("Element: %s"), *Elem);
// 或使用 FPlatformMisc::LocalPrint
FPlatformMisc::LocalPrint(*FString::Printf(TEXT(" \"%s\"\n"), *Elem));
```

## 查询

### Num — 获取元素数量

```cpp
int32 Count = FruitSet.Num();
```

### Contains — 存在性检查

```cpp
bool bHasBanana = FruitSet.Contains(TEXT("Banana"));  // true
bool bHasLemon  = FruitSet.Contains(TEXT("Lemon"));   // false
```

### FSetElementId — 索引标识

FSetElementId 是 TSet 的元素索引结构体（非整数索引方法），用于定位特定元素：

```cpp
FSetElementId SetElementId = FruitSet.Add(TEXT("Water"));
FruitSet[SetElementId] += TEXT("Modify");
// 此时 Water 变为 WaterModify
```

> 注意：FSetElementId 的 `Index()` 函数在较新 UE 版本中已被移除，不应用作整数索引。

### Find — 查找元素（返回指针）

```cpp
FString* PtrBanana = FruitSet.Find(TEXT("Banana"));  // 有效指针
FString* PtrLemon  = FruitSet.Find(TEXT("Lemon"));   // nullptr

// *PtrBanana == "Banana"
//  PtrLemon  == nullptr
```

### Add 的 bool 出参

Add 可接收一个可选的 `bool*` 出参，指示元素是否已存在：

```cpp
bool bAlreadyInSet = false;
FruitSet.Add(TEXT("Banana"), &bAlreadyInSet);
// bAlreadyInSet == true（已存在）
```

### Array — 转换为 TArray

```cpp
TArray<FString> FruitArray = FruitSet.Array();
// 返回新创建的 TArray，不影响原 TSet
```

返回的是**新创建的数组副本**，不是对原 TSet 的引用。数组中的元素顺序与 TSet 的哈希顺序一致。

## 代码引用

- [SetActor.cpp - LoopSet()](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/006_Set/SetActor.cpp#L58-L100)：迭代完整实现
- [SetActor.cpp - QuerySet()](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/006_Set/SetActor.cpp#L102-L155)：查询完整实现
