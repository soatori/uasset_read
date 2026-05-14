# Phase 43 Discussion Log

**Date:** 2026-05-14
**Phase:** 043-packageindex-enhance

## Discussion Summary

### 迁移策略
- **Question:** resolve_with_linker() 的迁移策略？
- **Options:** 仅新增 linker 版 / 全面替换 / 新旧并存
- **Selected:** 全面替换
- **Notes:** 用户选择一次到位，不保留兼容性 shim

### 替换范围
- **Question:** 哪些函数需要替换为 linker 版本？
- **Options:** resolve_class_name + get_asset_class / detect_blueprint + resolve_parent_class / resolve_package_index_to_reference
- **Selected:** 全部（多选）
- **Notes:** 所有旧函数替换为 linker 版本，resolve_package_index_to_reference 完全移除

### 格式化层适配
- **Question:** 移除 dict 返回后，格式化层怎么处理？
- **Options:** 完全移除 dict 返回 / 保留转换函数
- **Selected:** 完全移除 dict 返回
- **Notes:** 格式化层直接使用 UObjectInstance 属性，需要 dict 时自行构建

## Deferred Ideas

无

---

*Generated: 2026-05-14*
