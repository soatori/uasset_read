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
| TECH-01 | 移除旧版本/UE4 兼容代码 | Phase 44a |
| TECH-02 | 替换直接字节读取为 FArchive 方法 | Phase 44b |
| TECH-03 | 清理废弃测试工具 | Phase 44c |
| LINK-05 | 图序列化 linker 变体 | Phase 45 |
| LINK-06 | 373 测试 0 回归 | Phase 46 |

## v6.0 遗留 → v7.0 映射

| 遗留问题 | v7.0 方案 | Phase |
|----------|-----------|-------|
| linked_to_raw 为空 | FLinkerLoad 对象图重建 | 41-45 |
| PackageIndex 仅名字 | UObjectInstance 引用 | 43 |
| 无对象图 | PackageLinker 构建 | 41 |

## v7.0 技术债

| ID | 问题 | 方案 | Phase |
|----|------|------|-------|
| TECH-01 | UE4 兼容代码误导分析 | 删除所有 UE4 分支 | 44a |
| TECH-02 | 直接字节读取绕过 FArchive | 统一使用 FArchive 方法 | 44b |
| TECH-03 | 测试工具混乱 | 清空废弃/调试文件 | 44c |

## 阶段 45 过渡条件

| # | 条件 | 验证方法 |
|---|------|----------|
| 1 | 不存在直接字节读取代码 | `grep -r 'struct.unpack' src/` 返回 0 结果（除 archive.py） |
| 2 | 不存在兼容其他版本的代码 | `grep -r 'is_ue4_file\|UE4_\|legacy_file_version >' src/` 返回 0 结果 |
| 3 | 清空测试工具 | `tools/` 和 `temp/` 目录为空 |
| 4 | 可用 BP_FirstPersonCharacter.uasset 完整解析 | `uasset-read` 成功执行并输出结构化结果 |

## Out of Scope

修改现有序列化器 | 修改 parse_uasset() | 导出纹理/模型 | Cooked 资产 | C++ 生成

*Updated: 2026-05-14*
