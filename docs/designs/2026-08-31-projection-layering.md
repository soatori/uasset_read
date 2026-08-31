# Projection 分层重构边界（G4）

status: target

> 定义 `projection.py` 的可执行重构边界：投影 → 截断 → 序列化。纯代码搬移级重构，公开行为与签名不变。

## 现状（基线 bd3309a7 核实）

`project_document`（`src/uasset_read/v2/projection.py:67-256`）一个函数混做三件事：

1. **结构转换**：`obj_to_dict`（`projection.py:276-308`）按 view 分支附加字段（`if view in ("raw","debug")`，:295-296；`_package_to_dict` 同样，:271-272）；`select_objects` 过滤（:14-32）；`fields` 白名单过滤（:119-124）。
2. **分页**：`paginate`（:35-61），语义正确。
3. **max_bytes 截断**：:209-254。问题集中在这里：
   - 每弹出一个对象就全量重序列化测量一次（`_encoded()`，:211-213，在 :232 的 while 循环内），且每轮重跑 `_scope_to_page`——后者含关系可达性 BFS（:133-144）。总体 O(弹出数 × (全量 json.dumps + 全关系扫描))。
   - 截断逻辑直接读写 `result` dict 的 5 个键（objects/relations/dependencies/payloads/diagnostics），与 envelope 构建互相依赖，无法单测"截断"本身。
   - 唯一做对的一点：**测量在编码后**（量的是真正会发出的 UTF-8 字节数），这个原则保留。

## 目标分层

同文件内拆成三个纯函数，不新增模块、不新增类：

```python
def project_document(doc, *, view, depth, ...) -> dict:
    envelope = _project_envelope(doc, view, selection, page, ...)   # 层1：结构转换，永不截断
    if max_bytes is not None:
        envelope = _enforce_budget(envelope, max_bytes, offset, total=len(selected))  # 层2：截断 pass
    return envelope                                                  # 层3：序列化在调用方
```

- **层 1 投影**：现有 :101-206 的 envelope 构建 + `obj_to_dict`/`_package_to_dict`/`_scope_to_page` 原样进 `_project_envelope`。输入 document + 选择参数，输出完整 dict。唯一职责是结构转换。
- **层 2 截断**：现有 :209-254 整体搬出为 `_enforce_budget(result, max_bytes, offset, total) -> result`。签名上只依赖已投影的 dict，不摸 `PackageDocument`——截断决策因此可脱离解析路径单测（输入手工 dict，断言 `truncation`/`next_offset`/`TRUNCATED` 诊断）。内部允许一次优化：对每个对象 dict 单独 `dumps` 缓存字节数，按累计值决定保留前缀，再对最终 envelope 验证一次；替代现在的逐弹逐测。预算过小时的 `ValueError`（:243）行为不变。
- **层 3 序列化**：CLI/Agent 层各一次 `json.dumps`。投影内部除 `_enforce_budget` 的测量外不再序列化。

`next_offset`/`truncation` 的输出格式与现行为逐字节一致（schema `docs/designs/contract/package_document_v2.schema.json:71-90` 不动）。

## 明确拒绝：字段元数据驱动视图

不做 per-field 声明（如 `field(view=...)` 元数据表、注册式字段目录、由 schema 反向驱动投影）。理由：当前全部 view 差异只有 2 个字段开关（`projection.py:295-296`、`:271-272`），`if view in (...)` 两行可读；字段元数据框架是为想象中的第 N 个视图预付抽象，违反目标设计原则 10（"只有第二个真实消费者出现时才抽共享抽象"，canonical design §Design Principles）。调用方字段选择已由 `fields` 参数覆盖（:119-124）。

**何时才值得重新考虑**：出现第 4 个 view，或 raw/debug 需要按字段增减超过约 10 处 `if view` 分支、且多消费方对同一字段集重复手写分支。到那时也是抽一个 `dict[view, set[str]]` 常量表，不是框架。

## 验收

- 现有 projection/agent/CLI 契约测试零修改通过（行为不变是本重构的验收线）。
- 新增 `_enforce_budget` 独立测试：喂 20 行手工 dict 断言 dropped 数与 `next_offset`，不经过 parse。
- O(n²) 序列化消失：`_enforce_budget` 每次调用最多 2 次全量 dumps（决策一次 + 验证一次）。
