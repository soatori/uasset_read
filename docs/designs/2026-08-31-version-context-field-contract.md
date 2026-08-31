# G1：VersionContext 字段契约

> **文档状态：current + target**（current = 基线 `bd3309a7` 已实现；target = 本文件末尾的扩展决策）。
> 关联：`docs/designs/2026-08-26-package-first-uasset-parser-refactor.md`（权威目标，其 VersionContext 一节）；Issue #621。
> 现状断言全部以基线源码为准，引用 `file:line`。

## 1. 当前实现位置

- 类型定义：`src/uasset_read/v2/version.py` — `VersionContext`（`frozen=True` dataclass，14 字段，`version.py:32-61`），辅助类型 `EngineVersion`（`version.py:13-22`）、`MappingInfo`（`version.py:25-29`）。
- 构造入口：`build_version_context_from_summary()`（`version.py:64-125`）。
- 唯一构造点：`LegacyPackageReader.read()` 在 `depth in ("asset", "decode")` 时调用（`src/uasset_read/v2/package/legacy.py:445-452`），随后传给 `run_handlers()`（`legacy.py:455-457`）。
- 唯一消费链：`v2/handlers.py` 的 `AssetHandler.supports/enrich` 形参与 `run_handlers()`（`handlers.py:21-51`）。**基线中 handler 实际读取的 context 字段只有 `depth`**（`handlers.py:728`、`handlers.py:740`，`BlueprintFamilyHandler` 按 depth 分支）；`projection.py`、`agent_tools.py`、`api.py` 均不引用 `VersionContext`（全仓 grep 核实，除定义/构造/传参外无其他读取点）。

## 2. 逐字段契约表

来源缩写：**S** = package summary（`serializers/package_summary.py`）；**R** = reader 参数/构造注入；**—** = 无人赋值（保持默认）。

| 字段 | 类型 | 来源 | 填充情况（基线） | 消费者 | 必填性 |
|---|---|---|---|---|---|
| `file_version_ue4` | `int` | S：`summary.file_version_ue4`（`package_summary.py:328`→`version.py:112`） | 已填充 | **暂无**（仅 `version_string` 属性引用，`version.py:61`，该属性当前无调用方） | 有默认值 0；实际包恒有值 |
| `file_version_ue5` | `int` | S：`summary.file_version_ue5`（`version.py:113`） | 已填充（UE4 包为 0） | **暂无**（`is_ue5` 属性引用，`version.py:53`，阈值 522；当前无调用方） | 同上 |
| `licensee_version` | `int` | S：`summary.file_version_licensee`（`version.py:114`） | 已填充 | **暂无** | 可选 |
| `custom_versions` | `Mapping[str,int]` | S：`summary.custom_versions` 的 `guid→version` 映射（`version.py:80-86`；guid 为小写 hex，`package_summary.py:190`） | 已填充 | **暂无** | 可选（空 dict） |
| `engine_version` | `EngineVersion\|None` | S：`summary.saved_by_engine_version`（`version.py:89-98`） | 已填充（summary 无该字段时 None） | **暂无**（`version_string` 优先用它，`version.py:57-58`） | 可选 |
| `compatible_engine_version` | `EngineVersion\|None` | S：`summary.compatible_with_engine_version`（`version.py:100-109`） | 已填充（同上） | **暂无** | 可选 |
| `package_layout` | `Literal["legacy","zen"]` | R：构造点硬编码 `"legacy"`（`legacy.py:448`） | 已填充 | **暂无** | 有默认 `"legacy"` |
| `cooked` | `bool\|None` | 构造参数；**基线构造点未传**（`legacy.py:446-452` 无此 kwarg） | **恒为 None** | **暂无** | 可选 |
| `editor_only_filtered` | `bool\|None` | 同上，未传 | **恒为 None** | **暂无** | 可选 |
| `platform` | `str\|None` | 同上，未传 | **恒为 None** | **暂无** | 可选 |
| `game` | `str\|None` | R：`LegacyPackageReader.__init__(game=…)` → 构造点传入（`legacy.py:450`；CLI `--game`，`cli.py:128`） | 已填充（未指定时 None） | context 侧**暂无**（game profile 的实际生效路径是 `parse_properties_from_export(game=…)` 直接收参，`legacy.py:597`） | 可选 |
| `byte_order` | `Literal["little","big"]` | 无人赋值 | **恒为默认 `"little"`** | **暂无** | 有默认 |
| `mappings` | `MappingInfo\|None` | R：`mappings_path` 存在时 `MappingInfo(path=…)`（`legacy.py:450`；CLI `--mappings`，`cli.py:127`） | 已填充（无 .usmap 时 None） | context 侧**暂无**（mappings 实际生效路径同为 property parser 直接收参，`legacy.py:596`） | 可选 |
| `depth` | `Literal["package","object","asset","decode"]` | R：`read(depth=…)` 透传（`legacy.py:451`） | 已填充 | **handler**：`BlueprintFamilyHandler`（`handlers.py:728,740`） | 有默认 `"package"` |

诚实结论：**14 个字段中 13 个当前没有代码消费者**；context 目前实质只承载 `depth`。字段本身不是死代码——它们是把 v1 summary 中分散的版本事实集中冻结的载体，供后续 handler/property reader 消费（见 §4）。注意：属性 tag 格式的版本门控目前仍走 `archive._file_version_ue4/_ue5` 回写（`legacy.py:313-314`），**不经过 VersionContext**；收敛该回写属于 target（§4）。

## 3. 决策（contract）

1. **frozen 不可变**：`VersionContext` 保持 `@dataclass(frozen=True)`（`version.py:33`）。不得引入 setter、`dataclasses.replace` 后的"影子版本"或原地 `Mapping` 内容修改；`custom_versions` 构建完成后视为常量。
2. **reader 在解析入口一次性构建**：版本事实只有 reader 有资格汇总。由 `LegacyPackageReader`（未来 `ZenPackageReader`）在 `read()` 内构造一次并传给全部 handler；同一 document 生命周期内不存在第二个 context 实例。基线的"仅 depth≥asset 才构造"是懒化细节，target 收敛为入口一次性构建（handler 之外的 property 分支也应改读 context，替代 `legacy.py:313-314` 的 archive 回写）。
3. **handler 不得自行推导版本事实**：`AssetHandler` 的两个方法都以 `context: VersionContext` 为唯一版本输入（`handlers.py:21-28`）。handler 不接触 archive（基线已满足：`handlers.py` 全部 enrich 只读 `obj.properties`/`obj.coverage`/`package_data` tuple），不得重读 summary、不得按 `class_name` 之外的文件名/引擎大版本猜格式。游戏特殊分支必须是对 `context.game`/`context.custom_versions` 的显式查询，不允许散落字符串匹配（权威设计"解析器读取同一个不可变 context"一节）。
4. **字段只增不减**：新增字段必须带默认值，保证既有构造点（当前仅 `version.py:111-125`）不破坏。

## 4. 扩展点（target，随 Zen reader 到来）

- `package_layout="zen"`：`ZenPackageReader` 构造同一 `VersionContext`，layout 字段成为 handler 分流依据；Legacy/Zen 不共享二进制布局代码，只共享本契约。
- `cooked` / `editor_only_filtered`：当前恒 None。Legacy 侧可从 `summary.package_flags`（PKG_Cooked/PKG_FilterEditorOnly）填充；Zen 侧由 `FZenPackageSummary`/container metadata 填充。权威设计的 VersionContext 一节已列为必带信息。
- `platform` / `byte_order`：IoStore/Pak 容器元数据与 trailer 是真实来源（#624/#625 fixture 前置）；在获得样本前保持 None，不猜。
- `custom_versions`：当前是 `guid→version` 扁平映射；若出现第二个按自定义版本族分支的真实 handler，再考虑 Guid→名称解析表（不预建）。
- `mappings`：unversioned property reader（#623 fixture 前置）将通过本字段取得 `.usmap` 来源描述，而不是 reader 参数旁路。

## 5. 验收

- 契约测试断言 frozen（赋值抛 `FrozenInstanceError`）与 `build_version_context_from_summary` 对真实样本 summary 的逐字段映射（版本/自定义版本数非零）归 `tests/test_core.py` 收集项预算内。
- 任何"VersionContext 字段已生效"的宣称必须有源码消费点 + fixture 证据；本文 §2 的消费列是唯一的 current 依据。
