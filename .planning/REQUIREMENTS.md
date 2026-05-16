# Requirements

## v6.0 ✅ 完成

| ID | 需求 | 状态 | 模块 |
|----|------|------|------|
| MOD-01~09 | 模块化重构 (FArchive/常量/异常/序列化/解析器/模型) | ✓ | 各子模块 |
| STRUCT-01~02 | src layout + pyproject.toml | ✓ | 项目结构 |
| TEST-01~02 | 373 测试通过 | ✓ | tests/ |

## v7.0 ✅ 完成

| ID | 需求 | 状态 | Phase |
|----|------|------|-------|
| LINK-01 | link/ 模块 (UObjectInstance, PackageLinker) | ✓ | 41 |
| LINK-02 | parse_uasset_with_linker() 入口 | ✓ | 42 |
| LINK-03 | PackageIndex.resolve_with_linker() | ✓ | 43 |
| LINK-04 | UEdGraphPin linked_to_objects | ✓ | 44 |
| TECH-01 | 移除旧版本/UE4 兼容代码 | ✓ | 44a |
| TECH-02 | 替换直接字节读取为 FArchive 方法 | ✓ | 44b |
| TECH-03 | 清理废弃测试工具 | ✓ | 44c |
| LINK-05 | 图序列化 linker 变体 | ✓ | 45 |
| LINK-06 | 432 测试 0 回归 | ✓ | 46 |

## v8.0 🔨 进行中

| ID | 需求 | 状态 | Phase |
|----|------|------|-------|
| BP-01 | Pin LinkedTo 修复 | ✓ | 47 |
| BP-02 | 组件属性递归解析 | ✓ | 48 |
| BP-03 | CallFunction 参数引脚完整 | 🔴 未开始 | 49 |
| BP-04 | EnhancedInput 语义增强 | ✓ | 50 |

## Out of Scope

修改现有序列化器 | 修改 parse_uasset() | 导出纹理/模型 | Cooked 资产 | C++ 生成

*Updated: 2026-05-16*
