# Requirements

## v6.0 ✅ 完成

| ID | 需求 | 状态 | 模块 |
|----|------|------|------|
| MOD-01~09 | 模块化重构 (FArchive/常量/异常/序列化/解析器/模型) | ✓ | 各子模块 |
| STRUCT-01~02 | src layout + pyproject.toml | ✓ | 项目结构 |
| TEST-01~02 | 373 测试通过 | ✓ | tests/ |

## v7.0 📋 规划中

| ID | 需求 | 对应 Phase |
|----|------|------------|
| LINK-01 | link/ 模块 (UObjectInstance, PackageLinker) | Phase 41 |
| LINK-02 | parse_uasset_with_linker() 入口 | Phase 42 |
| LINK-03 | PackageIndex.resolve_with_linker() | Phase 43 |
| LINK-04 | UEdGraphPin linked_to_objects | Phase 44 |
| LINK-05 | 图序列化 linker 变体 | Phase 45 |
| LINK-06 | 373 测试 0 回归 | Phase 46 |

## v6.0 遗留 → v7.0 映射

| 遗留问题 | v7.0 方案 | Phase |
|----------|-----------|-------|
| linked_to_raw 为空 | FLinkerLoad 对象图重建 | 41-45 |
| PackageIndex 仅名字 | UObjectInstance 引用 | 43 |
| 无对象图 | PackageLinker 构建 | 41 |

## Out of Scope

修改现有序列化器 | 修改 parse_uasset() | 导出纹理/模型 | Cooked 资产 | C++ 生成

*Updated: 2026-05-14*
