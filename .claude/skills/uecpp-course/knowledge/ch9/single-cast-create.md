# Create 方法与委托替换

## Create 系列方法

除了通过成员变量的 `Bind*` 直接绑定，UE 委托还提供 `Create*` 系列**静态工厂方法**，返回一个独立的委托实例：

```cpp
// CreateUObject — 返回已绑定 UObject 方法的委托实例
auto MyDelegate = FXGSingDelegatePrintLocation::CreateUObject(
    this,
    &AXGSingleDelegateActor::MyFunction
);
```

Create 方法类型与 `Bind*` 一一对应：

| Create 方法 | 对应 Bind 方法 |
|-------------|---------------|
| `CreateUObject` | `BindUObject` |
| `CreateLambda` | `BindLambda` |
| `CreateSP` | `BindSP` |
| `CreateRaw` | `BindRaw` |
| `CreateStatic` | `BindStatic` |

## 委托替换（骚操作）

Create 方法的核心用途——**创建新的委托实例赋值给已有的委托成员变量**，实现绑定替换：

```cpp
// 第一步：初始绑定
SingDelegateReplace.BindUObject(this, &AXGSingleDelegateActor::MyFunction);
// 执行时调用 MyFunction

// 第二步：使用 Create 方法创建新委托并赋值替换
auto MyDelegage = FXGSingDelegatePrintLocation::CreateUObject(
    this,
    &AXGSingleDelegateActor::MyFunction
);
SingDelegateReplace = MyDelegage;  // 替换绑定

// 或者直接用 Lambda 替换
SingDelegateReplace = FXGSingDelegatePrintLocation::CreateLambda([]()
{
    UE_LOG(LogTemp, Warning, TEXT("SingDelegateReplace Execute ---> Lambda"));
});
// 执行时调用 Lambda
```

**原理**：单播委托是值类型，`operator=` 会拷贝替换整个委托对象。第一次 `BindUObject` 设置的绑定被第二次 `CreateLambda` 赋值覆盖。

## 应用场景

- **运行时动态切换行为**：根据游戏状态替换不同的回调逻辑
- **插件/框架设计**：允许外部代码在初始化时注入自定义实现
- **测试 Mock**：用测试委托替换生产委托

## 局限

**Native 委托不能作为 UFUNCTION 参数暴露到蓝图**：

```cpp
UFUNCTION(BlueprintCallable)
void TestDelegate(FXGSingDelegatePrintLocation InDelegate);  // 编译错误
// error: unable to find a class delegate annual extract with a lamb
```

如果需要在蓝图中使用委托，必须使用 Dynamic 系列委托。

> **代码位置**：[XGSingleDelegateActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/012_Delegate/XGSingleDelegateActor.cpp) — `BeginPlay()` 末尾的替换演示
