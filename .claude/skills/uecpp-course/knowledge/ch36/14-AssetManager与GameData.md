# AssetManager 与 GameData

## 概述

AssetManager 系统负责游戏资产的统一管理，包括物品数据、GameplayEffect 引用的异步/同步加载。

```
UXGRPGAssetManager（继承 UAssetManager）
    ├── 类型化资产加载（GetSubclass / GetOrLoadTypedGameData）
    ├── 全局 GameData 管理（GetGameData）
    └── 同步加载（SynchronousLoadAsset）
        ↓
UXGRPGGameData（继承 UPrimaryDataAsset）
    ├── DamageGameplayEffect_SetByCaller
    ├── HealGameplayEffect_SetByCaller
    └── DynamicTagGameplayEffect
```

## XGRPGAssetManager

### 单例访问

```cpp
UXGRPGAssetManager& UXGRPGAssetManager::Get()
{
    if (UXGRPGAssetManager* Singleton = Cast<UXGRPGAssetManager>(GEngine->AssetManager))
        return *Singleton;
    // 错误处理
}
```

### 资产类型定义

```cpp
class UXGRPGAssetManager : public UAssetManager
{
    static const FPrimaryAssetType PotionItemType;      // 药水类型
    static const FPrimaryAssetType TokenItemType;       // 令牌类型
    static const FPrimaryAssetType EquipmentItemType;   // 装备类型
};
```

### 核心方法

#### 类型化子类加载（GetSubclass）

```cpp
template<typename T>
TSubclassOf<T> GetSubclass(TSoftClassPtr<T> SoftClassPtr, bool bEnsureLoad = false)
{
    if (bEnsureLoad)
    {
        // 同步加载并驻留内存
        return SoftClassPtr.LoadSynchronous();
    }
    // 尝试从已加载资产获取
    if (SoftClassPtr.IsValid())
    {
        UClass* Class = SoftClassPtr.Get();
        if (Class)
            return Class;
        // 异步加载（由 AssetManager 管理）
    }
    return nullptr;
}
```

#### 泛型 GameData 加载（GetOrLoadTypedGameData）

```cpp
template<typename T>
T* GetOrLoadTypedGameData(TSoftObjectPtr<T> DataPtr)
{
    if (DataPtr.IsValid())
    {
        UClass* DataClass = T::StaticClass();
        if (UPrimaryDataAsset** Cached = GameDataMap.Find(DataClass))
        {
            return Cast<T>(*Cached);  // 缓存命中
        }
        // 同步加载并加入缓存
        T* Data = DataPtr.LoadSynchronous();
        GameDataMap.Add(DataClass, Data);
        return Data;
    }
    return nullptr;
}
```

#### 同步加载（SynchronousLoadAsset）

```cpp
UObject* UXGRPGAssetManager::SynchronousLoadAsset(const FSoftObjectPath& AssetPath)
{
    if (AssetPath.IsValid())
    {
        // 先检查是否已加载
        if (UObject* LoadedAsset = AssetPath.ResolveObject())
            return LoadedAsset;
        // 同步流式加载
        return StreamableManager.RequestSyncLoad(AssetPath);
    }
    return nullptr;
}
```

### 资产追踪

`LoadedAssets` 是一个 `TSet<const UObject*>`，线程安全地追踪所有已加载资产，防止重复加载。`AddLoadedAsset` 用于向集合中添加加载记录。

## 初始化流程

```cpp
void UXGRPGAssetManager::StartInitialLoading()
{
    Super::StartInitialLoading();
    // 在此处添加启动时需要的资产预加载
}
```

`StartInitialLoading` 在游戏启动时被 UE 引擎调用，可在此处预加载关键资产。本项目未放入大量预加载逻辑，以保持启动速度。

## XGRPGGameData

### 数据资产

```cpp
class UXGRPGGameData : public UPrimaryDataAsset
{
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Gameplay Effects")
    TSoftClassPtr<UGameplayEffect> DamageGameplayEffect_SetByCaller;    // 伤害 GE
    
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Gameplay Effects")
    TSoftClassPtr<UGameplayEffect> HealGameplayEffect_SetByCaller;      // 治疗 GE
    
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Gameplay Effects")
    TSoftClassPtr<UGameplayEffect> DynamicTagGameplayEffect;             // 动态标签 GE
};
```

`UXGRPGGameData` 作为一个 `UPrimaryDataAsset`，在 Content 目录中创建蓝图实例进行配置。可通过 `XGRPGGameDataPath` 在 `XGRPGAssetManager` 的默认对象中指定路径。

### SetByCaller 用法

`DamageGameplayEffect_SetByCaller` 使用 SetByCaller 机制，允许在运行时通过代码指定伤害数值而非在蓝图中硬编码：

```cpp
// 在 GA 中应用 GE 时动态设置伤害值
FGameplayEffectSpecHandle SpecHandle = ASC->MakeOutgoingSpec(
    UXGRPGAssetManager::Get().GetGameData()->DamageGameplayEffect_SetByCaller,
    1.0f,
    EffectContext);

if (SpecHandle.IsValid())
{
    SpecHandle.Data->SetSetByCallerMagnitude(FGameplayTag::RequestGameplayTag("Data.Damage"), DamageAmount);
    ASC->ApplyGameplayEffectSpecToTarget(*SpecHandle.Data, TargetASC);
}
```

## 资产引用方式对比

| 方式 | 适用场景 | 优势 | 劣势 |
|------|---------|------|------|
| 硬指针（UObject*） | 运行时确定 | 直接在 C++ 中访问 | 无法在蓝图中配置 |
| TSoftClassPtr/TSoftObjectPtr | 蓝图可配置 | 编辑器可视化、延迟加载 | 需额外加载逻辑 |
| UPrimaryDataAsset | 全局配置数据 | 可作为单数据资产管理 | 需要额外设置 |
| FPrimaryAssetId | AssetManager 管理 | 类型化统一管理 | 需要扫描 |

## 注意事项

- `GameDataMap` 缓存已加载的 GameData，避免重复加载
- Soft 引用不会自动加载，需通过 `LoadSynchronous` 或 `RequestSyncLoad` 显式加载
- `StartInitialLoading` 阶段不适合大量同步加载，会延长启动时间
- SetByCaller 的 Data Tag 需在 Gear 中保持一致，否则会导致计算错误
- 打包时 AssetManager 需要扫描 PrimaryAssetTypes 对应的目录
- `StreamableManager.RequestSyncLoad` 是阻塞调用，不要在游戏线程敏感位置使用
