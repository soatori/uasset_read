# TArray 添加元素

## Add vs Emplace

```cpp
TArray<FString> Arr;

// Add：拷贝已存在的对象进入数组
FString Str = TEXT("Hello");
Arr.Add(Str);  // 拷贝 Str 到数组内存中

// Emplace：在数组已分配内存中直接构造，避免拷贝
Arr.Emplace(TEXT("World"));  // 在数组内直接构造 FString
```

**区别**：`Add()` 接收已存在的对象并拷贝到数组中；`Emplace()` 接收构造函数参数并在数组已分配的内存中直接构造对象，避免不必要的拷贝。

## Append

```cpp
TArray<int32> Arr1 = {1, 2, 3};
TArray<int32> Arr2 = {4, 5, 6};
Arr1.Append(Arr2);  // Arr1 变为 {1, 2, 3, 4, 5, 6}
```

合并整个数组到末尾。也可以从 C 风格数组追加：

```cpp
FString ArrC[] = { TEXT("of"), TEXT("Tomorrow") };
StrArr.Append(ArrC, UE_ARRAY_COUNT(ArrC));
```

## Insert

```cpp
TArray<int32> Arr = {1, 2, 4, 5};
Arr.Insert(3, 2);  // 在索引 2 处插入 3：{1, 2, 3, 4, 5}
```

在指定索引位置插入元素，后续元素后移。

## EmplaceAt

```cpp
Arr.EmplaceAt(2, 3);  // 在索引 2 处就地构造
```

等同于 `Insert` 但使用就地构造。

## AddUnique

```cpp
StrArr.AddUnique(TEXT("!"));   // 添加，如果已存在则跳过
StrArr.AddUnique(TEXT("!"));   // "!" 已存在，不会重复添加
```

先判断元素是否已存在于数组中（使用 `operator==`），已存在则跳过，不存在才添加。用于维护数组元素的唯一性。

对于结构体数组同样适用：

```cpp
TArray<FXGEqualStructInfo> EqualStructArray;
EqualStructArray.AddUnique(0);  // 添加 ID=0
EqualStructArray.AddUnique(1);  // 添加 ID=1
EqualStructArray.AddUnique(1);  // 跳过，ID=1 已存在
EqualStructArray.AddUnique(2);  // 添加 ID=2
```

需要元素类型有 `operator==`。

## AddDefaulted / AddDefaulted_GetRef

```cpp
TArray<FMyStruct> Arr;

// 添加一个默认构造的元素，返回索引
int32 Index = Arr.AddDefaulted();

// 添加一个默认构造的元素，返回引用
FMyStruct& NewElem = Arr.AddDefaulted_GetRef();
NewElem.Healty += 2000;
```

`AddDefaulted()` 返回索引，`AddDefaulted_GetRef()` 返回元素引用，适合需要立即修改的场景。

> **代码位置**：[XGArrayActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/004_Array/XGArrayActor.h) / [XGArrayActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/004_Array/XGArrayActor.cpp) — 函数 `XGAddArrayString1~4()`, `XGAddDefaultArray()`, `XGAddUniqueString()`, `XGAddUniqueStruct()`
