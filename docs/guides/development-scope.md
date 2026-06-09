# 开发范围及限制

**版本**: 0.4.5-dev  
**最后更新**: 2026-06-09  
**维护者**: uasset_read Contributors

## 项目定位

**uasset_read** 是一个专为 AI 代理设计的虚幻引擎 `.uasset` 文件 Python 解析器，使 AI 代理无需 UE 编辑器即可读取和理解蓝图内容。

### 核心目标
- 提供对未烘焙/编辑器保存的 `.uasset` 文件的完整读取能力
- 使 AI 代理能够理解蓝图逻辑、变量、函数调用关系
- 输出结构化数据（JSON/Text/Markdown/C++ 骨架等格式）
- 保持零运行时依赖的轻量级设计
- **UE 保真度**：解析行为尽可能接近 UE FLinkerLoad 生命周期

---

## 开发范围

### ✅ 包含的功能（IN SCOPE）

#### 1. 核心解析能力
- `.uasset` 二进制格式解析（FArchive 序列化管线镜像）
- UE4/UE5 多个版本的兼容支持（legacy_file_version -9, -8）
- 包链接器（PackageLinker）对象图重建
- 名称表、导入表、导出表解析
- PropertyTag 及 40+ 种属性类型解析
- **UE 风格加载生命周期**：`link() → preload(idx) × N → post_load()`
- **类序列化策略表**：4 种策略拦截不支持的类（FULL_SERIALIZER / TAGGED_PROPERTIES_ONLY / OPAQUE_CLASS_PAYLOAD / SKIP_UNSUPPORTED）

#### 2. 蓝图解析
- 蓝图变量提取（类型、标志、默认值、GUID）
- 蓝图函数/事件提取
- 组件提取及变换数据解析
- 蓝图元数据提取
- 图节点（UEdGraph/Node/Pin）完整解析
- 执行流和数据流追踪
- Kismet 字节码反编译（16 种表达式类型）
- 事件→函数调用链追踪

#### 3. 资产类型支持

| 级别 | 含义 | 测试要求 |
|------|------|----------|
| **L4** | 完整解析（结构+属性+图+逻辑） | 集成+单元 |
| **L3** | 结构解析（结构+属性+BulkData 头部） | 集成 |
| **L2** | 基础元数据（名称表+导入导出+属性标签） | 单元 |
| **L1** | 仅 PackageFileSummary | — |
| **L0** | 不支持 / xfail | xfail |

**支持矩阵**：

| 资产类型 | 级别 | 序列化策略 | 说明 |
|----------|------|-----------|------|
| Blueprint / BPGC | L4 | TAGGED_PROPERTIES_ONLY | 变量、图、Kismet、调用链 |
| AnimBlueprint | L4 | TAGGED_PROPERTIES_ONLY | 动画节点+事件图 |
| LevelScriptBlueprint | L3 | TAGGED_PROPERTIES_ONLY | Actor 脚本逻辑 |
| MacroLibrary | L3 | TAGGED_PROPERTIES_ONLY | 宏节点解析 |
| WidgetBlueprint | L2 | TAGGED_PROPERTIES_ONLY | 基础元数据 |
| SkeletalMesh | L3 | OPAQUE_CLASS_PAYLOAD | 骨骼、LOD、顶点、材质槽 |
| StaticMesh | L3 | OPAQUE_CLASS_PAYLOAD | LOD、碰撞、顶点、材质槽 |
| Material | L3 | OPAQUE_CLASS_PAYLOAD | 属性+表达式 |
| MaterialInstanceConstant | L3 | OPAQUE_CLASS_PAYLOAD | 父材质+参数覆盖 |
| Texture2D | L3 | OPAQUE_CLASS_PAYLOAD | 属性+BulkData 头部 |
| AnimSequence / AnimMontage | L2 | OPAQUE_CLASS_PAYLOAD | 基础元数据，压缩数据不解压 |
| NiagaraSystem / NiagaraEmitter | L3 | OPAQUE_CLASS_PAYLOAD | 粒子结构 |
| ParticleSystem (UE4) | L3 | OPAQUE_CLASS_PAYLOAD | legacy -8/-9 |
| SoundWave / SoundCue | L2 | OPAQUE_CLASS_PAYLOAD | 基础属性，音频数据不解析 |
| Map/Level | L3 | TAGGED_PROPERTIES_ONLY | Actor 层次+World Partition |
| DataTable / CurveTable / StringTable | L2 | TAGGED_PROPERTIES_ONLY | 基础数据 |
| InputAction / InputMappingContext | L3 | TAGGED_PROPERTIES_ONLY | 输入配置 |
| 其他 UObject 子类 | L2 | TAGGED_PROPERTIES_ONLY | 通用解析器 |

**约束**：
1. L2 → L3 → L4 渐进，不可跳级
2. L3+ 必须有 `parsers/asset_types/` 专用解析器 + 集成测试
3. 降级必须记录警告，L0 必须 xfail
4. OPAQUE_CLASS_PAYLOAD 类标记为 opaque，表示有元数据但无完整 Serialize() 实现

#### 4. 输出格式
- JSON（完整/摘要）
- 人类可读文本
- Markdown + Mermaid 图表
- 蓝图翻译参考文本
- UE 格式文本
- C++ 类骨架生成
- 批量导出支持

#### 5. 容器支持
- 文件系统直接读取
- .pak 文件读取（AES 解密、LZ4/Zstd 解压）
- IoStore 容器读取
- 原始文件解析（JSON/INI/LocRes/LocMeta/Audio）

#### 6. 高级功能
- 类型映射支持（.usmap/.jmap）
- C++ 代码生成（骨架、函数体、组件初始化）
- CLI 工具（`python run.py`）
- 容错/严格双模式解析
- **统一状态模型**：`success | partial | failed`（跨所有输出格式一致）
- **SoftObjectPath 索引化解析**：UE5.7+ 索引模式
- **DependsMap FPackageIndex 语义**：正确解析导入/导出依赖

---

### ❌ 不包含的功能（OUT OF SCOPE）

#### 1. 写入/修改能力
- **不支持** 修改 `.uasset` 文件内容
- **不支持** 创建新的 `.uasset` 文件
- **不支持** 写入/保存任何更改到原始文件
- 本项目是**纯只读**解析器

#### 2. Cooked 资产支持
- **不支持** 解析已烘焙（Cooked）的资产
- Cooked 资产的图数据已被 UE 烘焙过程剥离
- 仅支持未烘焙/编辑器保存的资产

#### 3. 完整反编译
- **不提供** 100% 准确的蓝图→源代码反编译
- Kismet 字节码反编译存在局限性
- 复杂表达式可能无法完全还原
- 输出的是 C++ 骨架/参考，非可编译代码

#### 4. 运行时功能
- **不提供** UE 运行时模拟
- **不提供** 蓝图执行/模拟能力
- **不提供** 资产渲染/可视化

#### 5. 格式转换
- **不支持** `.uasset` ↔ 其他格式的双向转换
- 不支持从输出格式还原为 `.uasset`

#### 6. 类专属完整序列化
- **不实现** StaticMesh、Texture2D 等类的完整 `Serialize()` 方法
- 这些类标记为 `OPAQUE_CLASS_PAYLOAD`，仅解析 tagged properties
- 完整序列化需要大量 UE 内部知识，超出当前范围

---

## 技术限制

### Python 版本
- **最低要求**: Python 3.10
- 使用 Python 3.10+ 特性（match/case、类型注解）
- 不支持 Python 3.9 及以下版本

### 依赖限制
- **运行时零依赖**: `dependencies = []`
- PAK 相关功能为可选依赖（`optional-dependencies.pak`）
- 不得向主 `dependencies` 添加任何第三方包

### 版本兼容
| UE 版本 | 支持程度 |
|---------|----------|
| UE 4.x | 部分支持（legacy_file_version -9, -8） |
| UE 5.0+ | 完整支持 |
| UE 5.1+ | PropertyTag 扩展支持 |
| UE 5.2+ | 大型世界坐标支持 |
| UE 5.7+ | SoftObjectPath 索引化解析 |

### 已知限制
1. **P_Fire.uasset** (ParticleSystem): UE4 legacy_file_version=-3，当前仅支持 {-9, -8}
2. **Cooked 资产**: 图数据已被剥离，无法解析蓝图逻辑
3. **自定义属性**: 需要通过 `CUSTOM_PROPERTY_HANDLERS` 注册表手动扩展
4. **大文件**: 使用 mmap 阈值（`MMAP_THRESHOLD`）限制内存使用
5. **Opaque 类**: StaticMesh、Texture2D 等类标记为 opaque，无完整 Serialize() 实现
6. **SoftObjectPath 索引越界**: 超出范围返回空值并记录诊断，不抛异常
7. **DependsMap 循环依赖**: 当前不检测循环依赖（不影响解析正确性）

### 性能边界
- 单文件解析时间取决于资产复杂度
- 批量导出建议使用 `BatchExporter`
- 大文件（>100MB）建议使用 `--summary` 模式

---

## 错误处理模型

### 状态模型（v0.4.5 统一）

| 状态 | 含义 | 触发条件 |
|------|------|----------|
| **success** | 无错误，所有 export 解析成功 | 默认状态 |
| **partial** | 部分错误或某些 export 为 opaque/skipped | E1/E2 错误或 opaque 类 |
| **failed** | 严重错误，无可用数据 | E3/E4 错误 |

### 错误分级

| 级别 | tolerant | strict | 示例 |
|------|----------|--------|------|
| **E0** Info | 记录继续 | 记录继续 | 版本提示、可选数据缺失 |
| **E1** Warning | 记录继续 | 记录继续 | 未知属性类型 |
| **E2** Recoverable | 尝试恢复 | **停止** | PropertyTag 偏移异常 |
| **E3** Fatal | 返回部分结果 | 停止 | 文件头损坏、版本不支持 |
| **E4** Panic | 返回空结果 | 停止 | 内存越界、安全网触发 |

### CLI 退出码
- E0/E1 → 0
- E2 (tolerant) → 1
- E3+ → 2

---

## 代码统一性约束

| 原则 | 规则 |
|------|------|
| 单一错误入口 | 统一 `raise_error()`/`log_warn()`，禁止裸 `print()`/`logging.warning()` |
| 常量集中 | E0-E4 定义在 `constants.py`，禁止复制数值 |
| 恢复逻辑抽取 | 相同恢复逻辑抽取为函数，禁止复制粘贴 |
| ErrorContext 工厂化 | 通过 `make_error_context()` 构造 |

### 防重复架构

| 机制 | 状态 | 规则 |
|------|------|------|
| 属性解析器注册表 | 已存在 | 禁止 `if/elif` 链，通过 `CUSTOM_PROPERTY_HANDLERS` 注册 |
| 节点类型读取器 | 已存在 | 禁止 `read_ue_graph_node()` 中硬编码 if |
| 资产类型解析器 | 已存在 | 通过类名自动路由，禁止核心管线硬编码 |
| 版本常量 | 已存在 | 仅在 `constants.py` 定义，其他模块 import |
| 格式化器接口 | 统一 | `def format_xxx(data, options) -> str` |
| 类序列化策略 | 已存在 | 通过 `class_serialization_strategy.py` 注册，禁止硬编码 |

---

## 未知和自定义类型处理

### 未知资产回退链

```
Step1 类名匹配 → Step2 父类回退(XXXBlueprint→Blueprint) → Step3 通用UObject(L2) → Step4 仅摘要(L1)
```

### 未知属性处理

| 场景 | 行为 |
|------|------|
| 在已知类型表中 | 使用对应解析器 |
| ≤ 阈值(旧版UE4) | 序号映射，E1 Warning |
| > 阈值 | 跳过，E1 Warning |
| 在自定义注册表中 | 使用自定义处理器 |

### 自定义处理器

```python
@register_custom_property("CustomGameplayTag")
def parse_custom_gameplay_tag(ctx: CustomPropertyContext) -> PropertyValue: ...
```

- 异常视为 E2（可恢复），不阻断后续解析
- 不污染核心解析管线

### 约束
1. 未知类型优雅降级（L2→L1），不抛异常
2. 记录必须含：asset_type、class_name、file_path、offset
3. 相同未知类型日志去重
4. 回退链可配置

---

## 诊断输出（未知但结构可识别）

输出位置：`ParseResult.status.diagnostics.unknown_types[]`

```json
{
  "class_name": "CustomFortItemDefinition",
  "object_name": "DA_Sword_Common",
  "outer_path": "/Game/Items/Weapons/Sword",
  "serial_offset": 1024, "serial_size": 2048,
  "properties_sample": [{"name": "DisplayName", "type": "TextProperty"}],
  "properties_truncated": true, "properties_total_count": 35
}
```

### 限制

| 项目 | 上限 |
|------|------|
| 属性样本 | ≤ 20 个 |
| 类型名长度 | ≤ 128 字符 |
| 对象路径 | ≤ 256 字符 |
| 单文件条目 | ≤ 10 个 |
| 总计条目 | ≤ 50 个/次解析 |
| 原始二进制 | 不允许 |

---

## 测试要求

### 测试标准
- ≥ 200 个单元测试
- ≥ 40 个集成测试
- 100% 通过率（xfail 除外）
- 至少 12 种资产类型覆盖
- 稳定资产必须通过 strict 和 tolerant 双模式

### 验收测试
- 89 个验收用例覆盖 5 个维度
- 9 种资产类型 × 8 种输出格式 = 72 个矩阵用例
- 运行: `python scripts/test_matrix.py acceptance -q`
- 详见 `docs/guides/acceptance-matrix.md`

### 测试资产
依赖真实 UE 样本资产：
```
E:\Develop\lib\UnrealEngine\Samples\
├── FirstPerson\        # UE First Person 模板
├── ThirtPerson\        # UE Third Person 模板
├── StarterContent\     # UE Starter Content
└── Games\LyraStarterGame\  # UE Lyra 示例游戏
```

---

## 文件组织

### 源码布局
- `src/uasset_read/` — 主源码
- `tests/` — 测试文件
- `docs/` — 文档
- `temp/` — 临时文件（脚本、中间输出、调试日志、测试产物）

### 关键模块
- `parse_uasset.py` — 主入口，`parse_package()` 返回 `ParseResult`
- `core.py` — 高层 API（`parse_single`、`parse_batch`）
- `ir_builder.py` — `ParseResult` → `PackageIR`
- `models/ir.py` — IR 数据结构
- `models/result.py` — `ParseResult` 容器
- `parsers/class_serialization_strategy.py` — 类序列化策略表
- `link/linker.py` — 包链接器，preload/post_load 生命周期

### 外部参考
- `docs/formats/uasset/` — UE 格式文档（60+ Markdown 文件）
- `external/CUE4Parse/` — 参考 C# 实现
- `docs/reference/` — 蓝图节点文本参考等
- **必须参考 UE 源码**：格式理解必须追溯到 UE C++ 源码，禁止猜测二进制格式

---

## 未来可能的扩展方向（需另行规划）

1. **Cooked 资产支持** — 需要研究 UE cooked 格式
2. **写入能力** — 需要完整的序列化器实现
3. **更多资产类型** — 根据需求扩展专用解析器
4. **性能优化** — 并行解析、缓存机制
5. **Web API** — 提供 HTTP 接口服务
6. **GUI 工具** — 可视化资产浏览器
7. **类专属 Serialize()** — 为 StaticMesh、Texture2D 等高频资产实现完整序列化
8. **循环依赖检测** — 在依赖图构建后添加循环检测

---

**版本**: 0.4.5-dev  
**最后更新**: 2026-06-09  
**维护者**: uasset_read Contributors
