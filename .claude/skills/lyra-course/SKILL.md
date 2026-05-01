# lyra-course

| 字段 | 值 |
|------|-----|
| Skill 名称 | lyra-course |
| 版本 | UE 5.6 |
| 分类 | Unreal Engine 项目架构分析 |
| 触发词 | Lyra、LyraGame、Lyra 架构 |

---

## Skill 说明

### 能做什么

- 解释 Lyra 项目中任意系统/类的职责、位置和设计意图
- 指导在 Lyra 框架下添加新的 GameFeature、武器、装备、技能、UI 等
- 分析跨系统的调用链路（如：从输入到技能释放的完整路径）
- 提供 Lyra 核心设计模式的代码级参考（含相对路径和关键行号）
- 诊断常见的框架使用错误（如 InitState 顺序、AbilitySet 遗漏注册等）
- 指导从 Lyra Starter 项目出发进行游戏原型开发

### 不能做什么

- **不包含 Lyra 项目实际源代码** — 需配合 Lyra Starter 工程使用，代码路径以 `Source/LyraGame/` 为根
- **不覆盖所有系统细节** — 聚焦核心架构模式，极端边缘情况请参考 Lyra 源码
- **不包含蓝图/Verse 教程** — 仅关注 C++ 层架构
- **不包含网络复制深入分析** — 仅提及关键复制机制

---

## 项目全景

Lyra 是一个**模块化、数据驱动的多人射击游戏框架**。其核心设计理念：

- **Experience 驱动**：整个游戏的加载和行为由 Experience 数据资产编排
- **GameFeature 插件化**：功能模块以 GameFeature Plugin 形式动态加载/卸载
- **GAS 为核心**：所有角色能力通过 GameplayAbilitySystem 实现
- **水平分层 + 垂直切片**：每层（Input/GAS/Camera/UI）独立可替换，跨层通过 GameplayTag 和接口通信

### 源码目录结构

```
Source/LyraGame/
├── AbilitySystem/              # GAS 扩展（AbilitySet、Execution、TagRelationship、Cost 等）
├── Camera/                     # 相机系统（CameraMode、CameraAssist）
├── Character/                  # 角色类层级（LyraCharacter、LyraHeroComponent、HealthComponent）
├── Equipment/                  # 装备系统（Definition、Instance、Manager）
├── GameModes/                  # GameMode、GameState、PlayerState + Experience 框架
├── Input/                      # 输入系统（InputConfig、MappableConfig）
├── Inventory/                  # 库存系统（Definition、Instance、List、Manager）
├── Messages/                   # 消息协议（VerbMessage、NotificationMessage、MessageReplication）
├── Player/                     # PlayerController、PlayerState、PlayerSpawningManager
├── Weapons/                    # 武器系统（WeaponSpawner、Spread 曲线）
├── Cosmetics/                  # 换装系统（CharacterPart、Controller/Pawn 组件）
├── Teams/                      # 队伍系统（TeamSubsystem、PublicInfo）
├── UI/                         # UI 系统（PrimaryGameLayout、HUDLayout、IndicatorSystem）
├── GameFeatures/               # GameFeature 插件
└── Feedback/                   # 反馈系统
```

Plugins/
```
Plugins/GameplayMessageRouter/   # 通用 GameplayTag 消息路由子系统
```

---

## 模块依赖关系

```
Experience ──→ GameFeature 插件（动态激活子系统）
    │
    ├──→ GAS（AbilitySystemComponent + AttributeSet + GameplayAbility）
    │       │
    │       ├──→ HealthComponent（将 HealthSet 属性变化转为游戏事件）
    │       ├──→ Equipment（AbilitySet 通过 SourceObject 回溯）
    │       ├──→ Inventory（InventoryItemInstance 持有 AbilitySet）
    │       ├──→ Weapons（Spread/Heat 曲线通过 ILyraAbilitySourceInterface）
    │       └──→ GamePhase（GA 驱动游戏阶段切换）
    │
    ├──→ Character
    │       ├──→ HeroComponent（协调 Input/Camera/ASC）
    │       ├──→ PawnExtensionComponent（InitState 状态机）
    │       ├──→ HealthComponent（死亡状态机 + 事件分发）
    │       └──→ Cosmetics（CharacterPart 换装）
    │
    ├──→ Input ──→ EnhancedInput ──→ GAS（InputTag 绑定 GA）
    │
    ├──→ Camera（CameraMode 栈混合）
    │
    ├──→ UI（PrimaryGameLayout 四层栈）
    │
    ├──→ Messages ──→ GameplayMessageRouter（Tag 驱动的事件总线）
    │
    └──→ Teams ──→ Indicators
```

---

## 关键类索引

### Experience 层

| 类名 | 文件路径 | 职责 |
|------|---------|------|
| ULyraExperienceDefinition | `Source/LyraGame/GameModes/LyraExperienceDefinition.h` | Experience 数据资产，定义 GameFeature 列表和默认 Pawn/Controller/HUD |
| ULyraExperienceManager | `Source/LyraGame/GameModes/LyraExperienceManager.h` | 处理 Experience 加载状态和 Action 执行 |
| ULyraExperienceActionSet | `Source/LyraGame/GameModes/LyraExperienceActionSet.h` | 聚合多个 UGameFeatureAction |

### Character 层

| 类名 | 文件路径 | 职责 |
|------|---------|------|
| ALyraCharacter | `Source/LyraGame/Character/LyraCharacter.h` | 角色基类，实现 IAbilitySystemInterface、IGameplayTagAssetInterface、ILyraTeamAgentInterface |
| ULyraPawnExtensionComponent | `Source/LyraGame/Character/LyraPawnExtensionComponent.h` | 管理 Pawn 的 InitState 状态机，协调 ASC 生命周期 |
| ULyraHeroComponent | `Source/LyraGame/Character/LyraHeroComponent.h` | 玩家专属组件，管理输入绑定、相机和 ASC InitState |
| ALyraPlayerState | `Source/LyraGame/Player/LyraPlayerState.h` | 持有 ASC，网络拥有者，管理 TagStack |
| ULyraHealthComponent | `Source/LyraGame/Character/LyraHealthComponent.h` | 生命值组件，将 HealthSet 属性变化转为死亡状态机事件 |
| ULyraCharacterMovementComponent | `Source/LyraGame/Character/LyraCharacterMovementComponent.h` | 移动组件，Polar 加速度同步 + Tag 控制运动 |

### GAS 层

| 类名 | 文件路径 | 职责 |
|------|---------|------|
| ULyraAbilitySet | `Source/LyraGame/AbilitySystem/LyraAbilitySet.h` | 聚合 GA/GE/AttributeSet 的可配置数据资产 |
| ULyraGameplayAbility | `Source/LyraGame/AbilitySystem/Abilities/LyraGameplayAbility.h` | GA 基类，加入 ActivationGroup、AdditionalCosts 和额外触发事件 |
| ULyraAbilitySystemComponent | `Source/LyraGame/AbilitySystem/LyraAbilitySystemComponent.h` | ASC 扩展，管理输入激活三阶段管线（Pressed/Held/Released） |
| ULyraAbilityCost | `Source/LyraGame/AbilitySystem/Abilities/LyraAbilityCost.h` | 抽象消耗基类，CheckCost/ApplyCost 接口 |
| ULyraAbilityTagRelationshipMapping | `Source/LyraGame/AbilitySystem/LyraAbilityTagRelationshipMapping.h` | Cancel/Block 标签关系映射表 |
| ULyraHealthSet | `Source/LyraGame/AbilitySystem/Attributes/LyraHealthSet.h` | 生命值属性集，含 ClampAttribute 机制 |
| ULyraCombatSet | `Source/LyraGame/AbilitySystem/Attributes/LyraCombatSet.h` | 战斗属性集 |
| ULyraDamageExecution | `Source/LyraGame/AbilitySystem/Executions/LyraDamageExecution.h` | 自定义 GEEC 伤害计算 |
| ULyraGameplayEffectContext | `Source/LyraGame/AbilitySystem/LyraGameplayEffectContext.h` | 扩展 GEContext，携带 CartridgeID |

### Equipment 层

| 类名 | 文件路径 | 职责 |
|------|---------|------|
| ULyraEquipmentDefinition | `Source/LyraGame/Equipment/LyraEquipmentDefinition.h` | 装备定义数据资产，定义实例类型和 AbilitySet |
| ULyraEquipmentInstance | `Source/LyraGame/Equipment/LyraEquipmentInstance.h` | 装备实例，运行时持有 AbilitySet 和 SpawnedActor |
| ULyraEquipmentManagerComponent | `Source/LyraGame/Equipment/LyraEquipmentManagerComponent.h` | 装备管理组件，使用 FastArray 复制，管理 List |
| ULyraQuickBarComponent | `Source/LyraGame/Equipment/LyraQuickBarComponent.h` | 快捷栏组件，管理当前装备槽位切换 |

### Input 层

| 类名 | 文件路径 | 职责 |
|------|---------|------|
| ULyraInputConfig | `Source/LyraGame/Input/LyraInputConfig.h` | Tag→InputAction 映射数据资产 |
| ULyraInputComponent | `Source/LyraGame/Input/LyraInputComponent.h` | 绑定辅助类，按 Tag 自动绑定 GA |

### Camera 层

| 类名 | 文件路径 | 职责 |
|------|---------|------|
| ULyraCameraComponent | `Source/LyraGame/Camera/LyraCameraComponent.h` | Pawn 相机组件，持有 CameraModeStack |
| ULyraCameraMode | `Source/LyraGame/Camera/LyraCameraMode.h` | 相机模式基类，定义视角/距离/偏移 |
| ULyraCameraModeStack | `Source/LyraGame/Camera/LyraCameraMode.h` | 相机模式栈，自底向上混合，定义在 LyraCameraMode.h 中 |
| ULyraCameraAssistInterface | `Source/LyraGame/Camera/LyraCameraAssistInterface.h` | 相机辅助接口 |

### UI 层

| 类名 | 文件路径 | 职责 |
|------|---------|------|
| UPrimaryGameLayout | `Plugins/CommonGame/Source/Public/PrimaryGameLayout.h` | 顶层 UI 布局，管理四层 Widget 栈 |
| ULyraHUDLayout | `Source/LyraGame/UI/LyraHUDLayout.h` | HUD 根布局，响应 PlayerState 变化 |
| ULyraHUD | `Source/LyraGame/UI/LyraHUD.h` | HUD 基类，创建 PrimaryGameLayout |

### Cosmetics 层

| 类名 | 文件路径 | 职责 |
|------|---------|------|
| ULyraPawnComponent_CharacterParts | `Source/LyraGame/Cosmetics/LyraPawnComponent_CharacterParts.h` | Pawn 端换装组件，FastArray 驱动 |
| ULyraCosmeticCheats | `Source/LyraGame/Cosmetics/LyraCosmeticCheats.h` | Controller 端换装授权组件 |

### Teams 层

| 类名 | 文件路径 | 职责 |
|------|---------|------|
| ULyraTeamSubsystem | `Source/LyraGame/Teams/LyraTeamSubsystem.h` | 队伍子系统，管理 PublicInfo/PrivateInfo |
| ALyraTeamPublicInfo | `Source/LyraGame/Teams/LyraTeamPublicInfo.h` | 队伍公开信息（显示名、Tag），网络广播 |
| ALyraTeamPrivateInfo | `Source/LyraGame/Teams/LyraTeamPrivateInfo.h` | 队伍私有信息（仅服务器） |
| ULyraTeamDisplayAsset | `Source/LyraGame/Teams/LyraTeamDisplayAsset.h` | 队伍显示资产（颜色、材质） |

### Indicators 层

| 类名 | 文件路径 | 职责 |
|------|---------|------|
| UIndicatorDescriptor | `Source/LyraGame/UI/IndicatorSystem/IndicatorDescriptor.h` | 指示器描述符，定义场景到屏幕的映射 |
| SActorCanvas | `Source/LyraGame/UI/IndicatorSystem/SActorCanvas.h` | Slate 控件，在屏幕空间渲染 Indicator |

### Cheats 层

| 类名 | 文件路径 | 职责 |
|------|---------|------|
| ULyraCheatManager | `Source/LyraGame/Player/LyraCheatManager.h` | CheatManager 基类，支持 CheatExtension |

### Player 层

| 类名 | 文件路径 | 职责 |
|------|---------|------|
| ULyraPlayerSpawningManagerComponent | `Source/LyraGame/Player/LyraPlayerSpawningManagerComponent.h` | 玩家生成管理器，按队伍和优先级分配生成点 |

### Inventory 层

| 类名 | 文件路径 | 职责 |
|------|---------|------|
| ULyraInventoryItemDefinition | `Source/LyraGame/Inventory/LyraInventoryItemDefinition.h` | 物品定义数据资产，含 Fragment 数组 |
| ULyraInventoryItemFragment | `Source/LyraGame/Inventory/LyraInventoryItemDefinition.h` | 物品片段基类，EditInlineNew 组合式扩展 |
| ULyraInventoryItemInstance | `Source/LyraGame/Inventory/LyraInventoryItemInstance.h` | 物品运行时实例，Replicated，含 StatTags |
| FLyraInventoryList | `Source/LyraGame/Inventory/LyraInventoryManagerComponent.h` | FFastArraySerializer 物品清单 |
| ULyraInventoryManagerComponent | `Source/LyraGame/Inventory/LyraInventoryManagerComponent.h` | 库存管理组件，提供 Add/Remove/Consume API |
| IPickupable | `Source/LyraGame/Inventory/IPickupable.h` | 可拾取接口，返回 FInventoryPickup |
| ALyraWeaponSpawner | `Source/LyraGame/Weapons/LyraWeaponSpawner.h` | 武器生成器，支持拾取—冷却—重生循环 |

### Messages 层

| 类名 | 文件路径 | 职责 |
|------|---------|------|
| UGameplayMessageSubsystem | `Plugins/GameplayMessageRouter/.../GameplayMessageSubsystem.h` | 消息路由子系统，基于 GameplayTag 的发布—订阅 |
| FLyraVerbMessage | `Source/LyraGame/Messages/LyraVerbMessage.h` | 动作消息协议（谁对谁做了什么） |
| FLyraVerbMessageReplication | `Source/LyraGame/Messages/LyraVerbMessageReplication.h` | FFastArraySerializer 消息复制 |
| UGameplayMessageProcessor | `Source/LyraGame/Messages/GameplayMessageProcessor.h` | 消息处理器基类，模板方法模式 |

### GamePhase 层

| 类名 | 文件路径 | 职责 |
|------|---------|------|
| ULyraGamePhaseAbility | `Source/LyraGame/AbilitySystem/Phases/LyraGamePhaseAbility.h` | 阶段能力，GA 驱动游戏流程阶段切换 |
| ULyraGamePhaseSubsystem | `Source/LyraGame/AbilitySystem/Phases/LyraGamePhaseSubsystem.h` | 阶段子系统，管理阶段互斥和观察者注册 |

---

## 核心设计模式

### 模式一：Experience 框架（3 阶段加载）

Experience 将游戏启动流程分为 3 个阶段：

```
ExperienceDefinition（数据资产）
    │  定义：GameFeature 插件列表、默认 Pawn/Controller/HUD/GameMode
    │  存放：Content/Game/Blueprints/Experiences/
    │
    ▼
ExperienceManagerComponent（状态机）
    │  状态流：Inactive → WaitingForAction → LoadingActions → Loaded → Deactivating
    │  路径：Source/LyraGame/GameModes/LyraExperienceManagerComponent.h
    │
    ▼
UGameFeatureAction（加载动作，Engine 原生类）
    │  Lyra 通过 ExperienceActionSet 聚合多个 GameFeatureAction
    │  路径：通过 ULyraExperienceActionSet 间接引用
```

Lyra 的 ExperienceActionSet 持有 `TArray<TObjectPtr<UGameFeatureAction>>`，由 Engine 原生 `UGameFeatureAction` 子类处理插件激活、GameMode 切换等操作。可在 Project Settings 中配置 GameFeature Plugin 的 Actions 列表，无需自定义 Lyra 层 Action 类。

详细参考：[references/Experience框架与加载流程.md](references/Experience框架与加载流程.md)

---

### 模式二：InitState 初始化状态机

Lyra 用 4 态状态机协调 Pawn 各组件（ASC/Input/Camera/Movement）的初始化顺序：

```
Spawned ──→ DataAvailable ──→ DataInitialized ──→ GameplayReady
```

**参与者**：实现 `IGameFrameworkInitStateInterface` 的组件（接口来自 Engine 模块 `Components/GameFrameworkInitStateInterface.h`）

```
class IGameFrameworkInitStateInterface
{
    // 返回此 Actor 期望注册的状态
    virtual FName GetFeatureName() const = 0;

    // 返回此 Actor 依赖哪个 Feature 的哪个状态
    virtual FName GetRequiredState() const = 0;

    // 返回此 Actor 达到哪个状态后，依赖它的其他 Actor 可以继续
    virtual FName GetPrerequisiteState() const = 0;

    // 状态变更通知
    virtual void OnStateChanged(FName OldState, FName NewState) = 0;
};
```

**关键实现**：

| 组件 | 文件路径 | 注册状态 | 前置条件 |
|------|---------|---------|---------|
| ULyraPawnExtensionComponent | `Character/LyraPawnExtensionComponent.h` | DataAvailable | Spawned |
| ULyraHeroComponent | `Character/LyraHeroComponent.h` | DataInitialized | DataAvailable |
| UAbilitySystemComponent | GAS 模块 | GameplayReady | DataInitialized |

注册方式：
```
// ULyraPawnExtensionComponent::OnRegister()
// 向全局 InitState 管理器注册本组件
RegisterInitStateFeature();
```

详细参考：[references/InitState初始化状态机.md](references/InitState初始化状态机.md)

---

### 模式三：Equipment Fragment（三层设计）

装备系统分为三层，职责分离：

```
ULyraEquipmentDefinition（定义层）
    │  作为 PrimaryDataAsset，定义 Instance 类型和 AbilitySet
    │  路径：Source/LyraGame/Equipment/LyraEquipmentDefinition.h
    │
    ▼
ULyraEquipmentInstance（实例层）
    │  运行时实例，持有 GrantedAbilitySet 和 SpawnedActor
    │  路径：Source/LyraGame/Equipment/LyraEquipmentInstance.h
    │
    ▼
ULyraEquipmentManagerComponent（管理层）
    │  FastArray 同步列表（FLyraEquipmentList）
    │  路径：Source/LyraGame/Equipment/LyraEquipmentManagerComponent.h
```

装备加入后的 AbilitySet 授予链路：
```
EquipmentManagerComponent::AddEquipment()
    → EquipmentInstance.SpawnEquipmentActor()
    → EquipmentDefinition.GrantedAbilities（读取 AbilitySet）
    → ASC::GiveAbility() / ASC::InitStats()
    → EquipmentInstance 记录 Granted Handles（以便移除时回收）
```

**SourceObject 回溯**：GA 可通过 `GetSourceObject()` 回溯到 EquipmentInstance，再回溯到 EquipmentDefinition，从而在 GEContext 中携带装备信息（如 CartridgeID）。

```
// GA 中获取来源装备
ULyraEquipmentInstance* EquipInst = Cast<ULyraEquipmentInstance>(
    GetAbilitySourceObject()
);
```

详细参考：[references/装备与武器系统.md](references/装备与武器系统.md)

---

### 模式四：Input Config（Tag→Action 映射）

输入系统采用 **Tag 驱动**方式，将输入与 GameplayAbility 解耦：

```
EnhancedInput InputAction
    │  ULyraInputConfig 维护 Tag→InputAction 映射
    │  路径：Source/LyraGame/Input/LyraInputConfig.h
    ▼
InputTag（如 InputTag.Move、InputTag.Jump）
    │  ULyraInputComponent 按 Tag 自动绑定
    ▼
GameplayAbility（通过 InputTag 激活）
```

```
// ULyraInputConfig 核心结构
UCLASS()
class ULyraInputConfig : public UDataAsset
{
    GENERATED_BODY()

public:
    // Tag→InputAction 映射
    UPROPERTY(EditDefaultsOnly, Category = "Input")
    TArray<FLyraInputAction> InputActions;

    // 根据 Tag 查找 InputAction
    const UInputAction* FindInputActionForTag(const FGameplayTag& Tag) const;
};

USTRUCT()
struct FLyraInputAction
{
    UPROPERTY(EditDefaultsOnly)
    FGameplayTag InputTag;

    UPROPERTY(EditDefaultsOnly)
    TObjectPtr<UInputAction> InputAction;
};
```

绑定到 GA 的方式：
```
// ULyraHeroComponent::InitializePlayerInput()
// 路径：Source/LyraGame/Character/LyraHeroComponent.h

ULyraInputComponent* LyraInputComp = ...;
ULyraInputConfig* InputConfig = ...;

// 按 Tag 绑定 GA
LyraInputComp->BindAbilityActions(
    InputConfig,                 // Tag→Action 映射
    InputHandles,                // 输出句柄
    this,                        // UObject
    &ThisClass::OnInputStarted,
    &ThisClass::OnInputTriggered,
    &ThisClass::OnInputCompleted
);
```

详细参考：[references/输入系统与InputConfig.md](references/输入系统与InputConfig.md)

---

### 模式五：Camera Stack（三层相机架构）

相机系统分为三个层次：

```
ULyraCameraComponent（组件层）
    │  挂载在 Pawn 上，持有 CameraModeStack
    │  路径：Source/LyraGame/Camera/LyraCameraComponent.h
    │
    ▼
ULyraCameraModeStack（栈层）
    │  管理活跃 CameraMode 列表，自底向上混合
    │  路径：Source/LyraGame/Camera/LyraCameraMode.h（定义在同一文件）
    │
    ▼
ULyraCameraMode（模式层）
    │  定义具体相机行为（视角/距离/偏移/弹簧臂）
    │  路径：Source/LyraGame/Camera/LyraCameraMode.h
```

混合计算过程：
```
CameraModeStack::GetBlendInfo()
    → 遍历激活的 CameraMode 列表
    → 从底部 mode0 开始 blend 到顶部 modeN
    → 最终 BlendInfo = mode0 * (1-blend) + mode1 * blend
```

```cpp
// 添加自定义 CameraMode
void AMyPawn::SetupCustomCamera()
{
    ULyraCameraComponent* CameraComp = FindComponentByClass<ULyraCameraComponent>();
    if (CameraComp)
    {
        // 默认模式：第三人称
        CameraComp->AddCameraModeClass(ULyraCameraMode_ThirdPerson::StaticClass());

        // 叠加模式：瞄准缩放
        CameraComp->AddCameraModeClass(ULyraCameraMode_AimDownSights::StaticClass());
    }
}
```

---

### 模式六：UI Layer Stack（四层 UI 栈）

UI 系统通过 `UPrimaryGameLayout` 管理四层 Widget 栈，每层独立：

```
Game（游戏层）      — HUD、准星、血条、技能冷却
GameMenu（菜单层）   — 游戏内菜单（ESC 菜单）
Menu（功能层）       — 背包、设置、商店
Modal（模态层）      — 提示框、确认框（BlockInput）
```

```
// 路径：Plugins/CommonGame/Source/Public/PrimaryGameLayout.h
UCLASS()
class UPrimaryGameLayout : public UCommonActivatableWidgetStack
{
    GENERATED_BODY()

public:
    // 四层栈访问
    UCommonActivatableWidgetStack* GetGameStack() const;
    UCommonActivatableWidgetStack* GetGameMenuStack() const;
    UCommonActivatableWidgetStack* GetMenuStack() const;
    UCommonActivatableWidgetStack* GetModalStack() const;
};
```

向指定层 Push Widget 的方式：
```
// 向 Game 层 Push HUD
UPrimaryGameLayout* RootLayout = UPrimaryGameLayout::GetPrimaryGameLayout(Controller);
RootLayout->GetGameStack()->AddWidget(CreateWidget<UMyHUDWidget>(Controller));
```

Lyra 中 HUD 的默认结构：
```
ALyraHUD（路径：Source/LyraGame/UI/LyraHUD.h）
    └── ULyraHUDLayout（根 Widget）
            ├── TopLeft Tier（队伍信息、玩家列表）
            ├── LowerLeft Tier（生命值、弹药）
            ├── LowerMiddle Tier（快捷栏、装备切换）
            └── LowerRight Tier（击杀信息、通知）
```

详细参考：[references/UI层栈架构.md](references/UI层栈架构.md)

---

### 模式七：HealthComponent 死亡状态机

生命值组件在 GAS 属性系统和游戏表现层之间扮演桥梁角色，核心是 3 态死亡状态机：

```
NotDead ──→ DeathStarted ──→ DeathFinished
```

**文件**：`Source/LyraGame/Character/LyraHealthComponent.h`

```
ULyraHealthComponent
  InitializeWithAbilitySystem(ASC)
    → HealthSet 的 AttributeChangeDelegate 绑定
    → OnHealthChanged / OnMaxHealthChanged
    → StartDeath / FinishDeath 状态控制

3 态死亡状态机：
  NotDead（正常状态）
    → 收到 GE 伤害，Health 归零
    → StartDeath → bDead = true, 状态 = DeathStarted
    → OnDeathStarted.Broadcast()

  DeathStarted（死亡表现触发）
    → 触发布娃娃、死亡动画等表现
    → 延迟后调用 FinishDeath → 状态 = DeathFinished
    → OnDeathFinished.Broadcast()

  DeathFinished（死亡完成）
    → 角色完全死亡，响应 Ragdoll 结束或重生
```

完整调用链路：

```
GE Damage → ULyraDamageExecution::Execute
  → HealthSet::PostAttributeChange（Health 归零检测）
  → ULyraHealthComponent::OnHealthChanged
  → StartDeath() → bDead = true
  → OnDeathStarted.Broadcast()
  → ULyraCharacter::OnDeathStarted（布娃娃）
  → 延迟 → FinishDeath()
  → OnDeathFinished.Broadcast()
```

4 个核心 Delegate：

| Delegate | 触发时机 | 用途 |
|----------|---------|------|
| OnHealthChanged | Health 属性变化 | UI 血条更新 |
| OnMaxHealthChanged | MaxHealth 属性变化 | UI 血条上限调整 |
| OnDeathStarted | 进入 DeathStarted 状态 | 播放死亡动画/布娃娃 |
| OnDeathFinished | 进入 DeathFinished 状态 | 重生/计分/清理 |

详细参考：[references/GAS能力系统架构.md](references/GAS能力系统架构.md)

---

### 模式八：GameplayMessageRouter 发布—订阅

消息路由系统基于 GameplayTag 提供全局事件总线，实现跨系统的松耦合通信。

**插件层核心**（GameplayMessageRouter Plugin）：

```
// 广播消息：按 Tag 遍历所有匹配的 Listener
BroadcastMessage(Tag, Message)
  → Tag 精确匹配 + 父标签回溯

// 注册监听器
RegisterListener(Params)
  → Params 包含 Tag、回调函数、匹配模式
```

**应用层协议**：FLyraVerbMessage

描述"谁(Instigator) 对谁(Target) 做了什么(Verb)"：

```
struct FLyraVerbMessage {
    FGameplayTag Verb;          // 动作标签
    TObjectPtr<UObject> Instigator;
    TObjectPtr<UObject> Target;
    FGameplayTagContainer InstigatorTags;
    FGameplayTagContainer TargetTags;
    FGameplayTagContainer ContextTags;
    double Magnitude;
};
```

**消息复制机制**：FLyraVerbMessageReplication

```
服务器
  AddMessage(VerbMessage)
  → FastArray（FLyraVerbMessageReplication）自动 NetDeltaSerialize
  → 客户端 PostReplicatedAdd/Change
    → 本地重新 BroadcastMessage
    → 本地监听者收到消息
```

**消息处理器基类**：UGameplayMessageProcessor

模板方法模式，子类只需重写 StartListening()：

```
BeginPlay() → StartListening()
EndPlay()   → StopListening()（自动清理 ListenerHandle）
```

详细参考：[references/库存与消息系统.md](references/库存与消息系统.md)

---

## 跨系统调用链路

### 链路 1：玩家输入 → 技能释放

```
玩家按下按键
    → EnhancedInput 触发 UInputAction
    → ULyraHeroComponent::OnInputStarted（InputTag 匹配）
        [路径：Source/LyraGame/Character/LyraHeroComponent.h]
    → ASC::AbilityLocalInputPressed（Tag 映射到 GA）
    → ULyraGameplayAbility::ActivateAbility
        [路径：Source/LyraGame/AbilitySystem/Abilities/LyraGameplayAbility.h]
    → GA 内部调用 CommitAbility / ApplyGameplayEffect
    → ULyraDamageExecution::Execute_Implementation（伤害计算）
        [路径：Source/LyraGame/AbilitySystem/Executions/LyraDamageExecution.h]
```

### 链路 2：Experience 加载 → 角色初始化

```
GameMode::InitGame
    → 加载 ExperienceDefinition
    → ExperienceManagerComponent::StartExperience
        [路径：Source/LyraGame/GameModes/LyraExperienceManagerComponent.h]
    → 激活 GameFeature 插件
    → Spawn Default Pawn
    → Pawn::PostInitializeComponents
    → PawnExtensionComponent::OnRegister（注册 InitState）
        [路径：Source/LyraGame/Character/LyraPawnExtensionComponent.h]
    → InitState: Spawned → DataAvailable → DataInitialized → GameplayReady
    → 各组件按顺序就绪
```

### 链路 3：装备切换 → AbilitySet 变更

```
玩家按数字键
    → ULyraQuickBarComponent::CycleNextSlot / SetActiveSlot
        [路径：Source/LyraGame/Equipment/LyraQuickBarComponent.h]
    → EquipmentManagerComponent::RemoveEquipment（卸载旧装备）
        [路径：Source/LyraGame/Equipment/LyraEquipmentManagerComponent.h]
    → ASC::RemoveAbility（回收旧 GA Handle）
    → EquipmentManagerComponent::AddEquipment（装备新装备）
    → SpawnEquipmentActor
    → ASC::GiveAbility / InitStats（授予新 GA 和属性）
    → 新装备的 ULyraEquipmentInstance 记录 Granted Handles
```

### 链路 4：换装同步（网络）

```
服务器端调用换装
    → ULyraCosmeticCheats::AddCharacterPart
        [路径：Source/LyraGame/Cosmetics/LyraCosmeticCheats.h]
    → ULyraPawnComponent_CharacterParts::AddCharacterPart
        [路径：Source/LyraGame/Cosmetics/LyraPawnComponent_CharacterParts.h]
    → FastArray（FLyraAppliedCharacterPartList）复制到客户端
    → OnRep_CharacterPartList 触发
    → Spawn/Create 对应的 CharacterPart Actor
```

### 链路 5：伤害 → 死亡处理

```
GA 激活 → ApplyGameplayEffect
    → ULyraDamageExecution::Execute_Implementation
        [路径：Source/LyraGame/AbilitySystem/Executions/LyraDamageExecution.h]
    → HealthSet Health 属性归零
        [路径：Source/LyraGame/AbilitySystem/Attributes/LyraHealthSet.h]
    → ULyraHealthComponent::OnHealthChanged（属性变化回调）
        [路径：Source/LyraGame/Character/LyraHealthComponent.h]
    → StartDeath() → bDead = true, 状态 = DeathStarted
    → OnDeathStarted.Broadcast()
    → ALyraCharacter::OnDeathStarted（播放布娃娃/死亡动画）
    → 延迟 → FinishDeath() → 状态 = DeathFinished
    → OnDeathFinished.Broadcast()
    → 可选：发送 FLyraVerbMessage（击杀通知）
      → GameplayMessageSubsystem::BroadcastMessage
```

### 链路 6：拾取 → 库存 → 装备

```
玩家进入 ALyraWeaponSpawner 碰撞体
    [路径：Source/LyraGame/Weapons/LyraWeaponSpawner.h]
    → AttemptPickUpWeapon(Pawn)
    → GiveWeapon(WeaponItemClass, InventoryManager)
    → ULyraInventoryManagerComponent::AddItemDefinition
        [路径：Source/LyraGame/Inventory/LyraInventoryManagerComponent.h]
    → FLyraInventoryList::AddEntry（FastArray 同步到客户端）
    → ULyraQuickBarComponent 检测到新物品
        [路径：Source/LyraGame/Equipment/LyraQuickBarComponent.h]
    → 切换到新槽位
    → ULyraEquipmentManagerComponent::AddEquipment
        [路径：Source/LyraGame/Equipment/LyraEquipmentManagerComponent.h]
    → ULyraEquipmentInstance::SpawnEquipmentActor
    → ULyraAbilitySet::GiveToAbilitySystem（授予技能和属性）
```

---

## 常见开发工作流

### 工作流 1：添加新武器

1. 创建武器类继承 `ULyraEquipmentInstance`，路径：`Equipment/`
2. 创建 AbilitySet 数据资产，包含武器 GA、GE、AttributeSet
3. 创建 ULyraEquipmentDefinition 数据资产，指向上面两步
4. 将 Definition 配置到背包物品或直接通过 QuickBarComponent 测试
5. （可选）为武器创建 CameraMode 子类实现瞄准缩放

### 工作流 2：添加新技能（GA）

1. 继承 `ULyraGameplayAbility`，路径：`AbilitySystem/Abilities/`
2. 设置 `ActivationGroup`（Independent / Exclusive_Replaceable / Exclusive_Blocking）
3. 定义 `ActivationOwnedTags` 和 `ActivationRequiredTags`
4. 若技能包含伤害，使用 `FLyraGameplayEffectContext` 携带 CartridgeID
5. 添加到 `ULyraAbilitySet` 数据资产中

### 工作流 3：添加新的 GameMode

1. 创建新的 `ULyraExperienceDefinition` 数据资产
2. 定义该 Experience 加载的 GameFeature 插件列表
3. 设置默认 Pawn、Controller、HUD、PlayerState、GameState
4. 在 ExperienceDefinition 的 GameFeature Actions 中配置 GameMode 切换
5. 在 Project Settings → Maps & Modes → Default GameMode 指向自定义 GameMode

### 工作流 4：添加新 UI 界面

1. 创建 Widget 继承 `UCommonActivatableWidget`（支持 Push/Pop 生命周期）
2. 在 `UPrimaryGameLayout` 的四层栈中选择合适层
3. 调用 `RootLayout->GetXxxStack()->AddWidget(Widget)` 显示
4. 实现 `OnActivated`/`OnDeactivated` 生命周期方法

### 工作流 5：添加新的队伍显示资产

1. 创建 `ULyraTeamDisplayAsset` 数据资产，设置颜色和材质
2. 在 `ALyraTeamPublicInfo` 中设置 DisplayAsset
3. 各系统的显示逻辑读取 TeamSubsystem 中的 DisplayAsset 更新视觉效果

### 工作流 6：添加库存物品

1. 创建 `ULyraInventoryItemDefinition` 数据资产，设置 DisplayName
2. 添加 `ULyraInventoryItemFragment` 子类扩展物品行为（如添加武器段、消耗品段）
3. 若物品需要可拾取，配置 `ALyraWeaponSpawner` 并在其 `ULyraWeaponPickupDefinition` 中指向物品定义
4. 管理员调用 `InventoryManagerComponent->AddItemDefinition(ItemDef, StackCount)`
5. 物品被添加到 `FLyraInventoryList`（FastArray 自动同步）

### 工作流 7：添加伤害反馈与死亡表现

1. 确保角色已配置 `ULyraHealthComponent` 和 `ULyraHealthSet`（默认由 PawnData 中的 AbilitySet 提供）
2. 创建自定义 GE 蓝图，设置伤害属性（Damage.Health）、伤害类型 Tag
3. 在角色 Blueprint 中绑定 `OnHealthChanged` 事件显示伤害数字、HitMarker
4. 在角色 Blueprint 中绑定 `OnDeathStarted` 事件播放死亡蒙太奇/布娃娃
5. 在角色 Blueprint 中绑定 `OnDeathFinished` 事件处理重生/计分
6. （可选）通过 `FLyraVerbMessage` 发送击杀通知，UI 层监听显示击杀信息

---

## 扩展阅读

| 文档 | 内容 |
|------|------|
| [Experience框架与加载流程](references/Experience框架与加载流程.md) | Experience 3 阶段加载、GameFeature 激活流程、ManagerComponent 状态机 |
| [InitState初始化状态机](references/InitState初始化状态机.md) | 4 态状态机、IGameFrameworkInitStateInterface 接口、组件注册方式 |
| [输入系统与InputConfig](references/输入系统与InputConfig.md) | InputConfig 数据结构、BindAbilityActivation、输入修饰器 |
| [GAS能力系统架构](references/GAS能力系统架构.md) | AbilitySet、ActivationGroup、ASC 输入激活、HealthComponent 死亡状态机、AbilityCost 消耗系统 |
| [装备与武器系统](references/装备与武器系统.md) | 三层装备设计、QuickBarComponent、Spread/Heat 机制 |
| [UI层栈架构](references/UI层栈架构.md) | 四层 UI 栈、PrimaryGameLayout、HUDLayout Tier 结构 |
| [动画系统概览](references/动画系统概览.md) | Lyra 动画架构 |
| [角色初始化与移动系统](references/角色初始化与移动系统.md) | PlayerSpawningManager、移动加速度 Polar 量化、Tag 控制运动 |
| [库存与消息系统](references/库存与消息系统.md) | 四层库存架构、拾取系统、GameplayMessageRouter、GamePhase |

---

## 使用示例

### 示例：询问"添加一个火箭筒武器需要怎么做"

> 要添加火箭筒武器到 Lyra 项目：
>
> 1. **创建 EquipmentDefinition**：在 Content 目录创建 `ULyraEquipmentDefinition` 数据资产，设置 Instance 类型和 AbilitySet
> 2. **创建 EquipmentInstance**：继承 `ULyraEquipmentInstance` 添加火箭筒特有逻辑（如 SpawnedActor 类型）
> 3. **创建 AbilitySet**：包含火箭筒发射 GA、爆炸 GE、火箭筒弹药 AttributeSet
> 4. **配置 QuickBarComponent**：将新武器的 Definition 添加到 QuickBarComponent 的 DefaultSlots
> 5. **添加 Spread 曲线**：如需扩散机制，在武器 GA 中实现 `ILyraAbilitySourceInterface` 接口
>
> 参考代码模式：Equipment Fragment 三层设计（见核心设计模式三）

### 示例：询问"解释一下 Lyra 中换装同步的机制"

> Lyra 换装系统采用**双组件架构**：
>
> - **ULyraCosmeticCheats**（挂载在 Controller 上）：授权端，只有服务器有权修改换装列表
> - **ULyraPawnComponent_CharacterParts**（挂载在 Pawn 上）：通过 FastArray 网络复制换装数据
>
> 服务器调用 `AddCharacterPart` 时，修改 `FLyraAppliedCharacterPartList`（FastArray），该数组自动复制到所有客户端。客户端收到 `OnRep` 后，Spawn 对应的 `UCharacterPart` Actor（如武器挂件、头盔等静态网格体）。
>
> 关键文件：`Source/LyraGame/Cosmetics/`
