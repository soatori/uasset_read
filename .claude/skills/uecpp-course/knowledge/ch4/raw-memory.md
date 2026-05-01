# TArray 原始内存

## GetData()

`GetData()` 返回指向数组内部元素缓冲区的原始指针：

```cpp
TArray<int32> Arr = {10, 20, 30, 40, 50};
int32* DataPtr = Arr.GetData();  // 指向第一个元素
```

## 指针运算

```cpp
int32 First  = *DataPtr;        // 10
int32 Second = *(DataPtr + 1);  // 20
int32 Third  = DataPtr[2];      // 30
```

## 安全性注意

```cpp
int32* DataPtr = Arr.GetData();

Arr.Add(60);  // 可能触发 realloc

// DataPtr 已失效！此时访问 DataPtr 是未定义行为
int32 Val = DataPtr[3];  // 危险！
```

一旦对数组执行了可能导致扩容的操作（Add、Remove、Insert 等），之前通过 `GetData()` 获取的指针就会失效。

## const 数组

```cpp
const TArray<int32>& ConstArr = Arr;
const int32* DataPtr = ConstArr.GetData();  // const 指针，不可修改
```

## AddUninitialized

分配内存但不初始化元素，适用于后续通过原始内存操作（如 `FMemory::Memcpy`）写入数据：

```cpp
int32 SrcInts[] = { 2, 3, 5, 7 };
TArray<int32> UninitInts;
UninitInts.AddUninitialized(4);
FMemory::Memcpy(UninitInts.GetData(), SrcInts, 4 * sizeof(int32));
// UninitInts == [2, 3, 5, 7]
```

**注意**：对于有构造函数的 USTRUCT，`AddUninitialized` 不会调用构造函数，直接操作内存可能引发问题。

## InsertUninitialized

在指定位置插入未初始化的元素空间，配合 placement new 使用：

```cpp
TArray<FString> UninitStrs;
UninitStrs.Emplace(TEXT("A"));
UninitStrs.Emplace(TEXT("D"));

UninitStrs.InsertUninitialized(1, 2);  // 在索引 1 处预留 2 个空位

// 使用 placement new 在预留位置构造对象
new ((void*)(UninitStrs.GetData() + 1)) FString(TEXT("B"));
new ((void*)(UninitStrs.GetData() + 2)) FString(TEXT("C"));

// UninitStrs == ["A", "B", "C", "D"]
```

## AddZeroed

添加一个零初始化的元素（所有字节置零）：

```cpp
TArray<FMyStruct> Arr;
Arr.AddZeroed();  // 添加一个全零元素
```

对包含指针、int32、float 的结构体尤其有用（指针初始化为 nullptr，数值初始化为 0）。

## SetNumUninitialized / SetNumZeroed

```cpp
struct S
{
    S(int32 InInt, void* InPtr, float InFlt)
        : Int(InInt), Ptr(InPtr), Flt(InFlt) {}
    int32 Int;
    void* Ptr;
    float Flt;
};

TArray<S> SArr;

SArr.AddZeroed();  // [{ Int:0, Ptr:nullptr, Flt:0.0f }]

SArr.SetNumUninitialized(3);  // 扩容到 3，新元素未初始化
// 手动构造
new ((void*)(SArr.GetData() + 1)) S(5, (void*)0x12345678, 3.14f);
new ((void*)(SArr.GetData() + 2)) S(2, (void*)0x87654321, 2.72f);

// SetNumZeroed：扩容并用零填充新的元素
SArr.SetNumZeroed(5);  // 扩容到 5，新增的索引起始 4-5 用零填充
```

| 函数 | 行为 |
|------|------|
| `SetNum(N)` | 调整到 N 个元素，新增元素默认构造 |
| `SetNumUninitialized(N)` | 调整到 N 个元素，新增元素不初始化 |
| `SetNumZeroed(N)` | 调整到 N 个元素，新增元素置零 |

## Swap / SwapMemory

```cpp
TArray<int32> MyInts = {1, 2, 3, 4, 5};

MyInts.Swap(0, 4);        // {5, 2, 3, 4, 1}——带越界检查
MyInts.SwapMemory(0, 4);   // 不带越界检查，更快

// Swap(0, 5) 越界会导致崩溃
```

`Swap()` 有越界检查；`SwapMemory()` 不做检查，性能更优但不安全。

## 推荐使用方式

- 仅在只读遍历且数组不会被修改的场景使用 GetData
- 优先使用 `[]` 操作符或迭代器而非原始指针
- `AddUninitialized` / `InsertUninitialized` 适合性能敏感场景
- `AddZeroed` / `SetNumZeroed` 适合需要零值初始化的场景

> **代码位置**：[XGArrayActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/004_Array/XGArrayActor.cpp) — 函数 `XGOriginArray1~2()`, `XGZeroArray()`, `XGZeroAndUninitArray()`, `XGSwapArray()`
