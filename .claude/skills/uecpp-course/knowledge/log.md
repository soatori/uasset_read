# 操作日志

> 按时间追加的知识操作记录。每条记录以 `## [日期] 操作类型 | 标题` 开头，便于 `grep` 检索。
> 操作类型：`ingest`（知识摄入）、`query`（知识查询归档）、`lint`（健康检查）、`update`（文档更新/策略变更）。

## [2026-04-27] update | 蒸馏策略制定（基于 Lyra 经验）
- **来源**：Lyra 课程蒸馏输出物分析（`dist/skills/xg-lyra-course/`）
- **变更文件**：`knowledge/课程纲要.md` — 新增"七、知识蒸馏策略"章节
- **策略要点**：
  - 四阶段流程：章节级 Ingest → 细粒度拆分 → 横向模式提炼 → Skill 蒸馏
  - 章节分类 P0~P2 三档优先级（第零~四章已标记为已完成）
  - 细粒度文档模板（继承 Lyra references/ 风格）
  - 6 个待提炼的横向模式
  - 最终 Skill 产出物结构规划
- **状态**：完成 ✅

## [2026-04-29] update | Ingest 经验固化增加自检机制
- **来源**：用户反馈第23章 Ingest 遗漏了经验固化环节
- **变更文件**：
  - `AGENTS.md`（编辑）— 步骤 7 "经验固化"末尾增加"自检（强制）"子句：所有 Ingest 产出写入后，AI 必须读取 log.md 末尾确认同日的固化记录存在
  - `skills/xg-course-context/SKILL.md`（编辑）— 6.2 流程图末尾增加"经验固化（强制自检）"分支节点；6.3 输出规范增加同名自检项
- **自检规则**：TodoWrite 标记 Ingest 为完成之前，必须确认 log.md 中已存在同日的 `update | 固化` 记录（或 Ingest 中声明"本次无新增固化经验"），缺失则补充，不可跳过
- **设计意图**：经验固化本身已有"强制"标注，但缺少"是否真的做了"的检查环节。自检机制将检查动作嵌入 TodoWrite 完成前的流程，作为 Ingest 的最后一个必要步骤
- **状态**：完成 ✅

## [2026-04-28] ingest | 第十七章 多线程知识提取
- **来源**：字幕 x11（`subtitles/017第十七章多线程/` 下 001~010）、代码 x8（`code/001_XGSampleDemo/Source/XGSampleDemo/020_Thread/` 下 4 组 8 个文件）
- **代码核对**：逐帧比对代码实现与字幕讲解的一致性。确认 FRunnable/FCriticalSection/FThreadSafeBool/AsyncTask/Async/FGraphEvent/ParallelFor 的代码实现与字幕描述一致。补充代码中额外发现：SetMyNum 的 IsInGameThread 保护性重分发模式、PrintWarning 线程安全日志模式
- **差异记录**：
  - `InitXGSimpleThreadBool()` 实际创建 `FXGSimpleRunnable`（带锁版本）而非 `FXGSimpleRunnableBool`（FThreadSafeBool 版本），FThreadSafeBool 类已定义但未被 Subsystem 实例化
  - `InitParallelFor()` 使用 `FDateTime::Now().GetTicks()` 计时，而非字幕提及的 `FPlatformTime::Cycles64()`
- **产出**：
  - `knowledge/ch17/01-虚幻多线程基础架构.md`（新建）
  - `knowledge/ch17/02-FRunnable与FRunnableThread.md`（新建）
  - `knowledge/ch17/03-加锁与线程安全.md`（新建）
  - `knowledge/ch17/04-AsyncTask异步任务.md`（新建）
  - `knowledge/ch17/05-Async函数与TFuture.md`（新建）
  - `knowledge/ch17/06-FGraphEvent任务依赖系统.md`（新建）
  - `knowledge/ch17/07-ParallelFor并行循环.md`（新建）
  - `knowledge/ch17/08-经典卡主线程的方式.md`（新建）
  - `knowledge/第十七章-多线程.md`（重写）— 从占位页更新为完整索引页
- **状态**：完成 ✅

## [2026-04-27] fix | 修正优先级表格（第零~四章已完成状态）
- **来源**：用户反馈指正
- **变更文件**：`knowledge/课程纲要.md` — 优先级表格中第零~四章从 P0/P3 改为 ✅ 已完成
- **说明**：第零章（116 行）、第一章（234 行）、第二章（400 行）已有完整内容；第 3~4 章含 ch3/ch4 细粒度文档。错误地将它们标为待处理，已修正
- **状态**：完成 ✅

## [2026-04-27] update | 课程纲要与章节入口文件全量更新
- **来源**：字幕全量上传（共 447 个 .srt 文件，37 章节）
- **变更文件**：
  - `knowledge/课程纲要.md`（重写）— 章节总数从 36→37，章节结构表从 5 行扩展至 37 行全量覆盖，移除"后续章节待上传"部分，更新字幕覆盖状态为全量已完成
  - `knowledge/第五章-TMap.md`（新建）
  - `knowledge/第六章-TSet.md`（新建）
  - `knowledge/第七章-基础案例.md`（新建）
  - `knowledge/第八章-定时器.md`（新建）
  - `knowledge/第九章-委托.md`（新建）
  - `knowledge/第十章-字符串.md`（新建）
  - `knowledge/第十一章-GameplayTag.md`（新建）
  - `knowledge/第十二章-日志记录.md`（新建）
  - `knowledge/第十三章-编程子系统.md`（新建）
  - `knowledge/第十四章-断言.md`（新建）
  - `knowledge/第十五章-配置.md`（新建）
  - `knowledge/第十六章-智能指针.md`（新建）
  - `knowledge/第十七章-多线程.md`（新建）
  - `knowledge/第十八章-ControlFlows.md`（新建）
  - `knowledge/第十九章-虚幻商城标准插件开发.md`（新建）
  - `knowledge/第二十章-虚幻标准第三方库封装.md`（新建）
  - `knowledge/第二十一章-LibWebP集成使用_生成.md`（新建）
  - `knowledge/第二十二章-LibWebP集成使用_展示.md`（新建）
  - `knowledge/第二十三章-虚幻Slate独立程序.md`（新建）
  - `knowledge/第二十四章-商业化Json读写使用.md`（新建）
  - `knowledge/第二十五章-HTTP基础_获取公网时间.md`（新建）
  - `knowledge/第二十六章-HTTPServer_自定义登录注册服务器.md`（新建）
  - `knowledge/第二十七章-HTTP上传文件_摄像头活体检测.md`（新建）
  - `knowledge/第二十八章-HTTP流式传输_大模型通讯.md`（新建）
  - `knowledge/第二十九章-WebSocket_语音识别.md`（新建）
  - `knowledge/第三十章-WebSocket_语音合成.md`（新建）
  - `knowledge/第三十一章-WebSocketSever_MMO分布式服务器通信.md`（新建）
  - `knowledge/第三十二章-TCP实战_自动发送邮箱验证码.md`（新建）
  - `knowledge/第三十三章-虚幻基础案例模板.md`（新建）
  - `knowledge/第三十四章-部署MMO分布式多人游戏.md`（新建）
  - `knowledge/第三十五章-多人网络游戏基础.md`（新建）
  - `knowledge/第三十六章-虚幻高级网络游戏技能系统GAS案例.md`（新建）
- **状态**：完成 ✅

## [2026-04-26] ingest | 第三章 基础概念
- **来源**：字幕 x14（000~013）、代码 x12（001_BaseType/002_UFunction/003_UInterface）、文档（完全入门指南.docx）
- **产出**：知识文档拆分（`knowledge/ch3/` 下 10 个细粒度文件），原始文档保留为索引
- **变更文件**：
  - `knowledge/第三章-基础概念.md` → 重写为索引页，含全部子页面链接
  - `knowledge/ch3/ue-reflection.md`（新建）
  - `knowledge/ch3/naming-conventions.md`（新建）
  - `knowledge/ch3/uobject.md`（新建）
  - `knowledge/ch3/uclass.md`（新建）
  - `knowledge/ch3/uproperty.md`（新建）
  - `knowledge/ch3/ustruct.md`（新建）
  - `knowledge/ch3/uenum.md`（新建）
  - `knowledge/ch3/ufunction.md`（新建）
  - `knowledge/ch3/uinterface.md`（新建）
  - `knowledge/ch3/fundamentals.md`（新建）
  - `knowledge/log.md`（新建）
- **metadata**：课程章节覆盖 12 模块，引用代码文件 12 对
- **状态**：完成 ✅

## [2026-04-26] lint | 第三章知识文档补充代码引用
- **来源**：用户反馈第三章知识文档缺少代码文件引用
- **变更文件**：
  - `knowledge/ch3/naming-conventions.md`（编辑）— 新增"配套代码"表格，映射各前缀示例类到对应代码文件
  - `knowledge/ch3/fundamentals.md`（编辑）— 新增"配套代码"表格，映射 Actor 生命周期/CDO/NewObject/GC 保护到 XGBaseActor/XGClassActor/XGObjectActor
  - `knowledge/ch3/ue-reflection.md`（编辑）— 新增"配套代码"表格，映射 GENERATED_BODY/GENERATED_USTRUCT_BODY/UCLASS/UPROPERTY/UFUNCTION/UENUM/UINTERFACE 宏到各头文件
  - `knowledge/ch3/uclass.md`（编辑）— 新增"配套代码"表格，映射 UCLASS 声明/BlueprintType/MinimalAPI/XGSAMPLEDEMO_API 到 XGClassActor/XGBaseObject/InterfaceActor
  - `knowledge/ch3/uenum.md`（编辑）— 新增"配套代码"表格，映射 EMYUENUM/EXGActorType/EColorBits 到 XGBaseStructEnum/InterfaceActor/XGPropertyActor
  - `knowledge/ch3/ustruct.md`（编辑）— 补充 FXGPropertyStruct2（含 UObject* 指针的结构体）位于 XGBaseStruct.h 的说明
  - `knowledge/第三章-基础概念.md`（编辑）— 索引页注明子页面已标注代码文件路径
- **规则**：按强化后的代码核对流程操作，子页面中每个知识点/类名均标注对应代码文件路径
- **状态**：完成 ✅

## [2026-04-26] ingest | 第四章 TArray 详解
- **来源**：字幕 x19（`subtitles/004第四章TArray/` 下 001~019）
- **产出**：知识文档拆分（`knowledge/ch4/` 下 14 个细粒度文件），章节索引页 `knowledge/第四章-TArray.md`
- **变更文件**：
  - `knowledge/第四章-TArray.md`（新建）— 章节索引页，含全部子页面链接
  - `knowledge/ch4/creation.md`（新建）— 创建与初始化
  - `knowledge/ch4/adding.md`（新建）— 添加元素（Add/Emplace/Append/Insert）
  - `knowledge/ch4/equality.md`（新建）— 结构体相等性判断
  - `knowledge/ch4/iteration.md`（新建）— 迭代
  - `knowledge/ch4/sorting.md`（新建）— 排序
  - `knowledge/ch4/predicate.md`（新建）— 二元谓词与 Lambda
  - `knowledge/ch4/querying.md`（新建）— 查询与访问
  - `knowledge/ch4/indexing.md`（新建）— 索引
  - `knowledge/ch4/finding.md`（新建）— 查找函数
  - `knowledge/ch4/advanced-query.md`（新建）— 高级查询
  - `knowledge/ch4/removing.md`（新建）— 移除操作
  - `knowledge/ch4/operators.md`（新建）— 运算符
  - `knowledge/ch4/heap.md`（新建）— 堆操作
  - `knowledge/ch4/memory.md`（新建）— 内存管理
  - `knowledge/ch4/raw-memory.md`（新建）— 原始内存
  - `knowledge/课程纲要.md`（编辑）— 补充第四章章节信息与字幕覆盖状态
- **状态**：完成 ✅

## [2026-04-26] ingest | SUMMARY.md 迁移至 knowledge/ 规范统一
- **来源**：用户反馈 SUMMARY.md 不应放在 subtitles/（只读区域）中
- **变更**：
  - 迁移：`subtitles/000/SUMMARY.md` → `knowledge/第零章-宣传视频.md`
  - 迁移：`subtitles/001/SUMMARY.md` → `knowledge/第一章-部署环境.md`
  - 迁移：`subtitles/002/SUMMARY.md` → `knowledge/第二章-基本架构.md`
  - 删除：3 个 subtitles/ 下的旧 SUMMARY.md
  - 更新引用：`knowledge/课程纲要.md`、`xg-course-context/SKILL.md`、`AGENTS.md`
- **产出**：
  - `knowledge/第零章-宣传视频.md`（新建）
  - `knowledge/第一章-部署环境.md`（新建）
  - `knowledge/第二章-基本架构.md`（新建）
- **规范确立**：章节知识入口文件统一放在 `knowledge/` 下，命名为 `第X章-名称.md`
- **状态**：完成 ✅

## [2026-04-26] ingest | SKILL.md 架构升级
- **来源**：Karpathy LLM Wiki 模式分析
- **变更**：
  - `xg-uecpp-knowledge/SKILL.md`：增加 Query 操作定义、log.md 规范、Lint 操作定义
  - `knowledge/课程纲要.md`：第三章引用更新为细粒度知识文档路径
- **状态**：完成 ✅

## [2026-04-26] lint | 规则强化：代码核对强制化 + 代码引用规范化
- **来源**：第四章知识提取时遗漏代码核对，用户反馈后补充 14 个遗漏知识点
- **变更文件**：
  - `AGENTS.md`（编辑）— 步骤 4 拆分为代码核对（强制）+ 搜索 docs，新增代码缺失记录规范
  - `skills/xg-course-context/SKILL.md`（编辑）— 6.2 步骤 4 强化为"代码核对（强制）"；6.3 输出规范新增"代码引用"要求（每 API/函数/类名标注对应代码文件路径，格式为 markdown 链接）
- **规则变更要点**：
  - 每个类名、函数名、API 名称都必须在 `code/` 中找到对应实现
  - 知识文档每提及一个代码元素必须标注对应代码文件路径
  - 找不到对应实现时记录到 `log.md`
- **状态**：完成 ✅

## [2026-04-26] ingest | 第零章~第二章 SUMMARY.md 格式统一
- **产出**：
  - `subtitles/000第零章宣传视频/SUMMARY.md`（新建）— 课程概览、12 案例展示、前置要求、讲师背景、学习建议
  - `subtitles/001第一章部署环境/SUMMARY.md`（完善）— 补充参考资源章节
  - `subtitles/002第二章基本架构/SUMMARY.md`（完善）— 补充参考资源章节
  - `knowledge/课程纲要.md`（完善）— 各章节统一补充 SUMMARY.md 路径引用
- **变更文件**：
  - `subtitles/000第零章宣传视频/SUMMARY.md`（新建）
  - `subtitles/001第一章部署环境/SUMMARY.md`（编辑）
  - `subtitles/002第二章基本架构/SUMMARY.md`（编辑）
  - `knowledge/课程纲要.md`（编辑）
- **状态**：完成 ✅

## [2026-04-28] ingest | 第十八章 ControlFlows 知识提取
- **来源**：字幕 x10（`subtitles/018第十八章ControlFlows/` 下 001~010）、代码 x4（`code/001_XGSampleDemo/Source/XGSampleDemo/021_ControlFlows/` 下 XGControlFlowsSubsystem.h/.cpp、XGControlFlowsActor.h/.cpp）
- **代码核对**：逐帧比对代码实现与字幕讲解的一致性。确认 FControlFlow API、ManageTask 结构体、Tick 轮询逻辑与字幕描述一致。补充代码中额外发现：
  - FTickableGameObject 的 IsTickable 返回 `!IsTemplate()`（字幕未提及）
  - CallInitProgress/CallInitResult 采用委托副本 + AsyncTask 推回 GameThread 的防重入模式
  - UpdateTaskStatus 使用 `ManageList.Find(InManageTaskID)` 而非遍历（字幕用双循环）
  - ManageTaskResponse 广播在单独的循环中执行（三段式 Tick 结构，字幕未强调）
- **差异记录**：
  - 实际代码的 FXGControlFlowsTask 继承自 `TSharedFromThis`，但字幕中使用裸 TSharedPtr
  - 实际代码的 `CheckManageTaskStatus` 在 Failed 检测后不立即 return，而是继续执行 None 检查（字幕版先 return Failed 再检查 None）
  - Actor 的 BeginPlay 中没有调用 InitLevel（字幕演示中直接调用），实际调用入口由 Blueprint 触发
  - 实际代码的 InitLocalAsset 先 Broadcast 再 ContinueFlow（字幕讨论两种顺序的差异）
- **产出**：
  - `knowledge/ch18/01-FControlFlow异步编排框架.md`（新建）
  - `knowledge/ch18/02-模块配置与插件依赖.md`（新建）
  - `knowledge/ch18/03-蓝图交互委托框架.md`（新建）
  - `knowledge/ch18/04-异步执行与线程跳跃模式.md`（新建）
  - `knowledge/ch18/05-ManageTask并行子任务架构.md`（新建）
  - `knowledge/ch18/06-Tick状态检测与资源清理.md`（新建）
  - `knowledge/第十八章-ControlFlows.md`（重写）— 从占位页更新为完整索引页
- **状态**：完成 ✅

## [2026-04-28] ingest | 第八章 定时器知识提取
- **来源**：字幕 x5（`subtitles/008第八章定时器/` 下 001~005）、代码 x4（`code/001_XGSampleDemo/Source/XGSampleDemo/011_Timer/` 下 TimerActor.h/.cpp、XGCountDownTimerActor.h/.cpp）
- **代码核对**：逐帧比对代码实现与字幕讲解的一致性。确认 SetTimer/BeginPlay 创建、循环控制（RepeatingCallsRemaining 递减）、Pause/Resume/IsTimerActive/GetTimerRate/GetTimerElapsed 查询 API、CountDownTimerActor 的 AdvanceTimer 驱动模式、BlueprintNativeEvent 双向协作模式与字幕描述一致
- **差异记录**：无显著差异。字幕演示与代码实现完全一致
- **产出**：
  - `knowledge/ch8/01-定时器基本概念与FTimerManager.md`（新建）
  - `knowledge/ch8/02-SetTimer基本使用与循环控制.md`（新建）
  - `knowledge/ch8/03-CountDownTimerActor倒计时实例.md`（新建）
  - `knowledge/ch8/04-蓝图交互与BlueprintNativeEvent.md`（新建）
  - `knowledge/第八章-定时器.md`（重写）— 从占位页更新为完整索引页
- **状态**：完成 ✅

## [2026-04-28] ingest | 第五章 TMap 知识提取
- **来源**：字幕 x11（`subtitles/005第五章TMap/` 下 001~011）、代码 x2（`code/001_XGSampleDemo/Source/XGSampleDemo/005_Map/` 下 MapActor.h/.cpp）
- **代码核对**：逐帧比对代码实现与字幕讲解的一致性。确认 TMap Add/Emplace/Append、迭代（for-range + Iterator）、查询（Find/FindOrAdd/FindRef/FindKey/operator[]）、移除（Remove/FindAndRemoveChecked/RemoveAndCopyValue）、排序（KeySort/ValueSort）、复制赋值/MoveTemp、Slack/Compact/Shrink、结构体重载（operator==/GetTypeHash）、自定义 KeyFuncs（BaseKeyFuncs 模板）、调试工具（GetAllocatedSize/Dump/CountBytes）与字幕描述一致
- **差异记录**：无显著差异。字幕演示与代码实现完全一致
- **产出**：
  - `knowledge/ch5/overview.md`（新建）
  - `knowledge/ch5/creation.md`（新建）
  - `knowledge/ch5/iteration.md`（新建）
  - `knowledge/ch5/query.md`（新建）
  - `knowledge/ch5/removal-and-memory.md`（新建）
  - `knowledge/ch5/sorting-and-operators.md`（新建）
  - `knowledge/ch5/struct-as-key.md`（新建）
  - `knowledge/ch5/utilities.md`（新建）
  - `knowledge/第五章-TMap.md`（重写）— 从占位页更新为完整索引页
- **状态**：完成 ✅

## [2026-04-28] ingest | 第六章 TSet 知识提取
- **来源**：字幕 x7（`subtitles/006第六章TSet/` 下 001~007）、代码 x2（`code/001_XGSampleDemo/Source/XGSampleDemo/006_Set/` 下 SetActor.h/.cpp）
- **代码核对**：逐帧比对代码实现与字幕讲解的一致性。确认 TSet Add/Emplace/Append、迭代（for-range/CreateIterator/CreateConstIterator）、查询（Num/Contains/Find/FSetElementId/Array()）、移除（Remove/Reset/Empty/Reserve）、排序（Sort/StableSort）、拷贝赋值深拷贝语义、Slack（CompactStable/Shrink）与字幕描述一致
- **差异记录**：无显著差异。字幕演示与代码实现完全一致
- **产出**：
  - `knowledge/ch6/overview.md`（新建）
  - `knowledge/ch6/creation.md`（新建）
  - `knowledge/ch6/iteration-and-query.md`（新建）
  - `knowledge/ch6/removal-sort-operators.md`（新建）
  - `knowledge/ch6/defaultkeyfuncs-and-utilities.md`（新建）
  - `knowledge/第六章-TSet.md`（重写）— 从占位页更新为完整索引页
- **状态**：完成 ✅

## [2026-04-28] ingest | 第七章 基础案例知识提取
- **来源**：字幕 x19（`subtitles/007第七章基础案例/` 下 001~019）、代码 x14（`code/001_XGSampleDemo/Source/XGSampleDemo/007_QuickStart/`、`008_GameCamera/`、`009_PlayerCamera/`、`010_ComponentAndCollision/`、`code/003_XGFPS0Demo/Source/XGFPS0Demo/`）
- **代码分布注意**：本章代码横跨 5 个代码目录（007_QuickStart、008_GameCamera、009_PlayerCamera、010_ComponentAndCollision、003_XGFPS0Demo），用户特别提示避免遗漏
- **代码核对**：逐帧比对代码实现与字幕讲解的一致性。确认 FloatingActor（GetGameTimeSinceCreation + SetActorLocationAndRotation）、FloatingActorModify（BeginPlay 应用 NewMesh、FloatSpeed/RotationSpeed 驱动 Tick）、XAGCameraDirector（SetViewTarget/CameraTwo+CameraOne 双摄像头切换）、XGCameraDirectorModify（FCameraToggleInfo USTRUCT + GetAllActorsOfClass + check 断言）、XGPawnWithCamera（SceneComponent→StaticMesh→SpringArm→Camera 组件链 + 输入中间变量模式）、XGCollidingPawn（SphereComponent 根 + SafeMoveUpdatedComponent + SlideAlongSurface + 输入转发模式）、XGFPSProjectile（SphereComponent 碰撞根 + ProjectileMovementComponent + OnHit AddDynamic + InitialLifeSpan）、XGFPSCharacter（Camera-to-World 空间变换 + TSubclassOf + GunOffset + OwnerNoSee/OnlyOwnerSee）、XGFPSHUD（DrawHUD + Canvas->DrawItem）与字幕描述一致
- **差异记录**：
  - 实际代码的 FloatingActor 使用 `ConstructorHelpers::FObjectFinder` 硬编码路径加载 Mesh，字幕使用静态引用字符串；实际代码的 Tick 使用 `GetGameTimeSinceCreation()` 而非 `GetWorld()->GetTimeSeconds()`（字幕使用后者）
  - 实际代码的 XGCameraDirectorModify 的 USTRUCT 中 CameraOne 字段名为 `CameraOne` + `CameraBlendTime`，字幕演示的 USTRUCT 仅演示 `Camera` 作为字段名（两者指向同一设计意图）
  - 实际代码的 XGPawnWithCamera 的移动计算使用 `GetSafeNormal() * 100.0f` 再乘 DeltaTime（最终速度约 100 单位/秒），字幕演示中速度和加速度值有细微差别
  - 实际代码的 XGCollidingPawn 的 TickComponent 使用 `ConsumeInputVector().GetClampedToMaxSize(1.0f) * DeltaTime * 150.0f`，字幕演示使用 100.0f（速度值差异）
  - 实际代码的 XGFPSProjectile 的 `BodyInstance.SetCollisionProfileName(TEXT("ProjectileFile"))`，字幕演示使用 `SetCollisionProfileName(TEXT("Projectile"))`（名称可能有差异，取决于项目配置）
  - 实际代码的 XGFPSCharacter 的 MoveForward 使用 `FRotationMatrix(Controller->GetControlRotation()).GetScaledAxis(EAxis::X)`，字幕演示强调使用控制器的旋转而非 Actor 的旋转（方向一致）
  - 第 003_XGFPS0Demo 项目代码不完整，缺少 FPSMesh 构造函数赋值（仅声明），实际在 Blueprint 中设置
- **产出**：
  - `knowledge/ch7/01-FloatingActor-编辑快速入门.md`（新建）
  - `knowledge/ch7/02-GameCamera-游戏摄像机.md`（新建）
  - `knowledge/ch7/03-PlayerCamera-玩家控制摄像机.md`（新建）
  - `knowledge/ch7/04-ComponentAndCollision-组件碰撞与自定义移动.md`（新建）
  - `knowledge/ch7/05-FPSProjectile-发射物系统.md`（新建）
  - `knowledge/ch7/06-FPSCharacter-第一人称角色与输入.md`（新建）
  - `knowledge/第七章-基础案例.md`（重写）— 从占位页更新为完整索引页
- **状态**：完成 ✅

## [2026-04-28] ingest | 第九章 委托知识提取
- **来源**：字幕 x9（`subtitles/009第九章委托/` 下 001~009）、代码 x8（`code/001_XGSampleDemo/Source/XGSampleDemo/012_Delegate/` 下 4 组 8 个文件：XGSingleDelegateActor.h/.cpp、XGMultiDelegateActor.h/.cpp、XGDynamicSingleActor.h/.cpp、XGDynamicMulityDelegateActor.h/.cpp）
- **序号注意**：字幕文件夹编号为 `009第九章委托`，代码文件夹编号为 `012_Delegate`，序号不同但知识点一一对应
- **代码核对**：逐帧比对代码实现与字幕讲解的一致性。确认四种委托类型（单播/多播/动态单播/动态多播）的声明宏体系、API 模式、生命周期管理与字幕描述一致。代码中补充了字幕未详细展开的细节：
  - XGSingleDelegateActor 的 BeginPlay 中同时演示了 8 种绑定方式 + Create 替换
  - XGMultiDelegateActor 的 AXGMultiExecuteActor 使用 GUID 标识 + FDelegateHandle 管理生命周期
  - XGDynamicMulityDelegateActor 中 UPROPERTY(BlueprintAssignable) 与非 UPROPERTY 版本的对比
- **差异记录**：无显著差异。字幕演示与代码实现完全一致
- **产出**：
  - `knowledge/ch9/delegate-overview.md`（新建）— 四种委托类型概述、声明宏体系、操作对照表
  - `knowledge/ch9/single-cast-core.md`（新建）— 单播委托核心（声明/绑定/执行/返回值/Payload）
  - `knowledge/ch9/single-cast-bindings.md`（新建）— 8 种绑定方式详解及生命周期安全等级
  - `knowledge/ch9/single-cast-create.md`（新建）— Create 前缀方法与委托替换技术
  - `knowledge/ch9/multi-cast.md`（新建）— 多播委托（Add/Broadcast/Remove、FDelegateHandle、多执行 Actor 模式）
  - `knowledge/ch9/dynamic-single.md`（新建）— 动态单播委托（Init/Call/Release 模式、蓝图集成）
  - `knowledge/ch9/dynamic-multi.md`（新建）— 动态多播委托（BlueprintAssignable、AddDynamic/RemoveDynamic、Bind Event）
  - `knowledge/第九章-委托.md`（重写）— 从占位页更新为完整索引页
- **状态**：完成 ✅

## [2026-04-28] ingest | 第十章 字符串知识提取
- **来源**：字幕 x12（`subtitles/010第十章字符串/` 下 001~012）、代码 x2（`code/001_XGSampleDemo/Source/XGSampleDemo/013_String/` 下 XGStringActor.h/.cpp）
- **材料自动识别**：本次未指定素材路径，AI 自行识别字幕文件夹 `010第十章字符串/` 和代码文件夹 `013_String/`。代码编号 013 与章节编号 010 不一致，但通过类名 `XGStringActor` 确认对应关系
- **代码核对**：逐帧比对代码实现与字幕讲解的一致性。确认代码中 14 个 UFUNCTION 与字幕知识点一一对应：
  - `InitString()` — FString/FName/FText 三种类型互相转换
  - `PropertyString()` — 数值/结构体/UObject ↔ FString 转换
  - `ModifyString()` — Compare/Contains/Find
  - `ModifyString2()` — Append/Replace/ReplaceInline
  - `LogString()` — FString::Printf/UE_LOG 格式化
  - `OperateString()` — Left/Mid/Right 截取 + ToUpper/ToLower
  - `OperateString2()` — Split/ParseIntoArray 切割
  - `OperateURL()` — URL 解析实战
  - `TransformString()` — 已废弃宏（错误示范）
  - `WrongUse()` — 临时指针生命周期陷阱
  - `TransformStringRight()` — StringCast/FTCHARToUTF8（正确做法）
  - `FNameTest()` — FName 比较/FNAME_Find
  - `FTextTest()` — LOCTEXT/NSLOCTEXT 声明
  - `FTextFormat()` — FText::Format + 格式化说明符
- **差异记录**：无显著差异。字幕演示与代码实现完全一致。代码中的 `WrongUse` 函数在字幕中未作为独立知识点讲解，而是作为错误演示的补充代码
- **文件名-内容偏差记录**：009 文件名标"FString的切割"但实际内容为编码转换，010 文件名标"FString的编码转换细节"但实际内容为 FName
- **产出**：
  - `knowledge/ch10/01-三种字符串类型概述.md`（新建）
  - `knowledge/ch10/02-字符编码与TCHAR系统.md`（新建）
  - `knowledge/ch10/03-FString基本操作.md`（新建）
  - `knowledge/ch10/04-FString类型转换.md`（新建）
  - `knowledge/ch10/05-FString切割与解析.md`（新建）
  - `knowledge/ch10/06-FString编码转换.md`（新建）
  - `knowledge/ch10/07-FName使用详解.md`（新建）
  - `knowledge/ch10/08-FText本地化与格式化.md`（新建）
  - `knowledge/ch10/09-FString-FName-FText三者转换.md`（新建）
  - `knowledge/第十章-字符串.md`（重写）— 从占位页更新为完整索引页
- **经验固化**：追加 SKILL.md 16.15~16.18（文件名-内容偏差识别、函数级代码-字幕映射、三层教学结构文档策略、分层递进框架保留原则）
- **状态**：完成 ✅

## [2026-04-28] ingest | 第十一章 GameplayTag 知识提取
- **来源**：字幕 x4（`subtitles/011第十一章GameplayTag/` 下 001~004）、代码 x4（`code/001_XGSampleDemo/Source/XGSampleDemo/014_Tag/` 下 XGTagType.h/.cpp、XGTagActor.h/.cpp）
- **材料自动识别**：本次未指定素材路径，AI 自行识别字幕文件夹 `011第十一章GameplayTag/` 和代码文件夹 `014_Tag/`。代码编号 014 与章节编号 011 不一致，但通过类名 `XGTagActor`、`XGTagType` 确认对应关系
- **代码核对**：逐帧比对代码实现与字幕讲解的一致性。确认代码与字幕对应关系：
  - XGTagType.h — UE_DECLARE_GAMEPLAY_TAG_EXTERN 声明 `XG_Mode_Coding`、`XG_Mode_Working`
  - XGTagType.cpp — UE_DEFINE_GAMEPLAY_TAG_COMMENT 定义带注释的标签
  - XGTagActor.h — 继承 `IGameplayTagAssetInterface`，两个 FGameplayTagContainer 属性（MyTagContainer、MyStatusTagContainer）
  - XGTagActor.cpp — UE_DEFINE_GAMEPLAY_TAG_STATIC（文件级标签）、BeginPlay 中 AddTag + RequestGameplayTag、GetOwnedGameplayTags 聚合容器
- **差异记录**：无显著差异。字幕演示与代码实现完全一致。字幕将 GetOwnedGameplayTags 简化为"函数重写"，代码实际通过 `IGameplayTagAssetInterface` 接口实现
- **产出**：
  - `knowledge/ch11/01-GameplayTag概述与设计动机.md`（新建）
  - `knowledge/ch11/02-GameplayTag的四种创建方式.md`（新建）
  - `knowledge/ch11/03-GameplayTag匹配操作.md`（新建）
  - `knowledge/ch11/04-GameplayTag的C++声明与使用.md`（新建）
  - `knowledge/ch11/05-FGameplayTagContainer与GetOwnedGameplayTags.md`（新建）
  - `knowledge/ch11/06-GameplayTag版本兼容问题.md`（新建）
  - `knowledge/第十一章-GameplayTag.md`（重写）— 从占位页更新为完整索引页
- **经验固化**：追加 SKILL.md 16.19~16.22（字幕精炼度自适应、字幕简化接口还原、自动发现路径验证、教学顺序与实践推荐顺序张力处理）
- **状态**：完成 ✅

## [2026-04-28] ingest | 第十二章 日志记录知识提取
- **来源**：字幕 x4（`subtitles/012第十二章日志记录/` 下 001~004）、代码 x4（`code/001_XGSampleDemo/Source/XGSampleDemo/015_Log/` 下 XGLogType.h/.cpp、XGLogActor.h/.cpp）
- **材料自动识别**：本次未指定素材路径，AI 自行识别字幕文件夹 `012第十二章日志记录/` 和代码文件夹 `015_Log/`。代码编号 015 与章节编号 012 不一致（+3 偏移模式在第 9~12 章持续确认），但通过类名 `XGLogActor`、`XGLogType` 确认对应关系
- **代码核对**：逐帧比对代码实现与字幕讲解的一致性。确认 DECLARE_LOG_CATEGORY_EXTERN/DEFINE_LOG_CATEGORY 宏模式、DEFINE_LOG_CATEGORY_STATIC 文件级类别、UE_LOG 的 7 个级别演示（Fatal 注释保留）、FString::Printf 格式化、格式说明符（%d/%s/%f）、UE_LOGFMT 两种绑定形式、AsyncTask 线程安全日志、GEngine->AddOnScreenDebugMessage 与字幕描述一致
- **差异记录**：无显著差异。字幕演示与代码实现完全一致
- **产出**：
  - `knowledge/ch12/01-UE日志系统概述与日志级别.md`（新建）
  - `knowledge/ch12/02-定义日志类别（DECLARE-DEFINE宏模式）.md`（新建）
  - `knowledge/ch12/03-UE_LOG使用与格式化.md`（新建）
  - `knowledge/ch12/04-UE_LOGFMT结构化日志（UE5.2+）.md`（新建）
  - `knowledge/ch12/05-日志运行时控制与多线程安全.md`（新建）
  - `knowledge/第十二章-日志记录.md`（重写）— 从占位页更新为完整索引页
- **经验固化**：追加 SKILL.md 16.23~16.25（宏声明模式一致性认知、"两套并行 API"版本敏感处理、"概述性字幕"低密度处理策略）
- **本章关注点**：001 字幕为"概述性字幕"（VS 调试器/Blueprint 调试器/Widget Reflector 等外部工具概览），信息密度低，未独立成文
- **状态**：完成 ✅

## [2026-04-28] ingest | 第十三章 编程子系统知识提取
- **来源**：字幕 x5（`subtitles/013第十三章编程子系统/` 下 001~005）、代码 x4（`code/001_XGSampleDemo/Source/XGSampleDemo/016_Subsystem/` 下 XGSimpleSubsystem.h/.cpp、XGWorkActor.h/.cpp）
- **材料自动识别**：本次未指定素材路径，AI 自行识别字幕文件夹 `013第十三章编程子系统/` 和代码文件夹 `016_Subsystem/`。代码编号 016 与章节编号 013 不一致（+3 偏移模式在第 9~13 章连续 5 章确认），通过类名 `UXGSimpleSubsystem`、`AXGWorkActor` 确认对应关系
- **代码核对**：逐帧比对代码实现与字幕讲解的一致性。确认知识点对应关系：
  - Subsystem 五类类型体系（Engine/Editor/GameInstance/World/LocalPlayer）
  - UGameInstanceSubsystem 声明模式（头文件包含、GENERATED_BODY、三个重写方法）
  - ShouldCreateSubsystem/Initialize/Deinitialize 生命周期控制
  - 三种获取方式（AActor.GetGameInstance→GetSubsystem、UObject WorldContext 链式、静态单例）
  - DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams + BlueprintAssignable 事件分发
  - FTickableGameObject 接口 + 三个必须重写的方法（Tick/IsTickable/GetStatId）
  - bFirstTick 模式解决初始化时机问题
- **差异记录**：无显著差异。字幕演示与代码实现完全一致
- **产出**：
  - `knowledge/ch13/01-子系统概念与类型体系.md`（新建）
  - `knowledge/ch13/02-创建GameInstanceSubsystem.md`（新建）
  - `knowledge/ch13/03-获取Subsystem的三种方式.md`（新建）
  - `knowledge/ch13/04-Subsystem与动态多播委托.md`（新建）
  - `knowledge/ch13/05-Subsystem的Tick实现（FTickableGameObject）.md`（新建）
  - `knowledge/第十三章-编程子系统.md`（重写）— 从占位页更新为完整索引页
- **经验固化**：追加 SKILL.md 16.26~16.28（"接口即能力"文档组织模式、编号偏移置信度提升、"安全←→便捷"谱系显式呈现）
- **状态**：完成 ✅

## [2026-04-28] update | 补充 Ingest 效率分析经验（16.29）
- **来源**：用户询问"效率提升是否真实"，触发对 Ingest 效率波动的自分析
- **变更文件**：`skills/xg-course-context/SKILL.md` — 新增 16.29（Ingest 效率的真实来源与可预测性）
- **核心内容**：效率提升不是 AI 能力变化，而是三个客观因素：①模式建立成本已被摊销 ②代码-字幕差异的隐性成本 ③字幕数量是阅读时间的主要驱动。附粗略估算模型
- **状态**：完成 ✅

## [2026-04-28] ingest | 第十四章 断言知识提取
- **来源**：字幕 x4（`subtitles/014第十四章断言/` 下 001~004）、代码 x2（`code/001_XGSampleDemo/Source/XGSampleDemo/017_Assert/` 下 XGAssertActor.h/.cpp）
- **材料识别**：字幕文件夹 `014第十四章断言/`，代码文件夹 `017_Assert/`（+3 偏移确认，连续第 6 章成立）
- **代码核对**：逐帧比对，字幕演示与代码实现完全一致，无差异
- **知识点覆盖**：
  - 三大断言类别：check（最暴力，停止执行）、verify（Shipping 保留表达式副作用）、ensure（失败不崩溃，仅记录首次）
  - check 系列变体：check/checkf/checkNoEntry/checkCode/checkSlow/CastChecked
  - verify 的 Shipping 保留行为与使用场景
  - ensure/ensureMsgf 的返回值和失败不崩溃特性
  - 核心陷阱：不要把业务逻辑放到断言参数中（贯穿性警告，提升到概述文档）
  - Dump 文件调试流程与多线程 Crash 定位
- **差异记录**：无显著差异
- **产出**：
  - `knowledge/ch14/01-断言概述与三种类型.md`（新建）
  - `knowledge/ch14/02-check系列宏详解.md`（新建）
  - `knowledge/ch14/03-verify与ensure宏详解.md`（新建）
  - `knowledge/ch14/04-Dump文件调试与多线程Crash分析.md`（新建）
  - `knowledge/第十四章-断言.md`（重写）— 从占位页更新为完整索引页
- **经验固化**：追加 SKILL.md 16.30~16.32（跨文档重复警告统一策略、章节标题溢出内容保留策略、"兜底方法"文档模式）
- **状态**：完成 ✅

## [2026-04-28] ingest | 第十五章 配置知识提取
- **来源**：字幕 x9（`subtitles/015第十五章配置/` 下 001~009）、代码 x6（`code/001_XGSampleDemo/Source/XGSampleDemo/018_Config/` 下 XGSampleSettings.h/.cpp、XGConfigActor.h/.cpp、XGINIActor.h/.cpp）
- **材料识别**：字幕文件夹 `015第十五章配置/`，代码文件夹 `018_Config/`（+3 偏移确认，连续第 7 章成立）
- **代码核对**：逐帧比对代码实现与字幕讲解的一致性。确认知识点对应关系：
  - UDeveloperSettings 三组件（UCLASS(Config=X, defaultconfig)、FName GetContainerName/GetCategoryName/GetSectionName 重写、GetMutableDefault 工厂）
  - C++ 写回流程（GetMutableDefault → 属性赋值 → Modify() → SaveConfig）
  - UPROPERTY(Config) + UCLASS(config = Game) 自动加载模式
  - GConfig 手动读写（GetInt/SetInt/Flush）+ 直接文件路径指定写入层
  - GetMutableDefault + SaveConfig 的 CDO 持久化模式
- **差异记录**：
  - 字幕 002 中教师类命名为"XGSimpleSettings"，实际代码文件为"XGSampleSettings"（纯命名不一致，不影响知识点）
  - INI 6 层覆盖层次为字幕讲解，代码中无对应 UFUNCTION 直接演示（标注为"字幕讲解，无代码演示"）
  - 密钥泄露安全防护为字幕讲解，代码中无对应实现（标注为"安全工程领域溢出内容"）
- **产出**：
  - `knowledge/ch15/01-DeveloperSettings概述与创建.md`（新建）
  - `knowledge/ch15/02-CPP读写DeveloperSettings.md`（新建）
  - `knowledge/ch15/03-密钥泄露与安全防护.md`（新建）
  - `knowledge/ch15/04-INI配置系统与层级关系.md`（新建）
  - `knowledge/ch15/05-GConfig手动读写INI.md`（新建）
  - `knowledge/ch15/06-类保存属性与扩展内容.md`（新建）
  - `knowledge/第十五章-配置.md`（重写）— 从占位页更新为完整索引页
- **经验固化**：追加 SKILL.md 16.33~16.36（两套配置 API 的文档拆分策略、命名不一致的素材组织记录、配置安全溢出内容处理确认、纯讲解无代码素材处理规范）
- **命名不一致记录**：字幕中类名"XGSimpleSettings"，代码中为"XGSampleSettings"，经确认指向同一知识点
- **本章关注点**：配置章节同时包含声明式（UDeveloperSettings）和过程式（GConfig）两套 API，以及跨域的安全工程内容，素材类型多样
- **状态**：完成 ✅

## [2026-04-28] ingest | 第十六章 智能指针知识提取
- **来源**：字幕 x7（`subtitles/016第十六章智能指针/` 下 001~007）、代码 x2（`code/001_XGSampleDemo/Source/XGSampleDemo/019_SmartPointer/` 下 XGSmartPtrActor.h/.cpp）
- **材料识别**：字幕文件夹 `016第十六章智能指针/`，代码文件夹 `019_SmartPointer/`（+3 偏移确认，连续第 8 章成立）
- **代码核对**：字幕与代码完全一致，7 个字幕依次对应代码中 7 个 UFUNCTION。无任何差异记录（本次 Ingest 以来第一次"完全一致"章节）
- **代码独有知识点**：通过检查头文件发现 `FSmartPtrStruct` 继承自 `TSharedFromThis<FSmartPtrStruct>`，字幕未专门讲解 TSharedFromThis/AsShared/SharedThis，作为独立知识点提取
- **产出**：
  - `knowledge/ch16/01-智能指针概述与类型体系.md`（新建）
  - `knowledge/ch16/02-TSharedPtr共享指针.md`（新建）
  - `knowledge/ch16/03-TSharedRef共享引用.md`（新建）
  - `knowledge/ch16/04-TWeakPtr弱指针与循环引用.md`（新建）
  - `knowledge/ch16/05-TUniquePtr唯一指针.md`（新建）
  - `knowledge/ch16/06-TSharedFromThis与AsShared-SharedThis.md`（新建）— 代码独有知识点，字幕未讲解
  - `knowledge/第十六章-智能指针.md`（重写）— 从占位页更新为完整索引页
- **经验固化**：追加 SKILL.md 16.37~16.38（"字幕-代码完全一致"章节的高效处理模式、代码独有知识点的主动发现机制）
- **本章关注点**：第一次遇到"完全一致"章节，出现"代码独有知识点"新类型素材
- **状态**：完成 ✅

## [2026-04-28] ingest | 第十九章 虚幻商城标准插件开发
- **来源**：字幕 x5（`subtitles/019第十九章虚幻商城标准插件开发/` 下 001~005）
- **代码核对**：本章为商城上架流程操作教学，无对应代码文件。已确认 `code/` 和 `docs/` 目录均无第19章相关内容
- **特色说明**：本章是课程中第一类"纯流程规则教学"章节，不含代码实现，知识点全部来源于字幕
- **产出**：
  - `knowledge/ch19/01-商城插件上架流程与账号准备.md`（新建）
  - `knowledge/ch19/02-商品详情页面配置.md`（新建）
  - `knowledge/ch19/03-商城指南文档关键规则.md`（新建）
  - `knowledge/ch19/04-直链生成与支付税务.md`（新建）
  - `knowledge/ch19/05-蓝图项目插件模块丢失修复.md`（新建）
  - `knowledge/第十九章-虚幻商城标准插件开发.md`（重写）— 从占位页更新为完整索引页
- **状态**：完成 ✅

## [2026-04-29] ingest | 第二十一章 LibWebP 的集成使用（生成）知识提取
- **来源**：字幕 x14（`subtitles/021第二十一章LibWebP的集成使用_生成/` 下 001~014）、代码 x18+（`code/001_XGSampleDemo/Plugins/XGSampleWebP/` 全插件 + `code/001_XGSampleDemo/Source/XGSampleDemo/023_LibWebP/` + `code/012_第三方库资源/libwebp/`）
- **代码核对**：逐帧比对代码实现与字幕讲解的一致性。确认插件四层架构（FXGSampleWebPLib → FXGSampleWebPCore → Subsystem → BPLibrary）、单张 WebP 编码（WebPEncodeRGBA）、多张动态 WebP 编码（WebPAnimEncoder）、截图代理机制（FScreenshotRequest + GameViewportClient）、状态机设计（None/Recording/Generating）、线程交互模型（GameThread→RenderThread→WorkerThread）与字幕描述一致
- **差异记录**：无显著差异。字幕演示与插件代码实现完全一致。Demo Actor（XGSampleWebpActor）为空白 Actor 仅用于场景测试
- **产出**：
  - `knowledge/ch21/01-WebP概述与RGBA像素基础.md`（新建）
  - `knowledge/ch21/02-插件四层架构设计.md`（新建）
  - `knowledge/ch21/03-第三方库插件搭建与模块组织.md`（新建）
  - `knowledge/ch21/04-libwebp静态库集成与版本验证.md`（新建）
  - `knowledge/ch21/05-单张WebP底层编码接口.md`（新建）
  - `knowledge/ch21/06-视口像素获取与截图回调.md`（新建）
  - `knowledge/ch21/07-多张动态WebP底层编码接口.md`（新建）
  - `knowledge/ch21/08-多张WebP生成Subsystem与蓝图接口.md`（新建）
  - `knowledge/ch21/09-单张与多张WebP线程交互模型.md`（新建）
  - `knowledge/ch21/10-测试调试与打包修复.md`（新建）
  - `knowledge/第二十一章-LibWebP的集成使用_生成.md`（新建）— 章节索引页
- **状态**：完成 ✅

## [2026-04-29] ingest | 第二十二章 LibWebP 的集成使用（展示）知识提取
- **来源**：字幕 x6（`subtitles/022第二十二章LibWebP的集成使用_展示/` 下 000~005）、代码同第二十一章插件（`code/001_XGSampleDemo/Plugins/XGSampleWebP/`）
- **代码核对**：逐帧比对代码实现与字幕讲解的一致性。确认底层解码接口（WebPDemuxer/LoadDynamicWebpPictureByRGBA）、UEC++ 层封装（LoadDynamicWebpPicture）、ShowMultiSubsystem 状态机（None/Loading/Showing）、Tick 驱动的 UpdateTextureRegions 帧切换机制与字幕描述一致
- **差异记录**：无显著差异。字幕演示与插件代码实现完全一致
- **产出**：
  - `knowledge/ch22/01-WebP底层解码接口.md`（新建）
  - `knowledge/ch22/02-UEC++解码封装与蓝图展示入口.md`（新建）
  - `knowledge/ch22/03-Tick驱动纹理更新机制.md`（新建）
  - `knowledge/ch22/04-测试与打包修复.md`（新建）
  - `knowledge/第二十二章-LibWebP的集成使用_展示.md`（新建）— 章节索引页
- **状态**：完成 ✅

## [2026-04-29] update | 固化 ch21~22 实操经验（16.40~16.42）
- **来源**：回顾第二十一~二十二章 Ingest 全过程，提炼可复用经验
- **变更文件**：`skills/xg-course-context/SKILL.md` — 新增 16.40~16.42 三条经验
- **新增经验**：
  - **16.40 共享代码库的两章 Ingest 策略**：两章共享同一插件代码时的读代码一次、知识拆分到两个章节目录的策略
  - **16.41 综合案例章的"知识汇总价值"与文档组织**：新增"综合案例章"作为章节类型分类，确定按架构层次组织（非字幕时间线）的原则
  - **16.42 插件代码的定位模式与编号偏移的失效**：插件型代码组织打破 subtitle→code +3 偏移规律，DEMO Actor 可能产生误导信号
- **状态**：完成 ✅

## [2026-04-29] ingest | 第二十三章 虚幻Slate独立程序知识提取
- **来源**：字幕 x17（`subtitles/023第二十三章虚幻Slate独立程序/` 下 000~016）、代码 x20+（`code/013_独立程序源码/XGBlankProgram/`、`code/013_独立程序源码/XGSlateSample/` 全模块 + `code/006_SlateViewerTemplate_5.0.3/` + `code/007_UEProgram1/` + `code/008_UEProgram2/`）
- **素材识别**：用户提供了 5 个目录路径，其中 `code/006` 为 5.0.3 版本 SlateViewer 打包模板参考，`code/007` 和 `code/008` 为打包产物参考，`code/013_独立程序源码` 为本章主源码
- **代码核对**：逐帧比对代码实现与字幕讲解的一致性。确认以下与字幕描述一致：
  - BlankProgram 创建流程（IMPLEMENT_APPLICATION、Log 类别、类名替换）
  - Slate 程序框架（Build.cs/Target.cs 模块依赖、WinMain 引擎初始化序列、主循环 while 结构、帧率控制）
  - MVC 三层架构（Slate层/Core层/F层）与 Core 单例 + TickObject 接口 + TWeakPtr 管理
  - Slate 控件声明（SLATE_BEGIN_ARGS/SLATE_END_ARGS/Construct）和 Tab 管理系统
  - FDesktopPlatformModule 文件对话框和 IFileManager 文件遍历
  - CountCode 分帧状态机（ECountCodeStatus 四阶段枚举 + Tick 驱动的逐帧处理）
  - 打包排除法（必需的最小依赖目录清单）
- **差异记录**：无显著差异。字幕演示与代码实现完全一致。代码中的 SXGSSPModifyName.h 仅定义了空壳声明（实际 UI 布局代码可能在 .cpp 中），SXGSSPCoundCodeBox 同理。XGSSPCountCode.h 中所有成员变量（状态枚举、智能指针、TArray 队列、时间统计）与字幕讲解一一对应
- **产出**：
  - `knowledge/ch23/01-独立程序概述与BlankProgram创建.md`（新建）
  - `knowledge/ch23/02-Slate独立程序框架搭建.md`（新建）
  - `knowledge/ch23/03-小程序架构与Tick管理单例.md`（新建）
  - `knowledge/ch23/04-Slate基础概述.md`（新建）
  - `knowledge/ch23/05-ModifyName的UI布局与文件操作.md`（新建）
  - `knowledge/ch23/06-CountCode分帧状态机设计.md`（新建）
  - `knowledge/ch23/07-文件夹深度遍历与文件筛选计数.md`（新建）
  - `knowledge/ch23/08-独立程序暴力打包.md`（新建）
  - `knowledge/第二十三章-虚幻Slate独立程序.md`（重写）— 从占位页更新为完整索引页
- **状态**：完成 ✅

## [2026-04-29] update | 固化 ch23 实操经验（16.43~16.45）
- **来源**：回顾第二十三章 Ingest 全过程，提炼可复用经验
- **变更文件**：`skills/xg-course-context/SKILL.md` — 新增 16.43~16.45 三条经验
- **新增经验**：
  - **16.43 用户提供的多代码路径的用途分级**：用户提供 5 个目录（主源码 + 模板参考 + 打包产物参考），建立了"先分类→标注角色→差异化处理"的三步法。与 16.42 互补——16.42 防范自动发现时的误导，本条防范用户主动提供时的误判
  - **16.44 Slate 头文件的"空壳声明"特征**：Slate 控件的 .h 仅含 SLATE_BEGIN_ARGS/SLATE_END_ARGS 宏和 Construct 声明，完整实现都在 .cpp。Ingest 时不能仅凭 .h 判断类是否"空壳"
  - **16.45 分帧模式与状态机章节的文档组织策略**：含"状态机枚举 + 分帧 Tick + switch-case"的章节，应采用"先架构后算法"两层拆分（状态机设计文档 + 各阶段实现文档），避免产出巨石文档
- **状态**：完成 ✅

## [2026-04-29] ingest | 第二十四章 商业化Json读写使用知识提取
- **来源**：字幕 x7（`subtitles/024第二十四章商业化Json的读写使用/` 下 001~007）、代码 x2（`code/001_XGSampleDemo/Source/XGSampleDemo/024_Json/XGSampleJson.h/.cpp`）+ JSON 示例数据 x5（`code/004_Json/` 下 Message.json / Character.json / BadMessage.json / NotVeryBadMessage.json / VeryBadMessage.json）
- **素材识别**：用户提供 3 个路径——`subtitles/024` 为字幕，`code/004_Json` 为 JSON 示例数据文件（只读参考），`code/001_XGSampleDemo/024_Json` 为主源码
- **代码核对**：逐帧比对代码实现与字幕讲解的一致性。确认以下与字幕描述一致：
  - NotGoodJson — FString::Printf 原始拼接方式及逗号转义陷阱
  - GoodJson — TJsonWriter 写入流创建（TCondensedJsonPrintPolicy）、WriteObjectStart/WriteValue/WriteArrayStart 完整嵌套、TJsonReader 读取流、FJsonSerializer::Deserialize 反序列化、TryGetField/TryGetNumberField/GetNumberField/GetStringField/GetObjectField/GetArrayField 三种读取方式
  - GoodJson2 — TempMessageInfo::ToString() / FromString() 封装模式
  - BadJson — FBadMessageInfo 结构体 + JSON 字符串嵌套（Info 字段为 String 而非 Object）+ 二次反序列化
  - VeryBadJson — FGuid 动态 Key 名 + FJsonObject::Values TMap 遍历
  - GoodSturctJson — FJsonObjectConverter::UStructToJsonObjectString / JsonObjectStringToUStruct + UPROPERTY 过滤（NotWrite 字段不被序列化）
  - GoodSturctJson2 — 复杂嵌套 USTRUCT（含 TArray<USTRUCT> 结构体数组 + FDateTime 时间序列化）
- **差异记录**：无显著差异。代码实现与字幕讲解完全一致。代码中的 TempMessageInfo 结构体未使用 USTRUCT() 宏（非反射版本的手动实现），FXGSampleMessageInfo 使用完整 USTRUCT() + UPROPERTY() 反射实现，两者在 .h 中并列共存——字幕也明确讲解了"两种方法"的区别。代码中 FXGSampleMessageInfo::NotWrite 字段无 UPROPERTY 标注，在 GoodSturctJson2 中不会被序列化（与字幕演示一致）
- **产出**：
  - `knowledge/ch24/01-JSON基础规范与三种写法概述.md`（新建）
  - `knowledge/ch24/02-TJsonWriter与TJsonReader底层读写.md`（新建）
  - `knowledge/ch24/03-商业化嵌套读写与糟糕设计模式.md`（新建）
  - `knowledge/ch24/04-FJsonObjectConverter反射序列化.md`（新建）
  - `knowledge/第二十四章-商业化Json读写使用.md`（重写）— 从占位页更新为完整索引页
- **状态**：完成 ✅

## [2026-04-29] update | 固化 ch24 实操经验（16.46~16.47）
- **来源**：回顾第二十四章 Ingest 全过程，提炼可复用经验
- **变更文件**：`skills/xg-course-context/SKILL.md` — 新增 16.46~16.47 两条经验
- **新增经验**：
  - **16.46 JSON 三种写法的"递进式对比"文档策略**：当章节同时展示"错误做法→正确做法→最高级做法"的递进结构时，采用三列对比表呈现而非时间线叙述。这与 16.17（错误→演示→正确 三层结构）互补——16.17 适用于单个知识点的对错辨析，16.46 适用于一个子系统下多个平行方案的选择决策
  - **16.47 "非反射版本"与"反射版本"并列代码的核对注意事项**：第24章代码中 TempMessageInfo（非 USTRUCT 手动实现）与 FXGSampleMessageInfo（USTRUCT 反射实现）并列存在，Ingest 核对时不应误判为重复或冗余——它们是同一功能的两种实现范式，字幕也分别讲解了两种方式的适用场景
- **状态**：完成 ✅

## [2026-04-29] ingest | 第二十五章 HTTP基础——获取公网时间知识提取
- **来源**：字幕 x5（`subtitles/025第二十五章HTTP基础_获取公网时间/` 下 001~005）、代码 x2（`code/001_XGSampleDemo/Source/XGSampleDemo/025_HttpTime/XGSampleHttpTime.h/.cpp`）
- **素材识别**：用户提供字幕和代码两个目录路径。字幕 5 个文件覆盖 HTTP 概述→异步节点框架→执行流程→HTTP 请求链路→响应解析全流程。代码独立目录 `025_HttpTime/`，类名 `UXGSampleHttpTimeAsyncAction` 与章节主题一致，编号与章节编号完全对应（无偏移，与第 9~16 章的 +3 偏移模式不同）
- **代码核对**：逐帧比对代码实现与字幕讲解的一致性。确认以下与字幕描述一致：
  - EXGSampleNetTimeType 枚举（Local/TaoBao/XGServer 三值）、FXGSampleNetTimeRespInfo/FXGSampleNetTimeRespMessage/FXGSampleNetTimeRespDataInfo 三层 USTRUCT 结构、DECLARE_DYNAMIC_MULTICAST_DELEGATE_FourParams + 三引脚设计（Then/OnSuccess/OnFail）
  - UBlueprintAsyncActionBase 继承 + HideThen 元数据 + BlueprintInternalUseOnly 工厂函数模式 + NewObject + RegisterWithGameInstance
  - Activate() → AsyncTask(next-frame) → Activate_Internal() 错帧执行模式
  - SendHttp 配置序列（FHttpModule::Get().CreateRequest → SetURL → SetVerb → SetHeader → SetContentAsString → ProcessRequest）
  - BindUObject 委托重载传递 FGuid AsyncID + OnHttpRespReceived 三层验证（bSucceeded + GetStatus + GetResponseCode == 200）
  - FJsonObjectConverter::JsonObjectStringToUStruct 反射解析 + FCString::Atoi64 时间戳转换 + FDateTime::FromUnixTimestamp 时区偏移
  - CallOnSuccess/CallOnFail 的 AsyncTask(GameThread) 线程切换 + 值拷贝快照模式 + RealeaseResources 清理
- **差异记录**：无显著差异。字幕演示与代码实现完全一致。代码中额外演示了 Header 方式（`SetHeader("XGGuid", ...)` + `GetHeader("XGGuid")`）和委托重载参数传递两种请求-响应关联方式，字幕同时讲解了两种方法的适用场景
- **代码专题发现**：本章代码属于"异步蓝图节点"的参考实现模板，代码量 237 行，包含完整的生命周期（构造→Activate→错帧→实际工作→线程切换→广播→清理），可作为后续所有异步节点实现的参考范本
- **产出**：
  - `knowledge/ch25/http-basics.md`（新建）— HTTP 基础概念与 UE Http 模块入门
  - `knowledge/ch25/async-action-framework.md`（新建）— 异步蓝图节点框架与生命周期管理
  - `knowledge/ch25/execution-flow.md`（新建）— Activate 执行流与回调线程切换
  - `knowledge/ch25/http-request-chain.md`（新建）— 完整 HTTP 请求链路与 JSON 响应解析
  - `knowledge/第二十五章-HTTP基础-获取公网时间.md`（新建）— 章节索引页
- **状态**：完成 ✅

## [2026-04-29] update | 回撤 ch25 经验（16.48~16.50）——误将课程知识点记为过程经验
- **来源**：用户审查指出这三条属于课程具体知识点而非 Ingest 过程经验
- **操作**：从 `skills/xg-course-context/SKILL.md` 中移除 16.48~16.50
- **归属**：相关内容已在 `knowledge/ch25/` 的 4 篇细粒度文档中完整覆盖
  - 错帧执行模式 → `ch25/execution-flow.md`
  - BindUObject vs Header 追踪 → `ch25/http-request-chain.md`
  - 编号偏移模式 → 已有 16.14 和 16.27 覆盖方法论，无需额外固化
- **经验教训**：SKILL.md 第十六章只存放"提升蒸馏效率"的过程级经验（如何判断合并、如何定位代码、如何处理差异等），不存放课程具体的技术知识点。知识点应只存在于 `knowledge/` 文档中
- **状态**：完成 ✅

## [2026-04-29] ingest | 第二十六章 HTTPServer_自定义登录注册服务器
- **来源**：
  - 字幕：`subtitles/026第二十六章HTTPServer_自定义登录注册服务器/`（21 个 srt 文件）
  - 服务端源码：`code/013_独立程序源码/XGSampleServer/`（入口 + Config/ + ServerObject/ + Type/ + Util/ + Log/ + Build.cs + Target.cs）
  - 客户端插件源码：`code/001_XGSampleDemo/Plugins/XGSampleClient/`（模块声明 + BPLibrary + Subsystem + Settings + Type + Util + Log + Build.cs）
  - 对比对照：`code/013_独立程序源码/XGSlateSample/`、`code/013_独立程序源码/XGBlankProgram/`
  - 打包产物：`code/008_UEProgram2/Engine/Binaries/Win64/XGSampleServer-Win64-Debug.exe`、`code/007_UEProgram1/Engine/Binaries/Win64/XGSlateSample-Win64-Debug.exe`
- **产出**：
  - `knowledge/ch26/01-HTTPServer独立程序概述与架构总览.md`（新建）— 架构总览与 Ch23 对比
  - `knowledge/ch26/02-服务端框架搭建与独立程序入口.md`（新建）— 入口与主循环
  - `knowledge/ch26/03-自定义INI配置系统.md`（新建）— 配置系统
  - `knowledge/ch26/04-HTTP端口绑定与请求处理管线.md`（新建）— 请求管线
  - `knowledge/ch26/05-HTTP数据封装与JSON序列化.md`（新建）— 数据封装
  - `knowledge/ch26/06-MD5令牌验证与安全机制.md`（新建）— 令牌机制
  - `knowledge/ch26/07-服务端业务逻辑实现.md`（新建）— 业务逻辑
  - `knowledge/ch26/08-客户端插件架构与蓝图接口.md`（新建）— 客户端架构
  - `knowledge/ch26/09-独立程序手动打包与部署.md`（新建）— 打包部署
  - `knowledge/第二十六章-HTTPServer_自定义登录注册服务器.md`（更新）— 主索引页
- **状态**：完成 ✅

## [2026-04-29] update | 固化 16.48——客户端-服务端双代码库的"数据流优先"策略
- **来源**：第二十六章 HTTPServer Ingest 过程经验
- **操作**：在 `xg-course-context/SKILL.md` 第十六章新增 16.48
- **状态**：完成 ✅

## [2026-04-29] ingest | 第二十七章 HTTP上传文件_摄像头活体检测
- **来源**：
  - 字幕：`subtitles/027第二十七章HTTP上传文件_摄像头活体检测/`（15 个 srt 文件）
  - XGSamplePicture 插件源码：`code/001_XGSampleDemo/Plugins/XGSamplePicture/`（uplugin + Build.cs + 模块声明 + AsyncAction 共 6 个文件）
  - XGSampleXFLink SilentBiopsy 源码：`code/001_XGSampleDemo/Plugins/XGSampleLink/Source/XGSampleXFLink/`（SilentBiopsy 请求/响应 Type + AsyncAction + Log + 模块声明共 8 个文件）
  - 加密基库源码：`code/001_XGSampleDemo/Plugins/XGSampleLink/Source/ThirdParty/XGSampleXFLinkLibrary/`（Build.cs + XGSampleXFLinkBase.h/.cpp 共 3 个文件）
  - **排除**（属于 Ch29/Ch30）：XGSampleXFLinkBPLibrary、STT/TTS Type、STT 与 AudioCapture Subsystem、ConsumeVoiceRunnable
- **产出**：
  - `knowledge/ch27/01-知识概览.md`（新建）— 文件索引、Pipeline 总览、三种 HTTP 上传方式对比
  - `knowledge/ch27/02-异步蓝图节点框架.md`（新建）— UBlueprintAsyncActionBase 模式详解
  - `knowledge/ch27/03-RenderTarget2D转PNG.md`（新建）— ReadPixels + Alpha 预乘 + 异步 PNG 压缩
  - `knowledge/ch27/04-摄像头视频流整合.md`（新建）— Media Framework 设备枚举与轨道选择
  - `knowledge/ch27/05-HMAC-SHA256鉴权与URL签名.md`（新建）— OpenSSL HMAC-SHA256 + 讯飞 URL 签名管线
  - `knowledge/ch27/06-请求体构造与HTTP发送.md`（新建）— JSON 三层结构 + Base64 编码 + 4MB 限制
  - `knowledge/ch27/07-响应解析.md`（新建）— RawMessage/TextMessage 双层解析
  - `knowledge/ch27/08-UObject生命周期管理.md`（新建）— GC 生命周期陷阱 + Super::Activate()
  - `knowledge/ch27/09-插件架构与模块依赖.md`（新建）— 双插件架构 + 加密模块分离 + 模块间依赖链
  - `knowledge/第二十七章-HTTP上传文件_摄像头活体检测.md`（更新）— 主索引页
- **状态**：完成 ✅

## [2026-04-29] update | 固化 16.49~16.50——跨插件数据流追踪与同插件多章节边界标注
- **来源**：第二十七章 HTTP上传文件 Ingest 过程经验
- **操作**：在 `xg-course-context/SKILL.md` 第十六章新增 16.49（跨插件数据流追踪）和 16.50（同插件多章节代码边界标注）
- **状态**：完成 ✅

## [2026-04-29] ingest | 第二十八章 HTTP流式传输——大模型通讯（百度文心一言）
- **来源**：
  - 字幕：`subtitles/028第二十八章HTTP流式传输_大模型通讯/`（10 个 srt 文件）
  - XGSampleBDLink 模块源码：`code/001_XGSampleDemo/Plugins/XGSampleLink/Source/XGSampleBDLink/`（Build.cs + Log + ReqType/ReqType.cpp + RespType/RespType.cpp + AsyncAction + 模块声明共 11 个文件）
  - 加密基库（百度相关函数）：`code/001_XGSampleDemo/Plugins/XGSampleLink/Source/ThirdParty/XGSampleXFLinkLibrary/`（BDHMACSHA256、GenerateBDHeaders、GenerateBDAuthorizationToken、AnalyseBDURL）
- **代码核对**：逐帧比对代码实现与字幕讲解的一致性。确认 AKSK 签名管线（BCE v1、bce-auth-v1 前缀、Hex 输出 HMAC-SHA256）、FBDReqUtil 条件 JSON 工厂（-1/"None"哨兵值 + 可选字段跳过）、非流式响应解析（error_code 顶层检测 + FJsonObjectConverter）、流式处理（OnStreamReady + TArray<uint8> 累积 + \n\n 分隔符 + 递归 ParseStreamData + OnUpdate 引脚）与字幕描述一致
- **差异记录**：
  - 字幕中 BDHMACSHA256 最初未加 `static` 导致编译错误，实际代码已正确添加（字幕现场修复确认）
  - 字幕中 OnHttpRespReceived 最初忘记调用 OnSuccess，实际代码已正确调用（字幕现场修复确认）
  - 字幕中 messages 数组的 role 字段曾误写为 "row"，实际代码已修正（字幕现场修复确认）
- **产出**：
  - `knowledge/ch28/01-知识概览.md`（新建）— 文件索引、Pipeline 总览、与第二十七章的对比
  - `knowledge/ch28/02-异步蓝图节点框架.md`（新建）— BDChat 节点四引脚设计（Then/OnSuccess/OnUpdate/OnFail）
  - `knowledge/ch28/03-百度AKSK鉴权签名.md`（新建）— BCE v1 签名、HMAC-SHA256 十六进制输出、Header 鉴权
  - `knowledge/ch28/04-请求体构造与JSON工厂.md`（新建）— FBDReqUtil 条件写入、messages 数组、manual JSON 构建
  - `knowledge/ch28/05-非流式响应解析.md`（新建）— HTTP 状态检查、error_code 判断、FJsonObjectConverter 反序列化
  - `knowledge/ch28/06-HTTP流式数据处理.md`（新建）— OnStreamReady 绑定、跨线程处理、\n\n 分隔符解析
  - `knowledge/ch28/07-响应类型体系.md`（新建）— 全部响应类型 USTRUCT 定义
  - `knowledge/ch28/08-蓝图节点生命周期与跨线程安全.md`（新建）— RegisterWithGameInstance、跨线程委托广播、资源释放
  - `knowledge/第二十八章-HTTP流式传输_大模型通讯.md`（更新）— 从占位页更新为完整索引页
- **对比章节**：第二十七章讯飞 vs 第二十八章百度——鉴权方式（URL Base64 vs Header Hex）、请求体结构（三层嵌套 vs 扁平 JSON）、错误位置（嵌套 vs 顶层）、流式处理（无/WebSocket 有 vs OnStreamReady 新增 OnUpdate 引脚）
- **状态**：完成 ✅

## [2026-04-29] update | 固化
- **操作**：在 `xg-course-context/SKILL.md` 第十六章新增 16.51（"变体章节"的模板复用与差异化提取策略）
- **状态**：完成 ✅

## [2026-04-29] ingest | 第二十九章 WebSocket 语音识别（讯飞 STT）
- **来源**：
  - 字幕：`subtitles/029第二十九章WebSocket_语音识别/`（15 个 srt 文件，001~015）
  - XGSampleXFLink 模块源码：`code/001_XGSampleDemo/Plugins/XGSampleLink/Source/XGSampleXFLink/`（STT 子系统 + AudioCapture 子系统 + ConsumeVoiceRunnable + BPLibrary + Type STT 全套共约 15 个文件）
  - WebSocket 协议模板：`code/009_WebSocketJson/`（InitJson/MessJson/TickJson/ClientReqQuitJson 共 4 个文件）
  - 第三方加密基库：`code/001_XGSampleDemo/Plugins/XGSampleLink/Source/ThirdParty/XGSampleXFLinkLibrary/`（XGSampleXFLinkBase.h/.cpp — AssembleAuthUrl 及 HMAC 工具）
- **代码核对**：逐帧比对代码实现与字幕讲解的一致性。确认 STT 子系统状态机（Ready/Init/WaitToServerClose）、WebSocket 五回调（OnConnected/OnConnectionError/OnClosed/OnMessage/OnMessageSent）、音频采集（UAudioCaptureFunctionLibrary::CreateAudioCapture）、重采样（48K 步进降采样 + 44.1K LinearResample 线性插值）、数据格式转换（float→int16→uint8 LE）、消费线程（FRunnable 10ms 轮询）、音量 RMS 计算与字幕描述一致
- **差异记录**：
  - STT 使用 UGameInstanceSubsystem 而非 UBlueprintAsyncActionBase（其他 HTTP/WS 章节使用），原因是需要常驻连接和后台线程
  - 鉴权方式为 HMAC-SHA1 URL 参数，与 Ch27/Ch30 的 HMAC-SHA256 URL 签名不同
  - 使用 Socket->Send(binary) 发送二进制 PCM 数据，而非文本 JSON
- **产出**：
  - `knowledge/ch29/01-知识概览.md`（新建）— 文件索引、Pipeline 总览、与第二十七章的对比
  - `knowledge/ch29/02-STT子系统与状态机.md`（新建）— UXGSampleSTTSubsystem、状态机、WebSocket 生命周期
  - `knowledge/ch29/03-音频采集子系统.md`（新建）— UXGSampleAudioCaptureSubsystem、UAudioCapture、OnAudioGenerate
  - `knowledge/ch29/04-音频重采样与格式转换.md`（新建）— 48K/44.1K→16K 降采样、LinearResample、float→int16→uint8
  - `knowledge/ch29/05-音频消费线程.md`（新建）— FXGSampleConsumeVoiceRunnable、生产者-消费者模式
  - `knowledge/ch29/06-讯飞STT认证与WebSocket通信.md`（新建）— HMAC-SHA1 鉴权、009_WebSocketJson 协议
  - `knowledge/ch29/07-STT响应解析.md`（新建）— started/result/error 三种响应解析
  - `knowledge/ch29/08-麦克风音量计算.md`（新建）— RMS 算法、跨线程音量传递
  - `knowledge/ch29/09-蓝图接口.md`（新建）— BPLibrary 五个静态函数
  - `knowledge/第二十九章-WebSocket_语音识别.md`（更新）— 从占位页更新为完整索引页
- **状态**：完成 ✅

## [2026-04-29] ingest | 第三十章 WebSocket 语音合成（讯飞 TTS）
- **来源**：
  - 字幕：`subtitles/030第三十章WebSocket_语音合成/`（8 个 srt 文件，001~008）
  - XGSampleXFLink 模块源码：TTS 异步节点 + TTS ReqType/RespType + 第三方加密基库
  - WebSocket 协议模板同第二十九章
- **代码核对**：确认 TTS 异步节点（UBlueprintAsyncActionBase 工厂 + 四引脚）、AssembleAuthUrl 鉴权（HMAC-SHA256）、JSON 请求（三层嵌套 USTRUCT → FJsonObjectConverter::UStructToJsonObjectString）、响应解析（code 检查 + Base64 解码 + 累积）、USoundWave 创建（FSampleBuffer 方式）、WAV 文件生成（RIFF/fmt/data 三块结构 + 异步 FFileHelper::SaveArrayToFile）与字幕描述一致
- **差异记录**：
  - TTS 使用 UBlueprintAsyncActionBase 模式（与 Ch27/Ch28 相同），而非 Ch29 的 UGameInstanceSubsystem
  - 响应中 data.audio 字段包含的是 Base64 编码的音频数据，需解码后创建 USoundWave
  - USoundWave 创建探索了三种方式：RawPCMData（deprecated）、RawData（UE5 推荐）、最终使用 FSampleBuffer
- **产出**：
  - `knowledge/ch30/01-知识概览.md`（新建）— 文件索引、Pipeline 总览、与第二十九章的对比
  - `knowledge/ch30/02-TTS异步节点架构.md`（新建）— 工厂方法、四输出引脚、生命周期
  - `knowledge/ch30/03-讯飞TTS认证与WebSocket通信.md`（新建）— HMAC-SHA256 鉴权、AssembleAuthUrl
  - `knowledge/ch30/04-请求参数体系.md`（新建）— 三层嵌套 USTRUCT 全部参数定义
  - `knowledge/ch30/05-响应解析与音频数据提取.md`（新建）— JSON 反序列化、Base64 解码
  - `knowledge/ch30/06-USoundWave创建三种方式.md`（新建）— RawPCMData/RawData/FSampleBuffer 对比
  - `knowledge/ch30/07-WAV文件生成与存储.md`（新建）— WAV 三块结构、ConvertPCMToWave、异步保存
  - `knowledge/ch30/08-文本编码与Base64.md`（新建）— FString→UTF-8→Base64 编码链路
  - `knowledge/第三十章-WebSocket_语音合成.md`（更新）— 从占位页更新为完整索引页
- **状态**：完成 ✅

## [2026-04-29] update | 固化 16.52——功能对称但架构不同的同供应商章节处理策略
- **来源**：第二十九~三十章 Ingest 过程经验（ch29 STT + ch30 TTS，同属 XGSampleXFLink 插件，同调用讯飞接口，但架构完全不同）
- **操作**：在 `xg-course-context/SKILL.md` 第十六章新增 16.52
- **核心内容**：两章共享同一 XGSampleXFLink 插件但使用不同的节点类型（UGameInstanceSubsystem vs UBlueprintAsyncActionBase）、不同的鉴权方式（HMAC-SHA1 URL 参数 vs HMAC-SHA256 URL 签名）、不同的数据传输方式（二进制 PCM 流 vs JSON+Base64）——同一供应商的不同服务接口不共享架构模式，应分别处理
- **状态**：完成 ✅

## [2026-04-29] ingest | 第三十一章 WebSocketServer——MMO 分布式服务器通信
- **来源**：`subtitles/031第三十一章WebSocketSever_MMO分布式服务器通信/`（15 个字幕文件，含 009）
- **来源**：`code/001_XGSampleDemo/Plugins/XGSampleWSM/`（13 个源文件）
- **产出**：
  - `knowledge/第三十一章-WebSocketSever_MMO分布式服务器通信.md`（章节入口）
  - `knowledge/ch31/01-知识概览.md`（Pipeline + 架构图 + 文件层级）
  - `knowledge/ch31/02-MMOARPG分布式服务器架构与通讯拓扑.md`（服务器层次 + 容器拓扑）
  - `knowledge/ch31/03-消息协议与编解码.md`（JSON 消息格式 + ActionType + Base64）
  - `knowledge/ch31/04-插件架构与子系统设计.md`（Build.cs + Subsystem + 三模块计划）
  - `knowledge/ch31/05-服务器端实现.md`（IWebSocketServer + ServerConnection + Tick）
  - `knowledge/ch31/06-客户端实现与全流程通讯.md`（IWebSocket + 6 回调 + 数据重组 + 状态机）
  - `knowledge/ch31/07-蓝图测试与多实例调试.md`（蓝图绑定 + Postman + 多实例）
- **状态**：完成 ✅

## [2026-04-29] update | 固化 16.53——自建服务端插件 Ingest 策略
- **来源**：第三十一章 Ingest 过程自分析
- **操作**：在 `xg-course-context/SKILL.md` 第十六章新增 16.53
- **核心内容**：当课程内容从"连接第三方服务"切换到"自建服务端"时，文档组织应从"线性调用链"切换到"消息协议 → 双端实现 → 状态机"的分层架构策略
- **状态**：完成 ✅

## [2026-04-29] update | 修正 009 文件遗漏与文档错误
- **来源**：用户指正 + 重新读取 009 字幕
- **操作**：
  - 字幕数从 14 修正为 15（含 009）
  - 章节入口、课程纲要同步修正字幕数
  - `ch31/03-消息协议.md` 修正 ActionType 枚举名（ClientTickToServer → ClientCallTick）和 Code 默认值（0 → -1）
  - `ch31/04-插件架构.md` 修正服务端状态枚举名（PendingInit/TickHeartbeat/Close → WaitClientToInit/Tick/PrepareToQuit/Quit/OutOfTime）
  - `ch31/05-服务器端实现.md` 重写：状态机、消息分发 Switch、Code 安全校验、连接可用性概念、迁移清理
  - `ch31/06-客户端实现.md` 修正心跳 ActionType
  - `ch31/07-蓝图测试.md` 修正 ActionType 数值表
  - `ch31/01-知识概览.md` 修正状态枚举名 + 拆分客户端/服务端枚举
- **根因**：文件名 `009_完成服务端初始化,心跳,退出的代码_字幕.srt` 含中文逗号，被 LS/Glob 工具遗漏
- **状态**：完成 ✅

## [2026-04-29] update | 固化 16.54——字幕文件名中文标点搜索遗漏
- **来源**：009 文件遗漏事件的复盘
- **操作**：在 `xg-course-context/SKILL.md` 第十六章新增 16.54
- **核心内容**：非 ASCII 字符（中文逗号）在文件名中导致 LS/Glob 工具遗漏检测，需使用 ls 批处理 + 编号序列扫描 + UTF-8 感知工具保障素材发现的可靠性。与 xg-file-change-reliability 形成文件可靠性的两个保障维度
- **状态**：完成 ✅

## [2026-04-29] ingest | 第三十二章 TCP 实战——自动发送邮箱验证码
- **来源**：`subtitles/032第三十二章TCP实战_自动发送邮箱验证码/`（10 个 .srt）+ `code/001_XGSampleDemo/Plugins/XGSampleEMail/`（17 个插件文件）
- **产出**：
  - `knowledge/第三十二章-TCP实战_自动发送邮箱验证码.md`（章节入口，已填充）
  - `knowledge/ch32/01-插件架构与四类核心设计.md`
  - `knowledge/ch32/02-SMTP协议状态机实现.md`
  - `knowledge/ch32/03-FRunnable多线程TCP通信.md`
- **核心内容**：案例 11——基于 SMTP 协议的自动邮箱验证码发送插件。插件架构（AsyncAction/Runnable/Subsystem/BPLibrary 四类模式）、SMTP 状态机（~14 个状态枚举阶段推进）、FRunnable 多线程 TCP 通信（Socket 创建/连接/收发/关闭完整生命周期）
- **关键设计决策**：AsyncAction 继承 TSharedFromThis（非 UBlueprintAsyncActionBase）、Build.cs 不含 Engine 模块、C++ 单例 Subsystem（非 UGameInstanceSubsystem）、内部类无导出宏
- **关键 Bug**：FRunnable 先 Reset 后 Stop 导致野指针——正确顺序为 Stop→WaitForCompletion→delete Thread→Reset
- **状态**：完成 ✅
- **经验固化**：本次无新增固化经验（常规 Ingest 流程，未发现新的工具问题或流程优化空间）

## [2026-04-29] ingest | 第三十三章 虚幻基础案例模板
- **来源**：`subtitles/033第三十三章虚幻基础案例模板/`（12 个 .srt）
- **说明**：本章无关联代码（解读虚幻引擎官方模板，无粘贴代码到工程），按用户要求精简处理
- **产出**：
  - `knowledge/第三十三章-虚幻基础案例模板.md`（章节入口，已从占位符填充）
  - `knowledge/ch33/01-FP第一人称模板详解.md`
  - `knowledge/ch33/02-TP第三人称模板概述.md`
  - `knowledge/ch33/03-TD俯视角模板概述.md`
- **核心内容**：三种虚幻官方模板（FP/TP/TD）的蓝图 + C++ 解读。FP 最为详细（手写完整六个 C++ 类：GameMode/PlayerController/Character/PickupComponent/WeaponComponent/Projectile），重点演示了 Enhanced Input 系统（Input Action + IMC + LocalPlayerSubsystem + EnhancedInputComponent 绑定）。TP 以第三人称摄像机与动画蓝图为主，TD 以鼠标点击移动（LineTrace + AI 寻路 + Niagara 特效）为主
- **状态**：完成 ✅
- **经验固化**：本次无新增固化经验（纯模板解读章节，无代码核对环节，流程无特殊问题）

## [2026-04-29] ingest | 第三十五章 多人网络游戏基础
- **来源**：
  - `subtitles/035第三十五章多人网络游戏基础/`（22 个 .srt）
  - `code/016_XGNetDemo/`（7 个 .h/.cpp 文件）
  - `code/017_XGNetDemoForDS/`（5 个 Target.cs + 2 个 .h/.cpp）
  - `code/001_XGSampleDemo/026_Net/`（7 个 .h/.cpp）
  - `code/001_XGSampleDemo/027_RPC/`（2 个 .h/.cpp）
  - `docs/虚幻网络游戏.docx`（5 节网络基础文档）
  - 上下文关联：第三十一章 XGSampleWSM 插件、第三十四章 DSM 架构
- **说明**：本章为 UE 原生网络复制体系的核心章节，使用第三十一章的 XGSampleWSM 插件，构建了 016_XGNetDemo（服务器+客户端）和 017_XGNetDemoForDS（专用服务器打包）两个工程
- **产出**：
  - `knowledge/第三十五章-多人网络游戏基础.md`（章节入口，已从占位符填充）
  - `knowledge/ch35/01-章节概览与网络架构基础.md`
  - `knowledge/ch35/02-Actor网络角色体系.md`
  - `knowledge/ch35/03-属性同步与OnRep通知.md`
  - `knowledge/ch35/04-条件复制与所有权控制.md`
  - `knowledge/ch35/05-结构体部分复制与指针复制.md`
  - `knowledge/ch35/06-RPC基础与三种调用模式.md`
  - `knowledge/ch35/07-RPC验证与安全.md`
  - `knowledge/ch35/08-Actor网络休眠与复制流程.md`
  - `knowledge/ch35/09-碰撞事件绑定与DS部署实践.md`
- **核心内容**：UE 原生网络复制完整体系——Actor 角色体系（ENetRole/LocalRole/RemoteRole/所有权/相关性/优先级）；属性同步（DOREPLIFETIME/OnRep_Notify 三种签名/REPNOTIFY 策略）；条件复制（COND_OwnerOnly/DOREPLIFETIME_ACTIVE_OVERRIDE/PreReplication）；结构体部分复制与 FNetworkGUID 指针映射；RPC 三种模式（Server/Client/Multicast）及其验证机制（WithValidation/断线策略） ；Actor 休眠与复制流程（Dormancy/脏标记/RPC 排序/连接通道）；DS 部署实践（ServerGameMode/Target.cs/DS 打包）
- **状态**：完成 ✅
- **经验固化**：追加 SKILL.md 16.55~16.56（"docs/作为理论前置知识框架"定位策略、"同域渐进抽象链"跨章节对比策略）

## [2026-04-29] ingest | 第三十六章 虚幻高级网络游戏技能系统GAS案例（修复与验证）
- **说明**：第三十六章 16 篇细粒度文档在上次 session 中已创建，但因 session 中断遗留了以下问题：15-动画通知系统.md 文件截断、02-04 三篇文档与代码事实存在偏差、章节索引页为占位符。本次 session 完成修复、验证和补充。
- **来源**：
  - `subtitles/036第三十六虚幻高级网络游戏技能系统GAS案例/`（60 个 .srt）
  - `code/017_XGRPG/XGRPG/Source/XGRPG/`（全部源码）
  - `docs/`（无独立讲义文件）
- **修复项**：
  1. **15-动画通知系统.md**：重写被截断的后半部分（添加 NotifyEnd 逻辑、文件索引表、设计原则小结）
  2. **02-GAS核心框架.md**：GameplayTag 声明从"设计意图列表"修正为实际代码声明（InputTag_LightAttack→Melee/AirAttack/Key_1~4；移除不存在的 GameplayCue；补充 SetByCaller 和 Status 分类）
  3. **03-AttributeSet与属性系统.md**：属性表从 HealthReg/ManaReg 修正为 Level/MaxExp（共 12 属性）；基类描述从"含 ATTRIBUTE_ACCESSORS"修正为"仅 GetWorld + GetASC"；PostGameplayEffectExecute 代码示例从简化版修正为与实际一致的六参数委托广播和 Damage 归零逻辑
  4. **04-伤害计算与GEEC.md**：基础 GEEC 从"Attack - Defense 减法规避公式"修正为"Damage 直传递归"；Air GEEC 从"Attack/(Attack+Defense) 比例公式"修正为"BaseDamage + Attack - Defense + 5 线性公式"
  5. **章节索引页**：从占位符填充为含 16 篇文档分类表格的完整索引页
  6. **课程纲要.md**：第三十六章描述从"GE/GC/GA"修正为具体系统列表（移除不存在的 GC）
- **状态**：完成 ✅
- **经验固化**：追加 SKILL.md 16.57~16.59（"靶向验证"Header 优先原则、批量写入后截断文件检测、GAS 精度漏洞模式）

## [2026-04-29] ingest | 阶段二：横向模式提炼
- **来源**：`knowledge/` 下全部 36 章知识文档 + 各章对应代码目录
- **产出**：
  - [横向-反射宏体系总览.md](横向-反射宏体系总览.md)（6 大反射宏对比表）
  - [横向-容器选型决策.md](横向-容器选型决策.md)（TArray/TMap/TSet 决策树）
  - [横向-依赖注入与配置模式.md](横向-依赖注入与配置模式.md)（Subsystem/DeveloperSettings/CDO 对比）
  - [横向-异步执行模式.md](横向-异步执行模式.md)（5 种异步模式 + TaskGraph 陷阱分析，578 行）
  - [横向-网络通信演进.md](横向-网络通信演进.md)（8 章通信章节全景演进链路）
  - [横向-实战案例多项目策略.md](横向-实战案例多项目策略.md)（12 个案例组织策略）
- **说明**：6 篇横向专题文档覆盖反射、容器、异步、网络、配置、项目组织六大主题，每篇跨 2~8 章综合提炼。文档命名规范定为"横向-名称.md"。
- **状态**：完成 ✅
- **经验固化**：追加 SKILL.md 16.60（横向专题文档的跨章节合成方法论）

## [2026-04-29] lint | 课程全局健康检查
- **来源**：`knowledge/` 下全部 286 个 .md 文件 + `dist/` 下 16 个文件
- **检查项**：文件规模 / 命名变体 / 代码引用失效 / 孤立页面 / 交叉引用完整性 / 概念遗漏 / 矛盾声明
- **产出**：本报告
- **状态**：完成 ✅

### 一、文件规模统计

| 区域 | 文件数 | 说明 |
|------|--------|------|
| knowledge/ 元数据 | 2 | 课程纲要.md + log.md |
| knowledge/ 横向文档 | 6 | 横向-*.md 专题文档 |
| knowledge/ 章节入口 | 37 | 第X章-*.md（含 3 个骨架页） |
| knowledge/ 细粒度文档 | 238 | ch{N}/ 下子文档（34 个目录） |
| knowledge/ 合计 | 286 | 全部 .md 文件 |
| dist/ (学员交付) | 16 | SKILL.md + 15 references |
| **总计** | **302** | |

### 二、命名变体问题 [严重度：中]

发现 3 对命名变体文件，每对包含一个**完整入口页**和一个**骨架页**（10 行占位符）：

| 完整版（有内容） | 骨架版（10行占位符） |
|----------------|-------------------|
| `第二十一章-LibWebP的集成使用_生成.md`（3,179 bytes） | `第二十一章-LibWebP集成使用_生成.md`（255 bytes） |
| `第二十二章-LibWebP的集成使用_展示.md`（2,340 bytes） | `第二十二章-LibWebP集成使用_展示.md`（254 bytes） |
| `第二十五章-HTTP基础-获取公网时间.md`（3,041 bytes） | `第二十五章-HTTP基础_获取公网时间.md`（257 bytes） |

**建议**：骨架页是 Ingest 前的初始脚手架残留，应删除。

### 三、代码引用失效 [严重度：高]

在全部 710 条 `file:///` 引用中，精细分类结果：

| 分类 | 数量 | 说明 |
|------|------|------|
| A_纯文件有效 | 554 | 文件存在，无锚点 |
| B_锚点有效 | 76 | 文件存在且锚点行号在范围内 |
| C_锚点越界 | 0 | 无过期锚点 |
| E_文件断裂 | 15 | ❌ 文件不存在 |
| F_目录引用 | 65 | 引用目录而非文件（合理） |
| **总计** | **710** | |

**15 条断裂引用 × 4 种模式：**

**模式 1（5 条）— ch35/02-Actor网络角色体系.md**
- 引用：`XGNetCharacter.h`、`XGNetPlayerController.h` 等
- 实际：`XGNetDemoCharacter.h`、`XGNetDemoPlayerController.h`（含 Demo 前缀）
- 涉及文件：`016_XGNetDemo/Source/XGNetDemo/`

**模式 2（2 条）— ch35/09-碰撞事件绑定与DS部署实践.md**
- 引用：`code/017_XGNetDemoForDS/` 目录
- 实际：该目录不存在（仅有 `code/017_XGRPG/`）

**模式 3（5 条）— 横向-实战案例多项目策略.md**
- 引用：`.uproject` 含数字前缀（如 `001_XGSampleDemo.uproject`）
- 实际：文件名无数字前缀（如 `XGSampleDemo.uproject`）

**模式 4（3 条）— 横向-网络通信演进.md**
- 引用：`Source/XGSampleServer/` 路径（UE 插件风格）
- 实际：独立程序使用 `XGSampleServer/Private/` 结构

### 四、孤立页面 [严重度：中]

`knowledge/` 下无入链的页面：

| 文件 | 大小 | 状态 |
|------|------|------|
| `第二十一章-LibWebP集成使用_生成.md` | 255 bytes | 骨架页，应删除 |
| `第二十二章-LibWebP集成使用_展示.md` | 254 bytes | 骨架页，应删除 |
| `第二十五章-HTTP基础_获取公网时间.md` | 257 bytes | 骨架页，应删除 |
| `第二十五章-HTTP基础-获取公网时间.md` | 3,041 bytes | ⚠️ 完整内容被孤立，课程纲要指向骨架版 |

### 五、交叉引用缺失 [严重度：高]

- **课程纲要.md 第 54 行**：链接指向 `第二十五章-HTTP基础_获取公网时间.md`（骨架版，257 bytes）
- 应指向 `第二十五章-HTTP基础-获取公网时间.md`（完整版，3,041 bytes，53 行）
- 其他章节：37 个章节入口页 ↔ 课程纲要 43 条相对路径引用全部覆盖 ✅
- 章节索引页 → 细粒度文档：238 条 file:/// 引用全部完整 ✅

### 六、概念遗漏评估 [严重度：低]

- 18 个代码工程与 37 章内容对应关系清晰
- 所有核心工程（反射容器/网络/动画/GAS/增强输入等）均有章节覆盖
- 无重大概念遗漏

### 七、矛盾声明评估 [严重度：低]

- 横向文档间、章节文档间未发现实质矛盾声明
- 主要问题集中在上文所述的链接歧义和命名混乱

### 八、总计与修复建议

| 类别 | 数量 | 建议优先级 |
|------|------|-----------|
| 断裂引用 | 15 条 | 🔴 高 — 导致文档链接失效 |
| 骨架页清理 | 3 个文件 | 🟡 中 — 残留脚手架 |
| 课程纲要链接 | 1 处 | 🔴 高 — 入口页指向错误 |
| 命名统一 | 3 对 | 🟡 中 — 便于维护 |

**建议修复顺序：**
1. 课程纲要.md 第54行 → 指向完整版第25章
2. 删除 3 个骨架页面
3. 修复横向-实战案例多项目策略.md 中 5 条 .uproject 路径
4. 修复横向-网络通信演进.md 中 3 条 Source/ → Private/ 路径
5. 修复 ch35/02-Actor网络角色体系.md 中 5 条 XGNet* → XGNetDemo* 文件名
6. 修复 ch35/09-碰撞事件绑定与DS部署实践.md 中 2 条路径
7. 经验固化：记录批量 lint 方法论

## [2026-04-29] update | Lint 问题批量修复
- **来源**：课程全局健康检查 Lint 报告（2026-04-29 lint 条目）
- **修复内容**：
  - ✅ **课程纲要.md** 第54行：`第二十五章-HTTP基础_获取公网时间.md` → `第二十五章-HTTP基础-获取公网时间.md`
  - ✅ **删除3个骨架页**：第21/22/25章的下划线/无"的"版本（Ingest 前脚手架残留）
  - ✅ **横向-实战案例多项目策略.md**：5条 .uproject 路径去除数字前缀，`017_XGRPG.uproject` 修正为子目录 `XGRPG/XGRPG.uproject`
  - ✅ **横向-网络通信演进.md**：3条 `Source/XGSampleServer/` → `XGSampleServer/Private/`（独立程序结构修正）
  - ✅ **ch35/02-Actor网络角色体系.md**：3条 `XGNet*.h` → `XGNetDemo*.h`（类名与前缀不匹配）
  - ✅ **ch35/09-碰撞事件绑定与DS部署实践.md**：2条 `017_XGNetDemoForDS/` 断裂引用 → 标记为"课程素材未入库"
- **经验固化**：追加 SKILL.md 16.61（全局 lint 后的批量修复模式）
- **状态**：完成 ✅

## [2026-04-29] update | 创建 dist/README.md 学员交付入口页
- **来源**：参照 Lyra-Deep-Dive/dist/README.md 格式
- **产出**：`dist/README.md`（147 行，9.2 KB）
- **内容**：课程简介、交付物总览（字幕/code/knowledge/Skill 四类）、学习建议（强调 knowledge/ 的查阅价值）、课程素材说明、Skill 介绍与使用示例
- **状态**：完成 ✅

## [2026-04-29] update | SKILL.md 知识蒸馏补齐（6 references + SKILL.md 更新）
- **来源**：逐章对照 knowledge/ 37 章细粒度文档与 SKILL.md 覆盖率，发现 3 个核心遗漏（字符串/网络同步/增强输入）+ 7 个重要遗漏（日志断言/GameplayTag/定时器/智能指针/JSON）
- **产出**：
  - `dist/skills/uecpp-course/references/字符串处理详解.md`（Ch10，180 行）
  - `dist/skills/uecpp-course/references/网络同步基础.md`（Ch35，180 行）
  - `dist/skills/uecpp-course/references/增强输入系统.md`（Ch33，111 行）
  - `dist/skills/uecpp-course/references/日志断言与调试.md`（Ch12+Ch14，126 行）
  - `dist/skills/uecpp-course/references/GameplayTag与定时器.md`（Ch11+Ch8，126 行）
  - `dist/skills/uecpp-course/references/智能指针详解.md`（Ch16，140 行）
  - `dist/skills/uecpp-course/references/HTTP通信详解.md` — 扩充 JSON 序列化章节（Ch24，+86 行）
  - `dist/skills/uecpp-course/SKILL.md` — 36→37 章修正 + 关键类索引+6 分类 + 使用示例+6 问答 + 参考文档索引+6 链接
- **固化**：本次无新增固化经验（属既有流程的批量补齐操作，未发现新的模式性认知）
- **状态**：完成 ✅
