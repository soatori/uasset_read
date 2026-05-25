# Feature Landscape

**Domain:** CUE4Parse Python 全量对齐 — Pak/IoStore 包解析、压缩/加密、资源导出、游戏适配
**Researched:** 2026-05-26

## 现有能力基线（v12.0 已归档）

| 模块 | 状态 | 说明 |
|------|------|------|
| FArchive | 已完成 | mmap、字节交换、FString/FName 读取、全类型原语 |
| Package 解析 | 已完成 | Summary → NameMap → Import/Export Map、两阶段 Linker |
| 14 种属性解析器 | 已完成 | Bool/Byte/Int/Float/Str/Name/Object/SoftObject/Array/Struct/Map/Set/Enum/Text/Delegate |
| 蓝图图解析 | 已完成 | UEdGraph/Node/Pin 提取、执行流/数据流/连接映射 |
| Kismet 字节码 | 已完成 | 60+ EExprToken 表达式、C++ 翻译、结构化控制流 |
| N2C 中间格式 | 已完成 | 126 种 K2Node 类型、9 个 Processor、JSON Schema |
| C++ 骨架生成 | 已完成 | ClassIR → .h/.cpp 文件对 |
| **Pak/IoStore** | 缺失 | v14.0 新增 |
| **压缩算法** | 缺失 | v14.0 新增 |
| **加密/AES** | 缺失 | v14.0 新增 |
| **资源导出** | 缺失 | v14.0 新增 |
| **游戏适配** | 缺失 | v14.0 新增 |

## Table Stakes

用户在游戏资产逆向领域期望 CUE4Parse 对齐工具必须具备的功能。缺失任何一项，产品会被视为不完整。

| Feature | Why Expected | Complexity | Notes |
|---------|-------------|------------|-------|
| **.pak 文件解析** | 游戏分发标准格式，所有提取流程的入口 | High | 需要 FPakInfo 读取（尾部 Magic 0x5A6F12E1，版本 1~12）、Entry 表解析、按偏移+大小定位条目。支持 v10+ 高效索引格式和旧版 Legacy 格式。 |
| **IoStore (.utoc/.ucas) 解析** | UE5 默认打包格式，取代 .pak | High | .utoc 包含 FIoStoreTocResource（Chunk ID 表、偏移量、压缩块信息、目录哈希索引），.ucas 是实际数据存储。需要完美哈希 O(1) 查找和分区容器支持。 |
| **AES 解密** | 绝大多数游戏 .pak 都加密 | Medium | AES-ECB 标准解密（16 字节块），32 字节 AES Key 从 FPakInfo 读取。部分游戏使用 AES-CBC 变体（需要 IV）。Python 可用 `cryptography` 库。 |
| **Oodle 解压缩** | UE4.25+ 默认游戏压缩算法 | High | 需要绑定 `oo2core` C 原生库（Oodle.NET 的 Python 对应）。UE 使用 `CompressionFormatName` 标识 Oodle 变体（Bithack/LZH/LZNA/Kraken/Mermaid/Selkie/Leviathan）。无法用纯 Python 替代（性能差 100x）。 |
| **LZ4 解压缩** | 常见快速压缩 | Low | 纯 Python 实现可行但慢。推荐 `lz4` PyPI 包。`FCompressedChunk` 结构：CompressedSize + UncompressedSize + ECompressionFlags + CompressedData。 |
| **Zstd 解压缩** | 高压缩比场景 | Low | 推荐 `zstandard` PyPI 包。 |
| **Zlib 解压缩** | 通用压缩（UE 内置支持） | Low | Python 标准库 `zlib` 即可，零额外依赖。 |
| **纹理数据提取** | 最常被提取的资产类型 | High | 读取 UTexture2D 的 BulkData（MIP 链），解析 EPixelFormat。需要按格式解码像素数据。支持的格式：DXT1/3/5、BC4/5/6H/7、ASTC、ETC1/2、未压缩 RGBA。平台反交错（Xbox XBPS / Switch）。 |
| **网格数据提取** | 3D 模型提取核心 | High | 静态网格：PositionVertexBuffer + VertexBuffer（UVs/Normals/Tangents）+ IndexBuffer + Sections。骨骼网格：ReferenceSkeleton（骨骼层级）+ 顶点权重（每顶点 1~4 骨骼）+ Morph Targets。UE5 Nanite：ZOrder 编码顶点 + 多层 LOD cluster。 |
| **音频数据提取** | 声音资产提取 | Medium | 检测格式（OGG/Vorbis、WEM/Wwise、ADPCM、PCM、BINKA、RADA、OPUS、AT9），选择对应解码器。输出 WAV（PCM 包装）或 OGG（重新编码）。 |
| **动画数据提取** | 动画资产提取 | Medium | USkeleton 骨骼引用 + UAnimSequence 关键帧数据（压缩/未压缩）。ACL 动画压缩集成（CUE4Parse 专有）。 |
| **材质参数提取** | 材质实例参数读取 | Medium | UMaterialInstanceConstant 的 ScalarParameters / VectorParameters / TextureParameterValues / FontParameterValues。输出 JSON 描述。 |
| **UObject 继承树完整映射** | 所有资产类型的基础 | Medium | 100+ UObject 派生类的序列化逻辑：UField → UEnum/UStruct/UClass/UFunction → UProperty 体系（20+ 子类）→ 具体导出类（纹理/网格/音频/材质等）。每个类有独立的 `Serialize()` 方法。 |
| **版本感知序列化** | UE 跨版本兼容 | High | VersionContainer 模式：EGame（70+ 游戏枚举）+ FPackageFileVersion + CustomVersionContainer（Guid→Version 映射）。每个序列化方法需要 `if (Ar.Ver >= EUEVersion.X)` 版本分支。 |
| **游戏特定覆盖** | 70+ 游戏各有特殊处理 | High | 加密覆盖（CustomEncryption 委托）、PAK 版本覆盖（UsingCustomPakVersion）、Package 头部处理（XOR 解密/跳过头部/版本号修正）、版本行为选择（Ar.Game switch）。 |
| **IFileProvider 文件发现** | 统一文件访问入口 | Medium | 文件扫描、路径映射、包加载。DefaultFileProvider（本地目录扫描）、StreamedFileProvider（流式加载）、ApkFileProvider（Android APK）。 |

## Differentiators

超出用户基本期望，但在实际使用中价值极高的功能。

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **多格式网格导出** | 直接输出 psk/glb/obj，无需后处理 | High | psk（ActorX 二进制，Blender 插件支持）、glb（glTF 2.0 二进制，通用交换格式）、obj（文本，最简格式）。需要实现三种写入器。 |
| **纹理 PNG/TIFF/HDR 导出** | 直接输出可用图片 | High | 解码 EPixelFormat → RGBA byte[] → PNG 写入。HDR 格式（BC6H）需要 float 通道。TIFF 支持多 MIP 层级存储。 |
| **音频 WAV/OGG 导出** | 直接输出可播放音频 | Medium | 解码后包装为 WAV（44 字节头 + PCM 数据）或重新编码为 OGG。 |
| **JSON 序列化兼容** | CUE4Parse 的 UObject → JSON 序列化 | Low | 现有项目的 `to_n2c_json()` 已验证此模式。所有 UObject 派生类需要 `ToJson()` 方法。 |
| **批量提取管线** | 一键提取整个游戏目录 | Medium | 递归扫描 .pak/.utoc/.ucas，自动解密/解压，按类型分类输出。 |
| **N2C 蓝图中间格式** | AI 代理优化的蓝图表示 | 已实现 | 现有项目的独特优势。CUE4Parse 输出表达式树，本项目输出语义化节点连接图 + N2C JSON。 |
| **C++ 骨架生成** | 蓝图 → C++ 代码参考 | 已实现 | CUE4Parse 无此功能。本项目的独家能力。 |

## Anti-Features

明确不应该构建的功能。

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **纯 Python Oodle 实现** | Oodle 是专有闭源算法，逆向工程不可行，且纯 Python 性能差 100x | 绑定 `oo2core` C 原生库（Windows .dll / Linux .so），或使用 `oodle` PyPI 包（如有）。如果不可用，标记为需要原生依赖并回退到不解压。 |
| **修改/写入 .uasset** | 项目定位为只读解析器，写入需要完整的 UE 序列化器实现 | 保持只读。如果用户需要修改，建议导出为 JSON/N2C → 手动编辑 → 使用 UE 编辑器重新烘焙。 |
| **Cooked 资产完整解析** | Cooked 资产使用完全不同的序列化格式（BulkData + 平台特定布局） | 仅解析未烘焙蓝图（项目已有能力）。Cooked 资产标记为"部分支持"或"需要额外研究"。 |
| **MCP Server** | 增加运行时依赖和复杂度，偏离核心解析目标 | 保持 CLI + Python API。MCP 可作为独立项目扩展。 |
| **实时 3D 渲染预览** | 需要 OpenGL/Vulkan 绑定，远超解析器范围 | 输出 glb/psk 格式，用户自行在 Blender/UE 中预览。 |
| **全 70+ 游戏适配一次性完成** | 每个游戏需要独立的逆向工程，工作量巨大 | 先实现通用框架（VersionContainer + CustomEncryption 接口），按游戏按需添加覆盖。 |
| **ACL 动画压缩** | 需要 ACL C 库绑定，且仅少数游戏使用 | 标记为"高级功能"，在基础动画提取完成后实现。 |

## Feature Dependencies

```
Pak/IoStore 解析 → 文件发现 → 条目定位 → AES 解密 → 压缩解压 → 原始 .uasset 字节
                                                                ↓
                                                       FArchive（已有）
                                                                ↓
                                                  Package 解析（已有）
                                                                ↓
                              ┌──────────────┬──────────────┬──────────────────┐
                              ↓              ↓              ↓                  ↓
                        纹理提取        网格提取       音频提取          蓝图图解析（已有）
                              ↓              ↓              ↓                  ↓
                        PNG 导出       psk/glb 导出    WAV 导出        N2C JSON（已有）
                              ↓              ↓              ↓                  ↓
                        ────────────────────────────────────────────→ 批量提取管线

版本管理系统 ← 所有解析模块（版本感知序列化需要）
游戏特定覆盖 ← Pak 解析 + 加密 + 版本管理
UObject 继承树 ← 所有资产类型提取
```

## MVP 推荐（v14.0 第一阶段）

按依赖顺序和实现复杂度排列：

1. **版本管理系统（VersionContainer）** — 所有后续模块的基础，需要先建立 EGame 枚举 + CustomVersion 查询
2. **AES 解密** — 中等复杂度，`cryptography` 库支持，覆盖大多数加密 .pak
3. **LZ4/Zstd 解压缩** — 低复杂度，PyPI 包成熟，覆盖大部分非 Oodle 压缩
4. **.pak 文件解析** — 高复杂度但核心，FPakInfo + Entry 表 + 条目提取
5. **UObject 继承树扩展** — 中复杂度，在现有属性解析基础上增加具体类型序列化

延后实现：
- **IoStore 解析** — 依赖 Pak 解析经验，UE5 特有，格式更复杂
- **Oodle 解压缩** — 需要 C 原生库绑定，调研成本大
- **纹理/网格/音频导出** — 依赖资产类型提取完成后，转换层独立实现
- **游戏特定覆盖** — 框架完成后按需添加

## 复杂度评估

| 复杂度级别 | 模块数 | 模块 |
|------------|--------|------|
| High | 5 | Pak 解析、IoStore 解析、Oodle 解压缩、纹理提取、网格提取 |
| Medium | 7 | AES 解密、音频提取、动画提取、材质提取、UObject 继承树、版本管理、游戏覆盖 |
| Low | 3 | LZ4 解压、Zstd 解压、Zlib 解压（标准库） |

## 新增 Python 依赖预估

| PyPI 包 | 用途 | 版本约束 |
|---------|------|----------|
| `cryptography` | AES-ECB/CBC 解密 | >=41.0 |
| `lz4` | LZ4 解压缩 | >=4.0 |
| `zstandard` | Zstd 解压缩 | >=0.21 |
| `numpy` | 像素数据处理（可选） | >=1.24 |
| `Pillow` | PNG/TIFF 写入 | >=10.0 |

注意：Oodle 需要原生 C 库绑定，目前 Python 生态无成熟包，需要自行封装或标记为"需要原生依赖"。

## Sources

- [CUE4Parse GitHub](https://github.com/FabianFG/CUE4Parse) — HIGH confidence (官方源码)
- [CUE4Parse-索引.md](E:\Develop\uasset_read\docs\CUE4Parse-索引.md) — HIGH confidence (项目内源码分析)
- [FRAMEWORK.md](E:\Develop\uasset_read\docs\FRAMEWORK.md) — HIGH confidence (项目内能力索引)
- [PROJECT.md](E:\Develop\uasset_read\.planning\PROJECT.md) — HIGH confidence (项目路线图)
- [FModel GitHub](https://github.com/4sval/FModel) — MEDIUM confidence (CUE4Parse 的主要消费者)
- [FortnitePorting GitHub](https://github.com/h4lfheart/FortnitePorting) — MEDIUM confidence (下游工具参考)
