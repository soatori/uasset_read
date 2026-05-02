# uasset_read

解析 Unreal Engine .uasset 文件的 Python 工具，使 AI 代理能够在不依赖 UE 编辑器的情况下读取蓝图内容。

## 功能

- **PackageFileSummary** — 文件头解析
- **NameMap** — 名称表提取
- **ImportMap** — 依赖映射
- **ExportMap** — 导出映射
- **蓝图图解析** — UEdGraph/Node/Pin 结构
- **高级属性** — Struct/Map/Set/Enum/Text/Delegate
- **依赖分析** — ImportMap + SoftObjectPaths 依赖图构建
- **循环依赖检测** — ImportMap 相互引用检测

## 安装

```bash
git clone https://github.com/soatori/uasset_read.git
cd uasset_read
```

零运行时依赖，仅需 Python 3.10+。

## 使用

### CLI

```bash
# 解析并输出 JSON
python -c "from uasset_read import parse_uasset; import json; r = parse_uasset('file.uasset'); print(json.dumps(r.to_dict(), indent=2))"
```

### Python API

```python
from uasset_read import parse_uasset, ParseResult

# 解析 .uasset 文件
result = parse_uasset('BP_FirstPersonCharacter.uasset')

# 访问解析数据
print(result.name_map)          # 名称表
print(result.import_map)        # 导入依赖
print(result.export_map)        # 导出表
print(result.blueprint)         # 蓝图信息
print(result.graphs)            # 蓝图图结构
print(result.dependencies)      # 依赖图
print(result.circular_deps)     # 循环依赖
```

## 测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行测试（简要）
python -m pytest tests/ --tb=short
```

测试覆盖：边界验证、蓝图提取、依赖分析、图解析、高级属性等（216+ 测试用例）。

## 架构

采用镜像 UE 的 FArchive 管道模式：

```
.uasset → FArchive → Deserializer → Models → OutputFormatter
                ↓ 扩展组件
          GraphParser (蓝图图)
          AdvancedPropParser (高级属性)
          DependencyGraphBuilder (依赖分析)
```

## 技术栈

- **语言**: Python 3.10+
- **依赖**: 零运行时依赖（仅标准库）
- **解析**: `struct` 二进制读取 + `mmap` 大文件支持
- **模型**: `dataclasses` + `asdict()` JSON 输出

## 限制

专注于未烘焙/编辑器保存的资产（包含完整蓝图数据）。烘焙后的资产仅包含烘焙数据，无蓝图源码。

## 许可证

MIT License