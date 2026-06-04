# 开发指南

## 测试

### 测试运行命令

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行所有测试 + 覆盖率
python -m pytest tests/ -v --cov=uasset_read

# 仅运行集成测试
python -m pytest tests/ -v -m integration

# 运行真实资产集成测试
python -m pytest tests/test_sample_assets_representative.py -v -m integration

# 运行单个测试文件
python -m pytest tests/test_pak_handling.py -v
```

### 测试要求

| 要求 | 说明 |
|------|------|
| **最小测试数** | ≥ 800 个单元测试 |
| **通过率** | 100%（不包括预期的 xfail） |
| **集成测试** | ≥ 40 个用例，使用 `@pytest.mark.integration` 标记 |
| **资产覆盖** | 至少 12 种资产类型（Blueprint、SkeletalMesh、Material、MaterialInstance、StaticMesh、Texture2D、Niagara、Map、InputAction、InputMappingContext、AnimBlueprint、ParticleSystem） |
| **双模式** | 稳定资产必须在 strict 和 tolerant 两种模式下都通过 |

> **当前状态** (v0.4.2): 994 passed, 2 xfail, 51 测试文件, 40+ 集成测试

### 样本资产

测试依赖 `E:\Develop\lib\UnrealEngine\Samples` 目录的真实 UE 资产：

```
E:\Develop\lib\UnrealEngine\Samples\
├── FirstPerson\        # UE First Person 模板
├── ThirtPerson\        # UE Third Person 模板
├── StarterContent\     # UE Starter Content
└── Games\LyraStarterGame\  # UE Lyra 示例游戏
```

在 `tests/test_sample_assets_representative.py` 中配置：
- `STABLE_ASSETS` — 已知可正常解析的资产
- `DIAGNOSTIC_ASSETS` — 用于诊断的资产
- `PARSER_ASSETS` — 用于测试特定资产类型解析器的资产

### 集成测试验证要求

**每个解析成功的资产必须验证**:
1. `result.is_success` 为 `True`
2. `result.summary`、`result.linker`、`result.name_map`、`result.export_map` 不为空

**蓝图资产额外验证**:
1. `result.blueprint` 不为空，`len(result.blueprint.variables) >= 1`
2. 至少一个变量有 GUID（`any(variable.var_guid for ...)`）
3. `len(result.graphs) >= 1`，至少一个 Graph 有 `graph_guid`
4. 至少一个节点有 Pin，至少一个 Pin 有 `persistent_guid`
5. 至少一个 Pin 有连接关系（`linked_to_raw` 非空）
6. 至少一个变量有默认值

### 已知缺陷资产

| 资产 | 缺陷 | 标记 |
|------|------|------|
| `P_Fire.uasset` (ParticleSystem) | UE4 legacy_file_version=-3，当前仅支持 {-9, -8} | `xfail` |

### 提交前检查

- [ ] 所有单元测试通过（`python -m pytest tests/ -v`）
- [ ] 所有集成测试通过（`python -m pytest tests/ -v -m integration`）
- [ ] 无新的测试失败（xfail 除外）
- [ ] 新增功能有对应的测试用例
- [ ] Bug 修复有回归测试

### 版本发布前测试

发布新版本前，除常规测试外还需：
1. **真实资产随机测试** — 从 LyraStarterGame 随机抽取 ≥ 50 个资产验证
2. **多类型蓝图验证** — 手动验证 ≥ 3 种不同类型蓝图的完整输出
3. **事件函数执行追踪** — 验证至少 2 个蓝图的事件→函数调用链可正确追踪
4. **版本号一致性** — 确认 `__init__.py`、文档版本号统一
5. **文档同步** — 确认 CLAUDE.md、README.md、Wiki 文档与代码一致

详细测试规范见 `docs/guides/testing-requirements.md`。

## 开发命令

### 直接调用

```bash
python run.py path/to/file.uasset --text
python run.py path/to/file.uasset --cpp-skeleton
```

或通过模块：

```bash
python -m uasset_read path/to/file.uasset --text
```

### 测试

```bash
python -m pytest tests/ -v                  # 所有测试
python -m pytest tests/ -v --cov=uasset_read # + 覆盖率
python -m pytest tests/test_pak_handling.py -v  # 单个文件
python -m pytest tests/ -v -m integration   # 仅集成测试
```

### CLI 入口

```bash
python run.py path/to/file.uasset              # JSON 输出（默认）
python run.py path/to/file.uasset --output out.json   # 保存到文件
python run.py path/to/file.uasset --summary      # 仅摘要
python run.py path/to/file.uasset --text       # 人类可读文本
python run.py path/to/file.uasset --markdown   # Markdown + Mermaid 图表
python run.py path/to/file.uasset --blueprint-text   # 蓝图节点文本
python run.py path/to/file.uasset --blueprint-ue-text  # UE 格式文本
python run.py path/to/file.uasset --cpp-skeleton       # C++ 类骨架
python run.py --batch-dir path/to/dir/           # 批量导出目录
python run.py path/to/file.uasset --strict     # 遇到警告时停止
python run.py path/to/file.uasset --tolerant   # 容错模式（默认）
python run.py path/to/file.uasset --verbose    # 启用调试日志
```

## 架构

解析器镜像 UE 内部的 `FArchive` 序列化管线：

```
.uasset → FArchive → Deserializer → Models → Formatters → Output
                ↓
          GraphParser · BlueprintParser · DependencyGraphBuilder
          PackageLinker · KismetDecompiler · PakFileReader
          IR Builder → Renderers (JSON/Text/Markdown/BlueprintText/BlueprintUE/CppSkeleton)
```

### 模块结构 (`src/uasset_read/`)

> 代码位置查询优先使用 `codegraph_files` 或 `codegraph_search`，下表仅供参考。

| 模块 | 路径 | 职责 |
|------|------|------|
| **核心** | | |
| FArchive | `archive.py` | 二进制读取器，支持字节交换、mmap |
| 常量 | `constants.py` | 版本号、属性类型阈值、CPF/PropertyTag 标志 |
| 异常 | `exceptions.py` | `UAssetError`、`VersionError`、`ParseError`、`ErrorContext` |
| 主解析器 | `parse_uasset.py` | `parse_package()`、`parse_uasset()` 和 `parse_uasset_with_linker()` 入口 |
| 包管理 | `package.py` | `PackageBundle`、`PackageProvider`（文件系统/Pak/IoStore） |
| 原始文件 | `raw.py` | JSON/INI/LocRes/LocMeta/Audio 等非 uasset 文件解析 |
| CLI | `cli.py` | argparse 入口，委托 `core.py` API |
| 版本管理 | `versioning.py` | `VersionContainer`、`build_version_container`、`EUEVersion` |
| 映射 | `mappings.py` | UE 类型映射（`.usmap`/`.jmap` 解析） |
| **序列化** | `serializers/` | `PackageFileSummary`、`ImportMap`、`ExportMap`、`PropertyTag`、图序列化器、对象资源 |
| **数据模型** | `models/` | `UEdGraph/Node/Pin`、属性值模型、`ParseResult`、变换、蓝图模型、节点类型、IR 中间表示 |
| **属性解析器** | `parsers/` | 40+ 种属性类型解析器 + 分发器 + 自定义属性注册表 + 类特定跳过机制 |
| ├ 资产类型 | `parsers/asset_types/` | SkeletalMesh、Texture2D、Material、MaterialInstanceConstant 专用解析器 |
| **蓝图** | `blueprint/` | 变量/变换/组件/元数据提取 |
| **图分析** | `graph/` | 执行流/数据流追踪、链构建器、Pin 追踪报告、子 Pin 恢复 (`_try_recover_to_subpins`) |
| **Kismet** | `kismet/` | 字节码提取器、`EExprToken` → AST → C++ 翻译器、BPGC 回退、结构化控制流 |
| ├ 表达式 | `kismet/expressions/` | 16 种表达式类型（赋值、控制流、函数调用、字面量等） |
| **链接器** | `link/` | `PackageLinker` 两阶段对象图重建、`UObjectInstance` |
| **C++ 生成** | `cpp_gen/` | C++ 骨架/函数提取、IR 格式化器、类型映射、UPROPERTY 映射、构造函数 IR 构建器 |
| **Pak** | `pak/` | `FPakInfo/PakEntry/FPakDirectoryEntry`、`PakFileReader`、索引解析、压缩分发、AES 解密 |
| **IoStore** | `iostore/` | IoStore 容器读取器、Chunk ID、偏移/大小结构 |
| **Bulk Data** | `bulk/` | BulkData 头部解析、标志定义 |
| **UObject** | `objects/` | UObject 类型体系、类型注册表、导出类型（StaticMesh/SkeletalMesh/Texture2D/Material） |
| **IR** | `ir_builder.py`、`models/ir.py` | 包级中间表示构建器、`PackageIR`、`ExportIR`、`PropertyIR` |
| **Renderer** | `renderers/` | 可插拔 `IRenderer` ABC + format registry（JSON/Text/Markdown/BlueprintText/BlueprintUE/CppSkeleton，6 种渲染器） |
| **格式化器** | `formatters/` | JSON/Text/Markdown(with Mermaid)/蓝图翻译文本/UE 格式文本输出生成器 |
| **Core API** | `core.py` | `parse_single()`、`parse_batch()`、`list_formats()` — 简化高层 API |
| **Simple API** | `simple.py` | 更简化的单文件解析入口 |

### 公共 API

所有公共符号在 `src/uasset_read/__init__.py` 中通过 `__all__` 导出。以该文件为权威 API 参考。
合并或重构后务必运行 `python -m pytest tests/test_api_cleanup.py -v` 验证导出完整性。

## 外部参考

- `docs/formats/uasset/` — UE .uasset 格式文档（60+ 个 Markdown 文件，覆盖资产类型、序列化、Cooked 格式、版本兼容）。`Index.md` 为主索引。
- `external/CUE4Parse/` — 参考 C# 实现，用于交叉验证解析逻辑。
- `docs/reference/` — 蓝图节点文本参考、UE 加载流程、CUE4Parse 对照索引、蓝图转 C++ 指南。
