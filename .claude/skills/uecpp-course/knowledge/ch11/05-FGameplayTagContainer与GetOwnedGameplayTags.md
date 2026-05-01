# FGameplayTagContainer 与 GetOwnedGameplayTags

## FGameplayTagContainer 基本操作

```cpp
// 声明容器（支持 Blueprint 暴露）
UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = "XG")
FGameplayTagContainer MyTagContainer;

UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = "XG")
FGameplayTagContainer MyStatusTagContainer;
```

### 添加标签

```cpp
// 通过静态宏变量添加
MyTagContainer.AddTag(XX_Mode_Idle);

// 通过运行时字符串查找添加
MyTagContainer.AddTag(FGameplayTag::RequestGameplayTag(TEXT("XG")));

// 合并另一个容器
MyTagContainer.AppendTags(AnotherContainer);
```

### 查询标签

```cpp
Container.HasTag(SingleTag);                 // 概念匹配
Container.HasAny(OtherContainer);             // OR 匹配
Container.HasAll(OtherContainer);             // AND 匹配
Container.HasTagExact(SingleTag);             // 精确匹配
Container.HasAnyExact(OtherContainer);        // 精确 OR
Container.HasAllExact(OtherContainer);        // 精确 AND
```

## GetOwnedGameplayTags 模式

### 接口定义

`IGameplayTagAssetInterface` 提供了标准的标签访问接口：

```cpp
class AXGTagActor : public AActor, public IGameplayTagAssetInterface
{
    virtual void GetOwnedGameplayTags(FGameplayTagContainer& TagContainer) const override;
};
```

### 聚合模式

多个标签容器合并为一个统一的查询接口，适合大型项目中不同子系统（库存、状态、邮件、角色）各自管理自己的标签：

```cpp
void AXGTagActor::GetOwnedGameplayTags(FGameplayTagContainer& TagContainer) const
{
    TagContainer.AppendTags(MyTagContainer);
    TagContainer.AppendTags(MyStatusTagContainer);
}
```

### 完整代码

见 [XGTagActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/014_Tag/XGTagActor.h) 和 [XGTagActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/014_Tag/XGTagActor.cpp)。

## Blueprint 叠加问题

### 场景

C++ 基类在 `BeginPlay` 中添加了标签，但 Blueprint 子类通过 `GetOwnedGameplayTags` 覆盖可能无法立即获取到 C++ 添加的标签。

### 原因

`Super::BeginPlay()` 内部会触发 `BlueprintImplementableEvent`，导致 Blueprint 端的 `BeginPlay` 在 **C++ 端代码执行之前** 运行。

```cpp
void AXGTagActor::BeginPlay()
{
    Super::BeginPlay();   // ← 这里会触发 Blueprint BeginPlay

    // ↓ 以下代码在 Blueprint BeginPlay 之后才执行
    MyTagContainer.AddTag(FGameplayTag::RequestGameplayTag(TEXT("XG")));
    MyTagContainer.AddTag(XX_Mode_Idle);
}
```

### 解决方案

1. 将标签添加代码移到 `Super::BeginPlay()` 之前
2. 在 Blueprint 中使用 `Delay` 节点延迟一帧再访问标签
