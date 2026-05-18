# Unreal Editor 加载 .uasset 文件完整流程

## 1. 概述

本文档详细描述了 Unreal Engine Editor 从 Content Browser 中双击资产到 .uasset 文件完全加载到内存中的完整管线。涉及的核心子系统包括：Content Browser UI、AssetTools、UFactory、FLinkerLoad（核心序列化）、Asset Registry。

## 2. 整体管线概览

```
用户双击 Content Browser 中的资产
        │
        ▼
SContentBrowser::OnItemsActivated()
        │
        ▼
UContentBrowserDataSource::BulkEditItems()
        │
        ▼
IAssetTypeActions::OpenAssetEditor() / AssetDefinition::OpenAssets()
        │
        ▼
FAssetData::GetAsset() 或 LoadPackage()
        │
        ▼
LoadPackageInternal() → FLinkerLoad::CreateLinkerAsync()
        │
        ▼
FLinkerLoad::ProcessPackageSummary()  ← 读取文件头、验证版本
        │
        ▼
FLinkerLoad::Tick() → LoadAllObjects() → 序列化导出表
        │
        ▼
FinalizeCreation() → PostLoad() → 资产就绪
```

## 3. 编辑器入口 — Content Browser 交互

### 3.1 用户双击触发

| 文件 | 位置 |
|---|---|
| `Engine/Source/Editor/ContentBrowser/Private/SContentBrowser.cpp` | ~3184行 |
| `Engine/Source/Editor/ContentBrowser/Private/ContentBrowserSingleton.cpp` | ~633行 |

- `SContentBrowser::OnItemsActivated()` — 用户双击资产时触发，传入 `EAssetTypeActivationMethod::DoubleClicked`
- 调用 `UContentBrowserDataSource::BulkEditItems()` 批量处理选中项
- 根据资产类型路由到对应的 `IAssetTypeActions` 实现

### 3.2 关键代码流程

```cpp
void SContentBrowser::OnItemsActivated(TArrayView<const FContentBrowserItem> ActivatedItems, ...)
{
    // 按数据源分批
    for (const FContentBrowserItem& ActivatedItem : ActivatedItems)
    {
        if (ActivatedItem.IsFile())
        {
            // 获取内部项数据并执行编辑操作
            if (!SourceAndItemsPair.Key->BulkEditItems(SourceAndItemsPair.Value))
            {
                // 显示错误
            }
        }
    }
}
```

## 4. FAssetTools — 资产操作中枢

### 4.1 核心接口

| 文件 | 位置 |
|---|---|
| `Engine/Source/Developer/AssetTools/Private/AssetTools.h` | UAssetToolsImpl 类 |
| `Engine/Source/Developer/AssetTools/Private/AssetTypesActions/*.cpp` | 各类型实现 |
| `Engine/Source/Editor/ContentBrowser/Public/IAssetTypeActions.h` | 接口定义 |

- `UAssetToolsImpl::OpenEditorForAssets()` — 打开资产的编辑器
- `UAssetToolsImpl::CreateAsset()` — 通过 Factory 创建新资产
- `UAssetToolsImpl::ImportAssets()` — 导入文件为资产
- 使用 `IAssetTypeActions` 处理不同类型资产的打开逻辑

## 5. UFactory 工厂系统

### 5.1 核心接口

| 文件 | 位置 |
|---|---|
| `Engine/Source/Editor/UnrealEd/Classes/Factories/Factory.h` | 类定义 |
| `Engine/Source/Editor/UnrealEd/Private/Factories/Factory.cpp` | ~55-118行 |

- `UFactory::FactoryCreateFile()` — 从文件创建/导入对象
- `FactoryCreateNew()` — 创建空对象
- `FactoryCreateText()` — 从文本数据创建对象
- `FactoryCreateBinary()` — 从二进制数据创建对象

### 5.2 工厂流程

```cpp
UObject* UFactory::FactoryCreateFile(UClass* InClass, UObject* InParent, FName InName, ...)
{
    // 优先检查脚本实现
    if (ScriptFactoryCreateFile(Task))
    {
        return Task->GetObjects()[0];
    }

    // 如果设置了 bText 标志，按文本加载
    if (bText)
    {
        return FactoryCreateText(...);
    }

    // 按二进制加载
    TArray64<uint8> Data;
    FFileHelper::LoadFileToArray(Data, *Filename);
    return FactoryCreateBinary(...);
}
```

## 6. FLinkerLoad — 核心序列化机制

这是整个加载管线的心脏，负责从磁盘读取 .uasset 文件。

### 6.1 核心文件

| 文件 | 说明 |
|---|---|
| `Engine/Source/Runtime/CoreUObject/Private/UObject/LinkerLoad.cpp` | 274KB，核心实现 |
| `Engine/Source/Runtime/CoreUObject/Public/UObject/Package.h` | 包定义 |

### 6.2 创建流程

- `FLinkerLoad::CreateLinkerAsync()` — 检查是否已有 Linker，否则创建新的
- `FLinkerLoad::CreateLoader()` — 创建底层 I/O 加载器（FIoLoader / FArchive）

```cpp
FLinkerLoad* FLinkerLoad::CreateLinker(FUObjectSerializeContext* LoadContext, UPackage* Parent, ...)
{
    // 先创建异步 Linker
    FLinkerLoad* Linker = CreateLinkerAsync(LoadContext, Parent, PackagePath, LoadFlags, ...);

    // Tick Linker 以加载包摘要
    if (Linker->Tick(0.f, false, false, nullptr) == LINKER_Failed)
    {
        return nullptr;
    }

    FCoreUObjectDelegates::PackageCreatedForLoad.Broadcast(Parent);
    return Linker;
}
```

### 6.3 加载阶段详解

| 阶段 | 函数 | 说明 |
|---|---|---|
| **1. 包摘要处理** | `ProcessPackageSummary()` | 读取并验证包文件头、引擎版本、文件格式 |
| **2. 导入表加载** | — | 加载所有导入表条目（引用的外部对象） |
| **3. 导出表处理** | — | 读取导出表条目（本包内存储的对象），创建 UObject 实例 |
| **4. 对象序列化** | `Tick()` / `LoadAllObjects()` | 序列化所有对象数据，调用 `Preload()` 序列化属性 |
| **5. 创建完成** | `FinalizeCreation()` | 连接对象图，标记包为完全加载 |

### 6.4 异步创建

```cpp
FLinkerLoad* FLinkerLoad::CreateLinkerAsync(...)
{
    // 检查是否已存在 Linker
    FLinkerLoad* Linker = FindExistingLinkerForPackage(Parent);
    if (Linker)
    {
        return Linker;
    }

    // 创建新 Linker
    Linker = new FLinkerLoad(Parent, PackagePath, LoadFlags, InstancingContext);
    Parent->SetLinker(Linker);

    if (GEventDrivenLoaderEnabled)
    {
        Linker->CreateLoader(Forward<TFunction<void()>>(InSummaryReadyCallback));
    }

    return Linker;
}
```

## 7. LoadPackage 与 LoadObject

### 7.1 LoadPackage

- `LoadPackage()` — 外部接口，内部调用 `LoadPackageInternal()`
- `LoadPackageInternal()` 流程：
  1. 检查是否已加载
  2. 创建新包（如需要）
  3. 创建 FLinkerLoad
  4. 处理包摘要
  5. 加载导入和导出
  6. 调用 LoadAllObjects()

### 7.2 LoadObject

- 先用 `FindObjectFast()` 查找内存中是否已有对象
- 找不到才触发包加载

## 8. UClass / UBlueprint 生成

- UBlueprint 资产加载时，其 `FLinkerLoad` 处理导出表
- `UBlueprintGeneratedClass` 作为导出项被加载
- 所有字节码、函数映射、属性数据被序列化
- 调用 `PostLoad()` 完成蓝图初始化

## 9. Asset Registry 注册

| 文件 | 位置 |
|---|---|
| `Engine/Source/Runtime/AssetRegistry/Private/AssetRegistry.cpp` | 注册实现 |
| `Engine/Source/Runtime/AssetRegistry/Public/AssetData.h` | FAssetData 定义 |
| `Engine/Source/Runtime/CoreUObject/Private/Misc/AssetRegistryInterface.cpp` | 接口 |

- 包加载后自动被 Asset Registry 跟踪
- `FAssetData` 从包的元数据创建
- 通过 `GetAssetRegistryTags()` 提取标签
- 通过 `FAssetRegistry::RegisterAsset()` 注册
- `FAssetData::GetAsset()` 可按需加载对应的包

```cpp
UPackage* FoundPackage = LoadPackage(nullptr, *PackageName.ToString(), LOAD_None, nullptr, &InstancingContext);
```

## 10. 核心类关系总结

| 类 / 结构 | 职责 |
|---|---|
| `FLinkerLoad` | 从磁盘反序列化 .uasset 包文件 |
| `UPackage` | 资产容器，对应一个 .uasset 文件 |
| `UFactory` | 按资产类型决定如何从文件创建对象 |
| `FAssetData` | 资产的元数据快照（支持延迟加载） |
| `IAssetTypeActions` | 定义资产类型的编辑器行为 |
| `FAssetTools` | 资产操作的统一入口 |

## 11. 一句话总结

编辑器通过 Content Browser 触发资产打开 → AssetTools 路由到对应类型动作 → LoadPackage 创建 FLinkerLoad → Linker 读取 .uasset 的包摘要、导入表、导出表 → 逐个反序列化对象及其属性 → PostLoad 后资产完全就绪。
