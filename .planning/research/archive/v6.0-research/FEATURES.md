# Feature Landscape

**Domain:** Python单文件模块化重构（二进制解析器）
**Researched:** 2026-05-06
**Project Size:** ~5,100行单文件代码

## Table Stakes

重构时必须具备的特性。缺少这些会让重构失败或引入严重问题。

| 特性 | 为什么必需 | 复杂度 | 说明 |
|------|-----------|--------|------|
| **API向后兼容性** | 用户依赖现有导入路径 | 低 | 通过`__init__.py`重新导出所有公共API，使用`__all__`声明稳定接口 |
| **保持功能不变** | 重构仅改变代码组织 | 高 | 必须通过全部359测试用例，不能有功能性变更 |
| **循环导入预防** | Python模块重构常见陷阱 | 中 | 延迟导入、重新组织依赖、使用`import module`而非`from import` |
| **清晰模块边界** | 单一职责原则 | 中 | 每个模块一个明确的职责，避免模糊边界 |
| **测试可运行性** | 重构过程中持续验证 | 低 | pytest支持unittest测试，无需立即迁移测试框架 |
| **导入路径稳定性** | 现有代码不应中断 | 低 | 主入口`from uasset_read import *`必须保持工作 |
| **类型提示完整性** | Python 3.10+特性 | 低 | 拆分后保持所有类型提示正确，不引入类型错误 |

## Differentiators

让重构有价值但不必需的特性。具备这些会让未来维护更容易。

| 特性 | 价值主张 | 复杂度 | 说明 |
|------|---------|--------|------|
| **src布局** | 符合Python打包最佳实践 | 低 | 将代码放入`src/uasset_read/`，防止导入混淆，强制安装测试 |
| **分层架构** | 清晰的关注点分离 | 中 | FArchive(二进制) → Deserializer(反序列化) → Models(数据模型) → Output(输出) |
| **依赖最小化** | 降低循环导入风险 | 低 | 模块间松耦合，仅在必要时导入，优先延迟导入 |
| **文档同步更新** | 代码结构变更后API文档仍准确 | 中 | 更新docstring、README、API导出说明 |
| **模块级`__all__`** | 明确公共vs私有边界 | 低 | 在每个模块声明`__all__`，用于静态分析工具检查边界违规 |
| **可重用性** | 单一模块可独立使用 | 中 | 其他项目可仅导入需要的子模块（如仅使用`FArchive`类） |

## Anti-Features

明确不做的特性。做这些会导致过度设计。

| Anti-Feature | 为什么避免 | 替代方案 |
|--------------|-----------|---------|
| **过度拆分** | 5000行代码不需要20个模块 | 4-6个模块足够，每个800-1500行 |
| **抽象层过多** | 增加理解成本，未必有价值 | 直接实现，避免不必要的factory/builder模式 |
| **预测式拆分** | 基于假设未来需求而非当前代码 | 仅在发现真实痛点时拆分 |
| **过早优化性能** | 代码组织优先于性能 | 保持代码清晰，性能优化在需求出现时再做 |
| **完美主义架构** | 重构不是重写 | 保持现有算法不变，仅移动代码位置 |
| **立即迁移测试框架** | pytest可以直接运行unittest | 保持测试不变，未来需要时再迁移 |
| **C++代码生成** | 当前里程碑不包含 | 延后至v5.2或v6.0里程碑 |
| **复杂的依赖注入** | 增加导入复杂度 | 使用简单实例化，仅在循环导入问题时引入工厂 |

## Feature Dependencies

```
API向后兼容性 → 模块边界设计 → src布局决策
循环导入预防 → 模块导入顺序 → 测试可运行性
功能不变保证 → 测试通过 → 重构完成
```

## MVP Recommendation

对于uasset_read.py（~5,100行）的模块化重构，按优先级：

### 必须做（Table Stakes）
1. **API向后兼容性** — 使用`__init__.py`重新导出所有现有公共API
2. **保持功能不变** — 确保所有359测试用例通过，零功能性变更
3. **循环导入预防** — 设计导入顺序，使用延迟导入策略
4. **清晰模块边界** — 4-6个模块，每个职责单一

### 强烈推荐（Differentiators）
5. **src布局** — 符合Python最佳实践，`src/uasset_read/`目录结构
6. **分层架构** — 按数据流分层，而非按技术组件分组

### 可选（延后）
7. **模块级`__all__`** — 增加清晰度但非必需
8. **文档同步更新** — 重构完成后再统一更新

## 推荐模块结构（4-6模块）

基于现有代码分析，建议按以下边界拆分：

```
src/uasset_read/
├── __init__.py                 # 公共API导出（向后兼容）
├── archive.py                  # FArchive二进制读取器
├── parser.py                   # PackageFileSummary、反序列化逻辑
├── models.py                   # 所有dataclass模型（UEdGraph等）
├── graph_parser.py             # 蓝图图解析器（Phase 7-10）
└── output.py                   # JSON/文本输出格式化
```

**模块数量：** 6个（4-6的最佳范围）<br>
**平均行数：** ~850行/模块<br>
**依赖关系：** `archive.py` ← `parser.py` ← `graph_parser.py` → `models.py` → `output.py`

## 复杂度评估

| 阶段 | 复杂度 | 风险 | 时间估算 |
|------|--------|------|----------|
| 模块边界设计 | 中 | 低 | 2-4小时 |
| 代码拆分 | 高 | 中 | 8-16小时 |
| 修复导入问题 | 高 | 高 | 4-12小时 |
| 测试验证 | 低 | 中 | 1-3小时 |
| **总计** | **高** | **中** | **15-35小时** |

## 避免5000行代码过度设计的信号

根据社区实践，以下信号表明可能在过度设计：

1. **创建超过10个模块** — 5000行代码不需要太多模块
2. **引入复杂的工厂模式** — 直接实例化更简单
3. **过早抽象层** — 未来需求未出现，当前直接实现即可
4. **过度使用ABC（抽象基类）** — 增加理解成本
5. **过度依赖注入** - 增加导入复杂度，仅在必要时使用
6. **追求完美的SOLID原则** — 5个原则全部实施可能导致过度工程
7. **预测式解耦** — 基于假设而非实际需求拆分

**引用：** "Relentlessly cut design features you don't need. Then relentlessly refactor your code when you discover you do need them." ([29] Hacker News)

## 小项目 vs 大项目需求差异

| 方面 | 小项目（<5000行） | 大项目（>20000行） |
|------|------------------|-------------------|
| **模块数量** | 4-6个 | 10-20+个 |
| **架构模式** | 简单分层 | 完整Clean Architecture |
| **依赖注入** | 很少需要 | 必需（复杂依赖图） |
| **工厂模式** | 偶尔 | 普遍 |
| **文档要求** | README + docstring | 完整API文档 |
| **测试分层** | 单元测试 | 单元+集成+E2E |

**uasset_read定位：** 属于小项目到中等项目临界点，建议保持小项目思维，避免过早引入大项目复杂度。

## Sources

### Web Search Sources

- [Stack Overflow: Best practices for splitting large Python files](https://www.reddit.com/r/learnpython/comments/khj8nd/little_confused_on_best_practices_for_splitting/) — 社区共识：按逻辑职责分组，不要过度拆分
- [Teclado: Day 21 - Splitting Code Into Multiple Files](https://teclado.com/30-days-of-python/python-30-day-21-multiple-files/) — 初学者友好的多文件拆分指南
- [Stack Overflow: Avoiding circular imports in Python](https://stackoverflow.com/questions/7336802/how-to-avoid-circular-imports-in-python) — 经典讨论：8种防止循环导入的策略
- [Rollbar: How to Fix Circular Imports in Python](https://rollbar.com/blog/how-to-fix-a-circular-import-in-python/) — 通过重构共享模块打破依赖链
- [Medium: 8 Effective Strategies to Avoid Circular Imports](https://medium.com/@sandeepkumar172967/8-effective-strategies-to-avoid-circular-imports-in-python-a-comprehensive-guide-1a3c21b184b220) — 8种策略及代码示例
- [LogRocket: Single Responsibility Principle (SRP)](https://blog.logrocket.com/single-responsibility-principle-srp/) — SRP在模块边界设计中的应用
- [Real Python: SOLID Principles in Python](https://realpython.com/solid-principles-python/) — SOLID原则的Python实践
- [The Hitchhiker's Guide to Python: Structuring Your Project](https://docs.python-guide.org/writing/structure/) — Python项目结构标准
- [Python Packaging User Guide: src layout vs flat layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/) — 推荐src布局作为现代标准
- [Level Up Coding: How I Manage Large Python Projects](https://levelup.gitconnected.com/how-i-manage-large-python-projects-without-losing-my-sanity-ee9d67b96d7a) — 大型项目实用管理策略
- [Medium: Clean Architecture in Python Without Overengineering](https://medium.com/the-pythonworld/clean-architecture-in-python-without-overengineering-d1088f179de2) — 避免过度设计的实践方法
- [Instagram Engineering: Python at Scale: Strict Modules](https://instagram-engineering.com/python-at-scale-strict-modules-c0bb9245c834) — 大规模项目模块化经验
- [Hacker News: How to avoid over-engineering software](https://news.ycombinator.com/item?id=23612415) — 过度工程的警告信号
- [Real Python: Python's __all__: Packages, Modules, and Wildcard Imports](https://realpython.com/python-all-attribute/) — `__all__`的使用和公共API声明
- [Medium: Demystifying __all__ in Python](https://medium.com/@akshatgadodia/demystifying-all-in-python-a-closer-look-at-module-exports-f4d818a12bb6) — `__all__`详解及向后兼容性
- [Stack Overflow: Refactoring a module and keeping backward compatibility](https://stackoverflow.com/questions/44139641/refactoring-a-module-and-keeping-backward-compatibility-including-for-intersphi) — 保持向后兼容的具体方法
- [Stack Overflow: Parsing binary data in Python](https://stackoverflow.com/questions/30630090/parsing-binary-data-into-separate-variables-in-python) — 二进制解析的标准实践

### Confidence Levels

| 领域 | 信心 | 理由 |
|------|------|------|
| Table Stakes特性 | HIGH | 多个权威来源一致（Stack Overflow、Python官方指南） |
| 模块边界策略 | MEDIUM | 基于社区实践，需根据实际代码调整 |
| 循环导入预防 | HIGH | 官方文档+多篇权威文章确认 |
| 避免5000行过度设计 | HIGH | 多个来源警告预测式拆分的风险 |
| 向后兼容性方法 | HIGH | Python打包官方指南和NumPy实践案例 |
| src布局推荐 | HIGH | Python Packaging User Guide明确推荐 |

### 未验证项（需后续验证）

- **实际拆分后的性能影响** — 未找到针对二进制解析器模块化性能的量化研究（MEDIUM）
- **pytest迁移的具体收益** — 测试框架迁移的时间和复杂度评估基于通用案例，非二进制解析器特定（MEDIUM）