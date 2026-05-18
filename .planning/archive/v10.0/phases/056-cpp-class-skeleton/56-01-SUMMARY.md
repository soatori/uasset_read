---
phase: 056
plan: 01
subsystem: cpp_gen
tags: [type-mapping, uproperty-mapping, foundation, zero-dependency]
requires: []
provides: [cpp_type_mapper, cpp_uproperty_mapper]
affects: [Phase 56-02, Phase 56-03]
tech_stack:
  added: [cpp_gen module, UE_TO_CPP_TYPE_MAP, ENGINE_CLASS_PATHS, CPF_TO_UPROPERTY_MAP]
  patterns: [hardcoded dict + heuristic fallback, bitmask → mark list mapping]
key_files:
  created:
    - src/uasset_read/cpp_gen/__init__.py
    - src/uasset_read/cpp_gen/cpp_type_mapper.py
    - src/uasset_read/cpp_gen/cpp_uproperty_mapper.py
    - tests/test_cpp_type_mapper.py
    - tests/test_cpp_uproperty_mapper.py
  modified:
    - src/uasset_read/constants.py
decisions: []
metrics:
  duration: 7 minutes
  tasks_completed: 2
  files_created: 5
  files_modified: 1
  tests_added: 77
  completed_date: "2026-05-18"
---

# Phase 56 Plan 01: C++ Type Mapping Engine Summary

## 一句话总结

创建了 UE 类型路径 → C++ 类型名映射引擎和 CPF 标志 → UPROPERTY 标记映射模块，为 Phase 56 的骨架提取提供核心类型转换能力。

## 完成的任务

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create cpp_type_mapper.py | 7611230 | cpp_gen/__init__.py, cpp_gen/cpp_type_mapper.py |
| 2 | Create cpp_uproperty_mapper.py + tests | a9d3a43 | cpp_gen/cpp_uproperty_mapper.py, constants.py, test_cpp_type_mapper.py, test_cpp_uproperty_mapper.py |

## 实现细节

### Task 1: cpp_type_mapper 模块

创建了 `cpp_gen/cpp_type_mapper.py` 模块，实现 UE 类型路径到 C++ 类型名的转换：

- **UE_TO_CPP_TYPE_MAP**: 87 个条目的硬编码字典，覆盖 ScriptStruct（FVector, FRotator, FTransform 等）、Class（ACharacter, USceneComponent 等）和基本类型（float, bool, int32 等）
- **ENGINE_CLASS_PATHS**: 60 个 Engine 类路径映射，支持 D-02 继承链解析
- **ue_path_to_cpp_type()**: 主转换函数，支持三种输入格式：
  - 引用格式：`ScriptStruct'CoreUObject.Vector'` → `FVector`
  - 路径格式：`/Script/CoreUObject.Vector` → `FVector`
  - 基本类型：`float` → `float`
- **ue_package_path_to_cpp_class()**: 包路径转换，用于继承链解析
- **启发式前缀判断**: 未知类型根据 Actor/Component 后缀自动添加 A/U 前缀

### Task 2: cpp_uproperty_mapper 模块 + 测试

创建了 `cpp_gen/cpp_uproperty_mapper.py` 模块和两个测试文件：

- **CPF_TO_UPROPERTY_MAP**: 21 个映射规则，按优先级排序
- **cpf_flags_to_uproperty_marks()**: CPF 标志位 → UPROPERTY 标记列表转换
  - 组合标志处理：`CPF_Edit | CPF_BlueprintVisible` → `['EditAnywhere', 'BlueprintReadWrite']`
  - Net/Replicated 特殊处理：`CPF_Replicated` 隐含 `CPF_Net`，不重复显示
  - 组件默认标记：无显式可见性标志时添加 `VisibleAnywhere` + `BlueprintReadOnly`
- **uproperty_mark_to_cpf()**: 反向映射（用于测试/调试）

**测试覆盖**：
- test_cpp_type_mapper.py: 39 个测试
- test_cpp_uproperty_mapper.py: 38 个测试
- 共 77 个测试全部通过

## 偏差记录

### 自动修复的问题

**1. [Rule 3 - Blocking Issue] 修复 CPF_InstancedReference 常量值错误**

- **发现时机**: Task 2 测试运行时
- **问题**: constants.py 中 CPF_InstancedReference = 0x0000000000080000 (524288) 与 CPF_NoClear = 0x00080000 (524288) 碰撞，导致测试 `test_plan_instanced_reference` 失败
- **原因**: CPF_InstancedReference 应为 bit 23 (8388608)，但 constants.py 缺少一个十六进制位
- **修复**: 更新 constants.py 第 215 行：`0x0000000000080000` → `0x00000000000800000`
- **修改文件**: src/uasset_read/constants.py
- **Commit**: a9d3a43

## 验证结果

- 导入测试：所有符号从 `uasset_read.cpp_gen` 成功导出
- 单元测试：77 个测试全部通过
- 类型映射覆盖：87+ UE 类型路径 → C++ 类型映射
- UPROPERTY 映射覆盖：21 个 CPF 标志 → UPROPERTY 标记规则

## 关键决策

无新增决策。模块遵循 D-03（核心硬编码字典 + 可扩展脚本路径）和 D-04（CPF 标志直接映射）设计决策。

## 已知 Stub

无。模块完全实现，无 placeholder 或未完成功能。

## Threat Flags

无新增威胁标志。模块遵循 T-056-01 和 T-056-02 缓解策略：
- 类型路径验证：未知类型返回原值并记录警告日志
- CPF 范围验证：负数返回空列表，超出 64 位范围自动截断

## Self-Check: PASSED

**文件存在验证**:
- [x] src/uasset_read/cpp_gen/__init__.py EXISTS
- [x] src/uasset_read/cpp_gen/cpp_type_mapper.py EXISTS
- [x] src/uasset_read/cpp_gen/cpp_uproperty_mapper.py EXISTS
- [x] tests/test_cpp_type_mapper.py EXISTS
- [x] tests/test_cpp_uproperty_mapper.py EXISTS

**提交验证**:
- [x] Commit 7611230 EXISTS (feat(056-01): create cpp_type_mapper module)
- [x] Commit a9d3a43 EXISTS (feat(056-01): create cpp_uproperty_mapper and unit tests)

---
*Generated: 2026-05-18*