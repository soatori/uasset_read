# TArray 高级查询

## IndexOfByKey()

通过不同的 Key 类型查找元素索引：

```cpp
TArray<FCharacterInfo> Characters;

// 按 int32 ID 查找（Key 类型与元素类型不同）
int32 Index = Characters.IndexOfByKey(5);  // 查找 ID == 5 的元素
```

需要元素类型和 Key 类型之间有 `operator==`。如果 Key 类型与元素类型相同，也可以工作，但更推荐 `Find()`。

## FindByKey()

```cpp
FCharacterInfo* Found = Characters.FindByKey(5);
```

**注意**：`FindByKey()` 返回的是**元素指针**而非索引。如果元素是值类型，返回的是数组内部元素的地址。如果没找到，返回 `nullptr`。

### 指针数组的特殊情况

当数组元素本身就是指针时（如 `TArray<AActor*>`）：

```cpp
AActor* Found = Actors.FindByKey(TargetID);  // 返回 T**，需要额外解引用
```

此时 `FindByKey` 返回 `T**`（指向指针的指针），使用方式与值类型不同。

## FindByPredicate()

使用 Lambda 查找元素，返回元素指针：

```cpp
FCharacterInfo* Found = Characters.FindByPredicate([](const FCharacterInfo& Info)
{
    return Info.ID == 5;
});

if (Found)
{
    // 使用 Found->Name, Found->Money 等
}
```

推荐的安全使用模式：

```cpp
if (FString* Found = StrArray.FindByPredicate(Predicate))
{
    // 在 if 块内使用 Found
}
// 离开 if 块后指针可能失效
```

## FilterByPredicate()

返回一个新数组，包含所有匹配谓词的元素：

```cpp
TArray<int32> Numbers = {1, 2, 3, 4, 5, 6};
TArray<int32> EvenNumbers = Numbers.FilterByPredicate([](const int32& Val)
{
    return Val % 2 == 0;
});
// EvenNumbers = {2, 4, 6}
```

`FilterByPredicate` 内部使用 `Emplace` 将匹配的元素添加到新数组。

## IndexOfByPredicate()

使用 Lambda 查找元素的索引：

```cpp
int32 Index = StrArr.IndexOfByPredicate([](const FString& Str)
{
    return Str.Contains(TEXT("r"));
});
```

返回第一个匹配元素的索引，找不到返回 `INDEX_NONE`。

## 实战案例：伤害系统

判断一个 Actor 是否已经在本轮伤害中被击中：

```cpp
TArray<AActor*> HitActors;

bool bAlreadyHit = HitActors.ContainsByPredicate([&](const AActor* Target)
{
    return Target == SomeActor;
});

if (!bAlreadyHit)
{
    // 应用伤害
    HitActors.Add(SomeActor);
}
```

> **代码位置**：[XGArrayActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/004_Array/XGArrayActor.cpp) — 函数 `XGFindElementByKey()`, `XGCopyArray()`
