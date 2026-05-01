# uasset_read_cpp

Unreal Engine .uasset 文件解析器 - C++20版本。

将Python的 `uasset_read.py` 转换为C++，提供高性能的.uasset文件解析功能。

## 功能

- 解析 UE4/UE5 .uasset 文件头部（PackageFileSummary）
- 读取名称表（NameMap）、导入表（ImportMap）、导出表（ExportMap）
- 解析属性数据（PropertyTag、PropertyValue）
- 提取蓝图元数据（BlueprintMetadata）
- 输出 JSON 和 YAML 格式文本

## 构建

### 要求

- C++20 编译器（MSVC 2022、GCC 11+、Clang 14+）
- CMake 3.20+

### 编译步骤

```bash
# Windows (Visual Studio)
cmake -B build -G "Visual Studio 17 2022" -A x64
cmake --build build --config Release

# Linux/macOS
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
```

### 输出

构建完成后生成 `uasset_read` 可执行文件。

## 使用

```bash
# 基本用法（YAML文本输出）
uasset_read path/to/file.uasset

# JSON输出
uasset_read path/to/file.uasset --json

# 紧凑摘要
uasset_read path/to/file.uasset --summary

# 输出到文件
uasset_read path/to/file.uasset --json --output result.json
```

### 命令行选项

| 选项 | 说明 |
|------|------|
| `--json` | 输出完整JSON格式 |
| `--text` | 输出YAML格式文本（默认） |
| `--summary` | 输出紧凑摘要JSON |
| `--output FILE` | 写入文件而非stdout |

## 项目结构

```
uasset_read_cpp/
├── CMakeLists.txt
├── include/uasset/
│   ├── constants.hpp      # UE版本常量
│   ├── exceptions.hpp     # 异常类
│   ├── types.hpp          # 数据结构
│   ├── archive.hpp        # FArchive二进制读取器
│   ├── parser.hpp         # 核心解析函数
│   ├── property_parser.hpp # 属性解析
│   ├── blueprint_parser.hpp # 蓝图提取
│   └── output.hpp         # 输出格式化
├── src/
│   ├── archive.cpp
│   ├── parser.cpp
│   ├── property_parser.cpp
│   ├── blueprint_parser.cpp
│   ├── output.cpp
│   └── main.cpp
└── README.md
```

## 特点

- **零外部依赖**：仅使用C++标准库，无需第三方库
- **手动JSON生成**：避免nlohmann/json依赖
- **跨平台**：Windows、Linux、macOS
- **C++20特性**：std::optional、std::variant、std::filesystem

## 与Python版本对比

| 特性 | Python | C++ |
|------|--------|-----|
| 代码行数 | ~2800 | ~2800 |
| 依赖 | 标准库 | 标准库 |
| JSON库 | json模块 | 手动生成 |
| 性能 | 较慢 | 更快 |
| 字节序 | struct模块 | 手动byteswap |

## 限制

- mmap支持待实现（Phase 6）
- 单元测试待添加（Phase 6）
- 复杂属性类型支持有限

## 参考

基于 UE 5.7 源码：
- PackageFileSummary.h
- ObjectResource.h
- PropertyTag.h
- Archive.h

## 许可

MIT License