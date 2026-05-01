# TMap 移除与内存管理

## Remove() — 移除指定键

`Remove()` 通过键移除元素，返回被移除的元素数量（TMap 中为 0 或 1，TMultiMap 中可能大于 1）：

```cpp
TMap<int32, FString> FruitMap;
FruitMap.Add(5, TEXT("Mango"));
FruitMap.Add(7, TEXT("Pineapple"));
FruitMap.Add(10, TEXT("Grapefruit"));

int32 Removed = FruitMap.Remove(5);  // Removed == 1（键 5 存在）
int32 NotFound = FruitMap.Remove(8);  // NotFound == 0（键 8 不存在）
```

## FindAndRemoveChecked() — 移除并返回值

直接返回被移除的值。**如果键不存在会触发断言**：

```cpp
FString Removed5 = FruitMap.FindAndRemoveChecked(5);  // Removed5 == "Mango"
// FString Removed8 = FruitMap.FindAndRemoveChecked(8);  // Assert!
```

## RemoveAndCopyValue() — 安全移除并拷贝值

相比 `FindAndRemoveChecked`，不会触发断言。键不存在时返回 `false`，保留输出参数的原值：

```cpp
FString Removed = TEXT("XG");

bool bFound5 = FruitMap.RemoveAndCopyValue(5, Removed);  // bFound5 == true, Removed == "Mango"
bool bFound8 = FruitMap.RemoveAndCopyValue(8, Removed);  // bFound8 == false, Removed 不变
```

## Empty() — 清空所有元素

清除所有元素。可选参数指定保留的 Slack 容量：

```cpp
FruitMap.Empty();      // 清除所有元素，释放所有内存
FruitMap.Empty(10);    // 清除所有元素，但保留 10 个元素的内存容量
```

## Reset() — 重置但保留容量

清空元素，但**保留当前已分配的内存容量**，适合重复使用的场景：

```cpp
FruitMap.Reset();      // 清空元素，保留当前容量
```

## Reserve() — 预分配容量

预先分配足够容纳指定数量元素的内存，减少后续添加时的重新哈希：

```cpp
FruitMap.Reserve(3);   // 预分配 3 个元素的空间
FruitMap.Add(5, TEXT("Mango"));
FruitMap.Add(7, TEXT("Pineapple"));
FruitMap.Add(10, TEXT("Grapefruit"));

FruitMap.Reserve(10);  // 扩容到至少容纳 10 个元素
FruitMap.Reserve(2);   // 小于当前容量，无效果（不会缩容）
```

## Slack 机制

Slack 是 TMap 中预分配但尚未使用的空闲容量。

**Remove 不会立即释放内存**——被移除的元素标记为无效（类似于"软删除"），但其占用的内存空间（Slack）仍然保留：

```cpp
FruitMap.Reserve(10);   // 预分配 10 个元素空间
FruitMap.Add(1, TEXT("A"));
// ... 添加多个元素

FruitMap.Remove(2);     // 键 2 被移除，但内存仍保留为 Slack
FruitMap.Remove(4);
FruitMap.Remove(6);
// 容器中仍有空闲槽位
```

## Compact() / CompactStable() — 压缩空隙

移除操作产生无效空隙后，`Compact()` 将所有有效元素紧凑排列到容器前端：

```cpp
FruitMap.Remove(2);
FruitMap.Remove(4);
FruitMap.Remove(6);

FruitMap.Compact();           // 压缩空隙，不稳定排序
// FruitMap.CompactStable();  // 压缩空隙，保持插入顺序
```

- `Compact()` — 不保证元素的相对顺序
- `CompactStable()` — 保持元素的原始顺序

## Shrink() — 释放多余内存

`Shrink()` 释放末尾的空闲内存，使容器的已分配容量（Max）与实际元素数量（Num）匹配：

```cpp
// 典型模式：先 Compact 再 Shrink
FruitMap.Compact();
FruitMap.Shrink();
```

`Shrink()` 只释放容器**末尾**的空闲空间。因此通常先调用 `Compact()` 将有效元素集中到前端，再调用 `Shrink()` 释放后端内存。

## 移除与内存操作流程

推荐的内存回收模式：

```cpp
// 1. 移除不需要的元素
FruitMap.Remove(2);
FruitMap.Remove(4);

// 2. 压缩空隙（可选）
FruitMap.Compact();

// 3. 释放末尾空闲内存
FruitMap.Shrink();
```

## GetAllocatedSize() — 分配内存大小

返回容器自身已分配内存的字节数（不包括元素内部额外分配的内存）：

```cpp
TMap<int32, FString> MyMap;

MyMap.Reserve(4);
uint32 Size1 = MyMap.GetAllocatedSize();  // 预分配后的内存大小

MyMap.Add(1, TEXT("A"));
uint32 Size2 = MyMap.GetAllocatedSize();  // 添加元素后的内存大小
```

## CountBytes() / Dump()

- `CountBytes()` — 通过 `FArchive` 计算容器序列化占用的字节数
- `Dump()` — 将容器内容输出到 `FOutputDevice`，用于调试

## 移除操作对比

| 函数 | 行为 | 安全性 |
|------|------|--------|
| `Remove(key)` | 移除键对应的元素 | 安全，返回移除数量 |
| `FindAndRemoveChecked(key)` | 移除并返回值 | 不安全，键不存在时断言 |
| `RemoveAndCopyValue(key, out)` | 移除并拷贝值到输出参数 | 安全，返回 bool |
| `Empty()` | 清空所有元素 | 安全 |
| `Reset()` | 清空元素，保留容量 | 安全 |

> **代码位置**：[MapActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/005_Map/MapActor.cpp) — `XGRemoveMap()`, `XGRemoveCheckMap()`, `RemoveAndCopyValueMap()`, `EmptyMap()`, `ResetMap()`, `ReverseMap()`, `SlackMap()`, `StructSize()` 函数
