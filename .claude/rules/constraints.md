# 项目约束

## 核心约束

- **仅支持未烘焙/编辑器保存的资产** — 已烘焙资产的图数据已被剥离
- **只读** — 仅解析，禁止修改或写入
- **零运行时依赖** — `dependencies` 中不允许第三方包（PAK 可选依赖放在 `optional-dependencies`）
- **禁止 `pip install`** — 直接通过 `python run.py` 运行；CI 中 `pip install pytest` 仅用于测试
- **必须参考 UE 源码** — 格式理解必须追溯到 UE C++ 源码；禁止猜测二进制格式
- **临时文件存放在 `temp/`** — 脚本、中间输出、调试日志、测试产物

## 设计约束

- **统一状态模型** — 所有输出格式使用 `success | partial | failed`；不使用旧版 `fail`/`error`
- **导出级状态验证** — `parse_status` 必须是 `ExportParseStatus` 枚举值
- **UE 风格加载生命周期** — 执行顺序：`link() → preload(idx) × N → post_load()`；禁止在导出解析前调用 post_load
- **类序列化策略** — 通过 `class_serialization_strategy.py` 注册；核心管道中禁止硬编码类名
- **载荷偏移默认值** — 使用 `SerialOffset/SerialSize`（与 UE LinkerLoad.cpp:4793 对齐）；ScriptSerialization 偏移仅作诊断用途
- **不透明类标记** — `OPAQUE_CLASS_PAYLOAD` 必须同时设置实例和导出的 `parse_status`
- **无需向后兼容** — 本项目处于快速迭代阶段，API 和内部结构可自由重构，无需维护旧版兼容层
- **废弃代码即时清理** — 发现废弃代码（dead code、旧版别名、已弃用接口）时，在同一提交中直接删除，不保留 deprecated 标记或过渡期
- **优先最小实现** — 代码以最简方式实现目标，避免过度抽象、冗余封装和不必要的复杂度

## 测试文件规则

- **`tests/` 根目录仅保留 6 个测试文件** — 5 个基准测试 + 1 个样本测试（`tests/samples/`）
- **基准测试修改需确认** — 修改任何基准测试文件前，必须先说明变更内容并获得用户同意
- **其余测试放置在 `tests/temp/`** — 新增的实验性、临时性或非基准测试文件一律放入 `tests/temp/`，CI 不收集该目录
- **`tests/samples/` 仅存放测试用 `.uasset` 样本文件** — 不在此目录放置 Python 测试代码
