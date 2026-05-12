# CLAUDE.md

Unreal Engine .uasset 文件解析器 — 让 AI 代理在不依赖 UE 编辑器的情况下读取蓝图内容。

## 快速参考

```bash
pip install -e ".[dev]"           # 安装
uasset-read file.uasset           # 解析文件
python -m pytest tests/ -v        # 测试
```

测试资产：`E:\Develop\lib\UnrealEngine\Samples\FirstPerson`

## 当前状态

**v6.0 完成** — 373 passed, 71 skipped, 0 failed。模块化包在 `src/uasset_read/`。

## 架构

管道：`.uasset → FArchive → Deserializer → Models → OutputFormatter`

扩展：GraphParser → AdvancedPropParser → DependencyGraphBuilder

| 模块 | 文件 | 说明 |
|------|------|------|
| FArchive | `archive.py` | 二进制读取器（字节交换/mmap） |
| 序列化 | `serializers/` | PackageSummary/Import/Export/PropertyTag |
| 数据模型 | `models/` | UEdGraph/Node/Pin + 属性数据类 |
| 解析器 | `parsers/` | 14 种属性类型 + 分派器 |
| 蓝图 | `blueprint/` | 变量/组件变换/元数据提取 |
| 图解析 | `graph/` | 执行流/数据流/连接映射 |
| 格式化 | `formatters/` | JSON/Text/Markdown/Mermaid |
| CLI | `cli.py` | argparse 入口 |
| 管线 | `parse_uasset.py` | 主编排函数 |

**技术栈**：Python 3.10+，零运行时依赖，setuptools + pytest。

## 文件组织

```
src/uasset_read/  # 源码    tests/          # 测试
.planning/        # 规划    output/debug/reports/  # 产物
uasset_read_cpp/  # C++参考 UnrealEngine/ LyraStarterGame/  # 外部（Git忽略）
```

## gsd-sdk 使用

仅支持 3 个命令：`run "<prompt>"` / `auto` / `init [input]`

**不支持** `query`、`list`、`get` 等子命令（会报错）。查 phase 信息请直接读 `.planning/` 文件或用 GSD slash commands。

## API 导出（通过 `from uasset_read import X`）

- **常量/异常**：`PACKAGE_FILE_TAG`, `MMAP_THRESHOLD`, `UAssetError`, `VersionError`, `ParseError`, `ErrorContext`
- **序列化**：`PackageFileSummary`, `PackageIndex`, `ObjectImport`, `ObjectExport`, `read_package_summary`, `read_name_table`, `read_import_map`, `read_export_map`, `detect_blueprint`, `FArchive`, `PropertyTag`
- **数据模型**：`UEdGraph`, `UEdGraphNode`, `UEdGraphPin`, `FEdGraphPinType`, `FMemberReference`, `K2NodeCallFunction`, `K2NodeEvent`, `K2NodeKnot`, `EdGraphNodeComment`, `K2NodeEnhancedInputAction`, `ParseResult`, `StatusInfo`
- **蓝图**：`BlueprintMetadata`, `BlueprintVariable`, `BlueprintFunction`, `BlueprintEvent`, `extract_blueprint_variables`, `parse_component_transform`, `extract_blueprint_metadata`
- **属性**：`PropertyValue`, `StructValue`, `MapValue`, `SetValue`, `EnumValue`, `TextValue`, `DelegateValue`, `parse_property_value`, `parse_properties_from_export`, `parse_bool/int/float/str/array/struct/map_property`
- **管线**：`parse_uasset`
- **图解析**：`extract_blueprint_graphs`, `build_execution_flows`, `build_data_flows`, `build_connections_map`
- **格式化**：`format_json_full/summary`, `format_text_full/summary`, `format_markdown`, `format_graphs_json`, `build_status_info`, `build_schema_info`
- **CLI**：`python -m uasset_read` 或 `uasset-read`

## 规划文档

- `.planning/ROADMAP.md` — 50 阶段路线图
- `.planning/STATE.md` — 当前里程碑状态
- `.planning/REQUIREMENTS.md` — 需求追溯
- `.planning/PROJECT.md` — 项目概览
- `.planning/MILESTONES.md` — 历史里程碑
