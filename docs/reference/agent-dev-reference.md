# Agent 开发参考索引

> 本页只提供检索顺序。不得从历史设计、Issue 状态或 Wiki 文案推断功能已经实现。

## 首先读取

| 目的 | 文档 |
| --- | --- |
| 仓库级工作规则 | [`AGENTS.md`](../../AGENTS.md) |
| 最新目标架构 | [`docs/designs/2026-08-26-package-first-uasset-parser-refactor.md`](../designs/2026-08-26-package-first-uasset-parser-refactor.md) |
| 历史设计状态 | [`docs/designs/README.md`](../designs/README.md) |
| 已归档仓库级方案 | [`docs/designs/archive/README.md`](../designs/archive/README.md)，仅用于历史追溯 |
| 当前用户能力 | [`README.md`](../../README.md)，随后核对源码与测试 |
| UE 格式事实 | [`docs/formats/uasset/Index.md`](../formats/uasset/Index.md) 和 UE 源码 |
| 当前公共 API（v4） | [`src/uasset_read/__init__.py`](../../src/uasset_read/__init__.py)（`__all__`）与 `src/uasset_read/package.py`（`parse_package_document`） |

## 判断顺序

1. 用 CodeGraph 读取当前符号、调用路径和影响范围。
2. 用源码和严格测试确认当前行为。
3. 用真实样本确认二进制分支和输出完整度。
4. 用 UE 源码确认字段、版本门槛和序列化顺序。
5. 只有在规划未来工作时才使用目标设计。

## 当前与目标边界

- 三个入口（CLI 默认、Python API、Agent tool）的输出均为 PackageDocument v4（`format_version: "4.0"`，恰好 `normal`/`debug` 两种模式，单包单完整文档），唯一顶层 format 为 `uasset_read.package`；legacy Semantic 1.x JSON 与 v1 pipeline 已删除，`--legacy-json`/`--markdown`/`--diff`/`--list-formats` 作为 retired flag 直接报错退出（见 `cli.py` retired 集合与 Issue #643）。`--batch`/`--batch-format` 已随 2026-09-28 v4 输出修正退役（CLI 显式拒绝）。
- `extract_payload` 对带 sidecar（`.uexp`/`.ubulk`）的 cooked 包执行真实字节提取（BulkData header 解析 + 结构化错误）。无 sidecar 的包返回 `PAYLOAD_EXTRACTION_DEFERRED`（见 `docs/designs/2026-08-31-payload-extraction-path.md`）。
- v4 没有 view/depth 公共输出模式：`project_document(document, *, mode=...)` 是唯一信封生产者（`normal` 含全部有序属性与安全解码值；`debug` 增加证据块，剥离证据并归一 `mode` 后与 `normal` 逐字节等价）。envelope 始终包含 `relations`/`dependencies`（依赖条目携带 `package_name`，#632）。parse 深度是 `parse_package_document(depth=...)` 的解析输入，不是输出面。
- 正式测试契约为 sample-first 两文件基线：`tests/test_samples.py`（manifest 驱动的真实样本驱动：manifest 闭合、67 项样本 parse、raw version/layout、v4 normal/debug schema/parity、golden、capability、quality、容器、sidecar 与最小边界聚合检查）与 `tests/test_size_baseline.py`（体积 + 2 模块上限门禁）；全树收集项至多 100（`tests/conftest.py` 收集预算 hook）。无 `tests/contract/`、`tests/serialization/` 与其他测试模块；广泛临时调查走未跟踪 `temp/`。
- 当前 v4 使用 package-first `PackageDocument`（legacy + tagged properties + sample-backed handlers 已实现；Zen/IoStore deferred；unversioned 为 usmap 驱动的 partial 路径，未映射尾部显式 opaque，payload extraction 已实现，见 docs/designs/README.md），输出所有 objects。
- 当前 Pak/IoStore、日志和 Agent 能力不得按目标设计提前宣称完成。
- **契约稳定性：** 当前冻结契约为 `docs/designs/contract/package_document_v4.schema.json`（`format_version: "4.0"`，2026-09-28 冻结；S1 的 `"2.0"` 与 v3 的 `"3.0"` 均已淘汰）；破坏性变更才 bump major。诊断与 experimental 字段**不得**作为跨版本 golden 的稳定断言面。
- 旧领域 Semantic 文档可用于理解 v0.5.5，但不得继续扩展为新的顶层 format。

## 按任务定位

| 任务 | 入口 |
| --- | --- |
| 当前解析管线（v4 package document） | `src/uasset_read/package.py`（`parse_package_document`）, `src/uasset_read/parsers/legacy_reader.py` |
| 当前语义 handler | `src/uasset_read/parsers/asset_types/handlers_impl.py`, `src/uasset_read/parsers/asset_types/`；1.x 格式页 [`semantic-json.md`](../formats/uasset/semantic-json.md) 仅供 historical 参考 |
| Package/sidecar/provider | `src/uasset_read/package.py` |
| 版本上下文 | `src/uasset_read/versioning.py`, `src/uasset_read/serializers/package_summary.py` |
| 属性解析 | `src/uasset_read/serializers/property_tags.py`, `src/uasset_read/parsers/` |
| Blueprint/Kismet | `src/uasset_read/kismet/`（#642 永久内部化：内部实现细节，不承诺公共 API）, `src/uasset_read/serializers/graph*.py` |
| Archive / SourceInfo | `src/uasset_read/archive.py`（`FArchive`, `ByteArchive`, `SourceInfo`；Source/FileSource/SliceReader 协议族已于 2026-09-10 删除） |
| Pak / IoStore 读取 | **未实现**（deferred：Zen/IoStore #624，`.pak` #625） |
| 日志 | 无（Gate L 2026-09-10 退役：project_logging.py 已删除；库只返回 structured diagnostics） |
| 重构验收条件 | 最新目标架构的 `Acceptance Gates` |

## 工作规范

- 代码、注释和错误信息使用英文；文档保持所在文档语言一致。
- 临时调查材料放入 `temp/`。
- 二进制读取必须有边界验证和严格回归测试。
- Phase 0 将一次性替换旧测试体系；不要继续扩展 Semantic 1.x 测试，也不要新增独立验证脚本。
- 样本缺失只登记 manifest gap，不用 skip/xfail/吞异常制造覆盖；支持声明必须有真实 fixture 和 structured diagnostics 断言。
- 当前只以本机 Windows + Python 3.14 作为阻断测试环境；其他平台和 Python 版本暂缓且不得宣称已验证。
- 不提交本机 UE 源码绝对路径、外部仓库副本、日志或 Agent 缓存。
- 报告结论必须标明是 current evidence 还是 target decision。
