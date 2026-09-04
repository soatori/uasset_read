# external/ peer 清单与再分发授权

status: current

> 本文件是 `docs/designs/2026-09-02-peer-corroboration-usage-scheme.md` §4 要求的 peer inventory。
> 它必须位于受版本控制的路径：`external/` 被 `.gitignore:5` 忽略，因此 `external/README.md`
> 永远无法被提交，写在那里的 pin commit 记录对任何 clone 都不可见。
>
> peer 是**佐证**，不是证明（`.claude/rules/constraints.md` Core Constraints「UE source reference required」）。
> 支撑宣称（version/asset-support）仍须满足 `.claude/rules/constraints.md` Test Organization 末条：
> UE source evidence + real fixture + structural assertions。

## 清单

pin commit 与日期于 2026-09-05 由 `git -C external/<peer> log -1` 实测取得，非文档抄录。

| Peer | 语言 | commit | 日期 | 许可证 | 佐证覆盖域 |
| --- | --- | --- | --- | --- | --- |
| CUE4Parse | C# | `dca8ae05` | 2026-05-17 | Apache-2.0 | Zen/IoStore（`UE4/IO/IoStoreReader.cs`、`FZenPackageSummary.cs`、`FIoStoreTocHeader.cs`）、`.usmap`（`MappingsProvider/Usmap/`）、版本枚举副本 |
| UAssetAPI | C# | `5c22374` | 2026-05-25 | MIT | loose 包、`ExportTypes/StringTableExport.cs`、export 表细节 |
| UAssetGUI | C# | `f2d4a7e` | 2026-05-25 | MIT | **无独立解析**：委托 UAssetAPI，不构成独立实现计数 |
| uasset-rs | Rust | `b1d5a7f` | 2025-06-24 | Apache-2.0（`LICENSE-APACHE`） | 仅包头：summary + name/import/export 表 + asset 引用。**不解析 tagged property 值**——`src/lib.rs:135-139` 只记录 `script_serialization_start_offset`/`_end_offset` 字节区间 |
| uasset-reader-js | JS | `a2ebd56` | 2026-06-05 | MIT | 同 uasset-rs：包头布局旁证，属性值解码覆盖未确认 |
| Unreal-Library | **C#** | `ee8cdd2` | 2026-04-19 | MIT | UE3/UE4/UE5 宽版本扫描 |
| AssetToJson | — | `b71e2bd` | 2026-06-19 | **无 LICENSE 文件** | 资产 JSON 字段对照；仅供阅读，见下方红线 |
| UE4TextExtractor | C++ | `37991af` | 2025-06-18 | **MIT NON-AI** | LocRes/文本历史类型（FText 旁证）；仅供阅读，见下方红线 |
| UnrealBPInspect | — | `8436dca` | 2026-06-21 | Apache-2.0 | 蓝图字节码旁证 |

## 再分发红线

1. **AssetToJson 无 LICENSE 文件** → 缺省即「保留所有权利」，不得复制其代码、生成物或字段表进本仓库。仅可作为本地阅读参考；引用其结论时写「阅读参考」而非「再分发允许」。
2. **UE4TextExtractor 是 MIT NON-AI License** → 该许可证显式限制 AI 相关使用。本项目的 CLI/Agent 工具链和 agent 工作流正落在其限制意图范围内：**只允许人类直接阅读其源码**，不得让 agent 把其内容转录进本仓库、也不得据此生成提交进仓库的代码或文档。若需 FText 旁证，改用 CUE4Parse/UAssetAPI。
3. **Lyra / ALS 等 Epic EULA 资产**属 fixture 而非 peer，一律不得入仓库（先例 #619 备注）。
4. 上述限制针对「把 peer 内容写进本仓库」。在本地 checkout 内阅读以形成判断，仍受各许可证约束。

## 维护规则

- 新增或升级 peer：必须在本表更新 commit + 日期 + 许可证，**并**同步更新方案文档的覆盖矩阵。
- 表中「佐证覆盖域」是经源码核实的事实陈述，不是推测。收窄某行时，注明核实所依据的具体文件路径（参照 CUE4Parse/uasset-rs 两行的写法）。
- 独立实现计数：UAssetGUI 委托 UAssetAPI，二者只计一个实现。写「多 peer 共识」前须确认各实现相互独立。
