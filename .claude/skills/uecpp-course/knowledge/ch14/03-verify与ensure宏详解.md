# verify 与 ensure 宏详解

verify 和 ensure 是 check 系列的重要补充，提供了 Shipping 构建中保留逻辑（verify）和"失败不崩溃"（ensure）两种能力。

## verify —— Shipping 中保留副作用的断言

### 行为差异

verify 和 check 在 Debug/Development 中的行为完全一致（失败时停止执行）。**关键差异在 Shipping 中：**

- **check**：参数表达式完全**不编译**
- **verify**：参数表达式**仍然执行**，但不检查结果

### 示例

```cpp
void AXGAssertActor::VerifyMana()
{
    verify(ModifyMana() > 0);
}

int32 AXGAssertActor::ModifyMana()
{
    Mana -= 20;
    return Mana;
}
```

- Debug/Development 中：`ModifyMana()` 执行，检查返回值是否大于 0，小于则触发断言
- Shipping 中：`ModifyMana()` **仍然执行**（`Mana -= 20` 生效），但不检查结果

### 使用场景

当断言条件中的函数调用**必须产生副作用**时使用 verify：

- 状态修改类函数的返回值检查
- 资源分配函数的成功与否检查
- 文件操作返回值检查

## ensure —— 失败不崩溃的断言

### 行为特征

```cpp
void AXGAssertActor::AttackEnemeyGood(AActor* InActor)
{
    ensure(InActor != nullptr);

    AXGAssertActor* MyAsserActor = Cast<AXGAssertActor>(InActor);
    if (MyAsserActor)
    {
        MyAsserActor->Health -= 10;
        // 不要这样子使用断言
        ensure(ModifyHealth());
    }
}
```

- ensure 失败时**记录日志但不停止执行**
- **只记录第一次失败**：同一条 ensure 在单次运行中只触发一次日志输出
- 返回布尔值，可在 if 条件中使用

### ensureMsgf —— 带自定义消息的 ensure

```cpp
void AXGAssertActor::EnsuerVersion(bool bInVersion)
{
    if (ensureMsgf(bInVersion, TEXT("当前版本不正确")))
    {
        UE_LOG(LogTemp, Warning, TEXT("版本正确"));
    }
}
```

- 第二个参数是自定义错误信息（TEXT 格式）
- 返回布尔值，可以嵌套在 if 表达式中使用
- 使用时注意：**ensureMsgf 本身包含了 if 检查逻辑**，不要在外部再套一层条件

### 适用场景

- **非关键路径检查**：UI 数据刷新、非核心资源加载
- **预期可能失败但不应崩溃**：网络请求、文件读取
- **发布版本的兜底检查**：即使出问题也要让游戏继续运行

## 核心陷阱：不要把业务逻辑放到断言参数中

### 错误示例

```cpp
// 错误！ModifyHealth() 在 Shipping 中不会执行
ensure(ModifyHealth());
```

`ModifyHealth()` 修改了 `Health += 10` 并返回 true。但使用 `ensure` 包裹意味着：

- Debug 中：`ModifyHealth()` 执行 → Health 增加 → ensure 通过
- Shipping 中：**ensure 被移除** → `ModifyHealth()` **不执行** → Health 不增加
- 结果：Shipping 和 Debug 中 Health 值不同，Bug 无法在开发阶段复现

### 正确做法

```cpp
// 先执行函数
ModifyHealth();
// 再单独断言结果
check(Health > 0);
```

### verify 也需注意

即使使用 `verify`，也要确保理解它在 Shipping 中的行为——表达式执行但不检查结果：

```cpp
verify(SomeFunction());  // Shipping 中 SomeFunction() 执行但结果不检查
```

如果你需要在 Shipping 中也检查结果，应用 if + 日志，而非断言。

## 对比总结

| 宏 | Debug 失败行为 | Shipping 表达式 | Shipping 失败检查 | 典型场景 |
|---|---------------|----------------|------------------|---------|
| check | 停止执行 | 不编译 | 无 | 空指针、类型检查 |
| verify | 停止执行 | 执行 | 无 | 有副作用的返回值检查 |
| ensure | 记录日志（首次），继续执行 | 执行 | 可选 | 非关键路径检查 |

## 配套代码

- [XGAssertActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/017_Assert/XGAssertActor.cpp) — verify/ensure/ensureMsgf 完整实现
