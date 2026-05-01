# 技术栈推荐

**领域：** Python 二进制解析器，面向 Unreal Engine .uasset 文件
**研究日期：** 2026-04-27

## 推荐技术栈

| 组件 | 推荐 | 版本 | 原因 |
|------|------|------|------|
| **语言** | Python | 3.10+ | 用户指定；dataclasses（3.7+）、typing改进（3.10+）、二进制解析支持良好 |
| **二进制解析** | struct（内置）+ mmap | 内置 | 无需外部依赖；struct 用于类型解包，mmap 用于大文件 |
| **数据模型** | dataclasses | 内置（3.7+） | 清晰模型定义；asdict() 用于 JSON 序列化；类型提示 |
| **JSON 输出** | json（内置）+ dataclasses.asdict | 内置 | 标准；无外部依赖；asdict() 直接转换模型 |
| **CLI 接口** | argparse | 内置 | 简单命令行解析；标准库；单文件工具足够 |
| **文件处理** | pathlib + open/mmap | 内置 | 跨平台路径；通过 mmap 流式文件访问用于大文件 |
| **错误处理** | 自定义异常 + logging | 内置 | 结构化错误；logging 用于调试；优雅降级 |

## 不推荐使用

| 库 | 避免原因 | 替代方案 |
|----|----------|----------|
| **construct** | 增加复杂性；比 struct 慢；声明式语法学习曲线 | 直接使用 struct.unpack 配合显式偏移 |
| **numpy** | 对字节解析过于繁重；内存开销；非二进制序列化设计 | 使用 struct + mmap |
| **pydantic** | 添加依赖；只读解析不需要验证开销 | 使用纯 dataclasses |
| **click/rich** | 外部依赖；简单 CLI argparse 已足够 | 使用 argparse + 简单 print |
| **pytest**（运行时） | 运行时不需要；测试是独立环节 | 仅用于测试 |
| **lark/parser** | .uasset 是二进制非文本；无需语法解析 | 使用 struct 二进制解析 |
| **marshmallow** | 序列化开销；非二进制格式设计 | 使用 dataclasses + 自定义序列化 |

## Python 版本要求

**最低：Python 3.10**

为何 3.10+：
- `match/case` 语句用于类型分发（比 if/else 链更清晰）
- `ParamSpec` 和 `TypeVarTuple` 用于高级类型（如需）
- 更好的错误信息（有助于调试二进制解析问题）
- `dataclasses` 成熟稳定（3.7 起可用，3.10 已充分测试）

若无法 3.10，3.8+ 可用 if/else 分发替代 match/case。

## 依赖理念

**零运行时依赖，仅使用 Python 标准库。**

原因：
- AI agent 需要简单安装（`pip install` 或直接 `python uasset_read.py`）
- 标准库足够用于二进制解析、JSON 输出、CLI
- 降低维护负担（无版本冲突、无安全更新）
- 单文件执行可行（`python uasset_read.py file.uasset`）

测试依赖（不交付）：
- `pytest` 用于单元测试
- `hypothesis` 用于属性测试（可选）

## 核心技术栈架构

```
┌─────────────────────────────────────────────────────────────┐
│                    运行时技术栈                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ argparse        CLI 参数解析                            ││
│  │ pathlib         文件路径处理                            ││
│  │ mmap            内存映射文件 I/O                        ││
│  │ struct          二进制解包                              ││
│  │ dataclasses     数据模型定义                            ││
│  │ json            JSON 序列化                             ││
│  │ logging         调试/错误日志                           ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    测试技术栈                                │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ pytest          单元测试框架                            ││
│  │ hypothesis      属性测试（可选）                        ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

## UE 源码参考技术栈

解析器必须与 Unreal Engine 的序列化技术栈对齐：

| UE 组件 | Python 对应 | 源码路径 |
|---------|-------------|----------|
| `FArchive` | `FArchive` 基类 | `Core/Public/Serialization/Archive.h` |
| `FArchiveState` | 归档状态跟踪 | `Core/Public/Serialization/ArchiveState.h` |
| `FPackageFileSummary` | `PackageSummary` dataclass | `CoreUObject/Public/UObject/PackageFileSummary.h` |
| `FPackageIndex` | `PackageIndex` dataclass | `CoreUObject/Public/UObject/ObjectResource.h` |
| `FObjectImport` | `ObjectImport` dataclass | `CoreUObject/Public/UObject/ObjectResource.h` |
| `FObjectExport` | `ObjectExport` dataclass | `CoreUObject/Public/UObject/ObjectResource.h` |
| `FName` | 名称表 + 索引解析 | `Core/Public/UObject/NameTypes.h` |
| `FString` | 带长度前缀字符串读取 | `Core/Public/Containers/UnrealString.h` |
| `FPropertyTag` | 属性标签解析 | `CoreUObject/Public/UObject/PropertyTag.h` |

UE 5.7 源码位置：`D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/`

## 版本处理策略

UE 使用多层版本系统：

```python
# 需处理的版本类型
EUnrealEngineObjectUE4Version  # 214-522+（从最旧到最新 UE4）
EUnrealEngineObjectUE5Version  # 1000+（UE5 版本）
FCustomVersionContainer        # GUID 为键的自定义版本
LegacyFileVersion             # -2 至 -9（现代格式指示符）
```

解析器必须：
1. 从 PackageFileSummary 读取所有版本字段
2. 维护版本兼容性矩阵
3. 根据版本分支解析逻辑
4. 不支持版本时优雅失败

## 二进制解析模式

### 模式 1：struct.unpack 配合显式字节序

```python
import struct

# 始终使用显式字节序（< 小端序，> 大端序）
def read_u32(archive) -> int:
    return struct.unpack('<I', archive.read(4))[0]

def read_i32(archive) -> int:
    return struct.unpack('<i', archive.read(4))[0]

def read_f32(archive) -> float:
    return struct.unpack('<f', archive.read(4))[0]

def read_u64(archive) -> int:
    return struct.unpack('<Q', archive.read(8))[0]
```

### 模式 2：大文件内存映射

```python
import mmap
import os

def create_archive(path: str):
    file_size = os.path.getsize(path)
    if file_size > 100 * 1024 * 1024:  # > 100MB
        return MappedArchive(path)  # mmap 方式
    return FileArchive(path)  # 标准文件句柄
```

### 模式 3：版本感知序列化

```python
def read_package_summary(archive) -> PackageSummary:
    tag = read_u32(archive)
    
    # 检查字节交换
    if tag == PACKAGE_FILE_TAG_SWAPPED:
        archive.set_byte_swapping(True)
        tag = PACKAGE_FILE_TAG
    
    # 版本字段
    legacy_version = read_i32(archive)
    ue4_version = read_i32(archive) if legacy_version >= -8 else 0
    ue5_version = read_i32(archive) if legacy_version >= -8 else 0
    # ... 继续版本感知逻辑
```

## JSON 输出技术栈

```python
from dataclasses import dataclass, asdict
import json

@dataclass
class BlueprintInfo:
    name: str
    parent_class: str
    variables: list[VariableInfo]

@dataclass
class VariableInfo:
    name: str
    type: str
    default_value: str | None

def output_json(blueprint: BlueprintInfo) -> str:
    return json.dumps(asdict(blueprint), indent=2)
```

## 文本输出技术栈

```python
def output_text(blueprint: BlueprintInfo) -> str:
    lines = [
        f"蓝图: {blueprint.name}",
        f"父类: {blueprint.parent_class}",
        "",
        "变量:",
    ]
    for var in blueprint.variables:
        lines.append(f"  - {var.name}: {var.type}")
        if var.default_value:
            lines.append(f"    默认值: {var.default_value}")
    return "\n".join(lines)
```

## 文件结构建议

```
uasset_read/
├── uasset_read.py          # 主入口（单文件版本）
├── src/
│   ├── __init__.py
│   ├── archive.py          # FArchive 基类 + 实现
│   ├── summary.py          # PackageFileSummary 模型 + 解析
│   ├── name_table.py       # 名称表解析
│   ├── import_export.py    # 导入/导出表解析
│   ├── properties.py       # 属性标签 + 值解析
│   ├── blueprint.py        # 蓝图特定提取
│   ├── output.py           # JSON/文本/概要格式器
│   └── errors.py           # 自定义异常
├── tests/
│   ├── test_archive.py
│   ├── test_summary.py
│   └── ...
└── pyproject.toml          # 项目元数据（可选）
```

**单文件版本**（`uasset_read.py`）便于简单部署：
- 所有代码在一文件（约 2000-3000 行）
- 直接执行：`python uasset_read.py file.uasset`
- 无需包安装

**包版本**（`src/` 目录）便于维护：
- 清晰关注点分离
- 可测试组件
- 可导入：`from uasset_read import parse_uasset`

## 安装模式

### 模式 A：单文件（零安装）

```bash
# 下载单文件
python uasset_read.py --json input.uasset > output.json
```

### 模式 B：pip 安装（包）

```bash
pip install uasset_read
python -m uasset_read --json input.uasset > output.json
```

### 模式 C：可导入模块（面向 AI agent）

```python
from uasset_read import parse_uasset, BlueprintInfo

result = parse_uasset("path/to/file.uasset")
print(result.blueprint.variables)
```

## 性能考量

| 方案 | 内存 | 速度 | 适用场景 |
|------|------|------|----------|
| FileArchive + read() | 低 | 中 | 小文件（<50MB） |
| MappedArchive + mmap | 极低 | 快 | 大文件（>50MB） |
| 全量读取 | 高 | 启动快 | 不推荐 |

## 测试技术栈

| 组件 | 目的 | 备注 |
|------|------|------|
| `pytest` | 单元测试框架 | 开发必需 |
| `hypothesis` | 属性测试 | 可选；适合二进制边缘情况 |
| Mock 归档 | 无真实文件测试 | FMemoryArchive 用于测试固定数据 |
| 示例 .uasset | 集成测试 | 创建简单 UE 项目获取测试文件 |

## 安全考量

- 无不可信输入解析（用户提供文件）
- 通过文件大小检查设置内存限制
- 无网络访问（独立工具）
- 无文件修改（只读）

## 置信度评估

| 推荐 | 置信度 | 原因 |
|------|--------|------|
| Python 3.10+ | 高 | 用户指定；标准库足够 |
| 零运行时依赖 | 高 | 标准库覆盖所有需求 |
| struct + mmap | 高 | 二进制解析的成熟模式 |
| dataclasses | 高 | 清晰模型；内置 JSON 序列化 |
| argparse | 高 | 简单 CLI；标准库 |
| 版本处理 | 中 | 复杂但 UE 源码中有文档 |
| 单文件版本 | 中 | 便于部署；增长后可能需重构 |

---

## 来源

- UE 5.7 源码：`D:/Program Files/Epic Games/Engine/UE_5.7/`
- Python 文档：struct、mmap、dataclasses、argparse（官方）
- CUE4Parse：UE 格式二进制解析模式
- FModel：类 Python 架构的 UE 资产解析