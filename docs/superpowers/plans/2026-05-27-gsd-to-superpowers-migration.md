# GSD → Superpowers 迁移实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将项目从 GSD phase-based 规划体系迁移到 Superpowers specs + plans 工作流，保留有价值的历史记录，删除所有 GSD 专用文件。

**Architecture:** 先为 4 个活跃 Phase（76-80）创建 Superpowers spec 文档，然后更新 CLAUDE.md 和 DEVELOPMENT.md/CONTRIBUTING.md 中的 GSD 引用，最后删除 GSD 专用文件。每步独立可验证。

**Tech Stack:** Python 3.10+, Git, Markdown

---

### Task 1: 创建 Phase 76 Spec — FArchive COR Fixes

**Files:**
- Create: `docs/superpowers/specs/2026-05-27-farchive-cor-fixes-design.md`

**Background:** Phase 76 是 v14.0 当前活跃的 Phase。核心工作是 VersionContainer 集成和 StructProperty fast-path/fallback 边界收口。来源：`.planning/phases/phase-76/76-01-PLAN.md` 和 `76-RESEARCH.md`。

- [ ] **Step 1: 创建 Phase 76 Spec**

写入 `docs/superpowers/specs/2026-05-27-farchive-cor-fixes-design.md`：

```markdown
# FArchive COR Fixes — VersionContainer 集成 + StructProperty 边界

## 背景

Phase 76 不是"未开始"而是"部分实现、未收口"。`VersionContainer`、`build_version_container()`、`EUEVersion` 已实现，`parse_uasset()` 已挂接 `version_container`，但关键读取路径仍使用硬编码的 `summary.file_version_ue5` 和 `summary.get_custom_version()`。

## 目标

1. VersionContainer 从结果对象升级为序列化决策基础设施
2. 4 个关键路径的版本判断统一收敛
3. StructProperty fast-path 增加 `tag.size` 校验
4. 修复 Phase 75 回归测试红灯

## 架构

给 `PackageFileSummary` 添加可选 `version_container: Optional[VersionContainer]` 字段。关键路径优先使用 `summary.version_container`，若无则回退到旧的 `summary.file_version_ue5` 检查。

StructProperty fast-path 在读取前校验 `tag.size` 是否匹配预期布局大小，不匹配时回退到 PropertyTag loop。

## 关键路径版本判断审计

| File | Line | 当前用法 | 迁移策略 |
|------|------|---------|---------|
| `parsers/property_parser.py` | 133,140,148 | `summary.file_version_ue5 >= threshold` | `version_container.is_at_least(threshold)` |
| `serializers/graph.py` | 165-166 | `summary.get_custom_version(GUID, 0)` | `version_container.get_version(GUID)` |
| `serializers/graph.py` | 1688 | `summary.file_version_ue5 >= 1011` (硬编码) | `version_container.is_at_least(1011)` |
| `kismet/bytecode_extractor.py` | 96,104 | `summary.file_version_ue5 >= threshold` | 同上 |
| `kismet/bpgc_bytecode.py` | 132,140 | `summary.file_version_ue5 >= threshold` | 同上 |

**不需要迁移的点：**
- `serializers/package_summary.py` — 这里是值被 SET 的地方
- `formatters/` — 仅用于输出展示

## StructProperty Fast-Path 增强

为所有 fast-path struct 增加 `tag.size` 预期值校验：

```python
_EXPECTED_STRUCT_SIZES = {
    "Vector": 12, "Rotator": 12, "Vector2D": 8, "Vector4": 16,
    "LinearColor": 16, "Color": 4, "Quat": 16, "Plane": 16,
    "Guid": 16, "IntPoint": 8, "IntVector": 12,
    "Box2D": 20, "Box": 28, "Sphere": 16, "BoxSphereBounds": 40,
    "Matrix": 64, "TwoVectors": 24, "OrientedBox": 60,
    "Transform": 48,
}
```

当 `tag.size != expected` 时，不走快径，回退到 PropertyTag loop。

## BodyInstance 策略

**不添加 BodyInstance fast-path。** CUE4Parse 本身只有游戏特定的 BodyInstance 处理（ConanExilesEnhanced），对通用情况使用 `FStructFallback`。BodyInstance 是 30+ 字段的复杂结构体，版本依赖性强，无稳定测试样本。

## 关键文件

- `src/uasset_read/versioning.py` — 版本查询 API
- `src/uasset_read/serializers/package_summary.py` — 添加 version_container 字段
- `src/uasset_read/parsers/property_parser.py` — 版本判断收敛
- `src/uasset_read/serializers/graph.py` — CustomVersion 查询收敛
- `src/uasset_read/parsers/property_types.py` — StructProperty tag.size 校验
- `src/uasset_read/kismet/bytecode_extractor.py` — 版本判断收敛
- `src/uasset_read/kismet/bpgc_bytecode.py` — 版本判断收敛

## 测试

- `tests/test_versioning.py` — 版本查询行为测试
- `tests/test_struct_property.py` — tag.size mismatch / fallback / recovery 测试
- `tests/test_phase75_event_node_field_alignment.py` — 回归修复

## 验收标准

- 至少 2 个关键读取函数使用 VersionContainer 或统一封装
- `tests/test_struct_property.py` 通过 + 至少 3 个新边界测试
- 全量测试绿灯（或无关失败已记录）
```

- [ ] **Step 2: 验证 Spec 文件存在**

```bash
ls docs/superpowers/specs/2026-05-27-farchive-cor-fixes-design.md
```

Expected: 文件存在且内容完整。

- [ ] **Step 3: 提交**

```bash
git add docs/superpowers/specs/2026-05-27-farchive-cor-fixes-design.md
git commit -m "chore: add Phase 76 FArchive COR fixes spec (Superpowers migration)"
```

---

### Task 2: 创建 Phase 78 Spec — UObject 继承 + Linker 重构

**Files:**
- Create: `docs/superpowers/specs/2026-05-27-uobject-inheritance-linker-design.md`

**Background:** Phase 78 有 3 个子计划（78-01/02/03），涵盖 UObject 反射层次、Archive 隔离、Provider 接口。来源：`.planning/phases/phase-78/INDEX.md` + 三个 PLAN 文件。

- [ ] **Step 1: 创建 Phase 78 Spec**

写入 `docs/superpowers/specs/2026-05-27-uobject-inheritance-linker-design.md`：

```markdown
# UObject 继承 + Linker 重构 — CUE4Parse 架构收敛

## 背景

当前 linker 体系是"本包对象壳 + 局部 preload"，需要推进到更接近 CUE4Parse 的 Package-centered + lazy + provider-aware 架构。

## 架构

分 3 个 wave 执行，顺序不可颠倒：

### Wave 1: 反射层次 + SuperField 链

**新建 `src/uasset_read/models/uobject.py`：**

UObject → UField → UEnum/UStruct/UClass/UFunction 反射层次模型。

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List

class UObjectCategory(Enum):
    UObject = "UObject"
    UField = "UField"
    UEnum = "UEnum"
    UStruct = "UStruct"
    UClass = "UClass"
    UFunction = "UFunction"
    Unknown = "Unknown"

@dataclass
class UObjectBase:
    name: str
    category: UObjectCategory = UObjectCategory.Unknown
    super_field_name: Optional[str] = None
    class_package: Optional[str] = None

    def is_field(self) -> bool:
        return self.category in (
            UObjectCategory.UField, UObjectCategory.UEnum,
            UObjectCategory.UStruct, UObjectCategory.UClass,
            UObjectCategory.UFunction,
        )

@dataclass
class UField(UObjectBase):
    category: UObjectCategory = UObjectCategory.UField

@dataclass
class UEnum(UField):
    category: UObjectCategory = UObjectCategory.UEnum
    enum_values: List[str] = None

@dataclass
class UStruct(UField):
    category: UObjectCategory = UObjectCategory.UStruct
    children: List[str] = None

@dataclass
class UClass(UStruct):
    category: UObjectCategory = UObjectCategory.UClass

@dataclass
class UFunction(UStruct):
    category: UObjectCategory = UObjectCategory.UFunction
```

导出类标签分类：

```python
class ExportClassTag(Enum):
    Unknown = "Unknown"
    Graph = "Graph"
    GraphNode = "GraphNode"
    GraphPin = "GraphPin"
    BlueprintClass = "BlueprintClass"
    Component = "Component"
    Actor = "Actor"

def get_reflection_category(class_name: str) -> UObjectCategory: ...
def get_export_class_tag(class_name: str) -> ExportClassTag: ...
```

**修改 `src/uasset_read/link/linker.py`：**

- `build_super_tree()` — 在 `link()` 中解析 SuperIndex → UObjectInstance
- `resolve_class_ref(export_index)` — 返回 class UObjectInstance
- `resolve_template_ref(export_index)` — 返回 template UObjectInstance
- `link()` 增加 `build_super_tree()` 调用

**修改 `src/uasset_read/link/object_instance.py`：**

- 新增 `super: Optional["UObjectInstance"] = None` 字段
- 新增 `get_super_field_chain()` 方法（20 层深度限制）
- 新增 `reflection_category` 和 `export_class_tag` 属性

### Wave 2: 独立 Archive + 生命周期 + 位置安全 preload

- 每个 `PackageLinker` 拥有独立的 `_archive` 引用
- `LinkerParseResult` 管理 archive 生命周期（不在函数返回前关闭）
- `preload()` 使用 save/restore 模式，不污染 archive 位置
- 连续 `parse_uasset(file_A)` + `parse_uasset(file_B)` 无缓存串扰

### Wave 3: Provider 接口 + Graph 单一路径

- `PackageLinker` 增加 provider/resolver 边界
- graph/blueprint/pin 解析统一走 linker-aware 主路径
- `/Script/` import 明确采用占位符策略
- 为 Phase 79 IoStore 建立不返工的接口面

## 关键文件

- `src/uasset_read/models/uobject.py` — 新建，反射层次模型
- `src/uasset_read/link/linker.py` — SuperField 链 + class/template 引用
- `src/uasset_read/link/object_instance.py` — super 字段 + 分类属性
- `src/uasset_read/link/result.py` — LinkerParseResult 生命周期
- `src/uasset_read/parse_uasset.py` — 独立 archive 创建

## 测试

- `tests/test_uobject_hierarchy.py` — 反射层次分类测试
- `tests/test_superfield_chain.py` — SuperField chain 解析测试
- `tests/test_linker_class_template.py` — class_ref / template_ref 测试
- `tests/test_linker_isolation.py` — 缓存串扰隔离测试
- `tests/test_linker_lazy_preload.py` — lazy preload 测试

## 验收标准

- BPGC SuperField chain 返回 3+ 层深度
- 连续 parse_uasset 无缓存串扰
- `/Script/` import 保持占位符，不引入真实脚本包加载
- link() 包含 build_super_tree() 调用
```

- [ ] **Step 2: 验证 Spec 文件存在**

```bash
ls docs/superpowers/specs/2026-05-27-uobject-inheritance-linker-design.md
```

Expected: 文件存在且内容完整。

- [ ] **Step 3: 提交**

```bash
git add docs/superpowers/specs/2026-05-27-uobject-inheritance-linker-design.md
git commit -m "chore: add Phase 78 UObject inheritance linker spec (Superpowers migration)"
```

---

### Task 3: 创建 Phase 79 + 80 Specs

**Files:**
- Create: `docs/superpowers/specs/2026-05-27-iostore-utoc-ucas-design.md`
- Create: `docs/superpowers/specs/2026-05-27-pascalcase-output-format-design.md`

**Background:** Phase 79 (IoStore) 和 Phase 80 (PascalCase 输出) 目前只有 `ROADMAP.md` 中的简要描述，研究内容较少。Spec 内容较短但结构完整。

- [ ] **Step 1: 创建 Phase 79 Spec**

写入 `docs/superpowers/specs/2026-05-27-iostore-utoc-ucas-design.md`：

```markdown
# IoStore .utoc/.ucas 解析

## 背景

Phase 79 为 v14.0 CUE4Parse 核心对齐的一部分，实现 UE IoStore 格式的文件解析支持。

## 目标

1. FIoStoreTocResource 解析（Chunk ID 表、偏移量、压缩块信息）
2. .ucas 数据段提取
3. DefaultFileProvider 路径扫描
4. 解析 .utoc/.ucas 对，提取有效 Container 条目

## 架构

新建 `io_store/` 和 `file_provider/` 模块目录。IoStore 解析依赖 Phase 78 建立的 Provider 接口边界。

关键组件：
- `io_store/toc_parser.py` — FIoStoreTocResource 解析
- `io_store/ucas_reader.py` — .ucas 数据段读取
- `file_provider/default_provider.py` — DefaultFileProvider 路径扫描

## 验收标准

- 解析 .utoc/.ucas 对，提取有效 Container 条目
- 压缩块信息正确分派到 Zlib/LZ4/Zstd/Oodle
- Phase 78 Provider 接口已就绪后再执行
```

- [ ] **Step 2: 创建 Phase 80 Spec**

写入 `docs/superpowers/specs/2026-05-27-pascalcase-output-format-design.md`：

```markdown
# 输出格式 PascalCase 对齐

## 背景

Phase 80 将 JSON/Text 输出格式与 CUE4Parse 字段名一一对齐，消除 snake_case 残留。

## 目标

1. `format_json_cue4parse()` — PascalCase 字段名、ExportTypes 结构
2. `format_text_full()` 重构 — dict→统一文本渲染
3. BlueprintText 统一到 Schema
4. JSON 输出与 CUE4Parse 字段名一一对应

## 架构

修改现有 formatter 模块，在 snake_case 输出旁增加 PascalCase 输出函数，逐步迁移默认行为。

关键文件：
- `src/uasset_read/formatters/json_formatter.py` — 新增 `format_json_cue4parse()`
- `src/uasset_read/formatters/text_formatter.py` — 重构 `format_text_full()`

## 验收标准

- JSON 输出与 CUE4Parse 字段名一一对应
- 无 snake_case 残留
- 向后兼容：旧格式函数仍可用
```

- [ ] **Step 3: 验证两个 Spec 文件存在**

```bash
ls docs/superpowers/specs/2026-05-27-iostore-utoc-ucas-design.md
ls docs/superpowers/specs/2026-05-27-pascalcase-output-format-design.md
```

Expected: 两个文件均存在。

- [ ] **Step 4: 提交**

```bash
git add docs/superpowers/specs/2026-05-27-iostore-utoc-ucas-design.md docs/superpowers/specs/2026-05-27-pascalcase-output-format-design.md
git commit -m "chore: add Phase 79/80 IoStore and PascalCase specs (Superpowers migration)"
```

---

### Task 4: 更新 CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

**Background:** CLAUDE.md 包含 "gsd-sdk 使用"、"规划文档"、"上下文与效率" 中的 GSD 引用，需要更新为 Superpowers。

- [ ] **Step 1: 更新当前状态行**

将第 25 行的"当前状态"从：

```markdown
**v14.0 活跃** — CUE4Parse 核心对齐：Phase 74✅ 75✅ (v13.0 遗留)，Phase 77✅ (Pak parser + compression + AES, 62 tests)，Phase 76⬜ (FArchive + COR 修复，下一个)，Phase 78⬜ (UObject 继承树 + Linker 重构)，Phase 79⬜ (IoStore .utoc/.ucas)，Phase 80⬜ (Kismet 输出格式 PascalCase 对齐)。索引驱动模式，UE 源码为权威金标准。
```

改为：

```markdown
**v14.0 活跃** — CUE4Parse 核心对齐：Phase 74✅ 75✅ (v13.0 遗留)，Phase 77✅ (Pak parser + compression + AES, 62 tests)，Phase 76⬜ (FArchive + COR 修复，下一个)，Phase 78⬜ (UObject 继承树 + Linker 重构)，Phase 79⬜ (IoStore .utoc/.ucas)，Phase 80⬜ (Kismet 输出格式 PascalCase 对齐)。索引驱动模式，UE 源码为权威金标准。规划体系已从 GSD 迁移至 Superpowers specs。
```

- [ ] **Step 2: 替换 "gsd-sdk 使用" 章节**

将第 68-72 行（`## gsd-sdk 使用` 整个章节）替换为：

```markdown
## Superpowers 工作流

本项目使用 Superpowers 进行规划和执行。Spec 文档位于 `docs/superpowers/specs/`，实施计划位于 `docs/superpowers/plans/`。

规划历史（v1.0-v13.0）已归档至 `.planning/archive/`，详见 `.planning/MILESTONES.md`。
```

- [ ] **Step 3: 更新 "规划文档" 章节**

将第 95-100 行从：

```markdown
## 规划文档

- `.planning/ROADMAP.md` — 阶段路线图
- `.planning/STATE.md` — 当前里程碑状态
- `.planning/milestones/` — 已归档里程碑（v7.0-v12.0）
- `.planning/MILESTONES.md` — 历史里程碑
```

改为：

```markdown
## 规划文档

- `docs/superpowers/specs/` — 当前活跃的设计文档（Superpowers specs）
- `docs/superpowers/plans/` — 实施计划（由 writing-plans 技能生成）
- `.planning/milestones/` — 已归档里程碑（v7.0-v12.0）
- `.planning/MILESTONES.md` — 历史里程碑
- `.planning/archive/` — v1.0-v13.0 历史归档
```

- [ ] **Step 4: 更新 "上下文与效率" 章节**

将第 110-115 行从：

```markdown
## 上下文与效率

- 上下文 >70% 时执行 `compact`
- 独立任务优先并行 subagent，主线程只看结构化摘要
- **GSD：** wave 或 PLAN 之间互补不干扰时均可并行执行
- 有依赖或共享状态的任务不可并行；写冲突风险可通过 git 分支管理规避
```

改为：

```markdown
## 上下文与效率

- 上下文 >70% 时执行 `compact`
- 独立任务优先并行 subagent，主线程只看结构化摘要
- 独立 spec/plan 之间互补不干扰时均可并行执行
- 有依赖或共享状态的任务不可并行；写冲突风险可通过 git 分支管理规避
```

- [ ] **Step 5: 验证 CLAUDE.md 无残留 GSD 引用**

```bash
grep -i "gsd" CLAUDE.md
```

Expected: 无匹配结果。

- [ ] **Step 6: 提交**

```bash
git add CLAUDE.md
git commit -m "chore: update CLAUDE.md for Superpowers migration (remove GSD references)"
```

---

### Task 5: 更新 DEVELOPMENT.md

**Files:**
- Modify: `docs/DEVELOPMENT.md`

**Background:** DEVELOPMENT.md 第 63 行引用 `.planning/` 目录，第 242-273 行是整个 "GSD 工作流" 章节，第 312-327 行是 "gsd-sdk 使用" 章节，均需删除或更新。

- [ ] **Step 1: 更新项目结构中的 .planning 描述**

将第 63 行从：

```markdown
├── .planning/              # GSD 规划文档（ROADMAP/STATE/REQUIREMENTS 等）
```

改为：

```markdown
├── .planning/              # 规划历史归档（v1.0-v13.0，MILESTONES.md 仍有效）
├── docs/superpowers/       # 当前规划（specs + plans，Superpowers 工作流）
```

- [ ] **Step 2: 删除 "GSD 工作流" 章节（第 242-273 行）**

删除整个 `## 6. GSD 工作流` 章节（从 `## 6. GSD 工作流` 到 `## 7. 分支策略` 之前）。

替换为：

```markdown
## 6. Superpowers 工作流

本项目使用 Superpowers 进行规划和执行。

### Specs + Plans

Spec 文档位于 `docs/superpowers/specs/`，描述"做什么"和"为什么"。
实施计划位于 `docs/superpowers/plans/`，描述"怎么做"（由 writing-plans 技能生成）。

### 规划历史

v1.0-v13.0 的 GSD Phase 规划已归档至 `.planning/archive/`。
```

- [ ] **Step 3: 删除 "gsd-sdk 使用" 章节（第 312-327 行）**

删除整个 `## 8. gsd-sdk 使用` 章节。章节编号重新编排（原 9→8，原节编号顺延）。

- [ ] **Step 4: 验证无残留 GSD 引用**

```bash
grep -i "gsd" docs/DEVELOPMENT.md
```

Expected: 无匹配结果（或仅有历史上下文中的引用）。

- [ ] **Step 5: 提交**

```bash
git add docs/DEVELOPMENT.md
git commit -m "chore: update DEVELOPMENT.md for Superpowers migration (remove GSD workflow)"
```

---

### Task 6: 更新 CONTRIBUTING.md

**Files:**
- Modify: `docs/CONTRIBUTING.md`

**Background:** CONTRIBUTING.md 第 140-149 行是 "GSD 工作流阶段" 章节，第 156 行引用 `.planning/` 目录作为活跃规划。

- [ ] **Step 1: 替换 "GSD 工作流阶段" 章节**

将第 140-149 行从：

```markdown
## GSD 工作流阶段

本项目采用 GSD（Goal-Driven Software Development）工作流，将开发分解为多个 Phase。了解 Phase 状态有助于避免重复工作：

- **规划文件**：所有 Phase 的规划文档位于 `.planning/` 目录。
- **ROADMAP.md**：50 阶段的路线图，查看整体进度。
- **STATE.md**：当前里程碑的详细状态。
- **当前状态**：v8.0 进行中 — Phase 47 已完成，Phase 48/50 部分完成，Phase 49 待启动。

如果您想参与某个 Phase，请先阅读对应的 PLAN 文件（如 `.planning/phase-49/PLAN.md`），确认该 Phase 尚未被他人认领。
```

改为：

```markdown
## 规划与 Phase 状态

本项目使用 Superpowers specs + plans 进行规划。当前活跃的 spec 文档位于 `docs/superpowers/specs/`。

v1.0-v13.0 的历史 Phase 规划已归档至 `.planning/archive/`。`.planning/MILESTONES.md` 包含版本历史索引。

如果您想参与某个功能，请查看对应的 spec 文件，确认该功能尚未被他人认领。
```

- [ ] **Step 2: 更新文件组织中的 .planning 描述**

将第 156 行从：

```markdown
.planning/          # Phase 规划文档
```

改为：

```markdown
.planning/          # 规划历史归档（v1.0-v13.0）
docs/superpowers/   # 当前规划（specs + plans）
```

- [ ] **Step 3: 验证无残留 GSD 引用**

```bash
grep -i "gsd" docs/CONTRIBUTING.md
```

Expected: 无匹配结果。

- [ ] **Step 4: 提交**

```bash
git add docs/CONTRIBUTING.md
git commit -m "chore: update CONTRIBUTING.md for Superpowers migration (remove GSD references)"
```

---

### Task 7: 删除 GSD 专用文件

**Files:**
- Delete: `.planning/phases/` (entire directory)
- Delete: `.planning/research/` (entire directory)
- Delete: `.planning/ROADMAP.md`
- Delete: `.planning/STATE.md`
- Delete: `.planning/REQUIREMENTS.md`
- Delete: `.planning/PROJECT.md`
- Delete: `.planning/config.json`

**Background:** GSD 专用文件，内容已提取到 specs 或合并到 CLAUDE.md。保留 `.planning/MILESTONES.md`、`.planning/archive/`、`.planning/milestones/`。

- [ ] **Step 1: 验证保留文件仍存在**

```bash
ls .planning/MILESTONES.md
ls .planning/archive/
ls .planning/milestones/
```

Expected: 三个路径均存在。

- [ ] **Step 2: 删除 GSD 文件**

```bash
rm -rf .planning/phases/
rm -rf .planning/research/
rm .planning/ROADMAP.md
rm .planning/STATE.md
rm .planning/REQUIREMENTS.md
rm .planning/PROJECT.md
rm .planning/config.json
```

- [ ] **Step 3: 验证删除结果**

```bash
ls .planning/
```

Expected: 仅剩 `MILESTONES.md`、`archive/`、`milestones/`。

- [ ] **Step 4: 验证 spec 完整性**

```bash
ls docs/superpowers/specs/
```

Expected: 4 个 spec 文件：
- `2026-05-27-farchive-cor-fixes-design.md`
- `2026-05-27-uobject-inheritance-linker-design.md`
- `2026-05-27-iostore-utoc-ucas-design.md`
- `2026-05-27-pascalcase-output-format-design.md`

- [ ] **Step 5: 提交**

```bash
git add -u .planning/
git commit -m "chore: delete GSD planning files (content migrated to Superpowers specs)"
```

---

### Task 8: 最终验证 + 全量提交

- [ ] **Step 1: 运行全量测试**

```bash
python -m pytest tests/ -q
```

Expected: 通过（或仅包含已知无关失败）。

- [ ] **Step 2: 检查 git 状态**

```bash
git status
```

Expected: 干净工作树（所有变更已提交）。

- [ ] **Step 3: 验证无残留 GSD 引用**

```bash
grep -ri "gsd" CLAUDE.md docs/DEVELOPMENT.md docs/CONTRIBUTING.md
```

Expected: 无匹配结果。

- [ ] **Step 4: 确认 .planning 目录状态**

```bash
ls .planning/
```

Expected: `MILESTONES.md` `archive/` `milestones/` 三个条目。

- [ ] **Step 5: 确认 docs/superpowers/ 结构**

```bash
find docs/superpowers/ -type f
```

Expected: 4 个 spec 文件 + 1 个设计文档 + plans 目录。

---

## 文件总览

### 新建文件 (6)
| 文件 | Task | 说明 |
|------|------|------|
| `docs/superpowers/specs/2026-05-27-gsd-to-superpowers-migration-design.md` | 设计阶段 | 迁移设计文档 |
| `docs/superpowers/specs/2026-05-27-farchive-cor-fixes-design.md` | Task 1 | Phase 76 spec |
| `docs/superpowers/specs/2026-05-27-uobject-inheritance-linker-design.md` | Task 2 | Phase 78 spec |
| `docs/superpowers/specs/2026-05-27-iostore-utoc-ucas-design.md` | Task 3 | Phase 79 spec |
| `docs/superpowers/specs/2026-05-27-pascalcase-output-format-design.md` | Task 3 | Phase 80 spec |
| `docs/superpowers/plans/` | 已有 | 目录（空，后续 plans 存放） |

### 修改文件 (3)
| 文件 | Task | 说明 |
|------|------|------|
| `CLAUDE.md` | Task 4 | 删除 GSD 引用，更新规划路径 |
| `docs/DEVELOPMENT.md` | Task 5 | 删除 GSD Workflow 章节 |
| `docs/CONTRIBUTING.md` | Task 6 | 删除 GSD 工作流阶段章节 |

### 删除文件/目录 (7)
| 路径 | Task | 说明 |
|------|------|------|
| `.planning/phases/` | Task 7 | GSD Phase 文件（整个目录） |
| `.planning/research/` | Task 7 | GSD 研究文件（整个目录） |
| `.planning/ROADMAP.md` | Task 7 | 路线图 |
| `.planning/STATE.md` | Task 7 | 状态追踪 |
| `.planning/REQUIREMENTS.md` | Task 7 | 需求文档 |
| `.planning/PROJECT.md` | Task 7 | 项目定义 |
| `.planning/config.json` | Task 7 | GSD 配置 |

### 保留文件 (3)
| 路径 | 说明 |
|------|------|
| `.planning/MILESTONES.md` | 版本历史索引 |
| `.planning/archive/` | v1.0-v13.0 已完成里程碑 |
| `.planning/milestones/` | 各版本测试报告 |
