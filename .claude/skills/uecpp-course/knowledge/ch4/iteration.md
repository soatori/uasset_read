# TArray 迭代

## for-range 循环

TArray 支持 C++ 范围的 for 循环：

```cpp
TArray<FString> Arr = {TEXT("A"), TEXT("B"), TEXT("C")};

// 按值拷贝——每个元素都会被拷贝，开销大
for (FString Str : Arr)
{
    // 操作 Str（拷贝）
}

// 按引用——不会拷贝，可直接修改
for (FString& Str : Arr)
{
    Str += TEXT("!");
}

// 按 const 引用——不会拷贝，只读，推荐
for (const FString& Str : Arr)
{
    // 只读访问 Str
}
```

## 索引循环

```cpp
for (int32 Index = 0; Index != StrArr.Num(); ++Index)
{
    // 使用 StrArr[Index]
}
```

## CreateConstIterator

```cpp
for (auto It = StrArr.CreateConstIterator(); It; ++It)
{
    // 使用 *It 访问元素
}
```

TArray 提供的迭代器模式，功能和 for-range 类似。

## 三种迭代方式对比

| 方式 | 示例 | 特点 |
|------|------|------|
| for-range | `for (const T& Elem : Arr)` | 最简洁，推荐首选 |
| 索引循环 | `for (int32 i = 0; i < Num; ++i)` | 可获取索引，适合需要索引的场景 |
| CreateConstIterator | `for (auto It = Arr.CreateConstIterator(); It; ++It)` | 迭代器风格 |

## 性能建议

| 方式 | 是否拷贝 | 可修改 | 推荐场景 |
|------|----------|--------|----------|
| `T Elem : Arr` | 是 | 是 | 元素类型为轻量值类型（int32、float 等） |
| `T& Elem : Arr` | 否 | 是 | 需要修改元素内容 |
| `const T& Elem : Arr` | 否 | 否 | 只读访问，**大多数场景的首选** |

## 迭代时安全移除元素

在遍历数组时移除元素需要谨慎，否则会导致索引错位或越界。

### 错误示范——正向遍历中 RemoveAt

```cpp
// 问题：移除元素后后续元素前移，跳过检查
for (int32 Index = 0; Index != StrArr.Num(); ++Index)
{
    if (TEXT("of") == StrArr[Index])
    {
        StrArr.RemoveAt(Index);  // 移除后，后面的元素前移，Index++ 跳过了一个元素
    }
}
```

### 正确方式一——反向遍历

```cpp
for (int32 Index = StrArr.Num() - 1; Index >= 0; --Index)
{
    if (TEXT("of") == StrArr[Index])
    {
        StrArr.RemoveAt(Index);  // 从后往前移除，前移的元素已经遍历过
    }
}
```

### 正确方式二——先收集索引，再分帧移除

```cpp
TArray<int32> RemovedIndexArray;

// 第一遍：收集要移除的索引
for (int32 Index = StrArr.Num() - 1; Index >= 0; --Index)
{
    if (ShouldRemove(StrArr[Index]))
    {
        RemovedIndexArray.Add(Index);
    }
}

// 第二遍：统一移除
for (int32 RemovedLoopIndex = 0; RemovedLoopIndex != RemovedIndexArray.Num(); ++RemovedLoopIndex)
{
    StrArr.RemoveAt(RemovedIndexArray[RemovedLoopIndex]);
}
```

**注意**：在 WebSocket 等异步通信场景中，不要在回调中创建新的连接，应分帧执行移除操作。

> **代码位置**：[XGArrayActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/004_Array/XGArrayActor.cpp) — 函数 `XGLoopArray1~3()`, `XGLoopArray_Error/Right/Right_2()`
