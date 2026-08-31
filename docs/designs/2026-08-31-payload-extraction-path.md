# Payload 提取路径（S2）

status: target

> 本文写于撤回决策**刚生效**之时：以基线 bd3309a7 的现状为对照，定义撤回后的稳定形态与未来两条优化路线。非本轮实现。

## 现状：fabricated 提取正在撤回为 `PAYLOAD_EXTRACTION_DEFERRED`

基线里存在的"main-region 提取"实为**伪造区间**：`LegacyPackageReader.read()` 在 `depth == "decode"` 时，把每个对象"属性流结束偏移 → `serial_region` 末尾"的剩余字节包成 `status="available"` 的 `PayloadDescriptor`（`src/uasset_read/v2/package/legacy.py:474-497`），`payloads.py:30-91` 再按此 descriptor 直接 `open()+seek()` 读文件返回 base64。该区间没有任何 UE 源码 trailer/FBulkData 证据，违反"Binary layout 决策必须溯源 UE 源码"与"不 fabricate"门禁。

**已生效决策**（另一工作区执行撤回）：

- `extract_payload`（`agent_tools.py:180-224`）对任意 `payload_id` 恒返回结构化错误 `PAYLOAD_EXTRACTION_DEFERRED`；工具签名与错误 envelope 形状不变。
- decode 深度不再产出 fabricated descriptor；`payloads[]` 在无可靠 descriptor 前为空数组（信封键保留，schema required 不动）。
- 真实 descriptor / extraction 等待**可再分发 sidecar/container fixture**（#623–#627）到位后按 UE 源码偏移证据重做；在此之前任何"提取成功"都必须是 fake，故宁可全部 DEFERRED。

## 未来路线：两条，先 B 后 A

### 路线 B：decode cache 复用（跟随 G2 缓存落地）

`extract_payload` 内部已是 `parse_package_document(file_path, depth="decode", object_ids=[owner])`（`agent_tools.py:197-199`）。[G2 缓存契约](2026-08-31-agent-doc-cache-contract.md)落地后，同一文件多次 extract（多 payload、分页续读 `next_offset`）天然命中缓存，**零解析器新代码**。注意 key 含 `depth`/`object_ids`，所以它只消除重复 extract，不加速首次 decode parse。

### 路线 A：payload-only 解析（只读目标 export serial region + trailer 映射）

reader 新增模式：读 summary/tables 定位目标 export 的 `serial_region`，跳过非目标对象的属性解析与 handler，再按 trailer/`FBulkData` 头映射出 descriptor 区间。

**A 与 B 比较：**

| | B cache 复用 | A payload-only |
|---|---|---|
| 新代码量 | ≈0（依赖 G2） | reader 新模式 + 区间映射，且需 UE 源码证据链 |
| 消除的成本 | 重复 parse | 首次 parse 的无关对象成本 |
| 正确性风险 | 无新增 | descriptor 偏移必须溯源，做不干净就是二次 fabricate |
| 前置 | G2 实现 | **#623–#627 fixture + trailer 证据** |

**决策**：B 先行，作为 G2 的免费收益；A **只与真实 descriptor 同期实现**——因为 A 的核心工作（trailer→区间映射）本来就与 #623–#627 落地时的 descriptor 重做是同一件事，提前单独做 A 只是给一个即将被替换的假 descriptor 铺性能。触发条件（确定性、非墙钟）：真实 fixture 中首次 decode parse 遍历了目标 payload 所属对象之外的多数 export 属性，即值得做 A。

## 外部区域（ubulk/uptnl/ucas）接口前置条件

- **来源抽象已就位**：`Source.read_at()` 协议（`src/uasset_read/v2/source.py:14-20`）；schema `source_region` 枚举已含 `ubulk/uptnl/ucas`（`package_document_v2.schema.json:289-292`）；`payloads.py:51-59` 已对非 `main` 区域返回 not-extractable 错误而非假数据。
- **#627 前置**（缺一不可）：
  1. 可再分发的 sidecar/container fixture 进入 `tests/samples/` 并登记 manifest（SHA-256/size/sidecar 校验）；
  2. `CompositePackageSource` 按 region 分发 `read_at`（canonical design §Source），descriptor 的 `source_region` 路由到对应子 source，禁止整容器进内存；
  3. descriptor 字段（`offset/stored_size/logical_size/compression`）逐项有 UE 源码 `FBulkData`/trailer 写路径证据，`status` 用 `external`/`missing` 如实分层；
  4. 缺失 sidecar 文件 → 对象级 diagnostic + `status="missing"`，不静默降级为 `main`。

Zen/IoStore 容器读取本身是 Phase 5 目标，不在 payload 路径上阻塞本决策：#627 落地前 ubulk sidecar（loose 包）即可先走条件 2 的最小子集。

## 本轮不做清单

不改 `payloads.py`/`agent_tools.py`（撤回由另一工作区执行）；不预建 payload-only reader 骨架；不给无 fixture 的能力写 skip 测试——缺口记入 manifest 与 #623–#627。
