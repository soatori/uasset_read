---
phase: 056
plan: 03
subsystem: cpp_gen
tags: [header-formatter, e2e-test, UE-conventions]
requires: [CPP-01, CPP-03]
provides: [cpp_header_formatter.py, format_cpp_header]
affects: []
tech_stack:
  added: [format_cpp_header]
  patterns: [UE .h template generation, CPF → UPROPERTY rendering]
key_files:
  created:
    - src/uasset_read/cpp_gen/formatters/cpp_header_formatter.py
    - tests/test_cpp_header_formatter.py
    - tests/test_cpp_skeleton_e2e.py
  modified:
    - src/uasset_read/cpp_gen/__init__.py
    - src/uasset_read/cpp_gen/formatters/__init__.py
decisions:
  - D-05: Complete UE header template from JSON IR
  - D-06: CppClassIR structure with header_meta, properties
  - T-056-05: HTML escape for comment strings to prevent injection
  - T-056-06: Class name sanitization (alphanumeric + underscore only)
metrics:
  duration_minutes: 15
  completed_date: "2026-05-18T02:30:00Z"
  test_count: 44
  files_modified: 4
  commits: 2
---

# Phase 56 Plan 03: C++ Header Formatter Summary

## 一句话总结

CppClassIR → 标准 UE .h 头文件文本生成器，含 #pragma once、includes、UCLASS、UPROPERTY 声明，支持组件和变量渲染。

## 完成内容

### Task 1: cpp_header_formatter.py — JSON IR → .h text output

实现了 `format_cpp_header(ir: CppClassIR) -> str` 函数，将 CppClassIR 转换为标准 UE .h 头文件格式：

- **结构元素**：
  - `#pragma once`（可选）
  - `#include "CoreMinimal.h"`（始终添加）
  - `#include` 行（排序，generated.h 最后）
  - `UCLASS(Blueprintable)` 宏
  - 类声明 `class {name} : public {parent_class}`
  - `GENERATED_BODY()` 宏
  - `public:` 构造函数声明
  - `protected:` 属性声明

- **组件渲染**：
  - `UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Instanced, Category = "Components", meta = (AllowPrivateAccess = "true"))`
  - `USceneComponent* DefaultSceneRoot;`

- **变量渲染**：
  - `UPROPERTY({marks}, Category = "{category}")`
  - `float MoveSpeed = 600.0f;`（float 使用 f 后缀）
  - `bool IsAiming = false;`（bool 使用 true/false）
  - `FString Name = TEXT("value");`（字符串使用 TEXT 包装）

- **安全措施**：
  - T-056-05：HTML 转义注释字符串，防止注入
  - T-056-06：类名清理，只允许字母数字和下划线

- **测试**：31 个单元测试覆盖所有场景

### Task 2: Golden-path e2e test — BP_FirstPersonCharacter mock data

创建了 `tests/test_cpp_skeleton_e2e.py`，验证完整管道：

- **Mock 数据**（模拟 BP_FirstPersonCharacter）：
  - 父类：`/Script/Engine.Character` → `ACharacter`
  - 组件：DefaultSceneRoot (USceneComponent), CameraBoom (USpringArmComponent), FirstPersonCamera (UCameraComponent)
  - 变量：MoveSpeed (float, 600.0), JumpHeight (float, 420.0), isAiming (bool, false)

- **测试场景**：
  - Full extraction：LinkerParseResult → CppClassIR 验证
  - Component properties：指针类型 + Instanced 标记
  - Variable properties：类型 + 默认值
  - Header generation：完整 .h 结构验证
  - Boundary cases：空蓝图、单继承、空组件、复制属性

- **测试**：13 个 e2e 测试

## 偏差记录

### Auto-fixed Issues

**1. [Rule 1 - Bug] 测试 CPF 标志值错误**

- **发现时机**：Task 2 测试运行时
- **问题**：Mock 数据使用错误的 CPF 标志值（0x00201028），导致 "Instanced" 不在 UPROPERTY marks 中
- **修复**：使用正确的 CPF 常量组合 `CPF_EditAnywhere | CPF_BlueprintVisible | CPF_InstancedReference`
- **影响文件**：`tests/test_cpp_skeleton_e2e.py`
- **Commit**：de77079

**2. [Rule 3 - Blocking] 测试 include 排序期望错误**

- **发现时机**：Task 1 测试运行时
- **问题**：测试期望 Engine/ 在 Components/ 前，但字母排序使 Components 先于 Engine
- **修复**：修正测试期望，字母排序正确
- **影响文件**：`tests/test_cpp_header_formatter.py`
- **Commit**：cddd7ea

## 认证门控

无认证门控。

## 已知 Stub

无。

## Threat Flags

无新增威胁表面（所有威胁已在 PLAN.md threat_model 中识别并缓解）。

## Commits

| Commit | 类型 | 描述 |
|--------|------|------|
| cddd7ea | feat | cpp_header_formatter — CppClassIR → UE .h text |
| de77079 | test | golden-path e2e test for BP_FirstPersonCharacter |

## Self-Check: PASSED

- cpp_header_formatter.py 存在：FOUND
- test_cpp_header_formatter.py 存在：FOUND
- test_cpp_skeleton_e2e.py 存在：FOUND
- cddd7ea commit 存在：FOUND
- de77079 commit 存在：FOUND
- 44 tests passed：VERIFIED