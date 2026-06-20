# uasset_read 更新计划：UE 5.8 锚定

> Active plan. Updated: 2026-06-19. Version anchor: Unreal Engine 5.8.0.

## 目标

把项目的 UE 格式基准从“UE5 通用支持”明确锚定到当前最新 UE 5.8.0，并让后续修复都能用本地 UE 5.8 源码、真实样本、以及可选 UE Editor MCP 读数闭环验证。

本轮不把“pytest 通过”视为完整成功。涉及用户可见 JSON/Markdown、Blueprint 图、组件 Transform、输入绑定、SoftObjectPath、Import/Export、资产类型 fallback 的改动，必须检查实际输出。

## 当前锚点

| 项 | 值 |
|---|---|
| 最新目标版本 | Unreal Engine 5.8.0 |
| 本地引擎路径 | `E:\Develop\lib\UnrealEngine` |
| 本地版本证据 | `Engine/Build/Build.version` = Major 5, Minor 8, Patch 0 |
| 版本宏证据 | `Engine/Source/Runtime/Launch/Resources/Version.h` = `ENGINE_MAJOR_VERSION 5`, `ENGINE_MINOR_VERSION 8` |
| 官方发布证据 | Epic: `https://www.unrealengine.com/news/unreal-engine-5-8-is-now-available` |
| 官方格式资料 | Epic release notes: `https://dev.epicgames.com/documentation/unreal-engine/unreal-engine-5-8-release-notes` |
| 编辑器真值通道 | UE 5.8 Experimental `ModelContextProtocol` plugin；`AllToolsets` 位于 `Engine/Plugins/Experimental/Toolsets/AllToolsets` |

UE 5.8 的 `EUnrealEngineObjectUE5Version` 当前仍以 `IMPORT_TYPE_HIERARCHIES = 1018` 作为 `AUTOMATIC_VERSION`。因此本项目的第一步不是盲目新增更高版本号，而是先确认 UE 5.8 相比现有 1018 支持面，在 PackageFileSummary、Import/Export、PropertyTag、CustomVersion 和具体资产序列化上是否有行为差异。

## 阶段 1：基线盘点

验收目标：得到一份可执行差异清单，区分“版本锚点已覆盖”“格式新增需要实现”“解析器已有 partial/fallback 但状态信号不足”。

任务：

- 对齐版本常量：检查 `src/uasset_read/constants.py`、`src/uasset_read/versioning.py`、`docs/formats/uasset/version/ue5-evolution.md` 是否与 UE 5.8 `ObjectVersion.h` 一致。
- 对齐 PackageFileSummary：以 UE 5.8 `PackageFileSummary.h`、`PackageFileSummary.cpp` 为准复核 `src/uasset_read/serializers/package_summary.py` 的字段顺序和条件分支。
- 对齐 Import/Export：复核 `IMPORT_TYPE_HIERARCHIES`、`FPackageIndex`、export `script_serialization_offset` / `metadata_serialization_offset` 的读取边界。
- 对齐 SoftObjectPath：复核 UE 5.7+ 索引式解析在 UE 5.8 样本上的行为，特别是 SoftClass/TopLevelAssetPath。
- 对齐 PropertyTag：复核 complete type name、extension flags、binary/native serialization 的 fallback 是否可诊断。

输出物：

- 更新 `docs/formats/uasset/version/ue5-evolution.md` 的 UE 5.8 同步状态。
- 如发现差异，新增或更新针对性测试；不要只更新文档。

## 阶段 2：真实样本验收矩阵

验收目标：用 `E:\Develop\lib\Samples` 下的真实资产覆盖主要输出表面，并记录 JSON/Markdown 的实际可读性。

样本矩阵：

| 类别 | 最低样本要求 | 重点输出 |
|---|---|---|
| Blueprint | 本地样本树中至少 2 个 Blueprint；若样本不足，先记录缺口再补充项目样本 | variables、graphs、nodes、pins、components、transforms、input bindings |
| StaticMesh | StarterContent 至少 2 个 mesh | import/export、materials、bounds、fallback status |
| SkeletalMesh | 本地样本树中至少 1 个 SkeletalMesh；若样本不足，先记录缺口再补充项目样本 | skeleton/material refs、LWC vector fields |
| Texture2D | StarterContent texture | platform data metadata、fallback status |
| Material / MIC | StarterContent material + material instance | scalar/vector/texture parameters |
| Animation | AnimSequence 或 BlendSpace 相关资产 | notifies、curves、blend sample structs |
| Pak/IoStore | 若本地有 `.pak/.utoc/.ucas`，至少 1 套真实容器 | container index、short-read diagnostics、unsupported compression status |

默认验收命令：

```powershell
git status --short
$sample = Get-ChildItem "E:\Develop\lib\Samples" -Recurse -Filter "*.uasset" |
    Where-Object { $_.FullName -match "Blueprint" } |
    Select-Object -First 1
python run.py $sample.FullName --output .tmp\ue58\sample.json
python run.py $sample.FullName --markdown --output .tmp\ue58\sample.md
python -m pytest tests -q
```

实际样本路径必须来自当前本地样本树。验收记录必须包含解析状态、错误/诊断数量、关键字段是否非空、Markdown 是否出现对应章节。

## 阶段 3：UE Editor MCP 真值闭环

验收目标：对声称 UE 保真的改动，增加一个读编辑器真值的可选流程；没有启动编辑器时不阻断普通测试。

任务：

- 在 UE 5.8 项目中启用 `ModelContextProtocol`，需要更广工具时启用 `AllToolsets`。
- 启动 MCP server，并记录 `tools/list`、`list_toolsets`、`describe_toolset`。
- 为同一批样本对比 editor-visible 数据和 parser JSON/Markdown：
  - asset class、export object names
  - Blueprint variables、graphs、nodes、pins
  - component hierarchy、transforms
  - input bindings、soft references
  - asset load/compile status
- 将差异归类为 cooked/editor-only stripping、未实现序列化、fallback 可接受、或 parser defect。

## 阶段 4：实现顺序

1. 版本锚点和文档同步：补齐 UE 5.8 本地证据、官方证据、版本表状态。
2. PackageFileSummary / Import / Export 差异修复：优先处理会导致偏移错位的字段。
3. PropertyTag / custom property fallback 修复：优先减少 opaque fallback，并保留诊断。
4. Blueprint 可见输出修复：优先 variables、components/transforms、input bindings、graph 节点/引脚。
5. 资产类型 parser 扩展：按真实样本失败率排序，不一次性承诺全资产覆盖。
6. MCP 证据固化：把编辑器真值流程写成可重复的手动验收步骤或可选脚本。

## 发布门槛

可进入下一个 dev 快照：

- `python run.py --help` 通过。
- `python run.py --list-formats` 通过。
- `python -m pytest tests -q` 通过，或失败项已明确归因为环境/样本缺失。
- UE 5.8 样本矩阵至少覆盖 Blueprint、StaticMesh、Texture2D、Material/MIC 四类。
- JSON/Markdown 人工抽查通过，不能只有测试通过。

可进入正式 release：

- 版本号、changelog、README、release notes 一致。
- 包装元数据齐全：`pyproject.toml` 或等价发布配置、LICENSE、发布标签。
- 真实样本验收记录可复现。
- UE 5.8 MCP 真值流程至少对 1 个 Blueprint 样本完成端到端对比；如未完成，release note 必须明确说明未验证。

## 非目标

- 不承诺写回或修改 `.uasset`。
- 不把 UE Editor MCP 作为普通测试硬依赖。
- 不把所有 fallback 都视为 bug；关键是让 fallback 可见、可解释、可追踪。
- 不为旧 UE4 cooked/editor-only 数据做无限兼容，除非有真实用户样本和明确输出需求。
