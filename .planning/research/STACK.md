# Technology Stack — CUE4Parse 全量对齐

**Project:** uasset_read v14.0
**Researched:** 2026-05-26

## 新增依赖总览

v14.0 需要在当前「零运行时依赖」的基础上引入可选依赖组（`optional-dependencies`），按功能域分组安装。核心原则：**基础 uasset 解析保持零依赖**，Pak/IoStore、资源导出等高级功能通过 extras 按需启用。

## Pak/IoStore 解析

### 方案推荐：自建实现（不引入外部 Pak 库）

| 决策 | 理由 |
|------|------|
| **自建 PakReader** | .pak 格式是纯二进制结构（FPakEntry 表 + FPakInfo 尾部），FArchive 已有完整底层读取能力，不需要第三方库 |
| **自建 IoStoreReader** | .utoc/.ucas 格式同样可由 FArchive 处理，核心是 TOC 解析 + 完美哈希查找 |
| **参考实现** | CUE4Parse `PakFileReader.cs` + `IoStoreReader.cs`，以及 pyUE4Parse（MinshuG/pyUE4Parse）的 Python 实现 |

**不引入** pyuepak 或 PyPAKParser —— 它们是独立工具，不是库级别的可复用组件，且架构与本项目不兼容。

### Pak 模块设计

```
src/uasset_read/
├── pak/
│   ├── __init__.py
│   ├── reader.py          # PakFileReader — FPakInfo/FPakEntry 解析
│   ├── vfs.py             # PakVFS — 虚拟文件系统抽象
│   └── structures.py      # FPakInfo, FPakEntry, FPakDirectoryEntry
├── iostore/
│   ├── __init__.py
│   ├── reader.py          # IoStoreReader — .utoc/.ucas 解析
│   └── structures.py      # FIoStoreTocResource, FIoChunkHash, FIoOffsetAndLength
└── file_provider/
    ├── __init__.py
    ├── base.py            # IFileProvider 抽象接口
    └── default.py         # DefaultFileProvider — 文件扫描/路径映射/包加载
```

## 压缩系统

### 推荐方案

| 算法 | Python 库 | 版本 | 安装方式 | C 绑定 | 使用场景 | 优先级 |
|------|-----------|------|----------|--------|----------|--------|
| **Zlib** | `zlib` (stdlib) | Python 3.10+ | 内置 | 否 | Pak 条目压缩 (`COMPRESS_ZLIB`) | 必需 |
| **LZ4** | `lz4` | >=4.3.2 | `pip install lz4` | 是（Cython 编译） | Pak 快速压缩 (`COMPRESS_LZ4`) | 高 |
| **Zstd** | `zstandard` | >=0.23.0 | `pip install zstandard` | 是（C 扩展） | Pak 高压缩比 (`COMPRESS_ZSTD`) | 高 |
| **Oodle** | `python_oodle` (CTypes wrapper) | 无 PyPI | 手动安装 + 编译 liboodle | **是（必需）** | UE4.25+ 默认游戏压缩 | 高 |

### Oodle — 详细说明

Oodle 是**唯一需要 C 原生绑定**的压缩库，也是 v14.0 安装最复杂的部分。

```
依赖链:
ooz (C 库, powzix/ooz)
  → liboodle (编译产物)
    → python_oodle (Python CTypes wrapper, baconwaifu/python_oodle)
      → uasset_read pak/compression.py
```

**安装步骤:**
1. 克隆并编译 [powzix/ooz](https://github.com/powzix/ooz)（C 库，支持 Kraken/Mermaid/Selkie/Leviathan/LZNA/Bitknit）
2. 或使用 Epic 官方提供的 Oodle DLL（`oo2core_*.dll`，UE 现已免费提供）
3. 安装 [baconwaifu/python_oodle](https://github.com/baconwaifu/python_oodle) CTypes 包装器
4. 在 `pyproject.toml` 中标记为 `oodle = ["python-oodle @ git+https://github.com/baconwaifu/python_oodle"]`

**降级策略:** 如果 Oodle 不可用，Pak 解压时跳过使用 Oodle 压缩的条目（记录警告），不影响其他压缩算法的条目。

**支持的 Oodle 算法**（通过 ooz/liboodle）:
- Kraken — 最常用，UE4.25+ 默认
- Mermaid — 中等压缩比
- Selkie — 快速解压
- Leviathan — 最高压缩比
- LZNA — 极高压缩比（慢）
- Bitknit — 文本/代码专用

### 压缩模块集成点

```python
# src/uasset_read/compression.py
from enum import IntFlag

class ECompressionFlags(IntFlag):
    COMPRESS_None      = 0x00
    COMPRESS_Zlib      = 0x01
    COMPRESS_Gzip      = 0x02
    COMPRESS_LZ4       = 0x10
    COMPRESS_Zstandard = 0x40
    COMPRESS_Oodle     = 0x80  # 需要 C 绑定

def decompress_chunk(data: bytes, flags: ECompressionFlags) -> bytes:
    """统一解压缩入口，按 flag 分发到对应引擎"""
```

## 加密系统

### 推荐方案

| 算法 | Python 库 | 版本 | 安装方式 | C 绑定 | 使用场景 |
|------|-----------|------|----------|--------|----------|
| **AES-ECB/CBC** | `pycryptodome` | >=3.20.0 | `pip install pycryptodome` | 是（C 扩展，自动编译） | Pak AES 解密 |
| **XOR** | 纯 Python 实现 | — | 无需安装 | 否 | 游戏轻量加密（Snowbreak 等） |

**选择 pycryptodome 而非 cryptography 的理由:**
- pycryptodome 是纯 Python + C 扩展，API 直接对应 AES-ECB/AES-CBC
- `cryptography` 库更重，面向 TLS/HTTPS 场景，AES 操作需要多层包装
- CUE4Parse 使用 BouncyCastle（也是直接 AES 原语），pycryptodome 语义最接近
- 支持 ECB 模式（Pak 标准模式）和 CBC 模式（游戏变体）

### 加密模块集成点

```python
# src/uasset_read/encryption.py
from Crypto.Cipher import AES

class AESKey:
    def __init__(self, key: bytes):  # 32 bytes for AES-256
        self._key = key

    def decrypt_ecb(self, data: bytes) -> bytes:
        cipher = AES.new(self._key, AES.MODE_ECB)
        return cipher.decrypt(data)

    def decrypt_cbc(self, data: bytes, iv: bytes) -> bytes:
        cipher = AES.new(self._key, AES.MODE_CBC, iv)
        return cipher.decrypt(data)
```

**游戏自定义加密** — 通过委托模式（参考 CUE4Parse `CustomEncryptionDelegate`）：
```python
# 允许注入 per-game 解密函数
CustomEncryption = Callable[[str, bytes], bytes]  # (path, data) -> decrypted
```

## 纹理导出

### 推荐方案

| 格式 | Python 库 | 版本 | 安装方式 | C 绑定 | 说明 |
|------|-----------|------|----------|--------|------|
| **BC1/DXT1** | `texture2ddecoder` | >=1.1 | `pip install texture2ddecoder` | 是（C 扩展） | Perfare Texture2DDecoder 的 Python wrapper |
| **BC4** | 同上 | 同上 | 同上 | 同上 | 单通道压缩 |
| **BC5** | 同上 | 同上 | 同上 | 同上 | 双通道（法线贴图） |
| **BC6H** | 同上 | 同上 | 同上 | 同上 | HDR 压缩 |
| **BC7** | 同上 | 同上 | 同上 | 同上 | 高质量 RGBA |
| **ASTC/ETC** | `imagecodecs` | >=2023.9.4 | `pip install imagecodecs` | 是（C 扩展） | Android 格式，作为 fallback |
| **PNG 输出** | `Pillow` | >=10.0 | `pip install Pillow` | 是（C 扩展） | RGBA byte[] → PNG 文件 |

**选择 texture2ddecoder 的理由:**
- 专门针对游戏资源提取场景设计（Perfare 是 UABE/UAssetAPI 作者）
- 支持 BC1/BC4/BC5/BC6H/BC7，覆盖 UE 主要纹理格式
- MIT 许可，体积小，API 简单（`decode_bc7(data, width, height) -> bytes`）
- 比 imagecodecs 更轻量（imagecodecs 是科学计算导向的大型库）

**imagecodecs 作为 fallback** — 当遇到 texture2ddecoder 不支持的格式（ASTC、ETC1/2、PVRTC）时使用。

### 纹理导出模块

```
src/uasset_read/
└── conversion/
    ├── __init__.py
    ├── textures/
    │   ├── __init__.py
    │   ├── decoder.py         # PixelFormat → decoder 分派
    │   ├── bc_decoder.py      # BC1/4/5/6/7 (texture2ddecoder)
    │   ├── deswizzle.py       # 平台反交错 (Xbox/Switch)
    │   └── exporter.py        # RGBA → PNG (Pillow)
    └── pixel_format.py        # EPixelFormat enum + 参数查询
```

## 网格导出

### 推荐方案

| 目标格式 | Python 库 | 版本 | 安装方式 | C 绑定 | 说明 |
|----------|-----------|------|----------|--------|------|
| **PSK/PSKX** | 纯 Python 实现 | — | 无需安装 | 否 | ActorX 二进制格式，结构已知可直接写 |
| **glTF/GLB** | `pygltflib` | >=1.16 | `pip install pygltflib` | 否 | glTF 2.0 Python 库，纯 Python 实现 |
| **OBJ** | 纯 Python 实现 | — | 无需安装 | 否 | 文本格式，直接字符串拼接 |

**PSK 格式** 是 UE 社区标准（Unreal Engine 自带的 ActorX 插件导出格式），二进制结构完全已知，不需要外部库。

**glTF** 选择 pygltflib 是因为：
- 纯 Python 实现，无 C 依赖
- 完整支持 glTF 2.0 spec（mesh/buffer/material/animation）
- 可直接输出 `.glb`（二进制 glTF）

### 网格导出模块

```
src/uasset_read/
└── conversion/
    ├── meshes/
    │   ├── __init__.py
    │   ├── static_mesh.py     # UStaticMesh → LOD 数据提取
    │   ├── skeletal_mesh.py   # USkeletalMesh → 骨骼/权重/LOD
    │   ├── psk_writer.py      # 纯 Python PSK 二进制写入
    │   ├── gltf_writer.py     # pygltflib → glTF/GLB
    │   └── obj_writer.py      # 纯 Python OBJ 文本写入
    └── materials/
        └── material_params.py  # UMaterial 材质参数提取为 JSON
```

## 音频导出

### 推荐方案

| 音频格式 | Python 库 | 版本 | 安装方式 | C 绑定 | 说明 |
|----------|-----------|------|----------|--------|------|
| **OGG/Vorbis** | `PyOgg` | >=0.5 | `pip install PyOgg` | 是（捆绑 DLL） | Xiph.org 绑定，自带动态库 |
| **OGG/Opus** | 同上 | 同上 | 同上 | 同上 | 同上 |
| **ADPCM (MS/IMA)** | 纯 Python 实现 | — | 无需安装 | 否 | 算法已知，纯 Python 实现（注意：`audioop` 在 Python 3.13 已移除） |
| **PCM** | `wave` (stdlib) | Python 3.10+ | 内置 | 否 | 直接包装为 WAV |
| **FLAC** | `PyOgg` | 同上 | 同上 | 同上 | Ogg FLAC 容器 |

**不引入 miniaudio** —— PyOgg 已覆盖 OGG/Vorbis/Opus/FLAC，miniaudio 更侧重播放而非解码。

**ADPCM 自行实现** —— MS ADPCM 和 IMA ADPCM 的解码算法是公开的，纯 Python 实现约 100 行代码，无需外部依赖。

### 音频导出模块

```
src/uasset_read/
└── conversion/
    └── sounds/
        ├── __init__.py
        ├── decoder.py         # 格式检测 → decoder 分派
        ├── vorbis_decoder.py  # PyOgg → PCM
        ├── adpcm_decoder.py   # 纯 Python MS/IMA ADPCM → PCM
        └── wav_writer.py      # PCM → WAV (wave stdlib)
```

## VersionContainer 游戏差异

### 推荐方案：纯内部实现

不需要外部库。基于现有 FArchive 的版本判断机制扩展：

```python
# src/uasset_read/versions/
# ├── __init__.py
# ├── game.py          # EGame enum (70+ 游戏)
# ├── container.py     # VersionContainer — 游戏/版本/自定义版本
# ├── custom.py        # CustomVersion 定义 (FCustomVersionEntry)
# └── behaviors.py     # 版本行为分派 (Ver >= UE4_23 ? ... : ...)
```

**关键设计**: 字符串键索引的自定义版本查询（与 CUE4Parse 一致）:
```python
container["SkeletalMesh.UseNewCookedFormat"]  # -> bool
container["Animation.ModifySerializeLayout"]  # -> int version
```

## UObject 继承树 Python 化

### 推荐方案：基于现有 PackageLinker 扩展

不需要外部库。利用已有的 PackageLinker 两阶段加载：

```python
# src/uasset_read/
# └── reflection/
#     ├── __init__.py
#     ├── hierarchy.py    # UClass → UStruct → UField 继承链解析
#     ├── uscript_class.py # UScriptClass — 脚本结构体字段描述
#     └── property_system.py  # UProperty 体系完整映射
```

**核心能力**:
- BPGC（BlueprintGeneratedClass）的 SuperField 链遍历
- UScriptClass 字段偏移表解析（未版本化属性模式）
- 完整的 UObject 类型注册表

## 完整 pyproject.toml 依赖配置

```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
]

# Pak/IoStore 解析（压缩 + 加密）
pak = [
    "lz4>=4.3.2",              # LZ4 压缩
    "zstandard>=0.23.0",       # Zstd 压缩
    "pycryptodome>=3.20.0",    # AES 加密/解密
    # python-oodle 需要手动安装（见 Oodle 安装说明）
]

# 纹理导出
textures = [
    "texture2ddecoder>=1.1",   # BCn 纹理解码
    "Pillow>=10.0",            # PNG 输出
]

# 网格导出
meshes = [
    "pygltflib>=1.16",         # glTF/GLB 导出
]

# 音频导出
audio = [
    "PyOgg>=0.5",              # OGG/Vorbis/Opus/FLAC
]

# 全部高级功能（组合所有 extras）
full = [
    "uasset_read[pak,textures,meshes,audio]",
]
```

## 依赖关系图

```
uasset_read (core, 零依赖)
├── FArchive → serializers → models → parsers → graph → kismet → n2c
│
├── [pak] → PakReader / IoStoreReader
│   ├── lz4 (LZ4 解压)
│   ├── zstandard (Zstd 解压)
│   ├── pycryptodome (AES 解密)
│   └── python_oodle (Oodle 解压, C 绑定, 可选)
│
├── [textures] → 纹理导出
│   ├── texture2ddecoder (BCn 解码, C 扩展)
│   └── Pillow (PNG 输出)
│
├── [meshes] → 网格导出
│   └── pygltflib (glTF, 纯 Python)
│
└── [audio] → 音频导出
    └── PyOgg (Vorbis/Opus, C 绑定)
```

## C 绑定需求汇总

| 库 | C 绑定类型 | 自动安装 | 手动步骤 | Windows 兼容性 |
|----|-----------|----------|----------|---------------|
| lz4 | Cython 编译 | `pip install` 自动编译 | 无 | 需要 MSVC 或预编译 wheel |
| zstandard | C 扩展 | `pip install` 自动编译 | 无 | 提供 prebuilt wheel |
| pycryptodome | C 扩展 | `pip install` 自动编译 | 无 | 提供 prebuilt wheel |
| texture2ddecoder | C 扩展 | `pip install` 自动编译 | 无 | 提供 prebuilt wheel |
| PyOgg | 捆绑 DLL | `pip install` 自带 DLL | 无 | 自带 libogg/libvorbis DLL |
| python_oodle | CTypes | **需要手动编译** | 编译 ooz/liboodle | 需要自行编译或使用 UE 自带 DLL |

**只有 Oodle 需要手动 C 编译步骤**，其余所有 C 绑定库都通过 pip 自动安装（提供预编译 wheel）。

## 不需要添加的库

| 库 | 为什么不添加 | 替代方案 |
|----|-------------|----------|
| pyuepak / PyPAKParser | 独立工具，不是库，架构不兼容 | 自建 PakReader |
| imagecodecs | 大型科学计算库，体积庞大（>100MB） | 仅在 ASTC/ETC 需要时作为 fallback |
| miniaudio | 侧重播放而非解码 | PyOgg 已覆盖 |
| cryptography | API 复杂，面向 TLS | pycryptodome 更直接 |
| numpy | 纯数值计算，不匹配资产解析场景 | 不需要 |
| scipy | 科学计算，完全不相关 | 不需要 |

## 安装命令

```bash
# 基础安装（零依赖，现有功能）
pip install -e ".[dev]"

# Pak/IoStore 支持
pip install -e ".[dev,pak]"

# 完整安装（所有功能）
pip install -e ".[dev,full]"
```

## Sources

- [CUE4Parse 官方源码](https://github.com/FabianFG/CUE4Parse) — 架构参考
- [CUE4Parse 外部依赖表](https://github.com/FabianFG/CUE4Parse) — NuGet 包列表
- [pyUE4Parse (Python port)](https://github.com/MinshuG/pyUE4Parse) — Python Pak/IoStore 解析实现
- [powzix/ooz](https://github.com/powzix/ooz) — 开源 Oodle 解压器
- [baconwaifu/python_oodle](https://github.com/baconwaifu/python_oodle) — Python Oodle CTypes wrapper
- [texture2ddecoder PyPI](https://pypi.org/project/texture2ddecoder/) — BCn 纹理解码
- [lz4 PyPI](https://pypi.org/project/lz4/) — LZ4 Python 绑定
- [zstandard PyPI](https://pypi.org/project/zstandard/) — Zstd Python 绑定
- [pycryptodome AES 文档](https://pycryptodome.readthedocs.io/en/latest/src/cipher/aes.html) — AES 加密
- [PyOgg PyPI](https://pypi.org/project/PyOgg/) — OGG/Vorbis/Opus/FLAC 解码
- [pygltflib PyPI](https://pypi.org/project/pygltflib/) — glTF 2.0 Python 库
- [Pillow DDS 文档](https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html) — 图像格式支持
- [UE5 Zen Loader 文档](https://dev.epicgames.com/documentation/unreal-engine/zen-loader-in-unreal-engine?lang=zh-CN) — IoStore 架构
- [audioop 文档](https://docs.python.org/3.10/library/audioop.html) — Python 标准库 ADPCM（已弃用）
