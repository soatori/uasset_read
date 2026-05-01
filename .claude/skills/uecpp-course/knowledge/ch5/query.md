# TMap 查询操作

## Num() — 元素数量

```cpp
TMap<int32, FString> FruitMap;
FruitMap.Add(5, TEXT("Grapefruit"));
FruitMap.Add(7, TEXT("Pineapple"));
FruitMap.Add(9, TEXT("Melon"));

int32 Count = FruitMap.Num();  // 3
```

## Contains() — 键是否存在

```cpp
bool bHas7 = FruitMap.Contains(7);  // true
bool bHas8 = FruitMap.Contains(8);  // false
```

## operator[] — 通过键访问

`operator[]` 支持读和写。**如果键不存在会触发断言崩溃**：

```cpp
FString Val7 = FruitMap[7];          // 读取，Val7 == "Pineapple"
FString& Val7Ref = FruitMap[7];      // 获取引用，可通过引用修改
Val7Ref += TEXT("Ref");

// 错误使用：键不存在导致断言
// FString Val8 = FruitMap[8];       // Assert!
```

使用前建议先用 `Contains()` 检查键是否存在。

## Find() — 返回指针

`Find()` 返回指向值的指针。如果键不存在，返回 `nullptr`，不会崩溃：

```cpp
FString* Ptr7 = FruitMap.Find(7);
FString* Ptr8 = FruitMap.Find(8);

if (Ptr7)
{
    // *Ptr7 == "Pineapple"
}

// Ptr8 == nullptr，安全
```

推荐的安全访问模式：

```cpp
if (FString* Ptr = FruitMap.Find(7))
{
    UE_LOG(LogTemp, Warning, TEXT("%d-%s"), 7, **Ptr);
}
```

## FindOrAdd() — 查找或创建

如果键存在，返回值的引用；如果键不存在，**创建**一个默认构造的值再返回引用：

```cpp
FString& Ref7 = FruitMap.FindOrAdd(7);   // 键 7 存在，返回引用
FString& Ref8 = FruitMap.FindOrAdd(8);   // 键 8 不存在，创建空 FString

Ref8 = TEXT("NewAdd8");                   // 修改新创建的值
```

与 `operator[]` 的区别：`FindOrAdd` 不会在键缺失时崩溃，而是自动创建默认值。

## FindRef() — 查找并返回副本

`FindRef()` 返回值的**副本**。如果键不存在，返回默认构造的值，但**不会创建新元素**：

```cpp
FString Val7 = FruitMap.FindRef(7);       // 键 7 存在，返回副本
Val7 += TEXT("998");                       // 只修改副本，不影响容器

FString Val6 = FruitMap.FindRef(6);       // 键 6 不存在，返回空 FString
// FruitMap 中仍然没有键 6 的元素
```

与 `FindOrAdd` 的关键区别：
- `FindRef()` — 返回副本，键不存在时不创建元素
- `FindOrAdd()` — 返回引用，键不存在时创建元素

## FindKey() — 反向查找值到键

根据值查找键。多个键映射到相同值时，返回**最先找到**的一个。时间复杂度 O(n)：

```cpp
TMap<int32, FString> FruitMap;
FruitMap.Add(5, TEXT("Mango"));
FruitMap.Add(7, TEXT("Pineapple"));
FruitMap.Add(10, TEXT("Pineapple"));

const int32* KeyMangoPtr = FruitMap.FindKey(TEXT("Mango"));     // *KeyMangoPtr == 5
const int32* KeyKumquatPtr = FruitMap.FindKey(TEXT("Kumquat")); // nullptr

// 多个 Pineapple，返回哪个键不确定
const int32* KeyFindTest1 = FruitMap.FindKey(TEXT("Pineapple"));
```

## GetKeys() / GetValues() — 提取键或值到数组

```cpp
TArray<int32>   FruitKeys;
TArray<FString> FruitValues;

FruitMap.GenerateKeyArray(FruitKeys);       // 提取所有键到数组
FruitMap.GenerateValueArray(FruitValues);   // 提取所有值到数组
```

## 查询方法对比

| 函数 | 键不存在时 | 返回类型 | 说明 |
|------|-----------|----------|------|
| `Contains()` | — | `bool` | 仅检查存在性 |
| `operator[]` | **断言崩溃** | 引用 | 读写均可 |
| `Find()` | `nullptr` | 指针 | 安全，推荐 |
| `FindOrAdd()` | 创建默认值 | 引用 | 会修改容器 |
| `FindRef()` | 返回默认值 | 值副本 | 不修改容器 |
| `FindKey()` | `nullptr` | 键指针 | O(n)，反向查找 |

> **代码位置**：[MapActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/005_Map/MapActor.cpp) — `QueryMap()`, `FindMap()`, `FindAdvMap()`, `FindKeyMap()`, `XGGetAllKeysAndValueMap()` 函数
