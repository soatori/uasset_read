# 动画蓝图与 Tag 映射

## ULyraAnimInstance

`ULyraAnimInstance` 继承自 `UAnimInstance`，是 Lyra 中所有动画蓝图基类。

### 地面距离

```cpp
UPROPERTY(BlueprintReadOnly)
float GroundDistance;
```

- `NativeUpdateAnimation` 中从 `ULyraCharacterMovementComponent::GetGroundInfo()` 获取地面距离
- 用于动画蓝图中的混合空间或状态机控制

### 初始化

```cpp
void ULyraAnimInstance::NativeInitializeAnimation()
{
    Super::NativeInitializeAnimation();
    AActor* OwningActor = GetOwningActor();
    if (UAbilitySystemComponent* ASC =
        UAbilitySystemGlobals::GetAbilitySystemComponentFromActor(OwningActor))
    {
        GameplayTagPropertyMap.Initialize(this, ASC);
    }
}
```

- 通过 `UAbilitySystemGlobals::GetAbilitySystemComponentFromActor` 获取 ASC
- 将 GameplayTagPropertyMap 与 ASC 绑定注册

## FGameplayTagBlueprintPropertyMap

将 GameplayTag 的状态自动映射到动画蓝图的属性变量。

### 数据结构

```cpp
struct FGameplayTagBlueprintPropertyMapping {
    FGameplayTag TagToMap;                           // 要监听的 Tag
    TFieldPath<FProperty> PropertyToEdit;            // 要设置的属性引用
    FName PropertyName;                              // 属性名称（用于查找）
    FGuid PropertyGuid;                              // 属性 GUID
    FDelegateHandle DelegateHandle;                  // 事件句柄
};

struct FGameplayTagBlueprintPropertyMap {
    TArray<FGameplayTagBlueprintPropertyMapping> PropertyMappings;
    TWeakObjectPtr<UObject> CachedOwner;              // 缓存的 Owner
    TWeakObjectPtr<UAbilitySystemComponent> CachedASC; // 缓存的 ASC
};
```

### 注册流程

```cpp
void Initialize(UObject* Owner, UAbilitySystemComponent* ASC)
{
    CachedOwner = Owner;
    CachedASC = ASC;
    for (auto& Mapping : PropertyMappings)
    {
        // 查找属性的 TFieldPath
        // 检查属性类型（bool/int/float）
        // 注册 GameplayTag 事件
        ASC->RegisterAndCallGameplayTagEvent(
            Mapping.TagToMap,
            FOnGameplayTagValueChange::FDelegate::CreateUObject(
                Owner, &UGameplayTagBlueprintPropertyMap::GameplayTagEventCallback,
                &Mapping),
            EGameplayTagEventType::NewOrRemoved);
    }
}
```

### 回调处理

```cpp
void GameplayTagEventCallback(
    const FGameplayTag Tag, int32 NewCount,
    FGameplayTagBlueprintPropertyMapping* RegisteredMapping)
{
    // 根据 Tag 找到对应的 PropertyMapping
    // 根据属性类型设置值：
    switch (PropertyType) {
        case FBoolProperty:  *bool_value   = NewCount > 0;     break;
        case FIntProperty:   *int32_value  = NewCount;          break;
        case FFloatProperty: *float_value  = float(NewCount);   break;
    }
}
```

- bool：`NewCount > 0` 时 true，否则 false
- int：直接赋值 `NewCount`
- float：隐式转换 `float(NewCount)`

## 典型用法

在动画蓝图中暴露 `GameplayTagPropertyMap` 为 `EditDefaultsOnly` 可编辑属性，在细节面板中配置：

| Tag | 属性名 | 类型 | 效果 |
|-----|--------|------|------|
| `Status.Crouching` | bIsCrouching | bool | 蹲伏时 Blend 到蹲伏动画 |
| `Movement.Mode.Walking` | bIsWalking | bool | 行走时 Blend 到行走动画 |
| `Status.Stunned` | StunCount | int | 被击晕后播放受击动画 |

## 代码引用

| 类/结构 | 文件 |
|---------|------|
| `ULyraAnimInstance` | [LyraAnimInstance.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/Animation/LyraAnimInstance.h) |
| `FGameplayTagBlueprintPropertyMap` | [LyraAnimInstance.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/Animation/LyraAnimInstance.h) |
| `FGameplayTagBlueprintPropertyMapping` | [LyraAnimInstance.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/Animation/LyraAnimInstance.h) |
