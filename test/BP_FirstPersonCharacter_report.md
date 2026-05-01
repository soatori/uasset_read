# BP_FirstPersonCharacter.uasset 解析报告

## 文件信息

- **文件路径**: `E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset`
- **文件大小**: 138,384 bytes
- **解析时间**: 2026-05-02

## 解析状态

| 项目 | 结果 |
|------|------|
| 解析成功 | ✓ True |
| 版本 | UE4=522, UE5=1017 |
| Legacy版本 | -9 |
| 包名 | `/Game/FirstPerson/Blueprints/BP_FirstPersonCharacter` |
| Package Flags | 0x00040000 (262144) |
| 名称表数量 | 368 |
| 导入表数量 | 73 |
| 导出表数量 | 69 |

## 发现的问题

### 1. SerialSize 数值异常

导出表中 `serial_size` 字段值异常大，例如：
- Export 0: 197,568,757,801 bytes
- Export 2: 8,654,359,101,451 bytes

这些数值远超文件总大小（138KB），表明导出表解析存在 bug。

**可能原因**：
- ExportMap 偏移量解析错误
- i64 字段读取位置不正确
- UE5+ 脚本序列化字段（ScriptSerialSize/ScriptSerialOffset）处理问题

### 2. 蓝图元数据提取失败

错误信息：
```
blueprint extraction error: Offset 321555611516928 exceeds file size 138384 at seek
```

偏移值 `321555611516928` 明显无效，表明导出数据偏移解析有问题。

## 导出表初步分析

从解析结果看，导出表似乎存在重复条目和异常命名：
- 多个导出名为 `/Game/FirstPerson/Blueprints/BP_FirstPersonCharacter`
- 类名包含异常后缀如 `_329`, `_55`, `_4294967235`

正常情况下，蓝图资产应该有明确的类继承关系，而非这些异常值。

## 技术细节

### UE 版本信息

| 版本类型 | 值 | 说明 |
|----------|-----|------|
| FileVersionUE4 | 522 | VER_UE4_AUTOMATIC_VERSION_FROM_PACKAGE |
| FileVersionUE5 | 1017 | UE5.OS_SUB_OBJECT_SHADOW_SERIALIZATION |
| LegacyFileVersion | -9 | 最新的 UE5 格式 |

### 解析器代码位置

相关源码位置（uasset_read.py）：
- `read_export_map()`: 行 1267-1330
- `extract_blueprint_metadata()`: 行 1643-1737

## 下一步建议

1. **验证 ExportOffset**：检查 header 中的 `export_offset` 是否正确
2. **调试导出表读取**：添加详细日志跟踪每个导出条目的解析位置
3. **检查 UE5 字段**：验证 `script_serial_size` 和 `script_serial_offset` 的读取逻辑
4. **对比 UE 源码**：确认 ObjectResource.h 中 FObjectExport 的序列化顺序

## 附录：原始数据

已生成以下文档文件：
- `BP_FirstPersonCharacter.json` - JSON 格式完整输出
- `BP_FirstPersonCharacter.txt` - YAML 格式文本输出

---

**生成工具**: uasset_read.py Phase 1-4
**报告日期**: 2026-05-02