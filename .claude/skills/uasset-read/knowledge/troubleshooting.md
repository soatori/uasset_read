# Troubleshooting - 故障排除指南

本文档提供 uasset_read 解析常见问题和解决方案，帮助 AI 和用户正确处理解析错误。

**API版本:** output_version: "3.0" (Phase 14冻结)

---

## 1. 常见错误类型

### 1.1 解析状态判断

使用 `status.status` 字段判断解析结果：

| 状态 | 含义 | 处理方式 |
|------|------|----------|
| `success` | 解析成功，无错误 | 正常使用数据 |
| `fail` | 有解析错误，部分结果可用 | 检查 `errors` 字段，使用可用数据 |
| `error` | 无法解析，严重错误 | 检查错误原因，尝试其他资产 |

### 1.2 错误类型分类

| 错误类型 | 错误类 | 常见原因 |
|----------|--------|----------|
| `VersionError` | 版本不兼容 | UE版本过新或过旧 |
| `ParseError` | 解析失败 | 文件损坏、格式异常 |
| `FileNotFoundError` | 文件不存在 | 路径错误 |
| `PermissionError` | 权限问题 | 文件锁定、无读取权限 |

### 1.3 状态检查代码

```python
from uasset_read import parse_uasset

result = parse_uasset("MyBlueprint.uasset")

# 检查解析状态
if result.status.status == "success":
    print("解析成功")

elif result.status.status == "fail":
    print("解析部分失败")
    for error in result.errors:
        print(f"错误: {error}")
    print("部分数据仍可使用")

elif result.status.status == "error":
    print("解析严重失败")
    for error in result.errors:
        print(f"错误: {error}")
```

---

## 2. Cooked资产识别

### 2.1 Cooked vs Uncooked区别

| 资产类型 | 蓝图数据 | EventGraph | 典型来源 |
|----------|----------|------------|----------|
| **Uncooked** | 完整保留 | ✓ 可解析 | 编辑器保存、Content目录 |
| **Cooked** | 已剥离 | ✗ 不可解析 | 打包游戏、Pak文件 |

**关键区别：**
- Cooked 资产为游戏运行优化，删除了编辑器专用数据
- EventGraph、蓝图变量等在 Cooked 资产中不可见
- uasset_read 专注于 **Uncooked** 资产解析

### 2.2 判断资产是否Cooked

**方法1：检查graphs字段**

```python
result = parse_uasset("MyBlueprint.uasset")

if result.is_success:
    if not result.graphs:
        print("未找到EventGraph — 可能是Cooked资产")
    else:
        print(f"找到 {len(result.graphs)} 个执行图")
```

**方法2：检查蓝图类属性**

```python
for export in result.export_map:
    if "BlueprintGeneratedClass" in export.class_name:
        if not export.properties:
            print("蓝图类无属性 — 可能是Cooked资产")
        else:
            print(f"蓝图类有 {len(export.properties)} 个属性")
```

### 2.3 Cooked资产处理方案

**方案1：使用Uncooked资产**
- 从 UE 编辑器保存的 Content 目录获取
- 使用源码项目的资产而非打包版本

**方案2：接受部分数据**
- Cooked 资产仍可解析文件头（PackageFileSummary）
- name_map、import_map 通常可用
- 导出对象名称可获取，但属性不完整

```python
# Cooked资产部分数据可用
result = parse_uasset("CookedAsset.uasset")

if result.status.status == "fail":
    print("Cooked资产解析不完整")
    print(f"资产名称: {result.summary.package_name}")  # 通常可用
    print(f"导出数: {len(result.export_map)}")        # 通常可用
    # 但 graphs、properties 不可用
```

---

## 3. 解析失败诊断

### 3.1 常见解析失败原因

| 原因 | 错误信息 | 解决方案 |
|------|----------|----------|
| 版本不支持 | `Unsupported UE5 version: XXX` | 更新解析器或使用其他版本资产 |
| 文件损坏 | `Invalid package tag: XXX` | 重新保存资产 |
| 偏移量无效 | `Offset validation failed` | 文件结构异常，检查资产完整性 |
| 名称表过大 | `Name count exceeds maximum` | 大型资产，可能需要调整限制 |

### 3.2 errors字段分析

```python
result = parse_uasset("ProblemAsset.uasset")

# 分析错误详情
for error in result.errors:
    print(f"错误类型: {type(error).__name__}")
    print(f"错误内容: {str(error)}")

    # 根据错误类型判断
    if "version" in str(error).lower():
        print("  → 版本问题，检查UE版本兼容性")
    elif "offset" in str(error).lower():
        print("  → 偏移问题，文件结构可能异常")
    elif "tag" in str(error).lower():
        print("  → 文件格式问题，可能是损坏资产")
```

### 3.3 部分结果处理

即使 `status: fail`，部分结果可能仍然可用：

```python
result = parse_uasset("ProblemAsset.uasset")

if result.status.status == "fail":
    # 检查可用数据
    available = []

    if result.summary:
        available.append("文件头 (PackageFileSummary)")

    if result.name_map:
        available.append(f"名称表 ({len(result.name_map)}个)")

    if result.import_map:
        available.append(f"导入表 ({len(result.import_map)}个)")

    if result.export_map:
        available.append(f"导出表 ({len(result.export_map)}个)")

    if result.graphs:
        available.append(f"执行图 ({len(result.graphs)}个)")

    print("可用数据:")
    for item in available:
        print(f"  ✓ {item}")
```

---

## 4. 版本兼容问题

### 4.1 UE4 vs UE5版本差异

| 版本范围 | legacy_file_version | 支持状态 |
|----------|---------------------|----------|
| UE4 (4.0-4.27) | -3 到 -7 | ✓ 支持 |
| UE5 Early | -8, UE5 < 1004 | ✓ 支持 |
| UE5 5.0+ | -8, UE5 >= 1004 | ✓ 支持 |
| 未来版本 | 可能超出范围 | ⚠ 可能不支持 |

### 4.2 legacy_file_version字段

```python
result = parse_uasset("MyBlueprint.uasset")

# 获取版本信息
summary = result.summary

print(f"legacy_file_version: {summary.legacy_file_version}")
print(f"file_version_ue4: {summary.file_version_ue4}")
print(f"file_version_ue5: {summary.file_version_ue5}")

# 判断UE版本
if summary.legacy_file_version <= -8:
    print("UE5 资产")
    print(f"UE5具体版本: {summary.file_version_ue5}")
else:
    print("UE4 资产")
    print(f"UE4具体版本: {summary.file_version_ue4}")
```

### 4.3 版本不兼容处理

```python
from uasset_read import parse_uasset, VersionError

try:
    result = parse_uasset("NewVersionAsset.uasset")

    if not result.is_success:
        for error in result.errors:
            if isinstance(error, VersionError):
                print("版本不兼容")
                print(f"  建议: 使用其他版本的资产或更新解析器")

except VersionError as e:
    print(f"严重版本错误: {e}")
```

---

## 5. 常见问题FAQ

### Q1: 为什么看不到EventGraph？

**检查清单：**
1. 检查 `status.status` 是否为 `success` 或 `fail`
2. 检查 `graphs` 字段是否为空
3. 检查资产是否为 **Cooked** 状态

```python
result = parse_uasset("MyBlueprint.uasset")

# 检查步骤
if not result.is_success:
    print("解析未成功，检查errors字段")
elif not result.graphs:
    print("graphs字段为空")
    print("可能原因: Cooked资产、非蓝图资产")
else:
    print(f"找到 {len(result.graphs)} 个执行图")
```

### Q2: 为什么变量默认值是None？

**可能原因：**
1. 资产是 **Cooked** 状态
2. 变量类型不支持默认值提取（复杂对象引用）
3. 变量未设置默认值

```python
for export in result.export_map:
    for prop in export.properties:
        if prop.get("value") is None:
            print(f"变量 '{prop['name']}' 默认值不可用")
            print(f"  类型: {prop['type']}")
            print(f"  建议: 检查资产是否Cooked或类型是否支持")
```

### Q3: 如何获取完整属性而非摘要？

**使用 `format_json_full`：**

```python
from uasset_read import parse_uasset, format_json_full, format_json_summary

result = parse_uasset("MyBlueprint.uasset")

# 精简输出（默认，减少70%+ token）
summary = format_json_summary(result)
print(f"摘要导出数: {len(summary.get('exports_summary', []))}")

# 完整输出
full = format_json_full(result)
print(f"完整导出数: {len(full.get('exports', []))}")
print(f"完整属性数: {len(full['exports'][0]['properties'])}")
```

### Q4: 如何处理大型资产？

**大型资产可能触发限制：**

| 限制类型 | 默认值 | 调整方式 |
|----------|--------|----------|
| 名称数量 | 100000 | 代码中 MAX_NAME_COUNT |
| 导出数量 | 100000 | 代码中 MAX_EXPORT_COUNT |
| 导入数量 | 100000 | 代码中 MAX_IMPORT_COUNT |

**处理建议：**
- 分批处理大型资产目录
- 使用 `format_json_summary` 减少输出
- 关注核心导出对象而非全部

### Q5: 解析结果如何验证正确性？

**验证方法：**

1. **与UE编辑器对比**
   - 检查变量名称是否匹配
   - 检查父类名称是否正确
   - 检查组件数量是否一致

2. **使用测试资产**
   - FirstPerson模板资产有已知结构
   - 可与FirstPersonC C++版本对照

```python
# 使用已知资产验证
result = parse_uasset("BP_FirstPersonCharacter.uasset")

# 验证已知信息
assert result.is_success
assert "FirstPerson" in result.summary.package_name
assert len(result.graphs) > 0  # 应有EventGraph
```

---

## 6. 错误处理示例

### 6.1 完整错误处理代码

```python
from uasset_read import parse_uasset, UAssetError, VersionError, ParseError

def safe_parse_uasset(asset_path):
    """安全解析uasset文件，处理各种错误"""
    try:
        result = parse_uasset(asset_path)

        # 检查解析状态
        if result.status.status == "success":
            return {
                "success": True,
                "data": result,
                "message": "解析成功"
            }

        elif result.status.status == "fail":
            return {
                "success": False,
                "partial_data": result,
                "errors": result.errors,
                "message": "部分解析失败，有部分可用数据"
            }

        else:  # error
            return {
                "success": False,
                "errors": result.errors,
                "message": "解析严重失败"
            }

    except VersionError as e:
        return {
            "success": False,
            "error_type": "version",
            "message": f"版本不兼容: {e}"
        }

    except ParseError as e:
        return {
            "success": False,
            "error_type": "parse",
            "message": f"解析错误: {e}"
        }

    except FileNotFoundError:
        return {
            "success": False,
            "error_type": "file",
            "message": f"文件不存在: {asset_path}"
        }

    except Exception as e:
        return {
            "success": False,
            "error_type": "unknown",
            "message": f"未知错误: {e}"
        }

# 使用示例
result_info = safe_parse_uasset("MyBlueprint.uasset")

if result_info["success"]:
    print("解析成功")
    data = result_info["data"]
else:
    print(f"解析失败: {result_info['message']}")
    print(f"错误类型: {result_info.get('error_type', 'unknown')}")
```

### 6.2 部分结果利用示例

```python
def use_partial_result(result):
    """利用部分解析结果"""
    # 文件头通常可用
    if result.summary:
        print(f"资产名称: {result.summary.package_name}")
        print(f"UE版本: {result.summary.file_version_ue4 or result.summary.file_version_ue5}")

    # 名称表通常可用
    if result.name_map:
        print(f"名称数量: {len(result.name_map)}")
        # 搜索特定名称
        for name in result.name_map[:20]:
            print(f"  - {name}")

    # 导入表通常可用
    if result.import_map:
        print(f"导入数量: {len(result.import_map)}")
        # 分析依赖
        for imp in result.import_map[:10]:
            print(f"  依赖: {imp.object_name}")

    # 导出表通常可用
    if result.export_map:
        print(f"导出数量: {len(result.export_map)}")
        for exp in result.export_map:
            print(f"  导出: {exp.object_name} ({exp.class_name})")
```

---

## 7. 参考链接

- **蓝图语义:** [blueprint-semantics.md](blueprint-semantics.md)
- **节点类型:** [node-types.md](node-types.md)
- **常见模式:** [common-patterns.md](common-patterns.md)
- **基础用法:** [examples/basic-usage.md](../examples/basic-usage.md)

---

*API版本: output_version: "3.0"*
*Skill: uasset-read*
*最后更新: 2026-05-03*