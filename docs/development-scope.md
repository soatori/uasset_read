# 开发范围及限制

## 项目定位

**uasset_read** 是一个专为 AI 代理设计的虚幻引擎 `.uasset` 文件 Python 解析器，使 AI 代理无需 UE 编辑器即可读取和理解蓝图内容。

### 核心目标
- 提供对未烘焙/编辑器保存的 `.uasset` 文件的完整读取能力
- 使 AI 代理能够理解蓝图逻辑、变量、函数调用关系
- 输出结构化数据（JSON/Text/Markdown/C++ 骨架等格式）
- 保持零运行时依赖的轻量级设计

## 开发范围

### ✅ 包含的功能（IN SCOPE）

#### 1. 核心解析能力
- `.uasset` 二进制格式解析（FArchive 序列化管线镜像）
- UE4/UE5 多个版本的兼容支持
- 包链接器（PackageLinker）对象图重建
- 名称表、导入表、导出表解析
- PropertyTag 及 40+ 种属性类型解析

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
- Blueprint（蓝图）
- SkeletalMesh（骨骼网格体）
- StaticMesh（静态网格体）
- Material（材质）
- MaterialInstanceConstant（材质实例常量）
- Texture2D（2D 纹理）
- Niagara（粒子系统）
- Map（关卡地图）
- InputAction / InputMappingContext（输入资产）
- AnimBlueprint（动画蓝图）
- ParticleSystem（粒子系统，UE4 有限支持）
- 60+ 种资产类型的基础元数据读取

#### 4. 输出格式
- JSON（完整/摘要）
- 人类可读文本
- Markdown + Mermaid 图表
- 蓝图翻译参考文本
- UE 格式文本
- C++ 类骨架生成
- N2C 中间格式 JSON
- 批量导出支持

#### 5. 容器支持
- 文件系统直接读取
- .pak 文件读取（AES 解密、LZ4/Zstd 解压）
- IoStore 容器读取
- 原始文件解析（JSON/INI/LocRes/LocMeta/Audio）

#### 6. 高级功能
- 类型映射支持（.usmap/.jmap）
- C++ 代码生成（骨架、函数体、组件初始化）
- Agent 翻译管线（蓝图→C++ 完整转换）
- CLI 工具（`uasset-read` 命令）
- 容错/严格双模式解析

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
- N2C 是中间格式，非最终交换格式
- 不支持从输出格式还原为 `.uasset`

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

### 已知限制
1. **P_Fire.uasset** (ParticleSystem): UE4 legacy_file_version=-3，当前仅支持 {-9, -8}
2. **Cooked 资产**: 图数据已被剥离，无法解析蓝图逻辑
3. **自定义属性**: 需要通过 `CUSTOM_PROPERTY_HANDLERS` 注册表手动扩展
4. **大文件**: 使用 mmap 阈值（`MMAP_THRESHOLD`）限制内存使用

### 性能边界
- 单文件解析时间取决于资产复杂度
- 批量导出建议使用 `BatchExporter`
- 大文件（>100MB）建议使用 `--summary` 模式

## 质量保证

### 测试要求
- ≥ 200 个单元测试
- ≥ 40 个集成测试
- 100% 通过率（xfail 除外）
- 至少 12 种资产类型覆盖
- 稳定资产必须通过 strict 和 tolerant 双模式

### 测试资产
依赖真实 UE 样本资产：
```
E:\Develop\lib\UnrealEngine\Samples\
├── FirstPerson\        # UE First Person 模板
├── ThirtPerson\        # UE Third Person 模板
├── StarterContent\     # UE Starter Content
└── Games\LyraStarterGame\  # UE Lyra 示例游戏
```

### 提交前检查清单
- [ ] 所有单元测试通过
- [ ] 所有集成测试通过
- [ ] 无新的测试失败（xfail 除外）
- [ ] 新增功能有对应测试用例
- [ ] Bug 修复有回归测试

## 开发规范

### 代码规范
- 使用 Python 类型注解
- 中文注释
- 匹配现有代码风格（注释密度、命名习惯）
- 遵循 `CLAUDE.md` 中的架构指导

### 文件组织
- 源码位于 `src/uasset_read/`
- 测试位于 `tests/`
- 文档位于 `docs/`
- **临时文件一律放在 `temp/` 目录**

### 外部参考
- `docs/uasset-format/` — UE 格式文档（60+ Markdown 文件）
- `external/CUE4Parse/` — 参考 C# 实现
- `docs/reference/` — 蓝图节点文本参考等
- **必须参考 UE 源码**：格式理解必须追溯到 UE C++ 源码，禁止猜测二进制格式

## 未来可能的扩展方向（需另行规划）

1. **Cooked 资产支持** — 需要研究 UE cooked 格式
2. **写入能力** — 需要完整的序列化器实现
3. **更多资产类型** — 根据需求扩展专用解析器
4. **性能优化** — 并行解析、缓存机制
5. **Web API** — 提供 HTTP 接口服务
6. **GUI 工具** — 可视化资产浏览器

---

**版本**: 0.4.2-dev  
**最后更新**: 2026-06-03  
**维护者**: uasset_read Contributors