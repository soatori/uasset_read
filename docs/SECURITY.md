# SECURITY.md

**项目:** uasset_read — Python .uasset 解析器
**审计日期:** 2026-05-02
**ASVS Level:** 1

---

## 当前状态

安全边界常量定义在 `src/uasset_read/constants.py`。
所有解析输入都经过边界验证，防止越界访问和无限循环。

---

## 安全边界常量汇总

| 常量 | 值 | 用途 |
|------|----|----|
| MAX_EXPORT_COUNT | 1,000,000 | 导出表大小限制 |
| MAX_PINS_PER_NODE | 1,000 | 单节点引脚数限制 |
| MAX_NODES_PER_GRAPH | 5,000 | 单图节点数限制 |
| MAX_LINKEDTO_PER_PIN | 100 | 单引脚连接数限制 |
| MAX_PROPERTY_COUNT | 10,000 | 属性循环限制 |
| MAX_DEPTH (Struct) | 5 | StructProperty 递归深度 |
| MAX_DEPTH (Array) | 10 | ArrayProperty 递归深度 |
| PKG_Cooked | 0x200 | Cooked 资产检测标志 |
| MMAP_THRESHOLD | - | mmap 大文件阈值 |

---

## 已接受的风险

以下风险已评估并接受：

- **ErrorContext 信息**：错误信息包含偏移量用于诊断，无敏感数据
- **原始数据存储**：部分原始字段（如 linked_to_raw）暂不验证格式
- **注释颜色**：CommentColor 无范围验证，不影响解析逻辑

---

*审计完成：2026-05-02*
*状态：SECURED*
