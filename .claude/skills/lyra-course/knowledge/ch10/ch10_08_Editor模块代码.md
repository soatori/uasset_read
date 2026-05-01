# Editor 模块代码

## 概述

LyraEditor 模块提供了编辑器扩展、资产验证、命令行工具、资产工厂和样式系统等功能，是 Lyra 项目编辑器侧的基础设施。

## 文件结构

- [LyraEditor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraEditor/LyraEditor.cpp) — 模块入口 StartupModule
- [GameEditorStyle.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraEditor/Private/GameEditorStyle.h) / [GameEditorStyle.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraEditor/Private/GameEditorStyle.cpp) — Slate 样式
- [LyraEditorEngine.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraEditor/LyraEditorEngine.h) / [LyraEditorEngine.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraEditor/LyraEditorEngine.cpp) — 编辑器引擎覆写
- [Validation/](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraEditor/Validation/) — 资产验证系统
- [Commandlets/](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraEditor/Commandlets/) — ContentValidationCommandlet
- [Utilities/](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraEditor/Utilities/) — 编辑器工具命令
- [Private/](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraEditor/Private/) — AssetTypeActions / Factory

## FLyraEditorModule StartupModule

[LyraEditor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraEditor/LyraEditor.cpp#L208-L234)

模块启动时依次执行：

1. **初始化样式**：`FGameEditorStyle::Initialize()`
2. **GameplayAbilitiesEditor 委托绑定**：通过模块加载回调监听 `GameplayAbilitiesEditor` 模块，绑定三个 GameplayCue 编辑器委托：
   - `GetGameplayCueNotifyClassesDelegate`：返回 `UGameplayCueNotify_Burst`、`AGameplayCueNotify_BurstLatent`、`AGameplayCueNotify_Looping`
   - `GetGameplayCueInterfaceClassesDelegate`：扫描所有实现 `UGameplayCueInterface` 的 AActor 子类
   - `GetGameplayCueNotifyPathDelegate`：从 `UAbilitySystemGlobals::GameplayCueNotifyPaths` 获取路径
3. **PIE 事件绑定**：绑定 `FEditorDelegates::BeginPIE` / `EndPIE`，PIE 开始时通知 `ULyraExperienceManager`
4. **注册资产类型**：注册 `FAssetTypeActions_LyraContextEffectsLibrary`
5. **注册工具栏菜单**：`RegisterGameEditorMenus()`

## FGameEditorStyle Slate 样式

[GameEditorStyle.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraEditor/Private/GameEditorStyle.h) / [GameEditorStyle.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraEditor/Private/GameEditorStyle.cpp)

纯静态类，管理名为 `GameEditorStyle` 的 `FSlateStyleSet`：

- 定义 `IMAGE_BRUSH` / `BOX_BRUSH` / `BORDER_BRUSH`（引擎路径）宏
- 定义 `GAME_IMAGE_BRUSH` / `GAME_IMAGE_BRUSH_SVG`（项目路径）宏
- 注册图标资源：`"GameEditor.CheckContent"` 使用项目 SVG 图标

## 工具栏菜单 RegisterGameEditorMenus

在 `LevelEditor.LevelEditorToolBar.PlayToolBar` 工具栏后插入三个扩展：

- **Check Content 按钮**：调用 `UEditorValidator::ValidateCheckedOutContent()`
- **Common Maps 下拉**：从 `ULyraDeveloperSettings::CommonEditorMaps` 读取常用地图列表

## ULyraEditorEngine

[LyraEditorEngine.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraEditor/LyraEditorEngine.h) / [LyraEditorEngine.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraEditor/LyraEditorEngine.cpp)

继承自 `UUnrealEdEngine`，覆写关键虚函数：

- **FirstTickSetup**：单次执行，强制启用 `UContentBrowserSettings::DisplayPluginFolders`
- **PreCreatePIEInstances**：PIE 创建前拦截，如果 `ALyraWorldSettings::ForceStandaloneNetMode` 为 true 则强制设置 NetMode 为 `PIE_Standalone`；然后通知 `ULyraDeveloperSettings` 和 `ULyraPlatformEmulationSettings` 的 `OnPlayInEditorStarted()`

## PIE 体验管理转发

[LyraExperienceManager.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/GameModes/LyraExperienceManager.h) / [LyraExperienceManager.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/GameModes/LyraExperienceManager.cpp)

`OnPlayInEditorBegun` 方法在 PIE 开始时被 `FLyraEditorModule` 调用，通知 ExperienceManager 进行初始化：

```cpp
void ULyraExperienceManager::OnPlayInEditorBegun()
{
    // PIE 开始时的体验管理初始化
    NotifyOfPluginActivation(...);
    RequestToDeactivatePlugin(...);
}
```

## 资产验证系统 Validation

路径：[LyraEditor/Validation/](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraEditor/Validation/)

采用策略模式，基类 `UEditorValidator` 继承自 `UEditorValidatorBase`。

### UEditorValidator 基类

[EditorValidator.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraEditor/Validation/EditorValidator.h) / [EditorValidator.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraEditor/Validation/EditorValidator.cpp)

- **FLyraValidationMessageGatherer**：内部类，继承 `FOutputDevice`，挂接到 `GLog` 捕获 Warning 及更低级别日志
- **ValidateCheckedOutContent**：获取源码控制中已变更的文件，对 .h 变更还通过 `GetChangedAssetsForCode()` 找出受影响的 Blueprint
- **ValidatePackages**：加载并验证资产包，先预加载监听 Load 警告，再调用 `UEditorValidatorSubsystem::ValidateAssetsWithSettings()`
- **ValidateProjectSettings**：检查 Python `bDeveloperMode` 是否被启用（不应被提交）
- **GetChangedAssetsForCode**：通过头文件变更查找受影响的 Blueprint（头文件中的 Native 类 → 派生 Blueprint）

### UEditorValidator_SourceControl

[EditorValidator_SourceControl.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Source/LyraEditor/Validation/EditorValidator_SourceControl.h) / [EditorValidator_SourceControl.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra/Source/LyraEditor/Validation/EditorValidator_SourceControl.cpp)

验证已提交到源码控制的资产是否引用了未添加到源码控制的资产。

### UEditorValidator_Blueprints

[EditorValidator_Blueprints.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra/Source/LyraEditor/Validation/EditorValidator_Blueprints.h) / [EditorValidator_Blueprints.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra/Source/LyraEditor/Validation/EditorValidator_Blueprints.cpp)

当非 data-only Blueprint 变更时，级联检查所有硬引用它的非 data-only Blueprint 是否仍有编译错误。

### UEditorValidator_Load

[EditorValidator_Load.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra/Source/LyraEditor/Validation/EditorValidator_Load.h) / [EditorValidator_Load.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra/Source/LyraEditor/Validation/EditorValidator_Load.cpp)

验证资产在加载时是否产生警告或错误。核心策略：如果资产已在内存中，将其复制到临时路径重新加载以捕获加载警告。

### UEditorValidator_MaterialFunctions

[EditorValidator_MaterialFunctions.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra/Source/LyraEditor/Validation/EditorValidator_MaterialFunctions.h) / [EditorValidator_MaterialFunctions.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra/Source/LyraEditor/Validation/EditorValidator_MaterialFunctions.cpp)

当 `UMaterialFunction` 变更时，级联检查所有硬引用它的 `UMaterial` 是否仍有编译错误。

## 命令行工具

### UContentValidationCommandlet

[ContentValidationCommandlet.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra/Source/LyraEditor/Commandlets/ContentValidationCommandlet.cpp)

内容验证 Commandlet，集成 Perforce 源码控制：

- 在命令行中执行批量资产验证
- 检查变更文件列表中的资产
- 与 P4 集成获取变更集信息

### 编辑器工具命令

[Utilities/](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra/Source/LyraEditor/Utilities/)

- **Lyra.CheckChaosMeshCollision**：检查 Chaos 网格碰撞体设置
- **Lyra.CreateRedirectorPackage**：创建重定向包
- **Lyra.DiffCollectionReferenceSupport**：集合引用差异比较工具

这些命令通过 `FAutoConsoleCommand` 注册，在编辑器控制台中可用。

## ContextEffects 编辑器支持

- [AssetTypeActions_LyraContextEffectsLibrary.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra/Source/LyraEditor/Private/AssetTypeActions_LyraContextEffectsLibrary.h) — 资产类型动作，分类为 `EAssetTypeCategories::Gameplay`
- [LyraContextEffectsLibraryFactory.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra/Source/LyraEditor/Private/LyraContextEffectsLibraryFactory.h) — 内容浏览器右键创建 ULyraContextEffectsLibrary 资产
