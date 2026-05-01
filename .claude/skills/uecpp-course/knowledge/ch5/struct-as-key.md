# TMap 结构体作为 Key 与 KeyFuncs

将自定义结构体作为 TMap 的键时，需要提供哈希和比较支持。有两种方式：**结构体重载**和**自定义 KeyFuncs**。

## 方式一：结构体重载 operator== 和 GetTypeHash

通过友元函数或成员函数为结构体提供 `operator==` 和 `GetTypeHash`：

### 定义结构体

```cpp
USTRUCT()
struct FXGMapInfo
{
    GENERATED_BODY()

    int32 Health = -1;
    FString NPCName = TEXT("None");

    FXGMapInfo() {}

    FXGMapInfo(FString InNPCName)
        : NPCName(InNPCName)
    {}

    bool operator==(const FXGMapInfo& Other) const
    {
        return NPCName == Other.NPCName;
    }

    friend uint32 GetTypeHash(const FXGMapInfo& Other)
    {
        return GetTypeHash(Other.NPCName);
    }
};
```

### 使用自定义结构体作为键

```cpp
TMap<FXGMapInfo, int32> MyNPCs;

MyNPCs.Add(FXGMapInfo(TEXT("Boss")), 1);
MyNPCs.Add(FXGMapInfo(TEXT("Player")), 2);
MyNPCs.Add(FXGMapInfo(TEXT("Tree")), 1);
MyNPCs.Add(FXGMapInfo(TEXT("player")), 3);   // 区分大小写，"player" ≠ "Player"

// 保证有至少 10 个 NormalEnemy
MyNPCs.FindOrAdd(FXGMapInfo(TEXT("NormalEnemy")), 10);

// 保证 Player 至少增加 4 个
int32& PlayerNum = MyNPCs.FindOrAdd(FXGMapInfo(TEXT("Player")));
PlayerNum += 4;
```

### 要点

- `operator==` 决定两个键是否相等，相等的键在 Map 中对应同一个槽位
- `GetTypeHash` 决定键的哈希桶位置，相等的键必须有相同的哈希值
- 区分大小写：`"player"` 和 `"Player"` 的哈希值不同，对应不同槽位
- `explicit` 关键字可防止隐式类型转换导致的意外构造

## 方式二：自定义 KeyFuncs

当无法修改键类型（如第三方库的结构体），或不想直接修改结构体的比较逻辑时，使用自定义 `KeyFuncs`。

### 定义键类型

```cpp
struct FMyStruct
{
    FString UniqueID = TEXT("");  // 参与哈希和比较
    float SomeFloat = 0.f;        // 不参与哈希和比较

    explicit FMyStruct(float InFloat)
        : UniqueID(FGuid::NewGuid().ToString())
        , SomeFloat(InFloat)
    {}
};
```

### 定义 KeyFuncs

`KeyFuncs` 继承自 `BaseKeyFuncs<TPair<KeyType, ValueType>, KeyInitType>`，提供 2 个类型定义和 3 个静态方法：

```cpp
template <typename ValueType>
struct TMyStructMapKeyFuncs : BaseKeyFuncs<TPair<FMyStruct, ValueType>, FString>
{
private:
    typedef BaseKeyFuncs<TPair<FMyStruct, ValueType>, FString> Super;

public:
    typedef typename Super::ElementInitType ElementInitType;
    typedef typename Super::KeyInitType     KeyInitType;

    // 从 TPair 中提取用于哈希/比较的键
    static KeyInitType GetSetKey(ElementInitType Element)
    {
        return Element.Key.UniqueID;
    }

    // 比较两个键是否相等
    static bool Matches(KeyInitType A, KeyInitType B)
    {
        return A.Compare(B, ESearchCase::CaseSensitive) == 0;
    }

    // 计算键的哈希值
    static uint32 GetKeyHash(KeyInitType Key)
    {
        return FCrc::StrCrc32(*Key);
    }
};
```

### 使用 KeyFuncs

在 TMap 模板参数中传入自定义 KeyFuncs：

```cpp
// KeyFuncs 指定为 TMyStructMapKeyFuncs<int32>
TMap<FMyStruct, int32, FDefaultSetAllocator, TMyStructMapKeyFuncs<int32>> MyMapToInt32;

MyMapToInt32.Add(FMyStruct(3.14f), 5);
MyMapToInt32.Add(FMyStruct(1.23f), 2);

// 也可以用于不同的 ValueType
TMap<FMyStruct, float, FDefaultSetAllocator, TMyStructMapKeyFuncs<float>> MyMapToFloat;
MyMapToFloat.Add(FMyStruct(3.14f), 50.f);
```

### KeyFuncs 的结构

| 成员 | 说明 |
|------|------|
| `ElementInitType` | TPair<KeyType, ValueType> 类型 |
| `KeyInitType` | 实际参与哈希和比较的字段类型（不同于 KeyType） |
| `GetSetKey()` | 从 TPair 中提取 KeyInitType |
| `Matches()` | 判断两个 KeyInitType 是否相等 |
| `GetKeyHash()` | 计算 KeyInitType 的哈希值 |

### FGuid 与 FGuid::NewGuid()

`FGuid` 是一个 128 位唯一标识符（A/B/C/D 四个 uint32 分量）。`FGuid::NewGuid()` 生成一个随机 GUID，用于唯一标识对象实例：

```cpp
FGuid NewID = FGuid::NewGuid();
FString IDString = NewID.ToString(EGuidFormats::Digits);
// 或使用：NewID.ToDebugString()
```

在上例中，`FMyStruct` 的构造函数使用 `FGuid::NewGuid().ToString()` 生成唯一 ID，使每个实例拥有独立的标识符。

### FCrc::StrCrc32

`FCrc::StrCrc32()` 对字符串计算 CRC32 哈希值，常用于将 FString 映射为 `uint32` 哈希：

```cpp
uint32 Hash = FCrc::StrCrc32(*SomeString);  // 计算 CRC32 哈希
```

## 两种方式对比

| 方式 | 适用场景 | 修改范围 |
|------|----------|----------|
| operator== + GetTypeHash 重载 | 自己定义的结构体 | 直接修改结构体定义 |
| 自定义 KeyFuncs | 第三方库、不可修改的结构体 | 单独定义 KeyFuncs 类，不侵入原始类型 |

> **重要**：使用自定义结构体作为 Key 时，一旦插入 Map，**不应再修改键中参与哈希计算的字段**，否则会导致容器内部状态不一致。

> **代码位置**：[MapActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/005_Map/MapActor.h) — `FXGMapInfo` 结构体 / `FMyStruct` 结构体 / `TMyStructMapKeyFuncs` 模板类 / [MapActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/005_Map/MapActor.cpp) — `StructMap()`, `StructKeyFunMap()` 函数
