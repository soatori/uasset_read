# UFUNCTION 宏

将 C++ 函数暴露给蓝图和 UE 反射系统。

## 蓝图相关 Specifiers

| Specifier | 蓝图执行引脚 | 说明 |
|-----------|-------------|------|
| `BlueprintCallable` | 有执行引脚 | C++ 实现，蓝图可调用 |
| `BlueprintPure` | 无执行引脚 | 纯函数，不修改状态 |
| `BlueprintImplementableEvent` | 有执行引脚 | 仅在蓝图中实现，C++ 无默认实现 |
| `BlueprintNativeEvent` | 有执行引脚 | C++ 有默认实现（`_Implementation` 后缀），蓝图可覆写 |

## BlueprintPure vs BlueprintCallable

- BlueprintPure：无执行引脚，类似纯函数，不可修改状态（推荐配合 const 使用）
- BlueprintCallable：有执行引脚，可修改状态
- `ForceBlueprintCallable` 可为 const 函数强制显示执行引脚
- **陷阱**：`BlueprintPure = false`（拼写错误，应为 `BlueprintPure = false` 或 `BlueprintPure`）会导致 Pure 不生效，退化为 BlueprintCallable 行为

```cpp
UFUNCTION(BlueprintPure)
float BlueprintPureFunction();

UFUNCTION(BlueprintCallable)
float BlueprintCallableFunction();

UFUNCTION(BlueprintCallable)
int32 BlueprintCallableConstFunction() const;

// 拼写错误！fasle → false，退化为 Callable 行为（仍是 const 函数，但显示执行引脚）
UFUNCTION(BlueprintPure = fasle)
int32 BlueprintPureFalseFunction() const;
```

参考实现：[XGFunctionActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/002_UFunction/XGFunctionActor.h)

## BlueprintImplementableEvent vs BlueprintNativeEvent

| 特性 | BlueprintImplementableEvent | BlueprintNativeEvent |
|------|---------------------------|---------------------|
| C++ 默认实现 | 无 | 有（`_Implementation` 后缀） |
| 蓝图覆写 | 必须实现 | 可选覆写 |
| 调用方式 | 直接调用函数名 | 直接调用函数名，反射系统自动处理优先顺序 |

```cpp
// 头文件声明
UFUNCTION(BlueprintCallable, BlueprintImplementableEvent)
int32 BPOnlyMustOverride(float InMyFloat);

UFUNCTION(BlueprintCallable, BlueprintNativeEvent)
int32 BPAndCPPMustOverride(float InMyFloat);

// C++ 实现（仅 BNE 需要 _Implementation）
int32 AXGFunctionActor::BPAndCPPMustOverride_Implementation(float InMyFloat)
{
    return InMyFloat + 10;
}
```

参考实现：[XGFunctionActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/002_UFunction/XGFunctionActor.h) + [XGFunctionActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/002_UFunction/XGFunctionActor.cpp)

## 网络相关 Specifiers

| Specifier | 说明 |
|-----------|------|
| `Client` | 只在客户端执行 |
| `Server` | 只在服务器执行 |
| `NetMulticast` | 在所有机器上执行 |
| `Reliable` | 可靠传输，保证到达 |
| `Unreliable` | 不可靠传输，不保证到达（适合频发数据如位置同步） |

网络 specifiers 通常与 `Validate` 一起使用（验证客户端调用的合法性）。

## 其他 Specifiers

| Specifier | 说明 |
|-----------|------|
| `Exec` | 可在控制台输入命令调用 |
| `CallInEditor` | 在编辑器细节面板中显示为按钮 |
| `Const` | 标记函数不修改对象状态 |
| `ForceBlueprintCallable` | 强制函数在蓝图中可调用（配合 Const 使用） |

## 参数传递

| 写法 | 蓝图行为 | 说明 |
|------|---------|------|
| `const Type&` | 输入参数 | 标准输入传递 |
| `Type&` | 输出参数 | 蓝图会显示为输出引脚 |
| `TArray<Type>&`（不加 UPARAM(ref)） | 拷贝传入 | C++ 中的数组修改不会影响蓝图侧 |
| `UPARAM(ref) TArray<Type>&` | 引用传递 | C++ 中的修改会反映回蓝图 |

```cpp
// 正确：引用传递，修改会反映回蓝图
bool AXGFunctionActor::GetBodyArray(TArray<int32>& InNum)
{
    InNum.Add(322);
    return true;
}

// 错误：值传递，修改不会影响蓝图侧
bool AXGFunctionActor::GetBodyArray_Error(TArray<int32> InNum)
{
    InNum.Add(322);
    return true;
}
```

参考实现：[XGFunctionActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/002_UFunction/XGFunctionActor.cpp)
