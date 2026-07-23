# Changelog

## [0.5.4.44] — 2026-07-19

Code quality, report quality, and test consolidation release.

### Breaking Changes
- 移除 `--text` 格式和 TextRenderer — 使用 `--markdown` 替代

### Report Quality
- 批量模式新增 partial 状态统计，按原因分类显示
- JSON renderer 新增 `warnings` 和 `statistics` 顶层字段
- Markdown renderer 诊断信息按严重度分组并显示图标
- 结构化摘要生成（ReportSummary）

### Bug Fixes
- #422: LevelSequence 改为走 tagged properties 路线
- #423: batch 失败时记录完整 traceback 到日志文件
- #424: serial_scan_recovery 增加伪 EExprToken 启发式过滤
- CI resource-safety job 指向现存测试文件
- Ruff: 移除无插值 f-string 前缀，移除未使用变量

### Improvements
- #421: batch_summary 新增 elapsed_seconds 字段
- 测试目录扁平化 — 合并子目录到 tests/ 根目录，正式测试 ≤20 文件
- 清理已删除 API 残留测试

## [0.5.4] — 2026-07-13

Code quality and maintenance release.

### Improvements
- #374: Delete `core.py` dead code (368 lines) — shadowed by `core/` package directory
- #375: Trim `_compat.py` deprecated exports (415→20 lines, removed 356 unused mappings)
- #376: Merge duplicate `sanitize_identifier` wrapper functions (3 files consolidated)
- #377: Update wiki Public-API.md import paths (deprecated → focused imports)
- Merge `curve_table._resolve_name` into shared `resolve_name_from_index`
- Total: **-790 lines** (48085 → 47295, 1.6% reduction)

### Internal
- Removed dead `core.py` file (Python only loads `core/__init__.py`)
- Only 7 deprecated export mappings retained (verified by tests/wiki)
- All `sanitize_identifier` calls use canonical `cpp_gen.sanitizer` module

## [0.5.3.23] — 2026-07-12

23 issue fixes since v0.5.2.31.

### Fixes
- #341: PropertyTag type tree parses correctly according to UE5 version, eliminating inner_count misjudgment
- #341: PropertyTag recovery scan uses real FName binary format
- #341: Window-end candidates rejected when validation fails instead of degraded acceptance
- Limit Zlib/Gzip decompression output size to prevent decompression bombs
- Add decompression ratio cap (10:1) to prevent decompression bombs
- Add resource limits to IoStore header parsing (entry count/block count/method count/partition count/index size)
- Add cycle detection and depth limits to IoStore directory index
- Add recursion depth limit to usmap/mappings property type parsing
- Add ResourceBudget protection to usmap/jmap decompression path
- Fix multiple issues after Transform/DependsMap/graph node review (Issue #329 #331 #338)
- Fix EventGraph export offset out-of-bounds protection (Issue #338)
- Fix FTEXT-SAFETY recovery position corrected to field start position (Issue #337)
- Fix SubGraphs array length limit (Issue #333)
- Fix FText args count limit unified to MAX_SAFE_COUNT (Issue #332)
- Fix Graph node read exception capture expanded (Issue #331)
- Fix StructProperty Transform size corrected to 40/80 (Issue #329)
- Fix preload export NoneType protection (Issue #328)
- Fix read_name index out-of-bounds enhanced diagnostics and strict mode (Issue #334)
- Fix FArchive base class add skip() method, correct test constructor parameters (Issue #327)
- Fix UE4 version constants aligned with UE source ObjectVersion.h (Issue #324)
- Fix SkeletalMesh SK_* file parsing failure (Issue #321)
- Fix bytecode fallback scan classification and confidence marking (Issue #77)
- Fix batch mode recursive scan of subdirectories for .uasset/.umap (Issue #322)
- Fix Enhanced Input Action Trigger mapping correction, Markdown displays correctly (Issue #296)
- Fix _verify_imports class_index dead code replaced with class_name validation (Issue #307)
- Fix bytecode recovery log downgraded to debug to avoid polluting CLI stderr (Issue #303)
- Fix validate_size small file heuristic no longer uses remaining as fallback (Issue #312)
- Fix RSS acquisition failure adds warning log to avoid silently disabling memory protection (Issue #310)

### New Features
- AnimSequence basic trajectory data parsing (Issue #318)
- MovieScene and ControlRig ParameterTrack parsing support (Issue #317)
- ControlRig large file optimization, increase lightweight parsing threshold (Issue #320)
- Unified log management, runtime logs written to log/ directory (Issue #323)
- 235 new integration tests (coverage 28% → 50%)
- 14 new asset samples
- Add Pak/IoStore security integration tests
- Add CLI --version parameter support

### Improvements
- Memory safety: RSS measurement, parser checkpoints, resource budget model
- Security: boundary checks, expanded exception capture, resource limits
- Code refactor: parse_uasset.py split into three files
- Test suite streamlined 1688→78 tests

### Fixes
- #341: PropertyTag type tree parses correctly according to UE5 version, eliminating inner_count misjudgment
- #341: PropertyTag recovery scan uses real FName binary format
- #341: Window-end candidates rejected when validation fails instead of degraded acceptance

### New Features
- 235 new integration tests (coverage 28% → 50%)
- 14 new asset samples (FirstPerson, IntroToUnreal, Lyra, StackOBot, StarterContent)
- pyproject.toml package metadata

### Improvements
- Version number unified to 0.5.3.20

## [0.5.3.19] — 2026-07-11

自 v0.5.2.31 以来完成 19 个 issue 修复（#77, #296~#338）。

### 修复
- 修复 Transform/DependsMap/graph 节点审查后多项问题（Issue #329 #331 #338）
- 修复 EventGraph export 偏移越界防护（Issue #338）
- 修复 FTEXT-SAFETY 恢复位置修正为字段起始位置（Issue #337）
- 修复 SubGraphs 数组长度限制（Issue #333）
- 修复 FText args 数量限制统一为 MAX_SAFE_COUNT（Issue #332）
- 修复 Graph 节点读取异常捕获扩大（Issue #331）
- 修复 StructProperty Transform size 修正为 40/80（Issue #329）
- 修复 preload export NoneType 防护（Issue #328）
- 修复 read_name 索引越界增强诊断和 strict 模式（Issue #334）
- 修复 FArchive 基类添加 skip() 方法，修正测试构造参数（Issue #327）
- 修复 UE4 版本常量与 UE 源码 ObjectVersion.h 对齐（Issue #324）
- 修复 SkeletalMesh SK_* 文件解析失败（Issue #321）
- 修复 bytecode fallback scan 分类并标记置信度（Issue #77）
- 修复 batch 模式递归扫描子目录中的 .uasset/.umap（Issue #322）
- 修复 Enhanced Input Action 的 Trigger 映射修正，Markdown 正确显示（Issue #296）
- 修复 _verify_imports 中 class_index 死代码替换为 class_name 验证（Issue #307）
- 修复字节码恢复日志降级为 debug，避免污染 CLI stderr（Issue #303）
- 修复 validate_size 小文件启发式不再使用 remaining 作为 fallback（Issue #312）
- 修复 RSS 获取失败时添加 warning 日志，避免静默禁用内存保护（Issue #310）

### 新增
- AnimSequence 基础轨迹数据解析（Issue #318）
- MovieScene 及 ControlRig ParameterTrack 解析支持（Issue #317）
- ControlRig 大型文件优化，提高轻量解析阈值（Issue #320）
- 统一日志管理，运行日志写入 log/ 目录（Issue #323）
- 添加属性提取辅助函数模块，消除 asset_types 处理器中的重复模式
- 添加集中式状态计算模块 status.py
- 添加工作量预算，高连接度畸形输入快速中止
- diff 与文本输出采用流式输出，不同时持有两个完整文本
- 实现 BoundedEventBuffer 有界诊断收集器
- lazy raw bytes 默认不缓存，IR 使用不可变 tuple view
- mappings/raw 输入有界读取，拒绝压缩炸弹
- 添加大文件隔离判断逻辑
- 增加 JsonRenderer.render_to() 流式输出和 _build_data() 提取
- export 懒加载使用 open_file() 而不是 read_file()
- 实现受限分块解压并添加预算检查
- 添加 PackageProvider.open_file() 范围读取接口
- 建立可验证的资源预算模型
- 添加 CLI --version 参数支持

### 改进
- 内存安全：RSS 测量、解析器检查点、资源预算模型
- 安全防护：边界检查、异常捕获扩大、资源限制
- 代码重构：parse_uasset.py 拆分为三个文件、graph/flow_builder.py 提取 graph_utils.py
- 测试套件精简 1688→78 测试

## [0.5.2.31] — 2026-07-04

自 v0.5.1.19 以来完成 31 个 issue 修复（#202 ~ #288）。

### 修复
- 修复 ParseResult.graphs 在 IR/JSON/Markdown 输出链中丢失（Issue #285）
- 修复 UEdGraph 从错误 export 偏移读取导致合法资产被标记 partial（Issue #286）
- 修复 Map Pin terminal 类型在反序列化和 IR 输出中丢失（Issue #287）
- 修正文档中不存在的 scripts/test_matrix.py 测试入口（Issue #288）
- 修复 core.py diff_single() 中 errors 列表未使用（Issue #281）
- 修复 batch 同 stem 的 uasset/umap 静默覆盖输出（Issue #278）
- 修复生产宏上下文丢失 tunnel/pin 数据导致非标准宏展开失效（Issue #277）
- 修复损坏 PropertyTag 在同一偏移重试至上限且 strict 模式失效（Issue #276）
- 修复 pytest console entry 无法收集 tests.conftest 导入模块（Issue #275）
- 修复 kismet/translator.py print() 改为 logging（Issue #271）
- 修复 16 处静默异常吞没（except + pass）丢失错误上下文（Issue #270）
- 修复 flow_builder.py 3 处可变默认参数（Issue #269）
- 修复 link 模块 get_full_name 无限递归和 verify_imports 静默丢弃（Issue #250）
- 修复 kismet translator 臃肿和 TextConst 枚举冲突（Issue #249）
- 修复 graph 模块 SubGraphs 缺失和硬编码 hack（Issue #248）
- 修复 blueprint 模块多处功能缺陷和零测试覆盖（Issue #247）
- 修复 archive.py 内联 import 反模式和 serialize_bits 语义偏差（Issue #246）
- 修复 blueprint wildcard 键含前导空格导致类型匹配完全失败（Issue #245）
- 修复 pak/ioStore 二进制格式与 UE 源码存在多处严重偏差（Issue #244）
- 修复 CPF_* 属性标志约 25 个值与 UE ObjectMacros.h 严重不匹配（Issue #243）
- 修复 legacy -6 文件解析失败（StarterContent 等）（Issue #257）
- 修复 models 层两层重复和 from_archive 混入（Issue #255）
- 修复 mappings.py 文件句柄泄漏和 batch_worker stderr 吞没（Issue #254）
- 修复 pak 模块编解码不对称和默认 Zlib 问题（Issue #253）
- 修复 renderers Markdown 过滤不一致和 IR Builder parent_class 风险（Issue #252）
- 修复入口点参数断裂、代码重复和私有函数泄漏（Issue #251）
- 修复 __all__ 重复条目 + 私有函数导出修复（Issue #259）
- 修复 6 个 CustomVersion GUID 错误（Issue #202）
- 补充 EUEVersion.UE5_8 并修复文档字符串（Issue #206）

### 新增
- CFG 结构化输出 — 基于 CFG 的控制流重建（Issue #265）
- Git textconv 集成 — .uasset 二进制 diff 可读化（Issue #266）

### 改进
- 新增 `_validate_graph_export_offset()` 偏移验证函数
- 新增 Map Pin terminal 类型测试覆盖
- CLAUDE.md 测试命令修正为标准 pytest 命令

## [0.5.2-dev] — 2026-06-28

### 新增

- **动画蓝图全面支持**
  - 移除 `AnimBlueprintGeneratedClass` 跳过标记
  - 新增 `AnimBlueprintIR` 数据模型
  - 提取 BakedStateMachines（烘焙后的状态机）
  - 提取 AnimNotifies（动画通知）
  - 提取 SyncGroupNames（同步组）
  - JSON/Markdown 渲染器支持动画字段输出

- **AnimSequence 深度元数据提取**
  - 提取 AdditiveAnimType、Interpolation、RateScale 等
  - 提取 FloatCurveNames（浮点曲线名称）
  - 检测 CompressedData 存在性

- **AnimMontage 全新 Handler**
  - 提取 BlendModeIn/Out、BlendIn/Out 参数
  - 提取 SyncGroup、SyncSlotIndex
  - 提取 AnimNotifies

- **动画子图类型识别**
  - UAnimationStateMachineGraph → state_machine
  - UAnimationStateGraph → state
  - UAnimationTransitionGraph → transition
  - UAnimationConduitGraph → conduit

## [0.5.1.19] — 2026-06-28

自 v0.5.0 以来完成 18 个 issue 修复（#169 ~ #186）。

### 新增
- PackageFlags 完整定义：从 UE 源码 ObjectMacros.h 迁移 30 个 PKG_ 常量（Issue #179）
- PackageFlags 解码输出：JSON 和 Markdown 渲染器新增 `package_flags_decoded` 字段
- AssetRegistryData 解析：提取资产元数据标签（ObjectPath、ObjectClassName、Tags）（Issue #185）
- HexView 调试系统：结构化字节偏移追踪，支持所有读取方法（u8/u16/u32/i32/f32/f64/fstring 等）（Issue #182）
- BlueprintDescription 提取：从蓝图元数据中提取描述信息（Issue #169）
- ImplementedInterfaces 提取：接口列表暴露到输出（Issue #169）
- --full-parse CLI 标志：强制完整蓝图解析（跳过 export_count > 300 的轻量解析）
- 动画蓝图 AnimGraph 嵌套子图解析支持（Issue #178）
- GatherableTextData 本地化数据解析（Issue #184）
- UE4/UE5 版本枚举注释完善（Issue #181）
- UE5 条件字段解析完整性验证（Issue #180）
- UE5.7 SavedPackageHash 字段顺序验证（Issue #186）

### 修复
- BlueprintVariable.var_type 字段：从泛型属性中正确提取 pin_category 和 pin_subcategory（Issue #172）
- ReceiveBeginPlay 事件分类：K2Node_Event 标记 is_implemented=False，与 MCP 语义对齐（Issue #171）
- 非蓝图资产 JSON 输出：修复 exports 为空的问题（Issue #175）
- package_name 填充：修复 summary.package_name 为字符串 "None" 的问题（Issue #175）
- BoxSphereBounds 多格式支持：3f/3d/LWC/pre-LWC/compact 格式（Issue #175）
- FString UTF-16 解码：使用 utf-16-le 显式字节序，修复代理对解码错误（Issue #183）
- HexView 空字符串条目：修复 read_fstring 空字符串时的记录问题
- ImplementedInterfaces 解析为 opaque 空字段修复（Issue #173）
- BP_FirstPersonPlayerController 变量 Category 解析失败修复（Issue #170）

### 改进
- 继承事件与实现函数区分：解析器现在正确区分 K2Node_Event 和 K2Node_FunctionEntry
- IR 构建器：object_class 正确解析非蓝图 export
- 蓝图解析器与 MCP 数据对比差异分析（Issue #177）

## [0.5.0] — 2026-06-12

### 新增
- 解析器模块拆分：blueprint/cpp_gen/kismet/parsers/serializers 独立子包
- IR Builder 增强，更完整的中间表示构建

### 变更
- **输出格式精简**：仅保留 JSON/Markdown 两种输出格式，移除 Text/BlueprintText/BlueprintUE/CppSkeleton
- 移除 cpp_gen/cpp_skeleton C++ 代码生成能力
- 移除 formatters/ 模块，所有格式化通过渲染器系统完成

### 改进
- 大文件拆分为子模块，改善代码组织结构
- 文档清理：移除已废弃模块的引用
- 测试重组为 contracts/units/e2e 三层架构

### 修复
- Kismet fallback class detection 和 self-referencing parent_class
- Graph detection fallback 和 node class_name resolution
- blueprint_text 渲染改进
- SerializationControlExtensions 语义映射与结构化诊断
- partial/opaque 状态必须附带可追踪诊断原因

## [0.4.5] — 2026-06-20

### 修复
- PackageFileSummary UE 5.8 对齐：修复 LegacyGuid 缺失读取（UE5 < 1016 资产偏移错位根因）
- 修正 OwnerPersistentGuid 条件：FileVersionUE4 >= 519 && < 520
- 修正 ChunkIDs 读取：TArray\<int32\>（4 bytes/元素）替代误用的 16 bytes
- 两个偏移 bug 相互抵消的隐性问题修复

### 改进
- UE 5.8 ObjectVersion.h 版本常量对齐（18 项全部确认一致）
- UE 5.8 样本验收：Blueprint、StaticMesh、Material、SkeletalMesh、Animation、DataTable 全部通过
- StructProperty size mismatch 警告消除
- FString 损坏恢复、Texture2D 边界检查
- Transform struct_binary_decoded 支持 + Input Action 绑定收集
- BinaryOrNative handler None 返回修复 + UE5 旧格式 PropertyTag 支持
- SerializationControlExtensions 虚假未知位警告消除

### 文档
- 新增 ue5-evolution.md UE 5.8 对齐修复记录
- 补充 FPropertyTag 完整字段表 + UPROPERTY 说明符 + CDO 机制文档
- 补充 K2Node 语义参考 + 蓝图通信机制 + UE 模块映射文档

## [0.4.3] — 2026-06-05

### 新增
- IR → Renderer 架构
- 8 种输出格式（JSON, Text, Markdown, 等）
- Kismet 反编译器改进
- C++ 骨架生成质量增强

### 改进
- 直接脚本运行（无需 pip install）
- 12+ 资产类型支持

### 修复
- 签名解析器修复
- 测试可移植性改进

## [0.4.2] — 2026-05-20

### 新增
- function_graphs 字段从 result.graphs 填充
- IR 构建器 function_graphs 支持

## [0.4.1] — 2026-05-15

### 改进
- JSON 渲染器 function_graphs 改用 ir.function_graphs
