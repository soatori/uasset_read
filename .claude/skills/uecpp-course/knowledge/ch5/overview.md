# TMap 基本概念

## 概述

TMap 是 UE 提供的**基于哈希表的键值对容器**。与 TArray 不同，TMap 是无序的——元素在容器中的存储位置由键的哈希值决定，而非插入顺序。

## 内部结构

```cpp
TMap<int32, FString> FruitMap;
FruitMap.Add(5, TEXT("Banana"));
FruitMap.Add(2, TEXT("Grapefruit"));
FruitMap.Add(7, TEXT("Pineapple"));
```

TMap 内部使用 `TPair<KeyType, ValueType>` 作为元素类型，并采用基于集合（set-based）的分配器来管理内存。每个键值对以哈希桶（hash bucket）的形式组织，支持 O(1) 平均复杂度的查找。

## TMultiMap

当需要为同一个键存储多个值时，使用 `TMultiMap`：

```cpp
TMultiMap<int32, FString> FruitMultiMap;
FruitMultiMap.Add(2, TEXT("Grapefruit"));
FruitMultiMap.Add(2, TEXT("Pineapple"));
FruitMultiMap.Add(2, TEXT("Melon"));
// Key 2 映射到三个不同的值
```

## 键类型要求

TMap 的键类型必须满足两个条件：

1. **可哈希**：提供 `GetTypeHash()` 函数计算哈希值
2. **可比较**：提供 `operator==` 判断键是否相等

基本类型（`int32`、`FString`、`FName` 等）已内置支持。

如果需要将自定义结构体作为键，需要提供这两个函数的实现（详见 [struct-as-key.md](struct-as-key.md)）。

## 指针/引用失效

对 TMap 执行添加或移除操作后，容器内部可能发生**重新哈希（rehashing）**，导致已获取的指针或引用失效：

```cpp
FruitMap.Add(5, TEXT("Banana"));

// 获取引用
FString& MyFruit = FruitMap.Add(5, TEXT("Banana"));
MyFruit += TEXT("!!!");  // 安全：Add 返回的引用在本次添加后有效

// 但后续操作可能导致之前的引用失效
FruitMap.Add(8, TEXT("Kiwi"));  // 可能触发 rehash
// MyFruit 此时可能已失效 —— 不应继续使用
```

## 内存布局与赋值

TMap 被设计为按值语义工作。进行复制时执行深拷贝：

```cpp
TMap<int32, FString> Map1;
Map1.Add(1, TEXT("A"));

TMap<int32, FString> Map2 = Map1;  // 深拷贝，两个独立容器
Map2[1] = TEXT("B");                // 只修改 Map2，不影响 Map1
```

> **代码位置**：[MapActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/005_Map/MapActor.h) / [MapActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/005_Map/MapActor.cpp) — `AMapActor` 类及 `InitMap()` 函数
