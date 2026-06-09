# 项目约束

## 核心约束

- **仅支持未烘焙/编辑器保存的资产** — Cooked 资产的图数据已被剥离
- **只读** — 仅解析，不支持修改或写入
- **零运行时依赖** — 不向 `dependencies` 添加第三方包（PAK 可选依赖在 `optional-dependencies` 中）
- **禁止 pip install** — 项目采用直接脚本运行（`python run.py`），禁止 `pip install -e .` 或 `pip install uasset_read`。CI 中的 `pip install pytest` 仅用于测试框架，不安装项目本身
- **必须参考 UE 源码** — 格式理解必须追溯到 UE C++ 源码，禁止猜测二进制
- **GUID 格式统一** — Pin GUID 在源头标准化为 32 位小写 hex（无 dashes），比较前统一格式
- **FText 偏移安全网** — 图序列化器包含 safety net 检测偏移错位，遇到时自动校正
- **临时文件放 `temp/`** — 脚本、中间输出、调试日志、测试产物一律放在项目根目录 `temp/` 子目录

## v0.4.5 新增约束

- **统一状态模型** — 所有输出格式使用 `success | partial | failed`，禁止使用旧的 `fail`/`error`
- **UE 风格加载生命周期** — 执行顺序必须为 `link() → preload(idx) × N → post_load()`，禁止在 export 解析前调用 post_load
- **类序列化策略** — 通过 `class_serialization_strategy.py` 注册，禁止在核心管线硬编码类名判断
- **Payload 偏移默认策略** — 默认使用 `SerialOffset/SerialSize`（与 UE LinkerLoad.cpp:4793 对齐），ScriptSerialization 偏移仅保留为诊断字段
- **Opaque 类标记** — OPAQUE_CLASS_PAYLOAD 类必须同时设置 instance 和 export 的 parse_status，禁止仅设置一方

## CodeGraph 使用

优先使用 `codegraph_*` 工具回答结构化问题（符号定义、调用链、影响范围）。详细规则见全局 CLAUDE.md。
