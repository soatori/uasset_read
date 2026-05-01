# UObject 体系

UObject 是所有 UE 反射对象的基类。其继承链为 `UObject → UObjectBaseUtility → UObjectBase`，但日常开发只需关注 UObject。

## 创建方式

| 方式 | 使用场景 | 说明 |
|------|----------|------|
| `NewObject<T>()` | 运行时动态创建 UObject | **必须使用**，替代 C++ `new` |
| `CreateDefaultSubobject<T>()` | 构造函数中创建默认子对象 | 仅在 Actor/ActorComponent 构造函数中使用 |
| `new` / `delete` | — | **禁止使用**，会导致内存泄漏或双重 GC |

## 构造函数约束

- 必须提供默认构造函数（无参），否则 UHT 无法生成反射代码
- 允许 `const FObjectInitializer&` 参数形式
- 不要在默认构造函数中写复杂逻辑——初始化工作放在 `BeginPlay` 或自定义 Init 函数中

## CDO（Class Default Object）

每个 UCLASS 都有一个全局唯一的 CDO，由类的默认构造函数在加载时生成，之后不再修改。

```cpp
// 访问 CDO
int32 AXGClassActor::GetMyCDOMoney()
{
    UClass* XGClass = AXGClassActor::StaticClass();
    UObject* MyObject = XGClass->GetDefaultObject();
    AXGClassActor* MyCDO = Cast<AXGClassActor>(MyObject);
    if (MyCDO)
    {
        return MyCDO->Money;
    }
    return -1;
}
```

参考实现：[XGClassActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/001_BaseType/XGClassActor.cpp)

构造函数中初始化的优先级：**声明默认值 → 构造函数初始化列表 → 构造函数体内赋值**。最终值写入 CDO。

## GC（Garbage Collection）

- UObject 由引擎自动管理内存
- 被 `UPROPERTY()` 标记的引用指针作为 GC 的"根"，保护对象不被回收
- 未被任何 UPROPERTY 引用的对象将在下次 GC 运行时被回收
- 使用 `IsValid()` 检查对象是否为空或已被 GC 回收

### GC 相关操作

| 操作 | 说明 |
|------|------|
| `IsValid(Obj)` | 检查对象非空且未被标记为待回收 |
| `AddToRoot()` | 将对象添加到 GC Root 集合保护起来（慎用） |
| `RemoveFromRoot()` | 从 GC Root 集合移除 |
| `MarkAsGarbage()` | 主动标记对象为待回收（原 `MarkPendingKill()`） |

```cpp
// GC 保护示例
void AXGObjectActor::InitMyXGObject()
{
    MyXGObject = NewObject<UXGObjectObject>();
    // MyXGObject->AddToRoot();  // 紧急保护，防止被 GC
    // MyXGObject->RemoveFromRoot();
}
```

参考实现：[XGObjectActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/001_BaseType/XGObjectActor.cpp)

## UObject 能力总结

| 能力 | 说明 |
|------|------|
| 序列化/反序列化 | 通过 UPROPERTY 控制的自动序列化 |
| 运行时类型识别 | `IsA<T>()`、`Cast<T>()` |
| 网络复制 | 配合 UPROPERTY(Replicated) 使用 |
| 编辑器集成 | 属性面板、蓝图节点 |
| GC 自动内存管理 | 基于 UPROPERTY 引用的可达性分析 |
| 反射元数据访问 | 运行时获取类/属性/函数信息 |
