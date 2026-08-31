# Agent 工具 PackageDocument 缓存契约（G2）

status: target

> 本轮不实现。定义 `agent_tools` 六个工具共享 `PackageDocument` 的缓存契约；实现落地时对外签名不得变化。

## 现状（基线 bd3309a7 核实）

六个工具各自独立全量重 parse，每个工具函数都直接调用 `parse_package_document`：

| Tool | 调用点 |
|---|---|
| `inspect_package` | `src/uasset_read/v2/agent_tools.py:41` |
| `list_objects` | `src/uasset_read/v2/agent_tools.py:60` |
| `get_object` | `src/uasset_read/v2/agent_tools.py:88` |
| `list_dependencies` | `src/uasset_read/v2/agent_tools.py:119` |
| `get_diagnostics` | `src/uasset_read/v2/agent_tools.py:152` |
| `extract_payload` | `src/uasset_read/v2/agent_tools.py:199`（`depth="decode"` + 单对象 `object_ids`） |

`parse_package_document`（`src/uasset_read/v2/api.py:16-36`）无任何缓存，每次构造新 `FileSource` 并完整走 `LegacyPackageReader.read()`。Agent 一次典型对话（inspect → list → get → diagnostics）对同一文件重复 parse 四次。

## 契约

### 缓存层级

缓存挂在 `api.py` 的 parse 层，不挂在工具层。工具的 `view/offset/limit/max_bytes` 是投影参数、不影响 parse 结果，不应进入 key；只有 parse 参数才属于 key。

### Key

```python
(str(resolved_path), stat.st_mtime_ns, stat.st_size,
 depth, ids_key, tolerant, mappings_path, game)
# ids_key = None 或 tuple(sorted(object_ids))
```

取舍：

- **`st_mtime_ns` + `st_size` 进 key**：文件一改，key 自然变化，旧条目自动失效，无需显式失效通道。用 ns 精度避免秒级 mtime 漏检。
- **`depth` 与 `object_ids` 进 key**：二者改变 parse 结果（`api.py:22-23`），不缓存会直接返回错文档。`object_ids` 排序归一化，`[a,b]` 与 `[b,a]` 同 key。
- **不做包含性命中**：`object_ids=None` 的缓存不服务 `[x]` 查询，`depth="decode"` 不服务 `"asset"`。子集推断要多写失效/拷贝逻辑，命中率收益未证实，拒绝。
- **不含 `max_bytes`/`offset`/`limit`**：投影参数，见上。

### 实现形态

stdlib `functools.lru_cache(maxsize=8)` 包住一个只收 hashable 参数的内部 `_parse_cached(...)`；公开函数 `parse_package_document` 先 `Path.resolve()` + `stat()` 再转调。不写自定义 cache 类，不做 TTL，不做文件监听——mtime 在 key 里，过期即 miss。

```python
# ponytail: lru_cache 限条数不限字节；若单个大 PackageDocument 常驻成为问题，
# 等真实内存证据后再换 max_size 型 LRU。
```

### 生命周期与共享语义

- 进程级、单进程内有效；MCP server 常驻即跨调用复用，CLI 单次调用无收益（也不受害）。
- 命中返回**同一个 `PackageDocument` 对象**。契约：调用方视其为只读。projection 已承诺不 mutate（`src/uasset_read/v2/projection.py:3`），六个工具仅读取；deep-copy 防御会把缓存收益原样退回去，不做。若未来出现 mutate-doc 消费者，那个消费者自己 copy。

### 失效

只靠 stat 进 key（上节）。明确不做的：TTL、mtime 轮询、inotify。

## API 是否变化

不变。`parse_package_document` 与六个工具签名保持原样；缓存是实现细节。唯一新增语义是文档级的“返回对象只读共享”约定。

## 验收（实现时）

- 同 key 两次调用返回 `is` 同一对象；touch 文件后返回不同对象。
- 六工具行为测试不改断言即通过（签名未变）。
