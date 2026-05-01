# TSet 初始化和填充

## 基本声明

```cpp
TSet<FString> FruitSet;
```

## 添加元素

### Add — 插入单一元素

```cpp
FruitSet.Add(TEXT("Banana"));
FruitSet.Add(TEXT("Grapefruit"));
FruitSet.Add(TEXT("Pineapple"));
// FruitSet == [ "Banana", "Grapefruit", "Pineapple" ]
```

重复插入会被覆盖：

```cpp
FruitSet.Add(TEXT("Pear"));
FruitSet.Add(TEXT("Banana"));  // 重复，被替换
// FruitSet == [ "Banana", "Grapefruit", "Pineapple", "Pear" ]
```

> Add 还可以接收一个可选的 `bool*` 出参，返回元素是否已存在。详见 [查询篇](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/knowledge/ch6/iteration-and-query.md)。

### Emplace — 原地构造

使用参数直接构造元素，跳过临时对象创建和拷贝：

```cpp
FruitSet.Emplace(TEXT("Orange"));
// FruitSet == [ "Banana", "Grapefruit", "Pineapple", "Pear", "Orange" ]
```

### Append — 合并另一个 TSet

```cpp
TSet<FString> FruitSet2;
FruitSet2.Emplace(TEXT("Kiwi"));
FruitSet2.Emplace(TEXT("Melon"));
FruitSet2.Emplace(TEXT("Mango"));
FruitSet2.Emplace(TEXT("Orange"));  // 已在 FruitSet 中存在

FruitSet.Append(FruitSet2);
// FruitSet == [ "Banana", "Grapefruit", "Pineapple", "Pear", "Orange", "Kiwi", "Melon", "Mango" ]
```

Append 自动去重，已有元素不会被重复添加。

## 初始化列表

```cpp
TSet<FString> FruitSet = { "Orange", "Pear", "Melon", "Grapefruit", "Mango", "Kiwi" };
```

## 蓝图暴露

通过 UPROPERTY 可将 TSet 暴露给蓝图，支持 BlueprintReadWrite：

```cpp
UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = SetExample)
TSet<FString> MyFruitSet;
```

## 代码引用

- [SetActor.cpp - InitSet()](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/006_Set/SetActor.cpp#L10-L56)：Add / Emplace / Append 完整示例
- [SetActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/006_Set/SetActor.h#L49-L51)：UPROPERTY 蓝图暴露
