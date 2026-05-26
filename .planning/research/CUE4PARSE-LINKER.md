# CUE4Parse Linker 架构调查报告

**日期:** 2026-05-26
**目的:** 理解 CUE4Parse 如何解决 UE 资产链接问题，为 Phase 76-79 实现提供架构参考
**来源:** CUE4Parse 源码 (E:\Develop\lib\CUE4Parse) + 架构分析

---

## 1. 核心架构概览

CUE4Parse **不是** UE 原生 `FLinkerLoad` 的直接复刻，而是采用 **Package 中心 + 懒加载** 模型。

### 两套包系统

| 类 | 用途 | UE 对应 |
|------|------|------|
| `Package` | 传统 `.uasset`/`.uexp` 解析 | FLinkerLoad (cooked) |
| `IoPackage` | UE5 IoStore (`.utoc`/`.ucas`) 包 | FIoStore + ZenLoader |
| `AbstractUePackage` | 两者基类 | FLinker base |

### 关键文件

- `Package.cs` — 传统包解析、ImportMap/ExportMap、懒加载
- `IoPackage.cs` — UE5 IoStore 格式、ExportBundle 处理、Hash 匹配
- `AbstractUePackage.cs` — 基类、ConstructObject/DeserializeObject
- `ObjectResource.cs` — FPackageIndex（32位有符号索引）
- `FPackageObjectIndex.cs` — 64位类型化索引（IoStore 专用）
- `AbstractFileProvider.cs` — 包加载调度、路径解析、VFS 管理

---

## 2. 索引系统

### FPackageIndex（传统 .uasset）

```
FPackageIndex = 32-bit signed integer
  > 0: ExportMap 索引，实际位置 = value - 1
  < 0: ImportMap 索引，实际位置 = -value - 1
  = 0: None / null
```

### FPackageObjectIndex（IoStore）

```
FPackageObjectIndex = 64-bit
  - 2-bit type field: Export | ScriptImport | PackageImport | Null
  - 62-bit ID: 根据类型含义不同
PackageImport 结构:
  - ImportedPackageIndex: 目标包的索引
  - ImportedPublicExportHashIndex: 目标 export 的 PublicExportHash 索引
```

> **对我们的启示：** uasset_read 目前只使用 FPackageIndex 模型。Phase 77/79 需要支持 IoStore 时必须引入 FPackageObjectIndex。

---

## 3. Import → Export 解析流程（ResolveImport）

`ResolveImport` 方法 (`Package.cs` L254-337) 是跨引用解析的核心，分四步：

### Step 1: 遍历 Outer 链
```csharp
// 从当前 import 开始，沿着 Outer 引用向上遍历
// 直到找到最外层的 import（Outer 为 None 的那个）
while (currentImport.OuterIndex.IsImport)
    currentImport = ResolveImport(currentImport.OuterIndex);
```

### Step 2: 检查 Script 包（/Script/ 前缀）
```csharp
if (outerMostImport.ObjectName.Text.StartsWith("/Script/"))
    return new ResolvedImportObject(ClassName, ObjectName);
```
> **关键决策：** CUE4Parse **不实际加载** /Script/ DLL，直接返回占位符。类型信息来自 TypeMappings 注册（UScriptClass），而非真实脚本包解析。

### Step 3: 跨包查找
```csharp
if (Provider.TryLoadPackage(outerMostImport.ObjectName.Text, out Package targetPackage))
{
    // 在目标包中查找匹配的 export
}
```

### Step 4: 名称/Hash 匹配
- **传统包：** 按 export name + outer 路径匹配
- **IoStore：** 用 `PublicExportHash` 精确匹配（仅名称匹配不够）

### ResolvedObject 层次结构

```
ResolvedObject (abstract)
├── ResolvedExportObject   — 包内实际 export，有 Lazy<UObject> Object 属性
├── ResolvedImportObject   — 未解析 import 的占位符，仅携带元数据
├── ResolvedPackageObject  — 包级引用
└── ResolvedLoadedObject   — 已加载的 UObject 包装
```

---

## 4. 跨包引用解析（两种机制）

### 传统 Package 路径

```
FObjectImport.PackageName (string, 如 "/Game/Path/AssetName")
    → Provider.TryLoadPackage(packageName, out package)
        → 遍历目标包 Exports
            → 按 name + outer path 匹配
```

### IoStore Package 路径

```
FPackageObjectIndex (PackageImport 类型)
    → ImportedPackageIndex → 定位目标包
    → ImportedPublicExportHashIndex → 取 hash
    → 对比目标包 Export.PublicExportHash → 精确匹配
    
回退机制:
    1. GlobalImportIndex 跨包匹配
    2. ImportedPackagesAllVersions 搜索所有历史版本
```

> **对我们的启示：** PublicExportHash 是 IoStore 的权威交叉引用。Phase 77/79 实现 IoStore 解析时，仅靠名称匹配是不够的。

---

## 5. Preload / 序列化管线

### 懒加载模式（默认）

```csharp
ExportsLazy[i] = new Lazy<UObject>(() => {
    // Phase 1: 创建外壳
    obj = ConstructObject(ClassIndex, this);
    obj.Name   = ResolvePackageIndex(NameIndex);
    obj.Outer  = ResolvePackageIndex(OuterIndex);
    obj.Super  = ResolvePackageIndex(SuperIndex);
    obj.Template = ResolvePackageIndex(TemplateIndex);
    
    // Phase 2: 按需反序列化
    Ar.SeekAbsolute(export.SerialOffset);
    DeserializeObject(obj, Ar, export.SerialSize);
    obj.PostLoad();
    return obj;
});
```

### Eager 模式（ExportLoader — 依赖排序加载）

仅在 `useLazySerialization = false` 时启用，用于需要确定性加载顺序的场景。

**依赖图构建：**
从 `PreloadDependencies` 构建 `LoadDependency` 图，分为四类依赖：

| 阶段 | 含义 |
|------|------|
| `SerializationBeforeSerializationDependencies` | 序列化前必须先序列化的对象 |
| `CreateBeforeSerializationDependencies` | 序列化前必须先创建的对象 |
| `SerializationBeforeCreateDependencies` | 创建前必须先序列化的对象 |
| `CreateBeforeCreateDependencies` | 创建前必须先创建的对象 |

**状态机：**
```
Create → Serialize → Complete
```
`Fire(phase)` 递归解析依赖后才进入下一阶段。

---

## 6. IoGlobalData（全局数据）

```
IoGlobalData — 从 global.utoc 加载，全局共享
├── GlobalNameMap         — 全局名称表（所有包的共享名称）
└── ScriptObjectEntries   — 脚本对象索引（/Script/ 类型的全局注册）
```

> **对我们的启示：** IoGlobalData 只加载一次，跨所有包共享。Phase 79 (IoStore) 实现时需要类似的全局数据结构。

---

## 7. 与 UE FLinkerLoad 的关键差异

| 方面 | UE FLinkerLoad | CUE4Parse |
|------|---------------|-----------|
| 对象创建 | `StaticConstructObject_Internal` | `ConstructObject` via `UScriptClass.ConstructObject(flags)` |
| Preload | `Preload()` via `RF_NeedLoad` flag | `Lazy<UObject>` 或 `ExportLoader.Fire()` |
| Import 解析 | `ResolveName()` 完整搜索 | 按 PackageName + 名称字符串匹配 |
| Script 包 | 加载 /Script/ DLL | 返回 `ResolvedImportObject` 占位符 |
| 序列化 | `UObject::Serialize()` 虚函数分发 | `obj.Deserialize(Ar, validPos)` C# 多态 |
| 依赖跟踪 | `FDependencyGraph` with `FExportBulkFlags` | `LoadDependency` 状态机 |
| IoStore | `FZipFileStoreReader` + `FIoDispatcher` | `IoStoreReader` + `IoGlobalData` |
| 跨包 | `FLinkerLoad::FindExportForLoadExternalImport` | `Provider.TryLoadPackage()` + name/hash match |
| 线程 | `FAsyncLoadingThread` 异步加载 | `Task.Run()` + `ConcurrentDictionary` |

---

## 8. 对 uasset_read Phase 76-79 的核心启示

### 8.1 架构模式对齐

CUE4Parse 的 link 本质是 **PackageName 字符串解析 + 名称/Hash 匹配**，而非 UE 原生完整 linker 搜索。我们的 `PackageLinker` 需要在 Python 端复现类似的：

```
ResolvePackageIndex → LazyDeserialize → 按需加载
```

### 8.2 两阶段模型

| 阶段 | 内容 | Python 实现建议 |
|------|------|----------------|
| **外壳创建** | 解析 ClassIndex/Name/Outer/Super/Template | `UObjectInstance` 已实现 |
| **按需反序列化** | 定位 SerialOffset → Deserialize → PostLoad | `preload()` 已实现，需补充依赖排序 |

### 8.3 需要补充的能力

| 能力 | 当前状态 | 优先级 | 对应 Phase |
|------|---------|--------|-----------|
| 依赖排序加载（ExportLoader 模式） | 缺失 | High | 76 |
| FArchive + PackageSummary 源码索引 | 缺失 | High | 76 |
| IoStore FPackageObjectIndex | 缺失 | Medium | 77/79 |
| PublicExportHash 匹配 | 缺失 | Medium | 79 |
| IoGlobalData 全局共享 | 缺失 | Medium | 79 |
| Script 包占位符 | 部分实现 | Low | 78 |

### 8.4 设计约束

1. **不加载 Script 包** — CUE4Parse 对 /Script/ import 返回占位符，我们应保持相同行为
2. **两套索引并存** — 传统 + IoStore，需要抽象层隔离
3. **懒加载是默认路径** — ExportLoader 仅在需要确定性时启用
4. **Hash 匹配优于名称匹配** — IoStore 场景下名称匹配不可靠

---

## 9. 参考类图

```
AbstractUePackage (abstract)
├── Package (traditional .uasset)
│   ├── ImportMap: FObjectImport[]
│   ├── ExportMap: FExport[]
│   ├── ExportsLazy: Lazy<UObject>[]
│   └── ResolvePackageIndex(FPackageIndex?) → ResolvedObject
├── IoPackage (UE5 IoStore)
│   ├── ExportBundleHeader
│   ├── PublicExportHashes
│   ├── GlobalImportIndex
│   └── ResolvePackageIndex(FPackageObjectIndex) → ResolvedObject

AbstractFileProvider
├── TryLoadPackage(name, out package) → bool
├── Packages: ConcurrentDictionary<string, AbstractUePackage>
└── IoGlobalData (shared global)

ResolvedObject (abstract)
├── ResolvedExportObject → Lazy<UObject>
├── ResolvedImportObject → metadata only
├── ResolvedPackageObject → package reference
└── ResolvedLoadedObject → already-loaded UObject

ExportLoader (eager mode)
├── LoadDependency[] (from PreloadDependencies)
├── LoadPhase enum: Create | Serialize | Complete
└── Fire(phase) → recursive dependency resolution
```
