---
phase: 056
plan: 02
subsystem: cpp_gen
tags: [cpp-skeleton, json-ir, extraction, tdd]
requires:
  - 056-01 (cpp_type_mapper, cpp_uproperty_mapper)
provides:
  - extract_cpp_class_skeleton
  - CppClassIR/CppProperty data models
  - format_cpp_class_json
affects:
  - Phase 57 (method extraction)
  - Phase 58 (function body translation)
  - Phase 59 (constructor generation)
tech_stack:
  added:
    - dataclasses for CppProperty/CppHeaderMeta/CppClassIR
    - unittest.mock for LinkerParseResult mocking
  patterns:
    - TDD (RED: tests written first, GREEN: implementation)
    - JSON IR intermediate representation per D-01/D-06
key_files:
  created:
    - src/uasset_read/cpp_gen/formatters/cpp_json_ir.py
    - src/uasset_read/cpp_gen/formatters/__init__.py
    - src/uasset_read/cpp_gen/extract_cpp_skeleton.py
    - tests/test_extract_cpp_skeleton.py
  modified:
    - src/uasset_read/cpp_gen/__init__.py
    - src/uasset_read/formatters/__init__.py
decisions:
  - D-06: JSON IR 结构（header_meta, properties, methods, constructor）
  - D-02: 继承链直接从 BlueprintMetadata.parent_class 解析
  - D-05: header_meta.build_from_parent() 根据父类前缀推断头文件路径
metrics:
  duration: ~5 minutes
  tasks: 2
  tests: 10
  commits: 2
  completed_date: 2026-05-18
---

# Phase 56 Plan 02: C++ Skeleton Extraction Core Summary

**一句话概述**: 实现核心骨架提取逻辑 `extract_cpp_class_skeleton()` 和 JSON IR 格式化模块，将 LinkerParseResult 转换为 CppClassIR 中间表示。

## 完成内容

### Task 1: CppProperty 和 CppClassIR 数据模型 + JSON IR 格式化

创建 `src/uasset_read/cpp_gen/formatters/` 子模块：

- **CppProperty**: 单个 UPROPERTY 声明，包含 `cpp_type`, `name`, `uproperty_marks`, `category`, `default_value`
- **CppHeaderMeta**: 头文件元数据，包含 `pragma_once`, `includes`, `forward_declarations`, `generated_include`
- **CppClassIR**: 完整类骨架 IR，包含 `name`, `parent_class`, `header_meta`, `properties`, `methods`, `constructor`
- **format_cpp_class_json()**: JSON IR 包装函数，输出 `{"cpp_class": {...}, "output_version": "1.0"}`

Per D-06: `methods` 和 `constructor` 留空数组，Phase 57-59 分别填充。

### Task 2: extract_cpp_class_skeleton() 实现（TDD）

实现 `src/uasset_read/cpp_gen/extract_cpp_skeleton.py`：

- **类名提取**: 从 `summary.package_name` 提取，根据父类类型添加 `A`/`U` 前缀
- **继承链解析**: 通过 `ue_package_path_to_cpp_class()` 转换 `/Script/Engine.XXX` 为 C++ 类名
- **组件属性提取**: 从 `blueprint.variables` (is_component=True) 和 `result.components` 提取，类型添加 `*` 指针，UPROPERTY 标记包含 `Instanced`
- **变量属性提取**: 从 `blueprint.variables` (is_component=False) 提取，通过 `ue_path_to_cpp_type()` 转换类型
- **header_meta 构建**: `CppHeaderMeta.build_from_parent()` 根据父类推断头文件路径

**测试覆盖**（10 个单元测试，全部通过）：
1. full blueprint → CppClassIR with name, parent_class, properties
2. blueprint with no variables → properties is empty list, not None
3. single inheritance chain → parent_class = ACharacter
4. component-only blueprint → properties contains component CppProperty entries
5. variable-only blueprint → properties contains variable CppProperty entries
6. header_meta.includes contains parent class header path
7. header_meta.generated_include matches class name + .generated.h
8. methods is empty list, constructor has empty sub-arrays
9. component properties get correct UPROPERTY marks (Instanced + Visible)
10. Component-derived blueprint gets U prefix instead of A

## Deviations from Plan

### Auto-fixed Issues

None - plan executed exactly as written.

## Commits

| Commit | Message |
|--------|---------|
| 53ab397 | feat(056-02): create CppProperty, CppHeaderMeta, CppClassIR data models |
| c7cb760 | feat(056-02): implement extract_cpp_class_skeleton() - core skeleton extraction |

## Verification

```bash
pytest tests/test_extract_cpp_skeleton.py -v -x
# 10 passed in 0.18s
```

## Next Steps

- Phase 57: 方法签名提取（填充 `methods` 数组）
- Phase 58: 函数体翻译（K2Node → C++ 代码）
- Phase 59: 构造函数生成（组件创建、默认值赋值）