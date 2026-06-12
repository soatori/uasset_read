# 项目约束

## 核心约束

- **仅支持未烘焙/编辑器保存的资产** — Cooked 资产的图数据已被剥离
- **只读** — 仅解析，不支持修改或写入
- **无向后兼容** — 纯输出脚本，不对外暴露 API，接口可直接修改/删除，无需版本过渡
- **零运行时依赖** — 不向 `dependencies` 添加第三方包（PAK 可选依赖在 `optional-dependencies` 中）
- **禁止 pip install** — 项目采用直接脚本运行（`python run.py`），禁止 `pip install -e .` 或 `pip install uasset_read`。CI 中的 `pip install pytest` 仅用于测试框架，不安装项目本身
- **必须参考 UE 源码** — 格式理解必须追溯到 UE C++ 源码，禁止猜测二进制
- **版本优先级** — 主要支持 UE5+，UE4 仅兼容部分主要资产类型，不为 UE4 特有边界情况投入过多精力
- **输出质量标准** — 不直接输出 C++ 代码，但解析输出质量必须与对照的 C++ 类定义和蓝图节点文本相匹配（结构、逻辑、语义可准确还原）
- **序列化策略** — 优先遵从 UE 编辑器源码的 `FArchive` 序列化加载方式，仅在语言环境、本地化等特殊场景才使用替代加载方式
- **GUID 格式统一** — Pin GUID 在源头标准化为 32 位小写 hex（无 dashes），比较前统一格式
- **FText 偏移安全网** — 图序列化器包含 safety net 检测偏移错位，遇到时自动校正
- **临时文件放 `temp/`** — 脚本、中间输出、调试日志、测试产物一律放在项目根目录 `temp/` 子目录

## v0.4.5 新增约束

- **统一状态模型** — 所有输出格式使用 `success | partial | failed`，禁止使用旧的 `fail`/`error`
- **UE 风格加载生命周期** — 执行顺序必须为 `link() → preload(idx) × N → post_load()`，禁止在 export 解析前调用 post_load
- **类序列化策略** — 通过 `class_serialization_strategy.py` 注册，禁止在核心管线硬编码类名判断
- **Payload 偏移默认策略** — 默认使用 `SerialOffset/SerialSize`（与 UE LinkerLoad.cpp:4793 对齐），ScriptSerialization 偏移仅保留为诊断字段
- **Opaque 类标记** — OPAQUE_CLASS_PAYLOAD 类必须同时设置 instance 和 export 的 parse_status，禁止仅设置一方

## 测试策略约束

- **真实资产抽测优先** — 优先从样本库中随机选取真实资产进行测试验证，而非仅依赖固定样本集；确保覆盖面和泛化能力
- **大文件内存安全** — 解析大文件（≥100MB）时必须关注内存占用：禁止一次性加载全文件到内存，使用流式/分块读取；解析完成后及时释放大对象；测试中需包含大文件场景验证
- **轻量模式兜底** — export_count > 300 时自动切换轻量解析，跳过完整蓝图解析，防止内存溢出
- **双模式验证** — 稳定资产必须在 strict 和 tolerant 双模式下通过

## CodeGraph 使用

优先使用 `codegraph_*` 工具回答结构化问题（符号定义、调用链、影响范围）。详细规则见全局 CLAUDE.md。
