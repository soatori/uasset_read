# 0.4.1-dev 超级计划：蓝图输出质量提升 — 从骨架到可读 C++

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将蓝图解析输出从"结构骨架"提升到"可读 C++ 类"级别，使 AI 代理无需 UE 编辑器即可理解蓝图的功能实现。

**Architecture:** 三层递进增强：(1) 修复报告中的解析错误 → (2) 增强 Kismet 反编译器输出完整 C++ 函数体 → (3) 增强 C++ 骨架生成器输出可读头文件。

**Tech Stack:** Python 3.10+, pytest, dataclasses, CUE4Parse 参考实现

**全局约束:**
- 测试命令: `python -m pytest tests/ -v --tb=short`
- 临时文件放在 `temp/` 目录
- 每个 Task 提交一次
- 零运行时依赖
- 输出质量目标：生成的 C++ 代码可被人类和 AI 直接理解

---

## 背景：为什么需要这个计划

### 当前输出质量差距

```cpp
// ❌ 当前输出（函数引用未解析，控制流退化为 goto）
void Move(double LeftRight, double ForwardBackward) {
    Function_123(this, LeftRight);  // 占位符
}

// ✅ 期望输出（完整可读 C++）
void Move(double LeftRight, double ForwardBackward) {
    FVector Direction = GetActorForwardVector();
    AddMovementInput(Direction, ForwardBackward);
}
```

### 根因分析

| 差距 | 根因 | 影响 |
|------|------|------|
| `Function_123` 占位符 | StackNode 未通过 linker 解析为函数名 | 函数调用不可读 |
| goto Label_N 退化 | 跳转标签预扫描未实现 | 控制流不可读 |
| 属性显示 ParseError | tag.size 不匹配 + skip 不完整 | 类结构不完整 |
| 事件函数无实现 | Kismet 反编译器只输出骨架 | 功能逻辑缺失 |

### 参考实现

- **CUE4Parse**: `BlueprintDecompilerUtils.GetLineExpression()` — 1700+ 行 Kismet→C++ 翻译
- **UE 编辑器**: "View C++ Header" — 基于 `UBlueprintGeneratedClass` + `UClassCookedMetaData`

---

## Phase 1: 解析错误修复（已完成 ✅）

> 已在 0.4.0-dev 分支完成，验证通过。

| Task | 状态 | 说明 |
|------|------|------|
| `read_validated_count` ValueError → ParseError | ✅ | smart continue 捕获数组越界 |
| preload 循环 try/except 容错 | ✅ | 单个 export 失败不中断整体 |
| `should_skip_export_for_tolerant_parsing` class_name 匹配 | ✅ | Niagara 等资产正确跳过 |
| `SKIP_CLASS_NAMES` 精确匹配集合 | ✅ | 60+ 个不兼容 class |

---

## Phase 2: Kismet 反编译器增强 — 函数引用解析（P0）

> **目标**: 将 `Function_123` 占位符替换为 `ClassName::FuncName` 完整签名。

### Task 2.1: 实现 StackNode → 函数名解析

**文件**: `src/uasset_read/kismet/translator.py`

**当前问题**:
```python
# translator.py 第 841-857 行
stack_node = expr.StackNode  # 仅 int 索引
class_name = f"Function_{stack_node}"  # 占位符
```

**修复方案**:
1. 在 `translate_expression` 中传递 linker 上下文
2. 通过 `linker.resolve_package_index(PackageIndex(stack_node))` 获取 UObjectInstance
3. 从 instance 中提取 `object_name` 和 `object_class`
4. 格式化为 `ClassName::FuncName`

**参考**: CUE4Parse `UClass.cs` 第 227-335 行

**验收标准**:
- `Function_123` → `UKismetMathLibrary::Add_IntInt`（数学库函数）
- `Function_456` → `AddMovementInput`（蓝图自定义函数）
- 无法解析时保留 `Function_N` 占位符（不崩溃）

### Task 2.2: 实现函数签名缓存

**文件**: `src/uasset_read/kismet/translator.py`

**目标**: 构建 `StackNode → (class_name, func_name)` 映射表

**方案**:
1. 在翻译开始前，遍历所有导出对象
2. 对每个 UFunction 导出，记录其 PackageIndex → 签名映射
3. 翻译时查询缓存而非每次 resolve

**验收标准**:
- 同一资产内多次调用同一函数只解析一次
- 缓存命中率 > 80%（典型蓝图）

---

## Phase 3: Kismet 反编译器增强 — 控制流重构（P0）

> **目标**: 将 goto Label_N 退化替换为结构化 C++ 控制流。

### Task 3.1: 实现跳转标签预扫描

**文件**: 新建 `src/uasset_read/kismet/label_resolver.py`

**参考**: CUE4Parse `UClass.cs` 第 163-224 行

**方案**:
```python
class LabelResolver:
    """预扫描字节码，收集 Jump 目标地址 → Label 映射。"""
    
    def __init__(self, expressions: List[KismetExpression]):
        self.jump_targets: Dict[int, str] = {}  # offset → label_name
        self._scan(expressions)
    
    def _scan(self, expressions):
        for expr in expressions:
            if isinstance(expr, EX_Jump):
                self.jump_targets[expr.CodeOffset] = f"Label_{expr.CodeOffset}"
            elif isinstance(expr, EX_PushExecutionFlow):
                # 提取 flow name 作为 label
                ...
```

**验收标准**:
- 所有 Jump/JumpIfNot 目标地址都有对应 Label
- Label 名称包含语义信息（如 `Label_Return`、`Label_DeadEnd`）

### Task 3.2: 增强结构化控制流检测

**文件**: `src/uasset_read/kismet/structured_flow.py`

**当前支持**: if/else, while

**新增支持**:
1. **for 循环**: 检测 `初始化 + 条件检查 + 迭代器更新` 模式
2. **switch/case**: 完整 `EX_SwitchValue` 处理
3. **do-while**: 至少执行一次的循环
4. **嵌套 if/else if/else**: 深度嵌套检测

**参考**: CUE4Parse `GetLineExpression()` 第 1162-1781 行

**验收标准**:
- 生成的 C++ 代码无 goto（除非确实无法结构化）
- switch/case 包含所有 case 分支
- 嵌套深度 > 3 层时仍正确缩进

### Task 3.3: 实现执行流栈追踪

**文件**: `src/uasset_read/kismet/translator.py`

**参考**: CUE4Parse `_executionFlowStack`

**方案**:
```python
class ExecutionFlowTracker:
    """追踪 PushExecutionFlow/PopExecutionFlow 栈。"""
    
    def __init__(self):
        self._stack: List[str] = []
    
    def on_push(self, flow_name: str):
        self._stack.append(flow_name)
    
    def on_pop(self) -> str:
        return self._stack.pop() if self._stack else ""
```

**验收标准**:
- PushExecutionFlow 生成 `{` 块开始
- PopExecutionFlow 生成 `}` 块结束
- 嵌套块正确缩进

---

## Phase 4: C++ 骨架生成器增强 — 函数体注入（P0）

> **目标**: 在 C++ 头文件中生成完整的函数体（不仅是声明）。

### Task 4.1: 增强函数体提取

**文件**: `src/uasset_read/cpp_gen/extractors/cpp_function_body_extractor.py`

**当前问题**: 函数声明无体或只有空体

**方案**:
1. 从 `result.decompiled_functions` 获取反编译的 C++ 代码
2. 匹配函数名到 `CppMethodIR.body`
3. 格式化为带缩进的函数体

**验收标准**:
```cpp
// ✅ 期望输出
UFUNCTION(BlueprintCallable)
void Move(double LeftRight, double ForwardBackward)
{
    FVector Direction = GetActorForwardVector();
    AddMovementInput(Direction, ForwardBackward);
}
```

### Task 4.2: 增强属性默认值输出

**文件**: `src/uasset_read/cpp_gen/cpp_default_value_formatter.py`

**当前问题**: 默认值显示为 `ParseError` 或空

**方案**:
1. 从 `blueprint.variables[].default_value` 提取
2. 格式化为 C++ 初始化语法
3. 复杂类型（结构体、数组）使用构造函数语法

**验收标准**:
```cpp
UPROPERTY(EditAnywhere)
float Health = 100.0f;

UPROPERTY(EditAnywhere)
FVector SpawnLocation = FVector(0.0f, 0.0f, 100.0f);

UPROPERTY(EditAnywhere)
TArray<AActor*> IgnoredActors = {};
```

---

## Phase 5: 类型系统增强（P1）

> **目标**: 完善 UE 类型到 C++ 类型的映射。

### Task 5.1: 扩展类型映射表

**文件**: `src/uasset_read/cpp_gen/cpp_type_mapper.py`

**新增映射**:
| UE 类型路径 | C++ 类型 |
|-------------|----------|
| `/Script/Engine.Actor` | `AActor` |
| `/Script/Engine.Character` | `ACharacter` |
| `/Script/Engine.PlayerController` | `APlayerController` |
| `/Script/Engine.CameraComponent` | `UCameraComponent` |
| `/Script/Engine.SkeletalMeshComponent` | `USkeletalMeshComponent` |
| `/Script/Engine.StaticMeshComponent` | `UStaticMeshComponent` |
| `/Script/Engine.BoxComponent` | `UBoxComponent` |
| `/Script/Engine.SphereComponent` | `USphereComponent` |
| `/Script/Engine.CapsuleComponent` | `UCapsuleComponent` |
| `/Script/Engine.LightComponent` | `ULightComponent` |
| `/Script/Engine.AudioComponent` | `UAudioComponent` |
| `/Script/Engine.ParticleSystemComponent` | `UParticleSystemComponent` |
| `/Script/Engine.WidgetComponent` | `UWidgetComponent` |
| `/Script/Engine.SceneComponent` | `USceneComponent` |

### Task 5.2: 实现类前缀推导

**文件**: `src/uasset_read/cpp_gen/extract_cpp_skeleton.py`

**参考**: CUE4Parse `BlueprintDecompilerUtils.GetPrefix()`

**方案**:
```python
def infer_class_prefix(parent_class: str) -> str:
    """从父类推导类名前缀。"""
    if parent_class.startswith("A"):
        return "A"  # Actor 派生
    elif parent_class.startswith("U"):
        return "U"  # UObject 派生
    elif parent_class.startswith("F"):
        return "F"  # 结构体
    elif parent_class.startswith("E"):
        return "E"  # 枚举
    elif parent_class.startswith("I"):
        return "I"  # 接口
    return "U"  # 默认
```

**验收标准**:
- `B_MyCharacter` → `AB_MyCharacter : public ACharacter`
- `BP_MyComponent` → `UBP_MyComponent : public UActorComponent`

---

## Phase 6: 输出格式增强（P1）

> **目标**: 增强所有输出格式，使其包含完整的蓝图功能信息。

### Task 6.1: 增强 JSON 输出

**文件**: `src/uasset_read/renderers/json_renderer.py`

**新增字段**:
```json
{
  "blueprint": {
    "variables": [...],
    "functions": [...],
    "events": [...],
    "components": [...]
  },
  "decompiled_functions": [
    {
      "name": "Move",
      "signature": "void Move(double LeftRight, double ForwardBackward)",
      "cpp_code": "FVector Direction = GetActorForwardVector();\nAddMovementInput(Direction, ForwardBackward);",
      "parameters": [...],
      "return_type": "void"
    }
  ],
  "execution_chains": [
    {
      "event": "EventBeginPlay",
      "chain": ["InitializeComponents", "SetTimer", "PrintString"]
    }
  ]
}
```

### Task 6.2: 增强 Markdown 输出

**文件**: `src/uasset_read/renderers/markdown_renderer.py`

**新增章节**:
```markdown
## Event Graph

### Event BeginPlay
```cpp
void AMyActor::EventBeginPlay()
{
    Super::EventBeginPlay();
    InitializeComponents();
    SetTimer(1.0f, true, "UpdateUI");
}
```

### Function: Move
```cpp
void AMyActor::Move(double LeftRight, double ForwardBackward)
{
    FVector Direction = GetActorForwardVector();
    AddMovementInput(Direction, ForwardBackward);
}
```
```

### Task 6.3: 增强 BlueprintText 输出

**文件**: `src/uasset_read/renderers/blueprint_text_renderer.py`

**新增**: 完整的事件函数实现输出

---

## Phase 7: 测试与验证（P0）

> **目标**: 确保所有修改都有对应测试，输出质量达到可理解 C++ 类的水平。

### Task 7.1: 新增反编译器单元测试

**文件**: 新建 `tests/test_kismet_decompilation.py`

**测试用例**:
1. 函数引用解析（StackNode → ClassName::FuncName）
2. 跳转标签预扫描
3. 结构化控制流（if/else, while, for, switch）
4. 执行流栈追踪
5. 数学库函数简化
6. Delay 延迟跳转处理

### Task 7.2: 新增 C++ 输出集成测试

**文件**: 新建 `tests/test_cpp_output_quality.py`

**测试用例**:
1. 蓝图资产生成的 C++ 头文件可读性
2. 函数体包含完整实现（非空体）
3. 属性默认值正确格式化
4. 类名前缀推导正确

### Task 7.3: 输出质量对比测试

**文件**: 新建 `tests/test_output_quality_comparison.py`

**测试用例**:
1. 选取 5 个典型蓝图资产
2. 生成 C++ 输出
3. 验证关键模式存在（如 `UFUNCTION`, `UPROPERTY`, 函数体非空）
4. 验证无 `Function_` 占位符（或比例 < 10%）

### Task 7.4: 全量回归测试

**命令**: `python -m pytest tests/ -v`

**目标**:
- 所有现有测试通过
- 新增测试 ≥ 30 个
- 无新的 xfail

---

## 文件结构

### 新建文件

| 文件 | 职责 |
|------|------|
| `src/uasset_read/kismet/label_resolver.py` | 跳转标签预扫描 |
| `tests/test_kismet_decompilation.py` | 反编译器单元测试 |
| `tests/test_cpp_output_quality.py` | C++ 输出质量测试 |
| `tests/test_output_quality_comparison.py` | 输出质量对比测试 |

### 修改文件

| 文件 | 修改内容 |
|------|----------|
| `src/uasset_read/kismet/translator.py` | 函数引用解析 + 执行流栈追踪 |
| `src/uasset_read/kismet/structured_flow.py` | 增强控制流检测 |
| `src/uasset_read/cpp_gen/extractors/cpp_function_body_extractor.py` | 函数体提取 |
| `src/uasset_read/cpp_gen/cpp_default_value_formatter.py` | 默认值格式化 |
| `src/uasset_read/cpp_gen/cpp_type_mapper.py` | 类型映射扩展 |
| `src/uasset_read/cpp_gen/extract_cpp_skeleton.py` | 类前缀推导 |
| `src/uasset_read/renderers/json_renderer.py` | JSON 输出增强 |
| `src/uasset_read/renderers/markdown_renderer.py` | Markdown 输出增强 |
| `src/uasset_read/renderers/blueprint_text_renderer.py` | BlueprintText 输出增强 |

---

## 验收标准

### 定量指标

| 指标 | 目标 | 测量方法 |
|------|------|----------|
| 资产解析通过率 | ≥ 99.5% | 全量扫描 4403 个资产 |
| 函数引用解析率 | ≥ 80% | 抽样 50 个蓝图，统计 `Function_` 占位符比例 |
| 控制流结构化率 | ≥ 70% | 抽样 50 个蓝图，统计 goto 使用率 |
| C++ 输出可读性 | ≥ 90% | 人工评审 10 个蓝图的输出 |

### 定性指标

| 指标 | 验证方法 |
|------|----------|
| 函数体包含完整实现 | 检查 `CppMethodIR.body` 非空 |
| 属性默认值可读 | 检查无 `ParseError` 占位符 |
| 类名前缀正确 | 检查 `A`/`U`/`F` 前缀匹配父类 |
| 事件函数有实现 | 检查 EventGraph 节点有对应 C++ 代码 |

---

## 风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| CUE4Parse 反编译逻辑移植复杂度高 | 中 | 高 | 分阶段实现，先实现 P0 级别 |
| 函数引用解析依赖 linker 上下文 | 高 | 中 | 使用现有 linker，不新增依赖 |
| 控制流检测误判 | 中 | 中 | 保守检测，误判时回退到 goto |
| 测试覆盖不足 | 低 | 高 | 每个 Task 必须有对应测试 |
| 性能下降 | 低 | 低 | 跳转标签预扫描是一次性开销 |

---

## 执行顺序

```
Phase 1: 解析错误修复 ✅ (已完成)
    ↓
Phase 2: 函数引用解析 (P0, 8h)
    ↓
Phase 3: 控制流重构 (P0, 12h)
    ↓
Phase 4: 函数体注入 (P0, 6h)
    ↓
Phase 5: 类型系统增强 (P1, 4h)
    ↓
Phase 6: 输出格式增强 (P1, 6h)
    ↓
Phase 7: 测试与验证 (P0, 8h)
```

**总预估工时**: 44h (P0: 34h, P1: 10h)

---

## 参考资源

| 资源 | 路径 | 用途 |
|------|------|------|
| CUE4Parse 反编译器 | `external/CUE4Parse/CUE4Parse/UE4/Objects/UObject/BlueprintDecompiler/` | Kismet→C++ 翻译参考 |
| CUE4Parse UClass | `external/CUE4Parse/CUE4Parse/UE4/Objects/UObject/UClass.cs` | 蓝图反编译入口 |
| CUE4Parse FKismetArchive | `external/CUE4Parse/CUE4Parse/UE4/Assets/Readers/FKismetArchive.cs` | 字节码读取参考 |
| UE 蓝图格式文档 | `docs/uasset-format/assets/blueprint-generated-class.md` | BGC 序列化格式 |
| 蓝图转 C++ 指南 | `docs/reference/blueprint-to-cpp-guide.md` | 转换可行性分析 |
| 当前反编译器 | `src/uasset_read/kismet/translator.py` | 现有实现基线 |
| 当前 C++ 生成器 | `src/uasset_read/cpp_gen/` | 现有实现基线 |
