# UI 层栈架构

## 概述

Lyra 的 UI 系统基于 **CommonUI** 插件构建，通过 `UPrimaryGameLayout` 管理四层 Widget 栈，每层独立显示和交互。这种架构使得 UI 的层级管理（HUD 在底层、菜单在中层、弹窗在顶层）成为声明式配置，而非手动管理。

---

## 四层栈结构

```
Modal（模态层）
    ↑ 提示框、确认框 — BlockInput = true，阻挡下层交互
Menu（功能层）
    ↑ 背包、设置、商店、地图
GameMenu（菜单层）
    ↑ 游戏内暂停菜单（ESC 菜单）
Game（游戏层）
    ↑ HUD、准星、血条、技能冷却、击杀信息
```

---

## PrimaryGameLayout

**文件**：`Plugins/CommonGame/Source/Public/PrimaryGameLayout.h`

```cpp
UCLASS()
class UPrimaryGameLayout : public UCommonActivatableWidgetStack
{
    GENERATED_BODY()

public:
    // 四层栈访问
    UFUNCTION(BlueprintPure)
    UCommonActivatableWidgetStack* GetGameStack() const;

    UFUNCTION(BlueprintPure)
    UCommonActivatableWidgetStack* GetGameMenuStack() const;

    UFUNCTION(BlueprintPure)
    UCommonActivatableWidgetStack* GetMenuStack() const;

    UFUNCTION(BlueprintPure)
    UCommonActivatableWidgetStack* GetModalStack() const;

    // 获取玩家对应的 PrimaryGameLayout
    static UPrimaryGameLayout* GetPrimaryGameLayout(APlayerController* Controller);
};
```

---

## HUDLayout 结构

**文件**：`Source/LyraGame/UI/LyraHUDLayout.h`

`ULyraHUDLayout` 是 ALyraHUD 创建的根 Widget，内部使用 CommonUI 的 Tier 布局：

```
ULyraHUDLayout
    ├── TopLeft Tier（队伍信息、玩家列表）
    ├── TopCenter Tier（游戏模式信息）
    ├── TopRight Tier（网络状态、FPS）
    ├── LowerLeft Tier（生命值、弹药、技能冷却）
    ├── LowerMiddle Tier（快捷栏、当前装备）
    └── LowerRight Tier（击杀信息、通知消息）
```

HUD 布局使用 `UCommonBorder` 作为容器，通过 GameplayTag 控制各 Tier 的可见性。

---

## Widget 生命周期

所有 UI Widget 继承 `UCommonActivatableWidget`，具有标准的生命周期：

```
CreateWidget → OnInitialized
    ↓
AddToStack → OnActivated
    ↓
（Widget 活跃，接收输入）
    ↓
RemoveFromStack / Push 其他 Widget → OnDeactivated
    ↓
Widget 被销毁
```

---

## HUD 创建流程

```
ALyraHUD::BeginPlay()
    → 创建 ULyraHUDLayout Widget
    → AddToViewport 并添加到 Game Layer

ALyraHUD::OnPlayerStateChanged()
    → HUDLayout 各 Tier 根据 PlayerState 创建/更新子 Widget
    → 示例：LowerLeftTier 创建 HealthWidget 和 AmmoWidget
```

---

## Push/Pop Widget

```cpp
// 向 Game 层 Push HUD
UPrimaryGameLayout* Layout = UPrimaryGameLayout::GetPrimaryGameLayout(Controller);
UCommonActivatableWidget* HUDWidget = CreateWidget<UMyHUDWidget>(Controller);
Layout->GetGameStack()->AddWidget(HUDWidget);

// 向 Menu 层 Push 背包界面
UCommonActivatableWidget* InventoryWidget = CreateWidget<UMyInventoryWidget>(Controller);
Layout->GetMenuStack()->AddWidget(InventoryWidget);

// 向 Modal 层 Push 确认框
UCommonActivatableWidget* ConfirmWidget = CreateWidget<UMyConfirmDialog>(Controller);
Layout->GetModalStack()->AddWidget(ConfirmWidget);
```

---

## 输入阻挡规则

| 层 | 输入行为 |
|----|---------|
| Game | 游戏输入（按键/鼠标）传递到 Pawn |
| GameMenu | 游戏输入被阻挡，菜单输入生效 |
| Menu | 游戏输入被阻挡，菜单输入生效 |
| Modal | 所有输入被阻挡，仅模态框组件接收输入（BlockInput=true） |

`BlockInput` 特性由 CommonUI 原生提供：当 Modal 层有 Widget 时，自动设置输入模式为 `UI Only`。

---

## 关键设计要点

1. **四层栈** — 自然映射了游戏的交互层级（HUD < 暂停菜单 < 功能界面 < 弹窗）
2. **CommonUI 原生支持** — ActivatableWidget 的 Push/Pop 生命周期减少了手动管理输入模式的代码
3. **Tier 布局** — HUDLayout 内部的 Tier 结构使得 HUD 元素的排列不依赖 Absolute 定位
4. **GameplayTag 驱动可见性** — 各 Tier 通过 GameplayTag 控制显隐，与 GAS 的 Tag 体系统一
5. **单例获取** — `GetPrimaryGameLayout` 通过 LocalPlayer 查找，保证每个玩家有独立的 UI 布局
