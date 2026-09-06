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
| 当前公共 API（v2） | [`src/uasset_read/__init__.py`](../../src/uasset_read/__init__.py)（`__all__`）与 `src/uasset_read/v2/api.py`（`parse_package_document`） |

## 判断顺序

1. 用 CodeGraph 读取当前符号、调用路径和影响范围。
2. 用源码和严格测试确认当前行为。
3. 用真实样本确认二进制分支和输出完整度。
4. 用 UE 源码确认字段、版本门槛和序列化顺序。
5. 只有在规划未来工作时才使用目标设计。

## 当前与目标边界

- 三个入口（CLI 默认、Python API、Agent tool）的输出均为 PackageDocument v2，唯一顶层 format 为 `uasset_read.package`；legacy Semantic 1.x JSON 与 v1 pipeline 已删除，`--legacy-json`/`--markdown`/`--batch`/`--diff`/`--list-formats` 作为 retired flag 直接报错退出（见 `cli.py` retired 集合与 Issue #643）。
- `extract_payload` 恒返回 `code="PAYLOAD_EXTRACTION_DEFERRED"`、`available_ids=[]`，不读文件（已生效决策，见 `docs/designs/2026-08-31-payload-extraction-path.md`）。真实提取（可提取字节、分页续读 `next_offset`）为 historical 承诺，blocked on Phase 5 containers 与 #623–#627 fixture。
- 默认 `semantic` 视图不携带 `serial_region`/`properties`（归 `raw`/`debug`）；depth >= object 时 semantic 携带紧凑的 `properties_summary`（names + 标量，容器仅保留长度，无 raw 字节，#636）。`project_document(sections=...)` 可省略 `relations`/`dependencies` 顶层节（省略时 schema 不要求该键，#631）；依赖条目携带 `package_name`（#632）。
- 正式测试契约层只有 `tests/test_core.py` 与 `tests/test_samples.py`（`tests/contract/` 已删除并收敛）。
- 当前 v2 使用 package-first `PackageDocument`（legacy + tagged properties + sample-backed handlers 已实现；Zen/IoStore、unversioned、payload extraction 仍 deferred，见 docs/designs/README.md），输出所有 objects。
- 当前 Pak/IoStore、日志和 Agent 能力不得按目标设计提前宣称完成。
- 旧领域 Semantic 文档可用于理解 v0.5.5，但不得继续扩展为新的顶层 format。

## 按任务定位

| 任务 | 入口 |
| --- | --- |
| 当前解析管线（v2 package document） | `src/uasset_read/__init__.py`（`parse_package_document`）, `src/uasset_read/v2/api.py`, `src/uasset_read/v2/document.py`, `src/uasset_read/v2/package/legacy.py` |
| 当前 v2 语义 handler | `src/uasset_read/v2/handlers.py`, `src/uasset_read/parsers/asset_types/`；1.x 格式页 [`semantic-json.md`](../formats/uasset/semantic-json.md) 仅供 historical 参考 |
| Package/sidecar/provider | `src/uasset_read/package.py` |
| 版本上下文 | `src/uasset_read/versioning.py`, `src/uasset_read/serializers/package_summary.py` |
| 属性解析 | `src/uasset_read/serializers/property_tags.py`, `src/uasset_read/parsers/` |
| Blueprint/Kismet | `src/uasset_read/kismet/`（#642 永久内部化：v2 实现细节，不承诺公共 API）, `src/uasset_read/v2/blueprint_graph.py`, `src/uasset_read/serializers/graph*.py` |
| Pak / IoStore 读取 | **未实现**（deferred：Zen/IoStore #624，`.pak` #625）。`src/uasset_read/v2/source.py:25` 仅预留 `kind` 取值字面量，无读取代码 |
| 日志 | `src/uasset_read/project_logging.py` |
| 重构验收条件 | 最新目标架构的 `Acceptance Gates` |

## 工作规范

- 代码、注释和错误信息使用英文；文档保持所在文档语言一致。
- 临时调查材料放入 `temp/`。
- 二进制读取必须有边界验证和严格回归测试。
- Phase 0 将一次性替换旧测试体系；不要继续扩展 Semantic 1.x 测试，也不要新增独立验证脚本。仓库根目录 `tests/test_*_contract.py` 是唯一的严格契约层，不得重新添加 `tests/v2/` 重复套件。
- 样本缺失只登记 manifest gap，不用 skip/xfail/吞异常制造覆盖；支持声明必须有真实 fixture 和 structured diagnostics 断言。
- 当前只以本机 Windows + Python 3.14 作为阻断测试环境；其他平台和 Python 版本暂缓且不得宣称已验证。
- 不提交本机 UE 源码绝对路径、外部仓库副本、日志或 Agent 缓存。
- 报告结论必须标明是 current evidence 还是 target decision。
