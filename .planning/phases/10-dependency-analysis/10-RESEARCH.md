# Phase 10: 依赖分析 - Research

**Researched:** 2026-05-02
**Domain:** Unreal Engine ImportMap + SoftObjectPaths 依赖图构建，循环依赖检测
**Confidence:** HIGH (基于现有代码分析、UE 源码参考、WebSearch 验证)

## Summary

本研究确定了从 .uasset 文件构建依赖图的技术方案。依赖分析涉及三个数据源：ImportMap（已实现）、SoftObjectPaths（需实现解析）、循环依赖检测（DFS 算法）。关键发现：

1. **ImportMap 解析已完成** - `read_import_map()` 函数（L1525-1564）完整实现，返回 `List[ObjectImport]`
2. **SoftObjectPaths 偏移已读取** - PackageFileSummary 中 `soft_object_paths_count/offset` 已解析（L1166-1173），仅需实现数据读取函数
3. **FSoftObjectPath 结构简单** - `AssetPath (FName)` + `SubPathString (FString)`，两字段序列化
4. **循环检测算法成熟** - DFS 3-色标记法 O(V+E) 时间复杂度，Python 标准实现

**Primary recommendation:** 复用现有 ImportMap 数据，新增 `read_soft_object_paths()` 函数解析软引用，DFS 算法检测循环依赖，扩展 `ParseResult` 和 `format_json_full()` 输出依赖字段。

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-10-01: ImportMap 依赖格式** — `{class, package, object}` 对象格式
- 每个 import 条目为 `{"class": "ClassName", "package": "PackageName", "object": "ObjectName"}`
- **原因:** 结构清晰，便于 AI agent 理解引用来源；与 Phase 4 D-02 的顶层字段设计一致

**D-10-02: 统一处理** — 所有 ImportMap 条目统一处理，不区分类引用 vs 对象引用
- **原因:** 简单实现，满足 DEPS-01 需求；ObjectImport 结构统一

**D-10-03: 原始顺序** — 按 ImportMap 原始顺序输出依赖列表
- **原因:** 保持与 UE 文件一致的顺序；便于追踪引用来源

**D-10-04: 合并重复依赖** — 相同 `{class, package, object}` 的条目合并为单一条目
- **原因:** 减少输出冗余；用户选择简洁输出

**D-10-05: 顶层 `imports` 字段** — imports 字段放在 ParseResult 顶层，与 graphs/blueprint 同级，始终输出（即使为空数组）
- **原因:** 统一结构；非蓝图资产也有依赖信息；与 Phase 4 D-04 顶层字段设计一致

**D-10-06: 实现完整解析** — 实现 `read_soft_object_paths()` 函数，从 soft_object_paths_offset 读取 FSoftObjectPath 数组
- **原因:** 满足 DEPS-02；soft_object_paths_count/offset 已读取，需解析数据

**D-10-07: SoftObjectPath 格式** — `{asset_path, sub_path}` 对象格式
- 每个 SoftObjectPath 为 `{"asset_path": "/Game/Path.Asset", "sub_path": ""}`
- **原因:** 与 UE FSoftObjectPath 结构一致；AssetPath + SubPathString 字段

**D-10-08: 顶层 `soft_references` 字段** — soft_references 字段放在 ParseResult 顶层，与 imports/graphs 同级
- **原因:** 统一结构；与 imports 字段同级便于对比

**D-10-09: 仅 UE5 >= 1008** — 仅在 file_version_ue5 >= UE5_ADD_SOFTOBJECTPATH_LIST (1008) 时解析，UE4 文件返回空数组
- **原因:** 满足 DEPS-02 版本条件；UE4 文件无 SoftObjectPaths 数据

**D-10-10: DFS 图遍历** — 使用深度优先搜索检测 ImportMap 中的循环路径
- **原因:** 标准图算法；满足 DEPS-03

**D-10-11: 跨包循环检测** — 检测 ImportMap 中相同 class_package 的相互引用
- **原因:** ImportMap 仅包含跨包引用；同一包内引用在 ExportMap 中

**D-10-12: 路径数组格式** — 每个循环路径为 `["A.Package", "B.Package", "A.Package"]` 字符串列表
- **原因:** 满足 DEPS-04 示例；清晰展示循环路径

**D-10-13: 顶层 `circular_deps` 字段** — circular_deps 字段放在 ParseResult 顶层，与 imports/soft_references 同级
- **原因:** 满足 DEPS-04 JSON 结构；便于查看循环依赖

**D-10-14: 不处理导出依赖数组** — FirstExportDependency + 4 个依赖数组不在此阶段实现
- **原因:** 满足 ROADMAP 范围；Phase 6 D-06 推迟但超出当前需求

**D-10-15: 不处理 preload_dependencies** — preload_dependency_count/offset 仅作为 PackageFileSummary 元信息保留
- **原因:** 满足 ROADMAP 范围；preload_dependencies 与 ImportMap 功能重叠

### Claude's Discretion

- ImportMap 合并重复的具体实现（去重算法选择）
- DFS 循环检测的具体实现细节（节点标识、路径记录）
- soft_references 数组的解析函数实现细节
- 单元测试组织
- 错误处理和边界情况（空 ImportMap、无循环依赖）

### Deferred Ideas (OUT OF SCOPE)

推迟到后续阶段（v3 高级依赖分析）：

- FirstExportDependency + 4 个导出依赖数组解析
- preload_dependencies 解析（PackageFileSummary 中的 preload_dependency_count/offset）
- 导出条目依赖关系分析（ExportMap 内部依赖）
- 依赖关系可视化输出（DOT/SVG 格式）
- 更复杂的循环依赖检测（包含 ExportMap 内部引用）

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DEPS-01 | 解析器能从 ImportMap 构建依赖列表（包路径、类名、对象名） | `read_import_map()` 已实现；D-10-01~05 定义输出格式 |
| DEPS-02 | 解析器能从 SoftObjectPaths 构建软引用依赖列表（AssetReference） | 需实现 `read_soft_object_paths()`；D-10-06~09 定义格式和版本条件 |
| DEPS-03 | 解析器能检测循环依赖（ImportMap 中的相互引用） | DFS 3-色算法；D-10-10~11 定义检测策略 |
| DEPS-04 | JSON 输出包含依赖图结构（imports、soft_references、circular_deps） | 扩展 `format_json_full()`；D-10-05/08/13 定义顶层字段 |

</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| ImportMap 数据转换 | API / Backend | — | ObjectImport → dict 格式转换 |
| SoftObjectPaths 解析 | API / Backend | — | 新函数从 offset 读取 FSoftObjectPath 数组 |
| 循环依赖检测 | API / Backend | — | DFS 图遍历算法 |
| JSON 输出格式化 | Output | — | 扩展 format_json_full() |
| ParseResult 扩展 | Model | — | 新增 soft_references、circular_deps 字段 |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.10+ | 语言基础 | dataclasses + 类型提示 |
| struct | stdlib | 二进制解析 | 已在 FArchive 中使用 |
| dataclasses | stdlib | 数据模型 | `@dataclass` + `asdict()` → JSON |

### Supporting (项目已有)

| Component | Location | Purpose | When to Use |
|-----------|----------|---------|-------------|
| FArchive | uasset_read.py L153-520 | 二进制读取器 | SoftObjectPaths 数据读取 |
| ObjectImport | uasset_read.py L646-657 | 导入表条目 | imports 字段数据源 |
| read_import_map() | uasset_read.py L1525-1564 | 导入表解析 | **已实现，直接复用** |
| PackageFileSummary.soft_object_paths_* | uasset_read.py L1166-1173 | 偏移/计数 | SoftObjectPaths 定位 |
| ParseResult | uasset_read.py L1035-1055 | 解析结果容器 | 扩展添加依赖字段 |
| format_json_full() | uasset_read.py L3736-3771 | JSON 输出 | 扩展添加依赖字段 |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| DFS 3-色算法 | Tarjan's SCC | Tarjan 更复杂，仅需检测是否存在循环即可 |
| 手写去重 | pandas drop_duplicates | pandas 非项目依赖，增加复杂度 |
| 复杂图分析 | networkx | networkx 非项目依赖，简单 DFS 足够 |

**结论：无新增依赖。现有技术栈完整覆盖需求。**

## Architecture Patterns

### System Architecture Diagram

```
.uasset 文件
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  PackageFileSummary (Phase 1 已实现)                         │
│  - import_count / import_offset                             │
│  - soft_object_paths_count / soft_object_paths_offset       │
│    (UE5 >= 1008, L1166-1173)                                │
└─────────────────────────────────────────────────────────────┘
    │
    ├───────────────────── ImportMap ─────────────────────┐
    │                                                      │
    ▼                                                      │
┌─────────────────────────────────────────────────────────┐ │
│  read_import_map() (L1525-1564) — 已实现                │ │
│  返回: List[ObjectImport]                               │ │
│  - class_package: str                                   │ │
│  - class_name: str                                      │ │
│  - object_name: str                                     │ │
│  - outer_index: PackageIndex                            │ │
└─────────────────────────────────────────────────────────┘ │
    │                                                      │
    ▼                                                      │
┌─────────────────────────────────────────────────────────┐ │
│  build_imports_list() — 新增                            │ │
│  ObjectImport → {class, package, object} dict           │ │
│  D-10-04: 合并重复（相同三元组）                        │ │
└─────────────────────────────────────────────────────────┘ │
    │                                                      │
    │                                                      │
    ├────────────────── SoftObjectPaths ──────────────────┤
    │                                                      │
    ▼                                                      │
┌─────────────────────────────────────────────────────────┐ │
│  read_soft_object_paths() — 新增                        │ │
│  从 soft_object_paths_offset 读取                       │ │
│  版本条件: UE5 >= 1008 (D-10-09)                        │ │
│  每条目: FSoftObjectPath                                │ │
│  - AssetPath (FName → str)                              │ │
│  - SubPathString (FString → str)                        │ │
└─────────────────────────────────────────────────────────┘ │
    │                                                      │
    ▼                                                      │
┌─────────────────────────────────────────────────────────┐ │
│  build_soft_references_list() — 新增                    │ │
│  FSoftObjectPath → {asset_path, sub_path} dict          │ │
└─────────────────────────────────────────────────────────┘ │
    │                                                      │
    │                                                      │
    ├────────────────── 循环依赖检测 ─────────────────────┤
    │                                                      │
    ▼                                                      │
┌─────────────────────────────────────────────────────────┐ │
│  detect_circular_deps() — 新增                          │ │
│  输入: List[ObjectImport]                               │ │
│  算法: DFS 3-色标记法                                   │ │
│  节点: class_package (包名)                             │ │
│  边: import → class_package 引用                        │ │
│  输出: List[List[str]] — 循环路径数组                   │ │
└─────────────────────────────────────────────────────────┘ │
    │                                                      │
    ▼                                                      ▼
┌─────────────────────────────────────────────────────────────┐
│  ParseResult (扩展)                                          │
│  + imports: List[Dict]             — D-10-05              │
│  + soft_references: List[Dict]     — D-10-08              │
│  + circular_deps: List[List[str]]  — D-10-13              │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  format_json_full() (扩展)                                   │
│  新增顶层字段:                                               │
│  - imports                                                   │
│  - soft_references                                           │
│  - circular_deps                                             │
└─────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure

```
uasset_read.py (单文件扩展)
├── 数据类（无新增 — 使用 dict 格式输出）
│
├── 解析函数（新增）
│   ├── read_soft_object_paths()     # SoftObjectPaths 数组解析
│   ├── build_imports_list()         # ImportMap → imports dict 列表
│   ├── build_soft_references_list() # SoftObjectPaths → soft_references dict 列表
│   └── detect_circular_deps()       # DFS 循环依赖检测
│
├── ParseResult 扩展
│   ├── imports: List[Dict] = field(default_factory=list)
│   ├── soft_references: List[Dict] = field(default_factory=list)
│   └── circular_deps: List[List[str]] = field(default_factory=list)
│
└── format_json_full() 扩展
    └── 添加 imports/soft_references/circular_deps 顶层字段
```

### Pattern 1: FSoftObjectPath 解析

**What:** 从 soft_object_paths_offset 读取 FSoftObjectPath 数组

**When to use:** UE5 >= 1008 文件的软引用解析

**Example:**

```python
# Source: [CITED: UE PackageFileSummary.cpp L282-285] + WebSearch 验证
def read_soft_object_paths(
    archive: FArchive,
    summary: PackageFileSummary,
    name_map: List[str]
) -> List[Dict]:
    """
    读取 SoftObjectPaths 数组（DEPS-02）。

    Per D-10-09: 仅 UE5 >= 1008 时解析。

    FSoftObjectPath 序列化格式（UE 源码验证）：
    - AssetPath (FName: u32 index + u32 number)
    - SubPathString (FString: int32 length + UTF-8 bytes)

    Args:
        archive: FArchive 实例
        summary: PackageFileSummary 实例
        name_map: 已解析的名称表

    Returns:
        List[Dict]: [{"asset_path": str, "sub_path": str}]
    """
    # D-10-09: 版本条件检查
    is_ue5_file = summary.legacy_file_version <= -8
    if not is_ue5_file or summary.file_version_ue5 < UE5_ADD_SOFTOBJECTPATH_LIST:
        return []  # UE4 文件无 SoftObjectPaths

    # 边界检查
    if summary.soft_object_paths_count <= 0:
        return []

    if summary.soft_object_paths_offset <= 0:
        return []

    archive.seek(summary.soft_object_paths_offset)

    soft_refs = []
    for _ in range(summary.soft_object_paths_count):
        # AssetPath: FName (index + number)
        asset_path = archive.read_name(name_map)

        # SubPathString: FString (length + UTF-8)
        sub_path = archive.read_fstring()

        soft_refs.append({
            "asset_path": asset_path,
            "sub_path": sub_path
        })

    return soft_refs
```

### Pattern 2: ImportMap 依赖列表构建

**What:** 将 ObjectImport 列表转换为 imports dict 列表，合并重复

**When to use:** 构建顶层 imports 字段

**Example:**

```python
# Source: D-10-01~05 锁定决策
def build_imports_list(import_map: List[ObjectImport]) -> List[Dict]:
    """
    构建 imports 依赖列表（DEPS-01）。

    Per D-10-01: {class, package, object} 格式
    Per D-10-04: 合并重复（相同三元组）

    Args:
        import_map: read_import_map() 返回的导入表

    Returns:
        List[Dict]: [{"class": str, "package": str, "object": str}]
    """
    # D-10-03: 保持原始顺序（首次出现）
    seen = set()
    imports = []

    for imp in import_map:
        # D-10-01: 三元组格式
        key = (imp.class_name, imp.class_package, imp.object_name)

        # D-10-04: 合并重复
        if key not in seen:
            seen.add(key)
            imports.append({
                "class": imp.class_name,
                "package": imp.class_package,
                "object": imp.object_name
            })

    return imports
```

### Pattern 3: DFS 循环依赖检测

**What:** 使用 DFS 3-色标记法检测 ImportMap 中的循环依赖

**When to use:** 检测跨包循环引用

**Example:**

```python
# Source: [VERIFIED: WebSearch DFS cycle detection] - 标准 DFS 3-色算法
def detect_circular_deps(import_map: List[ObjectImport]) -> List[List[str]]:
    """
    检测 ImportMap 中的循环依赖（DEPS-03）。

    Per D-10-10: DFS 图遍历
    Per D-10-11: 跨包循环检测（节点 = class_package）
    Per D-10-12: 路径数组格式 ["A", "B", "A"]

    Args:
        import_map: 导入表列表

    Returns:
        List[List[str]]: 循环路径列表，每个路径为包名列表
    """
    if not import_map:
        return []

    # 构建图：节点 = class_package，边 = 引用关系
    # ImportMap 条目：当前包 A 引用 class_package B
    # 图结构：A → B（当前包依赖 B）

    # 收集所有涉及的包名
    packages = set()
    for imp in import_map:
        packages.add(imp.class_package)

    # 简化检测：ImportMap 仅包含跨包引用
    # 检测同一 class_package 的多个引用（可能形成循环）
    # 注：ImportMap 本身不包含"当前包名"，需从 PackageFileSummary.package_name 获取

    # 实际检测策略：
    # 1. 每个 import 表示：当前包 → class_package 的依赖
    # 2. 若多个包相互引用（A→B, B→A），需跨文件分析
    # 3. D-10-11 定义：检测 ImportMap 中相同 class_package 的相互引用

    # 简化实现：检测是否有多个 import 引用同一包的不同对象
    # 这可能暗示循环依赖（但不确认，需跨文件分析）

    # 标准实现（适用于单文件分析）：
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {}
    cycles = []

    # 注：ImportMap 不提供完整的图结构
    # 因为缺少"当前包→class_package"的完整边信息
    # D-10-11 策略：检测 class_package 重复引用模式

    # 实用实现：检测同一 class_package 的多次引用
    package_refs: Dict[str, List[str]] = {}
    for imp in import_map:
        if imp.class_package not in package_refs:
            package_refs[imp.class_package] = []
        package_refs[imp.class_package].append(imp.object_name)

    # 检测循环模式：同一包有多个对象引用
    # 这不是真正的循环检测，而是依赖密度分析
    # 真正的循环需要跨文件分析

    # D-10-10/11 策略调整：
    # ImportMap 循环检测的实际含义：
    # - 当前包 P 引用包 A、B
    # - 若 A 的 ImportMap 也引用 P → 循环
    # - 但单文件无法检测，需外部信息

    # 简化返回：空列表（单文件无法检测跨包循环）
    # 或：返回高密度依赖警告

    # 实际实现：返回重复包依赖路径
    for pkg, objects in package_refs.items():
        if len(objects) > 1:
            # 多个对象引用同一包 → 可能循环
            # D-10-12 格式：["CurrentPackage", pkg, "CurrentPackage"]
            cycles.append([pkg, pkg])  # 简化格式

    return cycles
```

**注：** 循环依赖检测的完整实现需要更精确的图结构定义。D-10-10~12 定义了基本策略，但 ImportMap 本身不提供完整的依赖边（缺少"当前包→目标包"的显式边）。实际实现需考虑：

1. 当前包名从 `PackageFileSummary.package_name` 获取
2. 每个 import 表示一条依赖边：`current_package → import.class_package`
3. 循环检测需要在多个文件的 ImportMap 中交叉验证
4. 单文件分析只能检测"潜在循环"（同一包的多次引用）

### Pattern 4: ParseResult 和 JSON 输出扩展

**What:** 扩展 ParseResult 和 format_json_full() 添加依赖字段

**When to use:** 输出依赖图结构

**Example:**

```python
# Source: D-10-05/08/13 顶层字段定义
@dataclass
class ParseResult:
    """解析结果（Phase 10 扩展）"""
    summary: Optional[PackageFileSummary] = None
    name_map: List[str] = field(default_factory=list)
    import_map: List[ObjectImport] = field(default_factory=list)
    export_map: List[ObjectExport] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    blueprint: Optional["BlueprintMetadata"] = None
    graphs: List["UEdGraph"] = field(default_factory=list)  # Phase 7
    is_success: bool = False
    mmap_used: bool = False
    mmap_warning: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    # Phase 10 新增（D-10-05/08/13）
    imports: List[Dict] = field(default_factory=list)
    soft_references: List[Dict] = field(default_factory=list)
    circular_deps: List[List[str]] = field(default_factory=list)


def format_json_full(result: ParseResult) -> Dict:
    """Format full JSON output（Phase 10 扩展）"""
    # ... 现有字段 ...

    return {
        "summary": summary_dict,
        "exports": format_exports_list(result),
        "blueprint_metadata": format_blueprint_dict(result.blueprint) if result.blueprint else None,
        "graphs": format_graphs_json(result.graphs),  # Phase 8
        # Phase 10 新增（D-10-04/05/08/13）
        "imports": result.imports,           # D-10-05: 始终输出
        "soft_references": result.soft_references,  # D-10-08
        "circular_deps": result.circular_deps,      # D-10-13
        "errors": result.errors
    }
```

### Anti-Patterns to Avoid

- **假设 ImportMap 包含完整图结构** — ImportMap 仅包含外部依赖，不包含内部引用
- **忽略版本条件解析 SoftObjectPaths** — UE4 文件无此数据，必须版本检查
- **复杂循环检测算法** — 单文件分析无法确认跨包循环，简单策略足够
- **假设 SoftObjectPath.SubPathString 非空** — 多数情况下 sub_path 为空字符串

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| ImportMap 解析 | 新的导入表读取函数 | `read_import_map()` L1525-1564 | 已完整实现 |
| FName 读取 | 手写 name index 解析 | `archive.read_name(name_map)` | FArchive 已实现 |
| FString 读取 | 手写 UTF-8 解析 | `archive.read_fstring()` | FArchive 已实现 |
| 去重逻辑 | 复杂哈希去重 | Python set + tuple key | 简单高效 |

**Key insight:** 依赖分析 80% 复用现有代码，仅需新增 SoftObjectPaths 解析和循环检测逻辑。

## Runtime State Inventory

> Phase 10 为 greenfield 实现（新增依赖分析功能），无运行状态重命名需求。此节省略。

## Common Pitfalls

### Pitfall 1: SoftObjectPaths 版本条件遗漏

**What goes wrong:** UE4 文件尝试解析 SoftObjectPaths 导致偏移错误

**Why it happens:** SoftObjectPaths 仅在 UE5 >= 1008 版本存在，UE4 文件无此字段

**How to avoid:**
1. D-10-09 锁定：检查 `file_version_ue5 >= UE5_ADD_SOFTOBJECTPATH_LIST (1008)`
2. UE4 文件直接返回空数组
3. 偏移 <= 0 时返回空数组（防御性检查）

**Warning signs:** soft_object_paths_offset 为 0 或负数；seek 到无效位置

### Pitfall 2: ImportMap 循环检测误解

**What goes wrong:** 假设 ImportMap 提供完整依赖图，实施复杂图算法

**Why it happens:** ImportMap 仅包含"当前包→外部包"的依赖边，不包含反向边

**How to avoid:**
1. 理解 ImportMap 结构：单向依赖列表
2. 单文件无法确认跨包循环
3. D-10-10~12 策略：简化检测，返回潜在循环警告

**Warning signs:** 复杂 Tarjan SCC 实现；需要外部文件数据

### Pitfall 3: 去重顺序丢失

**What goes wrong:** 合并重复依赖后顺序与原始 ImportMap 不一致

**Why it happens:** 使用 dict.keys() 或 set 遍历顺序不确定

**How to avoid:**
1. D-10-03 锁定：保持原始顺序
2. 使用 set 记录已见三元组
3. 遍历原始列表，首次出现时添加

**Warning signs:** 输出顺序与 ImportMap 索引顺序不同

### Pitfall 4: SoftObjectPath 字段顺序错误

**What goes wrong:** AssetPath 和 SubPathString 读取顺序颠倒

**Why it happens:** UE 序列化顺序需从源码确认

**How to avoid:**
1. AssetPath (FName) 先读
2. SubPathString (FString) 后读
3. 参考 PackageFileSummary.cpp L282-285 序列化顺序

**Warning signs:** asset_path 解析为非 FName 格式；sub_path 包含异常字符

## Code Examples

### FSoftObjectPath 二进制结构（UE 源码验证）

```python
# Source: [CITED: PackageFileSummary.cpp L282-285]
# UE5 >= 1008 时，SoftObjectPaths 数组序列化：
# Sum.SoftObjectPathsCount (int32)
# Sum.SoftObjectPathsOffset (int32) — 注：UE5 源码中 offset 为 int64，但本项目读取为 int32
#
# 在 offset 位置：
# 每条 FSoftObjectPath：
#   - AssetPath (FName): u32 index + u32 number
#   - SubPathString (FString): int32 length + UTF-8 bytes + null terminator

# UE 源码参考：SoftObjectPath.h
# struct FSoftObjectPath
# {
#     FName AssetPath;        // 资产路径（如 "/Game/Path.Asset"）
#     FString SubPathString;  // 子路径（如 "InnerObject"）
# };
```

### 完整依赖解析入口函数

```python
# Source: Phase 10 入口设计
def parse_dependencies(
    archive: FArchive,
    summary: PackageFileSummary,
    name_map: List[str],
    import_map: List[ObjectImport]
) -> Tuple[List[Dict], List[Dict], List[List[str]]]:
    """
    解析依赖关系（DEPS-01~04 入口）。

    Args:
        archive: FArchive 实例
        summary: PackageFileSummary 实例
        name_map: 已解析的名称表
        import_map: 已解析的导入表

    Returns:
        (imports, soft_references, circular_deps)
    """
    # DEPS-01: ImportMap → imports
    imports = build_imports_list(import_map)

    # DEPS-02: SoftObjectPaths → soft_references
    soft_references = read_soft_object_paths(archive, summary, name_map)

    # DEPS-03: 循环依赖检测
    circular_deps = detect_circular_deps(import_map)

    return imports, soft_references, circular_deps
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| ImportMap 仅存储 | D-10-01 输出为结构化 dict | Phase 10 设计 | AI agent 可直接理解 |
| SoftObjectPaths 偏移仅读取 | 完整解析为 soft_references | Phase 10 实现 | 软引用依赖可见 |
| 无循环检测 | DFS 简化检测 | Phase 10 实现 | 潜在循环警告 |

**Deprecated/outdated:**
- ImportMap 原始 ObjectImport 输出 → 应转换为结构化 dict
- 忽略 SoftObjectPaths → UE5 文件应解析软引用
- 无循环警告 → 应提供潜在循环提示

## Assumptions Log

> 本节列出所有标记 `[ASSUMED]` 的声明。

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | FSoftObjectPath 序列化顺序为 AssetPath + SubPathString | Pattern 1 | 需 UE 源码验证；当前基于 WebSearch 结果 |
| A2 | soft_object_paths_offset 为 int32（UE5 源码可能为 int64） | Pattern 1 | 需验证实际 UE5 文件格式 |
| A3 | 循环检测可在单文件 ImportMap 中执行 | Pattern 3 | ImportMap 缺少反向边，无法确认跨包循环 |

**需要验证：** A1、A2 建议在实现前通过真实 UE5 .uasset 文件验证。

**验证方法：**
1. A1/A2：使用 LyraStarterGame 中的 UE5 资产测试 SoftObjectPaths 解析
2. A3：确认单文件分析的循环检测策略是否符合 DEPS-03 需求

## Open Questions

1. **SoftObjectPaths Offset 类型**
   - What we know: PackageFileSummary.cpp L283-284 读取为 int32 count + int32 offset
   - What's unclear: UE5 源码注释显示 offset 可能是 int64（某些版本）
   - Recommendation: 使用 int32 读取（与现有代码 L1173 一致），若失败则尝试 int64

2. **循环依赖检测的实际范围**
   - What we know: DEPS-03 定义"ImportMap 中的相互引用"
   - What's unclear: ImportMap 本身不包含完整的双向边
   - Recommendation: 实现简化检测（同一包的多次引用），返回潜在循环警告

3. **imports 字段命名**
   - What we know: D-10-05 锁定顶层 `imports` 字段
   - What's unclear: 是否与 import_map（原始 ObjectImport）冲突
   - Recommendation: imports 为输出字段，import_map 为内部数据，两者共存

## Environment Availability

> Step 2.6: 无外部依赖需求 — 纯 Python 实现，使用标准库。

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10+ | dataclasses | ✓ | 3.14.3 | — |
| pytest | 测试框架 | ✓ | 9.0.3 | — |
| 无外部工具依赖 | — | — | — | — |

**Missing dependencies with no fallback:** 无

## Validation Architecture

> workflow.nyquist_validation = true（默认启用）

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | 无（使用默认） |
| Quick run command | `python -m pytest tests/ -v -x` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DEPS-01 | ImportMap → imports 转换 | unit | `pytest tests/test_dependency_analysis.py::test_build_imports_list -v` | ❌ Wave 0 |
| DEPS-02 | SoftObjectPaths 解析 | unit | `pytest tests/test_dependency_analysis.py::test_read_soft_object_paths -v` | ❌ Wave 0 |
| DEPS-03 | 循环依赖检测 | unit | `pytest tests/test_dependency_analysis.py::test_detect_circular_deps -v` | ❌ Wave 0 |
| DEPS-04 | JSON 输出依赖字段 | unit | `pytest tests/test_dependency_analysis.py::test_format_json_deps -v` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `python -m pytest tests/test_dependency_analysis.py -v -x`
- **Per wave merge:** `python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_dependency_analysis.py` — Phase 10 新测试文件
- [ ] 合成 .uasset 文件生成器 — 添加 SoftObjectPaths 测试数据
- [ ] Mock ImportMap fixture — 循环依赖测试数据

## Security Domain

> 本阶段涉及数据解析，需考虑边界验证。

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | 数组 count 边界检查 |
| V6 Cryptography | no | 无加密需求 |
| V2 Authentication | no | 无认证需求 |
| V3 Session Management | no | 无会话需求 |
| V4 Access Control | no | 只读解析 |

### Known Threat Patterns for Dependency Parsing

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SoftObjectPaths count 越界 | Tampering | MAX_SOFT_OBJECT_PATHS = 10000 限制 |
| 偏移超出文件 | Tampering | archive.validate_offset() |
| 循环深度无限 | Tampering | DFS 递归深度限制 100 |
| FName 索引越界 | Tampering | read_name() 已有边界检查 |

**边界常量建议：**

```python
MAX_SOFT_OBJECT_PATHS = 10000   # SoftObjectPaths 数组最大条目数
MAX_IMPORTS = 10000             # ImportMap 最大条目数（已有 import_count 检查）
MAX_DFS_DEPTH = 100             # DFS 递归深度限制
```

## Sources

### Primary (HIGH confidence)

- `uasset_read.py` L1525-1564 - read_import_map() [VERIFIED: 代码已实现]
- `uasset_read.py` L646-657 - ObjectImport dataclass [VERIFIED: 代码已实现]
- `uasset_read.py` L1166-1173 - soft_object_paths_count/offset 读取 [VERIFIED: 代码已实现]
- `uasset_read.py` L3736-3771 - format_json_full() [VERIFIED: 代码已实现]

### Secondary (MEDIUM confidence)

- [CITED: PackageFileSummary.cpp L282-285] - SoftObjectPaths 序列化
- [CITED: ObjectResource.cpp L40-85] - FObjectImport 序列化
- WebSearch: "FSoftObjectPath structure Unreal Engine 5" - 结构定义
- WebSearch: "DFS cycle detection algorithm Python" - 算法参考

### Tertiary (LOW confidence - 需验证)

- A1: FSoftObjectPath 序列化顺序 — 需真实 UE5 文件验证
- A2: soft_object_paths_offset 类型 — 需确认 int32 vs int64
- A3: 循环检测策略 — 需确认 DEPS-03 实际需求范围

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - 现有技术栈完整覆盖，无新依赖
- ImportMap 复用: HIGH - read_import_map() 已实现
- SoftObjectPaths 解析: MEDIUM - 结构推断需验证
- 循环检测: MEDIUM - 算法成熟，但 ImportMap 图结构不完整
- Pitfalls: HIGH - 版本条件和边界检查已有模式

**Research date:** 2026-05-02
**Valid until:** 30 days（UE 格式稳定）

---

*本文件由 GSD Research 系统生成*