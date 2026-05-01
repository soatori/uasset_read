# UENUM 宏

## 基本语法

```cpp
UENUM(BlueprintType)
enum class EMYUENUM : uint8
{
    None,
    Base,
    Max UMETA(Hidden)
};
```

## 要点

| 特性 | 说明 |
|------|------|
| 底层类型 | **必须指定**底层类型（通常为 `uint8`），否则无法暴露给蓝图 |
| BlueprintType | 使枚举可在蓝图中作为变量类型 |
| `UMETA(Hidden)` | 隐藏指定枚举值（通常用于 `Max` 值，避免蓝图用户误选） |
| `UMETA(DisplayName = "友好名称")` | 设置编辑器中显示的友好名称 |
| 位掩码枚举 | 配合 `UENUM(Meta = (Bitflags))` 使用 |

## 完整示例

```cpp
UENUM(BlueprintType)
enum class EXGActorType : uint8
{
    None     UMETA(DisplayName = "未初始化"),
    NPC,
    Player,
    Max      UMETA(Hidden)
};
```

参考实现：[InterfaceActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/003_UInterface/InterfaceActor.h)

## 位掩码枚举

```cpp
UENUM(Meta = (Bitflags, UseEnumValuesAsMaskValuesInEditor = "true"))
enum class EColorBits2
{
    ECB_Red   = 0x01,
    ECB_Green = 0x02,
    ECB_Blue  = 0x04
};
```

位掩码枚举的值通常设为 2 的幂（`0x01`、`0x02`、`0x04`、`0x08` ...），配合 `UPROPERTY(Meta = (Bitmask))` 使用。

## 配套代码

| 枚举 | 代码文件 |
|------|----------|
| `EMYUENUM`（基本 BlueprintType 枚举） | [XGBaseStructEnum.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/001_BaseType/XGBaseStructEnum.h) |
| `EXGActorType`（带 UMETA(DisplayName/Hidden) 枚举） | [InterfaceActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/003_UInterface/InterfaceActor.h) |
| `EColorBits1` / `EColorBits2`（位掩码枚举） | [XGPropertyActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/001_BaseType/XGPropertyActor.h) |
