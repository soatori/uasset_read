# 测试要求规范

> 本文档定义 uasset_read 项目的测试要求，所有提交必须满足这些要求。

---

## 一、测试结构

```
tests/
├── test_pak_handling.py          # PAK 文件解析测试（集成测试）
├── test_variable_extractor.py    # 变量提取器测试
├── test_sample_assets_representative.py  # 真实资产测试（集成测试）
├── test_tolerant_class_specific.py       # 容错模式类特定跳过测试
├── test_binary_or_native_handlers.py     # 二进制/原生值处理器测试
├── test_pak_structures.py                # PAK 结构体测试
├── test_struct_lwc.py                    # 结构体 LWC 测试
├── test_api_cleanup.py                   # API 清理测试
├── test_flow_builder_deprecation.py      # 流程构建器废弃测试
├── test_package_bundle.py                # 包捆绑测试
├── test_package_summary_fields.py        # 包摘要字段测试
├── test_raw_readers.py                   # 原始文件读取器测试
└── test_cue4parse_gap_completion.py      # CUE4Parse 差异补充测试
```

---

## 二、测试要求

### 2.1 基础要求

| 要求 | 说明 |
|------|------|
| **最小测试数** | ≥ 200 个单元测试 |
| **通过率** | 100%（不包括预期的 xfail） |
| **Python 版本** | 3.10+ |
| **测试框架** | pytest |
| **运行命令** | `python -m pytest tests/ -v` |

### 2.2 集成测试要求

| 要求 | 说明 |
|------|------|
| **标记** | 使用 `@pytest.mark.integration` |
| **样本资产** | 依赖 `E:\Develop\lib\UnrealEngine\Samples` 目录 |
| **最小数量** | ≥ 40 个集成测试用例 |
| **覆盖资产** | 至少覆盖 10 种资产类型 |

### 2.3 真实资产测试要求

**必须覆盖的资产类型**:

| 资产类型 | 最小测试数 | 验证内容 |
|----------|-----------|----------|
| Blueprint | 2 | 变量、Graphs、节点、Pins、GUID |
| SkeletalMesh | 1 | 导出解析、元数据字段 |
| Material | 1 | 导出解析、材质属性 |
| MaterialInstance | 1 | 父材质索引、参数覆盖 |
| StaticMesh | 1 | LOD 数、Section 数 |
| Texture2D | 1 | 导入尺寸、cooked 标志 |
| Niagara | 1 | 基础解析不崩溃 |
| Map | 1 | 基础解析不崩溃 |
| InputAction | 1 | 基础解析不崩溃 |
| InputMappingContext | 1 | 基础解析不崩溃 |
| AnimBlueprint | 1 | 变量、Graphs、GUID |
| ParticleSystem | 0 (xfail) | 已知 UE4 版本缺陷 |

### 2.4 测试模式要求

| 模式 | 说明 |
|------|------|
| **Strict 模式** | `tolerant=False`，遇到错误应抛出异常 |
| **Tolerant 模式** | `tolerant=True`，容错继续解析 |
| **双重测试** | 稳定资产必须在两种模式下都通过 |

### 2.5 验证内容要求

**每个解析成功的资产必须验证**:

1. `result.is_success` 为 `True`
2. `result.summary` 不为空
3. `result.linker` 不为空
4. `result.name_map` 不为空
5. `result.export_map` 不为空

**蓝图资产额外验证**:

1. `result.blueprint` 不为空
2. `len(result.blueprint.variables) >= 1`
3. `any(variable.var_guid for variable in result.blueprint.variables)` — 至少一个变量有 GUID
4. `len(result.graphs) >= 1`
5. `event_graph.graph_guid` 不为空
6. `len(event_graph.nodes) >= 1`
7. `sum(len(node.pins) for node in event_graph.nodes) >= 1`
8. 至少一个 Pin 有 `persistent_guid`
9. 至少一个 Pin 有连接关系（`linked_to_raw` 非空）
10. 至少一个变量有默认值

**资产类型解析器验证**:

1. 导出解析返回 `dict` 类型
2. 返回的 dict 不为空
3. 包含预期的元数据字段（如 `imported_size_x`、`parent_material_index`、`lod_count` 等）

---

## 三、运行命令

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行所有测试 + 覆盖率
python -m pytest tests/ -v --cov=uasset_read

# 仅运行集成测试
python -m pytest tests/ -v -m integration

# 运行单个测试文件
python -m pytest tests/test_sample_assets_representative.py -v

# 运行真实资产集成测试
python -m pytest tests/test_sample_assets_representative.py -v -m integration
```

---

## 四、提交前检查

提交代码前必须确认：

- [ ] 所有单元测试通过（`python -m pytest tests/ -v`）
- [ ] 所有集成测试通过（`python -m pytest tests/ -v -m integration`）
- [ ] 无新的测试失败（xfail 除外）
- [ ] 新增功能有对应的测试用例
- [ ] Bug 修复有回归测试

---

## 五、测试数据

### 5.1 样本资产位置

```
E:\Develop\lib\UnrealEngine\Samples\
├── FirstPerson\        # UE First Person 模板
├── ThirtPerson\        # UE Third Person 模板（注意拼写）
├── StarterContent\     # UE Starter Content
└── Games\LyraStarterGame\  # UE Lyra 示例游戏
```

### 5.2 测试资产配置

在 `tests/test_sample_assets_representative.py` 中配置：

- `STABLE_ASSETS` — 已知可正常解析的资产
- `DIAGNOSTIC_ASSETS` — 用于诊断的资产（可能有不完整功能）
- `PARSER_ASSETS` — 用于测试特定资产类型解析器的资产

### 5.3 已知缺陷资产

| 资产 | 缺陷 | 标记 |
|------|------|------|
| `P_Fire.uasset` (ParticleSystem) | UE4 legacy_file_version=-3，当前仅支持 {-9, -8} | `xfail` |

---

## 六、版本发布测试要求

发布新版本前，除常规测试外还需：

1. **真实资产随机测试** — 从 LyraStarterGame 随机抽取 ≥ 50 个资产验证
2. **多类型蓝图验证** — 手动验证 ≥ 3 种不同类型蓝图的完整输出
3. **事件函数执行追踪** — 验证至少 2 个蓝图的事件→函数调用链可正确追踪
4. **版本号一致性** — 确认 `__init__.py`、文档版本号统一
5. **文档同步** — 确认 CLAUDE.md、README.md、Wiki 文档与代码一致
