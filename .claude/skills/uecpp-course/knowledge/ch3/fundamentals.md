# 编译构建系统、智能指针、Subsystem 与其他基础概念

## 编译与构建系统

| 文件 | 作用 |
|------|------|
| `.uproject` | 定义项目和模块依赖 |
| `.Build.cs` | 定义模块依赖：`PublicDependencyModuleNames`（公开依赖）、`PrivateDependencyModuleNames`（私有依赖） |
| `.Target.cs` | 定义构建目标（Editor、Game、Client、Server） |

核心依赖模块：`Core`、`CoreUObject`、`Engine`、`InputCore`

**注意**：一旦创建 C++ 类，项目从蓝图项目永久转换为 C++ 项目。

## 智能指针（非 UObject 类型）

对于非 UObject 类型（自定义 struct、非 UObject 类），使用 UE 智能指针体系：

| 类型 | 说明 |
|------|------|
| `TSharedPtr<T>` | 共享所有权，引用计数 |
| `TUniquePtr<T>` | 独占所有权，不可拷贝 |
| `TWeakPtr<T>` | 弱引用，不增加引用计数 |
| `MakeShareable(T*)` | 创建共享指针 |

UObject 对象**不**使用智能指针，由 GC 系统管理。

## Subsystem 模式

UE 提供的现代化单例模式，替代传统 C++ 单例：

| 子系统类型 | 生命周期范围 |
|-----------|-------------|
| `UGameInstanceSubsystem` | 游戏实例级别，跨关卡持久 |
| `UWorldSubsystem` | 世界级别，随关卡加载/卸载 |
| `UEditorSubsystem` | 编辑器级别，仅在 Editor 中有效 |

- 引擎自动管理生命周期（创建、初始化、销毁）
- 访问方式：`GetGameInstance()->GetSubsystem<UMySubsystem>()`
- 优势：引擎托管生命周期，线程安全，编辑器感知

## 其他基础概念

### Forward Declaration（前置声明）

- 在头文件中用 `class` 或 `struct` 前置声明类型，避免包含完整头文件
- 减少编译依赖和编译时间
- 仅在需要使用类型大小或调用成员时才需要包含完整头文件

### WITH_EDITOR / WITH_EDITORONLY_DATA

- 条件编译宏，仅在 Editor 构建中存在
- 用于编辑器专属数据和功能，发布版本自动排除
- 配合 `UPROPERTY(VisibleDefaultsOnly)` + `WITH_EDITORONLY_DATA` 保护编辑器专用属性

### Actor 生命周期

- 构造函数 → BeginPlay → Tick → EndPlay → 销毁
- RootComponent 需在构造函数中创建：`CreateDefaultSubobject<USceneComponent>(TEXT("Root"))`
- `PrimaryActorTick.bCanEverTick` 控制是否允许 Tick

### 未初始化变量的默认值

| 类型 | 默认值 |
|------|--------|
| 数值类型（int32、double 等） | 0 |
| FString | `""`（空字符串） |
| bool | false |
| 指针 | nullptr |

未显式初始化的成员变量不会自动获得预期值，建议总是显式初始化（这是 C++ 规则）。

## 配套代码

| 知识点 | 代码文件 |
|--------|----------|
| Actor 生命周期（构造/BeginPlay/Tick） | [XGBaseActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/001_BaseType/XGBaseActor.h) + [XGBaseActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/001_BaseType/XGBaseActor.cpp) |
| `CreateDefaultSubobject` + `RootComponent` 创建 | [XGClassActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/001_BaseType/XGClassActor.cpp) |
| `NewObject<T>()` 动态创建 UObject | [XGObjectActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/001_BaseType/XGObjectActor.cpp) |
| `StaticClass()` + `GetDefaultObject()` 访问 CDO | [XGClassActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/001_BaseType/XGClassActor.cpp) |
| `AddToRoot()` / `RemoveFromRoot()` GC 保护 | [XGObjectActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/001_BaseType/XGObjectActor.cpp) |
| 未初始化成员变量默认值 | [XGClassActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/001_BaseType/XGClassActor.h) |
| `TSubclassOf` 类引用 | [XGClassActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/001_BaseType/XGClassActor.h) |
