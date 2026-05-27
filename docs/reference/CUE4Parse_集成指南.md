# CUE4Parse 编译与集成实施指南

## 1. 编译步骤

### 1.1 环境要求

- **.NET SDK**: 8.0 或更高版本（CUE4Parse 目标框架为 `net8.0`）
- 系统已安装 .NET 10.0.204 SDK + .NET 8.0.27 运行时，可以直接编译
- **CMake**: 不需要（CUE4Parse-Natives 是可选的本地库，用于音频解码，蓝图解析不需要）

### 1.2 克隆仓库

```bash
git clone https://github.com/FabianFG/CUE4Parse.git --recursive
cd CUE4Parse
```

`--recursive` 很重要，因为 CUE4Parse-Natives 是子模块。

### 1.3 验证编译

```bash
# 恢复 NuGet 包
dotnet restore CUE4Parse.Example/CUE4Parse.Example.csproj

# 编译 Release 版本
dotnet build CUE4Parse.Example/CUE4Parse.Example.csproj -c Release
```

编译输出：
- `CUE4Parse.dll` — 核心解析库
- `CUE4Parse-Conversion.dll` — 资源转换库（纹理/网格/音频导出）
- `CUE4Parse.Example.dll` — 示例入口点

### 1.4 发布为独立 EXE

```bash
# 方式 A：自包含单文件（约 80MB，不依赖 .NET 运行时）
dotnet publish CUE4Parse.Example/CUE4Parse.Example.csproj \
  -c Release \
  -r win-x64 \
  --self-contained true \
  -p:PublishSingleFile=true \
  -o ./publish

# 方式 B：框架依赖（约 2MB，需要 .NET 8.0 运行时）
dotnet publish CUE4Parse.Example/CUE4Parse.Example.csproj \
  -c Release \
  -r win-x64 \
  --self-contained false \
  -o ./publish
```

方式 A 的产物：
```
publish/
  CUE4Parse.Example.exe   (80MB)
  blake3_dotnet.dll
  libSkiaSharp.dll
```

方式 B 的产物：
```
publish/
  CUE4Parse.Example.exe       (2MB)
  CUE4Parse.dll
  CUE4Parse-Conversion.dll
  <各种依赖 DLL>
```

**推荐方式 B**，因为我们的 Python 集成场景下 exe 体积更小，且 .NET 8.0 运行时已经安装。

---

## 2. 编写自定义 CLI 工具

CUE4Parse 自带的 Example 项目是为 Fortnite PAK 提取设计的，**不能直接用于单文件 .uasset 解析**。我们需要编写一个专用的 CLI 入口。

### 2.1 项目结构

```
CUE4Parse/
  CUE4Parse/              # 核心库（不变）
  CUE4Parse-Conversion/   # 转换库（不变）
  BPExtractor/            # 新增：我们的 CLI 工具
    BPExtractor.csproj
    Program.cs
    BlueprintNodeExtractor.cs
    Models/
      BlueprintNode.cs
      BlueprintPin.cs
      BlueprintGraph.cs
```

### 2.2 BPExtractor.csproj

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net8.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
    <AllowUnsafeBlocks>true</AllowUnsafeBlocks>
  </PropertyGroup>

  <ItemGroup>
    <ProjectReference Include="..\CUE4Parse\CUE4Parse.csproj" />
  </ItemGroup>

  <ItemGroup>
    <PackageReference Include="Newtonsoft.Json" Version="13.0.4" />
  </ItemGroup>
</Project>
```

### 2.3 Program.cs — 命令行入口

```csharp
using System;
using System.IO;
using System.Linq;
using CUE4Parse.FileProvider;
using CUE4Parse.UE4.Assets.Exports.EdGraph;
using CUE4Parse.UE4.Versions;
using Newtonsoft.Json;

namespace BPExtractor;

public static class Program
{
    public static int Main(string[] args)
    {
        if (args.Length < 1)
        {
            Console.Error.WriteLine("Usage: BPExtractor.exe <path-to-uasset> [--ue-version UE5_5]");
            Console.Error.WriteLine("  --ue-version: UE5_0 to UE5_7 (default: UE5_5)");
            return 1;
        }

        var uassetPath = args[0];
        if (!File.Exists(uassetPath))
        {
            Console.Error.WriteLine($"Error: File not found: {uassetPath}");
            return 1;
        }

        // Parse UE version argument
        var ueVersion = EGame.GAME_UE5_5;  // default
        for (int i = 1; i < args.Length; i++)
        {
            if (args[i] == "--ue-version" && i + 1 < args.Length)
            {
                i++;
                ueVersion = args[i].ToUpper() switch
                {
                    "UE5_0" => EGame.GAME_UE5_0,
                    "UE5_1" => EGame.GAME_UE5_1,
                    "UE5_2" => EGame.GAME_UE5_2,
                    "UE5_3" => EGame.GAME_UE5_3,
                    "UE5_4" => EGame.GAME_UE5_4,
                    "UE5_5" => EGame.GAME_UE5_5,
                    "UE5_6" => EGame.GAME_UE5_6,
                    "UE5_7" => EGame.GAME_UE5_7,
                    _ => EGame.GAME_UE5_5
                };
            }
        }

        try
        {
            var extractor = new BlueprintNodeExtractor();
            var result = extractor.Extract(uassetPath, ueVersion);

            var json = JsonConvert.SerializeObject(result, Formatting.Indented);
            Console.WriteLine(json);
            return 0;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"Extraction failed: {ex.Message}");
            Console.Error.WriteLine(ex.StackTrace);
            return 2;
        }
    }
}
```

### 2.4 BlueprintNodeExtractor.cs — 核心提取逻辑

```csharp
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using CUE4Parse.FileProvider;
using CUE4Parse.UE4.Assets;
using CUE4Parse.UE4.Assets.Exports;
using CUE4Parse.UE4.Assets.Exports.EdGraph;
using CUE4Parse.UE4.Objects.Engine.EdGraph;
using CUE4Parse.UE4.Versions;
using BPExtractor.Models;

namespace BPExtractor;

public class BlueprintNodeExtractor
{
    public BlueprintGraphResult Extract(string uassetPath, EGame ueVersion)
    {
        var dir = Path.GetDirectoryName(uassetPath)!;
        var fileName = Path.GetFileName(uassetPath);

        // DefaultFileProvider 需要一个目录，扫描其中的 .uasset 文件
        var provider = new DefaultFileProvider(
            dir,
            SearchOption.TopDirectoryOnly,
            new VersionContainer(ueVersion));

        provider.Initialize();

        // 包路径: 相对于 Content 目录的路径，不含扩展名
        // 对于独立文件，使用文件名（不含扩展名）作为包名
        var packagePath = Path.GetFileNameWithoutExtension(fileName);

        var package = provider.LoadPackage(packagePath);
        var exports = package.GetExports().ToList();

        var nodes = new List<BlueprintNodeDto>();
        var graphs = new List<string>();
        string blueprintClass = null!;

        foreach (var export in exports)
        {
            // 收集 BlueprintGeneratedClass 信息
            if (export.ExportType.Contains("BlueprintGeneratedClass"))
            {
                blueprintClass = export.Name;

                // 尝试获取 UberGraphFunction 引用
                if (export.TryGetLazy<string>("UbergraphFunction", out var uberGraph))
                {
                    graphs.Add(uberGraph);
                }
            }

            // 提取 UEdGraphNode（包括 UK2Node 子类）
            if (export is UEdGraphNode node)
            {
                nodes.Add(ExtractNode(node));
            }
        }

        // 对于没有被 CUE4Parse 强类型识别的节点（泛型 UObject）,
        // 通过 ExportType 检查是否为 EdGraph 相关对象
        foreach (var export in exports)
        {
            if (export is UEdGraphNode) continue; // already processed

            if (export.ExportType.StartsWith("K2Node_") ||
                export.ExportType.StartsWith("EdGraph") ||
                export.ExportType == "EdGraph" ||
                export.ExportType.Contains("GraphNode"))
            {
                // 这些对象作为泛型 UObject 加载，从 Properties 提取数据
                nodes.Add(ExtractGenericNode(export));
            }
        }

        return new BlueprintGraphResult
        {
            PackageName = package.Name,
            BlueprintClass = blueprintClass,
            Graphs = graphs,
            NodeCount = nodes.Count,
            Nodes = nodes,
            Warnings = new List<string>()
        };
    }

    private BlueprintNodeDto ExtractNode(UEdGraphNode node)
    {
        // NodePosX / NodePosY 存储在 UObject 的 Properties 列表中
        // 通过 GetOrDefault<float>() 访问
        var nodePosX = node.GetOrDefault<float>("NodePosX", 0f);
        var nodePosY = node.GetOrDefault<float>("NodePosY", 0f);
        var nodeGuid = node.GetOrDefault<Guid>("NodeGuid");

        var pins = new List<BlueprintPinDto>();

        // Pins 数组在 UEdGraphNode.Deserialize() 中已填充
        // 每个 Pin 是 UEdGraphPinReference? 类型，需要解析
        foreach (var pinRef in node.Pins)
        {
            if (pinRef is null) continue;

            if (pinRef is UEdGraphPin pin)
            {
                pins.Add(ExtractPin(pin));
            }
        }

        return new BlueprintNodeDto
        {
            Type = node.ExportType,
            Name = node.Name,
            NodePosX = nodePosX,
            NodePosY = nodePosY,
            NodeGuid = nodeGuid == Guid.Empty ? null : nodeGuid.ToString(),
            Pins = pins,
            // FunctionReference 对于 CallFunction 等节点
            FunctionName = node.GetOrDefault<string>("FunctionReference"),
        };
    }

    private BlueprintNodeDto ExtractGenericNode(UObject export)
    {
        // 对于未被强类型映射的节点类型，从 Properties 提取
        var nodePosX = export.GetOrDefault<float>("NodePosX", 0f);
        var nodePosY = export.GetOrDefault<float>("NodePosY", 0f);
        var nodeGuid = export.GetOrDefault<Guid?>("NodeGuid");

        return new BlueprintNodeDto
        {
            Type = export.ExportType,
            Name = export.Name,
            NodePosX = nodePosX,
            NodePosY = nodePosY,
            NodeGuid = nodeGuid?.ToString(),
            Pins = new List<BlueprintPinDto>(), // Pins 需要特殊处理
            FunctionName = null,
            Note = "Extracted as generic UObject - pin data may require property-level parsing"
        };
    }

    private BlueprintPinDto ExtractPin(UEdGraphPin pin)
    {
        var linkedTo = pin.LinkedTo
            .Where(p => p != null)
            .Select(p => p!.ToString() ?? "unknown")
            .ToList();

        return new BlueprintPinDto
        {
            PinId = pin.PersistentGuid.ToString(),
            PinName = pin.PinName.Text,
            Direction = pin.Direction.ToString(),
            PinCategory = pin.PinType.PinCategory.Text,
            PinSubCategory = pin.PinType.PinSubCategory.Text,
            DefaultValue = pin.DefaultValue,
            LinkedTo = linkedTo,
            IsReference = pin.PinType.bIsReference,
            IsConst = pin.PinType.bIsConst,
            ContainerType = pin.PinType.ContainerType.ToString()
        };
    }
}
```

### 2.5 Models/BlueprintGraph.cs — 输出 DTO

```csharp
using System.Collections.Generic;

namespace BPExtractor.Models;

public class BlueprintGraphResult
{
    public string PackageName { get; set; } = "";
    public string? BlueprintClass { get; set; }
    public List<string> Graphs { get; set; } = new();
    public int NodeCount { get; set; }
    public List<BlueprintNodeDto> Nodes { get; set; } = new();
    public List<string> Warnings { get; set; } = new();
}

public class BlueprintNodeDto
{
    public string Type { get; set; } = "";
    public string Name { get; set; } = "";
    public float NodePosX { get; set; }
    public float NodePosY { get; set; }
    public string? NodeGuid { get; set; }
    public string? FunctionName { get; set; }
    public List<BlueprintPinDto> Pins { get; set; } = new();
    public string? Note { get; set; }
}

public class BlueprintPinDto
{
    public string PinId { get; set; } = "";
    public string PinName { get; set; } = "";
    public string Direction { get; set; } = "";
    public string PinCategory { get; set; } = "";
    public string PinSubCategory { get; set; } = "";
    public string? DefaultValue { get; set; }
    public List<string> LinkedTo { get; set; } = new();
    public bool IsReference { get; set; }
    public bool IsConst { get; set; }
    public string ContainerType { get; set; } = "";
}
```

### 2.6 编译自定义 CLI

```bash
cd CUE4Parse
dotnet build BPExtractor/BPExtractor.csproj -c Release

# 发布为框架依赖模式（推荐，体积小）
dotnet publish BPExtractor/BPExtractor.csproj \
  -c Release \
  -r win-x64 \
  --self-contained false \
  -o ./bp-extractor-publish
```

### 2.7 命令行调用示例

```bash
# 基本用法
BPExtractor.exe "E:\Develop\uasset_resolver\BP_FirstPersonCharacter.uasset"

# 指定 UE 版本
BPExtractor.exe "E:\Develop\uasset_resolver\BP_FirstPersonCharacter.uasset" --ue-version UE5_5

# 输出到文件
BPExtractor.exe "path\to\Blueprint.uasset" > output.json
```

**预期 JSON 输出格式：**

```json
{
  "PackageName": "BP_FirstPersonCharacter",
  "BlueprintClass": "BP_FirstPersonCharacter_C",
  "Graphs": ["Ubergraph BP_FirstPersonCharacter_C"],
  "NodeCount": 15,
  "Nodes": [
    {
      "Type": "K2Node_Event",
      "Name": "K2Node_Event_0",
      "NodePosX": -224.0,
      "NodePosY": -16.0,
      "NodeGuid": "A1B2C3D4-...",
      "FunctionName": "ReceiveBeginPlay",
      "Pins": [
        {
          "PinId": "...",
          "PinName": "then",
          "Direction": "EGPD_Output",
          "PinCategory": "exec",
          "PinSubCategory": "",
          "DefaultValue": null,
          "LinkedTo": ["K2Node_CallFunction_1  ABCD1234"],
          "IsReference": false,
          "IsConst": false,
          "ContainerType": "None"
        }
      ]
    }
  ],
  "Warnings": []
}
```

---

## 3. Python 集成方案

### 3.1 subprocess 调用封装

```python
"""
BPExtractor Python 集成模块
通过 subprocess 调用 CUE4Parse 编译的 BPExtractor.exe，
解析 .uasset 蓝图文件并返回结构化数据。
"""

import json
import subprocess
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Pin:
    """蓝图引脚"""
    pin_id: str
    pin_name: str
    direction: str          # "EGPD_Input" | "EGPD_Output"
    pin_category: str       # "exec", "object", "float", "bool", ...
    pin_sub_category: str   # 具体类型
    default_value: Optional[str] = None
    linked_to: list[str] = field(default_factory=list)
    is_reference: bool = False
    is_const: bool = False
    container_type: str = ""


@dataclass
class BlueprintNode:
    """蓝图节点"""
    node_type: str
    name: str
    pos_x: float = 0.0
    pos_y: float = 0.0
    node_guid: Optional[str] = None
    function_name: Optional[str] = None
    pins: list[Pin] = field(default_factory=list)
    note: Optional[str] = None


@dataclass
class BlueprintGraph:
    """蓝图图表（整个 .uasset 的提取结果）"""
    package_name: str
    blueprint_class: Optional[str] = None
    graphs: list[str] = field(default_factory=list)
    nodes: list[BlueprintNode] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class BPExtractorError(Exception):
    """提取失败时的异常"""
    pass


class BPExtractor:
    """
    BPExtractor CLI 封装器。

    用法:
        extractor = BPExtractor(exe_path="./bp-extractor/BPExtractor.exe")
        graph = extractor.extract("path/to/Blueprint.uasset")
        for node in graph.nodes:
            print(f"{node.name} @ ({node.pos_x}, {node.pos_y})")
    """

    def __init__(
        self,
        exe_path: str | Path = "./bp-extractor-publish/BPExtractor.exe",
        ue_version: str = "UE5_5",
        timeout: int = 30,
    ):
        self.exe_path = Path(exe_path)
        self.ue_version = ue_version
        self.timeout = timeout

        if not self.exe_path.exists():
            raise FileNotFoundError(
                f"BPExtractor.exe not found at {self.exe_path}. "
                f"Compile first: dotnet publish BPExtractor/..."
            )

    def extract(self, uasset_path: str | Path) -> BlueprintGraph:
        """
        提取 .uasset 文件中的蓝图节点信息。

        Args:
            uasset_path: .uasset 文件的绝对路径

        Returns:
            BlueprintGraph: 结构化的蓝图图表数据

        Raises:
            BPExtractorError: 提取失败
            FileNotFoundError: .uasset 文件不存在
        """
        uasset_path = Path(uasset_path)
        if not uasset_path.exists():
            raise FileNotFoundError(f"File not found: {uasset_path}")

        cmd = [
            str(self.exe_path),
            str(uasset_path),
            "--ue-version", self.ue_version,
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,  # 我们自己检查退出码
            )
        except subprocess.TimeoutExpired:
            raise BPExtractorError(
                f"Extraction timed out after {self.timeout}s for {uasset_path}"
            )
        except OSError as e:
            raise BPExtractorError(f"Failed to execute BPExtractor.exe: {e}")

        # 非零退出码 = 错误
        if result.returncode != 0:
            error_msg = result.stderr.strip() or "Unknown error"
            raise BPExtractorError(
                f"BPExtractor exited with code {result.returncode}: {error_msg}"
            )

        # 解析 JSON 输出
        try:
            raw = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise BPExtractorError(f"Invalid JSON output: {e}")

        return self._parse_result(raw)

    def _parse_result(self, raw: dict) -> BlueprintGraph:
        """将原始 JSON 解析为 BlueprintGraph 对象。"""
        graph = BlueprintGraph(
            package_name=raw.get("PackageName", ""),
            blueprint_class=raw.get("BlueprintClass"),
            graphs=raw.get("Graphs", []),
            warnings=raw.get("Warnings", []),
        )

        for node_data in raw.get("Nodes", []):
            pins = []
            for pin_data in node_data.get("Pins", []):
                pins.append(Pin(
                    pin_id=pin_data.get("PinId", ""),
                    pin_name=pin_data.get("PinName", ""),
                    direction=pin_data.get("Direction", ""),
                    pin_category=pin_data.get("PinCategory", ""),
                    pin_sub_category=pin_data.get("PinSubCategory", ""),
                    default_value=pin_data.get("DefaultValue"),
                    linked_to=pin_data.get("LinkedTo", []),
                    is_reference=pin_data.get("IsReference", False),
                    is_const=pin_data.get("IsConst", False),
                    container_type=pin_data.get("ContainerType", ""),
                ))

            graph.nodes.append(BlueprintNode(
                node_type=node_data.get("Type", ""),
                name=node_data.get("Name", ""),
                pos_x=node_data.get("NodePosX", 0.0),
                pos_y=node_data.get("NodePosY", 0.0),
                node_guid=node_data.get("NodeGuid"),
                function_name=node_data.get("FunctionName"),
                pins=pins,
                note=node_data.get("Note"),
            ))

        return graph

    def extract_to_dict(self, uasset_path: str | Path) -> dict:
        """
        提取并返回原始字典（不包装为 dataclass）。
        适合直接序列化为 JSON 或快速查看。
        """
        uasset_path = Path(uasset_path)
        cmd = [
            str(self.exe_path),
            str(uasset_path),
            "--ue-version", self.ue_version,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.timeout,
            check=True,
        )
        return json.loads(result.stdout)
```

### 3.2 使用示例

```python
from bp_extractor import BPExtractor, BPExtractorError

extractor = BPExtractor(
    exe_path="C:/UE4Parse/bp-extractor-publish/BPExtractor.exe",
    ue_version="UE5_5",
)

try:
    graph = extractor.extract("E:/Develop/uasset_resolver/BP_FirstPersonCharacter.uasset")

    print(f"Package: {graph.package_name}")
    print(f"Class: {graph.blueprint_class}")
    print(f"Nodes: {len(graph.nodes)}")
    print(f"Warnings: {graph.warnings}")

    # 打印所有节点的连线信息
    for node in graph.nodes:
        print(f"\n[{node.node_type}] {node.name} @ ({node.pos_x}, {node.pos_y})")
        if node.function_name:
            print(f"  Function: {node.function_name}")
        for pin in node.pins:
            if pin.linked_to:
                print(f"  Pin '{pin.pin_name}' -> {pin.linked_to}")

    # 输出为 JSON
    import json
    with open("blueprint_graph.json", "w") as f:
        # 从 dataclass 转为 dict
        output = {
            "package_name": graph.package_name,
            "blueprint_class": graph.blueprint_class,
            "nodes": [
                {
                    "type": n.node_type,
                    "name": n.name,
                    "pos": (n.pos_x, n.pos_y),
                    "guid": n.node_guid,
                    "function": n.function_name,
                    "pins": [
                        {
                            "name": p.pin_name,
                            "direction": p.direction,
                            "category": p.pin_category,
                            "linked_to": p.linked_to,
                        }
                        for p in n.pins
                    ],
                }
                for n in graph.nodes
            ],
        }
        json.dump(output, f, indent=2)

except BPExtractorError as e:
    print(f"Extraction failed: {e}")
```

### 3.3 错误处理策略

| 错误场景 | 退出码 | 处理方式 |
|---------|--------|---------|
| 文件不存在 | 1 | 调用前检查 `Path.exists()` |
| 解析失败（格式不支持） | 2 | 捕获 `BPExtractorError`，记录日志 |
| 超时（大文件 >30s） | N/A | `TimeoutExpired` 异常，增加 timeout |
| 缺少 .usmap 映射文件 | 2 | 检查 stderr 中 "mapping file is missing"，提示用户提供 |

---

## 4. 数据完整度评估

### 4.1 可提取的数据

| 数据项 | 支持程度 | 来源类 | 说明 |
|--------|---------|--------|------|
| **NodePosX / NodePosY** | ✅ 完全支持 | `UObject.Properties` → `GetOrDefault<float>()` | 作为 UObject 的属性序列化，通过属性名访问 |
| **NodeGuid** | ✅ 完全支持 | `UObject.Properties` | UE4.0+ 每个节点都有 GUID |
| **节点类型 (K2Node_Event, K2Node_CallFunction 等)** | ✅ 完全支持 | `UEdGraphNode.ExportType` | CUE4Parse 已内置 UEdGraphNode 和 UK2Node 类型映射 |
| **引脚名称 (PinName)** | ✅ 完全支持 | `UEdGraphPin.PinName` (FName) | |
| **引脚方向 (Direction)** | ✅ 完全支持 | `UEdGraphPin.Direction` (enum) | EGPD_Input / EGPD_Output |
| **引脚类型 (PinCategory)** | ✅ 完全支持 | `UEdGraphPin.PinType.PinCategory` | "exec", "object", "float", "bool", "struct" 等 |
| **引脚子类型 (PinSubCategory)** | ✅ 完全支持 | `UEdGraphPin.PinType.PinSubCategory` | 具体类名如 "K2Node_CallFunction" |
| **引脚连线 (LinkedTo)** | ✅ 完全支持 | `UEdGraphPin.LinkedTo[]` | 数组，包含引用其他 Pin 的引用 |
| **引脚默认值 (DefaultValue)** | ✅ 完全支持 | `UEdGraphPin.DefaultValue` | 字符串形式 |
| **引脚容器类型 (Array/Set/Map)** | ✅ 完全支持 | `UEdGraphPin.PinType.ContainerType` | |
| **函数引用 (FunctionReference)** | ✅ 部分支持 | `UObject.Properties` | 需要确认存储格式（可能是 FSimpleMemberReference 结构体） |
| **引脚 FriendlyName** | ⚠️ 条件支持 | `UEdGraphPin.PinFriendlyName` | 仅在 `!IsFilterEditorOnly` 时序列化 |
| **引脚 ToolTip** | ⚠️ 条件支持 | `UEdGraphPin.PinToolTip` | 同上 |
| **PersistentGuid (Pin)** | ⚠️ 条件支持 | `UEdGraphPin.PersistentGuid` | 仅在 `!IsFilterEditorOnly` 时序列化 |

### 4.2 限制与注意事项

#### 4.2.1 Editor-Only 数据过滤

CUE4Parse 的默认文件加载行为取决于 `IsFilterEditorOnly` 标志：

- **Cooked（已打包）的 .uasset**：Editor-only 数据（PinFriendlyName, PinToolTip, PersistentGuid）已被剥离
- **Uncooked（开发中）的 .uasset**：包含完整数据

**影响**：BP_FirstPersonCharacter.uasset 是未 cook 的开发文件，应该包含完整数据。

#### 4.2.2 .usmap 映射文件需求

UE5 的 .uasset 文件使用**无版本属性**（Unversioned Properties），需要 `.usmap` 映射文件来解析属性名到类型的对应关系。

- **有 .uproject 的项目文件**：可以通过 UnrealPak 生成 `.usmap`
- **独立 .uasset 文件**：没有映射文件时，CUE4Parse 可能无法正确解析无版本属性

**解决方案**：
1. 如果 .uasset 是有版本属性的（UE4.x 或特定 UE5 设置），不需要映射文件
2. 如果需要映射文件，可以使用 UnrealPak 从 .uproject 生成，或使用第三方工具如 `UEMappings`

#### 4.2.3 类型识别

CUE4Parse 通过内置的类名→类型映射来识别导出对象类型：

```csharp
// 已知类型 → 强类型对象
UEdGraphNode  → UEdGraphNode 实例（引脚数据完整解析）
UK2Node       → UK2Node 实例（继承 UEdGraphNode）

// 未知类型 → 泛型 UObject
K2Node_CustomXxx → UObject 实例（需要从 Properties 手动提取）
```

对于**蓝图自定义节点类型**（项目自定义的 K2Node 子类），CUE4Parse 会将其作为泛型 `UObject` 加载。NodePosX/NodePosY 仍然可以通过属性访问，但 Pins 数组需要手动从 Properties 中解析。

### 4.3 与 UE 编辑器方案的差距对比

| 能力 | CUE4Parse | UE 编辑器 (FLinkerLoad) |
|------|-----------|----------------------|
| 读取 .uasset 文件结构 | ✅ | ✅ |
| 提取节点位置 (PosX/PosY) | ✅ | ✅ |
| 提取引脚定义 | ✅ | ✅ |
| 提取连线关系 (LinkedTo) | ✅ | ✅ |
| 反序列化 Kismet 字节码 | ⚠️ 部分（基础表达式） | ✅ 完整 |
| 读取 Editor-only 标签 | ⚠️ 取决于文件状态 | ✅ 完整 |
| 提取宏图 / 函数图 | ✅ | ✅ |
| 实时编辑器交互 | ❌ | ✅ |
| 编译/验证蓝图 | ❌ | ✅ |
| 需要安装 UE 编辑器 | ❌ | ✅ |
| 独立运行 | ✅ | ❌ |

**结论**：对于**读取蓝图节点结构**这个目标，CUE4Parse 的能力已经足够。唯一需要注意的潜在问题是 .usmap 映射文件的可用性。

### 4.4 关键风险：.usmap 映射文件

测试文件 `BP_FirstPersonCharacter.uasset` 是 UE5.x 文件。如果它使用无版本属性（`PKG_UnversionedProperties` 标志），CUE4Parse **需要** `.usmap` 映射文件才能正确解析。

**验证方法**：

```python
# 先尝试直接解析，如果失败则检查错误信息
try:
    graph = extractor.extract("BP_FirstPersonCharacter.uasset")
    print(f"Success: {len(graph.nodes)} nodes extracted")
except BPExtractorError as e:
    if "mapping file" in str(e).lower() or "unversioned" in str(e).lower():
        print("需要 .usmap 映射文件。请从 UE 编辑器生成或提供映射文件。")
    else:
        raise
```

**生成 .usmap 的方法**（如果有 UE 编辑器）：
```bash
# 通过 UnrealPak 命令行工具
UnrealPak.exe -GenerateMapping=YourProject.usmap YourProject.uproject
```

---

## 5. 推荐实施路径

### 阶段 1：验证可行性（1-2 天）

1. 编译 CUE4Parse + BPExtractor CLI
2. 对 `BP_FirstPersonCharacter.uasset` 进行实际测试
3. 检查是否需要 .usmap 映射文件
4. 验证 JSON 输出中 NodePosX/NodePosY/Pins/LinkedTo 的完整性

### 阶段 2：Python 集成（1 天）

1. 实现 `bp_extractor.py` 封装模块
2. 编写单元测试（用测试 .uasset 文件）
3. 集成到现有的 uasset_resolver 流程

### 阶段 3：兜底方案（如果需要 .usmap）

1. 方案 A：使用 UE 编辑器命令行生成 .usmap
2. 方案 B：切换到纯 Python 解析方案（参考现有 FLinkerLoad 实现）
3. 方案 C：使用 UE 编辑器的 `-unattended` 模式导出蓝图文本

---

## 6. 已验证的编译信息

| 项目 | 值 |
|------|-----|
| 仓库 | https://github.com/FabianFG/CUE4Parse |
| 最新版本 | 1.2.2 |
| 目标框架 | .NET 8.0 |
| 编译 SDK | .NET 10.0.204（兼容） |
| 编译结果 | 0 错误，0 警告（Natives 子模块跳过，不影响蓝图解析） |
| 发布产物（自包含） | CUE4Parse.Example.exe ~80MB |
| 发布产物（框架依赖） | ~2MB + DLLs |
| 许可证 | Apache 2.0 |
| NuGet 包 | `dotnet add package CUE4Parse` |
