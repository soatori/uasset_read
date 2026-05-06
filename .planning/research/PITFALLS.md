# Domain Pitfalls

**Domain:** Python模块化重构（单文件拆分）
**Researched:** 2026-05-06
**Overall confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: 循环导入（Circular Imports）

**What goes wrong:**
当将单文件拆分为多个模块时，原来在同一作用域的类和函数现在分布在不同文件中，容易形成A模块导入B模块、B模块又导入A模块的循环依赖。Python导入系统在模块加载时立即执行导入语句，循环依赖会立即失败，导致`ImportError`。

**Why it happens:**
- 单文件中代码可以相互引用，但拆分后每个文件需要独立导入
- `from module import Class`语法比`import module`更容易触发循环导入
- 开发者关注"将代码移到合适的位置"，而忽视导入依赖关系
- 模块初始化需要在导入完成前完成，循环依赖违反此要求

**Consequences:**
- 无法启动应用程序或运行测试
- 即使代码逻辑正确，导入顺序错误也会导致失败
- 修复循环导入通常需要重新设计模块边界，成本高昂

**Prevention:**
1. **先绘制依赖图，再拆分模块** - 使用工具或手动分析代码中的导入关系，识别循环风险
2. **使用`import module`而非`from module import name`** - 延迟解析到运行时，而非导入时
3. **提取共享代码到第三个模块** - 如果A和B相互引用，将共享部分提取到C，让A和B都导入C
4. **延迟导入（Lazy Import）** - 将导入语句移到函数内部，只在需要时导入（但应谨慎使用）
5. **保持单向依赖** - 设计模块层次结构，上层模块可以导入下层，下层绝不能导入上层

**Detection:**
- 在拆分后立即运行`python -m pytest tests/`，任何`ImportError`都是警告
- 使用`python -c "import your_package"`测试顶层导入是否成功
- 注意`ModuleNotFoundError: attempted relative import with no known parent package`
- IDE或编辑器的导入分析工具可以提前发现循环引用

**Phase to address:** Phase 23 - 模块结构设计，必须在代码移动前完成

---

### Pitfall 2: 破坏API兼容性

**What goes wrong:**
模块化后，外部调用者使用的导入路径失效。例如，原来`from uasset_read import parse_uasset`，拆分后变成`from uasset_read.parser import parse_uasset`，导致所有外部代码需要修改。

**Why it happens:**
- 开发者认为"内部重组不影响用户"，但导入路径是公共API的一部分
- 将代码从`__init__.py`移到子模块时，没有重新导出
- 缺少明确的公共API定义（如`__all__`），不清楚哪些是用户依赖的

**Consequences:**
- 所有依赖该库的代码需要修改
- 破坏用户代码的信任，降低升级意愿
- 违反零运行时依赖原则（用户需要修改代码）

**Prevention:**
1. **在`__init__.py`中重新导出所有公共API** - 保持向后兼容
   ```python
   # __init__.py
   from .parser import parse_uasset
   from .models import ParseResult, PackageFileSummary
   from .archive import FArchive
   from .exceptions import UAssetError
   ```
2. **使用`__all__`显式定义公共API** - 让用户和工具都知道哪些是稳定的
   ```python
   __all__ = ['parse_uasset', 'ParseResult', 'PackageFileSummary', 'FArchive', 'UAssetError']
   ```
3. **添加弃用警告** - 如果必须移除某个导出，先发出警告给用户适应时间
   ```python
   import warnings
   warnings.warn("Old import path deprecated, use ... instead", DeprecationWarning, stacklevel=2)
   ```
4. **保持导入路径稳定** - 内部重组不应影响顶层导入
5. **文档化公共API契约** - 在CHANGELOG或文档中明确说明哪些导入路径是稳定的

**Detection:**
- 运行所有359个测试用例，任何导入错误都是兼容性破坏
- 检查现有代码中对`from uasset_read import ...`的所有使用
- 使用`git diff`确认`__init__.py`中保留了所有原来的导出

**Phase to address:** Phase 23 - API兼容性检查清单，每个模块拆分后必须验证

---

### Pitfall 3: 破坏测试导入

**What goes wrong:**
测试文件依赖特定的导入路径，模块化后测试无法运行。例如，测试中`from uasset_read import FArchive`，但`FArchive`现在在`uasset_read.archive`中，且没有在`__init__.py`重新导出。

**Why it happens:**
- 测试使用绝对导入路径，依赖于文件位置
- 模块级代码在导入时执行，pytest无法在加载前mock
- conftest.py中的fixture依赖特定的导入结构
- pytest的import模式（prepend vs importlib）影响导入行为

**Consequences:**
- 所有测试失败，失去代码变更的安全网
- 无法验证重构的正确性
- 增加回归风险

**Prevention:**
1. **使用`src/`布局** - 防止导入路径依赖于项目根目录
   ```
   uasset_read/
   ├── src/
   │   └── uasset_read/
   │       ├── __init__.py
   │       ├── archive.py
   │       └── ...
   └── tests/
       └── test_archive.py
   ```
2. **保持`__init__.py`重新导出** - 测试依赖的导入路径必须继续工作
3. **使用conftest.py注入模块** - 确保测试导入一致性
4. **避免模块级代码执行副作用** - 模块加载不应执行可能失败的代码
5. **使用相对导入（测试内部）** - 测试文件之间使用相对导入避免路径问题
6. **测试导入验证** - 在拆分每个模块后立即运行相关测试

**Detection:**
- 拆分模块后立即运行`python -m pytest tests/test_<module>.py`
- 注意`ModuleNotFoundError`和`ImportError`
- 检查`pytest --collect-only`是否能收集到所有测试
- 使用`pytest -v`查看导入失败的具体位置

**Phase to address:** Phase 24 - 每个子阶段拆分后立即运行测试，通过才能继续

---

### Pitfall 4: `__init__.py`重组破坏

**What goes wrong:**
将代码从`__init__.py`移动到子模块，但没有保留导入兼容性。原来`from uasset_read import Something`（`Something`定义在`__init__.py`中），拆分后需要改为`from uasset_read.submodule import Something`。

**Why it happens:**
- 认为`__init__.py`应该"干净"，只包含导入
- 忽视`__init__.py`是包的公共接口
- 不清楚哪些代码被外部调用者依赖

**Consequences:**
- 破坏向后兼容性
- 所有使用该库的代码需要修改
- 违反"最小化改动"原则

**Prevention:**
1. **`__init__.py`作为facade（门面）** - 重新导出所有公共API
   ```python
   # uasset_read/__init__.py
   # 核心API
   from .parser import parse_uasset
   from .models import ParseResult

   # 二进制读取
   from .archive import FArchive

   # 蓝图结构
   from .blueprint import UEdGraph, UEdGraphNode, UEdGraphPin

   # 导出所有公共API
   __all__ = [
       'parse_uasset',
       'ParseResult',
       'FArchive',
       'UEdGraph',
       'UEdGraphNode',
       'UEdGraphPin',
   ]
   ```
2. **保持`__init__.py`作为唯一公共入口** - 外部代码应只从顶层包导入
3. **分层导入** - `__init__.py`可以按逻辑分组导入
   ```python
   # 核心解析
   from .parser import parse_uasset
   from .models import ParseResult

   # 二进制读取
   from .archive import FArchive, PackageFileSummary

   # 错误处理
   from .exceptions import UAssetError, FArchiveError
   ```
4. **避免在`__init__.py`中执行复杂逻辑** - 只包含导入和简单的重新导出

**Detection:**
- 检查`__init__.py`是否导出了所有原来单文件中导出的符号
- 运行`python -c "from uasset_read import *"`（如果使用通配符导入）
- 对比拆分前后的`dir(uasset_read)`

**Phase to address:** Phase 23 - 模块结构设计阶段，确定`__init__.py`的内容

---

## Moderate Pitfalls

### Pitfall 1: dataclass跨模块引用

**What goes wrong:**
拆分模块后，dataclass类型注解引用了其他模块的类，导致导入时`ImportError`或`typing.TYPE_CHECKING`问题。例如，`UEdGraphNode`在`blueprint.py`中，但`FArchive`在`archive.py`中，相互引用。

**Why it happens:**
- dataclass的类型注解在模块加载时评估，而非运行时
- 循环引用导致类型注解无法解析
- 开发者不注意类型注解的导入时机

**Consequences:**
- 模块无法导入
- 类型提示失效
- `asdict()`序列化失败

**Prevention:**
1. **使用`typing.TYPE_CHECKING`延迟类型检查**
   ```python
   from typing import TYPE_CHECKING

   if TYPE_CHECKING:
       from .blueprint import UEdGraphNode

   @dataclass
   class FArchive:
       current_graph: Optional['UEdGraphNode'] = None  # 字符串延迟解析
   ```
2. **将类型注解保留为字符串** - Python会自动解析字符串形式的类型注解
   ```python
   @dataclass
   class ParseResult:
       graphs: List['UEdGraph']  # 字符串形式
   ```
3. **使用`from __future__ import annotations`** - Python 3.7+特性，所有类型注解变为字符串
   ```python
   from __future__ import annotations
   from typing import List

   # 所有类型注解自动变为字符串，无需引号
   @dataclass
   class ParseResult:
       graphs: List[UEdGraph]  # 自动延迟解析
   ```
4. **设计清晰的模块层次** - 避免dataclass相互引用，高层可以引用低层

**Detection:**
- 导入模块时注意`TypeError`或`NameError`
- 运行`mypy`或`pyright`类型检查器发现循环引用
- 检查dataclass的`__annotations__`是否正确解析

**Phase to address:** Phase 24 - 在拆分每个模块时检查dataclass引用

---

### Pitfall 2: 模块级代码执行副作用

**What goes wrong:**
模块导入时执行的代码（模块级别的表达式、函数调用、类实例化）在测试环境中失败。例如，模块级读取配置文件或注册处理器，但测试环境缺少这些资源。

**Why it happens:**
- 在模块顶层执行初始化代码
- 假设导入时的环境与运行时相同
- 忽视pytest在导入时也会执行模块级代码

**Consequences:**
- 测试收集阶段失败
- pytest无法运行任何测试
- 导入模块时副作用不可预测

**Prevention:**
1. **延迟初始化** - 将模块级代码移到函数或类方法中
   ```python
   # 错误：模块级执行
   config = load_config()  # 导入时就执行

   # 正确：延迟初始化
   _config = None

   def get_config():
       global _config
       if _config is None:
           _config = load_config()
       return _config
   ```
2. **使用`if __name__ == "__main__"`** - 将需要运行的脚本代码放在此块中
3. **避免模块级副作用** - 模块导入应该是纯函数式的，无副作用
4. **测试环境隔离** - 使用pytest fixtures提供测试所需的环境

**Detection:**
- pytest收集失败，报告"failed during collection"
- 注意"import error"而非"test failure"
- 运行`python -c "import module"`独立测试导入

**Phase to address:** Phase 24 - 拆分模块时确保无模块级副作用

---

### Pitfall 3: 相对导入vs绝对导入混用

**What goes wrong:**
在模块中混用`from .sibling import X`（相对导入）和`from package.sibling import X`（绝对导入），导致包重命名或移动后导入失败。

**Why it happens:**
- 开发者习惯于相对导入（认为更简洁）
- 不同开发者使用不同风格
- 不清楚Python导入系统的行为差异

**Consequences:**
- 包结构变化时导入失败
- 代码可移植性差
- IDE和工具可能无法正确解析

**Prevention:**
1. **统一使用绝对导入** - 推荐在包内使用绝对导入
   ```python
   # 推荐
   from uasset_read.archive import FArchive

   # 避免（除非测试文件）
   from .archive import FArchive
   ```
2. **测试文件可以使用相对导入** - 测试在tests/目录内，相对导入更清晰
   ```python
   # tests/test_archive.py
   from ..src.uasset_read.archive import FArchive
   ```
3. **遵循PEP 8建议** - 绝对导入更明确、更清晰
4. **使用`isort`或`autopep8`** - 自动化导入排序和规范化

**Detection:**
- 代码审查时检查导入风格一致性
- 使用`flake8`或`pylint`检查导入规范
- 注意`Relative imports are not allowed in non-package`错误

**Phase to address:** Phase 23 - 制定导入规范并统一执行

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| 临时`sys.path.insert()`解决导入问题 | 快速让代码运行 | 破坏打包和安装，增加运行时脆弱性 | NEVER - 使用正确的包结构或`pip install -e .` |
| 延迟导入修复循环依赖 | 快速避免ImportError | 隐藏设计问题，代码难以理解，性能损失 | 仅在Phase 23-24临时过渡，后续重构 |
| `from x import *`快速导出大量符号 | 简化`__init__.py` | 命名空间污染，`__all__`失效，IDE无法自动补全 | NEVER - 显式导入每个符号 |
| 忽略`__all__`定义 | 省略一行代码 | 公共API不明确，意外导出内部符号，未来重构困难 | 仅在单文件MVP阶段，模块化时必须添加 |
| 绕过类型注解使用`Any` | 避免导入问题 | 失去类型检查，代码可维护性下降 | 仅在循环引用无法避免时，配合TYPE_CHECKING使用 |
| 将测试和源码放在同一目录 | 简化导入 | 打包困难，部署问题，不符合最佳实践 | NEVER - 使用tests/目录分离 |

---

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| pytest | 在测试中直接修改sys.path | 使用conftest.py或`pip install -e .`正确安装包 |
| 类型检查器（mypy/pyright） | 忽略循环引用导致类型错误 | 使用`TYPE_CHECKING`或字符串类型注解 |
| IDE自动导入 | 自动使用相对导入 | 配置IDE使用绝对导入（推荐） |
| 打包（pyproject.toml） | 忘记声明packages | 使用`find_packages()`或显式声明 |
| 文档生成（Sphinx） | 文档导入路径与实际不符 | 使用`autodoc_mock_imports`或重新设计导入 |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| 延迟导入过度使用 | 首次调用时慢，模块加载延迟，难以缓存 | 优先使用顶层导入，延迟导入仅在必要时 | 高频调用或热路径代码 |
| `__init__.py`导入过多符号 | 包启动慢，内存占用高 | 按需导入或使用`__getattr__`延迟加载 | 包包含数百个导出符号时 |
| 循环导入的临时修复 | 导入时间线性增长 | 重构模块消除循环依赖 | 模块数量>20且相互依赖复杂时 |
| 测试导入副作用 | pytest收集测试慢，内存泄漏 | 避免模块级副作用，使用fixture | 测试数量>500时 |

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| 未经验证的二进制反序列化 | 远程代码执行，DoS攻击 | 验证文件头，限制内存使用，拒绝异常大文件 |
| 依赖`__init__.py`执行路径 | 路径遍历攻击 | 不依赖导入路径执行操作，显式验证文件位置 |
| 类型注解作为输入验证 | 错误的安全假设 | 类型注解仅用于提示，不提供运行时验证 |

---

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| 破坏导入路径无警告 | 用户升级后代码立即失败，措手不及 | 使用DeprecationWarning至少一个版本周期 |
| 移除API但文档未更新 | 用户查阅文档但API不存在，困惑 | 文档和代码同步更新，使用CHANGELOG记录破坏性变更 |
| 隐藏循环导入错误 | 用户看到模糊的ImportError，不知如何修复 | 在错误消息中明确说明循环依赖和解决建议 |
| 测试失败但代码"可用" | 用户怀疑项目质量，不敢使用 | 保证测试100%通过，CI自动运行测试 |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **所有359个测试用例通过** — 运行`pytest tests/ -v`，确保无失败、无跳过
- [ ] **`__init__.py`导出所有原单文件的公共符号** — 对比`dir(uasset_read)`和原单文件导出
- [ ] **无循环导入** — 所有模块可以独立导入，`python -m pytest tests/ --collect-only`成功
- [ ] **`__all__`正确定义** - 文档化公共API，防止意外导出内部符号
- [ ] **类型注解可解析** - 运行`mypy`或`pyright`无类型错误
- [ ] **打包可安装** - `pip install -e .`成功，`python -c "import uasset_read"`成功
- [ ] **文档更新** - 更新所有代码示例和文档中的导入路径
- [ ] **CHANGELOG记录** - 记录所有破坏性变更和弃用警告
- [ ] **零依赖验证** - 检查`pyproject.toml`确保无运行时依赖
- [ ] **兼容性测试** - 测试旧代码使用新导入路径仍能工作

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| 循环导入 | HIGH | 1. 绘制依赖图识别循环 2. 提取共享代码到新模块 3. 重构模块层次为单向 4. 更新所有导入 5. 运行测试验证 |
| 破坏API兼容性 | MEDIUM | 1. 在`__init__.py`重新导出旧符号 2. 添加DeprecationWarning 3. 更新文档说明新路径 4. 给用户一个版本周期适应 5. 在下一个大版本移除 |
| 测试破坏 | LOW | 1. 检查失败的测试导入路径 2. 在`__init__.py`补充缺失的导出 3. 运行测试验证 4. 更新测试文档说明导入规范 |
| `__init__.py`重组破坏 | MEDIUM | 1. 回滚`__init__.py`变更 2. 使用`git diff`对比原导出列表 3. 重新添加所有缺失的导入 4. 添加`__all__`显式列表 5. 测试验证 |
| dataclass循环引用 | MEDIUM | 1. 使用`TYPE_CHECKING`延迟类型检查 2. 或将类型注解改为字符串 3. 或添加`from __future__ import annotations` 4. 运行类型检查器验证 |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 循环导入 | Phase 23 - 模块结构设计 | 绘制依赖图，确保无循环；所有模块独立导入成功 |
| 破坏API兼容性 | Phase 23 - API兼容性检查清单 | 所有359测试通过；`__init__.py`重新导出所有原符号 |
| 破坏测试导入 | Phase 24 - 每个子阶段拆分后 | 拆分模块后立即运行`pytest tests/test_<module>.py`，通过才能继续 |
| `__init__.py`重组破坏 | Phase 23 - `__init__.py`设计阶段 | 对比拆分前后导出列表，确保完全一致 |
| dataclass跨模块引用 | Phase 24 - 拆分模块时检查 | 运行`mypy`类型检查，无循环引用错误 |
| 模块级代码执行副作用 | Phase 24 - 拆分模块时检查 | `python -c "import module"`无副作用；pytest收集成功 |
| 相对导入vs绝对导入混用 | Phase 23 - 制定导入规范 | 使用`flake8`检查导入一致性；统一使用绝对导入 |

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Phase 23 - 模块结构设计 | 循环导入、API兼容性 | 先绘制依赖图再设计；使用`__init__.py`重新导出 |
| Phase 24 - 核心组件拆分 | 测试破坏、dataclass引用 | 每拆分一个模块立即运行测试；使用`TYPE_CHECKING` |
| Phase 25 - 蓝图模块拆分 | 循环导入（蓝图图结构复杂） | 保持单向依赖；提取共享模型 |
| Phase 26 - 零依赖验证 | 意外引入外部依赖 | 检查`pyproject.toml`；运行`pip check` |
| Phase 27 - 测试兼容性验证 | 测试导入路径 | 所有359测试通过；使用conftest.py |

## Sources

### 循环导入（HIGH confidence）
- [Stack Overflow: How to avoid circular imports in Python?](https://stackoverflow.com/questions/7336802/how-to-avoid-circular-imports-in-python) - 权威问答社区，详细讨论循环导入原因和解决方案
- [DataCamp: Python Circular Import Tutorial](https://www.datacamp.com/tutorial/python-circular-import) - 结构化教程，涵盖原因、修复和最佳实践
- [Python Morsels: Fixing circular imports](https://www.pythonmorsels.com/fixing-circular-imports/) - Python专家的实用指南
- [Rollbar: How to Fix a Circular Import in Python](https://rollbar.com/blog/how-to-fix-circular-import-in-python/) - 工程化视角的解决方案
- [Medium: So you got a circular import in Python](https://medium.com/@hamana.hadrien/so-you-got-a-circular-import-in-python-e9142fe10591) - 实际案例分析

### API兼容性（HIGH confidence）
- [Stack Overflow: Moving code out of __init__.py but keeping backwards compatibility](https://stackoverflow.com/questions/5427204/moving-code-out-of-init-py-but-keeping-backwards-compatibility) - 关于`__init__.py`重组的权威讨论
- [Stack Overflow: Refactoring a module and keeping backward compatibility](https://stackoverflow.com/questions/44139641/refactoring-a-module-and-keeping-backward-compatibility-including-for-intersphi) - 重构时保持兼容性的实用技巧
- [Real Python: Best Practices for Imports](https://realpython.com/ref/best-practices/imports/) - Python导入最佳实践，权威指南
- [Hacker News: Best practice for Python module imports?](https://news.ycombinator.com/item?id=657528) - 社区讨论，共识观点
- [Python Documentation: The import system](https://docs.python.org/3/reference/import.html) - 官方文档，导入系统权威说明

### 测试兼容性（HIGH confidence）
- [The Digital Cat: Refactoring with tests in Python - a practical example](https://www.thedigitalcatonline.com/blog/2017/07/21/refactoring-with-test-in-python-a-practical-example/) - 实际案例，展示测试驱动的重构流程
- [Alan Turing Institute: 7.4 Refactoring](https://alan-turing-institute.github.io/rse-course/html/module07_construction_and_design/07_04_refactoring.html) - 科学软件工程研究机构的重构指南
- [DEV Community: Testing and Refactoring With pytest and pytest-cov](https://dev.to/cwprogram/testing-and-refactoring-with-pytest-and-pytest-cov-22d6) - pytest最佳实践
- [Stack Overflow: Pytest import problems when tests import from adjacent directory](https://stackoverflow.com/questions/73726523/pytest-import-problems-when-tests-import-from-adjacent-directory) - pytest导入问题解决方案
- [Pytest Documentation: Deprecations and Removals](https://docs.pytest.org/en/stable/deprecations.html) - 官方文档，pytest导入系统说明

### 项目结构与零依赖（HIGH confidence）
- [Medium: Zero-Dependency Python: Building Tools That Avoid External Libraries](https://medium.com/@CodeWithHannan/zero-dependency-python-building-tools-that-avoid-external-libraries-f2a8f5092b57) - 零依赖Python项目实战指南
- [The Hitchhiker's Guide to Python: Structuring Your Project](https://docs.python-guide.org/writing/structure/) - Python项目结构权威指南
- [Real Python: Project Layout Best Practices](https://realpython.com/ref/best-practices/project-layout/) - Python项目布局推荐
- [Reddit: What is the optimal structure for a Python project?](https://www.reddit.com/r/Python/comments/18qkivr/what-is-the-optimal-structure-for-a-python-project/) - 社区讨论最佳实践
- [Dagster: Best Practices in Structuring Python Projects](https://dagster.io/blog/python-project-best-practices) - 工业级Python项目结构经验

### dataclass序列化（MEDIUM confidence）
- [Stack Overflow: How do I make a custom class that's serializable with dataclasses](https://stackoverflow.com/questions/77943054/how-do-i-make-a-custom-class-thats-serializable-with-dataclasses-asdict) - dataclass序列化问题解决方案
- [Tom Augspurger: Serializing Dataclasses](https://tomaugspurger.net/posts/serializing-dataclasses/) - 深入解析dataclass序列化挑战
- [Real Python: dataclasses Reference](https://realpython.com/ref/stdlib/dataclasses/) - 标准库官方参考
- [Python Discussions: dataclasses.asdict(type)](https://discuss.python.org/t/dataclasses-asdicttype-type/103448) - 社区讨论dataclass序列化新特性

### 导入风格（MEDIUM confidence）
- [Stack Overflow: What's the correct way to sort Python import statements](https://stackoverflow.com/questions/20762662/whats-the-correct-way-to-sort-python-import-x-and-from-x-import-y-statement) - 导入排序和最佳实践
- [Reddit: Is there a big difference between using import x vs from x import y?](https://www.reddit.com/r/learnpython/comments/5lggna/is-there-a-big-difference-between-using_import_x/) - 社区讨论导入风格差异
- [Level Up Coding: Import X VS From Y Import Z](https://levelup.gitconnected.com/import-x-vs-from-y-import-z-58b55c167f65) - 详细对比两种导入方式
- [Bric-a-brac: From X import Y vs. import X (as Z)](https://matevzkunaver.wordpress.com/2017/02/27/from-x-import-y-vs-import-x-as-z/) - 实用指南

### 弃用与兼容性（MEDIUM confidence）
- [Python Discuss: Mitigating python deprecation message frustrations](https://discuss.python.org/t/mitigating-python-deprecation-message-frustrations-by-improving-the-design-of-deprecation-message-handling/61985) - Python核心开发者关于弃用消息的讨论
- [Stack Overflow: Correct way to re-export modules from __init__.py](https://stackoverflow.com/questions/60440945/correct-way-to-re-export-modules-from-init-py) - `__init__.py`重新导出的权威讨论
- [Python What's New 3.14: Deprecated aliases removed](https://docs.python.org/3/whatsnew/3.14.html) - 官方弃用策略说明

### 延迟导入（MEDIUM confidence）
- [Python Discuss: PEP 690 - Lazy Imports](https://discuss.python.org/t/pep-690-lazy-imports/15474?page=10) - PEP 690延迟导入提案讨论
- [Hacker News: PEP 810 – Explicit lazy imports](https://news.ycombinator.com/item?id=45466086) - 社区对延迟导入的看法

---

*Pitfalls research for: Python模块化重构（单文件拆分）*
*Researched: 2026-05-06*
*Focus: 零依赖约束下的测试兼容性和API稳定性*