# TArray 移除操作

## Remove()

```cpp
TArray<int32> Arr = {1, 2, 3, 2, 4, 2};
Arr.Remove(2);  // 移除所有值为 2 的元素：{1, 3, 4}
```

需要元素类型有 `operator==`。移除所有匹配的元素，保持剩余元素的顺序。

## RemoveSingle()

```cpp
TArray<int32> Arr = {1, 2, 3, 2, 4, 2};
Arr.RemoveSingle(2);  // 只移除第一个 2：{1, 3, 2, 4, 2}
```

## RemoveAt()

```cpp
Arr.RemoveAt(2);  // 移除索引 2 处的元素
```

**索引越界会直接崩溃**。移除前应先调用 `IsValidIndex()` 检查：

```cpp
if (Arr.IsValidIndex(2))
{
    Arr.RemoveAt(2);
}
```

## RemoveAll()

```cpp
Arr.RemoveAll([](const int32& Val)
{
    return Val % 2 == 0;  // 移除所有偶数
});
```

使用谓词决定删除条件，不需要 `operator==`。

## RemoveAtSwap()

```cpp
Arr.RemoveAtSwap(1);  // 移除索引 1 的元素，用最后一个元素填补空位
```

与 `RemoveAt` 的区别：
- `RemoveAtSwap` **不保持顺序**，但更快（不需要移动中间元素）
- 内部实现：将最后一个元素拷贝到被删除位置，直接缩容

## RemoveSwap()

```cpp
Arr.RemoveSwap(2);  // 移除所有值为 2 的元素（不保持顺序）
```

等价于 `Remove` + `RemoveAtSwap` 的组合。

## RemoveAllSwap()

```cpp
ValArr.RemoveAllSwap([](int32 Val)
{
    return Val % 3 == 0;  // 移除所有 3 的倍数（不保持顺序）
});
```

等价于 `RemoveAll` + `RemoveAtSwap` 的组合。移除所有匹配元素，但不保持顺序，性能更快。

## Empty()

```cpp
Arr.Empty();     // 清除所有元素并释放内存
Arr.Empty(10);   // 清除所有元素，但保留 10 个元素容量的内存
```

调用每个元素的析构函数。

## Reset()

```cpp
Arr.Reset();    // 清除所有元素，但不释放内存（保留当前容量）
Arr.Reset(20);  // 如果当前容量 < 20，重新分配；否则不清除
```

`Reset()` 不会释放已分配的内存，适合重复使用同一数组的场景。

## Shrink()

```cpp
// 假设 Arr 的 Max = 50, Num = 10
Arr.Shrink();   // 释放多余内存，使 Max = 10
```

减少已分配内存到与当前元素数量匹配，消除 Slack。

## 移除操作对比

| 函数 | 保持顺序 | 使用方式 | 性能 |
|------|----------|----------|------|
| `Remove()` | 是 | 按值 | 中等（移动元素） |
| `RemoveSingle()` | 是 | 按值 | 中等 |
| `RemoveAt()` | 是 | 按索引 | 中等（移动元素） |
| `RemoveAll()` | 是 | 按谓词 | 中等 |
| `RemoveAtSwap()` | **否** | 按索引 | **快** |
| `RemoveSwap()` | **否** | 按值 | **快** |
| `RemoveAllSwap()` | **否** | 按谓词 | **快** |
| `Empty()` | — | 全部清除 | 快 |
| `Reset()` | — | 全部清除（保留内存） | 快 |

> **代码位置**：[XGArrayActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/004_Array/XGArrayActor.cpp) — 函数 `XGRemoveArrayType1~5()`, `XGRemoveMultiElement()`, `XGEmptyArray()`
