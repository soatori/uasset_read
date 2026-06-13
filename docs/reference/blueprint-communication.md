# 蓝图通信机制参考

> **UE 源码对照**: `Runtime/Engine/Classes/Engine/`, `Editor/BlueprintGraph/Classes/K2Node_*.h`
> **最后对齐**: UE 5.7 (2026-06)

## 概述

蓝图间/蓝图与 C++ 间的通信有四种主要模式。解析器需要识别这些模式，以在输出中提供语义信息。

---

## 1. 直接调用（Direct Call）

### 概念

一个蓝图直接调用另一个蓝图的函数或访问其变量。最常见、最直接的通信方式。

### .uasset 中的识别

| 标识 | 说明 |
|------|------|
| `K2Node_CallFunction` | 函数调用节点 |
| `K2Node_VariableGet/Set` | 变量读/写节点 |
| `K2Node_Message` | 接口消息调用 |
| `FMemberReference.member_parent` | 引用目标类路径 |

### 序列化特征

```
FMemberReference {
    member_name: "FunctionName"      // 函数/变量名
    member_parent: "/Game/Path/BP"   // 目标蓝图路径
    member_guid: FGuid               // 引用 GUID
}
```

### 解析器输出示例

```
Event.BeginPlay → CallFunction.GetPlayerPawn() → VariableSet.TargetPlayer
```

---

## 2. 委托（Delegate / Dispatcher）

### 概念

发送方广播事件，接收方绑定回调。解耦发送方和接收方，支持一对多通信。

### 委托类型

| 类型 | 说明 | 蓝图对应 |
|------|------|---------|
| **单播委托** | 一次只能绑定一个回调 | `AssignDelegate` 节点 |
| **多播委托** | 可绑定多个回调 | `AddDelegate` + `CallDelegate` |
| **事件委托** | 仅本类可广播 | `K2Node_Event` + `K2Node_CallDelegate` |

### .uasset 中的识别

| K2Node 类型 | 语义 |
|-------------|------|
| `K2Node_CallDelegate` | 广播委托（触发所有绑定回调） |
| `K2Node_AddDelegate` | 动态绑定委托回调 |
| `K2Node_AssignDelegate` | 赋值单播委托 |
| `K2Node_RemoveDelegate` | 解绑委托回调 |
| `K2Node_ClearDelegate` | 清除所有绑定 |
| `K2Node_CreateDelegate` | 创建委托绑定引用 |

### 委托属性在蓝图变量中的标记

```cpp
// UPROPERTY 声明
UPROPERTY(BlueprintAssignable)
FOnHealthChanged OnHealthChanged;

// 序列化为 CPF_BlueprintAssignable (0x10000000)
```

### 序列化特征

委托绑定在 `.uasset` 中存储为动态委托绑定数组：

```
FDelegateProperty (Multicast):
  InvocationList: Array<FScriptDelegate> {
      Object: PackageIndex (指向绑定对象)
      FunctionName: FName (回调函数名)
  }
```

### 解析器输出示例

```
Event.OnHealthChanged → CallDelegate(Health=NewHealth)
  → Bind: BP_Player.ReceiveHealthChanged
  → Bind: BP_UI.UpdateHealthBar
```

---

## 3. 蓝图接口（Blueprint Interface）

### 概念

定义一组函数签名，多个不相关的蓝图实现这些函数。调用方通过接口引用调用，无需知道具体实现类。类似 C++ 的虚函数/Java 的接口。

### .uasset 中的识别

| 标识 | 说明 |
|------|------|
| `K2Node_Message` | 接口消息调用节点 |
| `UBlueprintInterface` | 接口资产类型（ClassFlag: `CLASS_Interface`) |
| `Implements` 属性 | 类实现的接口列表 |

### 接口资产结构

蓝图接口资产（`.uasset`）包含：
- 接口函数声明（无实现）
- `FunctionFlags` 包含 `FUNC_BlueprintEvent`

### 实现识别

蓝图类通过以下属性声明实现的接口：

```
ClassDefaultObject:
  Interfaces: Array<FBlueprintInterface> {
      ClassExport: PackageIndex → 接口 UClass
  }
```

### K2Node_Message 序列化

```
K2Node_Message {
    message_name: "InterfaceFunction"   // 接口函数名
    message_target: Target Object        // 接口引用目标
    b_is_pure: bool                      // 是否纯调用
}
```

### 解析器输出示例

```
K2Node_Message: IDamageable.TakeDamage(Amount=50.0)
  → 目标: BP_Enemy (implements IDamageable)
  → 运行时动态分派到实际实现
```

---

## 4. 类型转换（Cast）

### 概念

将对象引用从父类转换为子类。转换成功则返回子类引用，失败则返回 null。常用于从通用引用（如 `Actor`）获取具体蓝图类型的访问权限。

### .uasset 中的识别

| K2Node 类型 | 语义 |
|-------------|------|
| `K2Node_DynamicCast` | UObject 动态类型转换 |
| `K2Node_ClassDynamicCast` | 从 Class 引用转换 |
| `K2Node_CastByteToEnum` | Byte → Enum 转换 |

### Cast 节点引脚

```
K2Node_DynamicCast:
  输入引脚:
    Object (ObjectReference) — 要转换的对象
  输出引脚:
    As<ClassName> (<ClassName>) — 转换成功的引用
    bSuccess (bool) — 转换是否成功
  执行引脚:
    then (exec) — 转换成功后继续执行
    cast failed (exec) — 转换失败后继续执行
```

### 序列化特征

```
K2Node_DynamicCast {
    target_type: PackageIndex → 目标 UClass
    b_is_ref_cast: bool          // 是否为引用转换（非拷贝）
    result_type: FName           // 目标类型名
}
```

### 解析器输出示例

```
Cast<BP_PlayerCharacter>(ActorRef)
  → Success: UseAsPlayerCharacter()
  → Failed: HandleInvalidCast()
```

---

## 通信模式对比

| 特性 | 直接调用 | 委托 | 接口 | Cast |
|------|---------|------|------|------|
| **耦合度** | 高（需知道目标类） | 低（广播解耦） | 低（通过接口） | 高（需知道目标类） |
| **方向** | 单向 | 一对多 | 多态 | 类型安全访问 |
| **运行时开销** | 低 | 中（委托列表遍历） | 中（动态分派） | 低 |
| **网络支持** | 需 RPC 标记 | 不支持 | 不支持 | 不支持 |
| **解析器识别** | CallFunction | CallDelegate | Message | DynamicCast |
| **CPF 标志** | — | CPF_BlueprintAssignable | — | — |

---

## 蓝图变量暴露与 RPC

### 网络复制标记

蓝图变量可通过 `Replicated` 标记实现网络同步：

```
UPROPERTY(Replicated)
float Health;

UPROPERTY(ReplicatedUsing=OnRep_Health)
float Health;
```

**序列化标识**：
- `CPF_Net` (0x20): 属性参与网络复制
- `CPF_RepNotify` (0x100000000): 复制后触发 `OnRep_` 函数

### RPC 函数标记

蓝图函数可通过 RPC 标记指定执行端：

```cpp
// FunctionFlags 中的网络标记
FUNC_Net          = 0x00004000,  // 网络函数
FUNC_NetClient    = 0x01000000,  // 仅在客户端执行
FUNC_NetServer    = 0x04000000,  // 仅在服务器执行
FUNC_NetMulticast = 0x08000000,  // 所有端执行
```

**解析器识别**：在函数 `FunctionFlags` 中检查上述位。

---

## 通信模式识别流程

解析器可通过以下流程识别蓝图中的通信模式：

```
遍历 UEdGraph 中的节点:
  ├─ K2Node_CallFunction
  │   ├─ member_parent 指向外部蓝图 → 直接调用
  │   └─ FunctionFlags & FUNC_Net → RPC 调用
  ├─ K2Node_CallDelegate → 委托广播
  ├─ K2Node_AddDelegate → 委托绑定
  ├─ K2Node_Message → 接口调用
  └─ K2Node_DynamicCast → 类型转换
      └─ 后续连接的 CallFunction → 转换后访问
```

---

## 源码引用

- `Editor/BlueprintGraph/Classes/K2Node_CallDelegate.h` — 委托广播节点
- `Editor/BlueprintGraph/Classes/K2Node_AddDelegate.h` — 委托绑定节点
- `Editor/BlueprintGraph/Classes/K2Node_Message.h` — 接口消息节点
- `Editor/BlueprintGraph/Classes/K2Node_DynamicCast.h` — 类型转换节点
- `Runtime/Engine/Classes/Engine/Blueprint.h` — 蓝图类定义
- `Runtime/CoreUObject/Public/UObject/ObjectMacros.h` — CPF_BlueprintAssignable 等
