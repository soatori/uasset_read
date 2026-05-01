# 蓝图交互与 BlueprintNativeEvent

## 概述

UE 的 C++ 代码可以通过 `BlueprintNativeEvent` 和 `UPROPERTY(EditAnywhere)` 与蓝图进行双向交互。C++ 提供默认实现和编辑器可编辑属性，蓝图子类可覆盖函数或修改属性值，无需重新编译 C++。

## BlueprintNativeEvent 规范

`UFUNCTION(BlueprintNativeEvent)` 是 C++ 定义**可被蓝图覆盖**的函数的标准方式。

### 声明

```cpp
UFUNCTION(BlueprintNativeEvent)
void CountdownHasFinished();
```

| 特性 | 说明 |
|------|------|
| C++ 默认实现 | 函数名加 `_Implementation` 后缀 |
| 蓝图覆盖 | Blueprint 可直接覆盖，无需调用父函数（与 BlueprintImplementableEvent 不同） |
| 父函数调用 | 蓝图中可选择是否 Call Parent Function |
| 事件节点 | 蓝图中生成事件节点（Event CountdownHasFinished），而非函数节点 |

### C++ 实现

```cpp
void AXGCountDownTimerActor::CountdownHasFinished_Implementation()
{
    CountdownText->SetText(FText::FromString(TEXT("GO!")));
}
```

规则：`_Implementation` 后缀是强制约定，否则编译器报错。

### 蓝图覆盖

1. 创建蓝图子类（继承自 `AXGCountDownTimerActor`）
2. 在 Event Graph 中看到 **Event CountdownHasFinished** 节点
3. 可以在事件中添加粒子特效、声音播放、切换关卡等逻辑
4. 如需要 C++ 默认逻辑，在蓝图中调用 **Parent: CountdownHasFinished**

## BlueprintNativeEvent vs BlueprintImplementableEvent

| 特性 | BlueprintNativeEvent | BlueprintImplementableEvent |
|------|---------------------|---------------------------|
| C++ 默认实现 | 必须提供（`_Implementation`） | 不提供 |
| 蓝图必须实现 | 否 | 是（否则运行时空函数） |
| 调用父类 | 蓝图中可选 | 不适用 |
| 适用场景 | C++ 提供基础行为，蓝图扩展 | 纯蓝图定义，C++ 仅声明接口 |

## UPROPERTY(EditAnywhere) 编辑器暴露

```cpp
UPROPERTY(EditAnywhere)
int32 CountdownTime;
```

`EditAnywhere` 使属性在以下位置可见：

| 位置 | 可修改 |
|------|--------|
| 关卡中放置的 Actor 实例 | Details 面板 |
| 蓝图子类的 Defaults | Class Defaults |
| 蓝图子类实例 | Details 面板 |

默认值 `CountdownTime = 3` 在构造函数中设置，每次创建实例时作为初始值。编辑器中对 `CountdownTime` 的修改不会影响 C++ 默认值，只影响当前实例或蓝图子类的默认值。

## 完整工作流

C++ → 蓝图的双向协作：

```
┌─ C++ AXGCountDownTimerActor ─────────────────┐
│  CountdownTime (EditAnywhere, 默认 3)         │
│  SetTimer -> AdvanceTimer (每秒递减)          │
│  CountdownTime < 1 -> ClearTimer              │
│  CountdownHasFinished_Implementation() -> GO! │
└──────────────┬────────────────────────────────┘
               │ 继承
┌──────────────▼────────────────────────────────┐
│  BP_MyCountDownTimer (蓝图子类)               │
│  - CountdownTime 可改为 5 / 10 / 任意值       │
│  - Event CountdownHasFinished:                 │
│    ╰─ SpawnEmitter / PlaySound / OpenLevel     │
└───────────────────────────────────────────────┘
```

优势：核心计时逻辑完全在 C++ 中实现，蓝图只需关注表现层定制（特效、音效、关卡切换等），无需关心底层定时器管理。

## 代码参考

- [XGCountDownTimerActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/011_Timer/XGCountDownTimerActor.h)
- [XGCountDownTimerActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/011_Timer/XGCountDownTimerActor.cpp)
