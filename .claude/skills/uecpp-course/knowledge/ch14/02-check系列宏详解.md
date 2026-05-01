# check 系列宏详解

check 系列是 UE 中使用最频繁的断言宏，涵盖从基础检查到特殊场景的多个变体。

## check —— 基础断言

```cpp
void AXGAssertActor::AttackEnemey(AActor* InActor)
{
    check(InActor != nullptr);
    AXGAssertActor* MyAsserActor = CastChecked<AXGAssertActor>(InActor);
    MyAsserActor->Health -= 10;
}
```

- 参数为布尔表达式
- 表达式为 `false` 时触发断言失败，停止执行
- Shipping 构建中完全移除
- 适用：空指针检查、参数合法性校验

## CastChecked —— check + 类型转换

```cpp
AXGAssertActor* MyAsserActor = CastChecked<AXGAssertActor>(InActor);
```

- 等价于 `check(Cast<AXGAssertActor>(InActor) != nullptr)` + 转换
- 转换失败时触发断言
- Shipping 构建中行为等同于 `static_cast`（无检查，直接转换）

## checkf —— 带格式化信息的 check

```cpp
checkf(Value > 0, TEXT("值异常: %d"), Value);
```

- 第一个参数是条件
- 后续参数是 UE_LOG 风格的格式化字符串
- 断言失败时把自定义信息输出到日志和控制台
- 在 Development 构建中有效

## checkNoEntry —— "不应到达的代码路径"

```cpp
void AXGAssertActor::CheckNoEnry(EXGAssertType InXGAssertType)
{
    switch (InXGAssertType)
    {
    case EXGAssertType::None:
        checkNoEntry();        // None 不应出现
        break;
    case EXGAssertType::Left:
        // ...
        break;
    case EXGAssertType::Max:
        checkNoEntry();        // Max 不是有效值
        break;
    }
}
```

- 不带参数，直接表示"代码不应执行到这里"
- 典型场景：
  - switch 中不该出现的枚举值
  - 函数中不应执行到的默认分支
  - 不应该被调用的虚函数路径

## checkCode —— 只在 Debug 中执行的代码块

```cpp
void AXGAssertActor::CheckNoCode(bool bInAllRight)
{
    checkCode(
        if (bInAllRight)
        {
            UE_LOG(LogTemp, Error, TEXT("一切正常"));
        }
        else
        {
            UE_LOG(LogTemp, Error, TEXT("一切不正常"));
        }
    );
}
```

- 包裹一段代码块，该代码块**只在 Debug/Development 中编译**
- Shipping 构建中整个代码块被移除
- 适用：开发阶段的日志记录、额外的校验逻辑
- **不要**把业务逻辑放到 checkCode 中

## checkSlow —— 仅在 Debug 模式下生效

```cpp
void AXGAssertActor::CheckSlowf(bool bInAllRight)
{
    checkSlow(bInAllRight);
}
```

- 行为与 check 相同，但只在 **DebugGame/DebugEditor** 中生效
- Development 构建**也不执行** checkSlow
- 适用：开销较大的校验逻辑（如全量容器遍历检查），只在调试时启用

## check 系列的选择矩阵

| 宏 | Shipping 行为 | 适用场景 |
|------|-------------|---------|
| check | 不编译 | 基础空指针、参数检查 |
| CastChecked | 裸转换 | 确定类型的转型 |
| checkf | 不编译 | 需要自定义错误信息的检查 |
| checkNoEntry | 不编译 | 不可达代码路径标记 |
| checkCode | 不编译 | 调试阶段的额外日志/校验 |
| checkSlow | 不编译 | 大开销的校验（仅 Debug） |

## 配套代码

- [XGAssertActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/017_Assert/XGAssertActor.cpp) — check/CastChecked/checkNoEntry/checkCode/checkSlow 完整实现
