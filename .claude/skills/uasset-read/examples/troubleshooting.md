# Troubleshooting - 错误处理示例

本文档演示 uasset_read skill 的错误处理场景和解决方案。

**API版本:** output_version: "3.0" (Phase 14冻结)

---

## 1. 错误处理基础

### 1.1 检查is_success字段

```python
from uasset_read import parse_uasset

result = parse_uasset("path/to/file.uasset")

if result.is_success:
    print(f"解析成功: {result.summary.package_name}")
else:
    print("解析失败！")
    for error in result.errors:
        print(f"  错误: {error}")
```

### 1.2 读取errors数组

```python
result = parse_uasset("ProblemAsset.uasset")

if not result.is_success:
    # 遍历所有错误
    for error in result.errors:
        print(f"错误类型: {type(error).__name__}")
        print(f"错误内容: {str(error)}")
```

### 1.3 status字段含义

```python
# 检查解析状态
result = parse_uasset("MyBlueprint.uasset")

status = result.status.status

if status == "success":
    print("解析成功，无错误")
elif status == "fail":
    print("部分解析失败，有部分数据可用")
    # 可使用部分数据
elif status == "error":
    print("严重错误，无法解析")
    # 检查资产有效性
```

---

## 2. Cooked资产问题

### 2.1 识别Cooked资产

```python
result = parse_uasset("GameAsset.uasset")

# 方法1：检查graphs字段
if result.is_success and not result.graphs:
    print("未找到EventGraph — 可能是Cooked资产")

# 方法2：检查蓝图类属性
for export in result.export_map:
    if "BlueprintGeneratedClass" in export.class_name:
        if not getattr(export, 'properties', []):
            print("蓝图类无属性 — 可能是Cooked资产")
```

### 2.2 Cooked资产处理

```python
def handle_cooked_asset(result):
    """处理Cooked资产部分结果"""
    if not result.graphs:
        print("Cooked资产：蓝图数据已剥离")
        print("可用数据:")

        # 文件头可用
        if result.summary:
            print(f"  ✓ 资产名称: {result.summary.package_name}")

        # 名称表可用
        if result.name_map:
            print(f"  ✓ 名称表: {len(result.name_map)}个")

        # 导出对象名称可用
        if result.export_map:
            print(f"  ✓ 导出对象: {len(result.export_map)}个")
            for export in result.export_map[:5]:
                print(f"    - {export.object_name}")

        print("\n不可用:")
        print("  ✗ EventGraph")
        print("  ✗ 蓝图变量详情")
        print("  ✗ 组件属性")
```

### 2.3 使用Uncooked资产

```python
# 推荐使用Uncooked资产
uncooked_path = "E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset"

result = parse_uasset(uncooked_path)

if result.is_success and result.graphs:
    print("Uncooked资产：完整蓝图数据可用")
    print(f"  EventGraph: {len(result.graphs)}个")
```

---

## 3. 常见解析错误

### 3.1 VersionError

```python
from uasset_read import parse_uasset, VersionError

try:
    result = parse_uasset("NewVersionAsset.uasset")

    if not result.is_success:
        for error in result.errors:
            if "version" in str(error).lower():
                print("版本不兼容")
                print(f"  建议: 使用支持的UE版本资产")

except VersionError as e:
    print(f"严重版本错误: {e}")
    print("  支持的版本: UE4 (legacy -3到-7), UE5 (-8+)")
```

### 3.2 ParseError

```python
from uasset_read import parse_uasset, ParseError

try:
    result = parse_uasset("CorruptedAsset.uasset")

    if not result.is_success:
        for error in result.errors:
            if "parse" in str(error).lower() or "offset" in str(error).lower():
                print("解析错误")
                print(f"  原因: {error}")
                print("  建议: 检查资产完整性或重新保存")

except ParseError as e:
    print(f"严重解析错误: {e}")
```

### 3.3 文件不存在错误

```python
from uasset_read import parse_uasset
import os

asset_path = "MissingAsset.uasset"

if not os.path.exists(asset_path):
    print(f"文件不存在: {asset_path}")
else:
    result = parse_uasset(asset_path)
```

---

## 4. 部分结果处理

### 4.1 利用可用数据

```python
result = parse_uasset("ProblemAsset.uasset")

if result.status.status == "fail":
    print("部分解析失败，检查可用数据...")

    # 文件头通常可用
    if result.summary:
        print(f"  ✓ 文件头可用: {result.summary.package_name}")
        print(f"    UE版本: {result.summary.file_version_ue4 or result.summary.file_version_ue5}")

    # 名称表通常可用
    if result.name_map:
        print(f"  ✓ 名称表可用: {len(result.name_map)}个")

    # 导入依赖通常可用
    if result.import_map:
        print(f"  ✓ 导入表可用: {len(result.import_map)}个")

    # 导出对象通常可用
    if result.export_map:
        print(f"  ✓ 导出表可用: {len(result.export_map)}个")

    # graphs可能不可用
    if result.graphs:
        print(f"  ✓ 执行图可用: {len(result.graphs)}个")
    else:
        print("  ✗ 执行图不可用")
```

### 4.2 部分数据分析示例

```python
def analyze_partial_result(result):
    """分析部分解析结果"""
    analysis = {"available": [], "unavailable": []}

    if result.summary:
        analysis["available"].append({
            "type": "summary",
            "data": f"Package: {result.summary.package_name}"
        })

    if result.name_map:
        analysis["available"].append({
            "type": "name_map",
            "count": len(result.name_map)
        })

    if result.import_map:
        analysis["available"].append({
            "type": "import_map",
            "count": len(result.import_map)
        })

    if result.export_map:
        analysis["available"].append({
            "type": "export_map",
            "count": len(result.export_map)
        })

    if not result.graphs:
        analysis["unavailable"].append("graphs (EventGraph)")

    if not any(getattr(e, 'properties', []) for e in result.export_map):
        analysis["unavailable"].append("properties (蓝图变量)")

    return analysis

# 使用示例
result = parse_uasset("CookedAsset.uasset")
analysis = analyze_partial_result(result)

print("可用数据:")
for item in analysis["available"]:
    if "count" in item:
        print(f"  ✓ {item['type']}: {item['count']}个")
    else:
        print(f"  ✓ {item['data']}")

print("\n不可用数据:")
for item in analysis["unavailable"]:
    print(f"  ✗ {item}")
```

---

## 5. 完整错误处理示例

### 5.1 安全解析函数

```python
from uasset_read import parse_uasset, VersionError, ParseError
import os

def safe_parse(asset_path):
    """安全解析uasset文件"""
    # 检查文件存在
    if not os.path.exists(asset_path):
        return {
            "success": False,
            "error": "file_not_found",
            "message": f"文件不存在: {asset_path}"
        }

    try:
        result = parse_uasset(asset_path)

        # 检查解析状态
        if result.status.status == "success":
            return {
                "success": True,
                "result": result,
                "message": "解析成功"
            }

        elif result.status.status == "fail":
            # 部分失败，返回可用数据
            return {
                "success": False,
                "partial": True,
                "result": result,
                "errors": result.errors,
                "message": "部分解析失败"
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
            "error": "version",
            "message": f"版本不兼容: {e}"
        }

    except ParseError as e:
        return {
            "success": False,
            "error": "parse",
            "message": f"解析错误: {e}"
        }

    except Exception as e:
        return {
            "success": False,
            "error": "unknown",
            "message": f"未知错误: {e}"
        }

# 使用示例
result_info = safe_parse("MyBlueprint.uasset")

if result_info["success"]:
    print("解析成功")
    data = result_info["result"]
    print(f"资产: {data.summary.package_name}")

elif result_info.get("partial"):
    print("部分成功")
    print(f"可用部分: {result_info['result'].summary.package_name}")

else:
    print(f"失败: {result_info['message']}")
```

---

## 6. 参考链接

- **故障排除知识库:** [../knowledge/troubleshooting.md](../knowledge/troubleshooting.md)
- **基础用法:** [basic-usage.md](basic-usage.md)
- **蓝图分析:** [blueprint-analysis.md](blueprint-analysis.md)

---

*API版本: output_version: "3.0"*
*Skill: uasset-read*
*最后更新: 2026-05-03*