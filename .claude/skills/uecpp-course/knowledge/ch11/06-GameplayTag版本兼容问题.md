# GameplayTag 版本兼容问题

## 问题描述

在 UE5.5+ 版本中，`Get Owned Gameplay Tags` 节点的实现方式发生了变化：

| 版本 | 实现方式 |
|------|---------|
| UE5.4 及之前 | 直接作为 `UFUNCTION` 存在于 `IGameplayTagAssetInterface` 中 |
| UE5.5+ | 改为 `BlueprintFunctionLibrary` 包装器形式 |

## 影响

- `Get Owned Gameplay Tags` 节点的默认 **Self** 引脚可能不会自动填充目标 Actor
- 在 **Level Blueprint** 中问题更明显（没有默认 `self` 上下文）
- 在 Actor Blueprint 中部分情况下仍然会自动连接

## 修复方法

手动将目标 Actor 连接到 `Self` 引脚，不要依赖默认值。
