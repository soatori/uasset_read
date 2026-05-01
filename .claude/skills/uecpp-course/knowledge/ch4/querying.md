# TArray 查询与访问

## 基本查询

```cpp
TArray<int32> Arr = {1, 2, 3, 4, 5};

int32 Count = Arr.Num();    // 5——当前元素个数
bool bEmpty = Arr.IsEmpty(); // false
```

## Num()

返回数组中当前元素的个数，类型为 `int32`。

## SetNum()

动态调整数组元素数量：

```cpp
TArray<FString> StrArr = { "Hello", "World", "of", "Tomorrow", "!" };

StrArr.SetNum(10);  // 扩容到 10 个，新增元素默认构造
StrArr.SetNum(5);   // 缩容到 5 个，多余元素析构
```

- 新数量大于当前数量：扩容，新增元素默认构造
- 新数量小于当前数量：缩容，超出部分元素被析构

## Empty()

```cpp
Arr.Empty();     // 清除所有元素，释放内存
Arr.Empty(10);   // 清除所有元素，但保留 10 个元素容量的内存（Slack）
```

`Empty()` 会调用每个元素的析构函数。

## GetData()

返回指向数组内部缓冲区的原始指针：

```cpp
int32* DataPtr = Arr.GetData();  // 指向第一个元素
FString* StrPtr = StrArr.GetData();
```

**危险**：一旦对数组进行了修改（Add/Remove 等），已获取的指针可能会失效（数组可能已重新分配内存）。建议仅在只读场景且确保数组不会被修改时使用。

对于 `const TArray`，`GetData()` 返回 `const` 指针，不可通过该指针修改元素。

## GetAllocatedSize()

返回数组已分配内存的字节大小：

```cpp
TArray<int32> MyInt;
MyInt.Add(1);
int32 Size = MyInt.GetAllocatedSize();  // int32=4 字节, 首次分配 4 个元素, 共 16 字节

MyInt.Empty(3);
int32 Size2 = MyInt.GetAllocatedSize(); // Empty(3) 保留 3 个元素容量: 12 字节

// 指针数组：一个指针在 64 位系统上是 8 字节
TArray<AActor*> MyPointers;
MyPointers.Add(this);
int32 Size3 = MyPointers.GetAllocatedSize();  // 4 个元素 x 8 字节 = 32 字节
```

## GetTypeSize()

返回单个元素类型的大小：

```cpp
uint32 Size1 = StrArr.GetTypeSize();  // FString = 16 字节
uint32 Size2 = IntArr.GetTypeSize();  // int32  = 4 字节
uint32 Size3 = Uint8Arr.GetTypeSize(); // uint8  = 1 字节
```

等价于 `sizeof(ElementType)`。

## sizeof 类型大小

使用 `sizeof` 可以检查元素类型的大小：

```cpp
int32 StrSize = sizeof(FString);  // 16 字节
int32 IntSize = sizeof(int32);    // 4 字节
int32 ByteSize = sizeof(uint8);   // 1 字节
```

## Max() / GetSlack()

```cpp
int32 Capacity = Arr.Max();      // 当前分配容量
int32 Slack = Arr.GetSlack();    // 空闲容量 = Max - Num
```

详见 [memory.md](memory.md)。

> **代码位置**：[XGArrayActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/004_Array/XGArrayActor.cpp) — 函数 `XGGetAllocatedSize()`, `XGSetStringNum()`, `XGFindArray_ElementSize()`
