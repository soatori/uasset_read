# TMap 调试与工具函数

## GetAllocatedSize() — 分配内存大小

返回容器自身管理的已分配内存字节数（不包括元素内部额外动态分配的内存，如 `FString` 的堆缓冲区）：

```cpp
TMap<int32, FString> MyMap;

MyMap.Reserve(4);
uint32 Size1 = MyMap.GetAllocatedSize();  // 预分配后的内存大小

MyMap.Add(1, TEXT("A"));
MyMap.Add(2, TEXT("A"));
MyMap.Add(3, TEXT("A"));

uint32 Size2 = MyMap.GetAllocatedSize();  // 添加 3 个元素后的内存大小

MyMap.Add(4, TEXT("A"));
MyMap.Add(5, TEXT("A"));
MyMap.Add(6, TEXT("A"));

uint32 Size3 = MyMap.GetAllocatedSize();  // 扩容后的内存大小
```

## Dump() — 输出容器内容

`Dump()` 将 TMap 中所有键值对输出到指定的 `FOutputDevice`，用于调试：

```cpp
// 将容器内容输出到日志
// MyMap.Dump();
```

## CountBytes() — 序列化字节计数

通过 `FArchive` 统计容器序列化时占用的字节数：

```cpp
// 计算序列化字节数
// MyMap.CountBytes();
```

## 内存操作总结

| 函数 | 作用 |
|------|------|
| `Reserve(N)` | 预分配 N 个元素容量，减少 rehash |
| `Empty(Slack)` | 清空所有元素，可选保留 Slack |
| `Reset()` | 清空元素，保留现有容量 |
| `Compact()` | 压缩有效元素，消除空隙 |
| `Shrink()` | 释放末尾空闲内存 |
| `GetAllocatedSize()` | 获取分配内存字节数 |
| `Dump()` | 输出容器内容到输出设备 |
| `CountBytes()` | 计算序列化占用字节 |

> **代码位置**：[MapActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/005_Map/MapActor.cpp) — `StructSize()` 函数
