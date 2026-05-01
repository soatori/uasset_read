# TMap 创建与填充

## Add() — 添加键值对

`Add()` 向 TMap 中插入一个键值对。如果键已存在，会覆盖原有的值：

```cpp
TMap<int32, FString> FruitMap;

FruitMap.Add(5, TEXT("Banana"));
FruitMap.Add(2, TEXT("Grapefruit"));
FruitMap.Add(7, TEXT("Pineapple"));

// FruitMap == [
//     { Key:5, Value:"Banana"     },
//     { Key:2, Value:"Grapefruit" },
//     { Key:7, Value:"Pineapple"  }
// ]

// 键已存在时覆盖
FruitMap.Add(2, TEXT("Pear"));
// FruitMap[2] == "Pear"  （覆盖了 "Grapefruit"）
```

`Add()` 返回被添加值（或覆盖值）的引用，可以直接修改：

```cpp
FString& MyFruit = FruitMap.Add(5, TEXT("Banana"));
MyFruit += TEXT("!!!");  // FruitMap[5] 变为 "Banana!!!"
```

### 仅添加键

`Add()` 可以只传入键，值使用默认构造：

```cpp
FruitMap.Add(4);
// FruitMap == [
//     { Key:4, Value:""  }
// ]
```

## Emplace() — 原地构造

`Emplace()` 与 `Add()` 功能相同，但直接传入构造参数，避免临时对象拷贝：

```cpp
FruitMap.Emplace(3, TEXT("Orange"));
// 等价于 FruitMap.Add(3, TEXT("Orange"))，但 Emplace 在容器内部直接构造
```

区别：
- `Add(key, value)` — 先构造临时对象，再拷贝/移动到容器
- `Emplace(key, value)` — 在容器内部直接构造，省去一次拷贝

## Append() — 合并另一个 Map

将一个 TMap 的所有元素合并到当前 Map 中。键重复时以**被追加的 Map** 为准：

```cpp
TMap<int32, FString> FruitMap2;
FruitMap2.Emplace(4, TEXT("Kiwi"));
FruitMap2.Emplace(9, TEXT("Melon"));
FruitMap2.Emplace(5, TEXT("Mango"));  // Key 5 已存在，会覆盖

FruitMap.Append(FruitMap2);
// FruitMap[5] == "Mango"  （被覆盖）
// FruitMap[4] == "Kiwi"
// FruitMap[9] == "Melon"

// FruitMap2 在此操作后被清空
```

## TMultiMap — 允许重复键

标准 TMap 不允许重复键，后插入的覆盖先插入的。如果需要一个键对应多个值，使用 `TMultiMap`：

```cpp
TMultiMap<int32, FString> FruitMultiMap;
FruitMultiMap.Add(2, TEXT("Grapefruit"));
FruitMultiMap.Add(2, TEXT("Pineapple"));
FruitMultiMap.Add(2, TEXT("Melon"));
// Key 2 现在关联三个值
```

## UPROPERTY — 蓝图暴露

TMap 可以通过 `UPROPERTY` 暴露给蓝图：

```cpp
UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = "XG|Fruit")
TMap<int32, FString> MyFruitMap;
```

支持在细节面板中编辑，以及蓝图读写操作。

> **代码位置**：[MapActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/005_Map/MapActor.h) — `MyFruitMap` 属性 / `InitMap()` 函数
