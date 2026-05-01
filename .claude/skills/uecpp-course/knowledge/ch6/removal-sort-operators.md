# TSet 移除、排序与运算符

## 移除元素

### Remove — 按值移除

按元素值移除，返回被移除的元素数量（0 或 1）：

```cpp
int32 GGNum = FruitSet.Remove(TEXT("GG"));  // 返回 1
int32 MMNum = FruitSet.Remove(TEXT("MM"));  // 返回 0（不存在）
```

### Remove — 按 FSetElementId 移除

```cpp
FruitSet.Remove(FSetElementId::FromInteger(0));
```

### Reset — 保留容量清空

清空元素但保留已分配的哈希桶内存（Slack 保留），适合重复使用的 TSet：

```cpp
TSet<FString> FruitSet1 = FruitSet;
FruitSet1.Reset();
```

### Empty — 释放容量清空

清空元素并释放所有内存（包括 Slack）：

```cpp
TSet<FString> FruitSet2 = FruitSet;
FruitSet2.Empty(0);  // 参数指定新容量
```

### Reserve — 预分配容量

提前分配容量，减少多次插入时的扩容开销：

```cpp
FruitSet.Reserve(4);
FruitSet.Add(TEXT("Banana"));
FruitSet.Add(TEXT("Grapefruit"));
// ...
```

## 排序

TSet 的排序与 TArray/TMap 类似，基于**内部数组排序**。排序后顺序是暂时保证的，后续插入/删除操作可能改变顺序。

### Sort — 不稳定排序

```cpp
TSet<FString> FruitSet = { "Orange", "Pear", "Melon", "Grapefruit", "Mango", "Kiwi" };

// 按字母逆序
FruitSet.Sort([](const FString& A, const FString& B) {
    return A > B;  // reverse-alphabetical
});
// FruitSet == [ "Pear", "Orange", "Melon", "Mango", "Kiwi", "Grapefruit" ]

// 按字符串长度升序
FruitSet.Sort([](const FString& A, const FString& B) {
    return A.Len() < B.Len();
});
// FruitSet == [ "Pear", "Kiwi", "Melon", "Mango", "Orange", "Grapefruit" ]
```

Sort 是**不稳定排序**（相同长度的字符串间不保证维持相对顺序）。

### StableSort — 稳定排序

```cpp
FruitSet.StableSort([](const FString& A, const FString& B) { return A.Len() < B.Len(); });
// 等长元素维持原始相对顺序
```

## 拷贝赋值运算符

```cpp
TSet<FString> FruitSet = { "Orange", "Pear", "Melon", "Grapefruit", "Mango", "Kiwi" };
TSet<FString> NewSet = FruitSet;  // 深拷贝容器

NewSet.Add(TEXT("Apple"));
NewSet.Remove(TEXT("Pear"));

// FruitSet == [ "Pear", "Kiwi", "Melon", "Mango", "Orange", "Grapefruit" ]  // 不受影响
// NewSet   == [ "Kiwi", "Melon", "Mango", "Orange", "Grapefruit", "Apple" ]
```

拷贝赋值对容器执行**深拷贝**。拷贝后两个 TSet 各自独立，修改一方不影响另一方。

> **注意**：若元素类型为 UObject 指针，拷贝赋值仅复制指针值（浅拷贝），不复制指向的 UObject 对象本身。这与 TMap 的行为一致。

## Slack 管理

### Slack 概念

Slack 是 TSet 预分配但未使用的哈希桶容量。Remove 操作会在内部数组留下"空洞"（无效槽位），Compact 后可通过 Shrink 回收。

### Compact

压缩内部数组，将有效元素移动到无效槽位前方：

```cpp
// 假设 FruitSet 包含 10 个元素："Fruit9"..."Fruit0"
// 移除奇数索引元素后，数组为：
// [ "Fruit8", <invalid>, "Fruit6", <invalid>, "Fruit4", <invalid>, "Fruit2", <invalid>, "Fruit0", <invalid> ]
```

**CompactStable** — 稳定压缩，保持有效元素的相对顺序：

```cpp
FruitSet.CompactStable();
// [ "Fruit8", "Fruit6", "Fruit4", "Fruit2", "Fruit0", <invalid>, <invalid>, <invalid>, <invalid> ]
```

普通 Compact 不保证顺序稳定性。

### Shrink

移除数组尾部连续无效槽位，回收内存：

```cpp
FruitSet.CompactStable();
FruitSet.Shrink();
// [ "Fruit8", "Fruit6", "Fruit4", "Fruit2", "Fruit0" ]
// 尾部无效槽位全部回收
```

典型工作流：Remove → CompactStable → Shrink。

## 代码引用

- [SetActor.cpp - RemoveSet()](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/006_Set/SetActor.cpp#L157-L194)：移除操作完整实现
- [SetActor.cpp - SortSet()](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/006_Set/SetActor.cpp#L196-L223)：排序完整实现
- [SetActor.cpp - OpeatorSet()](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/006_Set/SetActor.cpp#L226-L242)：拷贝赋值示例
- [SetActor.cpp - SlackSet()](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/006_Set/SetActor.cpp#L244-L287)：Slack 管理完整实现
