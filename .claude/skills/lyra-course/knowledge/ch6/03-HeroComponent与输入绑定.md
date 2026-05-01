# HeroComponent 与输入绑定

## 概述

`ULyraHeroComponent` 是角色的"英雄"组件，负责输入绑定、ASC 初始化和相机模式代理。它同样是初始化状态机的参与者，在 GameplayReady 状态下执行输入绑定的最终设置。

## 类声明

```cpp
class ULyraHeroComponent : public UPawnComponent, public IGameFrameworkInitStateInterface
```

## 初始化状态机参与

- Feature Name：`"Hero"`（与 PawnExtension 的 `"PawnExtension"` 不同）
- `RegisterInitStateFeature()` 注册自身
- 监听 PawnExtension 的状态变化
- 在 `DataAvailable → DataInitialized` 阶段：
  - 初始化 ASC（调用 PawnExtension->InitializeAbilitySystem）
  - 绑定 AbilityActivated 事件
- 在 `DataInitialized → GameplayReady` 阶段：
  - OnSetupInputComponents 绑定输入

## ASC 初始化

- 通过 `ULyraAbilitySystemComponent*` 创建或获取 ASC
- ASC 的 OwnerActor 为 PlayerState，AvatarActor 为 Pawn
- 绑定 `AbilityActivated` 事件，检查激活的 Ability 是否应由相机处理
- 如果是相机 Ability，向相机组件发送事件

## 输入绑定（SetupPlayerInputComponent）

`OnSetupInputComponents` 是输入绑定的入口，在初始化状态机到达 GameplayReady 时触发：

1. 确保拥有有效的 PlayerController
2. 创建 `ULyraInputComponent`
3. 从 PawnData 获取 `InputConfig`
4. 调用 `InputConfig->BindAbilityActivation(...)` 将输入动作绑定到 GA
5. 绑定原生输入动作

## 相机模式代理

HeroComponent 作为相机模式切换的代理层：

- 处理需要相机响应的 Ability（如瞄准）
- 将 Ability 激活/取消事件转发到 `ULyraCameraComponent`
- 调用 `CameraComponent->ChangeCameraMode(...)` 切换相机模式

## 与其他组件的关系

```
ULyraHeroComponent
  ├── 依赖 PawnExtensionComponent 的初始化状态
  ├── 创建并初始化 ULyraAbilitySystemComponent
  ├── 控制 ULyraInputComponent 的绑定
  ├── 代理相机模式切换到 ULyraCameraComponent
  └── 监听 GameplayAbility 的激活/取消事件
```

## 代码引用

| 类 | 文件 |
|----|------|
| `ULyraHeroComponent` | [LyraHeroComponent.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/Character/LyraHeroComponent.h) |
