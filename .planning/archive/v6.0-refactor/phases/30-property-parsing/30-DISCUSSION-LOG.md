# Phase 30: 属性解析模块 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-11
**Phase:** 30-属性解析模块
**Areas discussed:** 模块组织, 分派策略, 蓝图变量归属, 循环导入处理

---

## 模块组织

| Option | Description | Selected |
|--------|-------------|----------|
| 单一 parsers/ 目录 | 所有解析器放 parsers/ 目录下（property_parser.py, property_types.py），类似 serializers/ 的做法 | |
| 按功能分目录 | 拆分为 parsers/property/, parsers/blueprint/ 等子目录，按功能域分离 | |
| 你决定 | 由 Claude 根据代码依赖关系决定最佳拆分方式 | ✓ |

**User's choice:** 你决定 — 由 Claude 根据代码依赖关系决定最佳拆分方式
**Notes:** 用户信任 Claude 的判断，根据最终 CONTEXT.md，拆分为 parsers/property_parser.py + parsers/property_types.py + blueprint/ 独立目录。

## 分派策略

| Option | Description | Selected |
|--------|-------------|----------|
| 类型分派表 (推荐) | 保持现有 type_dispatch 字典模式，通过 tag.type 字符串分派到对应解析函数 — 简单直观，易扩展 | ✓ |
| 类继承 + 多态 | 每种属性类型一个解析类，统一接口 parse() — 更 OOP，但增加复杂度 | |
| match/case 分派 | 使用 Python 3.10+ match/case 语句替代字典分派 — 更现代，性能略好 | |

**User's choice:** 类型分派表 (推荐)
**Notes:** 保持现有成熟的 type_dispatch 字典模式，14 种属性类型的分派逻辑不变。

## 蓝图变量归属

| Option | Description | Selected |
|--------|-------------|----------|
| 归属 parsers/ 模块 | 蓝图变量提取逻辑放在 parsers/blueprint_vars.py，与属性解析器同级 | |
| 独立蓝图模块 | 放在单独的 blueprint/ 目录，因为 Phase 31 图解析也可能用到 | ✓ |
| 保留在属性解析器 | 作为 property_parser.py 的一部分，因为本质也是属性解析 | |

**User's choice:** 独立蓝图模块
**Notes:** 蓝图变量提取放在独立 blueprint/ 模块，与属性解析器同级但独立，方便 Phase 31 复用。

## 循环导入处理

| Option | Description | Selected |
|--------|-------------|----------|
| 字符串类型注解 | 使用 TYPE_CHECKING + 'ModelName' 前向引用，避免运行时循环导入 — 现有项目已采用此模式 | ✓ |
| 延迟导入 | 在函数内部 import，运行时才加载 — 简单但不够优雅 | |
| 共享中间层 | 创建 parsers/types.py 放置共享类型定义，parsers 和 models 都依赖它 | |

**User's choice:** 字符串类型注解
**Notes:** 使用 TYPE_CHECKING + 字符串类型注解，保持与现有项目一致的模式。

---

## Claude's Discretion

- 模块内部函数组织方式（property_parser.py 和 property_types.py 的具体拆分）
- 蓝图变量提取的精确边界（哪些函数归属 blueprint/）
- 是否需要 PropertyParser 类封装或保持函数式风格

## Deferred Ideas

- UberGraph/事件分发图增强 — 属于 Phase 31 或 Phase 42
- 自定义节点类型处理器 — 游戏特定，超出范围
- JSON Schema 验证 — 属于 v9.0
