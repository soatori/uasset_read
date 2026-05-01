# TArray 查找函数

## Contains()

```cpp
TArray<int32> Arr = {10, 20, 30, 40, 50};

if (Arr.Contains(30))  // true
{
    // 元素存在
}
```

需要元素类型有 `operator==`。

## ContainsByPredicate()

```cpp
bool bFound = Arr.ContainsByPredicate([](const int32& Val)
{
    return Val > 25;
});
```

使用 Lambda 谓词判断，不需要 `operator==`。

## Find() / FindLast()

### 通过引用参数返回索引

```cpp
int32 Index;
bool bFound = Arr.Find(30, Index);   // Index = 2, bFound = true
bool bFound = Arr.FindLast(30, Index); // 从后往前找
```

函数返回 `bool` 表示是否找到，索引通过 `int32&` 参数传出。

### 直接返回索引

```cpp
int32 Index = Arr.Find(30);  // Index = 2
int32 Index = Arr.Find(99);  // Index = INDEX_NONE（-1）
```

## INDEX_NONE

`INDEX_NONE` 是 UE 定义的常量，值为 `-1`。当查找不到元素时，`Find()` 返回此值。

```cpp
int32 Index = Arr.Find(99);
if (Index != INDEX_NONE)
{
    // 找到
}
```

## 调试技巧

在 Lambda 中使用计数器可以验证查找次数：

```cpp
int32 Counter = 0;
bool bFound = Arr.ContainsByPredicate([&Counter](const int32& Val)
{
    ++Counter;
    return Val > 25;
});
UE_LOG(LogTemp, Log, TEXT("查询次数：%d"), Counter);
```

需要按引用捕获计数器才能在 Lambda 内修改外部变量。

> **代码位置**：[XGArrayActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/004_Array/XGArrayActor.cpp) — 函数 `XGFindArray()`, `XGContainsArray()`
