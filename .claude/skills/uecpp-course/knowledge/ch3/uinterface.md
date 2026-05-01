# UINTERFACE 宏

UE 接口采用**双类模式**：一个 `U` 前缀的反射元数据类，和一个 `I` 前缀的实现类。

## 双类模式声明

```cpp
// U 类（反射元数据类，空的）
UINTERFACE(MinimalAPI)
class UXGHealthInterface : public UInterface
{
    GENERATED_BODY()
};

// I 类（实现类，包含实际虚函数）
class XGSAMPLEDEMO_API IXGHealthInterface
{
    GENERATED_BODY()

public:
    UFUNCTION(BlueprintCallable, BlueprintImplementableEvent)
    bool IsAlive();

    UFUNCTION(BlueprintCallable, BlueprintNativeEvent)
    bool IsDeath();
};
```

## 实现接口

```cpp
UCLASS()
class AInterfaceActor : public AActor, public IXGHealthInterface, public IXGActorTypeInterface
{
    GENERATED_BODY()

    bool IsDeath_Implementation() override;
};
```

## 接口判定

| 方式 | 说明 |
|------|------|
| `Cast<IXGHealthInterface>(Obj)` | C++ 接口转换，若未实现接口则返回 nullptr |
| `Obj->GetClass()->ImplementsInterface(UXGHealthInterface::StaticClass())` | 运行时检查 |
| `Obj->Implements<UXGHealthInterface>()` | 模板简化写法 |

```cpp
void AInterfaceActor::BeginPlay()
{
    Super::BeginPlay();

    // 方式 1：通过 GetClass 运行时检查
    bool bIsImplemented = this->GetClass()->ImplementsInterface(UXGHealthInterface::StaticClass());

    // 方式 2：模板简化写法
    bIsImplemented = this->Implements<UXGHealthInterface>();

    // 方式 3：Cast 接口指针
    IXGHealthInterface* HealthObj = Cast<IXGHealthInterface>(this);

    // 从接口 Cast 回 Actor
    AActor* Actor = Cast<AActor>(HealthObj);
}
```

参考实现：[InterfaceActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/003_UInterface/InterfaceActor.cpp)

## 注意事项

- 接口中**不允许** UPROPERTY
- BlueprintImplementableEvent 在接口中不能为 virtual
- `UINTERFACE(Blueprintable)` 允许蓝图类继承该接口
- 引擎预定义接口：`TeamAgentInterface`、`AbilitySystemInterface`、`GameplayTagAssetInterface` 等
- 从接口类型 Cast 到 AActor 是允许的（如果原对象是 Actor 子类）
