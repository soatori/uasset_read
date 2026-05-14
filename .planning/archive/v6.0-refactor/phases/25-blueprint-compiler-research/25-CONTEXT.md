# Phase 25: 蓝图编译流程研究

**阶段编号**: 25
**所属里程碑**: v5.0 架构重构与蓝图编译研究
**状态**: 进行中 ⏳
**预计完成**: 2026-05-20

## 上下文

### 问题陈述

当前 uasset_read 项目已能够离线解析 .uasset 文件，支持蓝图图解析、依赖分析等功能。虽然有蓝图转 C++ 的基础实现（95% 质量），但缺少完整的编译流程理解，包括：

1. **蓝图编译器流程**：UE 如何将蓝图编译为 C++ 代码
2. **蓝图虚拟机执行**：蓝图字节码如何在运行时执行
3. **节点到 C++ 映射**：蓝图节点如何映射到 C++ 函数调用

### 目标

深度研究 UE 5.7 蓝图编译器和虚拟机源码，提取关键信息用于 C++ 代码生成。

### 依赖

- Phase 24: JSON 输出规范化 ✓ COMPLETE

---

## 需求

### COMP-01: 研究蓝图编译器源码

**描述**：研究 `E:\Develop\lib\UnrealEngine\Engine\Source\Editor\KismetCompiler\Private\KismetCompiler.cpp`

**接受标准**：
- [ ] 理解编译器主流程（FKismetCompilerContext::CompileClassLayout）
- [ ] 理解函数编译流程（FKismetCompilerContext::CompileFunctions）
- [ ] 理解单个函数编译流程（FKismetCompilerContext::CompileFunction）
- [ ] 提取编译器管道步骤（Schema → Function List → Expansion → Validation → Code Generation → Finalization）

### COMP-02: 研究蓝图虚拟机源码

**描述**：研究 `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\Engine\Private\Kismet\KismetVM.cpp`

**接受标准**：
- [ ] 理解虚拟机上下文（FKismetVMContext）
- [ ] 理解字节码执行流程
- [ ] 理解栈管理和参数传递
- [ ] 提取虚拟机指令集

### COMP-03: 提取节点到 C++ 的映射关系

**描述**：提取蓝图节点类型到 C++ 函数调用的映射关系

**接受标准**：
- [ ] 提取 K2Node_CallFunction 到 C++ 函数调用映射
- [ ] 提取 K2Node_Event 到 C++ 事件映射
- [ ] 提取 K2Node_Knot 到变量访问映射
- [ ] 提取其他节点类型映射

### COMP-04: 编写研究文档

**描述**：编写蓝图编译流程研究文档

**接受标准**：
- [ ] 蓝图编译器流程文档 (BLUEPRINT_COMPILER_FLOW.md)
- [ ] 蓝图虚拟机文档 (BLUEPRINT_BYTECODE.md)
- [ ] 节点到 C++ 映射文档 (NODE_TO_CPP_MAPPING.md)

---

## 成功标准

### Phase 25 完成时必须为真的条件

1. **COMP-01**: 蓝图编译器核心流程文档完整
2. **COMP-02**: 蓝图虚拟机执行模型文档完整
3. **COMP-03**: 节点映射表建立完成
4. **COMP-04**: 所有研究文档编写完成

---

## 计划

### 25-01: COMP-01 研究蓝图编译器源码

**状态**: 📅 Planned

**输出**:
- `.planning/research/BLUEPRINT_COMPILER_FLOW.md`

**关键源码**:
- `E:\Develop\lib\UnrealEngine\Engine\Source\Editor\KismetCompiler\Private\KismetCompiler.cpp`

---

### 25-02: COMP-02 研究蓝图虚拟机源码

**状态**: 📅 Planned

**输出**:
- `.planning/research/BLUEPRINT_BYTECODE.md`

**关键源码**:
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\Engine\Private\Kismet\KismetVM.cpp`

---

### 25-03: COMP-03 提取节点到 C++ 的映射关系

**状态**: 📅 Planned

**输出**:
- `.planning/research/NODE_TO_CPP_MAPPING.md`

**关键源码**:
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\Engine\Public\Kismet\KismetNodeTypes.h`

---

### 25-04: COMP-04 编写研究文档

**状态**: 📅 Planned

**输出**:
- `.planning/research/BLUEPRINT_COMPILER_FLOW.md`
- `.planning/research/BLUEPRINT_BYTECODE.md`
- `.planning/research/NODE_TO_CPP_MAPPING.md`

---

## 输出文件

| 文件 | 描述 | 位置 |
|------|------|------|
| BLUEPRINT_COMPILER_FLOW.md | 蓝图编译器流程文档 | `.planning/research/` |
| BLUEPRINT_BYTECODE.md | 蓝图虚拟机文档 | `.planning/research/` |
| NODE_TO_CPP_MAPPING.md | 节点到 C++ 映射文档 | `.planning/research/` |

---

## 关键源码位置

| 文件 | 用途 | 位置 |
|------|------|------|
| KismetCompiler.cpp | 蓝图编译器核心 | `E:\Develop\lib\UnrealEngine\Engine\Source\Editor\KismetCompiler\Private\KismetCompiler.cpp` |
| KismetVM.cpp | 蓝图虚拟机 | `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\Engine\Private\Kismet\KismetVM.cpp` |
| KismetNodeTypes.h | 节点类型定义 | `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\Engine\Public\Kismet\KismetNodeTypes.h` |

---

## 参考资料

### UE 文档
- [Blueprint Communication](https://docs.unrealengine.com/5.7/en-US/programming-and-scripting/blueprints/blueprint-coding-efficiency/)
- [Kismet API](https://docs.unrealengine.com/5.7/en-US/API/Runtime/Engine/Kismet/)

### 项目文件
- `E:\Develop\uasset_read\.planning\BLUEPRINT_TO_CPP_TEST.md` — 蓝图转 C++ 基础实现
- `E:\Develop\lib\UnrealEngine\Samples\FirstPersonC\Source\FirstPersonC\` — C++ 代码参考

---

## 验证计划

### COMP-01 验证
- [ ] 编译器流程文档与源码一致
- [ ] 编译器管道步骤描述完整

### COMP-02 验证
- [ ] 虚拟机文档与源码一致
- [ ] 虚拟机指令集完整

### COMP-03 验证
- [ ] 节点映射表覆盖主要节点类型
- [ ] 映射关系与 UE 源码一致

### COMP-04 验证
- [ ] 所有研究文档编写完成
- [ ] 文档格式统一，易于理解

---

*创建日期：2026-05-06*
*最后更新：2026-05-06*