# UPROPERTY 宏

控制属性在编辑器、蓝图、网络中的可见性和行为。

## 常用 Specifiers

| Specifier | 说明 |
|-----------|------|
| `BlueprintReadWrite` | 蓝图可读写 |
| `BlueprintReadOnly` | 蓝图只读 |
| `EditAnywhere` | 所有上下文均可编辑 |
| `EditDefaultsOnly` | 仅在 CDO/蓝图类默认值中可编辑 |
| `EditInstanceOnly` | 仅在关卡实例中可编辑 |
| `VisibleAnywhere` | 可见但不可编辑 |
| `VisibleInstanceOnly` | 仅在关卡实例中可见 |
| `Category` | 在编辑器细节面板中的分组名 |
| `Replicated` | 网络复制 |
| `Transient` | 不参与序列化 |
| `SaveGame` | 参与存档保存 |

## Meta 说明符

| Meta | 说明 |
|------|------|
| `Bitmask` | 将 int32 属性变为位掩码下拉列表 |
| `BitmaskEnum = "EColorBits"` | 将位掩码与指定枚举值关联 |
| `EditCondition = "bEdite"` | 条件控制属性是否可编辑 |
| `DisplayName` | 编辑器中显示的友好名称 |
| `Hidden` | 在编辑器中隐藏 |

## 支持的属性类型

| 类型 | 说明 |
|------|------|
| `uint8` / `int32` / `int64` | 整数类型 |
| `float` / `double` | 浮点类型 |
| `bool` / `uint32 : 1` | 布尔类型（位域写法） |
| `FString` / `FText` / `FName` | 字符串类型 |
| `TArray<Type>` | 数组容器 |
| `TSubclassOf<Class>` | 类引用（类型安全） |
| `UObject*` | 对象引用 |

## 注意事项

- `uint16`、`uint32`、`int8`、`int16` 默认无法暴露给 UPROPERTY（类型不完整支持）
- `FString` 默认值用 `= TEXT("")`
- `FText` 默认值用 `NSLOCTEXT("Namespace", "Key", "Value")`
- 二维数组 `TArray<TArray<T>>` 不支持 UPROPERTY
- 位域写法 `uint32 bIsHungry : 1` 将 bool 打包为位字段

## Bitmask 位掩码完整示例

```cpp
// 位掩码枚举定义
UENUM(Meta = (Bitflags))
enum class EColorBits1
{
    ECB_Red,
    ECB_Green,
    ECB_Blue
};

UENUM(Meta = (Bitflags, UseEnumValuesAsMaskValuesInEditor = "true"))
enum class EColorBits2
{
    ECB_Red   = 0x01,
    ECB_Green = 0x02,
    ECB_Blue  = 0x04
};

// 用作 UPROPERTY 位掩码
UPROPERTY(EditAnywhere, Meta = (Bitmask))
int32 BasicBits;

UPROPERTY(EditAnywhere, Meta = (Bitmask, BitmaskEnum = "EColorBits1"))
int32 ColorFlags1;

// 用作 UFUNCTION 参数位掩码
UFUNCTION(BlueprintCallable)
void MyFunction(UPARAM(meta = (Bitmask)) int32 BasicBitsParam);

UFUNCTION(BlueprintCallable)
void MyOtherFunction(UPARAM(meta = (Bitmask, BitmaskEnum = "EColorBits2")) int32 ColorFlagsParam);
```

参考实现：[XGPropertyActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/001_BaseType/XGPropertyActor.h)
