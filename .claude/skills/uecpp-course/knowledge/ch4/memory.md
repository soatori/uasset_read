# TArray 内存管理

## 基本概念

TArray 内部维护两个核心指标：

| 指标 | 含义 | 获取方式 |
|------|------|----------|
| `Num()` | 当前实际存储的元素个数 | `Arr.Num()` |
| `Max()` | 当前已分配内存可容纳的元素个数 | `Arr.Max()` |
| **Slack** | 空闲容量 = `Max() - Num()` | `Arr.GetSlack()` |

## Slack 变化过程

```cpp
TArray<int32> Arr;
// 初始：Num=0, Max=0, Slack=0

Arr.Add(1);
// 首次添加：Num=1, Max=4, Slack=3

Arr.Add(2);
Arr.Add(3);
Arr.Add(4);
// Num=4, Max=4, Slack=0

Arr.Add(5);
// 触发扩容：Num=5, Max=20, Slack=15（增加 16）
```

## 扩容因子 16

UE5 的 TArray 扩容策略与 `std::vector`（通常扩容 1.5-2 倍）不同：

- **首次分配**：4 个元素
- **后续每次扩容**：增加 16 个元素的容量
- 受控于内存分配器中的 `FirstGrow` 和 `ConstGrow` 常量

扩容时调用链：`Realloc()` → `CalculateSlackGrow()` → `DefaultAllocator` → `ContainerAllocator`

此策略旨在减少频繁 realloc 的开销。

## Reserve()

```cpp
TArray<int32> Arr;
Arr.Reserve(100);  // 预分配 100 个元素的内存
// 后续 Add 100 次也不会触发 realloc
```

`Reserve()` 只分配内存，不添加元素。适合已知元素数量的场景，避免多次扩容带来的性能损耗。

**Reserve 不退还不缩容**：

```cpp
TArray<int32> Arr;
Arr.Reserve(10);   // 当前 Max=10
Arr.Add(1);
Arr.Add(2);
Arr.Add(3);        // Max 可能因扩容变大了

Arr.Reserve(2);    // 不会缩容！Max 保持不变
```

`Reserve()` 的参数如果小于当前 Max，**不会释放已分配的内存**。如果需要缩容，使用 `Shrink()`。

## Empty() vs Reset()

| 函数 | 清除元素 | 释放内存 | 典型场景 |
|------|----------|----------|----------|
| `Empty()` | 是 | 是（可指定保留量） | 彻底清空 |
| `Reset()` | 是 | **否** | 复用数组 |

```cpp
Arr.Empty();     // 清空并释放，Num=0, Max=0
Arr.Empty(10);   // 清空，但保留 10 个元素的容量

Arr.Reset();     // 清空，保持当前 Max 不变
Arr.Reset(50);   // 如果当前 Max < 50，重新分配到 50
```

## Shrink()

```cpp
TArray<int32> Arr;
Arr.Reserve(100);  // Max=100
for (int32 i = 0; i < 10; ++i) Arr.Add(i);  // Num=10

Arr.Shrink();      // Max 减少到 10（释放多余内存）
```

消除所有 Slack，使 Max 等于 Num。

## 性能建议

- 已知元素数量时使用 `Reserve()` 预分配
- 频繁复用的数组优先使用 `Reset()` 而非 `Empty()`
- 内存紧张时使用 `Shrink()` 释放不需要的容量空间
- 背包等固定容量场景（如 30 格背包），预分配避免扩容浪费

> **代码位置**：[XGArrayActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/004_Array/XGArrayActor.cpp) — 函数 `XGSlackArray()`, `XGRerversetArray()`, `XGEmptyArray()`
