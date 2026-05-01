# TMap 迭代与日志输出

## 基于范围的 for 循环

TMap 支持 C++ 范围 for 循环。遍历时每个元素是 `TPair<KeyType, ValueType>`，通过 `Elem.Key` 和 `Elem.Value` 访问键和值：

```cpp
TMap<int32, FString> FruitMap;
FruitMap.Add(1, TEXT("Grapefruit"));
FruitMap.Add(2, TEXT("Pineapple"));
FruitMap.Add(3, TEXT("Melon"));

for (auto& Elem : FruitMap)
{
    // Elem 类型为 TPair<int32, FString>
    // Elem.Key     == int32
    // Elem.Value   == FString
    UE_LOG(LogTemp, Warning, TEXT("(%d, \"%s\")"), Elem.Key, *Elem.Value);
}
```

也可以显式声明 `TPair` 类型：

```cpp
for (const TPair<int32, FString>& Element : FruitMap)
{
    // 明确使用 TPair 类型，语义更清晰
    FPlatformMisc::LocalPrint(*FString::Printf(
        TEXT("(%d, \"%s\")\n"), Element.Key, *Element.Value));
}
```

## 迭代器遍历

使用 `CreateConstIterator()` 创建常量迭代器，通过 `It.Key()` 和 `It.Value()` 访问：

```cpp
for (auto It = FruitMap.CreateConstIterator(); It; ++It)
{
    FPlatformMisc::LocalPrint(*FString::Printf(
        TEXT("(%d, \"%s\")\n"), It.Key(), *It.Value()));
}
```

`CreateIterator()` 返回非常量迭代器，允许修改值。

## UE_LOG 日志输出

使用 `UE_LOG` 宏进行结构化日志输出：

```cpp
UE_LOG(LogTemp, Warning, TEXT("(%d, \"%s\")"), Elem.Key, *Elem.Value);
```

参数说明：
- `LogTemp` — 日志类别（Category）
- `Warning` — 日志级别（Verbosity）：`Error`、`Warning`、`Display`、`Log`、`Verbose`、`VeryVerbose`
- `TEXT(...)` — 格式化字符串
- `%d` — int32 占位符
- `%s` — 字符串占位符（需要 `*` 解引用 FString）

## 日志辅助：函数名标记

可以在日志中加入 `__FUNCTION__` 标记当前函数名，便于调试时溯源：

```cpp
FString Message = FString::Printf(TEXT("(%d, \"%s\")\n"), Element.Key, *Element.Value);
UE_LOG(LogTemp, Warning, TEXT("%s, %s"), *FString(__FUNCTION__), *Message);
```

## FPlatformMisc::LocalPrint

用于输出到 Visual Studio 输出窗口，与 UE_LOG 互补：

```cpp
FPlatformMisc::LocalPrint(*FString::Printf(TEXT("(%d, \"%s\")\n"), Elem.Key, *Elem.Value));
```

> **注意**：TMap 是无序容器，遍历顺序**不保证**与插入顺序一致。每次遍历的结果可能不同。

> **代码位置**：[MapActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/005_Map/MapActor.cpp) — `IterateMap()` 函数
