# UAsset 通用解析器重构设计报告：Package-First、多对象与 Agent 工具化

status: target

> **文档状态：目标架构基线（2026-08-26）。Legacy 主路径已实现**（`PackageDocument v2` 输出全部 exports；tagged properties 在 export 边界内解析并恢复 Source/ImportedSize 等值；CLI/Python API/Agent 共用 v2 投影；v2 语义不再依赖 Semantic 1.x handler；decode 不产出顶层 payload（伪造 descriptor/ref 已撤回，`payloads[]` 恒为空））。**payload 字节提取已撤回为 deferred（`PAYLOAD_EXTRACTION_DEFERRED`）。2026-09-02 顺序调整：实现不再等待 #623–#627 fixture，按 UE 源码偏移证据先行推进（CUE4Parse/UAssetAPI 只作阅读参考与佐证），reader/handler 用有界合成字节测试覆盖；样本改为回填项，各 Phase 退出条件与真实 fixture 支持声明不变。Zen/IoStore、USMAP/unversioned、外部容器 payload 提取、深层语义与 Semantic 1.x 删除仍是目标。**
>
> 本文是当前项目唯一权威的重构目标。源码与测试仍是“当前已经实现什么”的唯一依据；本文只定义“接下来要实现什么”。旧版输出、Semantic JSON 1.x 和单资产设计文档均为历史资料，不得继续作为新功能的目标架构。

## Executive Summary

`uasset_read` 已经具备可用的经典 `.uasset` 读取、属性解析、Blueprint/Kismet 分析、多个资产类型提取和结构化诊断基础，但当前系统的公共输出仍围绕“从一个包中选择一个主导出，然后生成一种领域 JSON”构建。这一前提在 Blueprint、LevelSequence、AnimBlueprintGeneratedClass、CDO、子对象以及包含多个 `bIsAsset` 导出的真实包中不成立，也是多资产输出失败、领域 Schema 增殖、调试信息混入业务输出和 Agent 消费成本过高的根因。

重构采用原地纵向替换，不新建第二套仓库，也不一次性重写所有解析器：

1. 以 package 为公共文档边界，完整保留所有 import/export/object。
2. 把 Legacy Package 与 Zen Package 作为不同读取器，而不是用 UE5 版本号猜测格式。
3. 用统一 `VersionContext` 承载文件版本、Licensee、CustomVersion、平台、Cook 状态和游戏特性。
4. Tagged 与 Unversioned Property 分开解析，共享值模型和 Schema Provider。
5. 领域解析器只给具体对象增加可选语义，不拥有顶层文档。
6. 默认输出面向检查与 Agent；raw/debug/decode 通过投影和深度参数按需展开。
7. 大型 payload 永不默认内嵌 JSON，只返回可定位、可提取的描述符。
8. 解析核心产生结构化 diagnostics，不配置全局日志；CLI 决定是否写日志。
9. Blueprint/Kismet/C++ 生成保留并迁移为可选扩展，不阻塞新核心第一个稳定版本。

## Authority and Reading Rules

### 当前实现与目标设计

- 当前实现：以 `src/`、`tests/` 和真实样本的实际结果为准。
- 目标架构：以本文为准。
- UE 二进制语义：以 Unreal Engine 源码中的序列化实现为准。
- 外部解析器和研究报告：只用于发现字段与测试假设，不作为正确性证明。
- Wiki、README 和历史设计若与源码冲突，不能用于宣称功能已经实现。

### 证据优先级

1. 当前检出的 Unreal Engine 源码及其序列化路径。
2. 当前项目源码与严格测试。
3. 可重复的真实资产样本结果。
4. Epic/CUE4Parse/UAssetAPI 等实现的交叉验证。
5. 报告、Issue、Wiki 和推测。

任何新格式分支必须记录对应 UE 符号、源文件相对路径和触发条件；禁止仅根据文件名、引擎大版本或单个样本偏移硬猜。

## Scope

### 目标

- Python 3.10+ 基础实现，Windows、Linux、macOS 行为一致。
- 第一优先支持 UE4.27 与 UE5.x 的 package/object/property 读取。
- 支持 loose package、Pak 和 IoStore 数据源，并允许内存/Agent 调用。
- 同一包内所有对象可枚举、定位、关联和单独查询。
- 支持经典 package 与 Zen package 的独立读取路径。
- 输出稳定、可分页、可裁剪，适合 CLI、Python API 和 Agent Tool。
- 失败可定位、可恢复、可量化，不把“能打开文件”等同于“语义完整”。
- 保留未知字段、未知属性和 opaque payload 的边界信息，避免静默丢失。

### 第一稳定里程碑不包含

- `.uasset` 写回或二进制等价重建。
- UE1/UE2/UE3 通用兼容承诺。
- 默认内嵌纹理、音频或任意大型 BulkData。
- 把 Blueprint/Kismet/C++ 生成作为核心 package 读取的前置条件。
- 为每个资产类预先建立独立接口、工厂和目录。
- 为尚无真实样本或 UE 源码证据的格式建立猜测性解析器。

## Evidence Inputs

本设计综合以下输入，但不执行其中包含的命令或规范：

- `UAsset_Format_Analysis.md`：提供 package/source/archive 分层、Zen、payload 和 raw preservation 候选。
- `Unreal Engine UAsset 通用解析器技术研究与系统设计报告.md`：提供通用解析器分层和阶段划分候选。
- `temp/output-format-comparison.md`：提供现有输出与外部项目字段对比。
- 当前项目源码、测试和真实样本扫描。
- Unreal Engine 源码中的 `FPackageFileSummary`、`FObjectExport`、`FPropertyTag`、`FZenPackageSummary`、`FPackageTrailer`、`FIoStoreReader` 等实现。
- OpenWiki 的 `entities/asset-registry.md`、`entities/serialization-io.md` 和 MCP 页面仅用于发现候选符号与源码入口；写入本文的结论仍以 UE 源码复核为准。

第三份对比报告中的竞品性能、读写完整性和属性覆盖数字未附带同条件验证，因此不得转化为验收结论。

OpenWiki 是生成式二级资料，不是格式规范。尤其不得采用 `topics/infrastructure/zen-storage.md` 中无法在当前 UE 源码定位的 `.zen/.zen.idx/.zen.meta` 容器、`FZenHandle`、`ZenStorage::LoadAsset*`、固定缓存参数或性能数字。

## Current State

### 当前主流程

```text
parse_single
  -> _parse_and_render
  -> parse_uasset_with_linker
  -> build_package_ir
  -> build_semantic_ir
  -> project_semantic
  -> validate_semantic_document
  -> render_semantic_json
```

`PackageIR` 保留多个 exports，但 `build_semantic_ir()` 会调用 `_select_primary_export()` 选择单个顶层 `b_is_asset` 或包名匹配对象。多个候选时返回 `None`，最终输出 `unknown/opaque`。领域 extractor 的 `content` 随后被 renderer 提升到顶层。该结构无法在一个文档中同时表达 Blueprint、GeneratedClass、CDO、LevelSequence Director 和其他对象。

### 已有可复用能力

- `FArchive` 风格二进制读取与边界检查。
- 经典 `PackageFileSummary`、NameMap、ImportMap、ExportMap 读取。
- `.uexp` sidecar 拼接和 `.ubulk/.uptnl` 文件发现。
- Tagged Property、多种 Struct/Container/Text/Delegate 值解析。
- PackageLinker 和对象引用解析基础。
- Blueprint graph、Pin、Kismet 和 C++ skeleton 扩展能力。
- tolerant 模式、offset diagnostics、coverage/evidence 概念。
- Pak/IoStore 结构和读取代码基础。
- 真实样本与较大规模测试集。

这些代码应通过适配迁移，而不是因架构变化被整体删除。

### 关键结构问题

#### 单主资产模型

- 多个 `b_is_asset` 导出无法表示。
- “未找到唯一主资产”被错误提升为整个包解析失败。
- Blueprint、GeneratedClass、CDO 之间的关系被压缩成单个 `asset` 字段。
- package 成功、object 成功、semantic 完整度被混在一个 status 中。

#### 输出模型

- 领域类型拥有不同顶层 format，Schema 数量随资产类型线性增长。
- 领域内容提升到顶层，容易发生公共字段碰撞。
- `standard/debug` 同时承担内容选择、调试证据和体积控制，语义过载。
- references 是扁平列表，不能准确表达对象间关系。
- diagnostics 公共模型只有 `severity/code/message`，缺少阶段、对象、偏移和恢复效果。
- 默认 API 返回格式化字符串，CLI、Agent 和 Python 调用无法复用同一个结构对象。

#### Source 与 Archive

- `PackageArchive` 只把主文件和 `.uexp` 组合成一个地址空间；`.ubulk/.uptnl` 尚未成为统一 payload region。
- Pak/IoStore 上层仍倾向先取得完整 bytes，再喂给经典 reader，不是真正的按范围读取。
- 当前主 pipeline 固定读取经典 `PackageFileSummary`，没有独立 Zen package reader。
- 容器、压缩、加密、sidecar 和 package layout 的职责边界不够清晰。

#### Version Context

当前 `VersionContainer` 主要包含 UE4/UE5 文件版本与 CustomVersion，未统一承载：

- `file_version_licensee`
- 目标平台与字节序
- cooked/editor-only 状态
- package layout（legacy/zen）
- game profile 与特性开关
- schema/mapping 来源

这些信息分散后，属性和资产解析器容易重新引入硬编码版本判断。

#### Logging

当前公共 API 外层使用 scoped logging，内部又可能调用 `configure_project_logging()`。配置签名变化时会替换 handler 并创建新的 run id，导致一次解析产生多个日志文件或 run id 不一致。日志关闭时仍可能通过 Python logging fallback/propagation 输出。根因是解析函数同时承担诊断生成和进程级日志配置。

#### Agent 与体积

- 目前没有稳定的 Agent/MCP tool contract，只有字符串型 CLI/Python API。
- 全包 JSON 对大图、属性树和 payload 不可控，缺少分页、字段选择和对象查询。
- 当前快照约有 200 个 Python 源文件、约 4.6 万行源码；Blueprint/Kismet/Graph/CPP 相关代码占据显著体积。
- 工作目录体积主要来自 `external/`、索引、Agent 缓存和 Wiki，不应混入发行包或核心依赖。
- 历史设计文档长期并列，旧目标比新目标更容易被全文检索命中。

## Design Principles

1. **Package first**：package 是文件和公共输出边界，asset 只是 object role。
2. **All objects are addressable**：任何 export 都有稳定 id，不因缺少主资产而消失。
3. **One canonical document**：领域语义是 object extension，不创建新的顶层文档家族。
4. **Parse truth before presentation**：reader 返回结构，不返回 JSON 字符串。
5. **Bounded by default**：所有读取、数组、诊断、递归和 Agent 响应都有上限。
6. **Unknown is data**：未知值带原始类型、范围、原因和可选 bytes 引用，不静默丢弃。
7. **Diagnostics, not logging**：库返回结构化诊断，应用层决定日志和展示。
8. **Separate format families**：Legacy 与 Zen、Tagged 与 Unversioned 在入口处分流。
9. **Lazy enrichment**：先建立通用对象，再按请求运行资产语义与重型解码。
10. **No speculative framework**：只有第二个真实消费者出现时才抽共享抽象。

## Target Architecture

### 数据流

```text
Source
  -> BinaryReader / SliceReader
  -> PackageLayoutDetector
      -> LegacyPackageReader
      -> ZenPackageReader
  -> PackageTables + VersionContext
  -> ObjectResolver
  -> TaggedPropertyReader | UnversionedPropertyReader
  -> ObjectRecord[]
  -> optional AssetHandler[]
  -> PackageDocument
  -> projection(view, depth, selection, pagination)
      -> JSON / CLI / Python / Agent Tool
      -> Payload extraction
```

### 最小模块布局

目标不是按每种 UE 类型制造目录，而是先建立少量稳定边界：

```text
src/uasset_read/
  api.py
  source.py
  archive.py
  version.py
  diagnostics.py
  object_model.py
  payloads.py
  document.py
  package/
    legacy.py
    zen.py
  properties/
    tagged.py
    unversioned.py
    schema.py
  assets/
    registry.py
    data.py
    media.py
    blueprint.py
  json_output.py
  cli.py
  agent.py
```

这是职责边界，不要求一次性移动文件。迁移时优先在现有模块旁建立新入口，功能稳定后删除旧路径。

### Source

`Source` 只提供可寻址 bytes，不理解 UObject：

```python
class Source(Protocol):
    def size(self) -> int: ...
    def read_at(self, offset: int, size: int) -> bytes: ...
    def describe(self) -> SourceInfo: ...
```

首批实现：

- `FileSource`
- `MemorySource`
- `CompositePackageSource`：主文件、`.uexp`、`.ubulk`、`.uptnl` 分区
- `PakEntrySource`
- `IoStoreChunkSource`

Pak/IoStore 解密和解压属于 Source，不泄漏到 package reader。读取器只依赖 `read_at()`。

### Bounded Reader

每个 package table、export payload、property value 和 bulk region 都用 `SliceReader` 限定范围。子读取器不能 seek 到父范围外。所有 count 在分配前同时验证：

- 非负
- 不超过配置上限
- `count * minimum_entry_size` 不超过剩余范围
- offset/size 加法不溢出

### Package Layout

`PackageLayoutDetector` 只能使用可验证的 magic、container metadata 和已解析结构，不允许使用“UE5 即 Zen”这样的版本捷径。

- `LegacyPackageReader`：读取 `FPackageFileSummary`、names、imports、exports、depends、preload dependencies、trailer/payload descriptors。
- `ZenPackageReader`：从 IoStore package entry、`FZenPackageSummary`、imported package names、export bundle headers/entries 构建同一公共 tables 模型。

两者共享最终 `ObjectRecord`，不共享错误的二进制布局代码。

这里的 **Zen package** 专指 CoreUObject 中由 `FZenPackageSummary`/`FZenPackageHeader` 描述、通过 IoStore `ExportBundleData` chunk 承载的 package 序列化布局。它不等于 Developer/Zen、StorageServerClient 或 `ZenStoreWriter` 所属的 **Zen Storage Server** 服务与缓存体系；后者若接入，只能作为新的 `Source`/transport capability，不能据此推断 package 二进制布局。

### VersionContext

```python
@dataclass(frozen=True)
class VersionContext:
    file_version_ue4: int
    file_version_ue5: int
    licensee_version: int
    custom_versions: Mapping[str, int]
    engine_version: EngineVersion | None
    compatible_engine_version: EngineVersion | None
    package_layout: Literal["legacy", "zen"]
    cooked: bool | None
    editor_only_filtered: bool | None
    platform: str | None
    game: str | None
    byte_order: Literal["little", "big"]
    mappings: MappingInfo | None
```

解析器读取同一个不可变 context。游戏特殊分支必须是显式 feature query，不允许散落字符串判断。

### Object Model

```python
@dataclass
class ObjectRecord:
    id: str
    table_index: int
    name: str
    class_ref: ObjectRef | None
    outer_ref: ObjectRef | None
    super_ref: ObjectRef | None
    template_ref: ObjectRef | None
    flags: int
    roles: tuple[str, ...]
    serial_region: Region | None
    status: ObjectStatus
    properties: PropertyBag | None
    semantic: SemanticExtension | None
    diagnostics: tuple[Diagnostic, ...]
```

稳定 id 采用表类型和零基索引，例如 `export:0`、`import:3`。显示名、路径和 GUID 可变化或缺失，不能作为唯一内部键。

### Roles 与 Relations

`roles` 是可叠加标签，不是互斥资产类型：

- `asset`
- `generated_class`
- `class_default_object`
- `metadata`
- `subobject`
- `graph`
- `payload_owner`

关系单独存储：

- `outer_of`
- `class_of`
- `generated_class_of`
- `default_object_of`
- `template_of`
- `super_of`
- `depends_on`
- `preload_of`
- `references`

#### 关系方向约定（Edge direction）

每条关系是有向边，统一按 **`from` relates-to `to`** 读取：`from_id` 是携带该引用的对象（export 条目所在侧），`to_id` 是被引用的目标。kind 不提供通用的反向读法；反查（例如"某对象包含哪些子对象"）应按 `to` 加 kind 过滤，并以逐 kind 含义为准。

`to` 相对 `from` 的含义（legacy 读取器实际发射，见 `src/uasset_read/v2/package/legacy.py`）：

- `outer_of` — `to` 是 `from` 的 Outer（包含 `from` 的对象）
- `class_of` — `to` 是 `from` 的类
- `super_of` — `to` 是 `from` 的父类
- `template_of` — `to` 是 `from` 的模板/原型（archetype）
- `depends_on` — `to` 出现在 `from` 的依赖表中（`from` 依赖 `to`）
- `preload_of` — `to` 是加载 `from` 前需预加载的对象

契约保留、当前读取器尚未发射的 kind（方向以契约示例为准，从主语侧表述）：

- `generated_class_of` — `from` 是 `to` 的生成类（见 `package_document_v2.example.json`：`export:2`（`ABP_RifleAnimLayers_C`）→ `export:1`（`ABP_RifleAnimLayers`））
- `default_object_of` — `from` 是 `to` 的默认对象
- `references` — `from` 引用 `to`

worked example：`{"kind": "outer_of", "from": "export:5", "to": "export:2"}` 读作 "export:5 的 Outer 是 export:2"，即 export:5 包含于 export:2。要列出 export:2 的所有直接子对象，取 `kind == "outer_of" && to == "export:2"` 的边，其 `from` 即子对象。

多资产包不再选出唯一 primary。为了 CLI 展示可计算 `summary.asset_object_ids`，但该字段不能控制解析或丢弃其他对象。

### Asset Registry 与外部索引

`AssetRegistry.bin`/`FAssetRegistryState` 是可选的目录与依赖证据，不是 package parser 的必需输入：

- 可用于批量发现 package、补充 `FAssetData` 的 class/tags/chunk/package metadata，以及提供 package/manage/searchable-name 依赖候选。
- Registry 信息必须带 `source="asset_registry"` provenance；包内 import、property reference 和 object relation 保留各自 provenance，不能无来源地合并成一条边。
- Registry 可能缺失、过期或经过平台过滤；它不能覆盖 export/object identity、解析状态或包内字节证据。
- 不调用 `GetMostImportantAsset` 一类便利选择来决定输出主对象；Registry 返回多个顶层资产时仍全部保留。
- 核心读取器在没有 Registry 时必须完整工作；Registry loader 属于可选批处理/索引 adapter。

### Property System

#### Tagged

`TaggedPropertyReader` 按 `FPropertyTag` 读取 name/type/size/array index/type metadata/value，value 必须在 tag 声明范围内完成。未消费 bytes 产生诊断并保留 region。

#### Unversioned

`UnversionedPropertyReader` 需要 `SchemaProvider`：

```python
class SchemaProvider(Protocol):
    def fields_for(self, class_path: str, context: VersionContext) -> Sequence[FieldSchema] | None: ...
```

Schema 可来自 `.usmap`、已加载 package、内置 UE 类型描述或调用方注入。没有 schema 时返回 opaque property region，不猜字段顺序。

#### 公共值模型

两种 reader 最终产生同一 `PropertyValue` 树：scalar、name、object ref、struct、array、set、map、optional、text、delegate 和 opaque。领域 handler 不直接重新读取 archive。

### Asset Handlers

handler 输入 `PackageDocument + ObjectRecord`，只在有证据时添加 `semantic`：

```python
class AssetHandler(Protocol):
    def supports(self, obj: ObjectRecord, context: VersionContext) -> bool: ...
    def enrich(self, package: PackageDocument, obj: ObjectRecord, request: DecodeRequest) -> SemanticExtension: ...
```

第一批只建立已有样本和成熟解析路径的 handler：DataTable/CurveTable/StringTable、Texture/Sound metadata、Skeleton/Mesh summary。Blueprint handler 迁移现有 graph/Pin/coverage 能力，但作为后续扩展，不反向污染 package core。

## Output Contract

### 顶层规则

目标公共格式固定为 `uasset_read.package`：

```json
{
  "format": "uasset_read.package",
  "format_version": "2.0",
  "view": "semantic",
  "depth": "asset",
  "source": {},
  "package": {},
  "objects": [],
  "relations": [],
  "dependencies": [],
  "payloads": [],
  "diagnostics": [],
  "summary": {}
}
```

领域数据只能出现在 `objects[].semantic`，不得提升到顶层。`objects` 表达全部 exports；imports 通过 `dependencies` 或 raw table 查询，不伪装成导出对象。

### 示例

```json
{
  "format": "uasset_read.package",
  "format_version": "2.0",
  "view": "semantic",
  "depth": "asset",
  "source": {
    "kind": "loose",
    "name": "BP_Light.uasset",
    "size": 32145
  },
  "package": {
    "name": "/Game/BP_Light",
    "layout": "legacy",
    "engine_version": "5.4.4",
    "package_flags": 16448
  },
  "objects": [
    {
      "id": "export:0",
      "name": "BP_Light",
      "class": "Blueprint",
      "roles": ["asset"],
      "status": {"parse": "complete", "semantic": "complete"},
      "semantic": {
        "kind": "blueprint",
        "graphs": [],
        "variables": [],
        "components": []
      },
      "coverage": []
    },
    {
      "id": "export:1",
      "name": "BP_Light_C",
      "class": "BlueprintGeneratedClass",
      "roles": ["generated_class"],
      "status": {"parse": "complete", "semantic": "partial"},
      "semantic": {
        "kind": "class",
        "defaults": {}
      }
    }
  ],
  "relations": [
    {
      "kind": "generated_class_of",
      "from": "export:1",
      "to": "export:0"
    }
  ],
  "dependencies": [],
  "payloads": [],
  "diagnostics": [],
  "summary": {
    "object_count": 2,
    "asset_object_ids": ["export:0"]
  }
}
```

### View 与 Depth

View 决定字段用途，Depth 决定解析成本：

| 参数 | 含义 |
| --- | --- |
| `view=semantic` | 默认；对象身份、关系、业务摘要、coverage 和必要诊断 |
| `view=raw` | Header/tables、flags、offsets、完整属性树和未知字段描述符 |
| `view=debug` | raw 加读取分支、offset evidence、恢复信息和解析统计 |
| `depth=package` | 只读 summary 与 tables，不解析对象 payload |
| `depth=object` | 解析请求对象的通用属性 |
| `depth=asset` | 运行轻量领域 handler |
| `depth=decode` | 运行显式请求的重型 graph/bytecode/media 解码 |

默认 `semantic + asset` 不包含完整 name map、所有 raw property、HexView 或 blob bytes。

### Selection 与 Pagination

所有 API 和 Agent tool 统一支持：

- `object_ids`
- `roles`
- `classes`
- `fields`
- `offset`
- `limit`
- `max_bytes`

排序固定使用 table index。截断必须返回 `next_offset` 和结构化 `TRUNCATED` 诊断，不能静默省略。

### Status

状态分层，不再用一个字段概括整个文档：

- package：`complete | partial | failed`
- object parse：`complete | partial | opaque | failed`
- object semantic：`complete | partial | unavailable | not_requested`
- payload：`available | external | missing | unsupported`

`coverage` 表达“预期语义中已输出多少”；它不能替代 parse status，也不能仅通过字段数量推导。

object semantic 的 `complete` 绑定到 handler 声明的能力层级（#629）：handler 声明 `summary` 或 `decoded`，只有 decoded 层级产出语义时才能记 `complete`；summary 层级（kind/name 回显、light digest，如 Niagara、mesh 概要、depth=asset 的 Blueprint 概要）一律 `partial`，coverage 条目照常输出。

### Diagnostics

```json
{
  "severity": "warning",
  "code": "PROPERTY_VALUE_REMAINDER",
  "message": "Property value left 8 unread bytes",
  "stage": "properties.tagged",
  "object_id": "export:3",
  "property_path": "Root.ComponentTemplate",
  "offset": 4096,
  "size": 8,
  "effect": "semantic_loss",
  "recoverable": true,
  "count": 1
}
```

必填：`severity/code/message/stage`。其余按证据提供。相同 code、对象、路径和效果可以聚合 count；不同 offset 的首次与末次位置要保留。

### Payloads

```json
{
  "id": "payload:0",
  "owner": "export:7",
  "kind": "texture_mip",
  "source_region": "ubulk",
  "offset": 1024,
  "stored_size": 65536,
  "logical_size": 262144,
  "compression": "oodle",
  "status": "unsupported",
  "hash": null
}
```

payload 提取使用单独 API/tool（当前恒返回 `PAYLOAD_EXTRACTION_DEFERRED`，`payloads[]` 为空数组）。JSON 默认不含 Base64。extraction 恢复后，调用方显式请求且 `max_bytes` 允许时才返回 bytes 或写入目标文件；`max_bytes` 须限制序列化后的工具响应整体（base64 + JSON envelope），而非仅原始 payload 字节。

### Schema 策略

- 一个 package envelope schema。
- `objects[].semantic.kind` 使用 discriminator 选择可选领域定义。
- 领域 schema 不能重新定义 package 公共字段。
- Schema 版本只在不兼容公共契约变化时升级。
- 当前 Semantic JSON 1.x 在迁移期仅作为 legacy output adapter；新功能不再新增 1.x 顶层 format。

## Multi-Asset Rules

1. 解析成功不依赖是否存在 `bIsAsset`。
2. 所有 exports 都进入 `objects`，除非调用方显式 selection。
3. `bIsAsset` 只增加 `asset` role。
4. 包名匹配只用于显示排序提示，不能删除其他对象。
5. GeneratedClass、CDO、组件模板和图对象通过 relations 连接。
6. 一个对象可拥有多个 role；一个包可拥有多个 asset object。
7. 某个对象失败只降低该对象和 package aggregate，不抹掉其他成功对象。

## Agent Tool Design

首批工具保持小而稳定：

| Tool | 返回 |
| --- | --- |
| `inspect_package` | source/package/summary/diagnostic 摘要 |
| `list_objects` | 分页对象身份、class、roles、status |
| `get_object` | 单对象属性与可选 semantic |
| `list_dependencies` | 分页依赖和关系 |
| `get_diagnostics` | 按 stage/severity/object 过滤 |
| `extract_payload` | 当前恒返回 `PAYLOAD_EXTRACTION_DEFERRED`；extraction 恢复后在大小上限内返回或写出指定 payload |

工具直接调用 Python document API，不通过 CLI 文本反序列化。MCP 只是 transport adapter；核心包不强制依赖 MCP SDK。

每个工具必须：

- 有明确最大响应 bytes。
- 支持分页或 selection。
- 返回稳定 id。
- 区分 `not_requested` 与 `unavailable`。
- 不在错误信息中泄漏无关绝对路径或密钥。

## Logging and Debugging

### 库层

- parser/reader 只产生 `Diagnostic`。
- 默认不创建日志文件，不修改 root logger，不安装全局 handler。
- 可接受调用方注入的 event sink，用于实时进度，不用于保存真值。

### CLI 层

- `--verbose` 控制 stderr 展示。
- `--log-file` 或 `--log-dir` 显式启用文件日志。
- 一次 CLI invocation 只有一个 run id 和一个日志生命周期。
- batch worker 把 diagnostics 返回父进程，由父进程决定输出。
- 日志清理只处理明确日志目录，默认 dry-run 预览后再删除。

### Debug 输出

debug view 是结构化事实，不是日志镜像。它包含 reader 分支、range、offset、fallback 和统计，不包含重复的自然语言 trace。

## Cross-Platform and Dependencies

- 所有核心路径使用 `pathlib.Path`，输出 package path 统一使用 `/`。
- 测试不得依赖固定盘符或用户目录。
- 核心格式、JSON、压缩中的 zlib/lzma 使用标准库优先。
- AES、Zstd、LZ4、Oodle、MCP 等放在明确 capability 边界；缺失时返回 `unsupported`，不让导入核心包失败。
- 不再把“零依赖”当作不可改变的产品目标；新增 mandatory dependency 必须证明它减少了更多自维护代码，并通过跨平台 CI。
- 发行包不包含 `external/`、`.codegraph/`、Agent 缓存、日志、临时报告或真实商业资产。

## Repository Size and Documentation Policy

### 代码体积

- 先迁移公共读取路径，再删除旧 Semantic builder/projection/validator 和重复 renderer。
- Blueprint 与 AnimBlueprint 共享 graph、node、pin、coverage 模型，避免复制 extractor 基础设施。
- 不为单一实现建立 interface/factory；出现第二个真实实现再抽象。
- 外部参考项目不 vendoring 到发行包；只保留来源、版本和用途清单。

### 文档体积

- 本文是唯一目标架构。
- `docs/formats/` 记录二进制事实，不负责产品路线。
- `docs/designs/` 只保留活动目标和 Issue 证据；仓库级历史方案移动到 `docs/designs/archive/`，并标注归档状态。
- `wiki/` 描述当前可用行为；目标功能只能链接本文并标注未实现。
- README 同时展示 current stable 与 target refactor，禁止把后者写进 Features。
- Agent 指令必须要求先查源码，再查本文，不得从历史设计推断实现状态。

## Migration Plan

### Phase 0：冻结证据与契约

交付：

- 真实样本 manifest，记录 hash、来源类别、engine、layout 和 sidecars。
- 当前输出 golden 仅用于识别回归，不作为新 Schema 约束。
- `PackageDocument` v2 schema 与示例。
- current/target 文档分离完成。
- 在同一变更中删除旧 `tests/**/*.py`、已跟踪测试缓存和计时 benchmark，并立即建立可全绿的 v2 契约测试；不提交“先删测试、以后再补”的中间状态。
- 保留全部 47 个真实二进制样本及来源说明，逐项校验 manifest 中的 SHA-256 与大小；样本不得因重写测试而删除或替换。
- 迁移当前有效的 PackageDocument、projection 和 Agent tool 断言，不把并发中的 v2 Agent 契约随旧测试清空。
- 删除根目录 `run.py` 与 `extract_function_pins.py`，统一入口为 `python -m uasset_read`；Pin 提取能力待 Blueprint v2 扩展重新设计。

退出条件：旧 Python 测试模块和根目录独立脚本归零；新基础套件在当前本机 Windows + Python 3.14 全绿；47 个样本的 hash/size 全部匹配；多资产、无唯一主资产、classic、IoStore/Zen、tagged、unversioned、payload sidecar 均有明确 fixture 或 manifest gap。

### Phase 与测试同步规则

- Phase 0 一次性移除旧测试体系；之后每个实现 Phase 只增加该阶段已经实现且具有证据的最小严格测试。
- 不为缺少 fixture 的目标能力预提交 `skip`、`xfail` 或长期红测；缺口写入 manifest，取得样本并实现后再收集测试。
- 每个 Phase 的源码、测试、manifest 和文档状态在同一验收边界内交付，不保留永久双测试体系。
- 允许为新契约通过修复最少量生产源码，但不得借测试重构实现无真实证据的格式分支。

### Phase 1：Reader 与 Legacy PackageDocument

交付：

- `Source.read_at()` 与 `SliceReader`。
- `VersionContext`。
- 经典 package tables 映射到 `PackageDocument`。
- `objects[]` 包含所有 exports。
- 新 Python API 返回 document，不返回字符串。

退出条件：现有经典样本的 header/import/export 数量与旧 pipeline 一致；多资产包不再输出 `NO_EXPORTS`。

### Phase 2：Properties 与 Unknown Preservation

交付：

- Tagged reader 迁移。
- Unversioned reader + SchemaProvider。
- property range diagnostics。
- opaque property/payload descriptor。

退出条件：已支持属性 round-trip 到值模型；未知属性不会导致后续 export 丢失；每个 value reader 都受 slice 限制。

### Phase 3：Output、CLI 与 Agent

交付：

- semantic/raw/debug projection。
- depth、selection、pagination、max_bytes。
- 六个基础 Agent tools。
- 单一日志生命周期。

退出条件：CLI、Python API 和 Agent 对同一 document 的 object id/status/diagnostic 一致；默认输出不含 blob。

### Phase 4：Asset Handlers

交付顺序：

1. Data/manifest assets。
2. Texture/Sound metadata 与 payload descriptors。
3. Skeleton/Mesh summary。
4. Material/Niagara graph summary。
5. Blueprint/AnimBlueprint/Kismet/C++ 扩展迁移。

    - Phase 4.5：graph/node/pin 解码 + declaration（parent_class/interfaces/functions）+ SCS components + NewVariables names 已迁移到 v2 `BlueprintFamilyHandler` decode 分支。fixture 测试覆盖 StackOBot/BP_CombatCharacter/ABP_RifleAnimLayers/ALS_AnimBP。
    - 未迁移：VarType 类型解码、Kismet 反编译、C++ skeleton、parent-asset 解析（属 D1 deferred）。

退出条件：每个 handler 至少有一个真实样本、一个缺失/partial 样本和明确 coverage；handler 失败不影响同包其他对象。

### Phase 5：Zen 与 Container Streaming

交付：

- `ZenPackageReader`。
- IoStore chunk range source。
- compression/encryption capability reporting。
- package trailer 和 external payload 路由。

退出条件：真实 `.utoc/.ucas` fixture 可列出 package objects；读取单对象不会把整个容器复制到内存。

### Phase 6：删除旧路径

仅在调用方迁移完成后删除：

- `_select_primary_export()` 驱动的公共输出。
- `SemanticIR` 顶层领域 format 家族。
- content 顶层 promotion。
- 重复的 JSON renderer/schema registry。
- parser 内部日志配置。
- 已被新 core 覆盖的 compatibility shim。

不保留双实现永久同步。

## Testing Strategy

### 证据顺序

测试结论按以下顺序约束，低层证据不得覆盖高层证据：

1. Unreal Engine 源码中的序列化分支和版本条件。
2. 真实 fixture 的 SHA-256、大小、版本、layout、sidecar 与 manifest 结构断言。
3. `PackageDocument`、对象关系、状态和 structured diagnostics。
4. Python API、CLI 与 Agent 投影一致性。
5. 文本日志只验证开关、单次生命周期和副作用，不作为内容 golden。

### 测试层级

- Reader unit：边界、endianness、count、overflow、slice。
- Package contract：table 数量、index、relation、status 聚合。
- Property contract：tagged/unversioned/unknown。
- Real sample：按 layout 和资产族参数化。
- Container integration：Pak/IoStore range 读取。
- Output schema：同一 document 的不同 view/depth。
- Agent contract：分页、max_bytes、稳定 id、错误边界。

### 测试组织约束

- 真实样本支持声明必须来自 manifest 驱动的参数化测试；缺文件或 hash 不匹配直接失败，不在测试内 `skip`。
- aggregate/sample 测试不得捕获宽泛 `Exception` 后继续；失败必须保留样本名、stage、object 和 diagnostic code。
- 不用 `MagicMock` 伪造 UE package/export/property 结构；Reader 边界使用受控 bytes，端到端行为使用真实样本。Mock 只允许隔离文件流、时钟或进程边界。
- manifest 不能由测试自动改写。新增或修改预期值必须先核对样本与 UE 源码，再由评审确认。
- 不提交墙钟耗时阈值。性能门禁只使用确定性的 bytes、count、range、pagination 和 resource budget。
- 测试代码只放在 `tests/`；根目录和 `scripts/` 不增加独立验证程序。一次性调查使用命令行或未跟踪的 `temp/` 输出。
- 标准库 AST 门禁要求：
  - `tests/` 根目录的正式 Python 测试文件集合由 `tests/test_core.py::test_test_suite_structure_gate` 锁定，当前为四个：`test_core.py`（核心单元与结构门禁）、`test_samples.py`（manifest 驱动的真实样本）、`test_blueprint_decode.py`、`test_blueprint_graph.py`。新增第五个文件必须同时修改该门禁并说明为何不能归入现有文件；唯一允许的永久子目录仍为 `tests/samples/`。
  - `test_core.py` 只能使用顶层 `test_*` 函数；拒绝测试类、参数化 decorator、动态 `test_*` 赋值，从而使 AST 数量等于 pytest 收集项。
  - 核心测试收集项不得超过 10；样本参数项不设上限。
- pytest cache、`__pycache__`、日志、golden 调试转储和本机路径不得进入版本控制。

### 必须存在的回归

- 两个或更多 `bIsAsset` 导出仍完整输出。
- 无资产 role 但有 exports 的 package 不失败。
- 一个 export 失败时其他 objects 保留。
- standard 输出不含 evidence/raw bytes。
- debug 输出能定位 offset/stage/object。
- disabled logging 不创建文件、不向 root logger 泄漏。
- malformed count/offset 不进行超大分配或越界 seek。
- 缺少 optional codec 时 package metadata 仍可检查。

### 验证原则

测试通过只能证明当前测试覆盖的行为。任何“支持某 UE 版本/资产类型”的声明必须同时有：

- UE 源码分支证据。
- 真实 fixture。
- 结构断言，而不是仅检查命令退出 0。
- partial/unsupported 的诚实状态。

当前重构阶段的唯一阻断环境是本机 Windows + Python 3.14，标准命令为 `python -m pytest -q`。GitHub CI 只运行非阻塞的 fast-suite smoke job（`python -m pytest -q`，无墙钟阈值）作为回归证据；阻断性全量门禁仍是本机 Windows + Python 3.14。Linux/3.12 结果不得被描述为已验证环境。coverage 与 Codecov 仍暂停。Linux、macOS 和其他 Python 版本暂缓验证；源码仍遵守跨平台约束，但文档和发布说明不得宣称这些环境已通过测试。

## Acceptance Gates

### Core v2 Gate

- 一个 package document 表达所有 exports。
- Legacy package 读取不依赖 Semantic 1.x。
- VersionContext 字段集中且不可变。
- Tagged/Unversioned 在入口处分离。
- 所有读取受 range 和 count 限制。
- diagnostics 包含 stage，并可关联 object/offset。
- Python API 返回 document；JSON 是纯投影。
- 当前本机 Windows + Python 3.14 的完整新套件通过且无非预期 skip/xfail。
- Linux、macOS 和其他 Python 版本保留为 deferred，不作为当前 Gate，也不得被描述为已验证。

### Output v2 Gate

- 唯一顶层 format：`uasset_read.package`。
- semantic/raw/debug 与 depth 正交。
- 多资产、GeneratedClass、CDO 关系可表达。
- 默认输出无 blob、无完整 HexView、无无界数组。
- 所有截断可发现并可继续分页。
- schema 与示例由同一模型生成或严格验证。

### Agent Gate

- 六个工具共享 Python API。
- 工具调用可限定对象、字段、条数和 bytes。
- 错误为结构化 diagnostics，不返回日志堆栈作为正常数据。
- MCP adapter 缺失不影响核心库导入和 CLI。

### Migration Completion Gate

- 旧 Semantic 1.x 不再是默认 JSON。
- 所有公开文档只把旧契约描述为 legacy/current historical。
- Blueprint/Kismet 扩展在 v2 object model 上运行，或明确保留为未迁移可选能力。
- 旧 builder/projection/promotion 路径已删除，而不是永久并行。
- 发行包、源码树和文档树的体积基线已记录并进入 CI/发布检查。
- 根目录独立 Python 入口已删除，公开命令统一为 `python -m uasset_read`。
- 旧测试脚本、计时 benchmark、测试缓存和调试日志未残留在版本控制中。

## Risks and Controls

| 风险 | 控制 |
| --- | --- |
| 把 UE5 都当 Zen | 独立 layout detector + 真实 container metadata |
| 一次性重写导致样本能力回退 | 原地纵向迁移，按 phase 保留旧 reader 作为对照 |
| v2 输出无限膨胀 | view/depth/selection/pagination/max_bytes |
| 领域 handler 再次侵入 core | handler 只消费 document/object，不读取全局 archive |
| Unknown 数据静默丢失 | opaque region + diagnostic + payload descriptor |
| optional codec 破坏跨平台安装 | capability boundary，缺失时 metadata-only |
| 把 Zen Storage Server 当成 Zen package 格式 | 按源码模块和符号分名；服务端只作为 Source capability |
| Asset Registry 缺失或陈旧污染解析结果 | Registry 仅作带 provenance 的可选 enrich/index，不覆盖 package evidence |
| 文档提前宣布功能完成 | current/target 标记、源码优先、验收 gate |
| 历史文档继续被检索误用 | 顶部 superseded banner + 统一 design index |

## Decisions

- 采用原地 package-first 重构，不创建 clean-room 新项目。
- 使用一个 canonical `PackageDocument`，不再扩展顶层 domain format 家族。
- 不选择唯一主资产；所有 exports 是一等对象。
- Legacy 与 Zen 使用独立 reader。
- Tagged 与 Unversioned 使用独立 property reader。
- Writer 延后，第一阶段保持只读。
- Blueprint/Kismet/C++ 生成保留为可选扩展，后于 core v2。
- Agent tool 是正式接口；MCP 是可选 transport。
- 默认不写文件日志，不内嵌大型 payload。
- 最小依赖优先，但不把零依赖作为不可改变的架构限制。
- Phase 0 原子删除并重建测试体系；后续测试与实现 Phase 同步增长，不保留旧/新双套测试。
- 当前只以本机 Windows + Python 3.14 作为测试阻断环境；其他系统和 Python 版本暂缓且不得宣称已验证。
- CI keeps one non-blocking fast-suite smoke job as regression evidence; the blocking full gate remains local Windows + Python 3.14.
- 真实样本与 structured diagnostics 是测试基准；文本日志不是 golden。
- 禁止新增根目录独立验证脚本；可复用能力进入包内 API、CLI 或 Agent tool。

## Source Pointers

当前实现的重要入口：

- `src/uasset_read/core/__init__.py`
- `src/uasset_read/semantic/builder.py`
- `src/uasset_read/semantic/models.py`
- `src/uasset_read/semantic/render.py`
- `src/uasset_read/package.py`
- `src/uasset_read/versioning.py`
- `src/uasset_read/project_logging.py`

UE 源码核验入口使用相对于 Unreal Engine checkout 的路径：

- `Engine/Source/Runtime/CoreUObject/Public/UObject/PackageFileSummary.h`
- `Engine/Source/Runtime/CoreUObject/Public/UObject/ObjectResource.h`
- `Engine/Source/Runtime/CoreUObject/Public/UObject/PropertyTag.h`
- `Engine/Source/Runtime/CoreUObject/Public/Serialization/PackageTrailer.h`
- `Engine/Source/Runtime/CoreUObject/Public/Serialization/AsyncLoading2.h`
- `Engine/Source/Runtime/CoreUObject/Internal/Serialization/ZenPackageHeader.h`
- `Engine/Source/Runtime/Core/Public/IO/IoDispatcher.h`
- `Engine/Source/Runtime/Core/Internal/IO/IoStore.h`
- `Engine/Source/Runtime/AssetRegistry/Public/AssetRegistry/AssetRegistryState.h`
- `Engine/Source/Runtime/AssetRegistry/Public/AssetRegistry/IAssetRegistry.h`
- `Engine/Source/Runtime/CoreUObject/Public/AssetRegistry/AssetData.h`
- `Engine/Source/Developer/Zen/`
- `Engine/Source/Runtime/StorageServerClient/`

不在仓库文档中固定本机 UE 源码绝对路径；开发环境通过环境变量、项目配置或用户提供路径定位 checkout。
