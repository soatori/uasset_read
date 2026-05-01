## [2026-04-27] lint | 修复 lyra-course 路径断裂和不存在的抽象类

- **来源**：lyra-course Skill 质量评估（33% 路径断裂率 + 5 处不存在类）
- **产出**：
  - SKILL.md：修复目录树、类索引 10 层、设计模式、调用链路、工作流
  - references/Experience框架与加载流程.md：重构 Phase 3（ULyraExperienceAction→UGameFeatureAction）
  - references/GAS能力系统架构.md：修复 AbilitySet/TagRelationshipMapping/AttributeSets/HealthComponent 路径
  - references/输入系统与InputConfig.md：ULyraEnhancedInputComponent→ULyraInputComponent
  - references/InitState初始化状态机.md：修复 IGameFrameworkInitStateInterface 来源标注
  - references/UI层栈架构.md：修复 PrimaryGameLayout 路径
  - references/库存与消息系统.md：修复 2 条 GamePhase 路径
  - references/装备与武器系统.md：移除不存在的 ULyraWeaponSpreadSet 引用
- **状态**：完成

## [2026-04-27] lint | 沉淀 Lyra 全流程经验，优化三大 Skill + AGENTS.md

- **来源**：Lyra 课程全流程工作（10 章 Ingest、Skill 蒸馏、lint、路径验证、全系统对比）
- **产出**：
  - `AGENTS.md` — Skill 架构扩展为四层（+学员交付层），新增 Skill 蒸馏工作流，更新目录结构
  - `skills/xg-course-context/SKILL.md` — 新增第十一~十四章：Skill 蒸馏流程、混合素材处理、批量 Ingest 策略、路径验证规范
  - `skills/xg-lyra-knowledge/SKILL.md` — 增加 dist/ 目录、素材覆盖精确统计、Lyra 全流程经验总结（批量 Ingest/Skill 蒸馏/学员交付物规范）
  - `skills/xg-uecpp-knowledge/SKILL.md` — 更新目录结构（ch4/ 15 篇）、工作流引用指向新章节
- **关键经验**：
  - Skill 蒸馏：knowledge/ → dist/ 的二次加工，含设计模式提取 + 调用链路 + 开发工作流
  - 路径验证：references 中 file:/// 链接必须逐条确认存在
  - 批量 Ingest：骨架先行 → 逐章 Ingest → 交叉补充 → Skill 蒸馏 → 全库审核
  - 混合格式：.docx 提取为 .txt 再参与 Ingest
- **状态**：完成（commit: 05028370）

## [2026-04-27] query | Query 流程验证：ULyraHeroComponent + InitState 状态机

- **来源**：
  - `knowledge/课程纲要.md` — 定位第六章
  - `knowledge/第六章-角色与输入系统.md` — 章节索引
  - `knowledge/ch6/03-HeroComponent与输入绑定.md` — 问题1 主要来源
  - `knowledge/ch6/02-初始化状态机与PawnExtension.md` — 问题2 主要来源
  - `knowledge/ch6/07-相机系统.md` — 补充 CameraComponent 参与信息
  - `code/Lyra/Source/LyraGame/Character/LyraHeroComponent.h` — 源码验证
- **产出**：
  - 问题1：ULyraHeroComponent 三大职责（输入绑定/ASC初始化/相机代理）及其 InitState 参与方式
  - 问题2：4 态链（Spawned→DataAvailable→DataInitialized→GameplayReady），涉及 PawnExtension/HeroComponent/CameraComponent 三个组件
- **状态**：完成

## [2026-04-27] lint | Lyra 知识库全库健康检查

- **来源**：全库 102 篇 knowledge/ .md 文档 + 课程纲要 + 122 讲 docs/ 讲义
- **检查维度**：
  1. 代码引用有效性：346 条 file:/// 链接，4 条断裂（98.8% 有效）→ 已修复
  2. 矛盾声明：8 个核心概念跨章对比，0 条硬矛盾，1 条临界（IncludeOrderVersion Unreal5_4 命名）
  3. 概念覆盖遗漏：4 讲无知识文档（038 预加载/072 动画要点/073 移动相机/122 终章），其中 072/073 为截图为主有意跳过
  4. 交叉引用断裂：0 条
  5. 过时内容：课程纲要.md 中讲义总数 117→122，084/110 "无讲义"声明已修正
- **产出**：
  - `knowledge/ch9/ch9_03_指示器系统.md` — 修复 3 条断裂代码引用（U 前缀误入文件名）
  - `knowledge/ch9/ch9_02_队伍系统.md` — 修复 2 条断裂代码引用（Teams/→Player/ 目录 + 拼写）
  - `knowledge/课程纲要.md` — 修正讲义总数 117→122，修正 084/110 无讲义声明
  - `knowledge/log.md` — 本记录
  - `.understand-anything/knowledge-graph.json` — 重新生成（3 文件修改触发增量）
- **状态**：完成（4 条断裂全部修复，图谱同步更新）

## [2026-04-27] ingest | 创建知识体系骨架

- **来源**：全部 docs/ 讲义（117 篇 .md）分析 + code/ 源码目录结构分析（26 个子目录） + LyraGame.Build.cs 模块依赖分析
- **产出**：
  - `knowledge/课程纲要.md` — 知识体系总索引（10 章结构、讲义→知识映射、源码→知识映射、依赖关系图）
  - `knowledge/log.md` — 操作日志
- **状态**：完成

## [2026-04-27] ingest | 第三章/第四章补充 — 038/041 .docx 讲义提取

- **来源**：
  - `docs/UE5_Lyra学习指南_038_预加载界面.docx` — CommonStartupLoadingScreen 插件讲解（含 Slate 界面截图、Loading 控件蓝图）
  - `docs/UE5_Lyra学习指南_041_CommonUI_主界面.docx` — CommonUI 使用架构详解（含 20+ 控件/界面截图）
  - python-docx 提取段落文本
- **背景**：课程纲要标注 038、041 无对应讲义，实际存在 .docx 格式。用户反馈后补充提取
- **产出**：
  - `docs/UE5_Lyra学习指南_038_预加载界面.txt` — 提取文本（关联第三章设置系统）
  - `docs/UE5_Lyra学习指南_041_CommonUI_主界面.txt` — 提取文本（关联第四章 UI 架构）
  - `knowledge/课程纲要.md` — 更新讲义标注（038/041 归入 .docx 类）
  - `knowledge/第三章-设置系统.md` — 讲义范围补充 038 行
  - `knowledge/第四章-UI架构与登录流程.md` — 补充来源说明
- **图片说明**：038 含 LoadingScreen Slate/蓝图界面截图，041 含 20+ CommonUI 控件编辑界面截图，图片内容不可读
- **状态**：完成
- **备注**：知识体系按子系统组织（非教学顺序）。下一步依次对各章进行 Ingest，将讲义内容提取为结构化知识文档。

## [2026-04-27] ingest | 第一章 — 项目架构与工程搭建

- **来源**：
  - 讲义 001~009 + 009_补_01（共 10 篇 .md）
  - 代码验证：`LyraGame/System/`, `LyraGame/GameModes/`, `LyraGame/Player/`, `LyraGame/Settings/`, `LyraGame/UI/`, `LyraGame/Audio/`, `LyraEditor/`
- **产出**：
  - `knowledge/第一章-项目架构与工程搭建.md` — 章节知识入口（概述、讲义映射、关键类列表、日志分类、依赖关系）
  - `knowledge/ch1/ch1-项目概述.md` — Lyra 项目背景、功能特点、下载安装
  - `knowledge/ch1/ch1-源码架构概览.md` — 模块结构、LyraGame 目录结构、核心设计概念
  - `knowledge/ch1/ch1-工程搭建流程.md` — 创建工程、模块拆分、uproject 和 Build.cs 配置
  - `knowledge/ch1/ch1-Target文件配置.md` — 4 种 Target 文件、共享配置、插件管理
  - `knowledge/ch1/ch1-资产导入与项目设置.md` — 打包错误修复、碰撞配置、音频设置
  - `knowledge/ch1/ch1-日志系统.md` — 9 个日志类别定义、级别、FWorldContext
  - `knowledge/ch1/ch1-引擎类体系.md` — 引擎类继承关系、配置替换、加载时机
  - `knowledge/ch1/ch1-编辑器定制.md` — ULyraEditorEngine、FirstTickSetup、SPathView 补丁
- **代码验证**：11 个关键类全部在源码中找到对应实现
- **状态**：完成

## [2026-04-27] ingest | 第二章 — Experience 与 Gameplay 框架

- **来源**：
  - 讲义 010~027 + 泽篇 6 篇（共 32 篇 .md）
  - 代码验证：`LyraGame/GameModes/`, `LyraGame/Player/`, `LyraGame/System/`
- **产出**：
  - `knowledge/第二章-Experience与Gameplay框架.md` — 章节知识入口（概述、讲义映射、关键类列表、依赖关系、启动流程）
  - `knowledge/ch2/ch2-Experience定义与加载.md` — ExperienceDefinition 数据资产、ExperienceManagerComponent 状态机、加载流程、WorldSettings 配置
  - `knowledge/ch2/ch2-AssetManager与异步加载.md` — ULyraAssetManager、TSoftObjectPtr/FSoftObjectPath、异步加载模式、Asset Bundle
  - `knowledge/ch2/ch2-GameInstance与登录流程.md` — ULyraGameInstance、登录流程、OnlineSubsystem、DTLS 加密、令牌验证
  - `knowledge/ch2/ch2-GameMode工作流程.md` — InitGame → HandleMatchAssignment → OnExperienceLoaded 完整调用链、Player 登录流程
  - `knowledge/ch2/ch2-GameState与PlayerState.md` — GameState 的 ExperienceManager/PlayerSpawningManager 组件、TagStack FastArray 序列化
  - `knowledge/ch2/ch2-PlayerController与LocalPlayer.md` — PC 职责体系（HTTP/Replay/ForceFeedback/GAS/Team）、LocalPlayer 共享设置
  - `knowledge/ch2/ch2-玩家生成系统.md` — PlayerSpawningManagerComponent、ChoosePlayerStart 重写
  - `knowledge/ch2/ch2-开发者设置与模拟平台.md` — UDeveloperSettings、UserFacingExperienceDefinition、平台模拟
- **代码验证**：12 个关键类全部在源码中找到对应实现（ULyraExperienceDefinition、ULyraExperienceManagerComponent、ULyraExperienceActionSet、ULyraGameInstance、ALyraGameMode、ALyraGameState、ALyraPlayerState、ALyraPlayerController、ULyraPlayerSpawningManagerComponent、ULyraUserFacingExperienceDefinition、ALyraWorldSettings、ULyraBotCreationComponent）
- **状态**：完成

## [2026-04-27] ingest | 第三章 — 设置系统

- **来源**：
  - 讲义 028~037 + 泽篇 5 篇 + AI 篇 2 篇（共 15 篇 .md，038 无对应文件）
  - 代码验证：`LyraGame/Settings/`, `LyraGame/Settings/CustomSettings/`, `LyraGame/Settings/Screens/`, `LyraGame/Settings/Widgets/`, `LyraGame/Audio/`, `LyraGame/Hotfix/`, `LyraGame/GameFeatures/`, `LyraGame/Performance/`, `LyraGame/AbilitySystem/`
- **产出**：
  - `knowledge/第三章-设置系统.md` — 章节知识入口（概述、讲义映射、关键类列表、源码目录、核心架构、依赖关系）
  - `knowledge/ch3/ch3-设置系统架构.md` — ULyraSettingsLocal 双层架构、UGameUserSettings 基类、ULyraSettingsShared、ULyraGameSettingRegistry、自定义设置值类型
  - `knowledge/ch3/ch3-音频系统.md` — ULyraAudioSettings、ULyraAudioMixEffectsSubsystem、ControlBus 音频调制、HRTF 耳机模式、音频设备切换
  - `knowledge/ch3/ch3-性能与渲染设置.md` — ULyraPlatformSpecificRenderingSettings、ULyraPerformanceSettings、ELyraFramePacingMode、移动端品质辅助、帧率控制
  - `knowledge/ch3/ch3-Latency与NVIDIAReflex.md` — ILatencyMarkerModule、SetCustomLatencyMarker、LatencyFlashIndicators、ELatencyStage
  - `knowledge/ch3/ch3-GameFeature系统.md` — GameFeature 插件结构、ULyraGameFeaturePolicy、GameFeatureAction 体系、ContentBundle、插件实例
  - `knowledge/ch3/ch3-Hotfix系统.md` — ULyraHotfixManager、热修复流程、与设置的联动
  - `knowledge/ch3/ch3-GameplayCue管理.md` — ULyraGameplayCueManager、延迟加载、预加载、路径注册
- **代码验证**：16 个关键类/结构全部在源码中找到对应实现（ULyraSettingsLocal、ULyraSettingsShared、ULyraGameSettingRegistry、ULyraAudioSettings、ULyraAudioMixEffectsSubsystem、ULyraPlatformSpecificRenderingSettings、ULyraPerformanceSettings、ELyraFramePacingMode、ULyraHotfixManager、ULyraGameFeaturePolicy、UGameFeatureAction_AddGameplayCuePath、ULyraGameplayCueManager、UGameFeatureAction_AddAbilities、UGameFeatureAction_AddWidget、UGameFeatureAction_AddInputBinding、UGameFeatureAction_AddInputContextMapping）。ULyraPlatformSpecificRenderingSettings 确认在 LyraPerformanceSettings.h（Performance 目录）；ULyraSettingsHelpers 为 LyraSettingsLocal.cpp 内部 namespace。
- **状态**：完成

## [2026-04-27] ingest | 第四章 — UI 架构与登录流程

- **来源**：
  - 讲义 039~054（共 15 篇 .md，041 无对应文件）
  - 代码验证：`UI/`, `UI/Foundation/`, `UI/Frontend/`, `UI/Common/`, `Plugins/CommonGame/`, `Plugins/CommonUser/`, `Plugins/GameSettings/`, `Settings/`, `GameModes/`
- **产出**：
  - `knowledge/第四章-UI架构与登录流程.md` — 章节知识入口（概述、子系统一览、架构关系、关键模式、代码文件索引）
  - `knowledge/ch4/01-HUD架构与布局系统.md` — ULyraHUDLayout、UPrimaryGameLayout 层栈架构
  - `knowledge/ch4/02-按钮系统.md` — ULyraButtonBase 继承链、UE5.4+ 按钮内部变化
  - `knowledge/ch4/03-对话框系统.md` — UCommonGameDialog、ULyraConfirmationScreen、消息管线
  - `knowledge/ch4/04-底部操作栏.md` — UCommonBoundActionBar、ULyraBoundActionButton、输入法样式切换
  - `knowledge/ch4/05-会话系统.md` — UCommonSessionSubsystem、Host/Find/Join/QuickPlay 完整流程
  - `knowledge/ch4/06-CommonUser插件.md` — UCommonUserSubsystem、用户初始化状态机、权限体系
  - `knowledge/ch4/07-Tab列表系统.md` — FLyraTabDescriptor、ILyraTabButtonInterface、标签注册与导航
  - `knowledge/ch4/08-游戏设置界面与注册器.md` — ULyraSettingScreen、ULyraGameSettingRegistry、Tab-内容联动
  - `knowledge/ch4/09-设置面板列表与细节视图.md` — UGameSettingPanel、UGameSettingListView、UGameSettingDetailView、VisualData 映射
- **代码验证**：21 个关键类中 21 个确认在源码中存在对应实现（ULyraHUDLayout、UPrimaryGameLayout、ULyraButtonBase、ULyraBoundActionButton、ULyraConfirmationScreen、UCommonGameDialog、UCommonSessionSubsystem、ULyraUserFacingExperienceDefinition、UCommonUserSubsystem、UCommonUserInfo、FCommonUserInitializeParams、ECommonUserInitializationState、ULyraSettingScreen、ULyraGameSettingRegistry、UGameSettingPanel、UGameSettingListView、UGameSettingDetailView、UGameSettingVisualData、FLyraTabDescriptor、ILyraTabButtonInterface、ULyraTabListWidgetBase）。未找到独立 ULyraHUD 类（Lyra HUD 完全基于 Widget 体系）；ULyraDialogReceiverDefinition 和 UCommonGameDialogPopup 未在代码快照中找到；ULyraTabButtonBase 实际使用 ILyraTabButtonInterface 接口模式。
- **状态**：完成

## [2026-04-27] ingest | 第五章 — 设置界面实现

- **来源**：
  - 讲义 055~064（共 11 篇 .md）
  - 代码验证：`Settings/`, `Settings/CustomSettings/`, `Settings/Screens/`, `Settings/Widgets/`, `Input/`, `Performance/`, `Audio/`, `UI/`, `UI/PerformanceStats/`, `Plugins/GameSettings/`
- **产出**：
  - `knowledge/第五章-设置界面实现.md` — 章节知识入口（子系统一览、架构关系、关键模式、代码文件索引）
  - `knowledge/ch5/01-GameSettingRegistry体系.md` — 注册表架构、OnInitialize 流程、数据源宏（GET_LOCAL_SETTINGS_FUNCTION_PATH/GET_SHARED_SETTINGS_FUNCTION_PATH）、GC 生命周期
  - `knowledge/ch5/02-GameSetting类体系.md` — 完整类层级（UGameSetting→Collection/Value/Scalar/Discrete/Action）、生命周期、FGameSettingFilterState、FGameSettingEditableState、FGameSettingEditCondition、FWhenPlatformHasTrait
  - `knowledge/ch5/03-音频设置.md` — InitializeAudioSettings：音量（5 通道）、字幕（5 项）、音频输出设备、背景音频、耳机模式、HDR 音频
  - `knowledge/ch5/04-视频设置.md` — InitializeVideoSettings：显示（窗口模式/分辨率）、图形（色盲/亮度/安全区）、画质（AutoSetQuality 联动链 + 8 项品质）、高级图形（垂直同步）、帧率限制
  - `knowledge/ch5/05-输入绑定设置.md` — InitializeMouseAndKeyboardSettings + InitializeGamepadSettings：灵敏度缩放（ULyraSettingBasedScalar 反射）、反转轴、Enhanced Input 按键绑定（ULyraSettingKeyboardInput + ULyraPlayerMappableKeyProfile + 按键捕获 IInputProcessor）
  - `knowledge/ch5/06-游戏玩法设置.md` — InitializeGameplaySettings：语言选择（ULyraSettingValueDiscrete_Language + 确认对话框）、回放录制（RecordReplay + KeepReplayLimit）
  - `knowledge/ch5/07-性能分析设置.md` — AddPerformanceStatPage：18 项性能指标（FPS/帧时间/网络/延迟）、FLyraPerformanceStatCache 数据采集管线（IPerformanceDataConsumer）、FSampledStatCache 环形缓冲区（125 采样）、SLyraLatencyGraph Slate 自定义渲染、3 个延迟编辑条件
  - `knowledge/ch5/08-音乐组件.md` — B_MusicManagerComponent_Base（蓝图）、MetaSound 背景音乐、战斗强度系统、Fire Stinger
- **代码验证**：Settings/ 目录 8 个 CustomSettings 类 + 6 个 Registry 实现文件 + GameSettings 插件全部 20+ 基类 + Input 系统 4 个关键类 + Performance 系统 3 个关键类 + UI 性能统计 2 个 Widget 类均确认存在。MusicManager 组件确认仅蓝图实现。
- **状态**：完成

## [2026-04-27] ingest | 第六章 — 角色与输入系统

- **来源**：
  - 讲义 065~070, 078~079（共 8 篇 .md，071~072 无对应文件）
  - 代码验证：`Character/`、`Input/`、`Camera/`、`Animation/`
- **产出**：
  - `knowledge/第六章-角色与输入系统.md` — 章节知识入口（子系统一览、架构关系、代码文件索引）
  - `knowledge/ch6/01-角色类层级.md` — ALyraCharacter/ALyraPawn/ALyraCharacterWithAbilities 类层级、接口实现、Team 系统、加速同步（FLyraReplicatedAcceleration）、FastShared 复制、死亡流程、运动模式 Tag 系统
  - `knowledge/ch6/02-初始化状态机与PawnExtension.md` — InitState 4 态链（Spawned→DataAvailable→DataInitialized→GameplayReady）、PawnExtension 组件、IGameFrameworkInitStateInterface 接口、CanChangeInitState 逻辑、PawnData 管理、ASC 生命周期、HealthComponent 绑定
  - `knowledge/ch6/03-HeroComponent与输入绑定.md` — ULyraHeroComponent 初始化状态机参与、ASC 创建、OnSetupInputComponents 输入绑定、相机模式代理
  - `knowledge/ch6/04-移动系统与加速同步.md` — ULyraCharacterMovementComponent、加速度复制管线、Tag 控制运动（GetDeltaRotation/GetMaxSpeed 拦截）、地面检测（FLyraCharacterGroundInfo 帧缓存）、PackNetworkMovementMode 位打包
  - `knowledge/ch6/05-动画蓝图与Tag映射.md` — ULyraAnimInstance、地面距离、FGameplayTagBlueprintPropertyMap 注册与回调（bool/int/float 属性映射）
  - `knowledge/ch6/06-输入系统.md` — ULyraInputComponent、ULyraInputConfig（FLyraInputAction Tag→InputAction 映射）、BindAbilityActivation 绑定流程、输入修饰器系列、InputUserSettings
  - `knowledge/ch6/07-相机系统.md` — ULyraCameraComponent、ULyraCameraMode、ULyraCameraModeStack 层式混合、ULyraPlayerCameraManager、ULyraUICameraManagerComponent、ILyraCameraAssistInterface、InitState 参与
  - `knowledge/ch6/08-第三人称相机与穿透处理.md` — ULyraCameraMode_ThirdPerson UpdateView 计算流程（Pivot→Arm→Lag→Penetration→Offset→FOV）、FLyraPenetrationAvoidanceFeeler 多方向碰撞避免算法
- **代码验证**：Character/ 目录 8 类（ALyraCharacter、ALyraPawn、ALyraCharacterWithAbilities、ULyraPawnExtensionComponent、ULyraHeroComponent、ULyraCharacterMovementComponent、ULyraPawnData、ULyraHealthComponent）+ Input/ 目录 6 类 + Camera/ 目录 7 类 + Animation/ 目录 1 类，全部在源码中存在对应实现
- **状态**：完成

## [2026-04-27] ingest | 第六章补充 — 动画系统 .docx 讲义提取

- **来源**：
  - 讲义 071~077（共 7 篇 .docx，含动画编辑界面截图，图片内容无法提取文本）
  - python-docx 批量提取段落文本
- **背景**：课程纲要标注 072~077 无对应讲义，实际 071~077 以 .docx 格式存在（非 .md），初次 Ingest 时被遗漏。用户反馈后补充处理
- **产出**：
  - `knowledge/ch6/09-动画系统概览.md` — Lyra 动画资产生态全景（骨架网格体/LOD/布娃娃/物理资产/后处理动画/IK/Retarget/主 AnimBP/动画层/武器 locomotion 配置）
  - `knowledge/ch6/10-主动画蓝图线程安全逻辑.md` — BlueprintThreadSafeUpdateAnimation 工作线程逻辑（GetMainAnimBPThreadSafe、UpdateBlendWeightData、UpdateJumpFallData、UpdateSkelControlData、瞄准/腰射条件判断体系）
  - `knowledge/ch6/11-主动画蓝图状态机.md` — AnimGraph Locomotion 状态机（Idle/Start/Cycle/Stop/Pivot/Jump 六态 + Jump 子状态机 JumpStart→JumpApex→FallLoop→FallLand）
  - `knowledge/ch6/12-动画层蓝图.md` — FullBody 子状态层级（IdleState 含 TurnInPlace、StartState/CycleState/StopState/PivotState/JumpStates + LeftHandPose/IK/Aiming/Additives）
  - `knowledge/ch6/13-动画概念速查.md` — 10 个 UE 动画概念速查表（Animation Node Functions、Property Access、Blend Nodes、Pose Warping、Distance Matching、Hand IK、Two Bone IK、Copy Bone、Transform Bone、Virtual Bone）
  - `knowledge/第六章-角色与输入系统.md` — 补充动画系统索引表
- **图片说明**：072《动画要点》、073《打通基本移动和相机》两篇几乎全为截图，无有效段落文本，未生成独立知识文件。图片主要内容为动画编辑器界面和 BlendSpace 配置操作指引
- **状态**：完成

## [2026-04-27] ingest | 第七章 — GAS 能力系统

- **来源**：
  - 讲义 080~090（共 10 篇 .md + 1 篇 .docx）
  - 代码验证：`AbilitySystem/`、`Interaction/`、`Inventory/`
- **产出**：
  - `knowledge/第七章-GAS能力系统.md` — 章节知识入口（知识地图、架构图、关键机制一览）
  - `knowledge/ch7/01-GAS架构概述.md` — AbilitySet、AbilitySystemGlobals、EffectContext、GlobalAbilitySystem、AbilityTagRelationshipMapping、AbilityCost 等全貌
  - `knowledge/ch7/02-ASC与输入激活.md` — ASC 输入管线、ProcessAbilityInput、激活组、标签关系、能力失败、动态 GE、相机模式
  - `knowledge/ch7/03-GA_Jump与GA_Dash.md` — 跳越能力（CharacterMovement 驱动）、冲刺能力（RootMotion 驱动）、AbilityTask 详解
  - `knowledge/ch7/04-GA_Melee.md` — 近战能力：Capsule Trace、友军检查、伤害 GEEC、Lunge
  - `knowledge/ch7/05-属性集与HealthSet.md` — 属性集层级、HealthSet、元属性机制、ClampAttribute、ATTRIBUTE_ACCESSORS
  - `knowledge/ch7/06-GEEC伤害计算.md` — DamageExecution、HealExecution、捕获/衰减/队伍伤害、伤害公式
  - `knowledge/ch7/07-生命值组件.md` — HealthComponent、死亡状态机、属性事件桥接、网络同步
  - `knowledge/ch7/08-库存系统.md` — InventoryManager、ItemDefinition/Fragment/Instance、FFastArraySerializer、IPickupable
  - `knowledge/ch7/09-交互系统.md` — IInteractableTarget、FInteractionOption、ALyraWorldCollectable、拾取流程
  - `knowledge/课程纲要.md` — 更新第七章知识入口链接
  - `docs/UE5_Lyra学习指南_084_讲解GA_Melee.txt` — .docx 提取文本
- **代码验证**：AbilitySystem/ 目录 11 个关键头文件 + Interaction/ 目录 5 个关键文件 + Inventory/ 目录 4 个关键文件 + ShooterCore LyraWorldCollectable，全部在源码中存在对应实现
- **状态**：完成

## [2026-04-27] ingest | 第八章 — 装备与武器系统

- **来源**：
  - 讲义 091~099（共 10 篇 .md）
  - 代码验证：`Equipment/`、`Weapons/`、`Feedback/`、`UI/Weapons/`
- **产出**：
  - `knowledge/第八章-装备与武器系统.md` — 章节知识入口（架构图、分节索引）
  - `knowledge/ch8/装备系统架构.md` — EquipmentDefinition/Instance/ManagerComponent 三段式设计、QuickBar 装备流程、FLyraEquipmentList 网络复制、PickupDefinition、WeaponPickupDefinition
  - `knowledge/ch8/远程武器定义与扩散系统.md` — ULyraWeaponInstance/ULyraRangedWeaponInstance、HeatToSpread 曲线系统、四态精度乘数（Standing/Crouching/Jump/Aim）、FirstShotAccuracy、距离伤害衰减、材质伤害倍率
  - `knowledge/ch8/武器开火技能与预测系统.md` — ULyraGameplayAbility_RangedWeapon、双阶段子弹追踪（Ray→Sweep）、VRandConeNormalDistribution 扩散方向、预测系统、命中同步、成本系统
  - `knowledge/ch8/武器准心与命中标记系统.md` — ULyraWeaponStateComponent、ULyraReticleWidgetBase、UCircumferenceMarkerWidget、SHitMarkerConfirmationWidget、ClientConfirmTargetData 同步
  - `knowledge/ch8/伤害反馈与上下文效果系统.md` — ContextEffectComponent/Subsystem/Library/Interface、AnimNotify、音频分层、摄像震动、触觉反馈
  - `knowledge/ch8/伤害数字弹出系统.md` — LyraDamagePopStyleNiagara、LyraNumberPopComponent_NiagaraText/MeshText、GameplayCue 触发
  - `knowledge/ch8/武器生成器与拾取系统.md` — ALyraWeaponSpawner、拾取/冷却/重生流程、GiveWeapon、网络同步
  - `knowledge/ch8/手榴弹技能.md` — 抛物线投掷技能结构参考
  - `knowledge/ch8/辅助射击系统.md` — Aim Assist 拉力/减速概念
  - `knowledge/课程纲要.md` — 更新第八章知识入口链接
- **代码验证**：Equipment/ 4 个头文件 + Weapons/ 6 个头文件 + UI/Weapons/ 1 个头文件 + WeaponSpawner，全部在源码中存在对应实现。095~099 部分（Feedback、NumberPop、手榴弹、辅助射击）讲义以蓝图截图为主，对应源码多为蓝图资产，C++ 侧已验证 ContextEffect 系列类和 WeaponSpawner 的头文件定义
- **状态**：完成

## [2026-04-27] ingest | 第九章 — 换装队伍与指示器

- **来源**：
  - 讲义 100~109（共 10 篇，其中 109 为 .docx 提取）
  - 代码验证：`Cosmetics/`、`Teams/`、`UI/IndicatorSystem/`、`GameModes/`（GamePhase）、`Development/`、`Messages/`
- **产出**：
  - `knowledge/第九章-角色与装备进阶.md` — 章节知识入口（概述、讲义清单、知识点索引）
  - `knowledge/ch9/ch9_01_换装系统.md` — 换装系统架构（FLyraCharacterPart、FastArray、Controller/Pawn 双组件、动画层选择、换装作弊）
  - `knowledge/ch9/ch9_02_队伍系统.md` — 队伍系统完整架构（ILyraTeamAgentInterface、ULyraTeamDisplayAsset、Info 层级、TeamSubsystem、TeamCreation、Spawning、AsyncAction 观察）
  - `knowledge/ch9/ch9_03_指示器系统.md` — 指示器系统（UIndicatorDescriptor、ULyraIndicatorManagerComponent、SActorCanvas、5 种投影模式、吸附边缘、对象池、交互集成）
  - `knowledge/ch9/ch9_04_AsyncMixin异步加载.md` — AsyncMixin 插件（FAsyncMixin、FLoadingState、FAsyncStep、FAsyncCondition 轮询、FAsyncScope）
  - `knowledge/ch9/ch9_05_荣誉与击杀记录.md` — 荣誉系统 + VerbMessage 击杀记录（FLyraAccoladeDefinitionRow、ULyraAccoladeHostWidget、AssistProcessor、ElimChainProcessor、ElimStreakProcessor、KillFeed UI、计分）
  - `knowledge/ch9/ch9_06_游戏阶段系统.md` — 游戏阶段系统（ULyraGamePhaseAbility、ULyraGamePhaseSubsystem、阶段互斥、观察者、暖场/战斗/计分阶段、积分面板 UI）
  - `knowledge/ch9/ch9_07_机器人系统与AI.md` — 机器人系统（ULyraBotCreationComponent、ALyraPlayerBotController、行为树+EQS+GAS 集成）
  - `knowledge/ch9/ch9_08_外轮廓线.md` — Stencil 外轮廓线技术（后处理材质、CustomDepth、边缘检测、队伍颜色切换）
  - `docs/UE5_Lyra学习指南_109_行为树和环境查询.txt` — .docx 提取文本
  - `knowledge/课程纲要.md` — 更新第九章范围（100~109）、第十章范围缩小（110~122）、新增知识入口链接
- **代码验证**：Cosmetics/ 11 个头文件、Teams/ 11 个头文件（访问器 + 接口 + 接口相关 22 文件）、UI/IndicatorSystem/ 4 个关键类、GameModes/（GamePhase 系列类）、Messages/（VerbMessage 相关）全部在源码中存在对应实现
- **状态**：完成

## [2026-04-27] ingest | 起草 lyra-course 学员交付 Skill

- **来源**：全库 knowledge/ 知识文档（10 章 + 课程纲要）
- **产出**：
  - `dist/skills/lyra-course/SKILL.md` — 主 Skill 文档（架构全景、类索引、6 个核心设计模式、4 条跨系统链路、5 个工作流）
  - `dist/skills/lyra-course/references/Experience框架与加载流程.md`
  - `dist/skills/lyra-course/references/InitState初始化状态机.md`
  - `dist/skills/lyra-course/references/输入系统与InputConfig.md`
  - `dist/skills/lyra-course/references/GAS能力系统架构.md`
  - `dist/skills/lyra-course/references/装备与武器系统.md`
  - `dist/skills/lyra-course/references/UI层栈架构.md`
  - `dist/skills/lyra-course/references/动画系统概览.md`
- **状态**：完成

## [2026-04-27] ingest | 第十章：游戏流程与系统
- **来源**：讲义 110~122（UE5_Lyra学习指南_110_Gyra行为树补充.docx ~ UE5_Lyra学习指南_122_终章.md）、Lyra 源码 Game/UI/、Game/Player/、Game/Messages/、Game/GameModes/、Game/Development/、Game/Replays/、Game/System/、Plugins/PocketWorlds/、Plugins/GameFeatures/TopDownArena/、Plugins/GameplayMessageRouter/
- **产出**：
  - knowledge/ch10/ch10_01_作弊调试系统.md
  - knowledge/ch10/ch10_02_GameplayMessageRouter消息路由.md
  - knowledge/ch10/ch10_03_足迹上下文系统.md
  - knowledge/ch10/ch10_04_ReplicationGraph网络复制图.md
  - knowledge/ch10/ch10_05_自动化测试系统.md
  - knowledge/ch10/ch10_06_回放系统.md
  - knowledge/ch10/ch10_07_Game模板代码补充.md
  - knowledge/ch10/ch10_08_Editor模块代码.md
  - knowledge/ch10/ch10_09_Pocket插件补充.md
  - knowledge/ch10/ch10_10_炸弹人玩法俯视角竞技场.md
  - knowledge/ch10/ch10_11_Gyra行为树补充.md
  - knowledge/第十章-游戏流程与系统.md
  - knowledge/课程纲要.md（更新第十章知识入口链接）
- **状态**：完成

## [2026-04-27] ingest | 全系统对比补充 lyra-course Skill

- **来源**：全库 knowledge/ 知识文档（10 章），与当前 dist/ 产出（SKILL.md + 7 references）逐系统对比
- **比对范围**：10 章 × ~90 篇知识文档 vs 当前 9 篇 dist/ 产出文档
- **对比方法**：三层次对比（原始 knowledge/ → references/ 独立文档 → SKILL.md 汇总），逐系统标注覆盖率
- **补充产出**：
  - 创建 `dist/skills/lyra-course/references/角色初始化与移动系统.md` — PlayerSpawningManager、移动加速度 Polar 量化、Tag 控制运动
  - 创建 `dist/skills/lyra-course/references/库存与消息系统.md` — 四层库存架构、拾取系统、GameplayMessageRouter、GamePhase
  - 扩展 `dist/skills/lyra-course/references/GAS能力系统架构.md` — 追加 ASC 输入激活管线、GA_Jump 模板、HealthComponent 死亡状态机、AbilityCost 消耗系统
  - 更新 `dist/skills/lyra-course/SKILL.md`：
    - 源码目录结构：新增 Messages/、Weapons/ 目录
    - 模块依赖图：新增 HealthComponent、Messages、GamePhase 连接
    - 关键类索引：新增 4 个新层（Player/Inventory/Messages/GamePhase）+ 扩展现有层，共 +16 条目
    - 设计模式：新增模式七（HealthComponent 死亡状态机）、模式八（GameplayMessageRouter 发布—订阅）
    - 跨系统调用链路：新增链路 5（伤害→死亡处理）、链路 6（拾取→库存→装备）
    - 工作流：新增工作流 6（添加库存物品）、工作流 7（添加伤害反馈与死亡表现）
    - 扩展阅读表：更新为 9 篇 reference 文档
- **状态**：完成

## [2026-04-27] ingest | dist/README.md：课程促销与 Skill 介绍

- **来源**：lyra-course Skill 内容 + 课程信息 + 课程促销文案
- **产出**：
  - `dist/README.md` — 课程促销 README，包含课程简介、lyra-course Skill 介绍（内容覆盖、使用方式、适用场景）
- **放置策略**：位于 `dist/` 根目录而非 Skill 内部，避免 Skill 提交到 GitHub 时产生混淆，同时作为 dist/ 仓库的入口页面
- **状态**：完成