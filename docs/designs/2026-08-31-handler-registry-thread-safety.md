# Handler Registry 线程安全（G3）

status: target

> P2，deferred：等 MCP 多线程消费真实出现后再实施。本文只锁定决策，防止届时重新讨论。

## 现状（基线 bd3309a7 核实）

- 模块级可变列表：`_HANDLERS: list[AssetHandler] = []`（`src/uasset_read/v2/handlers.py:33`）。
- `register_handler` 对全局列表 `append`（`handlers.py:36-38`）；`get_handlers` 每次返回浅拷贝 `list(_HANDLERS)`（`handlers.py:41-43`）；`run_handlers` **直接迭代全局变量**（`handlers.py:63`）。
- 解析热路径经 `legacy.py:32` 导入、`legacy.py:455` 调用 `run_handlers`。

### 注册仅发生在 import 期——核实属实

`src/` 内全部 `register_handler(...)` 调用点均为 `handlers.py` 模块体顶层语句：`handlers.py:463-468`、`690-693`、`815-822`、`864`。除 `handlers.py` 自身外没有任何生产代码调用它（`legacy.py` 只 import `run_handlers`）。运行时唯一变更来源是测试：`tests/test_core.py` 用 `_HANDLERS[:] = ...` 切片赋值（:363、:388、:411、:524、:553）和 `register_handler(BadHandler())`（:515）注入。

## 决策：方案 B——import 窗口结束后冻结为 tuple

模块末尾（`handlers.py:864` 之后）执行冻结，`run_handlers` 继续读模块全局（调用时查找，重绑定依然生效）：

```python
_HANDLERS = tuple(_HANDLERS)   # import 期结束即冻结

def register_handler(handler):
    if isinstance(_HANDLERS, tuple):
        raise RuntimeError("handler registry is frozen after import")
    _HANDLERS.append(handler)
```

测试注入从"改内容"改为"换引用"：`handlers._HANDLERS = (Boom(), Ok())`，teardown 恢复原 tuple。涉及 `test_core.py` 约 6 处机械替换。

### 为什么 B 比 A（加锁）小且强

- 方案 A 要在 `register_handler` 与 `run_handlers` 两侧加 `threading.Lock`，并且 `run_handlers` 每次解析都得持锁或先快照——给一个**根本没有运行时写入者**的列表加锁，是纯负债。
- B 把整类"迭代中被 append/重绑定"的问题清零：运行时零锁、零可变性，CPython GIL 甚至不再参与语义正确性。
- 注册既然只在 import 期（上节核实），A 防的是不存在的写入。

### B 的代价（如实列出）

- 失去运行时扩展点：第三方想追加 handler 必须重绑 `handlers._HANDLERS` 全局（monkeypatch 语义，明确不支持并发下的重绑）。真正的插件式注册需求出现时，正确解法是 per-parse 注入（`LegacyPackageReader(handlers=...)`），不是解冻全局。
- 现有测试的 `_HANDLERS[:] = ...` 切片写法全部失效，需同步改。

## 触发条件

MCP adapter 出现多线程并发消费（线程池或 async 桥接 worker）即实施；在那之前维持现状，仅以本文锁定方案。实施时同步在 `handlers.py` 顶部 docstring 写明"注册仅限 import 期"。
