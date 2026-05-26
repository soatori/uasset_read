# Architecture Integration: CUE4Parse Features into uasset_read

**Project:** uasset_read v14.0 — CUE4Parse Python 全量对齐
**Researched:** 2026-05-26

## 1. Executive Summary

CUE4Parse 是一个 C# .NET 8.0 的 UE 资产解析库，定位为"游戏资源逆向提取 + 3D 导出"。uasset_read 是 Python 3.10+ 的蓝图语义解析器，定位为"AI 代理蓝图语义读取"。两个项目在**核心序列化层**高度重叠，但在**导出目标**、**数据深度**、**扩展机制**上存在根本差异。

v14.0 的"全量对齐"不意味着复制 CUE4Parse 的全部功能（纹理解码、网格导出、Pak/IoStore 解析不在本项目的 v14.0 范围内，已在 PROJECT.md 的 Out of Scope 中标注），而是指**序列化层和对象系统的完整一比一对应翻译**，使得 uasset_read 能够处理 CUE4Parse 能处理的所有 .uasset 资产类型，并在架构模式上对齐。

### 核心结论

| 维度 | 现状 | 目标状态 | 复杂度 |
|------|------|----------|--------|
| FArchive 读取原语 | 已有基础 | 补充 IntPacked、BulkArray、完整版本感知 | Medium |
| 版本管理系统 | 简单版本检查 | VersionContainer + CustomVersions + 游戏标识 | High |
| UObject 对象系统 | 扁平 dataclass | 继承层次 + Deserialize 模式 + Lazy 加载 | High |
| 属性类型扩展 | 14 种 | 30+ 种（含 SparseClassData、FieldPath 等） | Medium |
| 包结构 | Package 模式 | 保持单一，补充 DependsMap、BulkData 偏移 | Low |
| Kismet 字节码 | 已有基础 | Token 覆盖度提升 + 游戏特殊 Token | Medium |
| 游戏特定覆盖 | 无 | 可扩展钩子（非 70+ 游戏硬编码） | Medium |
| 加密/压缩 | 不支持 | 不在 v14.0 范围 | N/A |

## 2. Existing Architecture (Current State)

```
.uasset → FArchive → Deserializer → Models → OutputFormatter
         ↓
    PackageLinker (两阶段对象图重建)
         ↓
    GraphParser → AdvancedPropParser → DependencyGraphBuilder
         ↓
    Kismet (字节码 → 表达式树 → C++ 翻译)
         ↓
    N2C (中间格式 → JSON → Agent 消费)
         ↓
    Agent (翻译管线 → CppFileWriter)
```

### 现有模块职责边界

| 模块 | 当前职责 | 对应 CUE4Parse |
|------|----------|----------------|
| `archive.py` | FArchive 二进制读取器（mmap/字节交换/FString/FName） | `FArchive` / `FArchiveBigEndian` |
| `serializers/` | PackageSummary/Import/Export/PropertyTag 读取 | `FPackageFileSummary` / `FPropertyTag` |
| `models/` | UEdGraph/Node/Pin + 属性数据类 | `UObject` 派生类（部分） |
| `parsers/` | 14 种属性类型解析 | `FPropertyTagType.TryRead` |
| `blueprint/` | 变量/组件/变换提取 | `UObject` 派生类特定逻辑 |
| `graph/` | 执行流/数据流/连接映射 | 无直接对应（uasset_read 独有） |
| `link/` | PackageLinker 两阶段加载 | `Package` / `AbstractUePackage` |
| `kismet/` | 字节码提取/反编译/C++翻译 | `FKismetArchive` / `KismetExpression` |
| `n2c/` | N2C 中间格式 | 无对应（uasset_read 独有） |
| `agent/` | Agent 翻译管线 | 无对应（uasset_read 独有） |
| `cpp_gen/` | C++ 骨架提取 | 无直接对应 |

## 3. Gap Analysis: What CUE4Parse Has That uasset_read Lacks

### 3.1 高优先级 Gap（v14.0 必须对齐）

| Gap ID | CUE4Parse 能力 | uasset_read 现状 | 影响 | 新/修改 |
|--------|---------------|-------------------|------|---------|
| GAP-01 | **VersionContainer** — 游戏标识 + 版本标志 + CustomVersions 查询 | 仅简单 `is_ue5` / `is_unversioned` 检查 | 无法按版本/游戏选择序列化行为 | 新模块 |
| GAP-02 | **UObject 继承层次** — UObject → UField → UStruct → UClass/UFunction | 扁平 dataclass（UEdGraph/UEdGraphNode） | 无法复用反序列化逻辑，每类资产硬编码 | 新模块 |
| GAP-03 | **Lazy 反序列化** — `Lazy<UObject>[] ExportsLazy` | 顺序遍历 ExportMap 逐个解析 | 大文件内存峰值高，无法按需加载 | 修改 |
| GAP-04 | **FAssetArchive** — 包装 FArchive + 注入 NameMap/Versions | FArchive 独立使用，NameMap 手动传递 | 上下文信息分散，序列化代码冗余 | 修改 |
| GAP-05 | **完整 PropertyTag 类型覆盖** — 30+ 种 FPropertyTagType | 14 种解析器 | 遇到未知类型直接跳过或报错 | 修改 |
| GAP-06 | **IntPacked 压缩读取** — 7-bit 数据 + 1-bit 继续标志 | 不支持 | 无法读取使用 IntPacked 编码的资产 | 新模块 |
| GAP-07 | **ReadBulkArray 版本分支** — 新旧版 count 格式 | 不支持 | 无法正确读取 BulkData 数组 | 修改 |
| GAP-08 | **SparseClassData** — UE5 稀疏类数据分离序列化 | 不支持 | UE5 资产部分属性无法读取 | 新模块 |
| GAP-09 | **DependsMap** — Export 依赖图 | 无 | 无法按依赖顺序反序列化 | 新模块 |
| GAP-10 | **ObjectGuid** — UE4.27+ 对象 GUID | 无 | 缺少对象唯一标识 | 新模块 |

### 3.2 中优先级 Gap（v14.0 建议对齐）

| Gap ID | CUE4Parse 能力 | uasset_read 现状 | 影响 | 新/修改 |
|--------|---------------|-------------------|------|---------|
| GAP-11 | **FieldPathProperty** — UE5 属性引用（FFieldPath） | 不支持 | 无法解析引用其他属性的属性 | 新解析器 |
| GAP-12 | **MulticastDelegateProperty** — 多播委托 | DelegateProperty 单播 | 蓝图多播事件解析不完整 | 新解析器 |
| GAP-13 | **UnversionedProperties** — 按 UScriptClass 字段顺序读取 | 不支持 | 无法解析未版本化属性资产 | 新模块 |
| GAP-14 | **游戏特殊 Token 扩展** — EX_6E/EX_FD 等自定义 Token | 固定 EExprToken 集合 | 特定游戏蓝图字节码无法解析 | 修改 |
| GAP-15 | **ExportBundle 结构** — UE5 导出分组 | 扁平 ExportMap | UE5 导出顺序/依赖处理不完整 | 修改 |

### 3.3 低优先级 Gap（v14.0 可选/后续版本）

| Gap ID | CUE4Parse 能力 | 说明 | 优先级 |
|--------|---------------|------|--------|
| GAP-16 | **Pak/IoStore 解析** | 已在 Out of Scope | 后续版本 |
| GAP-17 | **加密支持（AES/XOR）** | 已在 Out of Scope | 后续版本 |
| GAP-18 | **压缩算法（Oodle/Zstd）** | 已在 Out of Scope | 后续版本 |
| GAP-19 | **纹理/网格/音频导出** | 不在本项目定位 | 不实现 |
| GAP-20 | **70+ 游戏特定覆盖** | uasset_read 定位为通用解析器，非游戏逆向 | 仅实现扩展钩子 |

## 4. New Component Architecture

### 4.1 新增模块

```
src/uasset_read/
├── archive.py                    [MODIFY] 补充 IntPacked, BulkArray
├── versions/                     [NEW]     版本管理系统
│   ├── __init__.py
│   ├── container.py              VersionContainer (对标 CUE4Parse VersionContainer)
│   ├── custom.py                 CustomVersion (Guid + int32)
│   ├── game.py                   游戏标识枚举 + 行为标志
│   └── ue_version.py             EUEVersion 枚举 + 版本比较
├── context/                      [NEW]     序列化上下文
│   ├── __init__.py
│   ├── asset_archive.py          FAssetArchive (包装 FArchive + 注入上下文)
│   └── loader.py                 资产加载器（对标 CUE4Parse 加载入口）
├── objects/                      [NEW]     UObject 对象系统
│   ├── __init__.py
│   ├── base.py                   UObject 抽象基类 + Deserialize 接口
│   ├── field.py                  UField / UEnum / UStruct / UClass / UFunction
│   ├── properties/               [NEW]     扩展属性类型
│   │   ├── __init__.py
│   │   ├── field_path.py         FieldPathProperty
│   │   ├── multicast_delegate.py  MulticastDelegateProperty
│   │   ├── lazy.py               LazyProperty (延迟反序列化包装)
│   │   └── unversioned.py        UnversionedProperty 读取器
│   └── exports/                  [NEW]     具体导出类（按需实现）
│       ├── __init__.py
│       ├── texture.py            UTexture2D (序列化结构)
│       ├── static_mesh.py        UStaticMesh (序列化结构)
│       └── sound.py              USoundWave (序列化结构)
├── serializers/
│   └── depends.py                [NEW]     DependsMap 读取器
├── parsers/
│   └── unversioned_parser.py     [NEW]     按 UScriptClass 字段顺序读取
└── kismet/
    └── tokens_ext.py             [NEW]     游戏特殊 Token 扩展注册
```

### 4.2 修改模块清单

| 模块 | 修改内容 | 依赖的新组件 |
|------|----------|-------------|
| `archive.py` | 添加 `read_int_packed()` / `read_bulk_array()` / `read_bulk_typed_array()` | 无 |
| `serializers/property_tags.py` | 扩展至 30+ 类型分派；添加 FieldPathProperty / MulticastDelegateProperty | `objects/properties/` |
| `serializers/package_summary.py` | 添加 DependsOffset 读取；ObjectGuid 条件读取 | `versions/` |
| `serializers/object_resources.py` | 添加 ExportBundle 结构支持 | `versions/` |
| `models/core.py` | UEdGraphNode 改为继承 UObject 基类 | `objects/base.py` |
| `models/properties.py` | 添加 FieldPathValue / MulticastDelegateValue | `objects/properties/` |
| `models/result.py` | 添加 version_info / game_id 字段 | `versions/` |
| `link/linker.py` | preload() 支持 Lazy 模式；DependsMap 感知加载顺序 | `context/` |
| `link/object_instance.py` | 添加 object_guid 字段 | `serializers/` |
| `parsers/property_parser.py` | 分派逻辑接入 VersionContainer 版本判断 | `versions/` |
| `kismet/tokens.py` | 添加可扩展 Token 注册机制 | `kismet/tokens_ext.py` |
| `kismet/bytecode_extractor.py` | 支持游戏特殊 Token 跳过/记录 | `kismet/tokens_ext.py` |
| `parse_uasset.py` | 主管线接入 FAssetArchive 上下文 | `context/` |
| `cli.py` | 添加 `--game` / `--custom-versions` 选项 | `versions/` |

## 5. Data Flow Changes

### 5.1 修改后的 parse_uasset() 流程

```
1. FArchive(path)                              → 打开文件
2. read_package_summary()                      → 解析头部
3. [NEW] build_version_container(summary)      → 构建 VersionContainer (游戏标识 + CustomVersions)
4. read_name_table()                           → FName 名称表
5. [MODIFIED] FAssetArchive(archive, name_map, versions)
                                               → 包装归档，注入上下文
6. read_import_map()                           → ImportMap
7. read_export_map()                           → ExportMap
8. [NEW] read_depends_map()                    → DependsMap (依赖图)
9. [MODIFIED] for export in export_map:
     resolve_lazy_export(export, asset_archive) → Lazy 按需反序列化
     → 判断 HasUnversionedProperties?
       → YES: deserialize_unversioned(asset_archive, script_class)
       → NO:  deserialize_tagged(asset_archive)  ← 现有 parse_properties_from_export
     → [NEW] if UE4.27+: read ObjectGuid
     → [NEW] if UE5 + SparseClassData: deserialize_sparse_class_data(asset_archive)
10. _post_process()                            → 后处理（不变）
     extract_blueprint_graphs()
     extract_blueprint_metadata()
     decompile_uasset()
     extract_components()
     build_imports_list()
11. return ParseResult                         → 新增 version_info / game_id
```

### 5.2 数据流差异对比

```
现有流程:
  FArchive → read_X → parse_properties → models → formatter

新流程:
  FArchive → VersionContainer → FAssetArchive → read_X
    → UObject.Deserialize (多态) → models (继承层次)
    → Lazy 缓存 → formatter
```

**关键变化：**
- `FArchive` 不再直接暴露给解析代码，而是通过 `FAssetArchive` 上下文访问
- 属性解析不再是扁平的 `parse_property_value()` 分派，而是 `UObject.Deserialize()` 多态调用
- Export 反序列化从"全部读取"改为"Lazy 按需"（大文件内存优化）
- 版本判断从"全局 is_ue5 布尔值"升级为"VersionContainer 查询"

### 5.3 FAssetArchive 上下文注入模式

```
FAssetArchive (对标 CUE4Parse FAssetArchive)
├── 包装 FArchive (继承/组合)
├── Owner.NameMap → FName 查找（替代手动传递 name_map）
├── Owner.Versions → VersionContainer 查询
├── Owner.Game → 游戏标识（用于 switch 分支）
└── ReadFName() → 自动查 NameMap（对标 CUE4Parse ReadFName）
```

所有序列化代码改为接收 `FAssetArchive` 而非裸 `FArchive`，消除 NameMap/Versions 手动传递。

## 6. Integration Points

### 6.1 与现有模块的集成边界

| 新组件 | 集成到的现有模块 | 集成方式 |
|--------|-----------------|----------|
| `versions/container.py` | `archive.py`, `serializers/` | 版本检查替代全局布尔值 |
| `context/asset_archive.py` | `archive.py`, 所有 serializers | 包装 FArchive，所有序列化入口改为接收 FAssetArchive |
| `objects/base.py` | `models/core.py` | UEdGraph/Node/Pin 改为继承 UObject |
| `objects/properties/` | `parsers/property_types.py` | 新增解析器注册到分派表 |
| `serializers/depends.py` | `link/linker.py` | 依赖图用于预加载排序 |
| `kismet/tokens_ext.py` | `kismet/tokens.py`, `kismet/bytecode_extractor.py` | Token 注册表扩展 |

### 6.2 不修改的模块（保持现状）

| 模块 | 原因 |
|------|------|
| `graph/` | 图解析是 uasset_read 独有功能，CUE4Parse 无对应 |
| `n2c/` | N2C 中间格式是 uasset_read 独有输出，CUE4Parse 无对应 |
| `agent/` | Agent 翻译管线是 uasset_read 独有目标 |
| `cpp_gen/` | C++ 代码生成是 uasset_read 独有目标 |
| `formatters/` | 格式化输出层不涉及序列化逻辑 |
| `blueprint/` | 蓝图提取依赖 graph/ 和 models/，序列化对齐后自动受益 |

### 6.3 API 兼容性

**向后兼容承诺：**
- `parse_uasset()` 签名不变（内部自动构建 VersionContainer）
- `FArchive` 类保留（FAssetArchive 包装而非替换）
- 现有 `parse_properties_from_export()` 保留（作为 Deserialize 的 fallback）
- 新增 `parse_uasset_with_context(path, game_id=None)` 可选入口

**新增公共 API：**
- `VersionContainer` — 版本查询
- `FAssetArchive` — 序列化上下文
- `UObject` — 对象基类
- `register_game_behavior(game_id, key, behavior_func)` — 游戏特定行为注册

## 7. Suggested Build Order

按依赖关系排序，每个阶段可独立验证。

### Phase 14.1: FArchive 原语补充
**目标：** 补齐 CUE4Parse FArchive 的读取原语
**组件：** `archive.py` 修改
**内容：**
- `read_int_packed()` — 变长压缩整数
- `read_bulk_array()` — 版本感知 BulkData 数组
- `read_bulk_typed_array()` — 带元素大小验证的批量读取
**验证：** 单元测试覆盖三种读取模式，对比 CUE4Parse 输出
**依赖：** 无
**复杂度：** Low

### Phase 14.2: VersionContainer 版本管理
**目标：** 建立版本查询系统
**组件：** `versions/` 新模块
**内容：**
- `VersionContainer` — 游戏标识 + 版本 + CustomVersions 查询
- `EUEVersion` — UE 版本枚举（UE4.0 ~ UE5.5）
- `CustomVersion` — (Guid, int32) 对
- `GameID` — 游戏标识（先支持 GENERIC + UE4/UE5 基线，后续可扩展）
**验证：** 解析已知资产的 CustomVersions，对比 CUE4Parse
**依赖：** Phase 14.1
**复杂度：** Medium

### Phase 14.3: FAssetArchive 上下文
**目标：** 消除 NameMap/Versions 手动传递
**组件：** `context/asset_archive.py`
**内容：**
- `FAssetArchive` — 包装 FArchive + 注入 NameMap + Versions
- `ReadFName()` — 自动 NameMap 查找
- 所有现有 serializers 改为接收 `FAssetArchive` 参数
**验证：** `parse_uasset()` 行为不变（回归测试）
**依赖：** Phase 14.2
**复杂度：** Medium（改动面广但逻辑简单）

### Phase 14.4: UObject 对象系统
**目标：** 建立继承层次 + Deserialize 模式
**组件：** `objects/` 新模块
**内容：**
- `UObject` 抽象基类 + `Deserialize(FAssetArchive)` 接口
- `UField` → `UEnum` / `UStruct` → `UClass` / `UScriptStruct` / `UFunction`
- `DeserializePropertiesTagged()` / `DeserializePropertiesUnversioned()`
- `UObjectInstance` (link/) 改为继承 `UObject`
**验证：** UEdGraph 通过新体系反序列化，输出与现有一致
**依赖：** Phase 14.3
**复杂度：** High

### Phase 14.5: 属性类型扩展
**目标：** 从 14 种扩展到 30+ 种
**组件：** `objects/properties/`, `parsers/property_types.py` 修改
**内容：**
- `FieldPathProperty` / `FieldPathValue`
- `MulticastDelegateProperty` / `MulticastDelegateValue`
- `SparseClassData` 支持
- `ObjectGuid` 读取（UE4.27+）
- 注册到 `FPropertyTagType` 分派表
**验证：** 解析包含新属性类型的资产
**依赖：** Phase 14.4
**复杂度：** Medium

### Phase 14.6: Lazy 反序列化 + DependsMap
**目标：** 按需加载 + 依赖感知
**组件：** `link/linker.py`, `serializers/depends.py`, `context/loader.py`
**内容：**
- `LazyExport` — Python property 延迟反序列化
- `read_depends_map()` — DependsOffset 解析
- `preload_ordered()` — 按依赖顺序预加载
**验证：** 大资产内存峰值下降；依赖解析正确
**依赖：** Phase 14.4, 14.5
**复杂度：** Medium

### Phase 14.7: Kismet Token 扩展 + 游戏特殊处理
**目标：** 字节码覆盖度提升
**组件：** `kismet/tokens_ext.py`
**内容：**
- 可扩展 Token 注册表
- 游戏特殊 Token 跳过/记录机制
- `FKismetArchive` 版本感知读取
**验证：** 解析特定游戏蓝图字节码
**依赖：** Phase 14.2（版本判断）
**复杂度：** Low

### Phase 14.8: ExportBundle + 完整包结构
**目标：** UE5 导出分组支持
**组件：** `serializers/object_resources.py` 修改
**内容：**
- `ExportBundleHeader` / `ExportBundle` 读取
- 导出顺序保证
- 完整性校验
**验证：** UE5 资产导出完整性
**依赖：** Phase 14.2, 14.3
**复杂度：** Low

## 8. Architecture Diagram: Post-v14.0

```
.uasset
  ↓
FArchive (raw bytes, mmap, byte swap)
  + read_int_packed() [NEW]
  + read_bulk_array() [NEW]
  ↓
VersionContainer [NEW]
  + Game identification
  + CustomVersions query
  + Version flags
  ↓
FAssetArchive [NEW]
  + NameMap injection
  + Versions injection
  + ReadFName() auto-lookup
  ↓
AbstractUePackage [NEW]
  + Summary → NameMap → ImportMap → ExportMap → DependsMap
  + Lazy<UObject> exports
  ↓
UObject.Deserialize [NEW]
  ├── tagged properties (existing parse_properties)
  ├── unversioned properties [NEW]
  └── sparse class data [NEW]
  ↓
Concrete types (UClass / UScriptStruct / UEdGraph / ...)
  ├── existing: graph extraction
  ├── existing: blueprint metadata
  ├── existing: Kismet decompilation
  └── [NEW]: texture/mesh/sound structure extraction
  ↓
N2C JSON + Agent Translation + C++ Generation (unchanged)
```

## 9. Design Patterns to Adopt

### 9.1 策略模式：VersionContainer

```python
class VersionContainer:
    def __init__(self, game: GameID, file_version: FileVersion, custom: list[CustomVersion]):
        self.game = game
        self.file_version = file_version
        self._custom = {cv.guid: cv.version for cv in custom}
        self._flags: dict[str, Any] = {}

    def is_at_least(self, version: EUEVersion) -> bool:
        return self.file_version >= version

    def get_custom(self, guid: str) -> int:
        return self._custom.get(guid, 0)

    def set_flag(self, key: str, value: Any) -> None:
        self._flags[key] = value
```

### 9.2 装饰器模式：FAssetArchive

```python
class FAssetArchive:
    """Wraps FArchive, injects NameMap and Versions context."""
    def __init__(self, archive: FArchive, name_map: list[str], versions: VersionContainer):
        self._archive = archive
        self.name_map = name_map
        self.versions = versions

    def read_fname(self) -> str:
        index = self._archive.read_i32()
        if index == -1:
            return "None"
        if index < 0 or index >= len(self.name_map):
            raise ParseError(f"Invalid name index: {index}")
        return self.name_map[index]

    def read_fstring(self) -> str:
        return self._archive.read_fstring()

    # Delegate all other reads to wrapped archive
    def __getattr__(self, name):
        return getattr(self._archive, name)
```

### 9.3 工厂模式：UObject.Deserialize 分派

```python
class UObjectRegistry:
    """Maps export type string to UObject subclass."""
    _registry: dict[str, type[UObject]] = {}

    @classmethod
    def register(cls, type_name: str, klass: type[UObject]) -> None:
        cls._registry[type_name] = klass

    @classmethod
    def create(cls, type_name: str, archive: FAssetArchive) -> UObject:
        klass = cls._registry.get(type_name, UObject)
        obj = klass()
        obj.deserialize(archive)
        return obj
```

### 9.4 懒加载模式：Python property

```python
class LazyExport:
    def __init__(self, export_entry: ObjectExport, linker: PackageLinker):
        self._export = export_entry
        self._linker = linker
        self._value: UObject | None = None

    @property
    def value(self) -> UObject:
        if self._value is None:
            self._value = self._deserialize()
        return self._value

    def _deserialize(self) -> UObject:
        instance = self._linker.resolve_package_index(self._export.package_index)
        self._linker.preload(instance.package_index)
        return instance
```

## 10. Risk Assessment

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| UObject 继承层次与现有 models/core.py 冲突 | High | Medium | 渐进迁移：先新建 objects/，models/ 作为 alias |
| FAssetArchive 改动面大，回归测试不足 | High | Medium | Phase 14.3 完成后立即运行全部 1319 tests |
| VersionContainer 游戏标识过度设计 | Medium | Low | v14.0 仅支持 GENERIC，游戏特定逻辑作为扩展钩子 |
| Lazy 反序列化破坏现有同步假设 | Medium | Low | LazyExport 保持同步接口（非异步），仅延迟执行时机 |
| 属性类型扩展到 30+ 种引入新 bug | Medium | Medium | 每种类型独立单元测试 + 已知资产对比 |
| Kismet Token 扩展影响现有翻译管线 | Low | Low | tokens_ext.py 独立模块，不影响现有 tokens.py |

## 11. Sources

- `docs/CUE4Parse-索引.md` — CUE4Parse 架构参考（HIGH confidence，项目内文档）
- `docs/FRAMEWORK.md` — uasset_read 框架索引（HIGH confidence，项目内文档）
- `.planning/PROJECT.md` — 项目定义和里程碑（HIGH confidence）
- `.planning/STATE.md` — v14.0 当前状态（HIGH confidence）
- `.planning/ROADMAP.md` — 历史路线图（HIGH confidence）
- CUE4Parse GitHub 仓库 (https://github.com/FabianFG/CUE4Parse) — 源码验证（MEDIUM confidence，未直接检查当前 commit）

## 12. Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Gap Analysis | HIGH | 基于 docs/CUE4Parse-索引.md 逐模块对比 |
| New Components | HIGH | 直接映射 CUE4Parse 模块到 Python |
| Data Flow Changes | MEDIUM | 架构设计合理，但具体实现细节需在 phase 中验证 |
| Build Order | MEDIUM | 依赖关系分析合理，但并行化机会需进一步评估 |
| Integration Points | HIGH | 明确标注了修改 vs 新建 vs 不变 |
| Risk Assessment | MEDIUM | 基于架构复杂度估算，实际风险需在开发中验证 |
